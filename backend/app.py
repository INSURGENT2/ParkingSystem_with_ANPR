import cv2
import pytesseract
import os
import base64
import sqlite3
from datetime import datetime
from roboflow import Roboflow
import json
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
import time 
from flask import send_file

app = Flask(__name__)
CORS(app)

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

rf = Roboflow(api_key="vj0Hrrvvu3SVjBh4dRG6")
plate_model = rf.workspace().project("license-plate-recognition-rxg4e").version(11).model
parking_model = rf.workspace().project("deteksiparkirkosong").version(6).model  # Parking detection model

# ─── Initialize DB ─────────────────────────
def init_db():
    conn = sqlite3.connect("plates.db")
    cursor = conn.cursor()

    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS detected_plates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            image_base64 TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entry_exit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            image_base64 TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_spots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            assigned_plate TEXT,
            timestamp TEXT
        )
    ''')

    conn.commit()
    conn.close()

init_db()


# - Preprocess
def resize_plate(plate_img, target_width=300):
    """Resize plate image while maintaining aspect ratio"""
    h, w = plate_img.shape[:2]
    aspect = w / h
    target_height = int(target_width / aspect)
    return cv2.resize(plate_img, (target_width, target_height), interpolation=cv2.INTER_CUBIC)

def preprocess_plate(plate_img):
    """Apply multiple preprocessing techniques to enhance plate text readability"""
    if plate_img.size == 0:
        return None
    
    # Resize for more consistent OCR
    plate_img = resize_plate(plate_img, target_width=300)
    
    # Convert to grayscale
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    
    # Apply bilateral filter to reduce noise while preserving edges
    filtered = cv2.bilateralFilter(gray, 11, 17, 17)
    
    # Apply CLAHE for better contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(filtered)
    
    # Create 3 different preprocessing variants for OCR
    
    # Variant 1: OTSU thresholding (good for clean plates)
    _, otsu = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Variant 2: Adaptive thresholding (good for uneven lighting)
    adaptive = cv2.adaptiveThreshold(
        contrast, 255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 
        19, 9
    )
    
    # Variant 3: Edge enhancement + thresholding
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(contrast, -1, kernel)
    _, sharp_thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return {
        'original': plate_img,
        'gray': gray,
        'contrast': contrast,
        'otsu': otsu,
        'adaptive': adaptive,
        'sharp_thresh': sharp_thresh
    }

def deskew_plate(binary_img):
    """Attempt to correct plate skew based on text orientation"""
    try:
        coords = np.column_stack(np.where(binary_img > 0))
        if len(coords) < 10:  # Not enough points
            return binary_img
            
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        (h, w) = binary_img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(binary_img, M, (w, h), 
                                flags=cv2.INTER_CUBIC, 
                                borderMode=cv2.BORDER_REPLICATE)
        return rotated
    except:
        return binary_img  # Return original if deskewing fails

def clean_plate_text(text):
    """Clean and validate the OCR result"""
    # Remove non-alphanumeric characters
    text = ''.join(c for c in text if c.isalnum())
    
    # Convert 0/O and other common confusions
    text = text.upper()
    
    # Apply common correction patterns
    replacements = {
        '0': 'O',
        '1': 'I',
        '5': 'S',
        '8': 'B',
        '2': 'Z'
    }
    
    # Only apply replacements to letters in positions where they're commonly found
    # For example, don't replace numbers in the numeric part of the license plate
    result = ""
    for i, char in enumerate(text):
        # For plates like BB8986, first 2 chars are typically letters
        if i < 2 and char in replacements.keys():
            result += replacements[char]
        # For plates like BB8986, characters after position 2 are typically numbers
        elif i >= 2 and char in replacements.values():
            # Reverse the replacement (e.g., convert 'B' to '8' in the number portion)
            reverse_map = {v: k for k, v in replacements.items()}
            if char in reverse_map:
                result += reverse_map[char]
            else:
                result += char
        else:
            result += char
            
    return result

def recognize_text(processed_images):
    """Try multiple OCR approaches and return the most reliable result"""
    # OCR configurations to try
    configs = [
        "--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        "--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        "--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ]
    
    candidates = []
    
    # Process each image variant with each config
    for img_name, img in processed_images.items():
        if img_name == 'original':  # Skip the color original
            continue
            
        # Try deskewing for binary images
        if img_name in ['otsu', 'adaptive', 'sharp_thresh']:
            deskewed = deskew_plate(img)
            
            # Try with normal and deskewed version
            for image_variant in [img, deskewed]:
                for config in configs:
                    text = pytesseract.image_to_string(image_variant, config=config).strip()
                    text = ''.join(c for c in text if c.isalnum())
                    if len(text) >= 4:
                        candidates.append(text)
        else:
            # For non-binary images, just use standard OCR
            for config in configs:
                text = pytesseract.image_to_string(img, config=config).strip()
                text = ''.join(c for c in text if c.isalnum())
                if len(text) >= 4:
                    candidates.append(text)
    
    if not candidates:
        return ""
    
    # Score candidates based on common license plate patterns
    scored_candidates = []
    for text in candidates:
        score = 0
        cleaned = clean_plate_text(text)
        
        # Exact length match for standard plates (e.g., 6 chars for BB8986)
        if len(cleaned) == 6:
            score += 5
        # Close length (5-7 chars)
        elif 5 <= len(cleaned) <= 7:
            score += 3
            
        # Pattern match: 2 letters followed by 4 digits (like BB8986)
        if len(cleaned) >= 6 and cleaned[:2].isalpha() and cleaned[2:6].isdigit():
            score += 10
            
        # Common start patterns (2 letters)
        if len(cleaned) >= 2 and cleaned[:2].isalpha():
            score += 3
            
        scored_candidates.append((cleaned, score))
    
    # Sort by score (highest first)
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    
    # Return the highest scoring candidate
    if scored_candidates:
        return scored_candidates[0][0]
        
    return ""
# ─── Parking Spot Assignment ─────────────────────


def assign_parking_spot(plate_text, frame, free_spots):
    """
    Assign a detected license plate to a free parking spot.
    Marks the parking spot in the image.
    Returns the assigned spot or None if no spot was assigned.
    """
    conn = sqlite3.connect("plates.db")
    cursor = conn.cursor()
    
    assigned_spot = None
    for spot in free_spots:
        spot_id = spot['id']
        # If the spot is free, assign the plate
        if spot['status'] == 'free':
            cursor.execute('''
                INSERT INTO parking_spots (spot_id, status, assigned_plate, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (spot_id, 'occupied', plate_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            # Draw the number plate text over the spot
            cv2.putText(frame, plate_text, (spot['x'], spot['y'] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            spot['status'] = 'occupied'  # Update the status of the parking spot
            assigned_spot = spot
            break
    
    conn.commit()
    conn.close()
    
    return assigned_spot  # Return the assigned spot


# ─── Upload & Process Image ────────────────
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

    notifications = []
    plates = []
    allocations = []

    # Get free parking spots before processing plates
    
    
    for pred in predictions.get("predictions", []):
        x, y, w, h = pred["x"], pred["y"], pred["width"], pred["height"]
        x1, y1 = int(x - w / 2), int(y - h / 2)
        x2, y2 = int(x + w / 2), int(y + h / 2)

        plate_img = frame[y1:y2, x1:x2]
        if plate_img.size == 0:
            continue

        _, original_buffer = cv2.imencode('.jpg', plate_img)
        original_b64 = base64.b64encode(original_buffer).decode('utf-8') if original_buffer is not None else ""

        processed_images = preprocess_plate(plate_img)
        if processed_images is None:
            continue

        text = recognize_text(processed_images)

        # Save debug images
        debug_dir = os.path.join("temp", "debug")
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for img_name, img in processed_images.items():
            if img_name != 'original':
                cv2.imwrite(os.path.join(debug_dir, f"{timestamp}_{text}_{img_name}.jpg"), img)

        if len(text) >= 4:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect("plates.db")
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp FROM detected_plates WHERE plate_text = ?", (text,))
            result = cursor.fetchone()

            if result:
                # EXIT
                cursor.execute("DELETE FROM detected_plates WHERE plate_text = ?", (text,))
                cursor.execute(
                    "INSERT INTO entry_exit_log (plate_text, timestamp, status, image_base64) VALUES (?, ?, ?, ?)",
                    (text, now, "exit", original_b64)
                )
                notifications.append({"plate": text, "status": "exit"})
                
                # Free up the parking spot when car exits
                cursor.execute("DELETE FROM parking_spots WHERE assigned_plate = ?", (text,))
            else:
                # ENTRY
                cursor.execute(
                    "INSERT INTO detected_plates (plate_text, timestamp, image_base64) VALUES (?, ?, ?)",
                    (text, now, original_b64)
                )
                cursor.execute(
                    "INSERT INTO entry_exit_log (plate_text, timestamp, status, image_base64) VALUES (?, ?, ?, ?)",
                    (text, now, "entry", original_b64)
                )
                notifications.append({"plate": text, "status": "entry"})

                # Allocate parking if there are free spots
                
            conn.commit()
            conn.close()

            plates.append({
                "text": text,
                "image": original_b64
            })

    try:
        os.remove(file_path)
    except OSError:
        pass

    return jsonify({
        "notifications": notifications,
        "plates": plates,
       
    })


# ─── Get Free Parking Spots ────────────────────
video_path = "parking_1920_1080.mp4"
cap = None

# Modify this function in your Flask app
def get_free_parking_spots():
    """
    Capture current video frame and detect free parking spots using Roboflow model.
    Returns a list of free parking spot dictionaries.
    """
    # Make sure the video is opened correctly
    global cap
    if cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(video_path)
    
    ret, frame = cap.read()
    if not ret:
        # Reset the video if we reached the end
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if not ret:
            print("❌ Could not read frame from video.")
            return []

    screenshot_path = "temp_frame.jpg"
    cv2.imwrite(screenshot_path, frame)

    try:
        result = parking_model.predict(screenshot_path).json()
        predictions = result.get("predictions", [])

        free_spots = []
        for i, pred in enumerate(predictions):
            if pred["class"] == "free":
                spot = {
                    "id": i + 1,  # Add a unique ID if not present
                    "x": int(pred["x"] - pred["width"] / 2),
                    "y": int(pred["y"] - pred["height"] / 2),
                    "width": int(pred["width"]),
                    "height": int(pred["height"]),
                    "confidence": pred["confidence"],
                    "status": "free"
                }
                free_spots.append(spot)

        print(f"✅ Detected {len(free_spots)} free spot(s).")
        return free_spots

    except Exception as e:
        print(f"❌ Roboflow detection error: {e}")
        return []

    finally:
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
# ─── Get Currently Parked Cars ─────────────
@app.route("/plates", methods=["GET"])
def get_current_plates():
    conn = sqlite3.connect("plates.db")
    cursor = conn.cursor()
    cursor.execute("SELECT plate_text, timestamp, image_base64 FROM detected_plates ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    data = [{"text": row[0], "timestamp": row[1], "image": row[2]} for row in rows]
    return jsonify({"stored_plates": data})

# ─── Get Entry/Exit History ────────────────
@app.route("/history", methods=["GET"])
def get_history():
    conn = sqlite3.connect("plates.db")
    cursor = conn.cursor()
    cursor.execute("SELECT plate_text, timestamp, status, image_base64 FROM entry_exit_log ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    data = [{"text": row[0], "timestamp": row[1], "status": row[2], "image": row[3]} for row in rows]
    return jsonify({"stored_plates": data})


@app.route("/parking-status", methods=["GET"])
def parking_status():
    conn = sqlite3.connect("plates.db")
    cursor = conn.cursor()
    
    # Get current parking spot assignments
    cursor.execute('''
        SELECT spot_id, status, assigned_plate, timestamp 
        FROM parking_spots 
        ORDER BY spot_id
    ''')
    spots = cursor.fetchall()
    
    # Get free spots from video analysis
    free_spots = get_free_parking_spots()
    
    # Convert to dictionary format
    spot_data = []
    for spot in spots:
        spot_data.append({
            "spot_id": spot[0],
            "status": spot[1],
            "assigned_plate": spot[2],
            "timestamp": spot[3]
        })
    
    conn.close()
    
    return jsonify({
        "parking_spots": spot_data,
        "free_spots": free_spots,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# ─── Assign Parking Spot ──────────────────────
@app.route("/assign-parking", methods=["POST"])
def assign_parking():
    data = request.json
    plate_text = data.get("plate_text")
    
    if not plate_text:
        return jsonify({"error": "Plate text is required"}), 400
    
    try:
        # Get current free spots
        free_spots = get_free_parking_spots()
        
        if not free_spots:
            return jsonify({"error": "No available parking spots detected"}), 400
        
        # Take a screenshot of the parking area
        global cap
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(video_path)
        
        ret, frame = cap.read()
        if not ret:
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            if not ret:
                return jsonify({"error": "Could not capture parking area"}), 500
        
        # Create a copy of the frame to draw on
        marked_frame = frame.copy()
        
        # Assign the first available spot
        assigned_spot = None
        for spot in free_spots:
            if spot['status'] == 'free':
                # Draw a rectangle around the spot
                cv2.rectangle(
                    marked_frame, 
                    (spot['x'], spot['y']), 
                    (spot['x'] + spot['width'], spot['y'] + spot['height']), 
                    (0, 255, 0), 
                    2
                )
                
                # Draw the plate text on the spot
                cv2.putText(
                    marked_frame, 
                    plate_text, 
                    (spot['x'], spot['y'] - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.9, 
                    (0, 0, 255), 
                    2
                )
                
                # Save to database
                conn = sqlite3.connect("plates.db")
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO parking_spots (spot_id, status, assigned_plate, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (spot['id'], 'occupied', plate_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
                
                # Convert marked full image to base64
                _, img_buffer = cv2.imencode('.jpg', marked_frame)
                img_base64 = base64.b64encode(img_buffer).decode('utf-8')
                
                assigned_spot = {
                    "spot_id": spot['id'],
                    "plate_text": plate_text,
                    "coordinates": {
                        "x": spot['x'],
                        "y": spot['y'],
                        "width": spot['width'],
                        "height": spot['height']
                    },
                    "marked_image": img_base64
                }
                break
        
        if assigned_spot:
            return jsonify({
                "message": "Parking spot assigned",
                "assigned_spot": assigned_spot
            })
        else:
            return jsonify({"error": "Failed to assign parking spot"}), 500
            
    except Exception as e:
        print(f"Error in assign_parking: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
if __name__ == "__main__":
    os.makedirs("temp", exist_ok=True)
    os.makedirs(os.path.join("temp", "debug"), exist_ok=True)
    app.run(host='0.0.0.0', port=5000, threaded=True)
