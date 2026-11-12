from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    base_delay_s: float = 0.1
    max_delay_s: float = 2.0

    def retryable(self, error_type: str | None) -> bool:
        return error_type in {"timeout", "TimeoutError", "ConnectionError", "rate_limit", "network"}


async def retry_async(operation: Callable[[], Awaitable[T]], policy: RetryPolicy) -> T:
    last: Exception | None = None
    for attempt in range(policy.max_attempts):
        try:
            return await operation()
        except Exception as exc:
            last = exc
            if attempt + 1 >= policy.max_attempts:
                break
            delay = min(policy.max_delay_s, policy.base_delay_s * (2**attempt))
            await asyncio.sleep(delay * (0.8 + random.random() * 0.4))
    assert last is not None
    raise last
