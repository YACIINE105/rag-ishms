import hashlib
import inspect
import logging
import re
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from functools import lru_cache, wraps

from helpers.config import get_settings
from utils.guardrails import redact_pii
from utils.logging import request_id_context
from utils.security import identity_context

logger = logging.getLogger(__name__)


def mask(data, **kwargs):
    if isinstance(data, str):
        return redact_pii(data)
    if isinstance(data, dict):
        return {key: mask(value) for key, value in data.items()}
    if isinstance(data, list):
        return [mask(value) for value in data]
    return data


def update_observation(observation, **kwargs):
    if observation is None:
        return
    try:
        observation.update(**mask(kwargs))
    except Exception:
        logger.warning("observability.update.failed")


@lru_cache(maxsize=1)
def get_client():
    settings = get_settings()
    if not getattr(settings, "LANGFUSE_ENABLED", False):
        return None
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        base_url=settings.LANGFUSE_BASE_URL,
        environment=settings.APP_ENVIRONMENT,
        release=settings.APP_VERSION,
        mask=mask,
        sample_rate=1.0,
        timeout=3,
    )


def trace_id(request_id):
    return hashlib.sha256(request_id.encode()).hexdigest()[:32]


@contextmanager
def span(name, metadata=None, as_type="span", model=None):
    client = get_client()
    if client is None:
        yield None
        return
    from langfuse import propagate_attributes

    context = (
        {"trace_id": trace_id(request_id_context.get())}
        if request_id_context.get() and name in {"answer", "stream"}
        else None
    )
    # Export failures should not alter the answer; do not catch application errors.
    try:
        observation = client.start_as_current_observation(
            name=name,
            as_type=as_type,
            trace_context=context,
            metadata=metadata,
            model=model,
        )
        attributes = propagate_attributes(
            user_id=identity_context.get(),
            tags=["rag"],
            metadata={"request_id": request_id_context.get() or "offline"},
        )
    except Exception:
        logger.warning("observability.unavailable")
        yield None
        return
    stack = ExitStack()
    try:
        current = stack.enter_context(observation)
        stack.enter_context(attributes)
    except Exception:
        stack.close()
        logger.warning("observability.unavailable")
        yield None
        return
    try:
        yield current
    except Exception as error:
        update_observation(current, level="ERROR", status_message=type(error).__name__)
        raise
    finally:
        stack.close()


def traced(name):
    def decorate(function):
        @wraps(function)
        async def wrapped(self, *args, **kwargs):
            bound = (
                inspect.signature(function)
                .bind_partial(self, *args, **kwargs)
                .arguments
            )
            project = bound.get("project")
            query = bound.get("query", bound.get("text", ""))
            metadata = {
                "index": self.get_index_metadata(),
                "project_id": getattr(project, "project_id", None),
                "k": bound.get("limit", 5),
                "language": "ar" if re.search(r"[\u0600-\u06ff]", query) else "en",
                "rerank_pool": getattr(self.app_settings, "RERANK_POOL", 30),
            }
            if project is not None:
                metadata["collection"] = self.create_collection_name(project.project_id)
            with span(name, metadata) as observation:
                update_observation(observation, input={"question": query})
                result = await function(self, *args, **kwargs)
                if observation:
                    details = {
                        "metadata": {
                            **metadata,
                            "prompt_version": self.prompt_version(),
                        }
                    }
                    if name == "answer" and isinstance(result, dict):
                        details["output"] = {
                            key: result[key]
                            for key in ("answer", "sources")
                            if key in result
                        }
                    update_observation(observation, **details)
                return result

        return wrapped

    return decorate


def traced_stream(function):
    """Capture trace IDs before the iterator is consumed across threadpool threads."""

    @wraps(function)
    def wrapped(self, *args, **kwargs):
        client = get_client()
        context = None
        if client and request_id_context.get():
            context = {"trace_id": trace_id(request_id_context.get())}
            parent = client.get_current_observation_id()
            if parent:
                context["parent_span_id"] = parent

        bound = (
            inspect.signature(function).bind_partial(self, *args, **kwargs).arguments
        )
        messages = list(bound.get("history") or [])
        messages.append({"role": "user", "content": bound.get("prompt", "")})

        def iterator():
            observation = None
            metadata = {}
            if client:
                try:
                    metadata = {"stream": True, "index": self.get_index_metadata()}
                    observation = client.start_observation(
                        name="generate",
                        as_type="generation",
                        trace_context=context,
                        model=getattr(
                            self.generation_client, "generation_model_id", None
                        ),
                        metadata=metadata,
                    )
                except Exception:
                    logger.warning("observability.stream.failed")
            update_observation(observation, input=messages)
            pieces = []
            completed = False
            failed = False
            response = None
            try:
                response = function(self, *args, **kwargs)
                for token in response:
                    if token:
                        if not pieces:
                            update_observation(
                                observation,
                                completion_start_time=datetime.now(timezone.utc),
                            )
                        pieces.append(token)
                    yield token
                completed = True
            except Exception as error:
                failed = True
                update_observation(
                    observation, level="ERROR", status_message=type(error).__name__
                )
                raise
            finally:
                try:
                    close = getattr(response, "close", None)
                    if callable(close):
                        close()
                finally:
                    update_observation(
                        observation,
                        output="".join(pieces),
                        metadata={**metadata, "completed": completed},
                    )
                    if not completed and not failed:
                        update_observation(
                            observation,
                            level="WARNING",
                            status_message="Stream interrupted",
                        )
                    if observation:
                        try:
                            observation.end()
                        except Exception:
                            logger.warning("observability.stream.failed")

        return iterator()

    return wrapped
