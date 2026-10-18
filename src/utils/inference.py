"""Run blocking operations off the event loop with one lock per shared client."""

import asyncio
from threading import Lock, RLock
from weakref import WeakKeyDictionary

from starlette.concurrency import run_in_threadpool

_lock_creation = Lock()


async def run_serialized(owner, function, *args, **kwargs):
    with _lock_creation:
        if not hasattr(owner, "_operation_lock"):
            owner._operation_lock = RLock()
        operation_lock = owner._operation_lock
        if not hasattr(owner, "_async_operation_locks"):
            owner._async_operation_locks = WeakKeyDictionary()
        loop = asyncio.get_running_loop()
        if loop not in owner._async_operation_locks:
            owner._async_operation_locks[loop] = asyncio.Lock()
        async_operation_lock = owner._async_operation_locks[loop]

    def call():
        with operation_lock:
            # Readiness probes share client locks without exporting inference traces.
            if getattr(function, "__name__", None) == "health_check":
                return function(*args, **kwargs)

            from utils.observability import span, update_observation

            name = {
                "embed_text": "embed",
                "rerank": "rerank",
                "generate_text": "generate",
            }.get(getattr(function, "__name__", "provider"), "provider")
            with span(
                name,
                as_type="generation" if name == "generate" else "span",
                model=getattr(owner, "generation_model_id", None)
                if name == "generate"
                else None,
            ) as observation:
                if observation and name == "generate":
                    history = kwargs.get(
                        "chat_history", args[1] if len(args) > 1 else None
                    )
                    messages = list(history or [])
                    messages.append(
                        {
                            "role": "user",
                            "content": kwargs.get("prompt", args[0] if args else ""),
                        }
                    )
                    update_observation(observation, input=messages)
                result = function(*args, **kwargs)
                if observation and name == "generate":
                    usage = {
                        key: value
                        for key, value in {
                            "input": getattr(result, "tokens_in", None),
                            "output": getattr(result, "tokens_out", None),
                        }.items()
                        if isinstance(value, int)
                    }
                    update_observation(
                        observation,
                        output=str(result) if result is not None else None,
                        usage_details=usage,
                    )
                return result

    # Wait outside the worker pool so queued inference cannot consume every slot.
    async with async_operation_lock:
        return await run_in_threadpool(call)
