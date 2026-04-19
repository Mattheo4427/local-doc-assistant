from __future__ import annotations

from typing import Iterable, List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from llm import get_chat_llm


def _invoke_llm(prompt: str, model_name: str) -> str:
    llm = get_chat_llm(model_name=model_name)
    response = llm.invoke(prompt)
    if isinstance(response, AIMessage):
        return str(response.content).strip()
    return str(response).strip()


def summarize_document(
    doc: Document,
    model_name: str = "mistral",
    chunk_size: int = 1200,
    chunk_overlap: int = 100,
) -> str:
    """Summarize one full document using map-reduce style chunk summarization."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_text(doc.page_content)
    if not chunks:
        return "No content to summarize."

    partial_summaries: List[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        prompt = (
            "Summarize the following text chunk in 3 to 5 concise bullet points. "
            "Focus on key facts and avoid repetition.\n\n"
            f"Chunk {idx}:\n{chunk}\n"
        )
        partial_summaries.append(_invoke_llm(prompt=prompt, model_name=model_name))

    merge_prompt = (
        "You are combining chunk summaries into one final summary. "
        "Provide: 1) a short paragraph overview, 2) 5 bullet key takeaways.\n\n"
        "Chunk summaries:\n"
        + "\n\n".join(partial_summaries)
    )

    return _invoke_llm(prompt=merge_prompt, model_name=model_name)


def summarize_documents(
    documents: Iterable[Document],
    model_name: str = "mistral",
) -> List[str]:
    """Summarize multiple documents and return one summary per document."""
    results: List[str] = []
    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        summary = summarize_document(doc=doc, model_name=model_name)
        results.append(f"Source: {source}\n{summary}")
    return results
