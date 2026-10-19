import hashlib
import logging
from importlib import import_module
from pathlib import Path


class TemplateParser:
    def __init__(self, language=None, default_language="en"):
        self.current_path = str(Path(__file__).resolve().parent)
        self.default_language = default_language
        self.remote_version = None
        self.set_language(language)

    def set_language(self, language):
        language = language or self.default_language
        self.language = (
            language
            if (Path(self.current_path) / "locales" / language).is_dir()
            else self.default_language
        )

    def get(self, group, key, vars=None):
        if not group or not key:
            return None
        for language in dict.fromkeys((self.language, self.default_language)):
            if not (
                Path(self.current_path) / "locales" / language / f"{group}.py"
            ).is_file():
                continue
            module = import_module(f"stores.llm.templates.locales.{language}.{group}")
            template = getattr(module, key, None)
            if template is not None:
                if group == "rag" and key == "system_prompt":
                    from helpers.config import get_settings
                    from utils.observability import get_client

                    label = getattr(get_settings(), "LANGFUSE_PROMPT_LABEL", None)
                    client = get_client() if label else None
                    if client:
                        try:
                            remote = client.get_prompt(
                                f"rag-system-{language}",
                                label=label,
                                cache_ttl_seconds=60,
                                fallback=template.template,
                                max_retries=0,
                                fetch_timeout_seconds=3,
                            )
                            self.remote_version = str(remote.version)
                            return remote.compile(**(vars or {}))
                        except Exception:
                            logging.getLogger(__name__).warning(
                                "prompt.remote.fallback"
                            )
                return template.substitute(vars or {})
        return None

    @property
    def version(self):
        content = []
        for key in ("system_prompt", "document_prompt", "footer_prompt"):
            for language in dict.fromkeys((self.language, self.default_language)):
                module = import_module(f"stores.llm.templates.locales.{language}.rag")
                template = getattr(module, key, None)
                if template is not None:
                    content.append(template.template)
                    break
        digest = hashlib.sha256("\n".join(content).encode()).hexdigest()[:12]
        remote = f"-lf{self.remote_version}" if self.remote_version is not None else ""
        return f"rag-{digest}{remote}"
