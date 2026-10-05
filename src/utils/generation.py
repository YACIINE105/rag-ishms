"""Keep generation compatible with string callers while retaining actual token usage."""
import logging


class GenerationText(str):
    def __new__(cls, text, tokens_in=None, tokens_out=None):
        result = super().__new__(cls, text)
        result.tokens_in = tokens_in
        result.tokens_out = tokens_out
        return result


def truncate_text(text, limit, logger=None):
    if len(text) > limit:
        (logger or logging.getLogger(__name__)).warning("query.truncated", extra={
            "original_characters": len(text), "retained_characters": limit})
    return text[:limit].strip()
