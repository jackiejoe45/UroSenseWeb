function fetchData() {
    fetch('data.php')
        .then(response => response.json())
        .then(data => {
            // Update cards with data
        })
        .catch(error => console.error('Error fetching data:', error));
}

fetchData();
setInterval(fetchData, 5000);
