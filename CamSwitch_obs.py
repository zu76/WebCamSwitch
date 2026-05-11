import time
import math
import os
import sys
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

# OBS WebSocket connection. The password is read from the OBS_WS_PASSWORD
# environment variable so it is never committed to the repository.
# Optional overrides: OBS_WS_HOST, OBS_WS_PORT.
OBS_HOST = os.environ.get("OBS_WS_HOST", "localhost")
OBS_PORT = int(os.environ.get("OBS_WS_PORT", "4455"))
OBS_PASSWORD = os.environ.get("OBS_WS_PASSWORD", "")

# Risoluzione cattura screenshot OBS (ridotta per performance)
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480

# Parametri logica
ANALYSIS_WIDTH = 640
LOOP_SLEEP = 0.20              # ~5 cicli al secondo (sensing piu' rapido)
SWITCH_THRESHOLD = 0.05        # vantaggio minimo richiesto sul punteggio totale
FRONTALITY_MARGIN = 0.05       # vantaggio minimo richiesto sulla frontality (anti-jitter)
SWITCH_PERSISTENCE = 0.3       # secondi per confermare lo switch (transizione rapida)
SWITCH_COOLDOWN = 8.0          # secondi minimi tra switch (transizioni piu' saltuarie)
NO_FACE_HOLD_SECONDS = 2.0     # se nessuna camera vede il volto, tieni l'ultima
SMOOTHING_ALPHA = 0.55         # media esponenziale score (piu' reattivo)

# Pesi score (somma = 1.0). La frontality (testa + sguardo verso la camera) domina.
W_FRONTALITY = 0.55
W_FACE_AREA  = 0.25
W_CENTERING  = 0.15
W_CONFIDENCE = 0.05

# Frontality - decadimento gaussiano sull'angolo combinato yaw/pitch (radianti).
# sigma ~= 25 gradi: a 0 deg score=1.0, a 25 deg ~0.61, a 45 deg ~0.20.
FRONTALITY_SIGMA_RAD = math.radians(25.0)
# Peso relativo dello sguardo oculare (blendshapes) rispetto alla posa della testa.
# 0 = ignora gli occhi, 1 = solo occhi. 0.4 = la testa pesa di piu' ma gli occhi rifiniscono.
EYE_GAZE_WEIGHT = 0.4

# =========================
# MEDIAPIPE
# =========================

from mediapipe import tasks

MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_landmarker.task")
if not os.path.exists(MODEL_PATH):
    import urllib.request
    MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    print(f"Downloading face landmarker model to {MODEL_PATH}...")
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
        "debug": {
            "face_area_norm": 0.0,
            "center_score": 0.0,
            "confidence": 0.0,
            "frontality": 0.0,
            "yaw_deg": 0.0,
            "pitch_deg": 0.0,
            "eye_offset": 0.0,
        }
    }

def extract_yaw_pitch(matrix):
    """Estrae yaw (rotazione Y) e pitch (rotazione X) dalla matrice 4x4 di
    trasformazione facciale di MediaPipe. Restituisce angoli in radianti.
    Frontale -> yaw=0, pitch=0."""
    # MediaPipe restituisce una matrice 4x4 column-major-friendly (numpy array).
    R = np.asarray(matrix, dtype=np.float64)[:3, :3]
    # Tait-Bryan Y-X-Z: pitch = asin(-R[1,2]), yaw = atan2(R[0,2], R[2,2])
    sin_pitch = -R[1, 2]
    sin_pitch = max(-1.0, min(1.0, sin_pitch))
    pitch = math.asin(sin_pitch)
    yaw = math.atan2(R[0, 2], R[2, 2])
    return yaw, pitch

def compute_head_frontality(yaw_rad, pitch_rad, sigma_rad=FRONTALITY_SIGMA_RAD):
    """1.0 quando la testa e' perfettamente frontale, ~0 in profilo."""
    angle_sq = yaw_rad * yaw_rad + pitch_rad * pitch_rad
    return math.exp(-angle_sq / (2.0 * sigma_rad * sigma_rad))

# Nomi blendshapes MediaPipe che indicano sguardo NON diretto verso la camera.
_EYE_GAZE_BLENDSHAPES = (
    "eyeLookInLeft", "eyeLookOutLeft",
    "eyeLookInRight", "eyeLookOutRight",
    "eyeLookUpLeft", "eyeLookUpRight",
    "eyeLookDownLeft", "eyeLookDownRight",
)

def compute_eye_offset(blendshapes):
    """Restituisce un valore [0..1] dove 0 = occhi puntati alla camera,
    1 = occhi completamente deviati. Usa il MAX dei blendshapes di sguardo:
    se anche solo una direzione e' fortemente attiva, gli occhi sono altrove."""
    if not blendshapes:
        return 0.0
    by_name = {b.category_name: b.score for b in blendshapes}
    vals = [by_name.get(n, 0.0) for n in _EYE_GAZE_BLENDSHAPES]
    if not vals:
        return 0.0
    return clamp(max(vals), 0.0, 1.0)

def compute_frontality(yaw_rad, pitch_rad, eye_offset):
    """Combina posa della testa e sguardo oculare in un unico score [0..1]."""
    head_front = compute_head_frontality(yaw_rad, pitch_rad)
    eye_front = 1.0 - eye_offset
    # Media pesata: head_front pesa (1 - EYE_GAZE_WEIGHT), eye_front pesa EYE_GAZE_WEIGHT.
    return clamp((1.0 - EYE_GAZE_WEIGHT) * head_front + EYE_GAZE_WEIGHT * eye_front)

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

    landmarks_list = getattr(results, "face_landmarks", None) or []
    if not landmarks_list:
        return _empty_result()

    matrixes = getattr(results, "facial_transformation_matrixes", None) or []
    blendshapes_list = getattr(results, "face_blendshapes", None) or []

    best_score = -1.0
    best_debug = None

    for i, lms in enumerate(landmarks_list):
        if not lms:
            continue
        # Bounding box dai landmark normalizzati [0..1].
        xs = [lm.x for lm in lms]
        ys = [lm.y for lm in lms]
        x_min, x_max = max(0.0, min(xs)), min(1.0, max(xs))
        y_min, y_max = max(0.0, min(ys)), min(1.0, max(ys))
        bw_n = x_max - x_min
        bh_n = y_max - y_min
        if bw_n <= 0 or bh_n <= 0:
            continue
        face_area_norm = clamp(bw_n * bh_n)
        center_x = (x_min + x_max) * 0.5 * w
        center_y = (y_min + y_max) * 0.5 * h
        center_score = compute_center_score(center_x, center_y, w, h)

        # Confidenza: FaceLandmarker non espone uno score diretto, usiamo l'area
        # come proxy (clampata) per mantenere la stessa struttura logica.
        score_conf = clamp(face_area_norm * 4.0)

        # Posa della testa.
        yaw = pitch = 0.0
        if i < len(matrixes) and matrixes[i] is not None:
            try:
                yaw, pitch = extract_yaw_pitch(matrixes[i])
            except Exception:
                yaw = pitch = 0.0

        # Sguardo oculare dai blendshapes.
        eye_offset = 0.0
        if i < len(blendshapes_list) and blendshapes_list[i]:
            try:
                eye_offset = compute_eye_offset(blendshapes_list[i])
            except Exception:
                eye_offset = 0.0

        frontality = compute_frontality(yaw, pitch, eye_offset)

        total_score = (
            W_FRONTALITY * frontality +
            W_FACE_AREA  * face_area_norm +
            W_CENTERING  * center_score +
            W_CONFIDENCE * score_conf
        )
        if total_score > best_score:
            best_score = total_score
            best_debug = {
                "face_area_norm": face_area_norm,
                "center_score": center_score,
                "confidence": score_conf,
                "frontality": frontality,
                "yaw_deg": math.degrees(yaw),
                "pitch_deg": math.degrees(pitch),
                "eye_offset": eye_offset,
            }

    if best_score < 0 or best_debug is None:
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
    if not OBS_PASSWORD:
        print(
            "ERROR: OBS_WS_PASSWORD environment variable is not set.\n"
            "       Set it to your OBS WebSocket password before running, e.g.:\n"
            "         PowerShell:  $env:OBS_WS_PASSWORD = 'your-password'\n"
            "         cmd.exe:     set OBS_WS_PASSWORD=your-password\n"
            "         bash:        export OBS_WS_PASSWORD='your-password'\n"
            "       See .env.example and README.md for details.",
            file=sys.stderr,
        )
        sys.exit(2)

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

    # Face landmarker (posa testa + blendshapes per sguardo oculare)
    base_options = tasks.BaseOptions(model_asset_path=MODEL_PATH)
    options = tasks.vision.FaceLandmarkerOptions(
        base_options=base_options,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    detector = tasks.vision.FaceLandmarker.create_from_options(options)

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

            # Decisione: doppio gate (score totale + frontality) per evitare switch
            # quando entrambe le camere vedono il volto ma una sola e' guardata.
            front_a = res_a["debug"]["frontality"]
            front_b = res_b["debug"]["frontality"]
            desired_scene = current_scene

            if face_a and not face_b:
                desired_scene = SCENE_A
            elif face_b and not face_a:
                desired_scene = SCENE_B
            else:
                if current_scene == SCENE_A:
                    if (smoothed_b > smoothed_a + SWITCH_THRESHOLD) and \
                       (front_b > front_a + FRONTALITY_MARGIN):
                        desired_scene = SCENE_B
                elif current_scene == SCENE_B:
                    if (smoothed_a > smoothed_b + SWITCH_THRESHOLD) and \
                       (front_a > front_b + FRONTALITY_MARGIN):
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
                f"A(face={face_a}, score={smoothed_a:.3f}, front={da['frontality']:.3f}, "
                f"yaw={da['yaw_deg']:+.0f}, pitch={da['pitch_deg']:+.0f}, eye={da['eye_offset']:.2f}, "
                f"area={da['face_area_norm']:.3f}, center={da['center_score']:.3f}) | "
                f"B(face={face_b}, score={smoothed_b:.3f}, front={db['frontality']:.3f}, "
                f"yaw={db['yaw_deg']:+.0f}, pitch={db['pitch_deg']:+.0f}, eye={db['eye_offset']:.2f}, "
                f"area={db['face_area_norm']:.3f}, center={db['center_score']:.3f})"
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