import React, { useState } from "react";
import axios from "axios";
import { Button, Card, Alert, Form, Spinner, Modal, Row, Col } from "react-bootstrap";

function UploadSingleImage() {
  const [image, setImage] = useState(null);
  const [results, setResults] = useState([]);
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [popupMessage, setPopupMessage] = useState("");
  const [popupType, setPopupType] = useState("");
  const [parkingSpots, setParkingSpots] = useState([]);
  const [findingParking, setFindingParking] = useState(false);
  const [selectedPlate, setSelectedPlate] = useState(null);
  const [entryPlates, setEntryPlates] = useState([]);

  const handleChange = (e) => setImage(e.target.files[0]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!image) return;

    const formData = new FormData();
    formData.append("image", image);

    setLoading(true);
    setError("");
    setResults([]);
    setAllocations([]);
    setParkingSpots([]);
    setEntryPlates([]);

    try {
      const response = await axios.post("http://localhost:5000/upload", formData);
      console.log("Backend response:", response.data);

      setResults(response.data.plates || []);
      setAllocations(response.data.allocations || []);

      if (response.data.notifications && response.data.notifications.length > 0) {
        const notification = response.data.notifications[0];

        // Only allow "Find Parking" for cars that are entering
        if (notification.status === "entry") {
          setEntryPlates([notification.plate]);
        }

        setPopupMessage(
          notification.status === "exit"
            ? `Plate ${notification.plate} has exited after ${notification.duration}`
            : `Plate ${notification.plate} has entered`
        );
        setPopupType(notification.status === "exit" ? "success" : "info");
      }
    } catch (error) {
      console.error("Error during image upload:", error);
      setError("Error processing image.");
    } finally {
      setLoading(false);
    }
  };

  
    const findParkingSpot = async (plateText) => {
      setSelectedPlate(plateText);
      setFindingParking(true);
      try {
        // First get the parking status
        const statusResponse = await axios.get("http://localhost:5000/parking-status");
        console.log("Parking status:", statusResponse.data);
        
        // Then try to assign a spot
        const response = await axios.post("http://localhost:5000/assign-parking", {
          plate_text: plateText,
        });
        console.log("Parking assignment response:", response.data);
    
        if (response.data.assigned_spot) {
          setPopupMessage(`Assigned parking spot ${response.data.assigned_spot.spot_id} to plate ${plateText}`);
          setPopupType("success");
          setAllocations([response.data.assigned_spot]);
        } else {
          setPopupMessage(response.data.message || "Parking spot assigned successfully");
          setPopupType("success");
        }
    
        setParkingSpots(statusResponse.data.parking_spots || []);
      } catch (error) {
        console.error("Error finding parking spot:", error);
        const errorMsg = error.response?.data?.error || error.message || "Unknown error";
        setPopupMessage(`Error finding parking spot: ${errorMsg}`);
        setPopupType("danger");
      } finally {
        setFindingParking(false);
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
                <Row>
                  <Col md={8}>
                    <Card.Title className="text-success fs-5">Plate Number: {plate.text}</Card.Title>
                    <img
                      src={`data:image/jpeg;base64,${plate.image}`}
                      alt={`Plate ${index}`}
                      style={{ width: "100%", border: "1px solid #ccc", borderRadius: "8px" }}
                    />
                  </Col>
                  <Col md={4} className="d-flex align-items-center justify-content-center">
                    <Button
                      variant="warning"
                      onClick={() => findParkingSpot(plate.text)}
                      disabled={findingParking || !entryPlates.includes(plate.text)}
                    >
                      {findingParking && selectedPlate === plate.text ? (
                        <Spinner animation="border" size="sm" />
                      ) : (
                        "Find Parking Spot"
                      )}
                    </Button>
                  </Col>
                </Row>
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
                  Spot ID: {allocation.spot_id}<br />
                  Coordinates: (x: {allocation.coordinates.x}, y: {allocation.coordinates.y})
                </Card.Text>
                {allocation.image && (
                  <img
                    src={`data:image/jpeg;base64,${allocation.image}`}
                    alt={`Allocated Spot ${index}`}
                    style={{ width: "100%", border: "1px solid #ccc", borderRadius: "8px" }}
                  />
                )}
              </Card.Body>
            </Card>
          ))}
        </div>
      )}

      {parkingSpots.length > 0 && (
        <div className="mt-5">
          <h4>Parking Spot Status:</h4>
          <Row>
            {parkingSpots.map((spot, index) => (
              <Col key={index} md={4} className="mb-3">
                <Card className={`shadow-sm ${spot.status === 'occupied' ? 'border-danger' : 'border-success'}`}>
                  <Card.Body>
                    <Card.Title>Spot #{spot.spot_id}</Card.Title>
                    <Card.Text>
                      Status: <strong>{spot.status}</strong><br />
                      {spot.assigned_plate && `Plate: ${spot.assigned_plate}`}
                    </Card.Text>
                  </Card.Body>
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      )}

      <Modal show={popupMessage !== ""} onHide={() => setPopupMessage("")}>
        <Modal.Header closeButton className={popupType === "success" ? "bg-success text-white" : popupType === "danger" ? "bg-danger text-white" : "bg-info text-white"}>
          <Modal.Title>
            {popupType === "success" ? "Success" : popupType === "danger" ? "Error" : "Notification"}
          </Modal.Title>
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
