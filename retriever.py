from __future__ import annotations

from typing import List, Tuple

from langchain_chroma import Chroma
from langchain_core.documents import Document


def get_retriever(vectorstore: Chroma, k: int = 3):
    """Create a similarity retriever with configurable top-k."""
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": k})


def semantic_search(
    vectorstore: Chroma,
    query: str,
    k: int = 5,
) -> List[Tuple[Document, float]]:
    """Run semantic search and return chunks with relevance scores."""
    return vectorstore.similarity_search_with_relevance_scores(query=query, k=k)
