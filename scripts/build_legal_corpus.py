"""Extract the complete bilingual corpus with the existing Qalam/parser pipeline."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def validate(records, known_issues=None):
    known_issues = known_issues or {}
    numbers = [row["article_number"] for row in records]
    if not numbers or any(type(number) is not int for number in numbers):
        raise ValueError("Article numbers must be integers")
    if numbers != list(range(1, max(numbers) + 1)):
        raise ValueError("Corpus has duplicate articles or unexplained gaps")
    for row in records:
        missing = [name for name in ("text_ar", "text_en") if not row[name].strip()]
        allowed = known_issues.get(str(row["article_number"]), {}).get(
            "missing_fields", []
        )
        if missing != allowed:
            raise ValueError(
                f"Article {row['article_number']} has unexpected missing language text"
            )
        if max(len(row["text_ar"]), len(row["text_en"])) > 20000:
            raise ValueError("Implausible article length")
        if 54 <= row["article_number"] <= 80 and not row["is_repealed"]:
            raise ValueError("Known repealed articles must retain repeal notices")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=ROOT / "eval/corpus/egyptian-civil-code.pdf"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/corpus/articles.json"
    )
    args = parser.parse_args()
    import qalam

    from helpers.extract_to_json import make_article_schema

    records, issues = make_article_schema(
        json.loads(qalam.Document(str(args.source)).to_json())
    )
    digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
    manifest = json.loads((ROOT / "eval/corpus/source-issues.json").read_text())
    known_issues = manifest["articles"] if manifest["source_sha256"] == digest else {}
    validate(records, known_issues)
    for record in records:
        record.update(source_sha256=digest, asset_name=args.source.name)
        if str(record["article_number"]) in known_issues:
            record["source_issue"] = known_issues[str(record["article_number"])]
            record["needs_review"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Extracted {len(records)} articles; {len(issues)} missing-language issues")


if __name__ == "__main__":
    main()
