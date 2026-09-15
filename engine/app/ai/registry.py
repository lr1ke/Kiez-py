from app.ai.interfaces import Providers
from app.ai.providers.gemini import Gemini
from app.ai.providers.openai import OpenAI
from app.ai.providers.transport import Transport
from app.errors import AppError


class Unavailable:
    provider_name = "unavailable"
    model_id = "unavailable"

    async def _fail(self, *args, **kwargs):
        raise AppError(503, "This AI feature is not connected yet. You can still read and write.")

    transcribe = translate = detect = speak = generate = _fail


class SpeechFallback:
    def __init__(self, primary, fallback, enabled):
        self.primary, self.fallback, self.enabled = primary, fallback, enabled

    async def speak(self, text, language):
        try:
            return await self.primary.speak(text, language)
        except AppError as error:
            if error.status != 429 or not self.enabled:
                raise
            return await self.fallback.speak(text, language)


def capabilities(s):
    google, openai = bool(s.gemini_api_key), bool(s.openai_api_key)
    features = dict(
        transcribe=s.transcription_provider == "gemini" and google,
        translate=s.translation_provider == "gemini" and google,
        detect=s.detection_provider == "gemini" and google,
        speech=(s.tts_provider in ("auto", "gemini") and google) or (s.tts_provider == "openai" and openai),
        chronicle=s.chronicle_provider == "openai" and openai,
    )
    return {"available": features["transcribe"], "languages": s.languages, "features": features}


def build_providers(s, client, db=None):
    transport = Transport(client, db)
    gemini, openai, unavailable = Gemini(s, transport), OpenAI(s, transport), Unavailable()
    speech = {
        "gemini": gemini,
        "openai": openai,
        "auto": SpeechFallback(gemini, openai, bool(s.openai_api_key)),
    }.get(s.tts_provider, unavailable)
    return Providers(
        transcriber=gemini if s.transcription_provider == "gemini" else unavailable,
        translator=gemini if s.translation_provider == "gemini" else unavailable,
        detector=gemini if s.detection_provider == "gemini" else unavailable,
        speech=speech,
        narrative=openai if s.chronicle_provider == "openai" else unavailable,
    )
