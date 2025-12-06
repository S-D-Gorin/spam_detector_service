from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class CheckParams(BaseModel):
    # общие параметры проверки
    # например: sensitivity: float = 0.5
    params: Dict[str, Any] = {}


class SpamRequest(BaseModel):
    text: str
    recipients: List[str]
    checks: List[str]  # ["blacklist", "links", "caps"]
    options: Optional[Dict[str, CheckParams]] = None


class CheckResult(BaseModel):
    name: str
    passed: bool
    score: float
    details: Dict[str, Any] = {}


class SpamResponse(BaseModel):
    is_spam: bool
    score: float
    results: List[CheckResult]
