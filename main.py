import psycopg2
import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
from threading import Thread

# Bot setup - Enable required intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Command tree for slash commands
tree = bot.tree

# Tracks claimed tickets per server (guild)
claimed_tickets = {}

# Instead of single global variables, store per guild
# Dictionary: guild_id -> list of role IDs
required_roles_per_guild = {}
# Dictionary: guild_id -> target channel ID
target_channel_per_guild = {}

# Authorized user ID for bot configuration commands
AUTHORIZED_USER_ID = 1005902785067372555

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')

async def init_database():
    """Initialize database tables"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                guild_id BIGINT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, key)
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

async def load_data_from_db():
    """Load settings from database for all guilds"""
    global required_roles_per_guild, target_channel_per_guild
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("SELECT guild_id, value FROM bot_settings WHERE key = 'required_role_ids'")
        rows = cur.fetchall()
        for guild_id, value in rows:
            role_ids = [int(rid) for rid in value.split(',') if rid.strip().isdigit()]
            required_roles_per_guild[guild_id] = role_ids
            print(f"Loaded required roles for guild {guild_id}: {role_ids}")

        cur.execute("SELECT guild_id, value FROM bot_settings WHERE key = 'target_channel_id'")
        rows = cur.fetchall()
        for guild_id, value in rows:
            try:
                channel_id = int(value)
                target_channel_per_guild[guild_id] = channel_id
                print(f"Loaded target channel for guild {guild_id}: {channel_id}")
            except Exception:
                print(f"Invalid channel id stored for guild {guild_id}: {value}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error loading data from database: {e}")

async def save_required_roles_to_db(guild_id, role_ids):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        role_ids_str = ','.join(str(rid) for rid in role_ids)
        cur.execute('''
            INSERT INTO bot_settings (guild_id, key, value)
            VALUES (%s, 'required_role_ids', %s)
            ON CONFLICT (guild_id, key)
            DO UPDATE SET value = EXCLUDED.value
        ''', (guild_id, role_ids_str))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving required roles to database: {e}")

async def save_target_channel_to_db(guild_id, channel_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO bot_settings (guild_id, key, value)
            VALUES (%s, 'target_channel_id', %s)
            ON CONFLICT (guild_id, key)
            DO UPDATE SET value = EXCLUDED.value
        ''', (guild_id, str(channel_id)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving target channel to database: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    await init_database()
    await load_data_from_db()
    await bot.tree.sync()
    print("Slash commands synced!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name and message.channel.name.startswith('ticket-'):
        guild_id = message.guild.id
        if guild_id not in claimed_tickets:
            claimed_tickets[guild_id] = set()

        if message.channel.id not in claimed_tickets[guild_id] and await user_has_required_role(message):
            target_channel_id = target_channel_per_guild.get(guild_id)
            if target_channel_id:
                claimed_tickets[guild_id].add(message.channel.id)
                await forward_message_to_channel(message, target_channel_id)
            else:
                print(f"No target channel set for guild {guild_id}")

    await bot.process_commands(message)

async def user_has_required_role(message):
    guild_id = message.guild.id
    required_role_ids = required_roles_per_guild.get(guild_id, [])
    if not required_role_ids:
        print(f"No required roles set for guild {guild_id}. Use !loggerrole to set them.")
        return False
    member = message.guild.get_member(message.author.id)
    if member:
        return any(role.id in required_role_ids for role in member.roles)
    return False

async def forward_message_to_channel(message, target_channel_id):
    try:
        target_channel = bot.get_channel(target_channel_id)
        if target_channel:
            forwarded_message = (
                "------------------------------\n"
                f"Ticket Number : {message.channel.name}\n"
                f"Staff Who Claimed : {message.author.mention}\n"
                f"Typed : {message.content}"
            )
            await target_channel.send(forwarded_message)
        else:
            print(f"Target channel {target_channel_id} not found")
    except Exception as e:
        print(f"Error forwarding message: {e}")

app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Bot is running!"

@app.route('/status')
def status():
    return {
        "status": "online",
        "bot_name": str(bot.user) if bot.user else "Not connected",
        "guilds": len(bot.guilds) if bot.is_ready() else 0
    }

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

def keep_alive():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask server started on port 5000")

# Commands
@bot.command(name='ping')
async def ping_command(ctx):
    await ctx.send(f'Pong! Latency: {round(bot.latency * 1000)}ms')

@bot.command(name='send_to_channel')
async def send_to_channel(ctx, channel_id: int, *, message):
    try:
        target_channel = bot.get_channel(channel_id)
        if target_channel:
            await target_channel.send(message)
            await ctx.send(f"Message sent to {target_channel.name}!")
        else:
            await ctx.send("Channel not found or bot doesn't have access to it.")
    except Exception as e:
        await ctx.send(f"Error sending message: {e}")

@bot.command(name='loggerrole')
async def logger_role(ctx, *roles: discord.Role):
    guild_id = ctx.guild.id
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    if not roles:
        await ctx.send("❌ Please mention at least one role. Example: !loggerrole @staff @support")
        return

    role_ids = [role.id for role in roles]
    required_roles_per_guild[guild_id] = role_ids

    try:
        await save_required_roles_to_db(guild_id, role_ids)
        mentions = ' '.join(role.mention for role in roles)
        await ctx.send(f"✅ Logger roles set to: {mentions}\nOnly users with **any** of these roles will have their ticket messages forwarded.")
    except Exception as e:
        await ctx.send(f"❌ Failed to save roles: {e}")

@bot.command(name='loggerchannel')
async def logger_channel(ctx, channel_id: int):
    guild_id = ctx.guild.id
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    try:
        channel = bot.get_channel(channel_id)
        if channel and channel.guild.id == guild_id:
            target_channel_per_guild[guild_id] = channel_id
            await save_target_channel_to_db(guild_id, channel_id)
            await ctx.send(f"✅ Logger channel set to: {channel.mention} ({channel.name})\nTicket messages will be forwarded to this channel.")
        else:
            await ctx.send("❌ Channel not found in this server or bot doesn't have access to it. Please check the channel ID.")
    except Exception as e:
        await ctx.send(f"❌ Invalid channel ID format or error: {e}")

@tree.command(name="loggerchannel", description="Set the logger channel for ticket messages")
@app_commands.describe(channel="Select a text channel")
async def slash_loggerchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild.id
    if interaction.user.id != AUTHORIZED_USER_ID:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    target_channel_per_guild[guild_id] = channel.id
    await save_target_channel_to_db(guild_id, channel.id)
    await interaction.response.send_message(f"✅ Logger channel set to: {channel.mention}", ephemeral=True)

@tree.command(name="loggerrole", description="Select roles that can forward tickets")
async def slash_loggerrole(interaction: discord.Interaction):
    guild = interaction.guild
    if interaction.user.id != AUTHORIZED_USER_ID:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    options = [
        discord.SelectOption(label=role.name, value=str(role.id))
        for role in guild.roles if role != guild.default_role
    ]

    class RoleSelect(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.add_item(discord.ui.Select(placeholder="Select roles", min_values=1, max_values=len(options), options=options))

        @discord.ui.select()
        async def select_callback(self, select: discord.ui.Select, interaction2: discord.Interaction):
            selected_role_ids = [int(rid) for rid in select.values]
            current_roles = required_roles_per_guild.get(guild.id, [])
            for rid in selected_role_ids:
                if rid not in current_roles:
                    current_roles.append(rid)
            required_roles_per_guild[guild.id] = current_roles
            await save_required_roles_to_db(guild.id, current_roles)
            mentions = ' '.join(f"<@&{rid}>" for rid in selected_role_ids)
            await interaction2.response.edit_message(content=f"✅ Logger roles added: {mentions}", view=None)

    view = RoleSelect()
    await interaction.response.send_message("Select roles to allow forwarding tickets:", view=view, ephemeral=True)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Please check your spelling.")
    else:
        print(f"Error in command {ctx.command}: {error}")
        await ctx.send(f"❌ An error occurred: {error}")

@bot.command(name='role')
@commands.has_permissions(manage_roles=True)
async def role_command(ctx):
    mentions = ctx.message.mentions
    role_mentions = ctx.message.role_mentions

    # Find user (first user mentioned)
    user = None
    for mention in mentions:
        if isinstance(mention, discord.Member):
            user = mention
            break

    # Collect all mentioned roles
    roles = role_mentions

    if not user or not roles:
        await ctx.send("❌ Please mention a **user** and at least one **role**.\nExample: `!role @User @Staff @Member`")
        return

    added = []
    failed = []

    for role in roles:
        try:
            await user.add_roles(role)
            added.append(role.name)
        except discord.Forbidden:
            failed.append(role.name)
        except Exception as e:
            failed.append(f"{role.name} ({e})")

    msg = f"✅ Added roles to {user.mention}: {', '.join(added)}"
    if failed:
        msg += f"\n⚠️ Failed to add: {', '.join(failed)} (check bot permissions or role position)."

    await ctx.send(msg)


if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("Error: DISCORD_TOKEN environment variable not found!")
        exit(1)
    keep_alive()
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error running bot: {e}")
