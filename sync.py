"""Live sync runner — pull from one or many sources into SQLite + FAISS.

Usage:
    uv run python sync.py                    # sync every source in sources.yaml
    uv run python sync.py --project apollo   # override the project tag for this run
    uv run python sync.py --config my.yaml   # use a different config file

If no sources.yaml exists, falls back to a single Discord channel from .env
(DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID) so the simplest setup still works.

Secrets (tokens, passwords) live in .env. sources.yaml holds only non-secret
identity: which channels / mailboxes / forums to pull. Each source is tracked by
its own source_id cursor, so adding a source never re-pulls or clobbers others.

This hits the network. It is the real-world counterpart to the offline pytest suite.
"""
import argparse
import os
import sys
import time

import requests

from core import store
from ingest.pipeline import sync_all, sync_source

# Maps a config "type" to its connector class. Import lazily-friendly at module load;
# these are cheap (no network, no model) so top-level import is fine.
from core.connectors.discord import DiscordConnector
from core.connectors.email import EmailConnector
from core.connectors.forum import ForumConnector
from core.connectors.mattermost import MattermostConnector

DISCORD_API = "https://discord.com/api/v10"

CONNECTOR_TYPES = {
    "discord": DiscordConnector,
    "email": EmailConnector,
    "forum": ForumConnector,
    "mattermost": MattermostConnector,
}


def _discord_get(path, token):
    """GET a Discord API path with the bot token, retrying once on rate-limit."""
    url = f"{DISCORD_API}{path}"
    headers = {"Authorization": f"Bot {token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 429:
        time.sleep(float(resp.json().get("retry_after", 1)) + 0.25)
        resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def discover_discord_connectors(token):
    """Build a DiscordConnector for every text channel in every server the bot is in.

    Enumerates GET /users/@me/guilds -> GET /guilds/{id}/channels (type 0 = text).
    Channels the bot cannot see are simply absent from the API response, so they're
    silently skipped — auto-discovery can miss data it lacks permission to read.
    """
    connectors = []
    guilds = _discord_get("/users/@me/guilds", token)
    print(f"Discovered {len(guilds)} server(s) the bot can see.")
    for guild in guilds:
        gname = guild.get("name", guild["id"])
        try:
            channels = _discord_get(f"/guilds/{guild['id']}/channels", token)
        except requests.HTTPError as e:
            print(f"  ! {gname}: cannot list channels ({e.response.status_code}) — skipped")
            continue
        text_channels = [c for c in channels if c.get("type") == 0]
        print(f"  {gname}: {len(text_channels)} text channel(s)")
        for c in text_channels:
            # channel_id makes the source_id unique and globally distinct across servers.
            connectors.append(DiscordConnector(channel=c["name"], channel_id=c["id"]))
    return connectors


def build_connector(spec: dict):
    """Turn one sources.yaml entry into a connector instance.

    `type` selects the class; the remaining keys are passed as kwargs. Secrets are
    NOT here — connectors read those from env in their fetch()."""
    spec = dict(spec)  # copy so we can pop
    ctype = spec.pop("type", None)
    if ctype not in CONNECTOR_TYPES:
        raise ValueError(
            f"Unknown source type: {ctype!r}. "
            f"Valid types: {', '.join(sorted(CONNECTOR_TYPES))}"
        )
    return CONNECTOR_TYPES[ctype](**spec)


def load_config(path: str):
    """Load sources.yaml -> (project, [connectors]). Returns (None, None) if absent."""
    if not os.path.exists(path):
        return None, None
    import yaml  # PyYAML is already available via dependencies

    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    raw_sources = cfg.get("sources", [])
    if not raw_sources:
        raise ValueError(f"{path} has no 'sources:' list.")

    connectors = [build_connector(s) for s in raw_sources]
    return cfg.get("project"), connectors


def print_summary(results: dict):
    """Pretty-print the {source_id: summary} dict from sync_all."""
    print("\nSync results:")
    total_new = 0
    for source_id, summary in results.items():
        if "error" in summary:
            print(f"  ✗ {source_id}: ERROR — {summary['error']}")
        else:
            total_new += summary["new"]
            print(f"  ✓ {source_id}: received {summary['received']}, "
                  f"new {summary['new']}, embedded {summary['embedded']}")
    print(f"\nTotal new messages ingested: {total_new}")
    if total_new > 0:
        print("Ready to query:  uv run python query.py")
    else:
        print("Nothing new — everything was already ingested, or sources are empty.")


def main():
    parser = argparse.ArgumentParser(description="Sync sources into Punch.io")
    parser.add_argument("--project", default=None,
                        help="Project tag for ingested messages (overrides config)")
    parser.add_argument("--config", default="sources.yaml",
                        help="Path to the sources config (default: sources.yaml)")
    parser.add_argument("--channel", default="general",
                        help="Channel label for the .env single-Discord fallback")
    parser.add_argument("--all", action="store_true",
                        help="Auto-discover and sync EVERY text channel in EVERY Discord "
                             "server the bot is in (ignores sources.yaml)")
    args = parser.parse_args()

    store.init_db()  # idempotent

    # --all: auto-discover every Discord channel across every server the bot can see.
    if args.all:
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            sys.exit("Missing DISCORD_BOT_TOKEN in .env — required for --all discovery.")
        print("Auto-discovering Discord servers and channels...")
        try:
            connectors = discover_discord_connectors(token)
        except requests.HTTPError as e:
            sys.exit(f"Discovery failed: {e.response.status_code} {e.response.text}")
        if not connectors:
            sys.exit("No text channels discovered (bot not in any server, or no access).")
        project = args.project
        print(f"\nSyncing {len(connectors)} discovered channel(s) (project: {project})...")
        results = sync_all(connectors, project=project)
        print_summary(results)
        return

    cfg_project, connectors = load_config(args.config)

    if connectors is None:
        # No config file: fall back to the original single-Discord-from-.env flow.
        print(f"No {args.config} found — falling back to single Discord channel from .env.")
        connector = DiscordConnector(channel=args.channel)
        project = args.project
        print(f"Syncing Discord (channel label: {args.channel}, project: {project})...")
        try:
            summary = sync_source(connector, project=project)
        except ValueError as e:
            print(f"\nConfig error: {e}")
            print("Create a .env with DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID, "
                  f"or create {args.config} (see sources.yaml.example).")
            sys.exit(1)
        print_summary({connector.source_id: summary})
        return

    # Config-driven multi-source path.
    project = args.project or cfg_project
    print(f"Syncing {len(connectors)} source(s) from {args.config} "
          f"(project: {project})...")
    for c in connectors:
        print(f"  - {c.source_id}")

    # sync_all isolates per-source failures, so one bad source won't stop the rest.
    results = sync_all(connectors, project=project)
    print_summary(results)


if __name__ == "__main__":
    main()
