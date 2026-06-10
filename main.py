import discord
from discord.ext import commands, tasks
import os
import json
import random
import asyncio
from dotenv import load_dotenv
from datetime import datetime, timedelta

# ---------------- WEB SERVER (RENDER FIX) ----------------

from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web, daemon=True).start()

# ---------------- ENV ----------------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise Exception("DISCORD_TOKEN manquant")

# ---------------- BOT ----------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- CONFIG ----------------

ALLOWED_IDS = [1275136312935977013, 1272599276538691750]
DATA_FILE = "tickets.json"

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

# ---------------- BAN COMMAND ----------------

@bot.command()
async def ban(ctx, user_id: int):

    if ctx.author.id not in ALLOWED_IDS:
        return await ctx.send("❌ Non autorisé.")

    try:
        user = await bot.fetch_user(user_id)
    except:
        return await ctx.send("❌ Utilisateur introuvable.")

    await ctx.send("📌 Raison du ban ?")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    reason = (await bot.wait_for("message", check=check)).content

    await ctx.send("⏳ Durée ? (ex: 7j, 12h)")

    duration = (await bot.wait_for("message", check=check)).content

    ticket_id = str(random.randint(10000, 99999))

    # ---------------- MP AVANT BAN ----------------

    mp_ok = True
    try:
        await user.send(
            f"🚫 TU AS ÉTÉ BANNI\n\n"
            f"📌 Raison : {reason}\n"
            f"⏳ Durée : {duration}\n"
            f"🎫 Ticket : {ticket_id}\n\n"
            f"Commande : !appeal {ticket_id}"
        )
    except discord.Forbidden:
        mp_ok = False
        await ctx.send("⚠️ MP bloqué")
    except:
        mp_ok = False
        await ctx.send("⚠️ Impossible d'envoyer le MP")

    # ---------------- BAN ----------------

    try:
        member = await ctx.guild.fetch_member(user_id)
        await member.ban(reason=reason)
    except:
        pass

    # ---------------- SAVE ----------------

    data[ticket_id] = {
        "user_id": user_id,
        "reason": reason,
        "duration": duration,
        "status": "banned",
        "mp_sent": mp_ok
    }

    save()

    await ctx.send(f"✔ Ban effectué. Ticket : {ticket_id}")

# ---------------- APPEAL ----------------

@bot.command()
async def appeal(ctx, ticket_id: str):

    if ticket_id not in data:
        return await ctx.send("❌ Ticket invalide.")

    t = data[ticket_id]

    if t.get("thread_id"):
        return await ctx.send("❌ Déjà ouvert.")

    thread = await ctx.channel.create_thread(
        name=f"appeal-{ticket_id}",
        auto_archive_duration=1440
    )

    t["thread_id"] = thread.id
    t["status"] = "writing"
    t["used"] = False

    save()

    await thread.send("✍️ Écris ta lettre ici. Elle sera envoyée aux admins.")

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

        await message.channel.send("📤 Lettre envoyée aux admins.")
        break

# ---------------- ADMIN CHECK ----------------

def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

# ---------------- ACCEPT ----------------

@bot.command()
async def oui(ctx, ticket_id: str):

    if not is_admin(ctx):
        return

    t = data.get(ticket_id)
    if not t:
        return await ctx.send("❌ Introuvable.")

    t["status"] = "accepted"
    t["used"] = True
    save()

    await ctx.send("✔ Accepté")

# ---------------- REFUSE ----------------

@bot.command()
async def non(ctx, ticket_id: str):

    if not is_admin(ctx):
        return

    t = data.get(ticket_id)
    if not t:
        return await ctx.send("❌ Introuvable.")

    t["status"] = "refused"
    t["used"] = True
    save()

    await ctx.send("❌ Refusé")

# ---------------- RUN BOT ----------------

bot.run(TOKEN)
