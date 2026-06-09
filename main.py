import discord
from discord.ext import commands
import os
import json
import random
import asyncio
from dotenv import load_dotenv
from mistralai import Client
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    app.run(host="0.0.0.0", port=10000)

Thread(target=run_web).start()

# ---------------- ENV ----------------

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
ai = Client(api_key=MISTRAL_API_KEY)

if not TOKEN:
    raise Exception("❌ DISCORD_TOKEN manquant")
if not MISTRAL_API_KEY:
    raise Exception("❌ MISTRAL_API_KEY manquante")

ai = Mistral(api_key=MISTRAL_API_KEY)

# ---------------- BOT ----------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "tickets.json"

# ---------------- CONFIG ----------------

ALLOWED_CHANNEL = 1513924199234928855
REPORT_NEW_TICKET = 1513924199234928855
REPORT_LETTERS = 1513856898129068042

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

# ---------------- IA ----------------

def get_score(text: str) -> int:
    try:
        res = ai.chat.complete(
            model="mistral-small-latest",
            messages=[
                {
                    "role": "system",
                    "content": "Note cette lettre d'excuse de 0 à 10. Réponds uniquement avec un chiffre."
                },
                {"role": "user", "content": text}
            ]
        )
        return int(res.choices[0].message.content.strip())
    except:
        return 0

# ---------------- BAN TICKET ----------------

@bot.command()
async def banticket(ctx, user_id: int = None):

    if ctx.channel.id != ALLOWED_CHANNEL:
        return await ctx.send("❌ Mauvais salon.")

    if user_id is None:
        return await ctx.send("❌ !banticket <ID utilisateur>")

    member = ctx.guild.get_member(user_id)
    if not member:
        return await ctx.send("❌ Utilisateur introuvable.")

    ticket_id = str(random.randint(10000, 99999))

    data[ticket_id] = {
        "user_id": user_id,
        "creator_id": ctx.author.id,
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
            f"👤 Cible : <@{user_id}>\n"
            f"🎫 ID : **{ticket_id}**"
        )

    await ctx.send(f"🎫 Ticket créé : **{ticket_id}**")

# ---------------- APPEAL ----------------

@bot.command()
async def appeal(ctx, ticket_id: str):

    if ticket_id not in data:
        return await ctx.send("❌ Ticket invalide.")

    t = data[ticket_id]

    # 🔴 BLOQUAGE TOTAL
    if t.get("used") == True:
        return await ctx.send("❌ Code déjà utilisé.")

    if t.get("thread_id") is not None:
        return await ctx.send("❌ Un fil existe déjà pour ce ticket.")

    thread = await ctx.channel.create_thread(
        name=f"appeal-{ticket_id}",
        type=discord.ChannelType.public_thread
    )

    t["thread_id"] = thread.id
    t["status"] = "writing"

    save()

    await thread.send("✍️ Écris ta lettre directement ici.")

# ---------------- MESSAGE LISTENER ----------------

@bot.event
async def on_message(message):

    await bot.process_commands(message)

    if message.author.bot:
        return

    for ticket_id, t in data.items():

        if t.get("thread_id") == message.channel.id and t["status"] == "writing":

            # 🔴 BLOQUAGE SI DÉJÀ UTILISÉ
            if t.get("used"):
                return

            text = message.content
            score = get_score(text)

            t["letter"] = text
            t["score"] = score
            t["status"] = "analyzed"
            save()

            await message.channel.send(f"🤖 IA Mistral : **{score}/10**")

            report = bot.get_channel(REPORT_LETTERS)

            if report:
                await report.send(
                    f"📤 **LETTRE À TRAITER**\n"
                    f"🎫 ID : {ticket_id}\n"
                    f"🤖 Score : {score}/10\n"
                    f"📝 {text[:1000]}"
                )

            # 🔴 REFUS AUTO
            if score <= 4:
                t["used"] = True
                t["status"] = "auto_refused"
                save()

                await message.channel.send("❌ Refus automatique.")

                await asyncio.sleep(10)
                await message.channel.send("⏳ Fermeture...")
                await message.channel.delete()
                return

            # 🟡 ADMIN
            t["status"] = "pending_admin"
            save()

            await message.channel.send("📤 Envoyé aux admins.")
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

    t["used"] = True
    t["status"] = "accepted"
    save()

    await ctx.send("✔ Déban validé")

    if t["thread_id"]:
        ch = await bot.fetch_channel(t["thread_id"])
        await ch.send("✅ Accepté.")
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
        await ch.send("❌ Refusé.")
        await asyncio.sleep(10)
        await ch.delete()

# ---------------- RUN ----------------

bot.run(TOKEN)
