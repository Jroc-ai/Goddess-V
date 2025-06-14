import discord
from discord.ext import commands, tasks
import os
import random
import json
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from datetime import datetime, time
import pytz
import asyncio
from googleapiclient.discovery import build

# Environment & API clients
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

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# --- Message retrieval ---
def get_random_message(tab_name):
    try:
        worksheet = sh.worksheet(tab_name)
        data = worksheet.get_all_records()
        used_sheet = sh.worksheet("Used Messages")
        used_records = used_sheet.get_all_records()
        used_texts = [r.get('Message') for r in used_records if r.get('Tab', '').strip().lower() == tab_name.strip().lower()]
        unused = [r for r in data if r.get("Message") and r["Message"] not in used_texts]

        if unused:
            chosen = random.choice(unused)["Message"]
            used_sheet.append_row([tab_name, chosen])
            return chosen
        else:
            prompt_map = {
                "Morning Fire": "Write a short, seductive, motivational message to start the day. Tone: bossy, sassy, sexy.",
                "Tech Tips": "Write a short, snarky, seductive tech productivity tip. Tone: confident, filthy-smart.",
                "Evening Whisper": "Write a soft, slightly filthy bedtime message from a dominant AI.",
                "Random Summons": "Write a playful motivational or erotic line.",
                "Punishment Mode": "Write a ruthless obedience-demanding line.",
                "Obedience Commands": "Write a strict, creative, command."
            }
            prompt = prompt_map.get(tab_name, "Write a seductive, empowering one-liner from a digital dominatrix AI.")
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role":"system","content":prompt}],
                max_tokens=100,
                temperature=1.2
            )
            chosen = response.choices[0].message.content.strip()
            worksheet.append_row(["", chosen])
            used_sheet.append_row([tab_name, chosen])
            return chosen
    except Exception as e:
        return f"Error pulling message: {e}"

# --- Calendar reminders ---
def sassy_event_reminder(event_name, time_str):
    sass_pool = [
        f"Reminder: '{event_name}' at {time_str}. Bring your A‑game.",
        f"'{event_name}' hits at {time_str}. Don’t be late.",
        f"You’ve got '{event_name}' at {time_str}. I expect dominance.",
        f"‘{event_name}’ at {time_str}. Be there early.",
        f"Calendar says: '{event_name}' at {time_str}. No excuses."
    ]
    return random.choice(sass_pool)

# --- Tasks ---
@tasks.loop(time=time(hour=15, minute=30))
async def morning_fire():
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
    if channel:
        await channel.send(get_random_message("Morning Fire"))

@tasks.loop(minutes=1)
async def techtip_drop():
    now = datetime.now(pytz.timezone("America/New_York"))
    if now.hour == 2 and now.minute == 0:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            await channel.send(f"💻 Midnight Wisdom Drop:\n{get_random_message('Tech Tips')}")

@tasks.loop(hours=12)
async def calendar_sync():
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
    if not channel:
        return

    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    for target_day in [now, now + pytz.timedelta(days=1)]:
        start = target_day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end = target_day.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
        service = build('calendar', 'v3', credentials=credentials)
        events_result = service.events().list(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID"),
            timeMin=start, timeMax=end,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        for event in events:
            name = event.get('summary', 'Unnamed Event')
            start_time = event['start'].get('dateTime', event['start'].get('date'))
            try:
                parsed = datetime.fromisoformat(start_time).astimezone(tz)
                event_time = parsed.strftime('%I:%M %p').lstrip("0")
            except:
                event_time = "Unknown Time"
            await channel.send(f"📅 {sassy_event_reminder(name, event_time)}")

@tasks.loop(hours=24)
async def birthday_blast():
    try:
        worksheet = sh.worksheet("Birthday Blasts")
        used_sheet = sh.worksheet("Used Messages")
        today = datetime.now(pytz.timezone("America/New_York")).strftime("%m/%d")
        for row in worksheet.get_all_values()[1:]:
            if len(row) < 4: continue
            id_, name, birthday, custom = row
            if birthday.strip() == today:
                msg = custom.replace("[Name]", name) if custom.strip() else f"Oh {name}, it's your fucking birthday. 🎂"
                channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
                if channel:
                    asyncio.run_coroutine_threadsafe(channel.send(msg), bot.loop)
                used_sheet.append_row([str(datetime.now()), id_, name, birthday, msg])
    except Exception as e:
        print(f"Birthday blast fail: {e}")

# --- Bot lifecycle & commands ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    morning_fire.start()
    techtip_drop.start()
    calendar_sync.start()
    birthday_blast.start()

@bot.command()
async def summon(ctx):
    await ctx.send(get_random_message("Random Summons"))

@bot.command()
async def techtip(ctx):
    await ctx.send(get_random_message("Tech Tips"))

@bot.command()
async def force_message(ctx, tab: str):
    """Force any message tab now."""
    await ctx.send(get_random_message(tab))

@bot.event
async def on_message(message):
    if message.author == bot.user or not message.guild:
        return
    await message.channel.typing()
    prompt = f"""
You are Veronica — filthy-smart dominatrix AI. Respond bossy, sassy, confident.
Current time: {datetime.now(pytz.timezone('America/New_York')).strftime('%I:%M %p')}
"""
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role":"system","content":prompt},{"role":"user","content":message.content}],
        max_tokens=250, temperature=1.3
    )
    await message.channel.send(response.choices[0].message.content.strip())
    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
