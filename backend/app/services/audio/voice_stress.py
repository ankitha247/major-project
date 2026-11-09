"""
Voice stress analyzer using librosa.
Takes a base64 encoded PCM audio chunk from the browser
and returns pitch, speaking rate, and stress score.
"""

import base64
import logging
import io
import numpy as np

logger = logging.getLogger(__name__)


def analyze_voice_chunk(chunk_b64: str, sample_rate: int = 16000) -> dict:
    """
    Analyzes a raw PCM audio chunk for vocal stress indicators.

    chunk_b64: base64 encoded raw PCM float32 audio
    sample_rate: audio sample rate in Hz (default 16000)

    Returns dict with keys:
        stress_score: float (0.0 to 1.0)
        pitch_mean: float (Hz)
        pitch_variance: float
        speaking_rate: float (syllables per second estimate)
        energy: float
    """
    try:
        import librosa

        # Decode base64 to bytes
        audio_bytes = base64.b64decode(chunk_b64)

        # Convert bytes to float32 numpy array
        audio_array = np.frombuffer(audio_bytes, dtype=np.float32)

        if len(audio_array) == 0:
            logger.warning("Empty audio chunk received")
            return _default_voice_result()

        # Normalize audio
        max_val = np.max(np.abs(audio_array))
        if max_val > 0:
            audio_array = audio_array / max_val

        # Extract pitch (fundamental frequency) using librosa
        pitches, magnitudes = librosa.piptrack(
            y=audio_array,
            sr=sample_rate,
            threshold=0.1,
        )

        # Get pitch values where magnitude is significant
        pitch_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 50:  # Filter out very low frequencies (noise)
                pitch_values.append(pitch)

        if pitch_values:
            pitch_mean = float(np.mean(pitch_values))
            pitch_variance = float(np.var(pitch_values))
        else:
            pitch_mean = 0.0
            pitch_variance = 0.0

        # Energy — RMS energy of the audio signal
        rms = librosa.feature.rms(y=audio_array)[0]
        energy = float(np.mean(rms))

        # Speaking rate estimate using zero crossing rate
        # Higher ZCR generally indicates more speech activity
        zcr = librosa.feature.zero_crossing_rate(audio_array)[0]
        speaking_rate = float(np.mean(zcr) * sample_rate / 100)
        speaking_rate = round(min(speaking_rate, 10.0), 3)

        # Stress score calculation
        # High pitch variance + high energy + abnormal pitch = stress
        stress_score = _calculate_stress_score(
            pitch_mean=pitch_mean,
            pitch_variance=pitch_variance,
            energy=energy,
        )

        return {
            "stress_score": round(stress_score, 4),
            "pitch_mean": round(pitch_mean, 2),
            "pitch_variance": round(pitch_variance, 2),
            "speaking_rate": round(speaking_rate, 3),
            "energy": round(energy, 4),
        }

    except Exception as exc:
        logger.warning("Voice stress analysis failed: %s", exc)
        return _default_voice_result()


def _calculate_stress_score(
    pitch_mean: float,
    pitch_variance: float,
    energy: float,
) -> float:
    """
    Calculates a stress score from vocal features.

    High stress indicators:
    - Very high or very low pitch mean (outside normal range 85-255 Hz)
    - High pitch variance (unstable voice)
    - Very high energy (shouting/tension) or very low (whispering/fear)
    """
    score = 0.0

    # Pitch mean outside normal conversational range
    if pitch_mean > 0:
        if pitch_mean > 300 or pitch_mean < 80:
            score += 0.3
        elif pitch_mean > 250 or pitch_mean < 100:
            score += 0.15

    # High pitch variance means unstable/trembling voice
    if pitch_variance > 5000:
        score += 0.4
    elif pitch_variance > 2000:
        score += 0.2
    elif pitch_variance > 1000:
        score += 0.1

    # Energy component
    if energy > 0.3:
        score += 0.2
    elif energy < 0.01 and pitch_mean > 0:
        score += 0.1

    return min(score, 1.0)


def _default_voice_result() -> dict:
    """Returns safe defaults when analysis fails."""
    return {
        "stress_score": 0.0,
        "pitch_mean": 0.0,
        "pitch_variance": 0.0,
        "speaking_rate": 0.0,
        "energy": 0.0,
    }