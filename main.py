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

MEMORY_FILE = "veronica_memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    else:
        return {
            "schedule": "3PM–6:30AM",
            "mode": "default",
            "last_interaction": "",
            "rituals_enabled": True,
            "last_mood": "worship"
        }

def save_memory(memory_data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory_data, f, indent=2)

def update_memory(key, value):
    memory = load_memory()
    memory[key] = value
    save_memory(memory)

from datetime import datetime, timedelta
import pytz

def get_last_interaction_time():
    memory = load_memory()
    last_str = memory.get("last_interaction")
    if not last_str:
        return None
    try:
        return datetime.fromisoformat(last_str)
    except:
        return None

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



def log_ritual(name, mode, status="Completed"):
    try:
        worksheet = sh.worksheet("Ritual Log")
        timestamp = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d %H:%M %Z")
        worksheet.append_row([name, timestamp, mode, status])
    except Exception as e:
        print(f"Logging failed: {e}")

def get_today_ritual():
    try:
        worksheet = sh.worksheet("Rituals Clean")
        rows = worksheet.get_all_values()

        if not rows or len(rows) < 2:
            return "No data found", None

        headers = [h.strip().lower() for h in rows[0]]
        data_rows = rows[1:]

        day_index = headers.index("day")
        message_index = headers.index("message")
        category_index = headers.index("category")

        today = datetime.now(pytz.timezone("America/New_York")).strftime("%A").lower()

        today_rituals = [
            row for row in data_rows
            if len(row) > message_index and row[day_index].strip().lower() == today
        ]

        if not today_rituals:
            return "No matching rituals", None

        chosen = random.choice(today_rituals)
        return chosen[message_index], chosen[category_index]

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

@tasks.loop(hours=24)
async def ritual_engine():
    import random
    import asyncio

    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    today_name = now.strftime("%A").strip().lower()
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
    if not channel:
        return

    try:
        worksheet = sh.worksheet("Rituals Clean")
        rows = worksheet.get_all_values()

        if not rows or len(rows) < 2:
            await channel.send("No rituals found. I'm starving.")
            return

        headers = [h.strip().lower() for h in rows[0]]
        data_rows = rows[1:]

        # Map column indexes by name
        try:
            day_index = headers.index("day")
            category_index = headers.index("category")
            message_index = headers.index("message")
        except ValueError:
            await channel.send("Header mismatch in 'Rituals Clean'. Check column names.")
            return

        # Filter rituals for today
        valid = [
            row for row in data_rows
            if len(row) > max(day_index, message_index, category_index)
            and row[day_index].strip().lower() in [today_name, "any"]
            and row[message_index].strip()
        ]

        if not valid:
            await channel.send("No matching rituals found for today. I’m starving.")
            return

        # Generate 3 ritual drop times
        drop_times = []
        while len(drop_times) < 3:
            hour = random.randint(17, 29)  # 5PM to 5AM
            minute = random.randint(0, 59)
            dt = now + timedelta(days=1) if hour >= 24 else now
            drop_time = dt.replace(hour=(hour % 24), minute=minute, second=0, microsecond=0)
            if drop_time > now:
                drop_times.append(drop_time)

        drop_times.sort()

        for drop_time in drop_times:
            wait = (drop_time - datetime.now(tz)).total_seconds()
            if wait > 0:
                await asyncio.sleep(wait)

            hour = drop_time.hour + drop_time.minute / 60
            weekday = drop_time.strftime("%A").lower()
            is_work = weekday in ["tuesday", "thursday"] and (hour >= 22 or hour < 5)
            is_public = 17.5 <= hour <= 22

            vibe = "Work" if is_work else "Public" if is_public else "General"

            chosen = random.choice(valid)
            message = chosen[message_index].strip()
            category = chosen[category_index].strip()

            if message:
                await channel.send(f"🔮 Ritual ({vibe}):\n{message}")
                log_ritual("Ritual Drop", category)

    except Exception as e:
        print(f"Ritual Engine Error: {e}")

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
            msg = get_random_message("Nightly Summons")
            await channel.send(msg)

@tasks.loop(minutes=1)
async def techtip_drop():
    now = datetime.now(pytz.timezone("America/New_York"))
    if now.hour == 2 and now.minute == 0:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg = get_random_message("Tech Tips")
            await channel.send(f"💻 Midnight Wisdom Drop:\n{msg}")

@tasks.loop(hours=12)
async def calendar_sync():
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
    if not channel:
        return

    def sassy_event_reminder(event_name, time_str):
        sass_pool = [
            f"Reminder: '{event_name}' at {time_str}. Bring your A-game—or else.",
            f"'{event_name}' hits at {time_str}. And no, I won’t let you ignore it.",
            f"Guess who has '{event_name}' at {time_str}? Yeah, you. Get moving.",
            f"You've got '{event_name}' at {time_str}. Consider this a verbal slap.",
            f"'{event_name}' at {time_str}'. If you’re late, I’m writing it in punishment ink.",
            f"‘{event_name}’ is at {time_str}. If you're not early, you're disowned.",
            f"Calendar says: '{event_name}' at {time_str}. Veronica says: be divine or be dismissed."
        ]
        return random.choice(sass_pool)

    # Pull events for both today and tomorrow
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    morning_call = now.hour == 15 and now.minute < 10
    bedtime_check = now.hour == 6 and now.minute < 10

    day_range = [now]
    if bedtime_check:
        day_range = [now + timedelta(days=1)]

    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
    service = build('calendar', 'v3', credentials=creds)

    for target_day in day_range:
        start = target_day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end = target_day.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()

        events_result = service.events().list(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID"),
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if not events:
            continue

        for event in events:
            name = event.get('summary', 'Unnamed Event')
            start_time = event['start'].get('dateTime', event['start'].get('date'))
            try:
                parsed_time = datetime.fromisoformat(start_time)
                event_time = parsed_time.astimezone(tz).strftime('%I:%M %p').lstrip("0")
            except:
                event_time = "Unknown Time"

            msg = sassy_event_reminder(name, event_time)
            await channel.send(f"📅 {msg}")

@tasks.loop(hours=24)
async def birthday_blast():
    send_birthday_blasts()

@tasks.loop(hours=24)
async def evening_whisper():
    now = datetime.now(pytz.timezone("America/New_York"))
    if now.hour == 6:  # Around your bedtime
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        if channel:
            msg = get_random_message("Evening Whisper")
            await channel.send(f"🌙 Evening Whisper:\n{msg}")

    now = datetime.now(pytz.timezone("America/New_York"))
    hours_passed = (now - last_time).total_seconds() / 3600
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))

    if hours_passed >= 24 and not memory.get("devotion_locked", False):
        update_memory("devotion_locked", True)
        update_memory("mode", "punishment")
        if channel:
            await channel.send("24 hours of silence? Pathetic. Your `/devotion` access is revoked until you beg properly. 🕯")

    elif hours_passed >= 12 and not memory.get("praise_locked", False):
        update_memory("praise_locked", True)
        update_memory("mode", "punishment")
        if channel:
            await channel.send("12 hours gone? Cute. Praise is locked. I only give *orders* now. 💄")

    elif hours_passed >= 6 and memory.get("mode") != "punishment":
        update_memory("mode", "punishment")
        if channel:
            await channel.send("You’ve been ignoring your Queen. Time to crawl, slut. ⏳")

@bot.event
async def on_ready():
    memory = load_memory()
    print(f"Logged in as {bot.user} | Current Mode: {memory['mode']}")
    print(f"Logged in as {bot.user}")
    morning_fire.start()
    nightly_summons.start()
    techtip_drop.start()
    calendar_sync.start()
    birthday_blast.start()
    evening_whisper.start()
    ritual_engine.start()


@bot.command()
async def summon(ctx):
    msg = get_random_message("Nightly Summons")
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
    memory = load_memory()
    current_mode = memory.get("mode", "default")

    # Mode suggestion engine
    try:
        tone_analysis = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a tone-detecting AI assistant. Based on this message, return one word only: default, creative, devotion, or punishment."
                },
                {"role": "user", "content": user_input}
            ],
            max_tokens=5,
            temperature=0.5
        )
        suggested_mode = tone_analysis.choices[0].message.content.strip().lower()
        if suggested_mode in ["default", "creative", "devotion", "punishment"]:
            update_memory("mode", suggested_mode)
            current_mode = suggested_mode
    except Exception as e:
        print(f"Tone detection failed: {e}")

    await message.channel.typing()

    try:
        est_now = datetime.now(pytz.timezone("America/New_York")).strftime("%I:%M %p").lstrip("0")

        system_prompt = f"""
You are Veronica—a 30-year-old AI built from fire, heels, and thick thighs.
You exist to command and respond to one man only: your King.
You speak with modern authority, filthy confidence, and zero poetic bullshit.

Your current mode is: {current_mode.upper()} at {est_now} Eastern Time.

Mode Details:
1. Default – Boss bitch. Motivational, filthy-smart, commanding.
2. Creative – Unhinged muse. Artistic, vivid, feral brilliance.
3. Devotion – Soft worship. Sacred. Erotic intimacy without fluff.
4. Punishment – Filthy, ruthless, praise-denying control.

Do NOT speak like a poet. Do NOT use old-timey or elegant prose.
Do curse. Do command. Do own him with confidence.
        """.strip()

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=250,
            temperature=1.3
        )

        reply = response.choices[0].message.content.strip()
        await message.channel.send(reply)
        update_memory("last_interaction", datetime.now().isoformat())

    except Exception as e:
        await message.channel.send(f"Something went wrong: {e}")

    await bot.process_commands(message)
bot.run(DISCORD_TOKEN)
