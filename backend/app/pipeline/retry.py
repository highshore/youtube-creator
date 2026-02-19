from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

import requests
from loguru import logger

T = TypeVar("T")


def is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return False


def retry_call(
    operation: str,
    func: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 0.75,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            transient = is_transient_error(exc)
            logger.warning(
                "Operation '{}' failed on attempt {}/{} (transient={}): {}",
                operation,
                attempt,
                max_attempts,
                transient,
                exc,
            )
            if not transient or attempt >= max_attempts:
                break
            sleep_s = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.2)
            time.sleep(sleep_s)
    assert last_error is not None
    raise last_error
