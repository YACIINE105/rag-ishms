import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from controllers.ProcessController import Document, ProcessController
from routes.schemes.data import ProcessRequest
from stores.llm.templates.template_parser import TemplateParser


@pytest.mark.parametrize("language", [None, "missing", "en"])
def test_language_fallback(language):
    parser = TemplateParser(language)
    assert parser.language == "en"
    assert "assistant" in parser.get("rag", "system_prompt")


@pytest.mark.parametrize(
    "group,key", [(None, "x"), ("rag", None), ("missing", "x"), ("rag", "missing")]
)
def test_missing_template_returns_none(group, key):
    assert TemplateParser().get(group, key) is None


def test_template_substitution_and_key_fallback():
    parser = TemplateParser("ar")
    assert "facts" in parser.get(
        "rag", "document_prompt", {"document_no": 1, "chunk_text": "facts"}
    )
    with patch(
        "stores.llm.templates.template_parser.import_module",
        side_effect=[
            SimpleNamespace(),
            SimpleNamespace(key=SimpleNamespace(substitute=lambda vars: "fallback")),
        ],
    ):
        assert parser.get("rag", "key") == "fallback"


@pytest.mark.parametrize("size,overlap", [(10, 0), (10, 3), (1, 0), (40, 39)])
def test_chunk_sizes_overlap_and_metadata(size, overlap):
    controller = ProcessController.__new__(ProcessController)
    text = "abcdefghijklmnopqrstuvwxyz" * 3
    metadata = {"source": "report.pdf", "page": 2}
    chunks = controller.process_simple_splitter(
        [text], [metadata], chunk_size=size, overlap_size=overlap
    )
    assert all(0 < len(c.page_content) <= size for c in chunks)
    assert all(
        c.metadata["page"] == 2 and c.metadata["source"] == "report.pdf" for c in chunks
    )
    rebuilt = chunks[0].page_content + "".join(
        c.page_content[overlap:] for c in chunks[1:]
    )
    assert rebuilt == text
    assert metadata == {"source": "report.pdf", "page": 2}
    if overlap:
        assert all(
            a.page_content[-overlap:] == b.page_content[:overlap]
            for a, b in zip(chunks, chunks[1:])
        )


def test_pages_never_merge_and_empty_text():
    controller = ProcessController.__new__(ProcessController)
    chunks = controller.process_simple_splitter(
        ["a", "b", " "], [{"page": 0}, {"page": 1}, {"page": 2}]
    )
    assert [c.metadata["page"] for c in chunks] == [0, 1]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"chunk_size": 0},
        {"chunk_size": 5, "overlap_size": 5},
        {"overlap_size": -1},
        {"splitter_tag": ""},
    ],
)
def test_invalid_splitter_settings(kwargs):
    with pytest.raises(ValueError):
        ProcessController.__new__(ProcessController).process_simple_splitter(
            ["abc"], [{}], **kwargs
        )


def test_mismatched_metadata_and_process_overlap():
    controller = ProcessController.__new__(ProcessController)
    with pytest.raises(ValueError):
        controller.process_simple_splitter(["abc"], [])
    chunks = controller.process_file_content(
        [Document("abcdefghij", {"page": 0})], "x", chunk_size=6, overlap_size=2
    )
    assert [c.page_content for c in chunks] == ["abcdef", "efghij"]
    with pytest.raises(ValueError):
        ProcessRequest(chunk_size=5, overlap_size=5)


@pytest.mark.parametrize(
    "extension,loader", [(".txt", "TextLoader"), (".pdf", "PyMuPDFLoader")]
)
def test_loader_selection(tmp_path, extension, loader):
    controller = ProcessController.__new__(ProcessController)
    controller.project_path = str(tmp_path)
    (tmp_path / f"doc{extension}").write_text("test")
    with patch(f"controllers.ProcessController.{loader}") as factory:
        factory.return_value.load.return_value = ["loaded"]
        assert controller.get_file_content(f"doc{extension}", W_qalam=False) == [
            "loaded"
        ]
        assert (
            controller.get_file_content_2(f"doc{extension}")
            == factory.return_value.document
        )
    assert controller.get_file_content("missing.pdf") is None
    assert controller.get_file_content_2("missing.pdf") is None
    (tmp_path / "doc.bin").write_text("x")
    assert controller.get_file_loader("doc.bin") is None


def test_qalam_document_to_articles_and_language_chunks(tmp_path, caplog):
    controller = ProcessController.__new__(ProcessController)
    controller.project_path = str(tmp_path)
    (tmp_path / "law.pdf").write_bytes(b"PDF input")

    arabic_text = "العقد شريعة المتعاقدين. " * 8
    english_text = "Contract provision in English. " * 8
    qalam_data = {
        "pages": [
            {
                "number": 16,
                "width": 600,
                "blocks": [
                    {
                        "type": "table",
                        "rows": [
                            [
                                {
                                    "text": f"مادة ١٤٧ {arabic_text}",
                                    "bbox": [310, 600, 580, 660],
                                },
                                {
                                    "text": f"Article 147 {english_text}",
                                    "bbox": [20, 600, 290, 660],
                                },
                            ]
                        ],
                    }
                ],
            },
            {
                "number": 17,
                "width": 600,
                "blocks": [
                    {
                        "type": "table",
                        "rows": [
                            [
                                {
                                    "text": "تكملة المادة.",
                                    "bbox": [310, 700, 580, 760],
                                },
                                {
                                    "text": "Continuation of the article.",
                                    "bbox": [20, 700, 290, 760],
                                },
                            ],
                            [
                                {"text": "", "bbox": [310, 600, 580, 660]},
                                {
                                    "text": "Article 148 Another English provision.",
                                    "bbox": [20, 600, 290, 660],
                                },
                            ],
                        ],
                    }
                ],
            },
        ],
    }
    loaded_document = SimpleNamespace(to_json=lambda: json.dumps(qalam_data))

    with (
        patch(
            "controllers.ProcessController.qalam.Document",
            return_value=loaded_document,
        ) as factory,
        patch.object(
            controller,
            "process_simple_splitter",
            side_effect=AssertionError("Articles must bypass the baseline splitter"),
        ),
    ):
        file_content = controller.get_file_content("law.pdf")
        assert file_content is loaded_document
        chunks = controller.process_file_content(
            file_content, "law.pdf", chunk_size=1, overlap_size=0
        )
        factory.assert_called_once_with(str(tmp_path / "law.pdf"))

    corpus_path = tmp_path / "law.articles.json"
    saved_text = corpus_path.read_text(encoding="utf-8")
    articles = json.loads(saved_text)

    assert "العقد" in saved_text
    assert [article["article_number"] for article in articles] == [147, 148]
    assert articles[0]["source_pages"] == [16, 17]
    assert articles[1]["text_ar"] == ""
    assert [
        (chunk.metadata["article_number"], chunk.metadata["language"])
        for chunk in chunks
    ] == [(147, "ar"), (147, "en"), (148, "en")]
    assert chunks[0].page_content == (
        "Egyptian Civil Code, Article 147\n" + arabic_text.strip() + "\n\nتكملة المادة."
    )
    assert chunks[1].page_content == (
        "Egyptian Civil Code, Article 147\n"
        + english_text.strip()
        + "\n\nContinuation of the article."
    )
    assert chunks[0].metadata["citation"] == "Egyptian Civil Code, Article 147"
    assert chunks[0].metadata["source_pages"] == [16, 17]
    assert len({chunk.metadata["chunk_key"] for chunk in chunks}) == 3
    assert "148" in caplog.text and "text_ar" in caplog.text

    output_path = tmp_path / "export" / "articles.json"
    exported_articles, issues = controller.convert_pdf_to_articles(
        file_content, "law.pdf", output_path=str(output_path)
    )
    assert exported_articles == articles
    assert issues == [
        {
            "article_number": 148,
            "missing_fields": ["text_ar"],
            "source_pages": [17],
        }
    ]
    assert json.loads(output_path.read_text(encoding="utf-8")) == articles


def test_local_prompt_version_is_content_based():
    english, arabic = TemplateParser("en"), TemplateParser("ar")
    assert english.version.startswith("rag-")
    assert english.version != arabic.version
    assert english.version == TemplateParser("en").version
