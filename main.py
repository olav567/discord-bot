print("Starting bot...")

import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import os
from flask import Flask
import threading

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

GUILD_ID = 1383416278256980151
ADMIN_ROLE_ID = 1383439184793960478
STAFF_ROLE_ID = 1383439184793960478  # Check of dit klopt
KLANT_ROLE_ID = 1383437786853539942
SUPERKLANT_ROLE_ID = 1383439183560970241
MUTED_ROLE_ID = 1383472481171542036

CHANNEL_TICKET = "🎫︱ticket"
TICKET_CATEGORY_NAME = "🎫 Tickets"
CHANNEL_WELCOME = "👋︱welkom"
CHANNEL_LOGS = "📜︱ticket-logs"
CHANNEL_SERVER_STATUS = "👥│leden"
CHANNEL_REVIEWS = "⭐︱reviews"

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
        await channel.send(f"Welkom bij de server, {member.mention}! 🎉")

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

    channel = discord.utils.get(interaction.guild.channels, name=CHANNEL_TICKET)
    if channel:
        await channel.send("Tickets aanmaken — klik op een knop hieronder:", view=TicketView())
        await interaction.response.send_message("Ticketpaneel gestuurd!", ephemeral=True)
    else:
        await interaction.response.send_message("Ticketkanaal niet gevonden!", ephemeral=True)

async def create_ticket(interaction: discord.Interaction, ticket_type: str):
    guild = interaction.guild
    member = interaction.user

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.get_role(ADMIN_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),  # i.p.v. bot.user
    }

    category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(TICKET_CATEGORY_NAME)

    channel_name = f"ticket-{ticket_type.lower()}-{member.name}".replace(" ", "-")
    existing_channel = discord.utils.get(guild.channels, name=channel_name)
    if existing_channel:
        await interaction.response.send_message(f"Je hebt al een openstaand ticket: {existing_channel.mention}", ephemeral=True)
        return

    channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
    await channel.send(f"Hallo {member.mention}, bedankt voor je {ticket_type.lower()} ticket! Een stafflid komt zo bij je kijken.")
    await interaction.response.send_message(f"Ticket geopend: {channel.mention}", ephemeral=True)

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

@tree.command(name="sluit", description="Sluit een ticketkanaal", guild=discord.Object(id=GUILD_ID))
async def sluit_command(interaction: discord.Interaction):
    if interaction.channel.name.startswith("ticket-"):
        logs_channel = discord.utils.get(interaction.guild.text_channels, name=CHANNEL_LOGS)
        messages = []
        async for msg in interaction.channel.history(limit=100, oldest_first=True):
            messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author}: {msg.content}")
        log_text = f"Ticket {interaction.channel.name} gesloten door {interaction.user}\n\n" + "\n".join(messages)

        if logs_channel:
            for chunk in [log_text[i:i+1990] for i in range(0, len(log_text), 1990)]:
                await logs_channel.send(f"```{chunk}```")

        await interaction.response.send_message("Ticket wordt gesloten...")
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("Dit commando werkt alleen in een ticketkanaal.", ephemeral=True)

@tree.command(name="ban", description="Ban een gebruiker", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Gebruiker die je wilt bannen", reden="Reden van ban")
async def ban_command(interaction: discord.Interaction, member: discord.Member, reden: str):
    if STAFF_ROLE_ID in [role.id for role in interaction.user.roles]:
        await member.ban(reason=reden)
        await interaction.response.send_message(f"{member.mention} is verbannen. ✈️")
    else:
        await interaction.response.send_message("Je hebt geen toestemming om dit te doen.", ephemeral=True)

@tree.command(name="timeout", description="Geef een gebruiker een timeout", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Gebruiker", minuten="Aantal minuten")
async def timeout_command(interaction: discord.Interaction, member: discord.Member, minuten: int):
    if STAFF_ROLE_ID in [role.id for role in interaction.user.roles]:
        until = datetime.datetime.utcnow() + datetime.timedelta(minutes=minuten)
        await member.timeout(until)
        await interaction.response.send_message(f"{member.mention} is in timeout voor {minuten} minuten.")
    else:
        await interaction.response.send_message("Je hebt geen toestemming om dit te doen.", ephemeral=True)

@tree.command(name="review", description="Laat een review achter", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(sterren="Aantal sterren", bericht="Jouw review")
async def review_command(interaction: discord.Interaction, sterren: int, bericht: str):
    channel = discord.utils.get(interaction.guild.text_channels, name=CHANNEL_REVIEWS)
    if channel:
        sterren_emoji = "⭐" * min(5, max(1, sterren))
        embed = discord.Embed(title="Nieuwe review", description=bericht, color=discord.Color.gold())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Beoordeling", value=sterren_emoji, inline=False)
        await channel.send(embed=embed)
        await interaction.response.send_message("Je review is verstuurd! Bedankt ❤️", ephemeral=True)
    else:
        await interaction.response.send_message("Reviewkanaal niet gevonden.", ephemeral=True)

@tree.command(name="embed", description="Stuur een embed via de bot", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(titel="Titel van de embed", beschrijving="Beschrijving in de embed", kleur="Hex kleurcode (bv. #ff0000)")
async def embed_command(interaction: discord.Interaction, titel: str, beschrijving: str, kleur: str = "#00ff00"):
    try:
        kleur_int = int(kleur.replace("#", ""), 16)
        embed = discord.Embed(title=titel, description=beschrijving, color=kleur_int)
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Embed succesvol gestuurd!", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Ongeldige kleurcode. Gebruik bijvoorbeeld: #ff0000", ephemeral=True)

# --- Start Flask webserver om poort open te houden ---
start_webserver()

# --- Start Discord bot ---
bot.run(os.getenv("DISCORD_TOKEN"))
