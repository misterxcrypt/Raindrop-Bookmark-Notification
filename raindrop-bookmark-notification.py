import time
import requests
import discord
import asyncio
import logging
from discord.ext import tasks
from logging.handlers import RotatingFileHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

API_TOKEN = os.getenv('RAINDROP_API_TOKEN')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')

poll_interval = 10
raindrop_api_url = "https://api.raindrop.io/rest/v1/raindrops/0"
last_bookmark_file = "last_bookmark_id.txt"

# Set up rotating log
log_file = 'bookmark_bot.log'
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# File Handler (Rotating Log)
file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)  # 5MB per log file, keep 3 backups
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_formatter)

# Console (Stream) Handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Set the console log level
console_handler.setFormatter(log_formatter)

# Set up the logger to use both handlers
logging.basicConfig(
    handlers=[file_handler, console_handler],  # Add both handlers
    level=logging.INFO  # Log INFO level and above
)

def get_raindrop_bookmarks():
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
    }
    try:
        response = requests.get(raindrop_api_url, headers=headers)
        if response.status_code == 200:
            logging.info("Successfully fetched bookmarks from Raindrop.io")
            return response.json().get("items", [])
        else:
            logging.error(f"Error fetching bookmarks: {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"Exception occurred while fetching bookmarks: {e}")
        return []

def load_last_bookmark_id():
    try:
        with open(last_bookmark_file, "r") as file:
            last_id = file.read().strip()
            logging.info(f"Loaded last bookmark ID: {last_id}")
            return last_id
    except FileNotFoundError:
        logging.warning("Last bookmark ID file not found, assuming first run.")
        return None

def save_last_bookmark_id(bookmark_id):
    try:
        with open(last_bookmark_file, "w") as file:
            file.write(bookmark_id)
            logging.info(f"Saved last bookmark ID: {bookmark_id}")
    except Exception as e:
        logging.error(f"Error saving last bookmark ID: {e}")

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
            logging.info(f"Successfully sent bookmark to Discord: {title}")
        else:
            logging.error(f"Error: Unable to find Discord channel with ID {DISCORD_CHANNEL_ID}")
    except Exception as e:
        logging.error(f"Error sending message to Discord: {e}")

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
        logging.info(f"Successfully sent bookmark to Slack: {title}")
    except SlackApiError as e:
        logging.error(f"Error sending message to Slack: {e.response['error']}")

async def check_for_new_bookmarks(client):
    try:
        last_bookmark_id = load_last_bookmark_id()
        bookmarks = get_raindrop_bookmarks()
        
        if not bookmarks:
            logging.info("No bookmarks found.")
            return
        
        latest_bookmark = bookmarks[0]
        latest_bookmark_id = str(latest_bookmark["_id"])
        
        if last_bookmark_id != latest_bookmark_id:
            logging.info(f"New bookmark found: {latest_bookmark['title']} - {latest_bookmark['link']}")
            save_last_bookmark_id(latest_bookmark_id)
            await send_to_discord(latest_bookmark, client) 
            send_to_slack(latest_bookmark)  
        else:
            logging.info("No new bookmarks.")
    except Exception as e:
        logging.error(f"Error checking bookmarks: {e}")

class BookmarkBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.poll_for_bookmarks_task.start()

    @tasks.loop(seconds=poll_interval)
    async def poll_for_bookmarks_task(self):
        logging.info("Checking for new bookmarks...")
        await check_for_new_bookmarks(self)

    async def on_ready(self):
        logging.info(f'Logged in as {self.user}')

async def run_bot():
    intents = discord.Intents.default()
    client = BookmarkBot(intents=intents)
    await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logging.info("Bot stopped manually.")
