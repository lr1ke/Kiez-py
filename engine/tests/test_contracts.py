import httpx

from app.main import create_app


def test_openapi_exposes_public_request_and_response_models(settings):
    document = create_app(settings).openapi()
    assert document["paths"]["/api/contributions"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/ContributionInput")
    response = document["paths"]["/api/neighborhoods"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response["items"]["$ref"].endswith("/Summary")
    assert document["paths"]["/api/transcribe"]["post"]["responses"]["202"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/AcceptedJob")
    public = document["components"]["schemas"]["Contribution"]["properties"]
    assert not {"session_id", "idempotency_key", "visibility"} & public.keys()


async def test_health_does_not_require_database_or_providers(settings):
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/healthz")).json() == {"ok": True}
