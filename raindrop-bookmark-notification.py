import time
import requests
import discord
import asyncio
from discord.ext import tasks
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import os

load_dotenv()

API_TOKEN = os.getenv('RAINDROP_API_TOKEN')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')

poll_interval = 10
raindrop_api_url = "https://api.raindrop.io/rest/v1/raindrops/0"
last_bookmark_file = "last_bookmark_id.txt"

def get_raindrop_bookmarks():
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
    }
    response = requests.get(raindrop_api_url, headers=headers)
    if response.status_code == 200:
        return response.json().get("items", [])
    else:
        print(f"Error fetching bookmarks: {response.status_code}")
        return []

def load_last_bookmark_id():
    try:
        with open(last_bookmark_file, "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        return None

def save_last_bookmark_id(bookmark_id):
    with open(last_bookmark_file, "w") as file:
        file.write(bookmark_id)

async def send_to_discord(bookmark, client):
    try:
        channel = client.get_channel(DISCORD_CHANNEL_ID)
        title = bookmark.get("title", "No title")
        link = bookmark.get("link", "No link")
        tags = ", ".join([tag for tag in bookmark.get("tags", [])]) if bookmark.get("tags") else "No tags"
        description = bookmark.get("excerpt", "No description")

        message = f"**New Bookmark Added!**\n\n**Title**: {title}\n**Link**: {link}\n**Tags**: {tags}\n**Description**: {description}"
        
        if channel:
            await channel.send(message)
        else:
            print(f"Error: Unable to find Discord channel with ID {DISCORD_CHANNEL_ID}")
    except Exception as e:
        print(f"Error sending message to Discord: {e}")

def send_to_slack(bookmark):
    try:
        slack_client = WebClient(token=SLACK_TOKEN)
        title = bookmark.get("title", "No title")
        link = bookmark.get("link", "No link")
        tags = ", ".join([tag for tag in bookmark.get("tags", [])]) if bookmark.get("tags") else "No tags"
        description = bookmark.get("excerpt", "No description")

        message = f"*New Bookmark Added!*\n\n*Title*: {title}\n*Link*: {link}\n*Tags*: {tags}\n*Description*: {description}"

        response = slack_client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=message
        )
        # print(f"Message sent to Slack channel {SLACK_CHANNEL_ID}: {response['ts']}")
    except SlackApiError as e:
        print(f"Error sending message to Slack: {e.response['error']}")

async def check_for_new_bookmarks(client):
    try:
        last_bookmark_id = load_last_bookmark_id()
        bookmarks = get_raindrop_bookmarks()
        
        if not bookmarks:
            print("No bookmarks found.")
            return
        
        latest_bookmark = bookmarks[0]
        latest_bookmark_id = str(latest_bookmark["_id"])
        
        if last_bookmark_id != latest_bookmark_id:
            # print(f"New bookmark found: {latest_bookmark['title']} - {latest_bookmark['link']}")
            save_last_bookmark_id(latest_bookmark_id)
            await send_to_discord(latest_bookmark, client) 
            send_to_slack(latest_bookmark)  
        # else:
        #     print("No new bookmarks.")
    except Exception as e:
        print(f"Error checking bookmarks: {e}")

class BookmarkBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.poll_for_bookmarks_task.start()

    @tasks.loop(seconds=poll_interval)
    async def poll_for_bookmarks_task(self):
        # print("Checking for new bookmarks...")
        await check_for_new_bookmarks(self)

    async def on_ready(self):
        print(f'Logged in as {self.user}')

async def run_bot():
    intents = discord.Intents.default()
    client = BookmarkBot(intents=intents)
    await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("Bot stopped manually.")
