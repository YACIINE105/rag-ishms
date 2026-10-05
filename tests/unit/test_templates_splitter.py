from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from controllers.ProcessController import ProcessController, Document
from stores.llm.templates.template_parser import TemplateParser
from routes.schemes.data import ProcessRequest


@pytest.mark.parametrize("language",[None,"missing","en"])
def test_language_fallback(language):
    parser=TemplateParser(language)
    assert parser.language=="en"
    assert "assistant" in parser.get("rag","system_prompt")


@pytest.mark.parametrize("group,key",[(None,"x"),("rag",None),("missing","x"),("rag","missing")])
def test_missing_template_returns_none(group,key):
    assert TemplateParser().get(group,key) is None


def test_template_substitution_and_key_fallback():
    parser=TemplateParser("ar")
    assert "facts" in parser.get("rag","document_prompt",{"document_no":1,"chunk_text":"facts"})
    with patch("stores.llm.templates.template_parser.import_module", side_effect=[SimpleNamespace(),SimpleNamespace(key=SimpleNamespace(substitute=lambda vars:"fallback"))]):
        assert parser.get("rag","key")=="fallback"


@pytest.mark.parametrize("size,overlap",[(10,0),(10,3),(1,0),(40,39)])
def test_chunk_sizes_overlap_and_metadata(size,overlap):
    controller=ProcessController.__new__(ProcessController)
    text="abcdefghijklmnopqrstuvwxyz"*3
    metadata={"source":"report.pdf","page":2}
    chunks=controller.process_simple_splitter([text],[metadata],chunk_size=size,overlap_size=overlap)
    assert all(0 < len(c.page_content) <= size for c in chunks)
    assert all(c.metadata["page"]==2 and c.metadata["source"]=="report.pdf" for c in chunks)
    rebuilt=chunks[0].page_content+"".join(c.page_content[overlap:] for c in chunks[1:])
    assert rebuilt==text
    assert metadata=={"source":"report.pdf","page":2}
    if overlap:
        assert all(a.page_content[-overlap:]==b.page_content[:overlap] for a,b in zip(chunks,chunks[1:]))


def test_pages_never_merge_and_empty_text():
    controller=ProcessController.__new__(ProcessController)
    chunks=controller.process_simple_splitter(["a","b"," "],[{"page":0},{"page":1},{"page":2}])
    assert [c.metadata["page"] for c in chunks]==[0,1]


@pytest.mark.parametrize("kwargs",[{"chunk_size":0},{"chunk_size":5,"overlap_size":5},{"overlap_size":-1},{"splitter_tag":""}])
def test_invalid_splitter_settings(kwargs):
    with pytest.raises(ValueError):
        ProcessController.__new__(ProcessController).process_simple_splitter(["abc"],[{}],**kwargs)


def test_mismatched_metadata_and_process_overlap():
    controller=ProcessController.__new__(ProcessController)
    with pytest.raises(ValueError):
        controller.process_simple_splitter(["abc"],[])
    chunks=controller.process_file_content([Document("abcdefghij",{"page":0})],"x",chunk_size=6,overlap_size=2)
    assert [c.page_content for c in chunks]==["abcdef","efghij"]
    with pytest.raises(ValueError):
        ProcessRequest(chunk_size=5,overlap_size=5)


@pytest.mark.parametrize("extension,loader",[(".txt","TextLoader"),(".pdf","PyMuPDFLoader")])
def test_loader_selection(tmp_path,extension,loader):
    controller=ProcessController.__new__(ProcessController); controller.project_path=str(tmp_path)
    (tmp_path/f"doc{extension}").write_text("test")
    with patch(f"controllers.ProcessController.{loader}") as factory:
        factory.return_value.load.return_value=["loaded"]
        assert controller.get_file_content(f"doc{extension}")==["loaded"]
        assert controller.get_file_content_2(f"doc{extension}")==factory.return_value.document
    assert controller.get_file_content("missing.pdf") is None
    assert controller.get_file_content_2("missing.pdf") is None
    (tmp_path/"doc.bin").write_text("x")
    assert controller.get_file_loader("doc.bin") is None
