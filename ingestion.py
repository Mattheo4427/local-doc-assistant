from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


def iter_supported_files(folder_path: str | Path) -> Iterable[Path]:
    """Yield supported files recursively from a folder."""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def load_documents_from_folder(folder_path: str | Path) -> List[Document]:
    """Load PDF/TXT/MD files from a folder into LangChain documents."""
    documents: List[Document] = []

    for file_path in iter_supported_files(folder_path):
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            loader = PyPDFLoader(str(file_path))
            file_docs = loader.load()
        else:
            loader = TextLoader(str(file_path), encoding="utf-8")
            file_docs = loader.load()

        for doc in file_docs:
            doc.metadata["source"] = str(file_path)

        documents.extend(file_docs)

    return documents


def split_documents(
    documents: List[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[Document]:
    """Split documents into chunks for embedding and retrieval."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def merge_documents_by_source(documents: List[Document]) -> List[Document]:
    """Merge page-level or chunk-level docs back into full documents by source."""
    grouped: Dict[str, List[str]] = {}

    for doc in documents:
        source = str(doc.metadata.get("source", "unknown"))
        grouped.setdefault(source, []).append(doc.page_content)

    merged: List[Document] = []
    for source, contents in grouped.items():
        merged.append(Document(page_content="\n\n".join(contents), metadata={"source": source}))

    return merged
