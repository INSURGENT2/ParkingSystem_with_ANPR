import React, { useEffect, useState } from "react";
import axios from "axios";
import { Card, Spinner, Alert } from "react-bootstrap";

function RegisteredCars() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    axios
      .get("http://localhost:5000/history")
      .then((res) => setHistory(res.data.stored_plates))
      .catch(() => setError("Failed to load car history."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2>Entry/Exit History</h2>
      {loading && <Spinner animation="border" />}
      {error && <Alert variant="danger">{error}</Alert>}
      {history.length > 0 ? (
        history.map((car, i) => (
          <Card key={i} className="mt-3 shadow-sm">
            <Card.Body>
              <Card.Text>
                <strong>Plate:</strong> {car.text}
                <br />
                <strong>Status:</strong> {car.status.toUpperCase()}
                <br />
                <strong>Time:</strong> {new Date(car.timestamp).toLocaleString()}
              </Card.Text>
              {car.image && (
                <img
                  src={`data:image/jpeg;base64,${car.image}`}
                  alt={`Plate ${car.text}`}
                  style={{ width: "100%", height: "auto", border: "1px solid #ccc" }}
                />
              )}
            </Card.Body>
          </Card>
        ))
      ) : (
        !loading && <Alert variant="info">No entry/exit logs found.</Alert>
      )}
    </div>
  );
}

export default RegisteredCars;
