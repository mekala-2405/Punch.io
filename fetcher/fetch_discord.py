import os
import json
import requests
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

def _get_credentials():
    """Get Discord credentials from environment."""
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    return bot_token, channel_id

def fetch_messages(channel_id: str, bot_token: str, limit: int = 100) -> list:
    """Fetch messages from a Discord channel."""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={limit}"
    headers = {
        "Authorization": f"Bot {bot_token}"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch messages: {response.status_code} - {response.text}")
        
    return response.json()

def fetch_and_save_discord_messages(channel_id: str = None, bot_token: str = None, output_dir: str = "data") -> int:
    """
    Fetch messages from Discord and save to JSON.
    
    Args:
        channel_id: Discord channel ID (uses env var if not provided)
        bot_token: Discord bot token (uses env var if not provided)
        output_dir: Directory to save the JSON file
        
    Returns:
        Number of messages saved
    """
    # Use environment variables if not provided
    if not bot_token or not channel_id:
        env_token, env_channel = _get_credentials()
        bot_token = bot_token or env_token
        channel_id = channel_id or env_channel
    
    if not bot_token or not channel_id:
        raise ValueError("Missing DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID")
    
    # Fetch messages
    raw_messages = fetch_messages(channel_id, bot_token)
    
    if not raw_messages:
        return 0

    # Discord returns newest messages first, so we reverse them for chronological order
    raw_messages.reverse()
    
    formatted_data = []
    for msg in raw_messages:
        # Skip empty messages
        if not msg.get("content"):
            continue
            
        # Extract author name safely
        author_name = msg.get("author", {}).get("username", "Unknown")
        
        # Add the message to our list
        formatted_data.append({
            "timestamp": msg["timestamp"],
            "author": author_name,
            "source": "Discord #general",
            "content": msg["content"]
        })
        
    # Ensure data directory exists
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "discord_chat.json")
    
    # Save the data to the JSON file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        
    return len(formatted_data)

def main():
    """CLI entry point."""
    bot_token, channel_id = _get_credentials()
    
    if not bot_token or not channel_id:
        raise ValueError("Missing DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID in .env file")
    
    print(f"Fetching messages from Discord Channel: {channel_id}...")
    
    try:
        count = fetch_and_save_discord_messages(channel_id, bot_token)
        print(f"Successfully saved {count} messages to data/discord_chat.json")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()