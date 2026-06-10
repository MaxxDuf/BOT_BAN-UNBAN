import discord
from discord.ext import commands
import os
import json
import random
import asyncio
from dotenv import load_dotenv
from datetime import datetime, timedelta

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

    # ---------------- 1. ENVOI MP AVANT BAN ----------------

    mp_ok = True
    try:
        await user.send(
            f"🚫 TU AS ÉTÉ BANNI\n\n"
            f"📌 Raison : {reason}\n"
            f"⏳ Durée : {duration}\n"
            f"🎫 Ticket : {ticket_id}\n\n"
            f"Commande d'appel : !appeal {ticket_id}"
        )
    except discord.Forbidden:
        mp_ok = False
        await ctx.send("⚠️ MP bloqué par l'utilisateur.")
    except Exception as e:
        mp_ok = False
        await ctx.send(f"⚠️ Erreur MP : {e}")

    # ---------------- 2. BAN ENSUITE ----------------

    try:
        member = await ctx.guild.fetch_member(user_id)
        await member.ban(reason=reason)
    except:
        pass

    # ---------------- 3. SAVE ----------------

    data[ticket_id] = {
        "user_id": user_id,
        "reason": reason,
        "duration": duration,
        "status": "banned",
        "mp_sent": mp_ok
    }

    save()

    await ctx.send(f"✔ Ban effectué. Ticket : {ticket_id}")

# ---------------- RUN ----------------

bot.run(TOKEN)
