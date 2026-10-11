import json
import logging
import os
from dataclasses import dataclass
from typing import List

import qalam

# from langchain_text_splitters  import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader

from helpers import make_article_schema
from models.enums import ProcessingSgnal

from .BaseController import BaseController
from .ProjectController import ProjectController

logger = logging.getLogger(__name__)


@dataclass
class Document:
    page_content: str
    metadata: dict


class ProcessController(BaseController):
    def __init__(self, project_id: str):
        super().__init__()

        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id=project_id)

    def get_file_extension(self, file_id: str):
        return os.path.splitext(file_id)[-1].lower()

    def get_file_loader(self, file_id: str, W_qalam: bool = False):

        file_extension = self.get_file_extension(file_id=file_id)
        file_path = os.path.join(self.project_path, file_id)

        if not os.path.exists(file_path):
            return None

        if file_extension == ProcessingSgnal.TXT.value:
            return TextLoader(file_path=file_path, encoding="utf-8")

        if file_extension == ProcessingSgnal.PDF.value and not W_qalam:
            return PyMuPDFLoader(file_path=file_path)

        if file_extension == ProcessingSgnal.PDF.value and W_qalam:

            class Qalamloader:
                def load(self):
                    return qalam.Document(file_path)

            return Qalamloader()
            # converter = DocumentConverter()
            # return converter.convert(source=file_path)
        return None

    def get_file_content(self, file_id: str, W_qalam: bool = True):
        loader = self.get_file_loader(file_id=file_id, W_qalam=W_qalam)
        if loader:
            return loader.load()
        else:
            return None

    def get_file_content_2(self, file_id: str):
        loader = self.get_file_loader(file_id=file_id)
        if loader:
            return loader.document
        else:
            return None

    def convert_pdf_to_articles(
        self,
        file_content,
        file_id: str,
        output_path: str | None = None,
    ):
        # 1. Reuse the Qalam document returned by get_file_content().
        qalam_data = json.loads(file_content.to_json())

        # 2. Convert pages, blocks, and tables into article records.
        articles, issues = make_article_schema(qalam_data)

        # 3. Save the article corpus in this project's folder.
        if output_path is None:
            file_stem = os.path.splitext(os.path.basename(file_id))[0]
            output_path = os.path.join(self.project_path, f"{file_stem}.articles.json")

        output_directory = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(output_directory, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(
                articles,
                file,
                ensure_ascii=False,
                indent=2,
            )

        return articles, issues

    def process_file_content(
        self,
        file_content: list | qalam.Document,
        file_id: str,
        chunk_size: int = 100,
        overlap_size: int = 20,
    ):

        if hasattr(file_content, "to_json"):
            articles, issues = self.convert_pdf_to_articles(
                file_content=file_content,
                file_id=file_id,
            )

            if issues:
                logger.warning("Missing article text for %s: %s", file_id, issues)

            chunks = []

            for article in articles:
                article_metadata = {
                    key: value
                    for key, value in article.items()
                    if key not in ("text_ar", "text_en")
                }

                for language in ("ar", "en"):
                    article_text = article[f"text_{language}"].strip()

                    if not article_text:
                        continue

                    chunks.append(
                        Document(
                            page_content=article_text,
                            metadata={
                                **article_metadata,
                                "source": file_id,
                                "language": language,
                                "chunk_index": 0,
                                "chunk_key": (
                                    f"egyptian-civil-code:"
                                    f"{article['article_number']}:{language}"
                                ),
                            },
                        )
                    )

            return chunks

        # text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap_size
        #                                                , length_function = len)

        file_content_texts = [
            record.page_content for record in file_content
        ]  # extracting texts
        file_content_metadata = [
            record.metadata for record in file_content
        ]  # extracting meta-data
        # splitting  content and putting each texts with its meta data .

        # chunks = text_splitter.create_documents(file_content_texts, metadatas=file_content_metadata)

        chunks = self.process_simple_splitter(
            texts=file_content_texts,
            metadatas=file_content_metadata,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
        )

        return chunks

    def process_simple_splitter(
        self,
        texts: List[str],
        metadatas: List[dict],
        chunk_size: int = 100,
        splitter_tag: str = "\n",
        overlap_size: int = 0,
    ):
        if len(texts) != len(metadatas):
            raise ValueError("Each text must have matching metadata")
        if chunk_size < 1 or not 0 <= overlap_size < chunk_size:
            raise ValueError("Require chunk_size > overlap_size >= 0")
        if not splitter_tag:
            raise ValueError("splitter_tag must not be empty")
        chunks = []
        for text, metadata in zip(texts, metadatas):
            content = splitter_tag.join(
                part.strip() for part in text.split(splitter_tag) if part.strip()
            )
            start = 0
            chunk_index = 0
            while start < len(content):
                end = min(start + chunk_size, len(content))
                chunk_text = content[start:end]
                if chunk_text.strip():
                    chunks.append(
                        Document(
                            page_content=chunk_text,
                            metadata={**metadata, "chunk_index": chunk_index},
                        )
                    )
                    chunk_index += 1
                if end == len(content):
                    break
                start = end - overlap_size
        return chunks
