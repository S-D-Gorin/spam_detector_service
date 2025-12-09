from typing import Dict, Any, List
from ..schemas import CheckResult
from .lib.phone_check_service import PhoneService
import httpx
import os
import logging

logger = logging.getLogger(__name__)

AVAILABLE_CHECKS = {}

def blacklist_words_check(text: str, params: Dict[str, Any]) -> CheckResult:
    words = params.get("words", ["free", "viagra", "casino"])
    text_lower = text.lower()
    hits = [w for w in words if w in text_lower]
    max_hits = params.get("max_hits", 3)
    score = min(len(hits) / max(max_hits, 1), 1.0)

    return CheckResult(
        name="blacklist",
        passed=len(hits) == 0,
        score=score,
        details={"hits": hits, "count": len(hits), "max_hits": max_hits},
    )
AVAILABLE_CHECKS["blacklist"] = blacklist_words_check


def links_сheck(text: str, params: Dict[str, Any]) -> CheckResult:
    import re

    urls = re.findall(r"https?://\S+", text)
    max_links = params.get("max_links", 3)
    score = min(len(urls) / max_links, 1.0)

    return CheckResult(
        name="links",
        # passed=len(urls) <= max_links,
        passed=len(urls) > 0,
        score=score,
        details={"links": urls, "count": len(urls), "max_links": max_links},
    )
AVAILABLE_CHECKS["links"] = links_сheck


def phone_numbers_check(text: str, params: Dict[str, Any]) -> CheckResult:
    phone_service = PhoneService(text, params)
    country = params.get('country', None)
    phones = phone_service.analyze()


    passed = len(phones) > 0
    score = 1.0 if phones else 0.0  # можно сделать гибче

    return CheckResult(
        name="phone",
        passed=passed,
        score=score,
        details={"phones": phones}
    )
AVAILABLE_CHECKS["phone"] = phone_numbers_check


def telegram_nick_check(text: str, params: Dict[str, Any]) -> CheckResult:
    import re

    # Telegram официальный формат имен:
    # длина никнейма: 5–32 символов; допустимы буквы, цифры и _
    pattern = r"@[A-Za-z0-9_]{5,32}"

    matches = re.findall(pattern, text)

    passed = len(matches) > 0
    score = 1.0 if matches else 0.0

    return CheckResult(
        name="telegram_nick",
        passed=passed,
        score=score,
        details={"nicknames": matches}
    )
AVAILABLE_CHECKS["telegram_nick"] = telegram_nick_check


def length_check(text: str, params: Dict[str, Any]) -> CheckResult:
    min_length = params.get("min_length", 10)
    max_length = params.get("max_length", 2000)

    length = len(text)

    # Проверяем выход за границы
    if length < min_length:
        passed = False
        # слишком короткое сообщение — считаем высоким риском
        score = (min_length - length) / min_length
        score = min(score, 1.0)
    elif length > max_length:
        passed = False
        score = (length - max_length) / max_length
        score = min(score, 1.0)
    else:
        passed = True
        score = 0.0

    return CheckResult(
        name="message_length",
        passed=passed,
        score=score,
        details={
            "length": length,
            "min_length": min_length,
            "max_length": max_length
        }
    )

AVAILABLE_CHECKS["message_length"] = length_check


def check_email_addresses(text: str, params: Dict[str, Any]) -> CheckResult:
    import re

    # Простая и рабочая регулярка для email
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    emails = re.findall(pattern, text)

    passed = len(emails) > 0
    score = 1.0 if emails else 0.0

    return CheckResult(
        name="email_addresses",
        passed=passed,
        score=score,
        details={"emails": emails}
    )
AVAILABLE_CHECKS["email_addresses"] = check_email_addresses


def emoji_check(text: str, params: Dict[str, Any]) -> CheckResult:
    import re

    max_emoji = params.get("max_emoji", 10)

    # Простая регулярка для поиска эмодзи
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "]+",
        flags=re.UNICODE,
    )

    emojis = emoji_pattern.findall(text)
    all_emojis = []
    for e in emojis:
        all_emojis.extend(list(e))
            

    passed = len(all_emojis) > max_emoji
    score = 1.0 if passed else 0.0

    emoji_real_count= lambda em_list: sum(len(em) for em in em_list)
    score = min(emoji_real_count(emojis) / max_emoji, 1.0)

    details = {
        "max_emoji": max_emoji,
        "emoji_count": emoji_real_count(emojis),
        "emojis": emojis
        }

    return CheckResult(
        name="emoji_check",
        passed=passed,
        score=score,
        details=details
    )
AVAILABLE_CHECKS["emoji_check"] = emoji_check


# Пример асинхронной проверки, которая обращается к внешнему сервису
async def async_external_service_exemple_check(text: str, params: Dict[str, Any]) -> CheckResult:
    """
    Асинхронная проверка через внешний сервис.

    Поддерживает параметры:
    - url: URL API
    - api_key: ключ авторизации
    - timeout: таймаут в секундах
    - fail_on_error: считать ли ошибку спамом (по умолчанию False)
    - payload: дополнительный payload ( dict )
    """

    # Параметры + env
    url = params.get("url") or os.getenv("ASYNC_EXAMPLE_URL", "https://example.com/api")
    api_key = params.get("api_key") or os.getenv("ASYNC_EXAMPLE_API_KEY", "")
    fail_on_error = bool(params.get("fail_on_error", False))

    # Конвертация timeout
    try:
        timeout_str = os.getenv("ASYNC_EXAMPLE_TIMEOUT")
        if timeout_str:
            timeout = float(timeout_str)
        else:
            timeout = float(params.get("timeout", 2.0))
    except (ValueError, TypeError):
        logger.warning("Invalid timeout value, using default 2.0")
        timeout = 2.0

    # Подготавливаем payload (без мутации исходного словаря)
    raw_payload = params.get("payload") or {}
    payload: Dict[str, Any] = dict(raw_payload)
    payload["text"] = text

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SpamDetector/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code == 200:
            # Пытаемся разобрать JSON
            try:
                data = resp.json()
            except ValueError as exc:
                details = {
                    "url": url,
                    "error": f"Invalid JSON in response: {exc}",
                    "status_code": resp.status_code,
                    "request": payload,
                    "response": resp.text[:200] if resp.text else "",
                }
                return CheckResult(
                    name="async_example",
                    passed=not fail_on_error,
                    score=0.0,
                    details=details,
                )

            # Предполагаемый формат ответа
            passed = bool(data.get("passed", True))
            score = float(data.get("score", 0.0))

            details = {
                "url": url,
                "status_code": resp.status_code,
                "request": payload,
                "response": resp.text[:200] if resp.text else "",
            }

            return CheckResult(
                name="async_example",
                passed=passed,
                score=score,
                details=details,
            )

        else:
            # HTTP-ошибки
            details = {
                "url": url,
                "error": f"HTTP {resp.status_code}",
                "status_code": resp.status_code,
                "request": payload,
                "response": resp.text[:200] if resp.text else "",
            }

            return CheckResult(
                name="async_example",
                passed=not fail_on_error,
                score  = 0.0,
                details=details,
            )

    except httpx.RequestError as exc:
        # Сетевые ошибки
        error_details: Dict[str, Any] = {
            "url": url,
            "request": payload,
            "error": str(exc),
        }
        error_details["timeout"] = timeout

        if isinstance(exc, httpx.ConnectTimeout):
            error_details["type"] = "connection_timeout"
        elif isinstance(exc, httpx.ReadTimeout):
            error_details["type"] = "read_timeout"
        elif isinstance(exc, httpx.ConnectError):
            error_details["type"] = "connection_error"

        return CheckResult(
            name="async_example",
            passed=not fail_on_error,
            score=0.0,
            details=error_details,
        )

    except Exception as exc:
        # Любые другие ошибки
        details = {
            "url": url,
            "request": payload,
            "timeout": timeout,
            "error": f"Unexpected error: {exc}",
        }
        return CheckResult(
            name="async_example",
            passed=not fail_on_error,
            score=0.0,
            details=details,
        )
    
AVAILABLE_CHECKS["async_exemple"] = async_external_service_exemple_check
