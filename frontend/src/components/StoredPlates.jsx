import React, { useEffect, useState } from "react";
import axios from "axios";
import { Card, Spinner, Alert } from "react-bootstrap";

// Error Boundary Component
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.log("Error caught in error boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <Alert variant="danger">Something went wrong while fetching the stored plates.</Alert>;
    }
    return this.props.children;
  }
}

function StoredPlates() {
  const [plates, setPlates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    axios
      .get("http://localhost:5000/plates")
      .then((res) => setPlates(res.data.stored_plates)) // Access stored_plates instead of plates
      .catch(() => setError("Failed to load stored plates."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ErrorBoundary>
      <div>
        <h2>Stored Plate Numbers</h2>
        {loading && <Spinner animation="border" />}
        {error && <Alert variant="danger">{error}</Alert>}
        {plates.length > 0 ? (
          plates.map((plate, i) => (
            <Card key={i} className="mt-3 shadow-sm">
              <Card.Body>
                <Card.Text>
                  <strong>Plate:</strong> {plate.text}
                </Card.Text>
                {plate.image && (
                  <img
                    src={`data:image/jpeg;base64,${plate.image}`}
                    alt={`Plate ${i}`}
                    style={{ width: "100%", height: "auto", border: "1px solid #ccc" }}
                  />
                )}
              </Card.Body>
            </Card>
          ))
        ) : (
          <Alert variant="info">No stored plates available.</Alert>
        )}
      </div>
    </ErrorBoundary>
  );
}

export default StoredPlates;
