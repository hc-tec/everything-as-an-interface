from __future__ import annotations

import time
import asyncio
from typing import Callable, Any, Awaitable

async def wait_until_result(func: Callable[[], Any], timeout: float) -> Any:
    """
    周期性调用 func，直到返回非 None 结果或超时。

    参数：
        func: 一个可调用对象，返回值可以是普通值或协程对象。当返回值不是 None 时，表示成功。
        timeout: 最大等待时间（毫秒），超过这个时间仍未得到结果则抛出 TimeoutError。

    返回：
        func 第一次返回的非 None 结果。

    异常：
        TimeoutError: 在超时时间内未获得非 None 结果。
    """
    start = time.monotonic()
    poll_interval = 0.5  # 轮询间隔（秒）

    while True:
        result = func()
        if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
            result = await result

        if result is not None:
            return result

        # 将毫秒转换为秒进行比较
        if (time.monotonic() - start) >= (float(timeout) / 1000.0):
            raise TimeoutError("超时")

        await asyncio.sleep(poll_interval)
