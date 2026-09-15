"""Feature contracts. New providers implement only the capabilities they support."""

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.api.models import SourceLanguage

LANGUAGES = {"en": "English", "de": "German", "tr": "Turkish", "ar": "Arabic", "es": "Spanish"}


class Transcript(BaseModel):
    text: str = Field(max_length=2000)
    language: SourceLanguage


class Transcriber(Protocol):
    async def transcribe(self, audio: bytes, mime_type: str) -> Transcript: ...


class Translator(Protocol):
    async def translate(self, text: str, language: str) -> str: ...


class LanguageDetector(Protocol):
    async def detect(self, text: str) -> str: ...


class SpeechSynthesizer(Protocol):
    async def speak(self, text: str, language: str) -> bytes: ...


class NarrativeModel(Protocol):
    provider_name: str
    model_id: str

    async def generate(self, source: Any, instruction: str, schema: dict | None = None) -> dict: ...


@dataclass
class Providers:
    transcriber: Transcriber
    translator: Translator
    detector: LanguageDetector
    speech: SpeechSynthesizer
    narrative: NarrativeModel
