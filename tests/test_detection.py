import pytest
from pydantic import ValidationError

from src.detection import (
    build_detection_response,
    detect_blacklist,
    detect_emojis,
    detect_links,
    detect_message_length,
    detect_phones,
)
from src.schemas import (
    BlacklistDetectionDetails,
    BlacklistDetectorResult,
    DetectionRequest,
    LinksDetectionDetails,
    LinksDetectorResult,
)


def test_blacklist_no_hits():
    result = detect_blacklist("ordinary message", ["token"])
    assert not result.detected
    assert result.count == 0
    assert result.details.hits == []
    assert result.details.occurrences_count == 0


def test_blacklist_unique_normalized_hits_and_occurrences():
    result = detect_blacklist("TOKEN token and casino", ["token", "TOKEN", "casino"])
    assert result.detected
    assert result.count == 2
    assert result.details.hits == ["token", "casino"]
    assert result.details.occurrences_count == 3


def test_links_extract_and_deduplicate_in_text_order():
    result = detect_links(
        "https://example.invalid/a https://other.invalid https://example.invalid/a"
    )
    assert result.detected
    assert result.count == 2
    assert result.details.links == [
        "https://example.invalid/a",
        "https://other.invalid",
    ]


def test_links_absent():
    result = detect_links("ordinary message")
    assert not result.detected
    assert result.count == 0


def test_phone_extracts_normalizes_and_deduplicates():
    result = detect_phones("Call +7 (000) 123-45-67 or 8 000 123 45 67")
    assert result.detected
    assert result.count == 1
    assert result.details.phones == ["+70001234567"]


def test_phone_does_not_treat_ordinary_number_as_phone():
    result = detect_phones("Order 123456 and room 2026")
    assert not result.detected
    assert result.count == 0


def test_message_length_uses_count_for_text_length_not_signal_count():
    result = detect_message_length("ordinary message", min_length=10, max_length=2000)

    assert not result.detected
    assert result.count == len("ordinary message")


@pytest.mark.parametrize(
    ("text", "expected_emojis"),
    [
        ("🫤😐🫣🤔🤗😓😯🙄", ["🫤", "😐", "🫣", "🤔", "🤗", "😓", "😯", "🙄"]),
        ("😀😃", ["😀", "😃"]),
        ("✈️", ["✈️"]),
        ("👍🏽", ["👍🏽"]),
        ("👩‍💻", ["👩‍💻"]),
        ("🇷🇺", ["🇷🇺"]),
        ("1️⃣", ["1️⃣"]),
        ("ordinary 😀 text 👩‍💻", ["😀", "👩‍💻"]),
    ],
)
def test_emoji_detector_returns_one_entity_per_emoji_grapheme(text, expected_emojis):
    result = detect_emojis(text, max_emoji=5)

    assert result.detected
    assert result.count == len(expected_emojis)
    assert result.details.emoji_count == len(expected_emojis)
    assert result.details.emojis == expected_emojis


def test_emoji_detector_keeps_raw_detection_independent_of_max_emoji():
    result = detect_emojis("😀" * 5, max_emoji=5)

    assert result.detected
    assert result.count == 5


def _blacklist_result(detected=False, count=0):
    return BlacklistDetectorResult(
        name="blacklist",
        detected=detected,
        confidence=1.0,
        count=count,
        details=BlacklistDetectionDetails(hits=["x"] if count else [], occurrences_count=count),
    )


def _links_result(detected=False, count=0):
    return LinksDetectorResult(
        name="links",
        detected=detected,
        confidence=1.0,
        count=count,
        details=LinksDetectionDetails(links=["https://example.invalid"] if count else []),
    )


def test_builder_aggregates_and_preserves_requested_order():
    response = build_detection_response(
        ["links", "blacklist"], [_blacklist_result(True, 1), _links_result()]
    )
    assert response.has_signals
    assert response.signal_count == 1
    assert [result.name for result in response.results] == ["links", "blacklist"]


def test_builder_all_zero_results_have_no_signals():
    response = build_detection_response(["blacklist"], [_blacklist_result()])
    assert not response.has_signals
    assert response.signal_count == 0


@pytest.mark.parametrize(
    ("requested", "results"),
    [
        (["blacklist"], [_blacklist_result(), _blacklist_result()]),
        (["blacklist", "links"], [_blacklist_result()]),
        (["blacklist"], [_blacklist_result(), _links_result()]),
    ],
)
def test_builder_rejects_duplicate_missing_and_unknown_results(requested, results):
    with pytest.raises(ValueError):
        build_detection_response(requested, results)


@pytest.mark.parametrize(("detected", "count"), [(False, 1), (True, 0)])
def test_result_rejects_detected_count_mismatch(detected, count):
    with pytest.raises(ValidationError):
        BlacklistDetectorResult(
            name="blacklist",
            detected=detected,
            confidence=1.0,
            count=count,
            details=BlacklistDetectionDetails(hits=[], occurrences_count=0),
        )


def test_request_rejects_duplicate_detectors_and_string_bool_like_unknown_data():
    with pytest.raises(ValidationError):
        DetectionRequest.model_validate(
            {"text": "x", "detectors": ["links", "links"], "options": {"links": {}}}
        )


def test_request_rejects_legacy_max_links_option():
    with pytest.raises(ValidationError):
        DetectionRequest.model_validate(
            {
                "text": "x",
                "detectors": ["links"],
                "options": {"links": {"max_links": 1}},
            }
        )
