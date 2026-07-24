"""Seed a Discord server with synthetic conversations for testing Punch.io.

Reads a JSON file of channels -> messages (with arbitrary usernames) and posts them
into a real Discord server YOU control. Uses per-channel webhooks so each message can
appear under its own username/avatar (a bot token alone cannot impersonate users).

JSON shape (generate this with any model):
{
  "channels": {
    "general":  [ {"user": "alice", "content": "kickoff is friday"},
                  {"user": "bob",   "content": "i'll prep the deck"} ],
    "backend":  [ {"user": "carol", "content": "db migration is blocking deploy"} ]
  }
}

Setup (.env in project root):
    DISCORD_BOT_TOKEN=...      # bot must be in the server with:
                              #   Manage Channels + Manage Webhooks
    DISCORD_GUILD_ID=...       # the server (guild) ID, or pass --guild

Run:
    uv run python seed_discord.py conversations.json
    uv run python seed_discord.py conversations.json --guild 123456789
"""
import argparse
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

API = "https://discord.com/api/v10"


def _bot_headers(token):
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


def _request(method, url, headers=None, **kwargs):
    """Thin wrapper that retries once on a 429 rate-limit."""
    resp = requests.request(method, url, headers=headers, **kwargs)
    if resp.status_code == 429:
        retry_after = resp.json().get("retry_after", 1)
        time.sleep(float(retry_after) + 0.25)
        resp = requests.request(method, url, headers=headers, **kwargs)
    return resp


def get_or_create_channel(guild_id, name, token, existing):
    """Return the channel id for `name`, creating a text channel if it doesn't exist."""
    if name in existing:
        return existing[name]

    resp = _request(
        "POST", f"{API}/guilds/{guild_id}/channels",
        headers=_bot_headers(token),
        json={"name": name, "type": 0},  # 0 = text channel
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create channel #{name}: {resp.status_code} {resp.text}")
    cid = resp.json()["id"]
    existing[name] = cid
    print(f"  created #{name}")
    return cid


def get_or_create_webhook(channel_id, token):
    """Return a webhook URL for the channel, reusing our seeding webhook if present."""
    hook_name = "punch-seed"
    resp = _request("GET", f"{API}/channels/{channel_id}/webhooks", headers=_bot_headers(token))
    resp.raise_for_status()
    for hook in resp.json():
        if hook.get("name") == hook_name:
            return f"{API}/webhooks/{hook['id']}/{hook['token']}"

    resp = _request(
        "POST", f"{API}/channels/{channel_id}/webhooks",
        headers=_bot_headers(token), json={"name": hook_name},
    )
    resp.raise_for_status()
    hook = resp.json()
    return f"{API}/webhooks/{hook['id']}/{hook['token']}"


def post_message(webhook_url, username, content):
    """Post one message under an arbitrary username via the webhook."""
    resp = _request("POST", webhook_url, headers={"Content-Type": "application/json"},
                    json={"username": username or "unknown", "content": content})
    # Webhook posts return 204 No Content on success.
    if resp.status_code not in (200, 204):
        print(f"    ! failed ({resp.status_code}): {content[:50]}")
        return False
    return True


def list_existing_channels(guild_id, token):
    resp = _request("GET", f"{API}/guilds/{guild_id}/channels", headers=_bot_headers(token))
    resp.raise_for_status()
    return {c["name"]: c["id"] for c in resp.json() if c["type"] == 0}


def write_sources_yaml(channels, project, path="sources.yaml"):
    """Write a sources.yaml mapping each channel name -> its id. channels: {name: id}."""
    lines = [f"project: {project}", "", "sources:"]
    for name, cid in channels.items():
        lines += [
            "  - type: discord",
            f"    channel: {name}",
            f'    channel_id: "{cid}"',
        ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Seed a Discord server with synthetic chats")
    parser.add_argument("json_file", nargs="?",
                        help="Path to the conversations JSON (omit when using --list)")
    parser.add_argument("--guild", default=os.getenv("DISCORD_GUILD_ID"),
                        help="Guild (server) ID; defaults to DISCORD_GUILD_ID in .env")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="Seconds between messages (avoid rate limits); default 0.4")
    parser.add_argument("--list", action="store_true",
                        help="List existing text channels (name + id) and exit")
    parser.add_argument("--write-config", metavar="PROJECT",
                        help="Write a sources.yaml for all existing channels, tagged with "
                             "this project name, then exit")
    args = parser.parse_args()

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        sys.exit("Missing DISCORD_BOT_TOKEN in .env")
    if not args.guild:
        sys.exit("Missing guild id — set DISCORD_GUILD_ID in .env or pass --guild")

    # --list / --write-config: work with channels that already exist, no seeding.
    if args.list or args.write_config:
        existing = list_existing_channels(args.guild, token)
        if not existing:
            sys.exit("No text channels found (or the bot can't see them).")
        print(f"Text channels in guild {args.guild}:")
        for name, cid in existing.items():
            print(f"  #{name:<20} {cid}")
        if args.write_config:
            write_sources_yaml(existing, args.write_config)
            print(f"\nWrote sources.yaml ({len(existing)} channels, project="
                  f"{args.write_config!r}). Now run:  uv run python sync.py")
        return

    if not args.json_file:
        sys.exit("Provide a conversations JSON file, or use --list / --write-config.")

    with open(args.json_file, encoding="utf-8") as f:
        data = json.load(f)

    channels = data.get("channels", {})
    if not channels:
        sys.exit("JSON has no 'channels' object with messages.")

    existing = list_existing_channels(args.guild, token)
    total = 0

    for chan_name, messages in channels.items():
        print(f"#{chan_name}: {len(messages)} messages")
        channel_id = get_or_create_channel(args.guild, chan_name, token, existing)
        webhook_url = get_or_create_webhook(channel_id, token)

        for msg in messages:
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if post_message(webhook_url, msg.get("user"), content):
                total += 1
            time.sleep(args.delay)

    print(f"\nDone. Posted {total} messages across {len(channels)} channel(s).")
    print("Now sync them:  uv run python sync.py")


if __name__ == "__main__":
    main()
