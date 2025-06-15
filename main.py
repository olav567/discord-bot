print("Starting bot...")

import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import os
import asyncio
from flask import Flask
import threading
import io
import random

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
intents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- Config ---
GUILD_ID = 1383416278256980151
ADMIN_ROLE_ID = 1383439184793960478
STAFF_ROLE_ID = 1383439184793960478
KLANT_ROLE_ID = 1383437786853539942
SUPERKLANT_ROLE_ID = 1383439183560970241
MUTED_ROLE_ID = 1383472481171542036
WARN_LOG_CHANNEL_ID = 1383883504579903548

CHANNEL_TICKET = "🎫︱ticket"
TICKET_CATEGORY_NAME = "🎫 Tickets"
CHANNEL_WELCOME = "👋︱welkom"
CHANNEL_LOGS = "📜︱ticket-logs"
CHANNEL_SERVER_STATUS = "👥│leden"
CHANNEL_REVIEWS_ID = 1383426131750817793

ROLE_NAMES = {
    "member": "Member",
    "klant": "Klant",
    "staff": "Staff Member",
}

def is_staff():
    async def predicate(interaction: discord.Interaction):
        return any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
    return app_commands.check(predicate)

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
        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.mention_everyone or "@evorony" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention}, je mag deze persoon niet mentionen.", delete_after=5)
    await bot.process_commands(message)

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

# ====== Commands =======

@tree.command(name="ticket", description="Stuur het ticketpaneel", guild=discord.Object(id=GUILD_ID))
async def ticket_command(interaction: discord.Interaction):
    class TicketView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="🎟 Support", style=discord.ButtonStyle.blurple)
        async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await create_ticket(interaction, "Support")

        @discord.ui.button(label="🛒 Bestelling", style=discord.ButtonStyle.green)
        async def bestelling_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await create_ticket(interaction, "Bestelling")

        @discord.ui.button(label="❗ Klacht", style=discord.ButtonStyle.red)
        async def klacht_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await create_ticket(interaction, "Klacht")

    await interaction.response.send_message("Tickets aanmaken — klik op een knop hieronder:", view=TicketView(), ephemeral=True)

async def create_ticket(interaction: discord.Interaction, onderwerp: str):
    guild = interaction.guild
    category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(TICKET_CATEGORY_NAME)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    channel = await guild.create_text_channel(f"ticket-{interaction.user.name}", category=category, overwrites=overwrites)
    await channel.send(f"{interaction.user.mention}, welkom bij je {onderwerp}-ticket! Een stafflid helpt je zo.")
    await interaction.response.send_message(f"Ticket aangemaakt: {channel.mention}", ephemeral=True)

@tree.command(name="sluit", description="Sluit een ticket", guild=discord.Object(id=GUILD_ID))
@is_staff()
async def sluit_command(interaction: discord.Interaction):
    channel = interaction.channel
    category = discord.utils.get(interaction.guild.categories, name=TICKET_CATEGORY_NAME)
    log_channel = discord.utils.get(interaction.guild.text_channels, name=CHANNEL_LOGS)

    if channel.category != category:
        await interaction.response.send_message("Dit is geen ticketkanaal.", ephemeral=True)
        return

    transcript = io.StringIO()
    async for msg in channel.history(limit=None, oldest_first=True):
        tijd = msg.created_at.strftime("[%Y-%m-%d %H:%M:%S]")
        transcript.write(f"{tijd} {msg.author.display_name}: {msg.content}\n")
    transcript.seek(0)
    bestand = discord.File(transcript, filename="transcript.txt")

    if log_channel:
        await log_channel.send(f"Transcript van {channel.name}", file=bestand)

    await interaction.response.send_message("Ticket wordt gesloten in 5 seconden...", ephemeral=True)
    await asyncio.sleep(5)
    await channel.delete()

@tree.command(name="verify", description="Verifieer jezelf", guild=discord.Object(id=GUILD_ID))
async def verify_command(interaction: discord.Interaction):
    class VerifyView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="✅ Verifieer mij", style=discord.ButtonStyle.green)
        async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
            role = discord.utils.get(interaction.guild.roles, name=ROLE_NAMES["member"])
            if role:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("✅ Je bent geverifieerd!", ephemeral=True)

    await interaction.response.send_message("Klik om jezelf te verifiëren:", view=VerifyView(), ephemeral=True)

@tree.command(name="review", description="Laat een review achter", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(sterren="Aantal sterren", bericht="Je review")
async def review(interaction: discord.Interaction, sterren: int, bericht: str):
    channel = interaction.guild.get_channel(CHANNEL_REVIEWS_ID)
    if channel:
        embed = discord.Embed(title="Review", description=bericht, color=discord.Color.gold())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Beoordeling", value="⭐" * sterren)
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Review verstuurd!", ephemeral=True)

@tree.command(name="warn", description="Waarschuw een gebruiker", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.describe(lid="Wie wil je waarschuwen?", reden="Waarom?")
async def warn(interaction: discord.Interaction, lid: discord.Member, reden: str):
    log = interaction.guild.get_channel(WARN_LOG_CHANNEL_ID)
    embed = discord.Embed(title="⚠️ Waarschuwing", description=reden, color=discord.Color.orange())
    embed.set_author(name=lid.name, icon_url=lid.display_avatar.url)
    embed.set_footer(text=f"Gewaarschuwd door: {interaction.user.display_name}")
    await log.send(embed=embed)
    try:
        await lid.send(f"Je bent gewaarschuwd op **{interaction.guild.name}**: {reden}")
    except:
        pass
    await interaction.response.send_message(f"{lid.mention} is gewaarschuwd.", ephemeral=True)

@tree.command(name="kick", description="Kick een gebruiker", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.describe(lid="Wie wil je kicken?", reden="Waarom?")
async def kick(interaction: discord.Interaction, lid: discord.Member, reden: str):
    await lid.kick(reason=reden)
    await interaction.response.send_message(f"{lid} is gekickt.", ephemeral=True)

@tree.command(name="ban", description="Ban een gebruiker", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.describe(lid="Wie wil je bannen?", reden="Waarom?")
async def ban(interaction: discord.Interaction, lid: discord.Member, reden: str):
    await lid.ban(reason=reden)
    await interaction.response.send_message(f"{lid} is verbannen.", ephemeral=True)

@tree.command(name="clear", description="Verwijder berichten", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.describe(aantal="Aantal berichten")
async def clear(interaction: discord.Interaction, aantal: int):
    await interaction.channel.purge(limit=aantal + 1)
    await interaction.response.send_message(f"🧹 {aantal} berichten verwijderd!", ephemeral=True)

@tree.command(name="giveaway", description="Start een giveaway", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.describe(tijd="Tijd in seconden", prijs="Wat kunnen ze winnen?")
async def giveaway(interaction: discord.Interaction, tijd: int, prijs: str):
    await interaction.response.send_message(f"🎉 Giveaway gestart voor **{prijs}**! Reacteer met 🎉 om mee te doen. ({tijd} sec)")
    msg = await interaction.channel.send(f"🎉 **GIVEAWAY** 🎉\nPrijs: **{prijs}**\nReacteer hieronder met 🎉 om mee te doen!")
    await msg.add_reaction("🎉")

    await asyncio.sleep(tijd)
    msg = await interaction.channel.fetch_message(msg.id)
    users = await msg.reactions[0].users().flatten()
    users = [u for u in users if not u.bot]
    if users:
        winnaar = random.choice(users)
        await interaction.channel.send(f"🥳 De winnaar is {winnaar.mention}! Gefeliciteerd met **{prijs}**!")
    else:
        await interaction.channel.send("Niemand heeft meegedaan 😢")

# --- Start webserver ---
start_webserver()

# --- Start bot ---
bot.run(os.getenv("DISCORD_TOKEN"))
