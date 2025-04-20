import cv2
import os
import base64
import json
from flask import Flask, request, jsonify
import parking  # Import our parking module

app = Flask(__name__)

@app.route("/test_allocation", methods=["POST"])
def test_allocation():
    """
    Test endpoint that simulates the upload process but focuses only on parking allocation.
    Expected request: {"plate_text": "AB1234", "image": "base64_encoded_image"}
    """
    data = request.json
    if not data or 'plate_text' not in data:
        return jsonify({"error": "Please provide license plate text"}), 400
    
    plate_text = data['plate_text']
    
    # Process the image if provided
    frame = None
    if 'image' in data and data['image']:
        try:
            # Decode the base64 image
            image_data = base64.b64decode(data['image'])
            
            # Save to temp file
            temp_path = "temp_upload.jpg"
            with open(temp_path, "wb") as f:
                f.write(image_data)
            
            # Read the image
            frame = cv2.imread(temp_path)
            
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        except Exception as e:
            print(f"Error processing uploaded image: {e}")
    
    # Get parking allocation
    allocation = parking.get_parking_allocations(plate_text, frame)
    
    if allocation:
        return jsonify({
            "success": True,
            "message": f"Parking spot allocated for plate {plate_text}",
            "allocation": allocation
        })
    else:
        return jsonify({
            "success": False,
            "message": "No parking spot could be allocated"
        })

# Simple test function to run standalone
def test_allocation_locally():
    """
    Run a local test of the parking allocation system without Flask.
    """
    test_plate = "AB1234"
    print(f"Testing allocation for plate: {test_plate}")
    
    # Get a test frame from video
    cap = cv2.VideoCapture("parking_1920_1080.mp4")
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("Could not get frame from video")
        return
    
    # Try to allocate parking
    allocation = parking.get_parking_allocations(test_plate, frame)
    
    if allocation:
        # Save the spot image for inspection
        if allocation["image"]:
            spot_image_data = base64.b64decode(allocation["image"])
            with open("test_allocated_spot.jpg", "wb") as f:
                f.write(spot_image_data)
        
        print(f"Successfully allocated parking spot: {json.dumps(allocation, indent=2)}")
    else:
        print("Failed to allocate parking spot")

if __name__ == "__main__":
    # Uncomment to run standalone test:
    # test_allocation_locally()
    
    # Or run the Flask app for API testing:
    app.run(debug=True, port=5001)