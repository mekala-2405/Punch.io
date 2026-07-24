"""Query runner — ask the LLM a question against ingested data.

Usage:
    uv run python query.py "what is blocking the deployment?"   # one-shot
    uv run python query.py                                       # interactive loop

Requires GROQ_API_KEY in .env and a FAISS index built by sync.py (data/faiss_db/).
This is the read side of the loop: sync.py ingests, query.py answers.
"""
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "faiss_db", "index.faiss")


def _check_ready():
    if not os.path.exists(DB_PATH):
        print("No FAISS index found at data/faiss_db/.")
        print("Run  uv run python sync.py  first to ingest some messages.")
        sys.exit(1)


def answer_once(question: str):
    # Imported lazily so the index/creds are only required when actually querying.
    from generation import ask_question, retrieve_context

    docs, _ = retrieve_context(question)
    answer = ask_question(question)

    print("\nAnswer:")
    print(answer)
    print("\n--- sources ---")
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        author = meta.get("author", "Unknown")
        ts = (meta.get("timestamp") or "")[:10]
        print(f"  {i}. [{author}] {ts}: {doc.page_content[:80]}")


def main():
    _check_ready()

    if len(sys.argv) > 1:
        answer_once(" ".join(sys.argv[1:]))
        return

    print("Punch.io query — ask about the project. Type 'quit' to exit.")
    while True:
        try:
            q = input("\nQuestion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in {"quit", "exit", "q"}:
            break
        if not q:
            continue
        answer_once(q)


if __name__ == "__main__":
    main()
