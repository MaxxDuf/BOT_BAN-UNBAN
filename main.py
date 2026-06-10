import discord
from discord.ext import commands
import os
import json
import random
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# ---------------- WEB SERVER (RENDER FIX) ----------------

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
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

data = load()

# ---------------- BAN COMMAND ----------------

@bot.command()
async def ban2(ctx, user_id: int):

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

    # MP AVANT BAN
    mp_ok = True

    try:
        await user.send(
            f"🚫 TU AS ÉTÉ BANNI\n\n"
            f"📌 Raison : {reason}\n"
            f"📅 Durée : {duration}\n"
            f"🎫 Ticket : {ticket_id}\n\n"
            f"Rejoins le serveur d'appel : https://discord.gg/NsbWYCD4\n"
            f"Commande : !appel {ticket_id}"
        )
    except discord.Forbidden:
        mp_ok = False
        await ctx.send("⚠️ MP bloqué.")
    except Exception:
        mp_ok = False
        await ctx.send("⚠️ Impossible d'envoyer le MP.")

    # BAN
    try:
        member = await ctx.guild.fetch_member(user_id)
        await member.ban(reason=reason)
    except Exception:
        pass

    data[ticket_id] = {
        "user_id": user_id,
        "reason": reason,
        "duration": duration,
        "status": "banned",
        "mp_sent": mp_ok,
        "thread_id": None,
        "used": False,
        "letter": None
    }

    save()

    await ctx.send(f"✔ Ban effectué. Ticket : {ticket_id}")

# ---------------- APPEL ----------------

@bot.command()
async def appel(ctx, ticket_id: str):

    if ticket_id not in data:
        return await ctx.send("❌ Ticket invalide.")

    t = data[ticket_id]

    if t.get("thread_id") is not None:
        return await ctx.send("❌ Ticket déjà ouvert.")

    try:
        thread = await ctx.channel.create_thread(
            name=f"appeal-{ticket_id}",
            auto_archive_duration=1440
        )
    except Exception as e:
        print("Erreur création thread :", e)
        return await ctx.send(
            "❌ Impossible de créer le fil de discussion."
        )

    t["thread_id"] = thread.id
    t["status"] = "writing"
    t["used"] = False

    save()

    await thread.send(
        f"🎫 Ticket {ticket_id}\n\n"
        "✍️ Écris ta lettre ici.\n"
        "Elle sera envoyée aux admins."
    )

    await ctx.send(f"✅ Fil créé : {thread.mention}")

# ---------------- MESSAGE HANDLER ----------------

@bot.event
async def on_message(message):

    await bot.process_commands(message)

    if message.author.bot:
        return

    for ticket_id, t in data.items():

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

# ---------------- ADMIN ----------------

def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

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

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")

bot.run(TOKEN)
