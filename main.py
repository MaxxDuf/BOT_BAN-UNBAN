import discord
from discord.ext import commands
import os
import json
import random
import asyncio
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# ---------------- WEB (Render) ----------------

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

ALLOWED_CHANNEL = 1513924199234928855
REPORT_NEW_TICKET = 1513924199234928855
REPORT_LETTERS = 1513856898129068042

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

# ---------------- BAN TICKET ----------------

@bot.command()
async def banticket(ctx, user_id: int):

    if ctx.channel.id != ALLOWED_CHANNEL:
        return await ctx.send("❌ Mauvais salon.")

    ticket_id = str(random.randint(10000, 99999))

    data[ticket_id] = {
        "user_id": user_id,
        "thread_id": None,
        "status": "new",
        "used": False,
        "letter": None
    }

    save()

    report = bot.get_channel(REPORT_NEW_TICKET)

    if report:
        await report.send(
            f"📩 **NOUVEAU TICKET**\n"
            f"👤 ID : {user_id}\n"
            f"🎫 Ticket : {ticket_id}"
        )

    await ctx.send(f"🎫 Ticket créé : {ticket_id}")

# ---------------- APPEAL ----------------

@bot.command()
async def appeal(ctx, ticket_id: str):

    if ticket_id not in data:
        return await ctx.send("❌ Ticket invalide.")

    t = data[ticket_id]

    if t["used"]:
        return await ctx.send("❌ Code déjà utilisé.")

    if t["thread_id"]:
        return await ctx.send("❌ Déjà ouvert.")

    thread = await ctx.channel.create_thread(
        name=f"appeal-{ticket_id}",
        type=discord.ChannelType.public_thread
    )

    t["thread_id"] = thread.id
    t["status"] = "writing"
    save()

    await thread.send("✍️ Écris ta lettre ici. Elle sera envoyée aux admins automatiquement.")

# ---------------- MESSAGE HANDLER ----------------

@bot.event
async def on_message(message):

    await bot.process_commands(message)

    if message.author.bot:
        return

    for ticket_id, t in data.items():

        if t.get("thread_id") == message.channel.id and t["status"] == "writing":

            if t["used"]:
                return

            text = message.content

            t["letter"] = text
            t["status"] = "pending_admin"
            save()

            report = bot.get_channel(REPORT_LETTERS)

            if report:
                await report.send(
                    f"📤 LETTRE À TRAITER\n"
                    f"🎫 ID: {ticket_id}\n"
                    f"📝 {text[:1500]}"
                )

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

    t["used"] = True
    t["status"] = "accepted"
    save()

    await ctx.send("✔ Déban accepté")

    if t.get("thread_id"):
        ch = await bot.fetch_channel(t["thread_id"])
        await ch.send("✅ Lettre acceptée, déban en cours...")
        await asyncio.sleep(10)
        await ch.delete()

# ---------------- REFUSE ----------------

@bot.command()
async def non(ctx, ticket_id: str):

    if not is_admin(ctx):
        return

    t = data.get(ticket_id)
    if not t:
        return await ctx.send("❌ Introuvable.")

    t["used"] = True
    t["status"] = "refused"
    save()

    await ctx.send("❌ Refus")

    if t.get("thread_id"):
        ch = await bot.fetch_channel(t["thread_id"])
        await ch.send("❌ Lettre refusée.")
        await asyncio.sleep(10)
        await ch.delete()

# ---------------- RUN ----------------

bot.run(TOKEN)
