from __future__ import annotations

from langchain_ollama import ChatOllama


def get_chat_llm(model_name: str = "mistral", temperature: float = 0.1) -> ChatOllama:
    """Create a local Ollama chat model."""
    return ChatOllama(model=model_name, temperature=temperature)
