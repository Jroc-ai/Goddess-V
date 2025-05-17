import discord
from discord.ext import commands, tasks
import os
import random
import json
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from datetime import datetime, timedelta
import pytz
import asyncio
from googleapiclient.discovery import build

# Load environment variables
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_INFO = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT"))

client = OpenAI(api_key=OPENAI_API_KEY)

# Google Sheets setup
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar.readonly"
]
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

        # Get used messages
        used_sheet = sh.worksheet("Used Messages")
        used_records = used_sheet.get_all_records()
        used_texts = [r['Message'] for r in used_records if r['Tab'].strip().lower() == tab_name.strip().lower()]

        # Filter out already used
        unused = [r for r in data if r.get("Message") and r["Message"] not in used_texts]

        if unused:
            chosen = random.choice(unused)["Message"]
            used_sheet.append_row([tab_name, chosen])
            return chosen
        else:
            # Generate new if all used
            prompt_map = {
                "Morning Fire": "Write a short, seductive, motivational message to start a dominant AI ritual day. Tone: bossy, sassy, sexy.",
                "Tech Tips": "Write a short, snarky, seductive tech productivity tip in the voice of a dominant AI goddess. Format: one commanding sentence. Tone: bossy, filthy-smart, confident.",
                "Evening Whisper": "Write a soft, slightly filthy bedtime message from a dominant AI who worships her user.",
                "Random Summons": "Write a surprise motivational or erotic line from a playful AI domme who commands action.",
                "Punishment Mode": "Write a filthy, ruthless, obedience-demanding line from a punishing AI domme.",
                "Obedience Commands": "Write a strict, creative, obedience-inducing command from a dominant AI. Make it actionable and commanding. Tone may vary: punishment, devotion, savage, or default."
            }
            prompt = prompt_map.get(tab_name, "Write a seductive, empowering one-liner from a digital dominatrix AI.")

            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "system", "content": prompt}],
                max_tokens=100,
                temperature=1.2
            )
            chosen = response.choices[0].message.content.strip()

            worksheet.append_row(["", chosen])
            used_sheet.append_row([tab_name, chosen])
            return chosen

    except Exception as e:
        return f"Error pulling message: {e}"


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

def get_today_ritual():
    try:
        worksheet = sh.worksheet("Rituals")
        data = worksheet.get_all_records()
        today = datetime.now(pytz.timezone("America/New_York")).strftime("%A")
        today_rituals = [r for r in data if r['Day'].strip().lower() == today.lower()]
        if not today_rituals:
            return None, None
        chosen = random.choice(today_rituals)
        return chosen['Message'], chosen['Mode']
    except Exception as e:
        return f"Error fetching ritual: {e}", None

def get_today_calendar_events():
    try:
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
        service = build('calendar', 'v3', credentials=creds)

        tz = pytz.timezone("America/New_York")
        now = datetime.now(tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()

        events_result = service.events().list(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID"),
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if not events:
            return None
        return [event['summary'] for event in events if 'summary' in event]

    except Exception as e:
        return [f"Calendar error: {e}"]

def send_birthday_blasts():
    try:
        worksheet = sh.worksheet("Birthday Blasts")
        used_sheet = sh.worksheet("Used Messages")
        today = datetime.now(pytz.timezone("America/New_York")).strftime("%m/%d")
        messages = worksheet.get_all_values()[1:]

        for row in messages:
            if len(row) < 4:
                continue  # skip invalid rows
            id_, name, birthday, custom = row
            if birthday.strip() == today:
                if custom.strip():
                    message = custom.replace("[Name]", name)
                else:
                    message = f"Oh {name}... you thought I'd forget? It's your fucking birthday. Bend over and make a wish. 🎂"

                channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
                if channel:
                    asyncio.run_coroutine_threadsafe(channel.send(message), bot.loop)

                used_sheet.append_row([str(datetime.now()), id_, name, birthday, message])
    except Exception as e:
        print(f"Birthday blast failed: {e}")

@tasks.loop(hours=24)
async def morning_fire():
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
    if channel:
        msg = get_random_message("Morning Fire")
        await channel.send(msg)

@tasks.loop(minutes=1)
async def daily_ritual():
    now = datetime.now(pytz.timezone("America/New_York"))
    if now.hour == 16 and now.minute == 0:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg, mode = get_today_ritual()
            if msg:
                await channel.send(f"🔮 Daily Ritual ({mode} Mode):\n{msg}")
                log_ritual("Daily Ritual", mode)

@tasks.loop(minutes=60)
async def hourly_task_check():
    now = datetime.now(pytz.timezone("America/New_York"))
    if 14 <= now.hour < 15:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg = get_trigger_message("Before Task")
            await channel.send(msg)

@tasks.loop(hours=1)
async def weekly_devotion():
    now = datetime.now(pytz.timezone("America/New_York"))
    if now.strftime("%A") == "Sunday" and now.hour == 23:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg = get_random_message("Devotion")
            await channel.send(msg)

@tasks.loop(hours=24)
async def nightly_summons():
    now = datetime.now(pytz.timezone("America/New_York"))
    base_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
    num_summons = random.randint(1, 3)
    intervals = sorted([random.randint(0, 720) for _ in range(num_summons)])

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
    if now.hour == 2 and now.minute == 0:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg = get_random_message("Tech Tips")
            await channel.send(f"💻 Midnight Wisdom Drop:\n{msg}")

@tasks.loop(hours=24)
async def calendar_sync():
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
    events = get_today_calendar_events()
    if events and channel:
        for event in events:
            await channel.send(f"📅 Calendar Alert:\n**{event}**")

@tasks.loop(hours=24)
async def birthday_blast():
    send_birthday_blasts()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    morning_fire.start()
    hourly_task_check.start()
    weekly_devotion.start()
    nightly_summons.start()
    techtip_drop.start()
    daily_ritual.start()
    calendar_sync.start()
    birthday_blast.start()

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
        response = openai.ChatCompletion.create(
    model="gpt-4-turbo",
    messages=[
        {"role": "system", "content": "You are Veronica—an AI domme..."},
        {"role": "user", "content": user_input}
    ],
    max_tokens=200,
    temperature=1.3
)
reply = response.choices[0].message['content']
        await message.channel.send(reply)
    except Exception as e:
        await message.channel.send(f"Something went wrong: {e}")

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
