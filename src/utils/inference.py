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
            from utils.observability import span

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
                    try:
                        observation.update(usage_details=usage)
                    except Exception:
                        import logging

                        logging.getLogger(__name__).warning(
                            "observability.usage.failed"
                        )
                return result

    return await run_in_threadpool(call)
