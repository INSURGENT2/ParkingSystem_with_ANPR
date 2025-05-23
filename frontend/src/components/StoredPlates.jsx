import React, { useEffect, useState } from "react";
import axios from "axios";
import { Card, Spinner, Alert } from "react-bootstrap";

function StoredPlates() {
  const [plates, setPlates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    axios
      .get("http://localhost:5000/plates")
      .then((res) => setPlates(res.data.stored_plates))
      .catch(() => setError("Failed to load stored plates."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2>Currently Parked Cars</h2>
      {loading && <Spinner animation="border" />}
      {error && <Alert variant="danger">{error}</Alert>}
      {plates.length > 0 ? (
        plates.map((plate, i) => (
          <Card key={i} className="mt-3 shadow-sm">
            <Card.Body>
              <Card.Text>
                <strong>Plate:</strong> {plate.text}
                <br />
                <strong>Time:</strong> {new Date(plate.timestamp).toLocaleString()}
              </Card.Text>
              {plate.image && (
                <img
                  src={`data:image/jpeg;base64,${plate.image}`}
                  alt={`Plate ${plate.text}`}
                  style={{ width: "100%", height: "auto", border: "1px solid #ccc" }}
                />
              )}
            </Card.Body>
          </Card>
        ))
      ) : (
        !loading && <Alert variant="info">No cars currently parked.</Alert>
      )}
    </div>
  );
}

export default StoredPlates;
