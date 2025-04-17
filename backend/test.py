import cv2

cap = cv2.VideoCapture("C:/Users/stly3/anpr_system/backend/parking_1920_1080.mp4")
if not cap.isOpened():
    print("❌ Video not found or can't be opened.")
else:
    print("✅ Video opened successfully")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imshow("Frame", frame)
        if cv2.waitKey(1) == 27:
            break
    cap.release()
    cv2.destroyAllWindows()
