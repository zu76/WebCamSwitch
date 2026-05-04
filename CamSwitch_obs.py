import time
import math
import cv2
import mediapipe as mp
import base64
import numpy as np
from obswebsocket import obsws, requests

# =========================
# CONFIGURAZIONE UTENTE
# =========================

# Sorgenti webcam in OBS (Trust 1080P Webcam x2)
OBS_SOURCE_A = "Video Capture Device"    # Trust 1080P #1 -> scena CAM_A
OBS_SOURCE_B = "Video Capture Device 2"  # Trust 1080P #2 -> scena CAM_B

SCENE_A = "CAM_A"
SCENE_B = "CAM_B"

OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "fbUKojx3JWxxxUW9"

# Risoluzione cattura screenshot OBS (ridotta per performance)
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480

# Parametri logica
ANALYSIS_WIDTH = 640
LOOP_SLEEP = 0.15              # ~6-7 cicli al secondo
SWITCH_THRESHOLD = 0.01        # vantaggio minimo richiesto
SWITCH_PERSISTENCE = 0.2       # secondi per confermare lo switch
SWITCH_COOLDOWN = 5.0          # secondi minimi tra switch
NO_FACE_HOLD_SECONDS = 2.0     # se nessuna camera vede il volto, tieni l'ultima
SMOOTHING_ALPHA = 0.35         # media esponenziale score

# Pesi score
W_FACE_AREA = 0.60
W_CENTERING = 0.30
W_CONFIDENCE = 0.10

# =========================
# MEDIAPIPE
# =========================

from mediapipe import tasks

import os
MODEL_PATH = os.path.join(os.path.dirname(__file__), "detector.tflite")
if not os.path.exists(MODEL_PATH):
    import urllib.request
    MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
    print(f"Downloading face detection model to {MODEL_PATH}...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Model downloaded.")

# =========================
# UTILS
# =========================

def resize_keep_ratio(frame, width):
    if frame is None or frame.size == 0:
        return None
    h, w = frame.shape[:2]
    if w == width:
        return np.ascontiguousarray(frame)
    if w <= 0 or h <= 0:
        return None
    new_h = int(h * (width / w))
    if new_h <= 0:
        return None
    return np.ascontiguousarray(cv2.resize(frame, (width, new_h)))

def clamp(x, min_val=0.0, max_val=1.0):
    return max(min_val, min(max_val, x))

def compute_center_score(bbox_center_x, bbox_center_y, frame_w, frame_h):
    cx = frame_w / 2.0
    cy = frame_h / 2.0
    dx = abs(bbox_center_x - cx) / cx
    dy = abs(bbox_center_y - cy) / cy
    dist = math.sqrt(dx * dx + dy * dy)
    return 1.0 - clamp(dist, 0.0, 1.0)

def capture_obs_screenshot(client, source_name):
    """Cattura uno screenshot di una sorgente OBS via WebSocket (accesso shared)"""
    try:
        resp = client.call(requests.GetSourceScreenshot(
            sourceName=source_name,
            imageFormat="jpg",
            imageWidth=CAPTURE_WIDTH,
            imageHeight=CAPTURE_HEIGHT
        ))
        img_data = resp.getImageData()
        if not img_data:
            return None
        if img_data.startswith('data:'):
            img_data = img_data.split(',', 1)[1]
        img_bytes = base64.b64decode(img_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"Errore screenshot da {source_name}: {e}")
        return None

def _empty_result():
    return {
        "face_found": False,
        "score": 0.0,
        "debug": {"face_area_norm": 0.0, "center_score": 0.0, "confidence": 0.0}
    }

def analyze_frame(frame, detector):
    try:
        if frame is None or frame.size == 0:
            return _empty_result()
        frame = resize_keep_ratio(frame, ANALYSIS_WIDTH)
        if frame is None:
            return _empty_result()

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame.copy(), cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = detector.detect(mp_image)
    except Exception as e:
        print(f"Errore in analyze_frame: {e}")
        return _empty_result()

    if not results.detections:
        return _empty_result()

    best_score = -1.0
    best_debug = None

    for det in results.detections:
        score_conf = det.categories[0].score if det.categories else 0.0
        bbox = det.bounding_box
        bw, bh = bbox.width, bbox.height
        if bw <= 0 or bh <= 0:
            continue
        face_area_norm = clamp((bw * bh) / float(w * h))
        center_x = bbox.origin_x + bw / 2.0
        center_y = bbox.origin_y + bh / 2.0
        center_score = compute_center_score(center_x, center_y, w, h)
        total_score = (
            W_FACE_AREA * face_area_norm +
            W_CENTERING * center_score +
            W_CONFIDENCE * score_conf
        )
        if total_score > best_score:
            best_score = total_score
            best_debug = {
                "face_area_norm": face_area_norm,
                "center_score": center_score,
                "confidence": score_conf
            }

    if best_score < 0:
        return _empty_result()
    return {"face_found": True, "score": best_score, "debug": best_debug}

def smooth_score(prev_score, new_score, alpha=SMOOTHING_ALPHA):
    if prev_score is None:
        return new_score
    return alpha * new_score + (1 - alpha) * prev_score

def set_obs_scene(client, scene_name):
    client.call(requests.SetCurrentProgramScene(sceneName=scene_name))

def get_obs_scene(client):
    resp = client.call(requests.GetCurrentProgramScene())
    return resp.getCurrentProgramSceneName()

# =========================
# MAIN
# =========================

def main():
    print("Connessione a OBS...")
    ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
    ws.connect()
    print("Connesso a OBS.\n")

    # Verifica sorgenti webcam via OBS Screenshot
    for label, src in [("A", OBS_SOURCE_A), ("B", OBS_SOURCE_B)]:
        frame = capture_obs_screenshot(ws, src)
        if frame is not None and np.mean(frame) > 5.0:
            print(f"Camera {label}: '{src}' OK ({frame.shape[1]}x{frame.shape[0]})")
        else:
            raise RuntimeError(f"Camera {label}: impossibile catturare da '{src}'")

    print()

    current_scene = get_obs_scene(ws)
    if current_scene not in (SCENE_A, SCENE_B):
        current_scene = SCENE_A
        set_obs_scene(ws, current_scene)
        print(f"Scena iniziale impostata a {current_scene}")

    smoothed_a = None
    smoothed_b = None
    last_switch_time = 0.0
    no_face_since = None
    candidate_scene = None
    candidate_since = None

    # Face detector
    base_options = tasks.BaseOptions(model_asset_path=MODEL_PATH)
    options = tasks.vision.FaceDetectorOptions(
        base_options=base_options,
        min_detection_confidence=0.5
    )
    detector = tasks.vision.FaceDetector.create_from_options(options)

    print("Loop avviato. Premi CTRL+C per uscire.\n")

    try:
        while True:
            frame_a = capture_obs_screenshot(ws, OBS_SOURCE_A)
            frame_b = capture_obs_screenshot(ws, OBS_SOURCE_B)

            if frame_a is None:
                print("Frame non valido da Camera A")
                time.sleep(0.2)
                continue
            if frame_b is None:
                print("Frame non valido da Camera B")
                time.sleep(0.2)
                continue

            res_a = analyze_frame(frame_a, detector)
            res_b = analyze_frame(frame_b, detector)

            smoothed_a = smooth_score(smoothed_a, res_a["score"])
            smoothed_b = smooth_score(smoothed_b, res_b["score"])

            face_a = res_a["face_found"]
            face_b = res_b["face_found"]
            now = time.time()

            # Gestione no-face
            if not face_a and not face_b:
                if no_face_since is None:
                    no_face_since = now
                print(
                    f"[NO FACE] scene={current_scene} | "
                    f"A={smoothed_a:.3f} B={smoothed_b:.3f}"
                )
                time.sleep(LOOP_SLEEP)
                continue
            else:
                no_face_since = None

            # Decisione
            desired_scene = current_scene

            if face_a and not face_b:
                desired_scene = SCENE_A
            elif face_b and not face_a:
                desired_scene = SCENE_B
            else:
                if current_scene == SCENE_A:
                    if smoothed_b > smoothed_a + SWITCH_THRESHOLD:
                        desired_scene = SCENE_B
                elif current_scene == SCENE_B:
                    if smoothed_a > smoothed_b + SWITCH_THRESHOLD:
                        desired_scene = SCENE_A
                else:
                    desired_scene = SCENE_A if smoothed_a >= smoothed_b else SCENE_B

            # Persistenza + cooldown
            if desired_scene != current_scene:
                if candidate_scene != desired_scene:
                    candidate_scene = desired_scene
                    candidate_since = now
                else:
                    if (now - candidate_since) >= SWITCH_PERSISTENCE and \
                       (now - last_switch_time) >= SWITCH_COOLDOWN:
                        set_obs_scene(ws, desired_scene)
                        current_scene = desired_scene
                        last_switch_time = now
                        candidate_scene = None
                        candidate_since = None
                        print(f"SWITCH -> {current_scene}")
            else:
                candidate_scene = None
                candidate_since = None

            da = res_a["debug"]
            db = res_b["debug"]
            print(
                f"[{current_scene}] "
                f"A(face={face_a}, score={smoothed_a:.3f}, area={da['face_area_norm']:.3f}, center={da['center_score']:.3f}, conf={da['confidence']:.3f}) | "
                f"B(face={face_b}, score={smoothed_b:.3f}, area={db['face_area_norm']:.3f}, center={db['center_score']:.3f}, conf={db['confidence']:.3f})"
            )

            time.sleep(LOOP_SLEEP)
    finally:
        detector.close()
        ws.disconnect()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")
    except Exception as e:
        print(f"Errore: {e}")