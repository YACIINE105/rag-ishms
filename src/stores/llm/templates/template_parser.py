from importlib import import_module
from pathlib import Path


class TemplateParser:
    def __init__(self, language=None, default_language="en"):
        self.current_path = str(Path(__file__).resolve().parent)
        self.default_language = default_language
        self.set_language(language)

    def set_language(self, language):
        language = language or self.default_language
        self.language = language if (Path(self.current_path)/"locales"/language).is_dir() else self.default_language

    def get(self, group, key, vars=None):
        if not group or not key:
            return None
        for language in dict.fromkeys((self.language, self.default_language)):
            if not (Path(self.current_path)/"locales"/language/f"{group}.py").is_file():
                continue
            module = import_module(f"stores.llm.templates.locales.{language}.{group}")
            template = getattr(module, key, None)
            if template is not None:
                return template.substitute(vars or {})
        return None
