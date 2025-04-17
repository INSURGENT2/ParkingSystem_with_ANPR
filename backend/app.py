from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import cv2
import pytesseract
import os
import base64
import sqlite3
from datetime import datetime
from roboflow import Roboflow
import threading
import queue
import time
import json

app = Flask(__name__)
CORS(app)

# Set tesseract path (update if necessary)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Load Roboflow models
rf = Roboflow(api_key="vj0Hrrvvu3SVjBh4dRG6")
# License plate model
plate_project = rf.workspace().project("license-plate-recognition-rxg4e")
plate_model = plate_project.version(11).model
# Parking spot model
parking_project = rf.workspace().project("deteksiparkirkosong")
parking_model = parking_project.version(6).model

# ---------- GLOBAL VARIABLES ----------
video_processing_queue = queue.Queue()
parking_allocations = {}  # {parking_spot_id: {"plate_text": text, "coordinates": (x,y,w,h)}}
plate_detection_history = {}  # {plate_text: last_detection_time}
latest_frame = None
frame_lock = threading.Lock()
processing_active = False
video_thread = None

# ---------- DATABASE SETUP ----------
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

def save_to_db(plate_text, image_base64=None, parking_spot=None, spot_coordinates=None):
    conn = sqlite3.connect("plates.db")
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO detected_plates 
        (plate_text, timestamp, image_base64, parking_spot, spot_coordinates) 
        VALUES (?, ?, ?, ?, ?)''',
        (plate_text, datetime.now().isoformat(), image_base64, 
         parking_spot, json.dumps(spot_coordinates) if spot_coordinates else None)
    )
    conn.commit()
    conn.close()

# ---------- VIDEO PROCESSING ----------
def process_video(video_source=0):
    global latest_frame, processing_active, parking_allocations
    
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print("Error: Could not open video source")
        return
    
    processing_active = True
    frame_count = 0
    process_every_n_frames = 10  # Process every 10th frame to reduce load
    
    while processing_active:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        # Store the latest frame for the video feed
        with frame_lock:
            latest_frame = frame.copy()
        
        if frame_count % process_every_n_frames != 0:
            continue
            
        # Process frame for license plates
        temp_file = "temp/frame.jpg"
        cv2.imwrite(temp_file, frame)
        
        # Detect license plates
        try:
            plate_predictions = plate_model.predict(temp_file, confidence=40).json()
        except Exception as e:
            print(f"Plate detection error: {e}")
            continue
            
        for pred in plate_predictions.get("predictions", []):
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

            if len(text) >= 4:
                # Check if this plate was recently detected
                if text in plate_detection_history and (time.time() - plate_detection_history[text]) < 30:
                    continue  # Skip if detected recently
                
                plate_detection_history[text] = time.time()
                
                # Detect parking spots
                try:
                    parking_predictions = parking_model.predict(temp_file, confidence=40).json()
                except Exception as e:
                    print(f"Parking detection error: {e}")
                    continue
                
                free_spots = [spot for spot in parking_predictions.get("predictions", []) 
                             if spot["class"] == "kosong"]
                
                if free_spots:
                    # Allocate the first free spot
                    allocated_spot = free_spots[0]
                    spot_coords = (allocated_spot['x'], allocated_spot['y'], 
                                  allocated_spot['width'], allocated_spot['height'])
                    parking_spot_id = f"spot_{allocated_spot['x']}_{allocated_spot['y']}"
                    
                    # Save allocation
                    parking_allocations[parking_spot_id] = {
                        "plate_text": text,
                        "coordinates": spot_coords
                    }
                    
                    # Save to database
                    _, buffer = cv2.imencode('.jpg', thresh)
                    img_b64 = base64.b64encode(buffer).decode('utf-8')
                    save_to_db(text, img_b64, parking_spot_id, spot_coords)
        
        # Visualize allocations on the frame
        for spot_id, data in parking_allocations.items():
            plate_text = data["plate_text"]
            x, y, w, h = data["coordinates"]
            
            # Draw rectangle around parking spot
            cv2.rectangle(frame, 
                         (int(x - w/2), int(y - h/2)),
                         (int(x + w/2), int(y + h/2)),
                         (0, 255, 0), 2)
            
            # Draw the plate text on the parking spot
            cv2.putText(frame, plate_text, (int(x), int(y)), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Save the processed frame for display
        with frame_lock:
            latest_frame = frame.copy()
    
    cap.release()
    print("Video processing stopped")

def generate_frames():
    while processing_active:
        with frame_lock:
            if latest_frame is None:
                time.sleep(0.1)
                continue
            
            ret, buffer = cv2.imencode('.jpg', latest_frame)
            if not ret:
                continue
                
            frame = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# ---------- API ENDPOINTS ----------
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), 
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/start_processing", methods=["POST"])
def start_processing():
    global processing_active, video_thread
    
    if processing_active:
        return jsonify({"status": "already running"})
    
    video_source = request.json.get("video_source", 0)
    if isinstance(video_source, str) and video_source.isdigit():
        video_source = int(video_source)
    
    video_thread = threading.Thread(target=process_video, args=(video_source,))
    video_thread.daemon = True
    video_thread.start()
    
    return jsonify({"status": "started"})

@app.route("/stop_processing", methods=["POST"])
def stop_processing():
    global processing_active
    
    processing_active = False
    if video_thread and video_thread.is_alive():
        video_thread.join()
    
    return jsonify({"status": "stopped"})

@app.route("/allocations", methods=["GET"])
def get_allocations():
    return jsonify({"allocations": parking_allocations})

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
        img_b64 = base64.b64encode(buffer).decode('utf-8')

        if len(text) >= 4:
            save_to_db(text, img_b64)
            plates.append({"text": text, "image": img_b64})

    try:
        os.remove(file_path)
    except OSError:
        pass

    return jsonify({"plates": plates})

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

@app.route("/clear_allocations", methods=["POST"])
def clear_allocations():
    global parking_allocations
    parking_allocations = {}
    return jsonify({"status": "allocations cleared"})

if __name__ == "__main__":
    os.makedirs("temp", exist_ok=True)
    app.run(host='0.0.0.0', port=5000, threaded=True)