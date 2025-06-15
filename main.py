print("Starting bot...")

import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import os
from flask import Flask
import threading
import asyncio

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
WARN_LOG_CHANNEL = 1383883504579903548

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
    await bot.wait_until_ready()
    guild = bot.get_guild(GUILD_ID)
    if guild:
        total_members = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)
        for channel in guild.channels:
            if channel.name.startswith("👥│leden"):
                try:
                    await channel.edit(name=f"👥│Leden: {total_members} | Bots: {bots} | Online: {online}")
                except:
                    pass

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

@tree.command(name="verify", description="Stuur een verify knop", guild=discord.Object(id=GUILD_ID))
async def verify_command(interaction: discord.Interaction):
    class VerifyView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="✅ Verifieer mij", style=discord.ButtonStyle.green)
        async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            role = discord.utils.get(interaction.guild.roles, name=ROLE_NAMES["member"])
            if role and role not in interaction.user.roles:
                await interaction.user.add_roles(role)
            await interaction.response.send_message("Je bent succesvol geverifieerd!", ephemeral=True)

    await interaction.response.send_message("Klik op de knop om jezelf te verifiëren:", view=VerifyView(), ephemeral=True)

@tree.command(name="review", description="Laat een review achter", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(sterren="Aantal sterren", bericht="Jouw review")
async def review_command(interaction: discord.Interaction, sterren: int, bericht: str):
    channel = interaction.guild.get_channel(CHANNEL_REVIEWS_ID)
    if channel:
        sterren_emoji = "⭐" * min(5, max(1, sterren))
        embed = discord.Embed(title="Nieuwe review", description=bericht, color=discord.Color.gold())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Beoordeling", value=sterren_emoji, inline=False)
        await channel.send(embed=embed)
        await interaction.response.send_message("Je review is verstuurd! Bedankt ❤️", ephemeral=True)
    else:
        await interaction.response.send_message("Reviewkanaal niet gevonden.", ephemeral=True)

# --- Start webserver ---
start_webserver()

# --- Start Discord bot ---
bot.run(os.getenv("DISCORD_TOKEN"))

