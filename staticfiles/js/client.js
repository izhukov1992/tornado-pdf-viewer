var form = document.getElementById("file");
var container = document.getElementById("content");
var socket = new WebSocket("ws://localhost:1337/files");

// Function update list of files and add handlers for links
function addFiles(data) {
    var content = "";

    if (!data.length) {
        // If there are no files, highlight this
        content += "<p>There are no any files</p>";
    }
    else {
        // Otherwise construct list of files in table
        content += "<p>Files:</p>";
        content += "<table>";
        data.forEach(function(file) {
            content += "<tr>";
            content += "<td>" + file.username + "</td>";
            content += "<td><a href='#' data-target='" + file.id + "' class='download'>" + file.filename + "</a></td>";
            content += "<td><a href='#' data-target='" + file.id + "' class='delete'>delete</a></td>";
            content += "</tr>";
        });
        content += "</table>";
    }

	// Update list of files
    container.innerHTML = content;

	// Get Download and Delete links objects
	var downloads = document.getElementsByClassName("download");
	var deletes = document.getElementsByClassName("delete");

	// Handle click on Download link
	for (var i = 0; i < downloads.length; i++) {
		downloads[i].addEventListener("click", function(e) {
			// Get ID of file
			var id = e.target.getAttribute("data-target");
			
			// Send Download event to server
			var data = JSON.stringify({action: 'download', file_id: id})
			socket.send(data);

			console.log("Download: " + id);
		}, false);
	}

	// Handle click on Delete link
	for (var i = 0; i < deletes.length; i++) {
		deletes[i].addEventListener("click", function(e) {
			// Get ID of file
			var id = e.target.getAttribute("data-target");
			
			// Send Delete event to server
			var data = JSON.stringify({action: 'delete', file_id: id})
			socket.send(data);

			console.log("Delete: " + id);
		}, false);
	}
};

socket.onopen = function() {
	console.log("Connection is opened.");
};

socket.onclose = function(event) {
	if (event.wasClean) {
		console.log("Connection successfully closed.");
	} else {
		console.log("Connection is aborted");
	}
	console.log("Code: " + event.code + " reason: " + event.reason);
};

socket.onerror = function(error) {
	console.log("Error " + error.message);
};

socket.onmessage = function(data) {
	var data = JSON.parse(data.data);
	addFiles(data);

	console.log("Data received " + data);
};
