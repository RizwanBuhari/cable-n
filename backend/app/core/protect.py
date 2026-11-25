"""Abuse protection for the public API.

* Rate limits per client IP (sliding 60 s window) and daily counters.
* Engine calls run in a small bounded thread pool. If every worker is busy
  for longer than a few seconds the request gets 503 "busy"; if a call runs
  past ENGINE_TIMEOUT_S the client gets 504. Python cannot kill a running
  thread, so the hard bound on work per request is the INPUT caps (feeder
  count, sweep points, cables per arrangement) - the timeout only stops the
  client waiting. All in-memory: with several server processes each process
  enforces its own limits (documented in KNOWN_LIMITATIONS.md).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from datetime import date

from fastapi import HTTPException, Request

from .config import get_settings

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)
_daily: dict[str, int] = defaultdict(int)
_daily_day = [date.today()]


def client_ip(request: Request) -> str:
    if get_settings().TRUST_PROXY_HEADERS:
        fwd = request.headers.get('x-forwarded-for', '')
        if fwd:
            return fwd.split(',')[0].strip()[:64]
    return (request.client.host if request.client else 'unknown')[:64]


def rate_limit(request: Request, bucket: str, per_minute: int):
    key = f'{bucket}:{client_ip(request)}'
    now = time.monotonic()
    with _lock:
        dq = _hits[key]
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= per_minute:
            retry = int(60 - (now - dq[0])) + 1
            raise HTTPException(429, f'Too many requests - please wait {retry} s and try again.',
                                headers={'Retry-After': str(retry)})
        dq.append(now)
        if len(_hits) > 50000:  # bound memory under address-spraying
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60][:25000]:
                _hits.pop(k, None)


def daily_quota(request: Request, bucket: str, per_ip: int, global_cap: int):
    with _lock:
        if _daily_day[0] != date.today():
            _daily.clear()
            _daily_day[0] = date.today()
        k_ip = f'{bucket}:{client_ip(request)}'
        k_all = f'{bucket}:*'
        if _daily[k_all] >= global_cap:
            raise HTTPException(429, 'The daily assistant allowance for this website has been used. '
                                     'Calculations are unaffected; please try the assistant tomorrow.')
        if _daily[k_ip] >= per_ip:
            raise HTTPException(429, 'Daily assistant limit reached for your connection. Calculations are '
                                     'unaffected.')
        _daily[k_ip] += 1
        _daily[k_all] += 1


_pool: ThreadPoolExecutor | None = None
_slots: threading.BoundedSemaphore | None = None


def _executor():
    global _pool, _slots
    if _pool is None:
        n = max(1, get_settings().ENGINE_MAX_CONCURRENT)
        _pool = ThreadPoolExecutor(max_workers=n, thread_name_prefix='cablen-engine')
        _slots = threading.BoundedSemaphore(n * 2)
    return _pool, _slots


def run_bounded(fn, *args, timeout: float | None = None, **kwargs):
    """Run an engine call with a concurrency bound and a wait timeout."""
    pool, slots = _executor()
    if not slots.acquire(timeout=5):
        raise HTTPException(503, 'The calculation engine is busy - please retry in a few seconds.',
                            headers={'Retry-After': '5'})
    fut = pool.submit(fn, *args, **kwargs)
    fut.add_done_callback(lambda _f: slots.release())
    try:
        return fut.result(timeout=timeout or get_settings().ENGINE_TIMEOUT_S)
    except FutTimeout:
        raise HTTPException(504, 'The calculation exceeded the time limit. Reduce the size of the problem '
                                 '(fewer feeders, cables or sweep points).')


def reset_for_tests():
    with _lock:
        _hits.clear()
        _daily.clear()
