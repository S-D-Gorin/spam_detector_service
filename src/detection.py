from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

import httpx
from pydantic import TypeAdapter

from .schemas import (
    AsyncExampleDetectionDetails,
    AsyncExampleDetectorResult,
    AsyncExampleOptions,
    BlacklistDetectionDetails,
    BlacklistDetectorResult,
    DetectionRequest,
    DetectionResponse,
    DetectorName,
    DetectorResult,
    EmailAddressesDetectionDetails,
    EmailAddressesDetectorResult,
    EmojiDetectionDetails,
    EmojiDetectorResult,
    EmojiOptions,
    LinksDetectionDetails,
    LinksDetectorResult,
    MessageLengthDetectionDetails,
    MessageLengthDetectorResult,
    MessageLengthOptions,
    PhoneDetectionDetails,
    PhoneDetectorResult,
    TelegramNickDetectionDetails,
    TelegramNickDetectorResult,
)
from .services.lib.phone_check_service import PhoneService, country_phone_patterns

MAX_EXTRACTED_LINKS = 100
MAX_EXTRACTED_PHONES = 100
URL_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;:!?)]}"
TELEGRAM_NICK_PATTERN = re.compile(r"@[A-Za-z0-9_]{5,32}")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"
    "\U0001f300-\U0001f5ff"
    "\U0001f680-\U0001f6ff"
    "\U0001f1e0-\U0001f1ff"
    "]+"
)
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


def detect_telegram_nicks(text: str) -> TelegramNickDetectorResult:
    nicknames = TELEGRAM_NICK_PATTERN.findall(text)
    return TelegramNickDetectorResult(
        name="telegram_nick",
        detected=bool(nicknames),
        confidence=1.0,
        count=len(nicknames),
        details=TelegramNickDetectionDetails(nicknames=nicknames),
    )


def detect_message_length(
    text: str, min_length: int, max_length: int
) -> MessageLengthDetectorResult:
    length = len(text)
    outside_range = length < min_length or length > max_length
    return MessageLengthDetectorResult(
        name="message_length",
        detected=outside_range,
        confidence=1.0,
        count=length,
        details=MessageLengthDetectionDetails(
            length=length, min_length=min_length, max_length=max_length
        ),
    )


def detect_email_addresses(text: str) -> EmailAddressesDetectorResult:
    emails = EMAIL_PATTERN.findall(text)
    return EmailAddressesDetectorResult(
        name="email_addresses",
        detected=bool(emails),
        confidence=1.0,
        count=len(emails),
        details=EmailAddressesDetectionDetails(emails=emails),
    )


def detect_emojis(text: str, max_emoji: int) -> EmojiDetectorResult:
    emoji_groups = EMOJI_PATTERN.findall(text)
    emoji_count = sum(len(group) for group in emoji_groups)
    return EmojiDetectorResult(
        name="emoji_check",
        detected=bool(emoji_count),
        confidence=1.0,
        count=emoji_count,
        details=EmojiDetectionDetails(
            max_emoji=max_emoji, emoji_count=emoji_count, emojis=emoji_groups
        ),
    )


async def detect_async_example(
    text: str,
    url: str,
    api_key: str,
    timeout: float,
    fail_on_error: bool,
    payload: dict,
) -> AsyncExampleDetectorResult:
    request_payload = {**payload, "text": text}
    headers = {"Content-Type": "application/json", "User-Agent": "SpamDetector/2.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=request_payload, headers=headers)
        if response.status_code == 200:
            try:
                detected = bool(response.json().get("passed", True))
            except ValueError:
                detected = fail_on_error
                return AsyncExampleDetectorResult(
                    name="async_exemple",
                    detected=detected,
                    confidence=1.0,
                    count=int(detected),
                    details=AsyncExampleDetectionDetails(
                        url=url,
                        status_code=response.status_code,
                        error="Invalid JSON in response",
                    ),
                )
        else:
            detected = fail_on_error
        return AsyncExampleDetectorResult(
            name="async_exemple",
            detected=detected,
            confidence=1.0,
            count=int(detected),
            details=AsyncExampleDetectionDetails(
                url=url,
                status_code=response.status_code,
                error=None if response.status_code == 200 else f"HTTP {response.status_code}",
            ),
        )
    except httpx.RequestError as exc:
        detected = fail_on_error
        return AsyncExampleDetectorResult(
            name="async_exemple",
            detected=detected,
            confidence=1.0,
            count=int(detected),
            details=AsyncExampleDetectionDetails(url=url, error=str(exc)),
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
        signal_count=sum(
            int(result.detected) if result.name == "message_length" else result.count
            for result in ordered
        ),
        results=ordered,
    )


async def run_detection(request: DetectionRequest) -> DetectionResponse:
    results: list[DetectorResult] = []
    for name in request.detectors:
        if name == "blacklist":
            assert request.options.blacklist is not None
            results.append(detect_blacklist(request.text, request.options.blacklist.words))
        elif name == "links":
            results.append(detect_links(request.text))
        elif name == "phone":
            results.append(detect_phones(request.text))
        elif name == "telegram_nick":
            results.append(detect_telegram_nicks(request.text))
        elif name == "message_length":
            options = request.options.message_length or MessageLengthOptions()
            results.append(
                detect_message_length(
                    request.text,
                    options.min_length,
                    options.max_length,
                )
            )
        elif name == "email_addresses":
            results.append(detect_email_addresses(request.text))
        elif name == "emoji_check":
            options = request.options.emoji_check or EmojiOptions()
            results.append(detect_emojis(request.text, options.max_emoji))
        elif name == "async_exemple":
            options = request.options.async_exemple or AsyncExampleOptions()
            results.append(
                await detect_async_example(
                    request.text,
                    options.url,
                    options.api_key,
                    options.timeout,
                    options.fail_on_error,
                    options.payload,
                )
            )
    return build_detection_response(request.detectors, results)
