import io
import time
import wave
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.ai.providers.audio import pcm_to_wav
from app.api.models import LocationInput
from app.dates import diary_date
from app.db.seed import fixtures
from app.errors import AppError
from app.neighborhoods.service import GeoJSONResolver
from app.security.service import sign, verify


@pytest.mark.parametrize(
    ("moment", "day"),
    [
        ("2026-01-01T22:59:59+00:00", "2026-01-01"),
        ("2026-01-01T23:00:00+00:00", "2026-01-02"),
        ("2026-06-01T21:59:59+00:00", "2026-06-01"),
        ("2026-06-01T22:00:00+00:00", "2026-06-02"),
        ("2026-03-29T00:59:59+00:00", "2026-03-29"),
        ("2026-03-29T01:00:00+00:00", "2026-03-29"),
        ("2026-10-25T00:59:59+00:00", "2026-10-25"),
        ("2026-10-25T01:00:00+00:00", "2026-10-25"),
    ],
)
def test_berlin_calendar(moment, day):
    assert diary_date(datetime.fromisoformat(moment)) == day


def test_fixtures_have_original_content_and_stable_day_counts():
    groups = fixtures("2026-01-12")
    entries = [e for g in groups for e in g["entries"]]
    assert len(entries) == 160
    assert len([g for g in groups if g["chronicle"]]) == 16
    assert len({e["neighborhood_id"] for e in entries}) == 4
    assert {e["language"] for e in entries} == {"en", "de", "tr", "ar", "es"}
    assert all(diary_date(e["created_at"]) == e["diary_date"] for e in entries)
    assert fixtures("2026-01-12") == groups


def test_signed_tokens_reject_tampering_and_expiry(settings):
    data = {"sid": "session", "exp": time.time() * 1000 + 1000}
    token = sign(settings, data)
    assert verify(settings, token) == data
    assert verify(settings, token + "x") is None
    assert verify(settings, token + ".extra") is None
    assert verify(settings, sign(settings, {"exp": 0})) is None


@pytest.mark.parametrize("accuracy", [0, -1, 50001, float("nan"), float("inf"), True, "10"])
def test_invalid_location_input(accuracy):
    with pytest.raises(ValidationError):
        LocationInput(latitude=52.49, longitude=13.415, accuracy=accuracy)


def test_wav_playable():
    audio = pcm_to_wav(bytes([1, 2, 3, 4]))
    with wave.open(io.BytesIO(audio)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 24000)
        assert wav.readframes(2) == bytes([1, 2, 3, 4])
    with pytest.raises(AppError):
        pcm_to_wav(b"odd")


@pytest.mark.parametrize(
    ("lat", "lng", "accuracy", "expected"),
    [
        (52.4917, 13.415, 10, "graefekiez"),
        (52.4878, 13.4325, 10, "reuterkiez"),
        (52.4887, 13.392, 10, "bergmannkiez"),
        (52.4752, 13.419, 10, "schillerkiez"),
        (53.54057, 9.99437, 10, None),
        (52.4917, 13.415, 300, None),
        (52.48701, 13.410, 50, None),
    ],
)
async def test_location_catalog_parity(db, lat, lng, accuracy, expected):
    resolver = GeoJSONResolver()
    if expected:
        assert (await resolver.resolve(db, lat, lng, accuracy))["id"] == expected
    else:
        with pytest.raises(AppError) as error:
            await resolver.resolve(db, lat, lng, accuracy)
        assert error.value.status == 422
