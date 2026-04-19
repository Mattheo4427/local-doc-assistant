from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.error import URLError
from urllib.request import urlopen

import streamlit as st

from embeddings import get_vectorstore, has_persisted_index, index_documents
from features.chat import answer_with_rag
from features.summary import summarize_documents
from ingestion import load_documents_from_folder, merge_documents_by_source, split_documents
from retriever import semantic_search


st.set_page_config(page_title="Local Document Assistant", page_icon="DI", layout="wide")
CUSTOM_MODEL_OPTION = "Custom..."

DEFAULT_PERSIST_DIR = "data/chroma"
DEFAULT_COLLECTION = "documents"
DEFAULT_CHAT_MODEL = "mistral"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_DOCS_DIR = Path("docs")

QUALITY_PRESETS: Dict[str, Dict[str, int]] = {
    "Fast": {"top_k": 3, "chunk_size": 500, "chunk_overlap": 50},
    "Balanced": {"top_k": 4, "chunk_size": 650, "chunk_overlap": 60},
    "Deep": {"top_k": 5, "chunk_size": 800, "chunk_overlap": 80},
}


@dataclass
class UIConfig:
    persist_dir: str
    collection: str
    model_name: str
    embedding_model: str
    quality: str


@st.cache_data(ttl=10, show_spinner=False)
def get_installed_ollama_models() -> List[str]:
    """Return locally installed Ollama model names from /api/tags."""
    url = "http://127.0.0.1:11434/api/tags"
    try:
        with urlopen(url, timeout=2) as response:
            data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError):
        return []

    models = [
        model.get("name", "")
        for model in data.get("models", [])
        if isinstance(model, dict) and model.get("name")
    ]
    return sorted(set(models))


@st.cache_data(ttl=1800, show_spinner=False)
def get_ollama_library_models() -> List[str]:
    """Fetch available model names from Ollama library page."""
    try:
        with urlopen("https://ollama.com/library", timeout=4) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except (URLError, TimeoutError, ValueError):
        return []

    matches = re.findall(r'href="/library/([a-zA-Z0-9._:-]+)"', html)
    cleaned = [m.strip() for m in matches if m and m.strip().lower() != "library"]
    return sorted(set(cleaned))


def choose_model(label: str, default_model: str, key_prefix: str) -> str:
    """Select an installed model or provide a custom model name."""
    installed = get_installed_ollama_models()
    options = [CUSTOM_MODEL_OPTION] + installed if installed else [CUSTOM_MODEL_OPTION]

    default_selection = default_model if default_model in installed else CUSTOM_MODEL_OPTION
    selected = st.selectbox(
        label,
        options=options,
        index=options.index(default_selection),
        key=f"{key_prefix}_select",
    )

    if selected == CUSTOM_MODEL_OPTION:
        return st.text_input(
            f"{label} (custom)",
            value=default_model,
            key=f"{key_prefix}_custom",
        ).strip()

    return selected.strip()


def ensure_docs_dir(path: Path = DEFAULT_DOCS_DIR) -> None:
    path.mkdir(parents=True, exist_ok=True)


def upload_documents(files: List[Any], docs_dir: Path = DEFAULT_DOCS_DIR) -> Tuple[int, List[str]]:
    ensure_docs_dir(docs_dir)
    saved: List[str] = []

    for file in files:
        target = docs_dir / Path(file.name).name
        target.write_bytes(file.getbuffer())
        saved.append(target.name)

    return len(saved), saved


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                font-family: "IBM Plex Sans", "Ubuntu", "Noto Sans", sans-serif;
                background:
                    radial-gradient(circle at 8% 8%, #f7ffe8 0%, transparent 35%),
                    radial-gradient(circle at 95% 0%, #e8f4ff 0%, transparent 35%),
                    linear-gradient(120deg, #f9f6ef 0%, #eff7ff 100%);
            }
            .top-title {
                font-size: 1.85rem;
                font-weight: 700;
                letter-spacing: 0.02em;
                color: #1f2a37;
                margin-bottom: 0.15rem;
            }
            .top-subtitle {
                color: #4b5563;
                margin-bottom: 1rem;
            }
            .status-card {
                background: rgba(255, 255, 255, 0.72);
                border: 1px solid #d8e0ea;
                border-radius: 12px;
                padding: 0.8rem;
                margin-bottom: 0.7rem;
            }
            .result-card {
                background: #ffffffcc;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 0.8rem;
                margin-bottom: 0.7rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def load_vectorstore(persist_dir: str, collection: str, embedding_model: str):
    return get_vectorstore(
        persist_directory=persist_dir,
        collection_name=collection,
        embedding_model_name=embedding_model,
    )


def run_ingestion(
    docs_dir: str | Path,
    persist_dir: str,
    collection: str,
    embedding_model: str,
    quality: str,
    reset: bool = False,
) -> str:
    preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["Balanced"])
    docs = load_documents_from_folder(docs_dir)
    if not docs:
        return f"No supported documents found in: {docs_dir}"

    chunks = split_documents(
        docs,
        chunk_size=preset["chunk_size"],
        chunk_overlap=preset["chunk_overlap"],
    )
    index_documents(
        chunks=chunks,
        persist_directory=persist_dir,
        collection_name=collection,
        embedding_model_name=embedding_model,
        reset=reset,
    )

    load_vectorstore.clear()
    return (
        f"Indexed {len(docs)} documents as {len(chunks)} chunks "
        f"using {quality} quality profile."
    )


def pull_model_with_logs(model_name: str, output_box, log_box) -> bool:
    """Run `ollama pull` and stream logs into the UI."""
    safe_name = model_name.strip()
    if not safe_name:
        output_box.error("Enter a model name to download.")
        return False

    output_box.info(f"Downloading model: {safe_name}")

    try:
        process = subprocess.Popen(
            ["ollama", "pull", safe_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        output_box.error("Ollama CLI not found. Install Ollama first.")
        return False

    lines: List[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        lines.append(line.rstrip())
        log_box.code("\n".join(lines[-20:]), language="text")

    return_code = process.wait()
    if return_code == 0:
        output_box.success(f"Model '{safe_name}' downloaded.")
        get_installed_ollama_models.clear()
        return True

    output_box.error(f"Download failed for '{safe_name}'.")
    return False


def render_chat_mode(
    persist_dir: str,
    collection: str,
    embedding_model: str,
    model_name: str,
    quality: str,
) -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Message your documents")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})

    if not has_persisted_index(persist_dir):
        answer = "No index yet. Import docs from sidebar and click Build knowledge base."
    else:
        with st.spinner("Thinking..."):
            vectorstore = load_vectorstore(persist_dir, collection, embedding_model)
            answer = answer_with_rag(
                vectorstore=vectorstore,
                question=prompt,
                model_name=model_name,
                top_k=QUALITY_PRESETS[quality]["top_k"],
            )

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()


def render_search_mode(persist_dir: str, collection: str, embedding_model: str, quality: str) -> None:
    st.subheader("Semantic Search")
    query = st.text_input("Search your knowledge base", placeholder="Find sections about risk and mitigations")
    if st.button("Search", use_container_width=False):
        if not query.strip():
            st.warning("Type a search query first.")
            return

        if not has_persisted_index(persist_dir):
            st.warning("No index yet. Build your knowledge base first.")
            return

        vectorstore = load_vectorstore(persist_dir, collection, embedding_model)
        with st.spinner("Searching..."):
            results = semantic_search(vectorstore, query=query, k=QUALITY_PRESETS[quality]["top_k"])

        if not results:
            st.info("No matching chunks found.")
            return

        for idx, (doc, score) in enumerate(results, start=1):
            source = doc.metadata.get("source", "unknown")
            snippet = doc.page_content.strip().replace("\n", " ")
            snippet = snippet[:460] + ("..." if len(snippet) > 460 else "")
            st.markdown(
                (
                    f"<div class='result-card'><b>Result {idx}</b><br>"
                    f"Relevance: {score:.4f}<br>"
                    f"Source: {source}<br><br>{snippet}</div>"
                ),
                unsafe_allow_html=True,
            )


def render_summary_mode(model_name: str, docs_dir: Path) -> None:
    st.subheader("Document Summaries")

    docs = []
    if docs_dir.exists():
        docs = merge_documents_by_source(load_documents_from_folder(docs_dir))

    sources = [Path(d.metadata.get("source", "unknown")).name for d in docs]
    source_to_doc = {Path(d.metadata.get("source", "unknown")).name: d for d in docs}

    selected = st.selectbox("Choose document", options=["All documents"] + sources)
    if st.button("Generate summary", use_container_width=False):
        if not docs:
            st.warning("No documents found. Upload documents from the sidebar first.")
            return

        target_docs = docs if selected == "All documents" else [source_to_doc[selected]]
        with st.spinner("Summarizing..."):
            summaries = summarize_documents(target_docs, model_name=model_name)

        for idx, summary in enumerate(summaries, start=1):
            st.markdown(f"### Summary {idx}")
            st.markdown(summary)


def render_quality_card(quality: str) -> None:
    preset = QUALITY_PRESETS[quality]
    st.markdown(
        (
            "<div class='status-card'>"
            f"Depth profile: <b>{quality}</b><br>"
            f"Retrieval breadth: {preset['top_k']} passages<br>"
            f"Chunking strategy: {preset['chunk_size']} / {preset['chunk_overlap']}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_import_section(config: UIConfig) -> None:
    st.divider()
    st.subheader("Import Documents")
    uploads = st.file_uploader(
        "Add personal documents",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
        help="Files are saved into the local docs folder.",
    )
    if st.button("Save uploads", use_container_width=True):
        if not uploads:
            st.warning("Select one or more files first.")
        else:
            count, names = upload_documents(uploads, DEFAULT_DOCS_DIR)
            st.success(f"Saved {count} file(s): {', '.join(names[:4])}{'...' if len(names) > 4 else ''}")

    if st.button("Build knowledge base", use_container_width=True):
        with st.spinner("Indexing documents..."):
            result = run_ingestion(
                docs_dir=DEFAULT_DOCS_DIR,
                persist_dir=config.persist_dir,
                collection=config.collection,
                embedding_model=config.embedding_model,
                quality=config.quality,
                reset=False,
            )
        st.success(result)


def render_model_hub_section(installed_models: List[str]) -> None:
    st.divider()
    st.subheader("Model Hub")
    catalog_query = st.text_input("Find model", value="")

    catalog = get_ollama_library_models()
    if st.button("Refresh model list", use_container_width=True):
        get_ollama_library_models.clear()
        get_installed_ollama_models.clear()
        st.rerun()

    if installed_models:
        st.caption(f"Installed: {len(installed_models)} model(s)")
    else:
        st.caption("Installed: none detected")

    filtered_catalog = catalog
    if catalog_query.strip():
        q = catalog_query.strip().lower()
        filtered_catalog = [m for m in catalog if q in m.lower()]

    if not filtered_catalog:
        filtered_catalog = installed_models

    selected_download_model = st.selectbox(
        "Available models",
        options=filtered_catalog[:500] if filtered_catalog else [DEFAULT_CHAT_MODEL],
        key="download_model_select",
    )

    if st.button("Download selected model", use_container_width=True):
        status = st.empty()
        logs = st.empty()
        pull_model_with_logs(selected_download_model, status, logs)

    st.caption("Download flow: select model -> click download -> watch live logs -> model appears in selectors")


def render_sidebar() -> UIConfig:
    with st.sidebar:
        st.header("Chat Setup")
        installed_models = get_installed_ollama_models()

        model_name = choose_model("Assistant model", default_model=DEFAULT_CHAT_MODEL, key_prefix="chat_model")
        embedding_model = choose_model(
            "Knowledge model",
            default_model=DEFAULT_EMBED_MODEL,
            key_prefix="embedding_model",
        )
        quality = st.select_slider("Answer depth", options=["Fast", "Balanced", "Deep"], value="Balanced")
        render_quality_card(quality)

        config = UIConfig(
            persist_dir=DEFAULT_PERSIST_DIR,
            collection=DEFAULT_COLLECTION,
            model_name=model_name,
            embedding_model=embedding_model,
            quality=quality,
        )

        render_import_section(config)
        render_model_hub_section(installed_models)

        if st.button("Clear chat history", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    return config


def main() -> None:
    inject_styles()

    ensure_docs_dir(DEFAULT_DOCS_DIR)
    if "selected_model_to_download" not in st.session_state:
        st.session_state.selected_model_to_download = ""

    st.markdown("<div class='top-title'>Local Document Assistant</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='top-subtitle'>Chat-first experience with local docs, local models, and one-click model downloads.</div>",
        unsafe_allow_html=True,
    )

    config = render_sidebar()

    mode = st.radio("Mode", options=["Chat", "Search", "Summary"], horizontal=True, label_visibility="collapsed")

    if mode == "Chat":
        render_chat_mode(
            config.persist_dir,
            config.collection,
            config.embedding_model,
            config.model_name,
            config.quality,
        )
    elif mode == "Search":
        render_search_mode(config.persist_dir, config.collection, config.embedding_model, config.quality)
    else:
        render_summary_mode(config.model_name, DEFAULT_DOCS_DIR)


if __name__ == "__main__":
    main()
