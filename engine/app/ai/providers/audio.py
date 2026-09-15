import io
import wave

from app.errors import AppError


def pcm_to_wav(data: bytes, rate=24000):
    if not data or len(data) % 2 or not 8000 <= rate <= 192000:
        raise AppError(502, "No valid speech audio was returned. Please retry.")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(data)
    return buffer.getvalue()
