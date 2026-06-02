import sounddevice as sd
import numpy as np
import subprocess
import time

THRESHOLD = 1.5
CLAP_COUNT = 0
last_clap_time = 0
COOLDOWN = 0.3
stop_detector = False  # flag to stop the detector

def trigger_ai():
    print("Triggering AI...")
    subprocess.Popen(["python", "C:\\Users\\asus\\Desktop\\projects\\AI\\JJ.py"])
    global stop_detector
    stop_detector = True  # signal the main loop to exit safely

def detect_clap(indata, frames, time_info, status):
    global CLAP_COUNT, last_clap_time

    try:
        volume_norm = np.linalg.norm(indata)
        now = time.time()

        if now - last_clap_time < COOLDOWN:
            return

        if volume_norm > THRESHOLD:
            print(f"Sound detected: {volume_norm:.2f}")

            if now - last_clap_time < 1:  # second clap window
                CLAP_COUNT += 1
            else:
                CLAP_COUNT = 1

            last_clap_time = now

            if CLAP_COUNT == 2:
                print("✅ Double clap detected!")
                CLAP_COUNT = 0
                trigger_ai()
    except Exception:
        pass  # ignore callback errors

print("Listening for claps...")

with sd.InputStream(callback=detect_clap):
    while not stop_detector:
        time.sleep(0.01)  # keep CPU usage low

print("Clap detector stopped.")