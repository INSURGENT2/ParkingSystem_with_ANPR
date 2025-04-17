import React from "react";
import { Card, Image } from "react-bootstrap";

const LiveCameraFeed = ({ allocations }) => {
  // This would normally come from your backend
  const videoFeedUrl = "http://localhost:5000/video_feed"; // Flask endpoint for video stream
  
  return (
    <Card className="mb-4">
      <Card.Header as="h5">Live Parking Allocation</Card.Header>
      <Card.Body>
        <div style={{ position: "relative" }}>
          {/* This would be your live video feed */}
          <Image 
            src={videoFeedUrl} 
            fluid 
            alt="Live camera feed" 
            style={{ border: "1px solid #ddd", borderRadius: "4px" }}
          />
          
          {/* Overlay allocations on the video */}
          {Object.entries(allocations).map(([spotId, plateText]) => {
            // Parse spot coordinates from spotId (format: "spot_x_y")
            const [, x, y] = spotId.split("_");
            
            return (
              <div 
                key={spotId}
                style={{
                  position: "absolute",
                  left: `${x}px`,
                  top: `${y}px`,
                  backgroundColor: "rgba(255, 0, 0, 0.7)",
                  color: "white",
                  padding: "2px 5px",
                  borderRadius: "3px",
                  fontWeight: "bold"
                }}
              >
                {plateText}
              </div>
            );
          })}
        </div>
        <Card.Text className="mt-2">
          {Object.keys(allocations).length > 0 
            ? "Current allocations displayed in red"
            : "No parking allocations currently"}
        </Card.Text>
      </Card.Body>
    </Card>
  );
};

export default LiveCameraFeed;