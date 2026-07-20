from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def _request(text):
    return {
        "text": text,
        "detectors": ["blacklist", "links", "phone"],
        "options": {
            "blacklist": {"words": ["sprotect_demo_token"]},
            "links": {},
            "phone": {},
        },
    }


def test_no_signals_and_no_moderation_fields():
    response = client.post("/api/v2/check", json=_request("ordinary message"))
    assert response.status_code == 200
    body = response.json()
    assert body["has_signals"] is False
    assert body["signal_count"] == 0
    assert all(result["detected"] is False for result in body["results"])
    assert "is_spam" not in body
    assert all("passed" not in result for result in body["results"])


def test_each_detector_reports_signals_without_policy_decision():
    text = "sprotect_demo_token https://example.invalid/test +7 (000) 123-45-67"
    response = client.post("/api/v2/check", json=_request(text))
    assert response.status_code == 200
    body = response.json()
    by_name = {result["name"]: result for result in body["results"]}
    assert body["has_signals"] is True
    assert body["signal_count"] == 3
    assert by_name["blacklist"]["count"] == 1
    assert by_name["links"]["count"] == 1
    assert by_name["phone"]["count"] == 1
    assert "is_spam" not in body


def test_absence_of_phone_is_only_an_absent_detection():
    response = client.post(
        "/api/v2/check",
        json={
            "text": "phone is required elsewhere",
            "detectors": ["phone"],
            "options": {"phone": {}},
        },
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["detected"] is False
    assert response.json()["results"][0]["count"] == 0


def test_legacy_policy_option_is_validation_error():
    response = client.post(
        "/api/v2/check",
        json={"text": "x", "detectors": ["links"], "options": {"links": {"max_links": 1}}},
    )
    assert response.status_code == 422


def test_openapi_contains_v2_schemas_and_deprecated_v1():
    document = client.get("/openapi.json").json()
    assert document["info"]["version"] == "0.2.0"
    assert "/api/v2/check" in document["paths"]
    assert document["paths"]["/api/check"]["post"]["deprecated"] is True
    assert "DetectionRequest" in document["components"]["schemas"]
