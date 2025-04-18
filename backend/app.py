from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import pytesseract
import os
import base64
import sqlite3
from datetime import datetime
from roboflow import Roboflow
import json

app = Flask(__name__)
CORS(app)

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

rf = Roboflow(api_key="vj0Hrrvvu3SVjBh4dRG6")
plate_model = rf.workspace().project("license-plate-recognition-rxg4e").version(11).model

def init_db():
    conn = sqlite3.connect("plates.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detected_plates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            image_base64 TEXT,
            parking_spot TEXT,
            spot_coordinates TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    os.makedirs("temp", exist_ok=True)
    file_path = os.path.join("temp", file.filename)
    file.save(file_path)

    frame = cv2.imread(file_path)
    predictions = plate_model.predict(file_path, confidence=40).json()

    plates = []
    notifications = []

    for pred in predictions.get("predictions", []):
        x, y, w, h = pred["x"], pred["y"], pred["width"], pred["height"]
        x1, y1 = int(x - w / 2), int(y - h / 2)
        x2, y2 = int(x + w / 2), int(y + h / 2)

        plate_img = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        text = pytesseract.image_to_string(
            thresh,
            config="--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )
        text = ''.join(c for c in text if c.isalnum())

        _, buffer = cv2.imencode('.jpg', thresh)
        img_b64 = base64.b64encode(buffer).decode('utf-8') if buffer is not None else ""

        if len(text) >= 4:
            conn = sqlite3.connect("plates.db")
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp FROM detected_plates WHERE plate_text = ?", (text,))
            result = cursor.fetchone()

            if result:
                # Exit detected
                entry_time = datetime.fromisoformat(result[0])
                duration = datetime.now() - entry_time

                cursor.execute("DELETE FROM detected_plates WHERE plate_text = ?", (text,))
                conn.commit()

                notifications.append({
                    "plate": text,
                    "status": "exit",
                    "duration": str(duration)
                })
            else:
                # Entry detected
                cursor.execute(
                    '''INSERT INTO detected_plates 
                    (plate_text, timestamp, image_base64, parking_spot, spot_coordinates) 
                    VALUES (?, ?, ?, ?, ?)''',
                    (text, datetime.now().isoformat(), img_b64, None, None)
                )
                conn.commit()

                notifications.append({
                    "plate": text,
                    "status": "entry"
                })

            conn.close()
            plates.append({"text": text, "image": img_b64})

    try:
        os.remove(file_path)
    except OSError:
        pass

    return jsonify({
        "plates": plates,
        "notifications": notifications
    })

@app.route("/plates", methods=["GET"])
def get_stored_plates():
    conn = sqlite3.connect("plates.db")
    cursor = conn.cursor()
    cursor.execute("SELECT plate_text, timestamp, image_base64, parking_spot, spot_coordinates FROM detected_plates ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()

    data = [
        {
            "text": row[0], 
            "timestamp": row[1], 
            "image": row[2], 
            "parking_spot": row[3],
            "spot_coordinates": json.loads(row[4]) if row[4] else None
        }
        for row in rows
    ]
    return jsonify({"stored_plates": data})

if __name__ == "__main__":
    os.makedirs("temp", exist_ok=True)
    app.run(host='0.0.0.0', port=5000, threaded=True)
