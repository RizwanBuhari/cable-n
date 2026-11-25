"""Background jobs for long-running work (batch schedules, validation suite).

Progress is real: it counts completed items (feeders, validation cases),
never a timer. Cancellation is cooperative between items. Jobs live in memory
only, are addressed by an unguessable id, and are discarded 15 minutes after
they finish - nothing is persisted.
"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='cablen-job')
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
TTL_S = 15 * 60


def _sweep():
    now = time.monotonic()
    with _lock:
        for jid in [k for k, j in _jobs.items() if j.get('finished') and now - j['finished'] > TTL_S]:
            _jobs.pop(jid, None)


def active_count() -> int:
    return sum(1 for j in _jobs.values() if j['status'] in ('queued', 'running'))


def submit(kind: str, fn, *args) -> str:
    _sweep()
    jid = uuid.uuid4().hex
    job = {'id': jid, 'kind': kind, 'status': 'queued', 'done': 0, 'total': None, 'result': None, 'error': None,
           'cancel': False, 'finished': None}
    with _lock:
        _jobs[jid] = job

    def progress(done, total):
        job['done'], job['total'] = done, total

    def cancelled():
        return job['cancel']

    def runner():
        job['status'] = 'running'
        try:
            job['result'] = fn(progress, cancelled, *args)
            job['status'] = 'cancelled' if job['cancel'] else 'completed'
        except Exception as e:  # surfaced to the client, not swallowed
            job['status'] = 'failed'
            job['error'] = str(getattr(e, 'detail', None) or e)[:500]
        finally:
            job['finished'] = time.monotonic()

    _pool.submit(runner)
    return jid


def get(jid: str) -> dict | None:
    _sweep()
    return _jobs.get(jid)


def cancel(jid: str) -> bool:
    j = _jobs.get(jid)
    if not j or j['status'] not in ('queued', 'running'):
        return False
    j['cancel'] = True
    return True


def public(job: dict) -> dict:
    out = {k: v for k, v in job.items() if k not in ('cancel', 'finished')}
    out['cancel_requested'] = job['cancel']
    return out
