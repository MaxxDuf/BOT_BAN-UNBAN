import discord
from discord.ext import commands, tasks
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

    digits = "".join(filter(str.isdigit, duration))
    time_value = int(digits) if digits else 1

    if "j" in duration:
        expires_at = datetime.utcnow() + timedelta(days=time_value)
    elif "h" in duration:
        expires_at = datetime.utcnow() + timedelta(hours=time_value)
    else:
        expires_at = datetime.utcnow() + timedelta(days=1)

    try:
        member = await ctx.guild.fetch_member(user_id)
        await member.ban(reason=reason)
    except:
        pass

    # SAUVEGARDE CORRECTE
    data[ticket_id] = {
        "user_id": user_id,
        "reason": reason,
        "duration": duration,
        "expires_at": expires_at.timestamp(),
        "status": "banned",
        "used": False,
        "thread_id": None,
        "letter": None
    }

    save()

    # ---------------- DM FIX ----------------

    try:
        await user.send(
            f"🚫 Vous avez été banni\n\n"
            f"📌 Raison: {reason}\n"
            f"⏳ Durée: {duration}\n"
            f"🎫 Ticket: {ticket_id}\n\n"
            f"Commande: !appeal {ticket_id}"
        )
    except discord.Forbidden:
        await ctx.send("⚠️ MP bloqué pour cet utilisateur.")
    except:
        await ctx.send("⚠️ Impossible d'envoyer le MP.")

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

        report = bot.get_channel(REPORT_LETTERS)

        if report:
            await report.send(
                f"📤 LETTRE\n"
                f"🎫 {ticket_id}\n"
                f"📝 {message.content[:1500]}"
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

    t["status"] = "accepted"
    t["used"] = True
    save()

    await ctx.send("✔ Déban accepté")

    if t.get("thread_id"):
        ch = await bot.fetch_channel(t["thread_id"])
        await ch.send("✅ Accepté")
        await asyncio.sleep(5)
        await ch.delete()

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

    await ctx.send("❌ Refus")

    if t.get("thread_id"):
        ch = await bot.fetch_channel(t["thread_id"])
        await ch.send("❌ Refusé")
        await asyncio.sleep(5)
        await ch.delete()

# ---------------- UNBAN SYSTEM ----------------

@tasks.loop(minutes=1)
async def unban_check():

    now = datetime.utcnow().timestamp()

    for ticket_id, t in list(data.items()):

        if t.get("status") != "banned":
            continue

        if now < t.get("expires_at", 0):
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

        except:
            pass

@bot.event
async def on_ready():
    unban_check.start()
    print("Bot prêt")

# ---------------- RUN ----------------

bot.run(TOKEN)
