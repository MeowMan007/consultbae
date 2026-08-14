import os
import wave
import struct
import math
import pytest
from audio_app.audio_processor import extract_audio_features


@pytest.fixture
def sample_wav_file(tmp_path):
    """Generates a synthetic 2-second 44.1kHz sine wave WAV file for testing."""
    wav_path = os.path.join(tmp_path, "test_tone.wav")
    sample_rate = 44100
    duration_sec = 2.0
    freq = 440.0  # A4 tone
    num_samples = int(sample_rate * duration_sec)

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)

        # Generate sine wave with amplitude ~ 0.5 (-6 dBFS)
        raw_frames = bytearray()
        for i in range(num_samples):
            val = int(0.5 * 32767.0 * math.sin(2.0 * math.pi * freq * i / sample_rate))
            raw_frames.extend(struct.pack("<h", val))
        wf.writeframes(raw_frames)

    return wav_path


def test_audio_feature_extraction(sample_wav_file):
    features = extract_audio_features(sample_wav_file)

    assert features["duration_seconds"] == pytest.approx(2.0, rel=0.1)
    assert features["sample_rate_khz"] == pytest.approx(44.1, rel=0.1)
    assert features["bitrate_kbps"] > 0
    assert -15.0 < features["loudness_dbfs"] < -3.0
    assert features["snr_db"] >= 0
    assert features["quality_grade"] in [
        "Excellent (Studio/Clean)",
        "Good (Acceptable Voice)",
        "Fair (Low Volume / Slight Noise)",
        "Poor (Muffled / Heavy Noise)",
    ]
