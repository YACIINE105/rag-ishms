import re

DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)


def article_header(text, language):
    pattern = (
        r"^مادة\s*[\[(]*\s*(\d+)\b"
        if language == "ar"
        else r"^(?:Article|rticle)\s*(\d+)\b"
    )

    text = text.strip()
    match = re.match(pattern, text.translate(DIGITS), re.IGNORECASE)

    if not match:
        return None, text

    body = text[match.end() :].strip()

    if language == "ar":
        # Remove heading brackets while preserving numbered paragraphs.
        body = re.sub(r"^[()\[\]]\s*(?=[^\d\s]|$)", "", body)

    return int(match.group(1)), body


def page_units(page):
    units = []

    for block in page["blocks"]:
        if block["type"] == "table":
            for row in block["rows"]:
                unit = {"ar": "", "en": "", "table": True}

                for cell in row:
                    center_x = (cell["bbox"][0] + cell["bbox"][2]) / 2
                    language = "ar" if center_x > page["width"] / 2 else "en"
                    unit[language] = cell["text"].strip()

                unit["top"] = max(cell["bbox"][3] for cell in row)
                unit["height"] = max(cell["bbox"][3] - cell["bbox"][1] for cell in row)
                units.append(unit)

        elif block["type"] == "text":
            center_x = (block["bbox"][0] + block["bbox"][2]) / 2
            language = "ar" if center_x > page["width"] / 2 else "en"

            units.append(
                {
                    "ar": "",
                    "en": "",
                    language: block["text"].strip(),
                    "table": False,
                    "top": block["bbox"][3],
                    "height": 0,
                }
            )

    # Qalam's y coordinates grow upwards.
    return sorted(units, key=lambda unit: -unit["top"])


def make_article_schema(data):
    records = {}
    issues = []

    levels = ["part", "book", "chapter", "section", "topic"]
    hierarchy = dict.fromkeys(levels)

    current = {"ar": None, "en": None}
    seen = {"ar": set(), "en": set()}

    started = False
    pending_heading = None

    # Observed topic labels requiring explicit recognition in this PDF.
    topic_labels = {
        "Leases of agricultural land.",
        "Lease of Wakf property.",
        "The Procedure for Preemption.",
        "2- The Relationship between the Surety and the Debtor",
    }

    def get_record(number):
        if number not in records:
            records[number] = {
                "article_number": number,
                **hierarchy,
                "text_ar": "",
                "text_en": "",
                "is_repealed": False,
                "source_page": None,
                "source_pages": [],
                "citation": f"Egyptian Civil Code, Article {number}",
            }

        return records[number]

    def append(record, language, text, page_number):
        field = f"text_{language}"

        if text:
            record[field] = (record[field] + "\n\n" + text).strip()

        if page_number not in record["source_pages"]:
            record["source_pages"].append(page_number)

        record["source_page"] = min(record["source_pages"])

    for page in sorted(data["pages"], key=lambda page: page["number"]):
        for unit in page_units(page):
            headers = {
                language: article_header(unit[language], language)
                for language in ("ar", "en")
            }

            en = unit["en"]
            ar = unit["ar"]

            # 1. Expand repeal notices into one record per article.
            repeal = re.search(
                r"\bArticles?\s*(\d+)\s*[-–—]\s*(\d+)\b.*\brepealed\b",
                en.translate(DIGITS),
                re.IGNORECASE,
            )

            if repeal:
                first, last = map(int, repeal.groups())

                for number in range(first, last + 1):
                    record = get_record(number)
                    record["is_repealed"] = True
                    record["text_kind"] = "repeal_notice"

                    append(record, "ar", ar, page["number"])
                    append(
                        record,
                        "en",
                        headers["en"][1].lstrip("* "),
                        page["number"],
                    )

                current = {"ar": None, "en": None}
                continue

            # 2. Capture hierarchy labels and short heading rows.
            heading = re.match(
                r"^(BOOK|CHAPTER|SECTION)\s+[IVXLCDM]+\b[.:]?\s*(.*)$",
                en,
                re.IGNORECASE,
            )
            part = re.match(
                r"^(?:FIRST|SECOND)\s+PART\s+(.*)$",
                en,
                re.IGNORECASE,
            )

            no_article = all(number is None for number, _ in headers.values())
            numbered_topic = re.match(r"^\d+\s*[.\-–]", en)

            short_row = (
                unit["table"]
                and en
                and unit["height"] <= 35
                and len(en) <= 180
                and (
                    numbered_topic
                    or en in topic_labels
                    or (ar and not en.endswith((".", ";", "!", "?")))
                )
            )

            if no_article and (heading or part or short_row or en in topic_labels):
                if part:
                    level, title = "part", part.group(1)
                elif heading:
                    level = heading.group(1).lower()
                    title = heading.group(2)
                elif pending_heading:
                    level, title = pending_heading, en
                else:
                    level = "topic"
                    title = re.sub(r"^\d+\s*[.\-–]\s*", "", en)

                hierarchy[level] = title.strip() or None

                for lower_level in levels[levels.index(level) + 1 :]:
                    hierarchy[lower_level] = None

                pending_heading = level if not title.strip() else None
                current = {"ar": None, "en": None}
                continue

            # 3. Skip issuance-law articles above the bilingual code.
            if not started:
                if headers["en"][0] is None:
                    continue
                started = True

            # 4. Keep separate language states across blocks and pages.
            for language in ("ar", "en"):
                number, body = headers[language]

                if number is not None:
                    if number in seen[language]:
                        raise ValueError(f"Repeated {language} Article {number}")

                    seen[language].add(number)
                    current[language] = number

                    append(
                        get_record(number),
                        language,
                        body,
                        page["number"],
                    )

                elif unit[language] and current[language] is not None:
                    append(
                        get_record(current[language]),
                        language,
                        unit[language],
                        page["number"],
                    )

    articles = [records[number] for number in sorted(records)]

    for article in articles:
        missing = [
            field for field in ("text_ar", "text_en") if not article[field].strip()
        ]

        if missing:
            issues.append(
                {
                    "article_number": article["article_number"],
                    "missing_fields": missing,
                    "source_pages": article["source_pages"],
                }
            )

    return articles, issues
