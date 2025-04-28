import base64
import io
import matplotlib.pyplot as plt
import sqlite3
from flask import request, jsonify, Flask
from flask_cors import CORS
import logging
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})


@app.route('/lab_results', methods=['GET'])
def lab_results():
    try:
        username = request.args.get('username')
        logger.info(
            f"Received request from {request.remote_addr} for username: {username}")

        conn = sqlite3.connect("lab_data.db", timeout=20)
        cursor = conn.cursor()

        if username:
            cursor.execute(
                "SELECT * FROM lab_results WHERE username = ?", (username,))
        else:
            cursor.execute("SELECT * FROM lab_results")

        data = cursor.fetchall()
        conn.close()

        if not data:
            logger.warning(f"No data found for username: {username}")
            return jsonify({"message": "No data found"}), 404

        column_names = ["record_time", "username", "bilirubin", "urobilinogen", "ketones",
                        "glucose", "protein", "blood", "nitrite", "ph", "specific_gravity", "leukocytes"]
        result = [dict(zip(column_names, row)) for row in data]
        logger.info(f"Returning {len(result)} records")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/predict/<biomarker>', methods=['GET'])
def predict_biomarker(biomarker):
    try:
        username = request.args.get('username')
        conn = sqlite3.connect("lab_data.db")

        # Get historical data
        query = f"SELECT record_time, {biomarker} FROM lab_results WHERE username = ? ORDER BY record_time"
        df = pd.read_sql_query(query, conn, params=(username,))
        conn.close()

        if len(df) < 6:  # Need at least 6 points for prediction
            return jsonify({"error": "Not enough data points"}), 400

        # Convert to numeric and handle any non-numeric values
        df[biomarker] = pd.to_numeric(df[biomarker], errors='coerce')
        df = df.dropna()

        # Create sliding window
        def create_sliding_window(data, n_steps=5):
            X, y = [], []
            for i in range(len(data) - n_steps):
                X.append(data[i:i + n_steps])
                y.append(data[i + n_steps])
            return np.array(X), np.array(y)

        data = df[biomarker].values
        X, y = create_sliding_window(data)
        model = LinearRegression()
        model.fit(X, y)

        # Predict future values
        future_values = []
        last_window = data[-5:]
        for _ in range(5):
            next_value = model.predict([last_window])[0]
            future_values.append(next_value)
            last_window = np.roll(last_window, -1)
            last_window[-1] = next_value

        # Create plot with last 10 points
        plt.figure(figsize=(10, 6))
        recent_data = data[-10:] if len(data) > 10 else data
        plt.plot(range(len(recent_data)), recent_data,
                 label='Historical Data', linewidth=2, color='#2196F3')
        future_index = range(len(recent_data), len(
            recent_data) + len(future_values))
        plt.plot(future_index, future_values,
                 label='Prediction', marker='o', linestyle='--', linewidth=2, color='#FF5722')

        # Add grid and styling
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.gca().set_facecolor('#f8f9fa')
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)

        # Add labels and title
        plt.xlabel('Time Step', fontsize=12, labelpad=10)
        plt.ylabel('Value', fontsize=12, labelpad=10)
        plt.title(f'{biomarker} Trend Prediction', fontsize=14, pad=20)

        # Position legend
        plt.legend(loc='upper left', frameon=True,
                   facecolor='white', edgecolor='none')

        # Adjust layout
        plt.tight_layout(pad=2.0)

        # Convert plot to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        plt.close('all')  # Close all figures to prevent memory leaks

        return jsonify({
            "image": base64.b64encode(buf.getvalue()).decode('utf-8'),
            "predictions": np.array(future_values).tolist()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/history', methods=['GET'])
def history():
    try:
        username = request.args.get('username')
        logger.info(
            f"Received history request from {request.remote_addr} for username: {username}")

        # Set a longer timeout for the database connection
        conn = sqlite3.connect("lab_data.db", timeout=30)
        cursor = conn.cursor()

        if username:
            cursor.execute(
                "SELECT * FROM lab_results WHERE username = ? ORDER BY record_time DESC LIMIT 50", (username,))
        else:
            cursor.execute(
                "SELECT * FROM lab_results ORDER BY record_time DESC LIMIT 50")

        data = cursor.fetchall()
        conn.close()

        if not data:
            logger.warning(f"No history data found for username: {username}")
            return jsonify({"message": "No history data found"}), 404

        column_names = ["record_time", "username", "bilirubin", "urobilinogen", "ketones",
                        "glucose", "protein", "blood", "nitrite", "ph", "specific_gravity", "leukocytes"]
        result = [dict(zip(column_names, row)) for row in data]
        logger.info(f"Returning {len(result)} history records")
        return jsonify(result)
    except Exception as e:
        logger.error(
            f"Error processing history request: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/submit_results', methods=['POST'])
def submit_results():
    try:
        data = request.get_json()
        logger.info(f"Received lab results from {request.remote_addr}: {data}")

        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['username', 'glucose', 'protein', 'ph', 'blood',
                           'specific_gravity', 'bilirubin', 'urobilinogen',
                           'ketones', 'nitrite', 'leukocytes']

        # Check for required fields
        missing_fields = [
            field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({"error": f"Missing required fields: {missing_fields}"}), 400

        conn = sqlite3.connect("lab_data.db", timeout=30)
        cursor = conn.cursor()

        # Insert the results
        cursor.execute("""
            INSERT INTO lab_results (
                record_time, username, bilirubin, urobilinogen, ketones,
                glucose, protein, blood, nitrite, ph, specific_gravity, leukocytes
            ) VALUES (
                datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            data['username'],
            data['bilirubin'],
            data['urobilinogen'],
            data['ketones'],
            data['glucose'],
            data['protein'],
            data['blood'],
            data['nitrite'],
            data['ph'],
            data['specific_gravity'],
            data['leukocytes']
        ))

        conn.commit()
        conn.close()

        return jsonify({"message": "Results saved successfully"}), 201
    except Exception as e:
        logger.error(f"Error saving results: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info("Starting Flask server on 0.0.0.0:5000")
    app.run(
        host='0.0.0.0',  # Allows external connections
        port=5000,
        debug=True,
        threaded=True    # Enable threading
    )

