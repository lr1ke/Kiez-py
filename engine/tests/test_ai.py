import json

import httpx
import pytest

from app.ai.interfaces import Providers, Transcript
from app.ai.providers.gemini import Gemini
from app.ai.providers.openai import OpenAI
from app.ai.providers.transport import Transport
from app.ai.registry import SpeechFallback, capabilities
from app.ai.workflows.chronicle import create_chronicle
from app.errors import AppError


class FakeProvider:
    provider_name = "fake"
    model_id = "test-model"

    def __init__(self):
        self.calls = []
        self.grounded = True
        self.cover = True
        self.before_review = None

    async def generate(self, source, instruction, schema=None):
        self.calls.append(instruction)
        if instruction.startswith("Extract"):
            return {"moments": [{"id": s["id"], "text": s["text"]} for s in source]}
        if instruction.startswith("Write"):
            return {
                "title": "Rain and quiet",
                "body": "I held the rain and the bicycle bells in my streets.",
                "coverage": {s["id"]: s["text"] for s in source["source"]} if self.cover else {},
            }
        if self.before_review:
            await self.before_review()
        return dict(
            grounded=self.grounded,
            allSourcesRepresented=True,
            firstPersonNeighborhood=True,
            conflictingMoodsPreserved=True,
        )

    async def transcribe(self, audio, mime_type):
        return Transcript(text="Ein leiser Regentag.", language="de")

    async def translate(self, text, language):
        return "Ein leiser Regentag."

    async def detect(self, text):
        return "de"

    async def speak(self, text, language):
        from app.ai.providers.audio import pcm_to_wav

        return pcm_to_wav(b"\0\0" * 100)

    def providers(self):
        return Providers(self, self, self, self, self)


async def test_chronicle_coverage_and_review():
    fake = FakeProvider()
    entries = [
        {"id": "one", "body": "rain", "language": "en"},
        {"id": "two", "body": "Lärm", "language": "de"},
    ]
    draft = await create_chronicle(entries, fake)
    assert set(draft.coverage) == {"one", "two"}
    assert len(fake.calls) == 3
    fake.cover = False
    with pytest.raises(AppError, match="Coverage"):
        await create_chronicle(entries, fake)
    fake.cover, fake.grounded = True, False
    with pytest.raises(AppError, match="Narrative review"):
        await create_chronicle(entries, fake)
    with pytest.raises(AppError, match="input budget"):
        await create_chronicle([{"id": "huge", "body": "a" * 500001, "language": "en"}], fake)


async def test_openai_transport_contract(settings):
    settings.openai_api_key = "fake-key"
    requests = []

    def handler(request):
        value = json.loads(request.content)
        requests.append(value)
        if request.url.path.endswith("/speech"):
            assert value["response_format"] == "pcm"
            return httpx.Response(200, content=b"\0\0" * 20)
        assert value["store"] is False
        assert value["model"] == settings.openai_chronicle_model
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"ok":true}'}]}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAI(settings, Transport(client))
        assert await provider.generate({}, "Return JSON") == {"ok": True}
        assert requests[0]["text"]["format"]["type"] == "json_object"
        await provider.generate({}, "Return JSON", {"type": "object"})
        assert requests[1]["text"]["format"]["strict"] is True
        assert (await provider.speak("Hello", "en")).startswith(b"RIFF")


@pytest.mark.parametrize("status", [429, 500, 401])
async def test_provider_errors_are_safe_and_classified(settings, status):
    settings.openai_api_key = "fake-key"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, text="secret provider data"))
    ) as client:
        with pytest.raises(AppError) as error:
            await OpenAI(settings, Transport(client)).generate({}, "Return JSON")
        assert error.value.retryable == (status in (429, 500))
        assert "secret provider data" not in error.value.message


async def test_gemini_transcript_and_silence(settings):
    settings.gemini_api_key = "fake-key"
    value = {"text": "مرحبا", "language": "ar"}

    def handler(request):
        data = json.loads(request.content)
        assert data["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "audio/webm"
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(value)}]}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Gemini(settings, Transport(client))
        assert (await provider.transcribe(b"fake", "audio/webm")).language == "ar"
        value["text"] = ""
        with pytest.raises(AppError, match="No clear speech"):
            await provider.transcribe(b"fake", "audio/webm")


async def test_fallback_only_on_quota():
    class Primary:
        status = 429

        async def speak(self, *args):
            raise AppError(self.status, "Provider error")

    primary, fallback = Primary(), FakeProvider()
    adapter = SpeechFallback(primary, fallback, True)
    assert (await adapter.speak("Hi", "en")).startswith(b"RIFF")
    primary.status = 502
    with pytest.raises(AppError):
        await adapter.speak("Hi", "en")


def test_features_are_independently_configurable(settings):
    settings.openai_api_key = "fake"
    settings.tts_provider = "openai"
    c = capabilities(settings)
    assert c["features"]["speech"] and c["features"]["chronicle"]
    assert not c["features"]["translate"] and not c["available"]
