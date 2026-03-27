import cv2
import sys

def test_camera_backend(i, backend_name, backend_flag):
    """Testa una singola camera con un backend specifico"""
    cap = cv2.VideoCapture(i, backend_flag)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            cap.release()
            return True, f"{width}x{height} @ {fps}fps"
        cap.release()
    return False, None

print("Scanning for available cameras with multiple backends...")
print("=" * 70)

available_cameras = []

for i in range(10):
    results = []
    
    # Test Media Foundation (MSMF) - supporta accesso condiviso
    success, info = test_camera_backend(i, "MSMF", cv2.CAP_MSMF)
    if success:
        results.append(f"MSMF: {info}")
        available_cameras.append(i)
    
    # Test DirectShow (DSHOW) - accesso esclusivo
    success, info = test_camera_backend(i, "DSHOW", cv2.CAP_DSHOW)
    if success:
        results.append(f"DSHOW: {info}")
        if i not in available_cameras:
            available_cameras.append(i)
    
    if results:
        print(f"✓ Camera Index {i}:")
        for result in results:
            print(f"  - {result}")
    
    sys.stdout.flush()

print("=" * 70)
if available_cameras:
    print(f"\n✓ Available camera indices: {available_cameras}")
    print(f"✓ Total cameras found: {len(available_cameras)}")
    print("\nNote: MSMF (Media Foundation) supports shared access with OBS")
    print("      DSHOW (DirectShow) requires exclusive access")
else:
    print("\n✗ No cameras found")
