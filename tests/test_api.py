import os
import wave
import struct
import math
import pytest
from fastapi.testclient import TestClient
from audio_app.server import app

client = TestClient(app)

def test_api_stats():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_candidates" in data
    assert "total_audio_submissions" in data
    print("[PASS] /api/stats endpoint verified.")

def test_duplicate_check_api():
    # Rohit Nair exists in database
    response = client.post(
        "/api/candidates/check-duplicate",
        json={"phone": "+91-9000000268", "name": "Rohit Nair"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_duplicate"] is True
    print("[PASS] /api/candidates/check-duplicate verified.")

def test_audio_submission_api(tmp_path):
    wav_path = os.path.join(tmp_path, "candidate_sample.wav")
    sample_rate = 44100
    duration_sec = 3.0
    num_samples = int(sample_rate * duration_sec)

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        raw_frames = bytearray()
        for i in range(num_samples):
            val = int(0.4 * 32767.0 * math.sin(2.0 * math.pi * 300.0 * i / sample_rate))
            raw_frames.extend(struct.pack("<h", val))
        wf.writeframes(raw_frames)

    with open(wav_path, "rb") as af:
        response = client.post(
            "/api/audio/submit",
            data={"name": "Kavya Verma", "phone": "9000000222"},
            files={"audio_file": ("sample.wav", af, "audio/wav")}
        )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["submission"]["duration_seconds"] == pytest.approx(3.0, rel=0.1)
    print(f"[PASS] /api/audio/submit verified with extracted loudness: {res_data['submission']['loudness_dbfs']} dBFS")

if __name__ == "__main__":
    test_api_stats()
    test_duplicate_check_api()
