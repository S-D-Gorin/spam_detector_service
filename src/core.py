from typing import List
from .schemas import SpamRequest, SpamResponse, CheckResult
from .services.checks import AVAILABLE_CHECKS
import logging

class SpamDetector:
    def __init__(self):
        # сюда можно передать конфиги, ресурсы и т.п.
        pass

    def run(self, req: SpamRequest) -> SpamResponse:
        results: List[CheckResult] = []

        for check_name in req.checks:
            check_func = AVAILABLE_CHECKS.get(check_name)
            if not check_func:
                logging.warning(f"Unknown check: {check_name}")
                continue
            
            # параметры для проверки (если есть)
            params = {}
            if req.options and check_name in req.options:
                params = req.options[check_name].params

            result = check_func(
                text=req.text,
                recipients=req.recipients,
                params=params,
            )
            results.append(result)

        # агрегируем результат
        if results:
            avg_score = sum(r.score for r in results) / len(results)
        else:
            avg_score = 0.0

        is_spam = any(not r.passed for r in results)

        return SpamResponse(
            is_spam=is_spam,
            score=avg_score,
            results=results,
        )
