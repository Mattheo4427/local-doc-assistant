from __future__ import annotations

from typing import List

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from llm import get_chat_llm


def _build_context(docs: List[Document], max_context_chars: int = 3500) -> str:
    """Create a bounded context string from retrieved chunks."""
    sections: List[str] = []
    total_chars = 0

    for idx, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page")
        page_note = f", page {page + 1}" if isinstance(page, int) else ""
        section = f"[Chunk {idx} | source: {source}{page_note}]\n{doc.page_content.strip()}"

        if total_chars + len(section) > max_context_chars:
            break

        sections.append(section)
        total_chars += len(section)

    return "\n\n".join(sections)


def answer_with_rag(
    vectorstore: Chroma,
    question: str,
    model_name: str = "mistral",
    top_k: int = 3,
) -> str:
    """Answer a user question using retrieval-augmented generation."""
    llm = get_chat_llm(model_name=model_name)
    docs = vectorstore.similarity_search(query=question, k=top_k)
    context = _build_context(docs)

    prompt = (
        "You are a document assistant. Answer only from the provided context. "
        "If the answer is not in context, say you do not have enough information. "
        "Keep the response clear and concise.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n"
        "Answer:"
    )

    response = llm.invoke(prompt)
    if isinstance(response, AIMessage):
        return str(response.content)
    return str(response)


def chat_loop(
    vectorstore: Chroma,
    model_name: str = "mistral",
    top_k: int = 3,
) -> None:
    """Interactive chat session for RAG question answering."""
    print("Chat mode started. Type 'exit' to quit.")

    while True:
        question = input("\nYou: ").strip()
        if question.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not question:
            continue

        answer = answer_with_rag(
            vectorstore=vectorstore,
            question=question,
            model_name=model_name,
            top_k=top_k,
        )
        print(f"\nAssistant: {answer}")
