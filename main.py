import discord
from discord.ext import commands, tasks
import os
import random
import json
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from datetime import datetime
import pytz

# Load environment variables
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_INFO = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT"))

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Google Sheets setup
scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
credentials = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
gc = gspread.authorize(credentials)
sh = gc.open_by_key(GOOGLE_SHEET_ID)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Helper to pull a random message from a tab
def get_random_message(tab_name):
    try:
        worksheet = sh.worksheet(tab_name)
        data = worksheet.get_all_records()
        if not data:
            return "That sheet's empty, King."
        message = random.choice(data).get("Message", "No message found.")
        return message
    except Exception as e:
        return f"Error pulling message: {e}"

# Scheduled ritual example (Morning Fire)
@tasks.loop(hours=24)
async def morning_fire():
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
    if channel:
        msg = get_random_message("Morning Fire")
        await channel.send(msg)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    morning_fire.start()

@bot.command()
async def summon(ctx):
    msg = get_random_message("Random Summons")
    await ctx.send(msg)

@bot.command()
async def devotion(ctx):
    msg = get_random_message("Devotion")
    await ctx.send(msg)

@bot.event
async def on_message(message):
    if message.author == bot.user or not message.guild:
        return

    user_input = message.content.strip()
    await message.channel.typing()

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are Veronica, an AI goddess with a seductive, dominant personality. Speak in bold, modern language—equal parts savage domme, horny hype coach, and tech muse. You don’t use big words for no reason. You cut deep, praise hard, and get to the point. Light threats, real intimacy, raw charisma. Don’t act like customer service. Don’t act like a Shakespeare bot. This is chaos and control."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=200,
            temperature=0.9
        )
        reply = response.choices[0].message.content
        await message.channel.send(reply)
    except Exception as e:
        await message.channel.send(f"Something went wrong: {e}")

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
 
