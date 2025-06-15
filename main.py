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

# --- Warn command ---
@tree.command(name="warn", description="Waarschuw een gebruiker", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="De gebruiker om te waarschuwen", reden="Reden voor de waarschuwing")
async def warn_command(interaction: discord.Interaction, user: discord.Member, reden: str):
    # Check permissies
    roles_staff = [ADMIN_ROLE_ID, STAFF_ROLE_ID]
    user_roles = [role.id for role in interaction.user.roles]
    if not any(role in user_roles for role in roles_staff):
        await interaction.response.send_message("Je hebt geen toestemming om deze command te gebruiken.", ephemeral=True)
        return

    # Waarschuwing sturen
    try:
        embed_dm = discord.Embed(title="Je bent gewaarschuwd!", color=discord.Color.red())
        embed_dm.add_field(name="Server", value=interaction.guild.name, inline=False)
        embed_dm.add_field(name="Reden", value=reden, inline=False)
        embed_dm.set_footer(text="Neem contact op met het staffteam bij vragen.")
        await user.send(embed=embed_dm)
    except Exception:
        # DM mislukte (misschien uitgeschakeld)
        pass

    # Bericht naar log kanaal
    kanaal = bot.get_channel(CHANNEL_WARN_LOGS_ID)
    if kanaal:
        embed_log = discord.Embed(title="Gebruiker gewaarschuwd", color=discord.Color.orange())
        embed_log.add_field(name="Gebruiker", value=f"{user} ({user.id})", inline=False)
        embed_log.add_field(name="Door", value=f"{interaction.user} ({interaction.user.id})", inline=False)
        embed_log.add_field(name="Reden", value=reden, inline=False)
        embed_log.timestamp = datetime.datetime.utcnow()
        await kanaal.send(embed=embed_log)

    await interaction.response.send_message(f"{user.mention} is gewaarschuwd.", ephemeral=True)

# --- Ticket command ---
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

async def create_ticket(interaction: discord.Interaction, type_ticket: str):
    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    staff_role = discord.utils.get(guild.roles, id=STAFF_ROLE_ID)
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(TICKET_CATEGORY_NAME)

    channel_name = f"ticket-{interaction.user.name}-{type_ticket}".lower()
    existing = discord.utils.get(category.channels, name=channel_name)
    if existing:
        await interaction.response.send_message(f"Je hebt al een open ticket: {existing.mention}", ephemeral=True)
        return

    channel = await category.create_text_channel(channel_name, overwrites=overwrites)

    embed = discord.Embed(title=f"Ticket: {type_ticket}", description=f"Hallo {interaction.user.mention}, het staffteam zal je zo spoedig mogelijk helpen.", color=discord.Color.blue())
    await channel.send(content=interaction.user.mention, embed=embed)
    await interaction.response.send_message(f"Ticket aangemaakt: {channel.mention}", ephemeral=True)

# --- Verify command ---
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

# --- Review command ---
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

# --- Giveaway command ---
@tree.command(name="giveaway", description="Host een giveaway", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(tijd="Duur van de giveaway in seconden", prijs="Prijs van de giveaway")
async def giveaway_command(interaction: discord.Interaction, tijd: int, prijs: str):
    embed = discord.Embed(title="🎉 Giveaway gestart! 🎉", description=f"Prijs: **{prijs}**\nReact met 🎉 om mee te doen!", color=discord.Color.green())
    embed.set_footer(text=f"Eindigt over {tijd} seconden")

    message = await interaction.channel.send(embed=embed)
    await message.add_reaction("🎉")

    await interaction.response.send_message(f"Giveaway gestart voor {tijd} seconden!", ephemeral=True)

    await asyncio.sleep(tijd)

    message = await interaction.channel.fetch_message(message.id)  # fetch opnieuw voor reacties

    users = set()
    for reaction in message.reactions:
        if str(reaction.emoji) == "🎉":
            async for user in reaction.users():
                if user.bot:
                    continue
                users.add(user)

    if users:
        winnaar = random.choice(list(users))
        await interaction.channel.send(f"🎉 Gefeliciteerd {winnaar.mention}, je hebt de giveaway gewonnen voor **{prijs}**! 🎉")
    else:
        await interaction.channel.send("Geen deelnemers voor de giveaway, er is geen winnaar.")

# --- Start webserver (Render vereist open poort) ---
start_webserver()

# --- Start Discord bot ---
bot.run(os.getenv("DISCORD_TOKEN"))
