import discord
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import psycopg2

# Bot setup - Enable required intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Tracks claimed tickets per server (guild)
claimed_tickets = {}

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
                guild_id BIGINT NOT NULL,
                key TEXT NOT NULL,
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

async def load_guild_settings(guild_id):
    """Load settings for a guild from database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Load required roles
        cur.execute("SELECT value FROM bot_settings WHERE guild_id = %s AND key = 'required_role_ids'", (guild_id,))
        result = cur.fetchone()
        role_ids = []
        if result:
            role_ids = [int(rid) for rid in result[0].split(',') if rid.strip().isdigit()]

        # Load target channel ID
        cur.execute("SELECT value FROM bot_settings WHERE guild_id = %s AND key = 'target_channel_id'", (guild_id,))
        result = cur.fetchone()
        target_channel_id = None
        if result:
            try:
                target_channel_id = int(result[0])
            except:
                pass

        cur.close()
        conn.close()
        return role_ids, target_channel_id
    except Exception as e:
        print(f"Error loading guild {guild_id} settings from database: {e}")
        return [], None

async def save_required_roles_to_db(guild_id, roles):
    """Save required roles for a guild to database"""
    try:
        role_ids_str = ','.join(str(role.id) for role in roles)
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
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
        print(f"Error saving required roles for guild {guild_id} to database: {e}")

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
        print(f"Error saving target channel for guild {guild_id} to database: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    await init_database()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name and message.channel.name.startswith('ticket-'):
        guild_id = message.guild.id

        if guild_id not in claimed_tickets:
            claimed_tickets[guild_id] = set()

        # Load roles and channel for this guild dynamically
        role_ids, target_channel_id = await load_guild_settings(guild_id)

        print(f"[DEBUG] Guild {guild_id} | Ticket channel: {message.channel.name} | Target channel: {target_channel_id} | Role IDs: {role_ids}")

        if message.channel.id not in claimed_tickets[guild_id]:
            if target_channel_id and await user_has_any_required_role(message, role_ids):
                print(f"[DEBUG] User {message.author} has required role(s), forwarding message...")
                await forward_message_to_channel(message, target_channel_id)
                claimed_tickets[guild_id].add(message.channel.id)
            else:
                print(f"[DEBUG] User {message.author} does NOT have required roles or target channel not set.")
    await bot.process_commands(message)

async def user_has_any_required_role(message, role_ids):
    """Check if user has any of the required roles"""
    if not role_ids:
        print("No required roles set.")
        return False
    member = message.guild.get_member(message.author.id)
    if member:
        return any(role.id in role_ids for role in member.roles)
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
            print(f"[DEBUG] Forwarded message from {message.author} in {message.channel.name} to {target_channel.name}")
        else:
            print(f"[ERROR] Target channel {target_channel_id} not found")
    except Exception as e:
        print(f"[ERROR] Error forwarding message: {e}")

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
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    if not roles:
        await ctx.send("❌ Please mention at least one role. Example: `!loggerrole @staff @support`")
        return

    try:
        await save_required_roles_to_db(ctx.guild.id, roles)
        mentions = ' '.join(role.mention for role in roles)
        await ctx.send(f"✅ Logger roles set to: {mentions}\nOnly users with **any** of these roles will have their ticket messages forwarded.")
    except Exception as e:
        await ctx.send(f"❌ Failed to save roles: {e}")

@bot.command(name='loggerchannel')
async def logger_channel(ctx, channel_id: int):
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    try:
        channel = bot.get_channel(channel_id)
        if channel:
            await save_target_channel_to_db(ctx.guild.id, channel_id)
            await ctx.send(f"✅ Logger channel set to: {channel.mention} ({channel.name})\nTicket messages will be forwarded to this channel.")
        else:
            await ctx.send("❌ Channel not found or bot doesn't have access to it. Please check the channel ID.")
    except Exception as e:
        await ctx.send(f"❌ Invalid channel ID format. Please provide a valid Discord channel ID (numbers only).")

@bot.command(name='checksettings')
async def check_settings(ctx):
    role_ids, channel_id = await load_guild_settings(ctx.guild.id)
    roles = [ctx.guild.get_role(rid) for rid in role_ids if ctx.guild.get_role(rid) is not None]
    roles_str = ', '.join([r.name for r in roles]) if roles else 'None'
    channel = bot.get_channel(channel_id)
    channel_str = channel.name if channel else 'None'
    await ctx.send(f"Logger Roles: {roles_str}\nLogger Channel: {channel_str}")

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
