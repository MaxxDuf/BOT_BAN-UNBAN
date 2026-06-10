import discord
from discord.ext import commands, tasks
import os
import json
import random
import asyncio
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

ALLOWED_IDS = [1275136312935977013, 1272599276538691750]
REPORT_LETTERS = 1513856898129068042
DATA_FILE = "tickets.json"

# ---------------- WEB ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web, daemon=True).start()

# ---------------- BOT ----------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- DATA ----------------
def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load()

# ---------------- SAFE DM ----------------
async def safe_dm(user, ctx, text):
    try:
        await user.send(text)
        print("✔ MP envoyé")
        return True

    except discord.Forbidden:
        print("❌ MP bloqués")

        ch = bot.get_channel(REPORT_LETTERS)
        if ch:
            await ch.send(f"⚠️ MP bloqué pour <@{user.id}>\n\n{text}")

        await ctx.send("⚠️ MP impossible (bloqué), message envoyé au staff.")
        return False

    except Exception as e:
        print("Erreur DM:", e)
        await ctx.send("❌ Erreur MP")
        return False

# ---------------- BAN ----------------
@bot.command()
async def ban(ctx, user_id: int):

    if ctx.author.id not in ALLOWED_IDS:
        return await ctx.send("❌ Non autorisé.")

    user = await bot.fetch_user(user_id)

    await ctx.send("Raison du ban ?")
    def check(m): return m.author == ctx.author and m.channel == ctx.channel
    reason = (await bot.wait_for("message", check=check)).content

    await ctx.send("Durée ? (ex: 7j / 12h)")
    duration = (await bot.wait_for("message", check=check)).content

    ticket_id = str(random.randint(10000, 99999))

    digits = "".join(filter(str.isdigit, duration))
    value = int(digits) if digits else 1

    if "h" in duration:
        expires = datetime.utcnow() + timedelta(hours=value)
    else:
        expires = datetime.utcnow() + timedelta(days=value)

    try:
        member = await ctx.guild.fetch_member(user_id)
        await member.ban(reason=reason)
    except:
        pass

    data[ticket_id] = {
        "user_id": user_id,
        "reason": reason,
        "expires_at": expires.timestamp(),
        "status": "banned",
        "thread_id": None,
        "used": False,
        "letter": None
    }

    save()

    await safe_dm(
        user,
        ctx,
        f"🚫 Tu as été banni\n\nRaison: {reason}\nTicket: {ticket_id}\n!appeal {ticket_id}"
    )

    await ctx.send(f"✔ Ban effectué : {ticket_id}")

# ---------------- APPEAL ----------------
@bot.command()
async def appeal(ctx, ticket_id: str):

    if ticket_id not in data:
        return await ctx.send("❌ Ticket invalide")

    t = data[ticket_id]

    if t["thread_id"]:
        return await ctx.send("❌ Déjà ouvert")

    thread = await ctx.channel.create_thread(
        name=f"appeal-{ticket_id}",
        auto_archive_duration=1440
    )

    t["thread_id"] = thread.id
    t["status"] = "writing"
    save()

    await thread.send("✍️ Écris ta lettre ici.")

# ---------------- MESSAGE HANDLER ----------------
@bot.event
async def on_message(message):

    await bot.process_commands(message)

    if message.author.bot:
        return

    for ticket_id, t in list(data.items()):

        if t.get("thread_id") != message.channel.id:
            continue

        if t.get("status") != "writing":
            continue

        if t.get("used"):
            continue

        t["letter"] = message.content
        t["status"] = "pending_admin"
        t["used"] = True
        save()

        ch = bot.get_channel(REPORT_LETTERS)
        if ch:
            await ch.send(
                f"📤 LETTRE\nTicket: {ticket_id}\n\n{message.content[:1500]}"
            )

        await message.channel.send("📤 Envoyé aux admins")
        break

# ---------------- ADMIN ----------------
def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

@bot.command()
async def oui(ctx, ticket_id: str):

    if not is_admin(ctx):
        return

    t = data.get(ticket_id)
    if not t:
        return await ctx.send("❌ Introuvable")

    t["status"] = "accepted"
    t["used"] = True
    save()

    await ctx.send("✔ Accepté")

@bot.command()
async def non(ctx, ticket_id: str):

    if not is_admin(ctx):
        return

    t = data.get(ticket_id)
    if not t:
        return await ctx.send("❌ Introuvable")

    t["status"] = "refused"
    t["used"] = True
    save()

    await ctx.send("❌ Refusé")

# ---------------- UNBAN SYSTEM ----------------
@tasks.loop(minutes=1)
async def unban_check():

    now = datetime.utcnow().timestamp()

    for t in data.values():

        if t["status"] != "banned":
            continue

        if now < t["expires_at"]:
            continue

        try:
            user = await bot.fetch_user(t["user_id"])

            for guild in bot.guilds:
                try:
                    await guild.unban(user)
                except:
                    pass

            t["status"] = "expired"
            save()

        except Exception as e:
            print("Unban error:", e)

# ---------------- READY ----------------
@bot.event
async def on_ready():
    unban_check.start()
    print("Bot prêt")

# ---------------- RUN ----------------
bot.run(TOKEN)
