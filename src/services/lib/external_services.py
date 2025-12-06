import os
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from ...schemas import CheckResult


import httpx

logger = logging.getLogger(__name__)


@dataclass
class ExternalServiceConfig:
    """
    Базовая конфигурация для внешнего асинхронного чекера.
    Значения по умолчанию берутся из env, если есть.
    """
    name: str = "async_example"

    url: str = field(
        default_factory=lambda: os.getenv(
            "ASYNC_EXAMPLE_URL",
            "https://example.com/api",
        )
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("ASYNC_EXAMPLE_API_KEY", "")
    )

    # таймаут по умолчанию; может быть перекрыт env или params
    timeout: float = field(
        default_factory=lambda: float(os.getenv("ASYNC_EXAMPLE_TIMEOUT", "2.0"))
    )

    fail_on_error: bool = False

    # базовый payload, который можно дополнять/перекрывать из params
    base_payload: Dict[str, Any] = field(default_factory=dict)


class AsyncExternalServiceExampleCheck:
    """
    Обёртка над асинхронной проверкой через внешний сервис.

    - хранит конфиг;
    - позволяет менять конфиг во время работы;
    - вызывается как обычная async-функция:
        await checker(text, params)
    """

    def __init__(self, config: Optional[ExternalServiceConfig] = None):
        self.config = config or ExternalServiceConfig()

    def update_config(self, **kwargs: Any) -> None:
        """
        Обновляет поля конфига на лету.
        Пример:
            checker.update_config(url="https://new-url", fail_on_error=True)
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                logger.warning("Unknown config field '%s'", key)

    def _resolve_timeout(self, params: Dict[str, Any]) -> float:
        """
        Приоритет:
        1) params["timeout"]
        2) env ASYNC_EXAMPLE_TIMEOUT
        3) self.config.timeout
        """
        # 1. Параметры вызова
        if "timeout" in params:
            try:
                return float(params["timeout"])
            except (ValueError, TypeError):
                logger.warning("Invalid timeout in params, fallback to env/config")

        # 2. Env
        timeout_str = os.getenv("ASYNC_EXAMPLE_TIMEOUT")
        if timeout_str:
            try:
                return float(timeout_str)
            except (ValueError, TypeError):
                logger.warning("Invalid timeout value in env, fallback to config")

        # 3. Конфиг
        return float(self.config.timeout)

    async def __call__(self, text: str, params: Dict[str, Any]) -> CheckResult:
        """
        Основной метод проверки (совместим с вашим интерфейсом AVAILABLE_CHECKS).
        """

        # Параметры + конфиг + env
        url = params.get("url") or self.config.url
        api_key = params.get("api_key") or self.config.api_key
        fail_on_error = bool(params.get("fail_on_error", self.config.fail_on_error))
        timeout = self._resolve_timeout(params)

        # Подготавливаем payload (конфиг + params, без мутации исходных словарей)
        payload: Dict[str, Any] = {}
        payload.update(self.config.base_payload or {})
        payload.update(params.get("payload") or {})
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
                        name=self.config.name,
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
                    name=self.config.name,
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
                    name=self.config.name,
                    passed=not fail_on_error,
                    score=0.0,
                    details=details,
                )

        except httpx.RequestError as exc:
            # Сетевые ошибки
            error_details: Dict[str, Any] = {
                "url": url,
                "request": payload,
                "timeout": timeout,
                "error": str(exc),
            }

            if isinstance(exc, httpx.ConnectTimeout):
                error_details["type"] = "connection_timeout"
            elif isinstance(exc, httpx.ReadTimeout):
                error_details["type"] = "read_timeout"
            elif isinstance(exc, httpx.ConnectError):
                error_details["type"] = "connection_error"

            return CheckResult(
                name=self.config.name,
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
                name=self.config.name,
                passed=not fail_on_error,
                score=0.0,
                details=details,
            )
