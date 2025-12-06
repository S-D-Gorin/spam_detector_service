import asyncio
from typing import List
from fastapi.concurrency import run_in_threadpool

from .schemas import SpamRequest, SpamResponse, CheckResult
from .services.checks import AVAILABLE_CHECKS


class SpamDetector:
    def __init__(self):
        pass

    async def run(self, req: SpamRequest) -> SpamResponse:
        tasks = []

        for check_name in req.checks:
            check_func = AVAILABLE_CHECKS.get(check_name)
            if not check_func:
                continue

            params = {}
            if req.options and check_name in req.options:
                params = req.options[check_name].params

            # если функция асинхронная — ждём её напрямую
            if asyncio.iscoroutinefunction(check_func):
                tasks.append(
                    check_func(
                        text=req.text,
                        params=params,
                    )
                )
            else:
                # синхронные проверки гоняем в threadpool, чтобы не блокировали event loop
                tasks.append(
                    run_in_threadpool(
                        check_func,
                        req.text,
                        params,
                    )
                )

        results: List[CheckResult] = await asyncio.gather(*tasks)

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
