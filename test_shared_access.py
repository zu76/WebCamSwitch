"""
Script di test per verificare l'accesso condiviso alle webcam
Esegui questo script mentre OBS sta usando le webcam per verificare
che il backend Media Foundation funzioni correttamente.
"""
import cv2
import time

CAMERA_INDEX_A = 3
CAMERA_INDEX_B = 1

def test_camera(index, backend_name, backend_flag):
    """Testa l'accesso a una camera con un backend specifico"""
    print(f"\n--- Test Camera {index} con {backend_name} ---")
    
    try:
        cap = cv2.VideoCapture(index, backend_flag)
        
        if not cap.isOpened():
            print(f"✗ Impossibile aprire camera {index} con {backend_name}")
            return False
        
        print(f"✓ Camera {index} aperta con {backend_name}")
        
        # Prova a leggere alcuni frame
        success_count = 0
        for i in range(5):
            ret, frame = cap.read()
            if ret and frame is not None:
                success_count += 1
                h, w = frame.shape[:2]
                print(f"  Frame {i+1}: ✓ OK ({w}x{h})")
            else:
                print(f"  Frame {i+1}: ✗ FAILED")
            time.sleep(0.1)
        
        cap.release()
        
        if success_count >= 3:
            print(f"✓ Test PASSED ({success_count}/5 frames)")
            return True
        else:
            print(f"✗ Test FAILED ({success_count}/5 frames)")
            return False
            
    except Exception as e:
        print(f"✗ Errore durante test: {e}")
        return False

print("="*60)
print("TEST ACCESSO CONDIVISO WEBCAM")
print("="*60)
print("\nQUESTO TEST DEVE ESSERE ESEGUITO MENTRE OBS STA USANDO LE WEBCAM")
print("\nIstruzioni:")
print("1. Avvia OBS")
print("2. Aggiungi le webcam come sorgenti nelle scene CAM_A e CAM_B")
print("3. Assicurati che OBS stia visualizzando le webcam")
print("4. Esegui questo script")
print("\n" + "="*60)

input("\nPremi INVIO quando OBS è pronto e sta usando le webcam...")

print("\n" + "="*60)
print("INIZIO TEST")
print("="*60)

# Test con Media Foundation (dovrebbe funzionare con OBS attivo)
print("\n>>> TEST 1: Media Foundation (MSMF) - Accesso Condiviso <<<")
msmf_a = test_camera(CAMERA_INDEX_A, "MSMF", cv2.CAP_MSMF)
msmf_b = test_camera(CAMERA_INDEX_B, "MSMF", cv2.CAP_MSMF)

# Test con DirectShow (probabilmente fallirà con OBS attivo)
print("\n>>> TEST 2: DirectShow (DSHOW) - Accesso Esclusivo <<<")
print("(Questo test è previsto che fallisca se OBS sta usando le webcam)")
dshow_a = test_camera(CAMERA_INDEX_A, "DSHOW", cv2.CAP_DSHOW)
dshow_b = test_camera(CAMERA_INDEX_B, "DSHOW", cv2.CAP_DSHOW)

# Riepilogo
print("\n" + "="*60)
print("RIEPILOGO RISULTATI")
print("="*60)

print(f"\nCamera {CAMERA_INDEX_A} (CAMERA_A):")
print(f"  MSMF:  {'✓ PASS' if msmf_a else '✗ FAIL'}")
print(f"  DSHOW: {'✓ PASS' if dshow_a else '✗ FAIL'}")

print(f"\nCamera {CAMERA_INDEX_B} (CAMERA_B):")
print(f"  MSMF:  {'✓ PASS' if msmf_b else '✗ FAIL'}")
print(f"  DSHOW: {'✓ PASS' if dshow_b else '✗ FAIL'}")

print("\n" + "="*60)
print("CONCLUSIONE")
print("="*60)

if msmf_a and msmf_b:
    print("\n✓✓✓ OTTIMO! Media Foundation funziona con accesso condiviso!")
    print("    Lo script CamSwitch_obs.py dovrebbe funzionare correttamente")
    print("    anche quando OBS sta usando le webcam.")
elif not msmf_a and not msmf_b and not dshow_a and not dshow_b:
    print("\n✗✗✗ PROBLEMA: Nessun backend funziona!")
    print("    Verifica che:")
    print("    - Gli indici delle camera siano corretti (3 e 1)")
    print("    - Le webcam siano collegate e funzionanti")
    print("    - Non ci siano altri programmi che bloccano le webcam")
else:
    print("\n⚠ PARZIALE: Alcuni test falliti")
    print("  Lo script proverà a usare il fallback OBS WebSocket")
    print("  per le webcam che non sono accessibili via VideoCapture.")
    print("\n  Assicurati che:")
    print("  - OBS WebSocket sia configurato e accessibile")
    print("  - Le webcam siano aggiunte come sorgenti in OBS")
    print("  - I nomi delle sorgenti siano configurati in CamSwitch_obs.py")

print("\n" + "="*60)
