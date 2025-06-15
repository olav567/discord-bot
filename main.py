print("Starting bot...")

import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import os
from flask import Flask
import threading
import asyncio
import re
from collections import defaultdict

# --- Flask app voor keep-alive en open poort ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_webserver():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

def start_webserver():
    t = threading.Thread(target=run_webserver)
    t.start()

# --- Discord bot setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- Config ---
GUILD_ID = 1383416278256980151
ADMIN_ROLE_ID = 1383439184793960478
STAFF_ROLE_ID = 1383439184793960478
KLANT_ROLE_ID = 1383437786853539942
SUPERKLANT_ROLE_ID = 1383439183560970241
MUTED_ROLE_ID = 1383472481171542036

CHANNEL_TICKET = "🎫︱ticket"
TICKET_CATEGORY_NAME = "🎫 Tickets"
CHANNEL_WELCOME = "👋︱welkom"
CHANNEL_LOGS = "📜︱ticket-logs"
CHANNEL_SERVER_STATUS = "👥│leden"
CHANNEL_REVIEWS_ID = 1383426131750817793
CHANNEL_WARN_LOGS_ID = 1383883504579903548

ROLE_NAMES = {
    "member": "Member",
    "klant": "Klant",
    "staff": "Staff Member",
}

# --- Globals voor spam en caps filter ---
mention_tracker = defaultdict(list)  # user_id: [timestamps]
MENTION_LIMIT = 5   # max mentions in interval
MENTION_INTERVAL = 10  # seconden
CAPS_THRESHOLD = 0.7  # >70% caps
CAPS_MIN_LENGTH = 5

@bot.event
async def on_ready():
    print(f"Bot is ingelogd als {bot.user}")
    update_server_status.start()
    await tree.sync(guild=discord.Object(id=GUILD_ID))

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name=CHANNEL_WELCOME)
    if channel:
        embed = discord.Embed(
            title="Welkom!",
            description=f"{member.mention} is zojuist toegetreden tot de server! 🎉",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Veel plezier!", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        await channel.send(embed=embed)

@tasks.loop(minutes=5)
async def update_server_status():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    total_members = guild.member_count
    bots = sum(1 for m in guild.members if m.bot)
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)
    channel = discord.utils.get(guild.channels, name=CHANNEL_SERVER_STATUS)
    if channel:
        await channel.edit(name=f"👥│Leden: {total_members} | Bots: {bots} | Online: {online}")

# Caps-lock filter + mention spam limiter
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Caps-lock filter
    content = message.content
    if len(content) >= CAPS_MIN_LENGTH:
        letters = re.findall(r'[A-Za-z]', content)
        if letters:
            caps_count = sum(1 for c in letters if c.isupper())
            ratio = caps_count / len(letters)
            if ratio > CAPS_THRESHOLD:
                try:
                    await message.delete()
                except:
                    pass
                await message.channel.send(f"{message.author.mention}, let op met caps-lock gebruik! Gebruik geen berichten met teveel hoofdletters.", delete_after=10)
                return

    # Mention spam limiter
    mentions = message.mentions
    now = datetime.datetime.utcnow().timestamp()
    user_id = message.author.id

    # Update mention timestamps
    mention_times = mention_tracker[user_id]
    mention_times = [t for t in mention_times if now - t < MENTION_INTERVAL]
    mention_times.extend([now] * len(mentions))
    mention_tracker[user_id] = mention_times

    if len(mention_times) > MENTION_LIMIT:
        # Mute user kort of waarschuwen
        muted_role = message.guild.get_role(MUTED_ROLE_ID)
        if muted_role and muted_role not in message.author.roles:
            try:
                await message.author.add_roles(muted_role, reason="Mention spam limiter")
                await message.channel.send(f"{message.author.mention} is tijdelijk gemute vanwege te veel @mentions.", delete_after=15)
            except Exception as e:
                print(f"Fout bij muten: {e}")
        else:
            await message.channel.send(f"{message.author.mention}, stop met te veel @mentions spammen!", delete_after=10)
        try:
            await message.delete()
        except:
            pass
        mention_tracker[user_id] = []  # reset na actie
        return

    await bot.process_commands(message)

# --- Server Statistieken Dashboard command ---
@tree.command(name="stats", description="Bekijk server statistieken", guild=discord.Object(id=GUILD_ID))
async def stats_command(interaction: discord.Interaction):
    roles_staff = [ADMIN_ROLE_ID, STAFF_ROLE_ID]
    user_roles = [role.id for role in interaction.user.roles]
    if not any(role in user_roles for role in roles_staff):
        await interaction.response.send_message("Je hebt geen toestemming voor deze command.", ephemeral=True)
        return

    guild = interaction.guild
    total_members = guild.member_count
    bots = sum(1 for m in guild.members if m.bot)
    online_members = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
    text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])

    embed = discord.Embed(title=f"Server Statistieken van {guild.name}", color=discord.Color.blurple())
    embed.add_field(name="Totaal aantal leden", value=str(total_members))
    embed.add_field(name="Aantal bots", value=str(bots))
    embed.add_field(name="Aantal online leden", value=str(online_members))
    embed.add_field(name="Aantal text-kanalen", value=str(text_channels))
    embed.add_field(name="Aantal voice-kanalen", value=str(voice_channels))
    embed.set_footer(text=f"Opgevraagd door {interaction.user}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Hier volgen je bestaande commands (ticket, verify, review, poll, warn, giveaway, etc)
# Voor de overzichtelijkheid voeg ik hier alleen de nieuwe commands toe.
# Voeg deze dus toe aan je bestaande script waar de andere commando’s staan.

# --- Ticket command (zoals in jouw script) ---
# --- Verify command ---
# --- Review command ---
# --- Poll command ---
# --- Warn command ---
# --- Giveaway command ---
# (Deze commands zijn zoals in je eerdere script, voeg je zelf toe of laat weten als je ze wil samengevoegd hebben)

# --- Start webserver (Render vereist open poort) ---
start_webserver()

# --- Start Discord bot ---
bot.run(os.getenv("DISCORD_TOKEN"))
