"""Reproduce the English article fixtures used by the CI evaluation set."""

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf

ARTICLES = {
    1,
    2,
    3,
    4,
    5,
    40,
    43,
    44,
    45,
    48,
    49,
    50,
    89,
    90,
    93,
    94,
    95,
    147,
    148,
    163,
}
SOURCE_URL = "https://sadanykhalifa.com/uploads/Laws/1576751803.pdf"


def extract_articles(source):
    sections = {}
    current = None
    with pymupdf.open(source) as document:
        for page_number, page in enumerate(document, 1):
            # English is the left column. Never concatenate the bilingual columns.
            text = page.get_text(
                clip=pymupdf.Rect(0, 0, page.rect.width / 2, page.rect.height)
            )
            for line in text.splitlines():
                match = re.fullmatch(r"Article\s+(\d+)\s*", line.strip())
                if match:
                    current = int(match.group(1))
                    if current in sections:
                        raise ValueError("Repeated article heading")
                    sections[current] = {"lines": [], "pages": set()}
                elif current is not None and line.strip():
                    sections[current]["lines"].append(line.strip())
                    sections[current]["pages"].add(page_number)
    digest = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    records = []
    for number in sorted(ARTICLES):
        section = sections[number]
        content = re.sub(r"[\u0600-\u06ff]", "", " ".join(section["lines"]))
        # Section headings between articles are not part of the legal provision.
        content = re.split(
            r"2\. The Application of Laws|2\. Juristic persons|2\. The Effects of a Contract",
            content,
        )[0].strip()
        if not content:
            raise ValueError(f"Article {number} has no text")
        records.append(
            {
                "article_number": number,
                "text_en": content,
                "source_pages": sorted(section["pages"]),
                "source_url": SOURCE_URL,
                "source_sha256": digest,
                "asset_name": Path(source).name,
                "citation": f"Egyptian Civil Code, Article {number}",
            }
        )
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Path("eval/corpus/egyptian-civil-code.pdf")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("eval/corpus/articles.json")
    )
    args = parser.parse_args()
    records = extract_articles(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Extracted {len(records)} evaluation article fixtures")


if __name__ == "__main__":
    main()
