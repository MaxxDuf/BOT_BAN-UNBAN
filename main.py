import discord
from discord.ext import commands
import os
import json
import random
import asyncio
import httpx
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# ---------------- WEB (Render keep alive) ----------------

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
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not TOKEN:
    raise Exception("DISCORD_TOKEN manquant")

if not MISTRAL_API_KEY:
    raise Exception("MISTRAL_API_KEY manquante")

# ---------------- BOT ----------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- CONFIG ----------------

ALLOWED_CHANNEL = 1513274703572373504
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

# ---------------- IA MISTRAL (FIX STABLE) ----------------

def get_score(text: str) -> int:
    try:
        r = httpx.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistral-small-latest",
                "messages": [
                    {
                        "role": "system",
                        "content": "Note cette lettre d'excuse de 0 à 10. Réponds uniquement avec un chiffre."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ]
            },
            timeout=30
        )

        data = r.json()
        return int(data["choices"][0]["message"]["content"].strip())

    except Exception as e:
        print("IA ERROR:", e)
        return 0

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
        "letter": None,
        "score": None
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

# ---------------- APPEAL THREAD ----------------

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

    await thread.send("✍️ Écris ta lettre ici.")

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
            score = get_score(text)

            t["letter"] = text
            t["score"] = score
            save()

            await message.channel.send(f"🤖 IA Mistral : **{score}/10**")

            # 🔴 REFUS AUTO (0-7)
            if score < 8:

                t["used"] = True
                t["status"] = "auto_refused"
                save()

                await message.channel.send("❌ Refus automatique.")

                await asyncio.sleep(10)
                await message.channel.delete()
                return

            # 🟢 ENVOI ADMINS (8-10)
            t["status"] = "pending_admin"
            save()

            report = bot.get_channel(REPORT_LETTERS)

            if report:
                await report.send(
                    f"📤 LETTRE À TRAITER\n"
                    f"🎫 ID: {ticket_id}\n"
                    f"🤖 Score: {score}/10\n"
                    f"📝 {text[:1000]}"
                )

            await message.channel.send("📤 Envoyé aux admins.")
            break

# ---------------- ADMIN COMMANDS ----------------

def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

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

    if t["thread_id"]:
        ch = await bot.fetch_channel(t["thread_id"])
        await ch.send("✅ Accepté")
        await asyncio.sleep(10)
        await ch.delete()

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

    if t["thread_id"]:
        ch = await bot.fetch_channel(t["thread_id"])
        await ch.send("❌ Refusé")
        await asyncio.sleep(10)
        await ch.delete()

# ---------------- RUN ----------------

bot.run(TOKEN)
