import psycopg2
import discord
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

        # Fetch all required roles for all guilds
        cur.execute("SELECT guild_id, value FROM bot_settings WHERE key = 'required_role_ids'")
        rows = cur.fetchall()
        for guild_id, value in rows:
            role_ids = [int(rid) for rid in value.split(',') if rid.strip().isdigit()]
            required_roles_per_guild[guild_id] = role_ids
            print(f"Loaded required roles for guild {guild_id}: {role_ids}")

        # Fetch all target channels for all guilds
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
    """Save required role IDs for a guild to database"""
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
    """Save target channel ID for a guild to database"""
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

@bot.event
async def on_message(message):
    if message.author.bot:
        return  # Ignore bot messages

    # Process commands first to avoid duplicate messages
    await bot.process_commands(message)

    # Ticket forwarding logic
    if message.channel.name and message.channel.name.startswith('ticket-'):
        guild_id = message.guild.id

        if guild_id not in claimed_tickets:
            claimed_tickets[guild_id] = set()

        # Only forward if this ticket hasn't been claimed
        if message.channel.id not in claimed_tickets[guild_id] and await user_has_required_role(message):
            target_channel_id = target_channel_per_guild.get(guild_id)
            if target_channel_id:
                # Mark as claimed BEFORE sending to prevent double triggers
                claimed_tickets[guild_id].add(message.channel.id)
                await forward_message_to_channel(message, target_channel_id)
            else:
                print(f"No target channel set for guild {guild_id}")

async def user_has_required_role(message):
    """Check if user has any of the required roles in that guild"""
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
    """Forward a message to a specific channel"""
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

# Flask webserver for keep_alive
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

# Optional: command error handler for user feedback on wrong commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Please check your spelling.")
    else:
        print(f"Error in command {ctx.command}: {error}")
        await ctx.send(f"❌ An error occurred: {error}")

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
