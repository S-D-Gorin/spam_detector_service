from typing import Dict, Any, List
from ..schemas import CheckResult

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
    import re

    # Ищем номера в формате +7XXXXXXXXXX
    pattern = r"\+7\d{10}"
    phones = re.findall(pattern, text)

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