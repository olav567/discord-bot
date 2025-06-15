print("Starting bot...")

import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import os
from flask import Flask
import threading
import asyncio
import io
import textwrap

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

# --- Utility: transcript maken voor tickets ---
async def create_transcript(channel: discord.TextChannel) -> io.BytesIO:
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        time = msg.created_at.strftime("%Y-%m-%d %H:%M")
        author = msg.author.display_name
        content = msg.content
        messages.append(f"[{time}] {author}: {content}")
    transcript_text = "\n".join(messages)
    transcript_file = io.BytesIO(transcript_text.encode("utf-8"))
    transcript_file.name = f"transcript-{channel.name}.txt"
    return transcript_file

# --- Ticket maken functie ---
async def create_ticket(interaction: discord.Interaction, category_name: str):
    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        discord.utils.get(guild.roles, id=STAFF_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(TICKET_CATEGORY_NAME)

    # Check als gebruiker al ticket heeft
    for channel in category.channels:
        if channel.name == f"ticket-{interaction.user.name}".lower():
            await interaction.response.send_message(f"Je hebt al een open ticket: {channel.mention}", ephemeral=True)
            return

    channel = await category.create_text_channel(f"ticket-{interaction.user.name}".lower(), overwrites=overwrites)
    embed = discord.Embed(title=f"Nieuw ticket: {category_name}", description=f"{interaction.user.mention}, welkom! Een staff lid komt zo bij je.", color=discord.Color.blue())
    await channel.send(embed=embed)
    await interaction.response.send_message(f"Ticket aangemaakt: {channel.mention}", ephemeral=True)

# --- Anti-@mention spam filter ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.mentions:
        for user in message.mentions:
            if user.id == bot.user.id:
                # Bijvoorbeeld 3x pingen verbieden in 10 seconden (voorbeeld)
                # Dit kan uitgebreid worden met cooldowns etc.
                await message.delete()
                warn_channel = bot.get_channel(WARN_LOG_CHANNEL)
                if warn_channel:
                    await warn_channel.send(f"🛑 {message.author.mention} probeerde de bot te spammen met mentions.")
                return
    await bot.process_commands(message)

# --- Bot events ---
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

# --- Server status updaten ---
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

# --- Commands ---

# /verify command
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

# /ticket command
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

    await interaction.response.send_message(
        "Tickets aanmaken — klik op een knop hieronder:",
        view=TicketView(),
        ephemeral=True
    )

# /review command
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

# /warn command
@tree.command(name="warn", description="Waarschuw een gebruiker", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(gebruiker="Gebruiker om te waarschuwen", reden="Reden van de waarschuwing")
@commands.has_permissions(manage_messages=True)
async def warn_command(interaction: discord.Interaction, gebruiker: discord.Member, reden: str):
    await gebruiker.send(f"⚠️ Je bent gewaarschuwd op **{interaction.guild.name}** door {interaction.user}.\nReden: {reden}")
    channel = interaction.guild.get_channel(WARN_LOG_CHANNEL)
    if channel:
        embed = discord.Embed(title="Gebruiker gewaarschuwd", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Gebruiker", value=gebruiker.mention, inline=True)
        embed.add_field(name="Door", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reden", value=reden, inline=False)
        await channel.send(embed=embed)
    await interaction.response.send_message(f"{gebruiker.mention} is gewaarschuwd!", ephemeral=True)

# /kick command
@tree.command(name="kick", description="Kick een gebruiker", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(gebruiker="Gebruiker om te kicken", reden="Reden van de kick")
@commands.has_permissions(kick_members=True)
async def kick_command(interaction: discord.Interaction, gebruiker: discord.Member, reden: str = "Geen reden opgegeven"):
    await gebruiker.kick(reason=reden)
    await interaction.response.send_message(f"{gebruiker.mention} is gekickt. Reden: {reden}", ephemeral=True)

# /ban command
@tree.command(name="ban", description="Ban een gebruiker", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(gebruiker="Gebruiker om te bannen", reden="Reden van de ban")
@commands.has_permissions(ban_members=True)
async def ban_command(interaction: discord.Interaction, gebruiker: discord.Member, reden: str = "Geen reden opgegeven"):
    await gebruiker.ban(reason=reden)
    await interaction.response.send_message(f"{gebruiker.mention} is gebanned. Reden: {reden}", ephemeral=True)

# /clear command
@tree.command(name="clear", description="Verwijder berichten", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(aantal="Aantal berichten om te verwijderen")
@commands.has_permissions(manage_messages=True)
async def clear_command(interaction: discord.Interaction, aantal: int):
    deleted = await interaction.channel.purge(limit=aantal)
    await interaction.response.send_message(f"{len(deleted)} berichten verwijderd.", ephemeral=True)

# /giveaway command
@tree.command(name="giveaway", description="Start een giveaway", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(duur="Duur van giveaway in seconden", prijs="Prijs van de giveaway")
@commands.has_permissions(manage_guild=True)
async def giveaway_command(interaction: discord.Interaction, duur: int, prijs: str):
    class GiveawayView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=duur)

        @discord.ui.button(label="🎉 Doe mee!", style=discord.ButtonStyle.green)
        async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id in self.participants:
                await interaction.response.send_message("Je doet al mee aan deze giveaway!", ephemeral=True)
            else:
                self.participants.add(interaction.user.id)
                await interaction.response.send_message("Je doet nu mee aan de giveaway!", ephemeral=True)

        async def on_timeout(self):
            if self.participants:
                winner_id = random.choice(list(self.participants))
                winner = bot.get_user(winner_id)
                if winner:
                    await self.message.channel.send(f"🎉 Gefeliciteerd {winner.mention}! Je hebt gewonnen: **{prijs}**")
                else:
                    await self.message.channel.send(f"🎉 Giveaway is afgelopen! Geen winnaar gevonden.")
            else:
                await self.message.channel.send("🎉 Giveaway is afgelopen! Er waren geen deelnemers.")
            self.stop()

    view = GiveawayView()
    view.participants = set()
    msg = await interaction.channel.send(f"🎉 **Giveaway gestart!** Prijs: **{prijs}**\nKlik op de knop om mee te doen! Duur: {duur} seconden.", view=view)
    view.message = msg
    await interaction.response.send_message("Giveaway gestart!", ephemeral=True)

# /sluit command - ticket sluiten met transcript
@tree.command(name="sluit", description="Sluit een ticket en maak transcript", guild=discord.Object(id=GUILD_ID))
@commands.has_permissions(manage_channels=True)
async def sluit_command(interaction: discord.Interaction):
    channel = interaction.channel
    if channel.category and channel.category.name == TICKET_CATEGORY_NAME:
        transcript = await create_transcript(channel)
        log_channel = discord.utils.get(interaction.guild.text_channels, name=CHANNEL_LOGS)
        if log_channel:
            await log_channel.send(file=discord.File(fp=transcript, filename=transcript.name), content=f"Ticket gesloten door {interaction.user.mention}: {channel.name}")
        await channel.delete()
    else:
        await interaction.response.send_message("Dit commando kan alleen gebruikt worden in een ticketkanaal.", ephemeral=True)

# Start de webserver (voor keep-alive)
start_webserver()

# Run de bot
bot.run(os.getenv("DISCORD_TOKEN"))

