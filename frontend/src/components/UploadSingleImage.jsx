import React, { useState } from "react";
import axios from "axios";
import { Button, Card, Alert, Form, Spinner, Modal } from "react-bootstrap";

function UploadSingleImage() {
  const [image, setImage] = useState(null);
  const [results, setResults] = useState([]);
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [popupMessage, setPopupMessage] = useState("");  // State for popup message
  const [popupType, setPopupType] = useState("");  // Success or error type

  const handleChange = (e) => setImage(e.target.files[0]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!image) return;

    const formData = new FormData();
    formData.append("image", image);

    setLoading(true);
    setError("");

    try {
      // Post the image to the backend to detect plates and allocations
      const response = await axios.post("http://localhost:5000/upload", formData);

      // Assuming the backend sends both detected plates and allocations
      setResults(response.data.plates || []);
      setAllocations(response.data.allocations || []);

      // Check if there are notifications to show (for entry/exit)
      if (response.data.notifications && response.data.notifications.length > 0) {
        const notification = response.data.notifications[0]; // Assuming one notification per plate
        setPopupMessage(`Plate ${notification.plate} has ${notification.status} for ${notification.duration || 'N/A'}`);
        setPopupType(notification.status === "exit" ? "success" : "info");
      }
    } catch {
      setError("Error processing image.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h2 className="mb-4">Upload an Image for Plate Detection</h2>
      <Form onSubmit={handleSubmit}>
        <Form.Group controlId="formFile">
          <Form.Control type="file" accept="image/*" onChange={handleChange} required />
        </Form.Group>
        <Button variant="primary" type="submit" className="mt-3" disabled={loading}>
          {loading ? <Spinner animation="border" size="sm" /> : "Detect Plate"}
        </Button>
      </Form>

      {error && <Alert variant="danger" className="mt-4">{error}</Alert>}

      {results.length > 0 && (
        <div className="mt-5">
          <h4>Detected Plates:</h4>
          {results.map((plate, index) => (
            <Card key={index} className="mb-3 shadow-sm">
              <Card.Body>
                <Card.Title className="text-success fs-5">Plate Number: {plate.text}</Card.Title>
                <img
                  src={`data:image/jpeg;base64,${plate.image}`}
                  alt={`Plate ${index}`}
                  style={{ width: "100%", border: "1px solid #ccc", borderRadius: "8px" }}
                />
              </Card.Body>
            </Card>
          ))}
        </div>
      )}

      {allocations.length > 0 && (
        <div className="mt-5">
          <h4>Parking Spot Allocations:</h4>
          {allocations.map((allocation, index) => (
            <Card key={index} className="mb-3 shadow-sm">
              <Card.Body>
                <Card.Title className="text-warning fs-5">
                  Spot Allocated: {allocation.plate_text}
                </Card.Title>
                <Card.Text>
                  Spot Coordinates: {`(x: ${allocation.coordinates[0]}, y: ${allocation.coordinates[1]}, w: ${allocation.coordinates[2]}, h: ${allocation.coordinates[3]})`}
                </Card.Text>
                <img
                  src={`data:image/jpeg;base64,${allocation.image}`}
                  alt={`Allocated Spot ${index}`}
                  style={{ width: "100%", border: "1px solid #ccc", borderRadius: "8px" }}
                />
              </Card.Body>
            </Card>
          ))}
        </div>
      )}

      {/* Popup Modal for Notification */}
      <Modal show={popupMessage !== ""} onHide={() => setPopupMessage("")}>
        <Modal.Header closeButton>
          <Modal.Title>{popupType === "success" ? "Car Exit Detected" : "Car Entry Detected"}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>{popupMessage}</p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setPopupMessage("")}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
}

export default UploadSingleImage;
