from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from pydantic import TypeAdapter

from .schemas import (
    BlacklistDetectionDetails,
    BlacklistDetectorResult,
    DetectionRequest,
    DetectionResponse,
    DetectorName,
    DetectorResult,
    LinksDetectionDetails,
    LinksDetectorResult,
    PhoneDetectionDetails,
    PhoneDetectorResult,
)
from .services.lib.phone_check_service import PhoneService, country_phone_patterns

MAX_EXTRACTED_LINKS = 100
MAX_EXTRACTED_PHONES = 100
URL_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;:!?)]}"
RESULT_ADAPTER = TypeAdapter(DetectorResult)


class DetectionLimitError(ValueError):
    pass


def _unique_in_order(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def detect_blacklist(text: str, words: Sequence[str]) -> BlacklistDetectorResult:
    normalized_text = unicodedata.normalize("NFKC", text).casefold()
    normalized_words = _unique_in_order(
        [unicodedata.normalize("NFKC", word).casefold() for word in words]
    )
    hits = [word for word in normalized_words if word in normalized_text]
    occurrences = sum(normalized_text.count(word) for word in hits)
    return BlacklistDetectorResult(
        name="blacklist",
        detected=bool(hits),
        confidence=1.0,
        count=len(hits),
        details=BlacklistDetectionDetails(hits=hits, occurrences_count=occurrences),
    )


def detect_links(text: str) -> LinksDetectorResult:
    links = _unique_in_order(
        [match.rstrip(TRAILING_URL_PUNCTUATION) for match in URL_PATTERN.findall(text)]
    )
    if len(links) > MAX_EXTRACTED_LINKS:
        raise DetectionLimitError(
            f"links detector found more than {MAX_EXTRACTED_LINKS} unique links"
        )
    return LinksDetectorResult(
        name="links",
        detected=bool(links),
        confidence=1.0,
        count=len(links),
        details=LinksDetectionDetails(links=links),
    )


def detect_phones(text: str) -> PhoneDetectorResult:
    raw_matches: list[tuple[int, str]] = []
    for pattern in country_phone_patterns.values():
        raw_matches.extend((match.start(), match.group(0)) for match in pattern.finditer(text))
    raw_matches.sort(key=lambda item: item[0])
    normalized = [PhoneService.normalize_phone(raw) for _, raw in raw_matches]
    phones = _unique_in_order([phone for phone in normalized if phone is not None])
    if len(phones) > MAX_EXTRACTED_PHONES:
        raise DetectionLimitError(
            f"phone detector found more than {MAX_EXTRACTED_PHONES} unique phones"
        )
    return PhoneDetectorResult(
        name="phone",
        detected=bool(phones),
        confidence=1.0,
        count=len(phones),
        details=PhoneDetectionDetails(phones=phones),
    )


def build_detection_response(
    requested_detectors: Sequence[DetectorName],
    results: Sequence[DetectorResult],
) -> DetectionResponse:
    if len(requested_detectors) != len(set(requested_detectors)):
        raise ValueError("requested detector names must be unique")
    validated = [RESULT_ADAPTER.validate_python(result) for result in results]
    by_name = {}
    for result in validated:
        if result.name in by_name:
            raise ValueError(f"duplicate result for detector: {result.name}")
        by_name[result.name] = result
    requested = set(requested_detectors)
    missing = requested.difference(by_name)
    unknown = set(by_name).difference(requested)
    if missing:
        raise ValueError(f"missing results for detectors: {sorted(missing)}")
    if unknown:
        raise ValueError(f"results returned for unrequested detectors: {sorted(unknown)}")
    ordered = [by_name[name] for name in requested_detectors]
    return DetectionResponse(
        has_signals=any(result.detected for result in ordered),
        signal_count=sum(result.count for result in ordered),
        results=ordered,
    )


def run_detection(request: DetectionRequest) -> DetectionResponse:
    results: list[DetectorResult] = []
    for name in request.detectors:
        if name == "blacklist":
            assert request.options.blacklist is not None
            results.append(detect_blacklist(request.text, request.options.blacklist.words))
        elif name == "links":
            results.append(detect_links(request.text))
        elif name == "phone":
            results.append(detect_phones(request.text))
    return build_detection_response(request.detectors, results)
