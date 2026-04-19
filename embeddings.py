from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings


def get_embedding_model(model_name: str = "nomic-embed-text") -> OllamaEmbeddings:
    """Create a local Ollama embedding model."""
    return OllamaEmbeddings(model=model_name)


def get_vectorstore(
    persist_directory: str = "data/chroma",
    collection_name: str = "documents",
    embedding_model_name: str = "nomic-embed-text",
) -> Chroma:
    """Load a persistent Chroma vector store."""
    embeddings = get_embedding_model(embedding_model_name)
    return Chroma(
        collection_name=collection_name,
        persist_directory=persist_directory,
        embedding_function=embeddings,
    )


def index_documents(
    chunks: List[Document],
    persist_directory: str = "data/chroma",
    collection_name: str = "documents",
    embedding_model_name: str = "nomic-embed-text",
    reset: bool = False,
) -> Chroma:
    """Embed chunks and store them in a persistent Chroma index."""
    persist_path = Path(persist_directory)
    if reset and persist_path.exists():
        shutil.rmtree(persist_path)

    embeddings = get_embedding_model(embedding_model_name)
    return Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory,
        collection_name=collection_name,
    )


def has_persisted_index(persist_directory: str = "data/chroma") -> bool:
    """Check whether Chroma persistence files are present."""
    persist_path = Path(persist_directory)
    return persist_path.exists() and any(persist_path.iterdir())
