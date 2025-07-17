// This script controls the webcam and sends the captured image to the server for fire analysis.

document.addEventListener("DOMContentLoaded", () => {
  const video = document.getElementById("camera-feed");
  const analyzeButton = document.getElementById("analyze-button");
  const contextList = document.getElementById("context-list");

  // Access the user's webcam
  navigator.mediaDevices.getUserMedia({ video: true })
      .then((stream) => {
          video.srcObject = stream;
      })
      .catch((err) => {
          console.error("Error accessing webcam: ", err);
      });

  analyzeButton.addEventListener("click", () => {
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext("2d");
      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Convert canvas to base64 image
      const imageData = canvas.toDataURL("image/jpeg");

      // Send image data to the server for analysis
      fetch("/process_image", {
          method: "POST",
          headers: {
              "Content-Type": "application/json"
          },
          body: JSON.stringify({ image_data: imageData })
      })
          .then((response) => response.json())
          .then((data) => {
              if (data.error) {
                  console.error("Error: ", data.error);
              } else {
                  // Display the fire detection context in the list
                  const listItem = document.createElement("li");
                  listItem.textContent = data.context;
                  contextList.appendChild(listItem);
              }
          })
          .catch((error) => {
              console.error("Error processing image: ", error);
          });
  });
});