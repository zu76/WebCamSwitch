import cv2
import sys

print("Scanning for available cameras (0-9)...")
print("-" * 50)

available = []
for i in range(10):
    # Prova prima MSMF (Media Foundation - accesso condiviso)
    cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
    ret, frame = cap.read()
    
    if ret and frame is not None:
        print(f"Camera {i}: ✓ AVAILABLE (MSMF - shared access)")
        available.append(i)
        cap.release()
    else:
        cap.release()
        # Fallback a DirectShow
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"Camera {i}: ✓ AVAILABLE (DSHOW - exclusive access)")
            available.append(i)
        else:
            print(f"Camera {i}: ✗ Not available")
        cap.release()

print("-" * 50)
print(f"\nAvailable camera indices: {available}")
print(f"Total cameras found: {len(available)}")
