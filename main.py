from __future__ import annotations

import argparse
from pathlib import Path

from embeddings import get_vectorstore, has_persisted_index, index_documents
from features.chat import answer_with_rag, chat_loop
from features.summary import summarize_documents
from ingestion import load_documents_from_folder, merge_documents_by_source, split_documents
from retriever import semantic_search


def cmd_ingest(args: argparse.Namespace) -> None:
    docs = load_documents_from_folder(args.docs_dir)
    if not docs:
        print(f"No supported files found in: {args.docs_dir}")
        return

    chunks = split_documents(
        documents=docs,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    index_documents(
        chunks=chunks,
        persist_directory=args.persist_dir,
        collection_name=args.collection,
        embedding_model_name=args.embedding_model,
        reset=args.reset,
    )

    print(f"Indexed {len(docs)} documents into {len(chunks)} chunks.")
    print(f"Persisted Chroma DB at: {args.persist_dir}")


def _require_index_or_exit(persist_dir: str) -> bool:
    if has_persisted_index(persist_dir):
        return True

    print("No persisted index found. Run ingestion first, for example:")
    print("python main.py ingest --docs-dir ./docs")
    return False


def cmd_chat(args: argparse.Namespace) -> None:
    if not _require_index_or_exit(args.persist_dir):
        return

    vectorstore = get_vectorstore(
        persist_directory=args.persist_dir,
        collection_name=args.collection,
        embedding_model_name=args.embedding_model,
    )

    if args.question:
        answer = answer_with_rag(
            vectorstore=vectorstore,
            question=args.question,
            model_name=args.model,
            top_k=args.k,
        )
        print(answer)
        return

    chat_loop(vectorstore=vectorstore, model_name=args.model, top_k=args.k)


def cmd_search(args: argparse.Namespace) -> None:
    if not _require_index_or_exit(args.persist_dir):
        return

    vectorstore = get_vectorstore(
        persist_directory=args.persist_dir,
        collection_name=args.collection,
        embedding_model_name=args.embedding_model,
    )
    results = semantic_search(vectorstore=vectorstore, query=args.query, k=args.k)

    if not results:
        print("No matching chunks found.")
        return

    for idx, (doc, score) in enumerate(results, start=1):
        source = doc.metadata.get("source", "unknown")
        snippet = doc.page_content.strip().replace("\n", " ")
        snippet = snippet[:300] + ("..." if len(snippet) > 300 else "")

        print(f"\nResult #{idx}")
        print(f"Score: {score:.4f}")
        print(f"Source: {source}")
        print(f"Text: {snippet}")


def cmd_summary(args: argparse.Namespace) -> None:
    folder = Path(args.docs_dir)
    if not folder.exists():
        print(f"Folder not found: {folder}")
        return

    docs = merge_documents_by_source(load_documents_from_folder(folder))
    if args.file:
        target = Path(args.file).resolve().as_posix()
        docs = [d for d in docs if Path(d.metadata.get("source", "")).resolve().as_posix() == target]

    if not docs:
        print("No documents found to summarize.")
        return

    summaries = summarize_documents(documents=docs, model_name=args.model)
    for i, summary in enumerate(summaries, start=1):
        print(f"\n=== Summary #{i} ===")
        print(summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local Document Assistant - chat, search, and summarize your documents"
    )

    parser.add_argument("--persist-dir", default="data/chroma", help="Path to persisted Chroma DB")
    parser.add_argument("--collection", default="documents", help="Chroma collection name")
    parser.add_argument("--embedding-model", default="nomic-embed-text", help="Ollama embedding model")
    parser.add_argument("--model", default="mistral", help="Ollama chat model")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_ingest = subparsers.add_parser("ingest", help="Load and index documents")
    p_ingest.add_argument("--docs-dir", default="docs", help="Folder containing source documents")
    p_ingest.add_argument("--chunk-size", type=int, default=500, help="Chunk size")
    p_ingest.add_argument("--chunk-overlap", type=int, default=50, help="Chunk overlap")
    p_ingest.add_argument("--reset", action="store_true", help="Delete existing index before indexing")
    p_ingest.set_defaults(func=cmd_ingest)

    p_chat = subparsers.add_parser("chat", help="Chat with indexed documents")
    p_chat.add_argument("--k", type=int, default=3, help="Top-k retrieved chunks")
    p_chat.add_argument("--question", default=None, help="Optional one-shot question")
    p_chat.set_defaults(func=cmd_chat)

    p_search = subparsers.add_parser("search", help="Semantic search over indexed chunks")
    p_search.add_argument("--query", required=True, help="Search query")
    p_search.add_argument("--k", type=int, default=5, help="Top-k results")
    p_search.set_defaults(func=cmd_search)

    p_summary = subparsers.add_parser("summary", help="Summarize documents from folder")
    p_summary.add_argument("--docs-dir", default="docs", help="Folder containing source documents")
    p_summary.add_argument("--file", default=None, help="Optional single file path to summarize")
    p_summary.set_defaults(func=cmd_summary)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
