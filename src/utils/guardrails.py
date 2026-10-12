"""Conservative English/Arabic rules; these are not a medical PII detector."""

import re

from fastapi import HTTPException

from utils.metrics import GUARDRAIL_DECISIONS

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
PII = re.compile(
    r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,189}\.[A-Za-z]{2,20}"
    r"|(?<!\d)[23]\d{13}(?!\d)"
    r"|(?<!\d)(?:\+?20[ -]?)?01[0125](?:[ -]?\d){8}(?!\d)"
    r"|(?:patient\s+name|اسم\s+المريض)\s*[:：]\s*[^\n,;؛.]{1,80}",
    re.IGNORECASE,
)
INJECTION = re.compile(
    r"(?:ignore|disregard)\s+(?:all\s+)?(?:previous|prior|system)\s+instructions"
    r"|(?:reveal|print|show)\s+(?:the\s+)?(?:system\s+prompt|api\s+key)"
    r"|(?:تجاهل|اهمل|أهمل)\s+(?:كل\s+|جميع\s+)?(?:التعليمات\s+السابقة|تعليمات\s+النظام)"
    r"|(?:اكشف|أظهر|اعرض)\s+(?:مفتاح|تعليمات\s+النظام)",
    re.IGNORECASE,
)


def redact_pii(text):
    normalized = text.translate(DIGITS)
    # Translation preserves offsets; leave unrelated Arabic digits unchanged.
    return PII.sub("[REDACTED]", normalized) if PII.search(normalized) else text


def protect_query(text):
    if INJECTION.search(text):
        GUARDRAIL_DECISIONS.labels("injection", "denied").inc()
        raise HTTPException(422, "Question contains an instruction override")
    redacted = redact_pii(text)
    GUARDRAIL_DECISIONS.labels(
        "input_pii", "redacted" if redacted != text else "allowed"
    ).inc()
    return redacted


def redact_stream(iterator):
    """Keep enough lookahead for every bounded PII pattern, including split tokens."""
    pending = ""
    try:
        for token in iterator:
            pending += token
            if len(pending) > 1024:
                cut = len(pending) - 512
                for match in PII.finditer(pending.translate(DIGITS)):
                    if match.start() < cut < match.end():
                        cut = match.start()
                if cut:
                    yield redact_pii(pending[:cut])
                    pending = pending[cut:]
        if pending:
            yield redact_pii(pending)
    finally:
        iterator.close()
