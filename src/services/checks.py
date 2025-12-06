from typing import Dict, Any, List
from ..schemas import CheckResult

AVAILABLE_CHECKS = {}

def check_blacklist_words(text: str, params: Dict[str, Any]) -> CheckResult:
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
AVAILABLE_CHECKS["blacklist"] = check_blacklist_words


def check_links(text: str, params: Dict[str, Any]) -> CheckResult:
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
AVAILABLE_CHECKS["links"] = check_links


def check_phone_numbers(text: str, params: Dict[str, Any]) -> CheckResult:
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
AVAILABLE_CHECKS["phone"] = check_phone_numbers


def check_telegram_nick(text: str, params: Dict[str, Any]) -> CheckResult:
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
AVAILABLE_CHECKS["telegram_nick"] = check_telegram_nick