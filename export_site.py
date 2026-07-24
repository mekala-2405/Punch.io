"""Export a static snapshot for the frontend: raw data + LLM-extracted timeline.

Writes JSON into frontend/public/data/ so the React app can ship with no backend.

Run:  uv run python export_site.py [--project apollo]
"""
import argparse
import json
import os
import re
from datetime import datetime

from core import store

OUT_DIR = os.path.join(os.path.dirname(__file__), "frontend", "public", "data")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "punch.db")

EVENT_TYPES = {"decision", "milestone", "blocker", "resolution"}

def _extract_system() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M %Z")
    return f"""Today is {now}. You analyze a project team's chat log and extract the timeline of \
what actually happened. Output ONLY events that matter to a project manager: decisions \
made, milestones reached, blockers raised, and blockers resolved. Ignore routine chatter.

Return a JSON array. Each event is an object:
{{"date": "YYYY-MM-DD", "type": "decision|milestone|blocker|resolution",
 "summary": "one concise sentence", "channel": "<channel>"}}

Rules:
- type MUST be exactly one of: decision, milestone, blocker, resolution.
- date MUST be the message's date (given per line).
- summary is one sentence, concrete, no fluff.
- A "resolution" resolves an earlier "blocker".
- Output the JSON array and NOTHING else. No markdown fences, no prose."""


def _messages_block(messages) -> str:
    lines = []
    for m in messages:
        date = (m.timestamp or "")[:10]
        lines.append(f"{date} | {m.channel} | {m.author}: {m.content}")
    return "\n".join(lines)


def _parse_events(raw_text: str) -> list[dict]:
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        return []
    try:
        events = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    clean = []
    for e in events:
        if not isinstance(e, dict):
            continue
        if e.get("type") not in EVENT_TYPES:
            continue
        if not e.get("date") or not e.get("summary"):
            continue
        clean.append({
            "date": str(e["date"])[:10],
            "type": e["type"],
            "summary": str(e["summary"]),
            "channel": str(e.get("channel", "")),
        })
    clean.sort(key=lambda e: e["date"])
    return clean


def extract_timeline(messages) -> list[dict]:
    """One LLM call: messages -> structured project events."""
    from langchain_core.messages import SystemMessage, HumanMessage
    from generation.llm import get_llm
    resp = get_llm().invoke([
        SystemMessage(content=_extract_system()),
        HumanMessage(content=f"Project chat log:\n\n{_messages_block(messages)}"),
    ])
    return _parse_events(resp.content)


def message_to_dict(m) -> dict:
    return {
        "external_id": m.external_id,
        "source": m.source,
        "channel": m.channel,
        "author": m.author,
        "timestamp": m.timestamp,
        "content": m.content,
        "project": m.project,
    }


def main():
    parser = argparse.ArgumentParser(description="Export static site data")
    parser.add_argument("--project", default=None,
                        help="Only export this project (default: everything)")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        raise SystemExit("No data/punch.db — run sync.py first.")

    messages = store.get_messages(db_path=DB_PATH, project=args.project)
    if not messages:
        raise SystemExit("No messages to export.")

    os.makedirs(OUT_DIR, exist_ok=True)

    msg_dicts = [message_to_dict(m) for m in messages]
    with open(os.path.join(OUT_DIR, "messages.json"), "w", encoding="utf-8") as f:
        json.dump(msg_dicts, f, ensure_ascii=False, indent=2)

    channels = sorted({m.channel for m in messages})
    projects = sorted({m.project for m in messages if m.project})
    meta = {
        "message_count": len(messages),
        "channels": channels,
        "projects": projects,
        "date_range": [messages[0].timestamp[:10], messages[-1].timestamp[:10]],
    }
    with open(os.path.join(OUT_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    events = extract_timeline(messages)
    with open(os.path.join(OUT_DIR, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {OUT_DIR}/  (messages, meta, timeline)")


if __name__ == "__main__":
    main()
