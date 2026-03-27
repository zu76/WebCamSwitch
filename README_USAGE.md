# WebCamSwitch per OBS - Guida all'uso

## Problema Risolto

Lo script ora supporta l'accesso condiviso alle webcam anche quando OBS le sta utilizzando. Il problema originale (conflitto di accesso esclusivo) è stato risolto implementando:

1. **Backend Media Foundation (MSMF)**: Supporta accesso condiviso su Windows 10/11
2. **Fallback DirectShow**: Per compatibilità con sistemi più vecchi
3. **Fallback OBS WebSocket**: Cattura screenshot dalle sorgenti OBS se VideoCapture non funziona

## Configurazione

### 1. Parametri Base (in `CamSwitch_obs.py`)

```python
CAMERA_INDEX_A = 3          # Indice prima webcam
CAMERA_INDEX_B = 1          # Indice seconda webcam

SCENE_A = "CAM_A"           # Nome scena OBS per camera A
SCENE_B = "CAM_B"           # Nome scena OBS per camera B

OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "fbUKojx3JWxxxUW9"
```

### 2. Nomi Sorgenti OBS (opzionale)

Se usi il fallback OBS WebSocket, configura i nomi delle sorgenti:

```python
OBS_SOURCE_A = "Webcam A"   # Nome sorgente in OBS per camera A
OBS_SOURCE_B = "Webcam B"   # Nome sorgente in OBS per camera B
```

Se lasci `None`, lo script proverà a rilevare automaticamente le sorgenti webcam in OBS.

### 3. Modalità di Cattura

```python
CAPTURE_MODE = "auto"  # Opzioni: "auto", "videocapture", "obs_screenshot"
```

- **"auto"**: Prova prima VideoCapture (MSMF/DirectShow), poi fallback a OBS screenshot
- **"videocapture"**: Solo VideoCapture (fallisce se OBS blocca l'accesso)
- **"obs_screenshot"**: Solo screenshot OBS (più lento ma sempre funzionante)

## Script di Utilità

### `test_shared_access.py`

**Uso**: Verifica che l'accesso condiviso funzioni mentre OBS è attivo

```bash
python test_shared_access.py
```

Questo script:
1. Chiede di avviare OBS e attivare le webcam
2. Testa l'accesso con MSMF (accesso condiviso)
3. Testa l'accesso con DirectShow (accesso esclusivo)
4. Mostra un riepilogo dei risultati

### `list_cameras.py`

**Uso**: Elenca tutte le webcam disponibili e i backend supportati

```bash
python list_cameras.py
```

Output esempio:
```
✓ Camera Index 1:
  - MSMF: 1280x720 @ 30fps
  - DSHOW: 1280x720 @ 30fps
✓ Camera Index 3:
  - MSMF: 1920x1080 @ 30fps
  - DSHOW: 1920x1080 @ 30fps
```

### `check_cameras.py`

**Uso**: Verifica rapida disponibilità webcam

```bash
python check_cameras.py
```

## Come Usare lo Script Principale

### Passo 1: Configura OBS

1. Avvia OBS
2. Abilita OBS WebSocket:
   - Menu → Tools → WebSocket Server Settings
   - Abilita "Enable WebSocket server"
   - Imposta password (stessa in `OBS_PASSWORD`)
   - Annota la porta (default: 4455)

3. Crea le scene:
   - Crea scena "CAM_A"
   - Aggiungi sorgente "Video Capture Device" per CAMERA_INDEX_A
   - Crea scena "CAM_B"
   - Aggiungi sorgente "Video Capture Device" per CAMERA_INDEX_B

### Passo 2: Identifica gli Indici delle Webcam

```bash
python list_cameras.py
```

Annota gli indici delle tue webcam e aggiornali in `CamSwitch_obs.py`.

### Passo 3: (Opzionale) Testa l'Accesso Condiviso

```bash
python test_shared_access.py
```

Segui le istruzioni per verificare che MSMF funzioni.

### Passo 4: Avvia lo Script

```bash
python CamSwitch_obs.py
```

Lo script:
- Si connette a OBS
- Apre le webcam (usando MSMF se possibile)
- Rileva i volti in entrambe le webcam
- Switcha automaticamente alla camera con il volto migliore

## Risoluzione Problemi

### "Impossibile aprire camera X"

**Causa**: Né VideoCapture né OBS screenshot funzionano

**Soluzioni**:
1. Verifica gli indici webcam con `list_cameras.py`
2. Controlla che OBS abbia le sorgenti webcam attive
3. Configura `OBS_SOURCE_A` e `OBS_SOURCE_B` con i nomi esatti delle sorgenti OBS
4. Prova a cambiare `CAPTURE_MODE` a `"obs_screenshot"`

### "Frame non valido da Camera X"

**Causa**: La webcam non restituisce frame validi

**Soluzioni**:
1. Verifica che la webcam funzioni in altre applicazioni
2. Prova a ridurre la risoluzione nelle impostazioni OBS
3. Riavvia OBS e lo script
4. Controlla che il driver della webcam sia aggiornato

### Performance Scadenti / Lag

**Causa**: Media Foundation o screenshot OBS sono più lenti di DirectShow

**Soluzioni**:
1. Aumenta `LOOP_SLEEP` (es. da 0.15 a 0.25)
2. Riduci la risoluzione capture in OBS
3. Riduci `ANALYSIS_WIDTH` (es. da 640 a 480)
4. Chiudi altre applicazioni che usano CPU/GPU

### Switch Troppo Frequenti

**Causa**: Parametri di persistenza/threshold troppo bassi

**Soluzioni**:
1. Aumenta `SWITCH_THRESHOLD` (es. da 0.01 a 0.05)
2. Aumenta `SWITCH_PERSISTENCE` (es. da 0.2 a 0.5)
3. Aumenta `SWITCH_COOLDOWN` (es. da 1.0 a 2.0)

## Dettagli Tecnici

### Backend Supportati

1. **Media Foundation (CAP_MSMF)**
   - ✓ Accesso condiviso con OBS
   - ✓ Windows 10/11
   - ⚠ Può essere più lento di DirectShow
   - ⚠ Non tutti i driver supportano MSMF

2. **DirectShow (CAP_DSHOW)**
   - ✓ Alta compatibilità
   - ✓ Performance ottimali
   - ✗ Accesso esclusivo (conflitto con OBS)

3. **OBS WebSocket Screenshot**
   - ✓ Funziona sempre se OBS è attivo
   - ✓ Nessun conflitto di accesso
   - ⚠ Più lento (richiede decode base64)
   - ⚠ Richiede configurazione sorgenti OBS

### Logica di Fallback

```
1. Prova CAP_MSMF (Media Foundation)
   ↓ fallisce
2. Prova CAP_DSHOW (DirectShow)
   ↓ fallisce
3. Usa OBS Screenshot (GetSourceScreenshot)
   ↓ fallisce
4. Errore: impossibile accedere alla camera
```

### Classe CameraCapture

La classe `CameraCapture` astrae l'accesso alla camera:

```python
# Uso trasparente - stesso codice per tutti i backend
cap = CameraCapture(index, obs_client)
ok, frame = cap.read()  # Funziona sia per VideoCapture che OBS screenshot
```

## File del Progetto

- `CamSwitch_obs.py` - Script principale
- `test_shared_access.py` - Test accesso condiviso
- `list_cameras.py` - Lista webcam e backend
- `check_cameras.py` - Verifica veloce webcam
- `detector.tflite` - Modello MediaPipe face detection
- `README_USAGE.md` - Questo file

## Requisiti

```bash
pip install opencv-python mediapipe obs-websocket-py numpy
```

- Python 3.8+
- Windows 10/11 (per Media Foundation)
- OBS Studio 28+ (con OBS WebSocket)
