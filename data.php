<?php
error_reporting(E_ALL);
ini_set('display_errors', 1);
header('Content-Type: application/json');

$db = new SQLite3('lab_data.db');

// Get the username from the request
$username = isset($_GET['username']) ? $_GET['username'] : '';

// Fetch the history records
$historyQuery = "SELECT * FROM lab_results WHERE username = :username ORDER BY record_time DESC";
$historyStmt = $db->prepare($historyQuery);
$historyStmt->bindValue(':username', $username, SQLITE3_TEXT);
$historyResult = $historyStmt->execute();
$historyRecords = array();
while ($row = $historyResult->fetchArray(SQLITE3_ASSOC)) {
    $historyRecords[] = $row;
}

$response = array();

if (count($historyRecords) > 0) {
    $response['latest'] = $historyRecords[0];
} else {
    $response['latest'] = null;
}

$response['history'] = $historyRecords;

// Return the data as JSON
echo json_encode($response);
?>
