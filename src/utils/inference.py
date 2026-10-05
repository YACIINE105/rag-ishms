"""Run blocking operations off the event loop with one lock per shared client."""
from threading import Lock, RLock
from starlette.concurrency import run_in_threadpool

_lock_creation = Lock()


async def run_serialized(owner, function, *args, **kwargs):
    with _lock_creation:
        if not hasattr(owner, "_operation_lock"):
            owner._operation_lock = RLock()
        operation_lock = owner._operation_lock

    def call():
        with operation_lock:
            return function(*args, **kwargs)

    return await run_in_threadpool(call)
