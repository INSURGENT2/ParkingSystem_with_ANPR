import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import UploadSingleImage from "./components/UploadSingleImage";
import StoredPlates from "./components/StoredPlates";
import LiveCameraFeed from "./components/LiveCameraFeed";
import RegisteredCars from "./components/RegisteredCars"; // ← ADD THIS

import { Container, Navbar, Nav, Button } from "react-bootstrap";
import "bootstrap/dist/css/bootstrap.min.css";

function App() {
  const [showCameraFeed, setShowCameraFeed] = useState(false);
  const [allocations, setAllocations] = useState({});

  // Function to fetch allocations from backend
  const fetchAllocations = async () => {
    try {
      const response = await fetch('http://localhost:5000/allocations');
      const data = await response.json();
      setAllocations(data.allocations);
    } catch (error) {
      console.error("Error fetching allocations:", error);
    }
  };

  // Periodically fetch allocations when camera feed is shown
  useEffect(() => {
    let interval;
    if (showCameraFeed) {
      fetchAllocations();
      interval = setInterval(fetchAllocations, 3000); // Update every 3 seconds
    }
    return () => clearInterval(interval);
  }, [showCameraFeed]);

  return (
    <Router>
      <Navbar bg="dark" variant="dark" expand="lg">
        <Container>
          <Navbar.Brand as={Link} to="/">PlateVision</Navbar.Brand>
          <Nav className="ms-auto">
            <Nav.Link as={Link} to="/">Home</Nav.Link>
            <Nav.Link as={Link} to="/stored">View Stored Plates</Nav.Link>
            <Nav.Link as={Link} to="/registered">Registered Cars</Nav.Link>
            <Button 
              variant={showCameraFeed ? "danger" : "success"} 
              onClick={() => setShowCameraFeed(!showCameraFeed)}
              className="ms-2"
            >
              {showCameraFeed ? "Hide Live Feed" : "Show Live Feed"}
            </Button>
          </Nav>
        </Container>
      </Navbar>

      <Container className="mt-5">
        {showCameraFeed && (
          <div className="mb-4">
            <LiveCameraFeed allocations={allocations} />
          </div>
        )}
        
        <Routes>
          <Route path="/" element={<UploadSingleImage />} />
          <Route path="/stored" element={<StoredPlates />} />
          <Route path="/registered" element={<RegisteredCars />} /> {/* ← ADD THIS */}
        </Routes>
      </Container>
    </Router>
  );
}

export default App;