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


def test_one_detected_phone_contributes_one_signal():
    response = client.post(
        "/api/v2/check",
        json={
            "text": "+7 (000) 123-45-67",
            "detectors": ["phone"],
            "options": {"phone": {}},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_signals"] is True
    assert body["signal_count"] == 1
    assert body["results"][0]["count"] == 1


def test_phone_signal_count_is_one_for_two_detected_phones():
    response = client.post(
        "/api/v2/check",
        json={
            "text": "+7 (000) 123-45-67 +7 (111) 222-33-44",
            "detectors": ["phone"],
            "options": {"phone": {}},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_signals"] is True
    assert body["signal_count"] == 1
    assert body["results"][0]["count"] == 2


def test_message_length_and_phone_each_contribute_one_signal():
    response = client.post(
        "/api/v2/check",
        json={
            "text": "x" * 201 + " +7 (000) 123-45-67",
            "detectors": ["message_length", "phone"],
            "options": {
                "message_length": {"max_length": 200},
                "phone": {},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_signals"] is True
    assert body["signal_count"] == 2
    assert [result["detected"] for result in body["results"]] == [True, True]


def test_v2_exposes_all_local_legacy_detectors():
    response = client.post(
        "/api/v2/check",
        json={
            "text": "@support_user user@e.co 😀😀",
            "detectors": [
                "telegram_nick",
                "message_length",
                "email_addresses",
                "emoji_check",
            ],
            "options": {
                "message_length": {"min_length": 100, "max_length": 200},
                "emoji_check": {"max_emoji": 10},
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_signals"] is True
    assert body["signal_count"] == 4
    by_name = {result["name"]: result for result in body["results"]}
    assert by_name["telegram_nick"]["details"]["nicknames"] == ["@support_user"]
    assert by_name["message_length"]["count"] == 26
    assert by_name["message_length"]["details"]["length"] == 26
    assert by_name["email_addresses"]["details"]["emails"] == ["user@e.co"]
    assert by_name["emoji_check"]["details"]["emoji_count"] == 2


def test_message_length_returns_text_length_in_count():
    response = client.post(
        "/api/v2/check",
        json={
            "text": "Коротко",
            "detectors": ["message_length"],
            "options": {"message_length": {"min_length": 10, "max_length": 2000}},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_signals"] is True
    assert body["signal_count"] == 1
    assert body["results"][0]["count"] == 7
    assert body["results"][0]["details"] == {
        "length": 7,
        "min_length": 10,
        "max_length": 2000,
    }


def test_emoji_check_returns_each_grapheme_as_a_separate_entity():
    response = client.post(
        "/api/v2/check",
        json={
            "text": "🫤😐🫣🤔🤗😓😯🙄",
            "detectors": ["emoji_check"],
            "options": {"emoji_check": {"max_emoji": 5}},
        },
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["detected"] is True
    assert result["count"] == 8
    assert result["details"] == {
        "max_emoji": 5,
        "emoji_count": 8,
        "emojis": ["🫤", "😐", "🫣", "🤔", "🤗", "😓", "😯", "🙄"],
    }


def test_emoji_check_reports_six_entities_with_max_emoji_five():
    response = client.post(
        "/api/v2/check",
        json={
            "text": "😀😀😀😀😀😀",
            "detectors": ["emoji_check"],
            "options": {"emoji_check": {"max_emoji": 5}},
        },
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["detected"] is True
    assert result["count"] == 6
    assert result["details"]["emoji_count"] == 6


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
