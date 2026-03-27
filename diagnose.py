"""
Script diagnostico rapido per verificare la configurazione
Esegui questo prima di avviare CamSwitch_obs.py
"""
import sys

print("="*70)
print("DIAGNOSTICA SISTEMA - WebCamSwitch")
print("="*70)

# Check 1: Import dipendenze
print("\n[1] Verifica dipendenze...")
try:
    import cv2
    print("  ✓ opencv-python installato (version: {})".format(cv2.__version__))
except ImportError:
    print("  ✗ opencv-python NON installato")
    print("    Installa con: pip install opencv-python")
    sys.exit(1)

try:
    import mediapipe as mp
    print("  ✓ mediapipe installato")
except ImportError:
    print("  ✗ mediapipe NON installato")
    print("    Installa con: pip install mediapipe")
    sys.exit(1)

try:
    from obswebsocket import obsws, requests
    print("  ✓ obs-websocket-py installato")
except ImportError:
    print("  ✗ obs-websocket-py NON installato")
    print("    Installa con: pip install obs-websocket-py")
    sys.exit(1)

try:
    import numpy as np
    print("  ✓ numpy installato")
except ImportError:
    print("  ✗ numpy NON installato")
    print("    Installa con: pip install numpy")
    sys.exit(1)

# Check 2: Backend OpenCV
print("\n[2] Verifica backend OpenCV disponibili...")
backends = []

# Test MSMF
cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
if cap.isOpened():
    backends.append("MSMF (Media Foundation)")
    cap.release()

# Test DSHOW
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if cap.isOpened():
    backends.append("DSHOW (DirectShow)")
    cap.release()

if backends:
    for backend in backends:
        print(f"  ✓ {backend}")
else:
    print("  ✗ Nessun backend disponibile (problema con i driver webcam?)")

# Check 3: File modello face detection
print("\n[3] Verifica modello face detection...")
import os
MODEL_PATH = os.path.join(os.path.dirname(__file__), "detector.tflite")
if os.path.exists(MODEL_PATH):
    size_mb = os.path.getsize(MODEL_PATH) / (1024*1024)
    print(f"  ✓ detector.tflite trovato ({size_mb:.2f} MB)")
else:
    print("  ⚠ detector.tflite non trovato (verrà scaricato al primo avvio)")

# Check 4: Parametri configurazione
print("\n[4] Lettura configurazione da CamSwitch_obs.py...")
try:
    # Leggi il file per estrarre i parametri
    with open("CamSwitch_obs.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    import re
    
    # Estrai parametri
    def extract_param(name, content):
        match = re.search(rf'^{name}\s*=\s*(.+?)(?:\s*#|$)', content, re.MULTILINE)
        return match.group(1).strip() if match else "Non trovato"
    
    cam_a = extract_param("CAMERA_INDEX_A", content)
    cam_b = extract_param("CAMERA_INDEX_B", content)
    scene_a = extract_param("SCENE_A", content)
    scene_b = extract_param("SCENE_B", content)
    obs_host = extract_param("OBS_HOST", content)
    obs_port = extract_param("OBS_PORT", content)
    capture_mode = extract_param("CAPTURE_MODE", content)
    
    print(f"  Camera A: indice {cam_a}, scena {scene_a}")
    print(f"  Camera B: indice {cam_b}, scena {scene_b}")
    print(f"  OBS: {obs_host}:{obs_port}")
    print(f"  Modalità cattura: {capture_mode}")
    
except Exception as e:
    print(f"  ⚠ Errore nella lettura configurazione: {e}")

# Check 5: Test connessione OBS
print("\n[5] Test connessione OBS WebSocket...")
print("  (assicurati che OBS sia in esecuzione)")

try:
    from obswebsocket import obsws
    
    # Prova a leggere i parametri dal file
    obs_host = "localhost"
    obs_port = 4455
    obs_password = "fbUKojx3JWxxxUW9"
    
    ws = obsws(obs_host, obs_port, obs_password)
    ws.connect()
    
    # Ottieni info versione
    from obswebsocket import requests
    resp = ws.call(requests.GetVersion())
    obs_version = resp.getObsVersion()
    ws_version = resp.getObsWebSocketVersion()
    
    print(f"  ✓ Connesso a OBS {obs_version}")
    print(f"  ✓ OBS WebSocket version: {ws_version}")
    
    # Verifica scene
    resp = ws.call(requests.GetSceneList())
    scenes = [s['sceneName'] for s in resp.getScenes()]
    
    if "CAM_A" in scenes:
        print("  ✓ Scena CAM_A trovata")
    else:
        print("  ⚠ Scena CAM_A NON trovata (crea la scena in OBS)")
    
    if "CAM_B" in scenes:
        print("  ✓ Scena CAM_B trovata")
    else:
        print("  ⚠ Scena CAM_B NON trovata (crea la scena in OBS)")
    
    # Verifica sorgenti webcam
    resp = ws.call(requests.GetSourcesList())
    sources = resp.getSources()
    camera_sources = [
        s['sourceName'] for s in sources 
        if 'dshow_input' in s.get('typeId', '') or 'video_capture' in s.get('typeId', '').lower()
    ]
    
    if camera_sources:
        print(f"  ✓ Sorgenti webcam trovate: {camera_sources}")
    else:
        print("  ⚠ Nessuna sorgente webcam trovata in OBS")
        print("    Aggiungi le webcam come sorgenti 'Video Capture Device'")
    
    ws.disconnect()
    print("  ✓ Test OBS completato con successo")
    
except ConnectionRefusedError:
    print("  ✗ Connessione rifiutata")
    print("    - Verifica che OBS sia in esecuzione")
    print("    - Verifica che OBS WebSocket sia abilitato")
    print("    - Verifica host e porta in CamSwitch_obs.py")
except Exception as e:
    print(f"  ✗ Errore: {e}")
    print("    - Verifica la password OBS in CamSwitch_obs.py")
    print("    - Verifica che OBS WebSocket sia abilitato")

# Riepilogo finale
print("\n" + "="*70)
print("RIEPILOGO")
print("="*70)
print("\nSe tutti i check sono ✓, puoi avviare CamSwitch_obs.py")
print("\nPer testare l'accesso condiviso con OBS attivo:")
print("  python test_shared_access.py")
print("\nPer avviare lo script principale:")
print("  python CamSwitch_obs.py")
print("\n" + "="*70)
