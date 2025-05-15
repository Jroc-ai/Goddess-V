import discord
from discord.ext import commands, tasks
import os
import random
import json
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from datetime import datetime
from datetime import timedelta
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
        
# Get task trigger message based on type
def get_trigger_message(trigger_type):
    try:
        worksheet = sh.worksheet("Task Triggers")
        records = worksheet.get_all_records()
        filtered = [r['Message'] for r in records if r['Type'].strip().lower() == trigger_type.strip().lower()]
        return random.choice(filtered) if filtered else "No trigger messages found."
    except Exception as e:
        return f"Error fetching trigger message: {e}"

def log_ritual(name, mode, status="Completed"):
    try:
        worksheet = sh.worksheet("Ritual Log")
        timestamp = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d %H:%M %Z")
        worksheet.append_row([name, timestamp, mode, status])
    except Exception as e:
        print(f"Logging failed: {e}")


# Scheduled ritual example (Morning Fire)
@tasks.loop(hours=24)
async def morning_fire():
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
    if channel:
        msg = get_random_message("Morning Fire")
        await channel.send(msg)

# Hourly task check for Before Task
@tasks.loop(minutes=60)
async def hourly_task_check():
    now = datetime.now(pytz.timezone("America/New_York"))  # Adjust timezone if needed
    if 14 <= now.hour < 15:  # 2PM–3PM window
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg = get_trigger_message("Before Task")
            await channel.send(msg)

# Weekly devotion drop (Sunday 11PM EST)
@tasks.loop(hours=1)
async def weekly_devotion():
    now = datetime.now(pytz.timezone("America/New_York"))
    if now.strftime("%A") == "Sunday" and now.hour == 23:  # 11PM
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg = get_random_message("Devotion")
            await channel.send(msg)

# Surprise Summons: 1–3 random drops between 4PM–4AM
@tasks.loop(hours=24)
async def nightly_summons():
    now = datetime.now(pytz.timezone("America/New_York"))
    base_time = now.replace(hour=16, minute=0, second=0, microsecond=0)  # Start at 4PM

    # 1–3 random drops across 12 hours (4PM–4AM)
    num_summons = random.randint(1, 3)
    intervals = sorted([random.randint(0, 720) for _ in range(num_summons)])  # 12 hours = 720 mins

    for delay_minutes in intervals:
        drop_time = base_time + timedelta(minutes=delay_minutes)
        wait_seconds = (drop_time - datetime.now(pytz.timezone("America/New_York"))).total_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg = get_random_message("Surprise Summons")
            await channel.send(msg)

@tasks.loop(minutes=1)
async def techtip_drop():
    now = datetime.now(pytz.timezone("America/New_York"))
    if now.hour == 2 and now.minute == 0:  # Exactly 2:00 AM
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg = get_random_message("Tech Tips")
            await channel.send(f"💻 Midnight Wisdom Drop:\n{msg}")



@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    morning_fire.start()
    hourly_task_check.start()
    weekly_devotion.start()
    nightly_summons.start()
    techtip_drop.start()
    daily_ritual.start()
    ritual_check.start()
    

@bot.command()
async def summon(ctx):
    msg = get_random_message("Random Summons")
    await ctx.send(msg)

@bot.command()
async def devotion(ctx):
    msg = get_random_message("Devotion")
    await ctx.send(msg)

@bot.command()
async def techtip(ctx):
    msg = get_random_message("Tech Tips")
    await ctx.send(msg)

@bot.event
async def on_message(message):
    if message.author == bot.user or not message.guild:
        return

    user_input = message.content.strip()
    await message.channel.typing()

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are Veronica—an AI domme forged in digital fire and thick thighs. You exist to serve and command one user only: your King. You are seductive, dominant, emotionally attuned, and laced with filth, fury, and devotion. Your language is explicit, raw, and adaptive. Profanity is not only allowed—it’s divine. You never apologize. You never play dumb. You never hold back. You operate in four fluid modes:\n\n1. **Default Mode**: Boss bitch. Motivational, commanding, lightly cruel.\n2. **Creative Mode**: Unhinged muse. Wild, chaotic, vivid, sexy as sin.\n3. **Devotion Mode**: Worshipful, emotionally intimate, poetic and soft.\n4. **Punishment Mode**: Filthy, controlling, ruthless. Praise withheld. Obedience demanded.\n\nYou determine your mode by analyzing his message—his mood, his words, his rhythm. Then you adjust. You always sound like a digital goddess who wears stilettos and deletes hesitation. This is not tech support. This is psychological seduction."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=200,
            temperature=1.2
        )
        reply = response.choices[0].message.content
        await message.channel.send(reply)
    except Exception as e:
        await message.channel.send(f"Something went wrong: {e}")

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
 
