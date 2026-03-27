# Quick Start Guide - WebCamSwitch

## 🚀 Avvio Rapido

### Prima Esecuzione

1️⃣ **Installa dipendenze** (se non fatto):
```bash
pip install opencv-python mediapipe obs-websocket-py numpy
```

2️⃣ **Configura OBS**:
   - Avvia OBS
   - Abilita WebSocket: Tools → WebSocket Server Settings
   - Crea scena "CAM_A" con sorgente webcam camera A
   - Crea scena "CAM_B" con sorgente webcam camera B

3️⃣ **Identifica indici webcam**:
```bash
python list_cameras.py
```
Aggiorna `CAMERA_INDEX_A` e `CAMERA_INDEX_B` in `CamSwitch_obs.py`

4️⃣ **Diagnostica sistema**:
```bash
python diagnose.py
```
Verifica che tutti i check siano ✓

5️⃣ **Test accesso condiviso** (con OBS attivo):
```bash
python test_shared_access.py
```
Verifica che MSMF funzioni ✓

6️⃣ **Avvia lo script**:
```bash
python CamSwitch_obs.py
```

---

## 📋 Elenco Script

| Script | Descrizione | Quando Usare |
|--------|-------------|--------------|
| `CamSwitch_obs.py` | **Script principale** | Esecuzione normale |
| `diagnose.py` | Diagnostica completa sistema | Prima esecuzione o problemi |
| `test_shared_access.py` | Test accesso condiviso | Verificare MSMF con OBS attivo |
| `list_cameras.py` | Elenca webcam e backend | Trovare indici webcam |
| `check_cameras.py` | Verifica rapida webcam | Check veloce disponibilità |

---

## ⚙️ Configurazione Rapida

Apri `CamSwitch_obs.py` e modifica:

```python
# INDICI WEBCAM (usa list_cameras.py per trovarli)
CAMERA_INDEX_A = 3
CAMERA_INDEX_B = 1

# NOMI SCENE OBS
SCENE_A = "CAM_A"
SCENE_B = "CAM_B"

# NOMI SORGENTI OBS (opzionale, per fallback screenshot)
# Lascia None per auto-discovery
OBS_SOURCE_A = None  # es. "Webcam A"
OBS_SOURCE_B = None  # es. "Webcam B"

# CONNESSIONE OBS WEBSOCKET
OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "la_tua_password"

# MODALITÀ CATTURA
CAPTURE_MODE = "auto"  # auto | videocapture | obs_screenshot
```

---

## 🔧 Risoluzione Problemi Rapida

### "Impossibile aprire camera X"

### "Errore OpenCV: _step >= minstep" (RISOLTO)

**Problema**: Media Foundation su alcune webcam restituisce frame con layout di memoria incompatibile con OpenCV/MediaPipe.

**Soluzione**: Lo script ora rileva automaticamente questo problema durante l'inizializzazione e passa a DirectShow se necessario. Se vedi il messaggio "Media Foundation fallito", è normale - lo script userà automaticamente DirectShow.

### "Impossibile aprire camera X"

```bash
# 1. Verifica indici
python list_cameras.py

# 2. Controlla diagnostica
python diagnose.py

# 3. Se MSMF non funziona, usa fallback OBS:
# In CamSwitch_obs.py, imposta:
CAPTURE_MODE = "obs_screenshot"
OBS_SOURCE_A = "nome_esatto_sorgente_A_in_obs"
OBS_SOURCE_B = "nome_esatto_sorgente_B_in_obs"
```

### "Frame non valido"

```bash
# Verifica con OBS attivo
python test_shared_access.py
```

### OBS non si connette

1. Verifica che OBS sia in esecuzione
2. Check WebSocket: Tools → WebSocket Server Settings → Enable
3. Verifica password in `CamSwitch_obs.py`

---

## 📊 Output Atteso

Quando funziona correttamente:

```
Connessione a OBS...
Connesso a OBS.

Apertura camera A...
Camera 3: Tentativo apertura con Media Foundation...
Camera 3: ✓ Media Foundation OK
Camera 3: Usando VideoCapture (backend condiviso)

Apertura camera B...
Camera 1: Tentativo apertura con Media Foundation...
Camera 1: ✓ Media Foundation OK
Camera 1: Usando VideoCapture (backend condiviso)

==================================================
Loop avviato. Premi CTRL+C per uscire.

[CAM_A] A(face=True, score=0.456, ...) | B(face=True, score=0.312, ...)
[CAM_A] A(face=True, score=0.478, ...) | B(face=True, score=0.498, ...)
🔄 SWITCH -> CAM_B
[CAM_B] A(face=True, score=0.445, ...) | B(face=True, score=0.512, ...)
```

---

## 📚 Documentazione Completa

Consulta `README_USAGE.md` per:
- Spiegazione dettagliata del problema risolto
- Guida completa configurazione
- Dettagli tecnici implementazione
- Risoluzione problemi avanzata
- Ottimizzazione performance

---

## 💡 Suggerimenti

- **Performance**: Se riscontri lag, aumenta `LOOP_SLEEP` da 0.15 a 0.25
- **Stabilità switch**: Aumenta `SWITCH_THRESHOLD` da 0.01 a 0.05
- **Compatibilità**: Se MSMF non funziona, il sistema usa automaticamente DSHOW o OBS screenshot
- **Debug**: Osserva i log all'avvio per vedere quale backend viene usato

---

**Tutto pronto!** Esegui `python diagnose.py` per iniziare. 🎥
