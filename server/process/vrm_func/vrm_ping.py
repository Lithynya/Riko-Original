# trigger_test.py
import requests
import time
from pathlib import Path
def vrm_talk(aud_path, expression, audio_text, audio_duraction):
    url = "http://localhost:8080/talk"
    payload = {
        "audio_path": aud_path,
        "expression": expression,
        "audio_text": audio_text,
        "audio_duraction": audio_duraction,
    }
    resp = requests.post(url, json=payload)
    print("Status:", resp.status_code)
    print("Response:", resp.json())


if __name__ == "__main__":
    audio_path = Path("setup_files") / "main_sample.wav"
    vrm_talk(str(audio_path), "relaxed", "Rayen, I love you so much. You're the greatest programmer alive!", 4)
    time.sleep(4)
