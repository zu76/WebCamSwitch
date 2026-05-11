# WebCamSwitch

Automatic OBS Studio scene switching driven by **head pose and eye gaze**: the camera that the speaker is actually facing and looking at becomes the active scene.

Built for a two-camera podcast / interview / streaming setup where both cameras frame the same person from different angles. Instead of a manual scene switch, the script watches both feeds in real time and switches OBS to whichever camera the subject is most directly facing.

---

## Why this exists

A naive “biggest face wins” approach fails when both cameras see the subject roughly equally well — the score becomes a coin flip and the stream ping‑pongs between scenes.

WebCamSwitch solves this by scoring each camera primarily on **frontality**:

- How directly the head is turned toward *that* camera (yaw + pitch).
- Where the eyes are actually looking (eye‑gaze blendshapes).

The camera the speaker is looking into wins, even when both cameras see the face at a similar size and position.

---

## How it works

```
   ┌──────────────┐     ┌──────────────┐
   │  Webcam A    │     │  Webcam B    │
   └──────┬───────┘     └──────┬───────┘
          │ used by             │ used by
          ▼                     ▼
   ┌──────────────────────────────────┐
   │            OBS Studio            │
   │  ─ Scene CAM_A   ─ Scene CAM_B   │
   │  ─ WebSocket server (port 4455)  │
   └──────────────┬───────────────────┘
                  │ GetSourceScreenshot
                  ▼
   ┌──────────────────────────────────┐
   │         CamSwitch_obs.py         │
   │                                  │
   │  1. Pull JPEG screenshot per     │
   │     camera from OBS WebSocket    │
   │  2. Run MediaPipe FaceLandmarker │
   │     → 478 landmarks              │
   │     → head pose matrix           │
   │     → 52 face blendshapes        │
   │  3. Compute per‑camera score:    │
   │       frontality (head + eyes)   │
   │     + face area                  │
   │     + centering                  │
   │     + detection confidence       │
   │  4. Smooth, apply hysteresis,    │
   │     persistence, cooldown        │
   │  5. SetCurrentProgramScene       │
   │     on OBS via WebSocket         │
   └──────────────────────────────────┘
```

### Scoring

```
score =  0.55 · frontality        # head pose + eye gaze
       + 0.25 · face_area
       + 0.15 · centering
       + 0.05 · detection_confidence
```

`frontality` is a gaussian decay (σ ≈ 25°) over the head yaw/pitch, blended with the *max* of the eight `eyeLookIn/Out/Up/Down × Left/Right` blendshapes (`EYE_GAZE_WEIGHT = 0.4`).

### Switching logic

A switch only fires when **all** of these hold:

1. The candidate camera's smoothed total score beats the current camera by at least `SWITCH_THRESHOLD` (0.05).
2. The candidate camera's frontality beats the current camera's by at least `FRONTALITY_MARGIN` (0.05) — prevents switches driven only by distance or framing changes.
3. The advantage persists for at least `SWITCH_PERSISTENCE` (0.6 s, ~2 cycles).
4. At least `SWITCH_COOLDOWN` (5 s) has elapsed since the last switch.

If neither camera sees a face, the current scene is held (no flicker on brief look‑aways).

---

## Components used

| Component | Purpose |
|---|---|
| **[MediaPipe Tasks – Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)** | 478 facial landmarks, 4×4 facial transformation matrix (head pose), and 52 face blendshapes (incl. eye gaze). |
| **[OpenCV](https://opencv.org/)** (`opencv-python`) | Image decoding, resizing, color conversion. |
| **[obs-websocket-py](https://github.com/Elektordi/obs-websocket-py)** | Client for the OBS WebSocket v5 protocol (screenshots + scene switching). |
| **[NumPy](https://numpy.org/)** | Array handling for the model input and pose math. |
| **[OBS Studio](https://obsproject.com/) ≥ 28** | Hosts the cameras and exposes them as sources; built‑in WebSocket v5 server. |

The `face_landmarker.task` model is downloaded automatically on first run from Google’s public MediaPipe model storage.

---

## Requirements

- **OS**: Windows 10/11 (tested). Should also work on macOS/Linux as long as OBS WebSocket v5 is reachable.
- **Python**: 3.10 – 3.12.
- **OBS Studio**: 28 or newer (WebSocket v5 is built in; no plugin needed).
- **Cameras**: two webcams added as Video Capture sources inside OBS. The script never opens the cameras directly — it asks OBS for screenshots — so there is no exclusive‑access conflict with OBS.

---

## Installation

```bash
git clone https://github.com/zu76/WebCamSwitch.git
cd WebCamSwitch
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # PowerShell
# or: .venv\Scripts\activate.bat (cmd) / source .venv/bin/activate (bash)

pip install opencv-python mediapipe numpy obs-websocket-py
```

On the first run, the script downloads `face_landmarker.task` (~3 MB) into the repo folder.

---

## OBS configuration

1. **Enable WebSocket v5**
   *Tools → WebSocket Server Settings*
   - Enable WebSocket server
   - Server port: `4455` (default)
   - Set a password and copy it

2. **Create scenes and sources**
   - Scene `CAM_A` containing a *Video Capture Device* for camera A.
   - Scene `CAM_B` containing a *Video Capture Device* for camera B.

3. **Note the exact source names**
   These are the names shown under *Sources* in OBS (e.g. `Video Capture Device`, `Video Capture Device 2`). They go into `OBS_SOURCE_A` / `OBS_SOURCE_B`.

---

## Script configuration

Sensitive values are read from environment variables; everything else lives at the top of [`CamSwitch_obs.py`](CamSwitch_obs.py).

### Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OBS_WS_PASSWORD` | **yes** | _(none)_ | OBS WebSocket password. The script exits with an error if this is unset. |
| `OBS_WS_HOST` | no | `localhost` | OBS WebSocket host. |
| `OBS_WS_PORT` | no | `4455` | OBS WebSocket port. |

Set them in your shell before running, or copy [`.env.example`](.env.example) to `.env` and load it with a tool of your choice (`direnv`, `python-dotenv`, etc.). `.env` is gitignored.

```powershell
# PowerShell (current session)
$env:OBS_WS_PASSWORD = "your-obs-password"
python CamSwitch_obs.py
```

```bash
# bash / zsh
export OBS_WS_PASSWORD="your-obs-password"
python CamSwitch_obs.py
```

### In-source configuration

```python
# OBS sources (exact names from the Sources panel)
OBS_SOURCE_A = "Video Capture Device"
OBS_SOURCE_B = "Video Capture Device 2"

# Scenes to switch between
SCENE_A = "CAM_A"
SCENE_B = "CAM_B"

# Capture / analysis
CAPTURE_WIDTH  = 640
CAPTURE_HEIGHT = 480
ANALYSIS_WIDTH = 640

# Pacing
LOOP_SLEEP         = 0.35   # ~3 Hz
SWITCH_PERSISTENCE = 0.6    # confirm window (s)
SWITCH_COOLDOWN    = 5.0    # min seconds between switches
SMOOTHING_ALPHA    = 0.45   # EMA on scores

# Decision thresholds
SWITCH_THRESHOLD   = 0.05   # total-score margin
FRONTALITY_MARGIN  = 0.05   # frontality margin (anti-jitter gate)

# Score weights (sum = 1.0)
W_FRONTALITY = 0.55
W_FACE_AREA  = 0.25
W_CENTERING  = 0.15
W_CONFIDENCE = 0.05

# Frontality model
FRONTALITY_SIGMA_RAD = math.radians(25.0)  # head-pose tolerance
EYE_GAZE_WEIGHT      = 0.4                 # head vs. eyes blend
```

---

## Running

```bash
python CamSwitch_obs.py
```

Expected output:

```
Connessione a OBS...
Connesso a OBS.

Camera A: 'Video Capture Device' OK (640x480)
Camera B: 'Video Capture Device 2' OK (640x480)

Loop avviato. Premi CTRL+C per uscire.

[CAM_A] A(face=True, score=0.612, front=0.870, yaw=-2, pitch=+3, eye=0.12, area=0.090, center=0.640) | B(face=True, score=0.431, front=0.520, yaw=+22, pitch=+5, eye=0.55, area=0.088, center=0.610)
[CAM_A] A(face=True, score=0.598, ...) | B(face=True, score=0.612, front=0.851, ...)
SWITCH -> CAM_B
[CAM_B] ...
```

Each log line shows, per camera:

| Field | Meaning |
|---|---|
| `face` | Whether a face was detected on this frame |
| `score` | Smoothed combined score (0–1) |
| `front` | Frontality (head pose + eye gaze, 0–1) |
| `yaw`, `pitch` | Head rotation in degrees (0 = facing the camera) |
| `eye` | Eye‑gaze offset (0 = looking into camera, 1 = fully averted) |
| `area` | Face area as a fraction of the frame |
| `center` | How centered the face is in the frame (1 = centered) |

Stop with `Ctrl+C`.

---

## Tuning guide

| You want… | Change |
|---|---|
| Snappier reaction | Lower `LOOP_SLEEP` (e.g. 0.20) and/or `SWITCH_PERSISTENCE` (e.g. 0.4) |
| Lower CPU usage | Raise `LOOP_SLEEP` (e.g. 0.7) — model inference is the dominant cost |
| Fewer switches | Raise `SWITCH_THRESHOLD`, `FRONTALITY_MARGIN`, `SWITCH_COOLDOWN` |
| More eye‑driven decisions | Raise `EYE_GAZE_WEIGHT` toward 1.0 |
| Tolerate larger off‑axis head poses | Increase `FRONTALITY_SIGMA_RAD` (e.g. `math.radians(35.0)`) |

---

## Performance

On a typical modern desktop CPU:

- **Model inference**: ~15–35 ms per camera per cycle (CPU, XNNPACK).
- **Loop rate**: ~3 iterations / second at the default `LOOP_SLEEP = 0.35` — well within budget.
- **CPU**: a few percent of one core during normal operation.
- **Memory**: ~150 MB resident (mostly MediaPipe + TFLite runtime).
- **No GPU required.**

The OBS screenshot round‑trip is the second largest cost after model inference; both are well under the per‑cycle budget.

---

## Repository layout

| File | Role |
|---|---|
| [`CamSwitch_obs.py`](CamSwitch_obs.py) | Main script. Connects to OBS, scores both cameras, switches scenes. |
| `face_landmarker.task` | MediaPipe model, auto‑downloaded on first run (gitignored). |
| `list_cameras.py`, `check_cameras.py` | Legacy helpers from the previous direct‑OpenCV capture approach. Not required when running through OBS WebSocket. |
| `diagnose.py`, `test_shared_access.py` | Legacy diagnostics. |
| `CamSwitch_obs.py.bak`, `detector.tflite` | Legacy artifacts from the previous BlazeFace‑based version. |
| `README_USAGE.md`, `QUICKSTART.md` | Older Italian usage notes; superseded by this README. |

---

## Troubleshooting

**`Errore screenshot da <source>`**
The source name in `OBS_SOURCE_A` / `OBS_SOURCE_B` does not exactly match a source in OBS. Open the Sources panel and copy the name verbatim (case sensitive, including any trailing digit).

**`impossibile catturare da '<source>'` at startup**
The OBS source is present but is producing black frames. Activate the source (make it visible in a scene), check that the underlying camera is not disabled, and try again.

**Cannot connect to OBS**
- WebSocket server enabled in OBS? (Tools → WebSocket Server Settings)
- Port and password match `OBS_PORT` / `OBS_PASSWORD`?
- Firewall not blocking `localhost:4455`?

**Switches feel wrong / oscillate**
Watch the log for a few seconds while looking at each camera: the camera you are facing should clearly have higher `front` and lower `eye`. If not, increase `FRONTALITY_MARGIN` and/or `SWITCH_THRESHOLD`. If yes but it still oscillates, increase `SWITCH_PERSISTENCE`.

**Model fails to download**
Download `face_landmarker.task` manually from
`https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`
and place it next to `CamSwitch_obs.py`.

---

## License

Released under the [MIT License](LICENSE).

---

## Acknowledgements

- [Google MediaPipe](https://ai.google.dev/edge/mediapipe) — Face Landmarker model and runtime.
- [OBS Studio](https://obsproject.com/) and the [OBS WebSocket](https://github.com/obsproject/obs-websocket) protocol.
