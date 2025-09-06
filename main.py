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

# Tracks guild settings in memory for faster access
# Format: {guild_id: {"roles": [role_ids], "channel": channel_id}}
guild_settings = {}

# Authorized user ID for bot configuration commands
AUTHORIZED_USER_ID = 1005902785067372555

# Database connection string
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

async def load_all_guild_settings():
    """Load settings from database for all guilds"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT guild_id, key, value FROM bot_settings")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Reset dict
        guild_settings.clear()

        for guild_id, key, value in rows:
            if guild_id not in guild_settings:
                guild_settings[guild_id] = {"roles": [], "channel": None}
            if key == 'required_role_ids':
                guild_settings[guild_id]['roles'] = [int(rid) for rid in value.split(',') if rid]
            elif key == 'target_channel_id':
                guild_settings[guild_id]['channel'] = int(value)

        print(f"Loaded settings for {len(guild_settings)} guild(s)")

    except Exception as e:
        print(f"Error loading guild settings: {e}")

async def save_guild_setting(guild_id, key, value):
    """Save a guild setting to the database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO bot_settings (guild_id, key, value)
            VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, key) DO UPDATE SET value = EXCLUDED.value
        ''', (guild_id, key, value))
        conn.commit()
        cur.close()
        conn.close()
        # Update cache
        if guild_id not in guild_settings:
            guild_settings[guild_id] = {"roles": [], "channel": None}
        if key == 'required_role_ids':
            guild_settings[guild_id]['roles'] = [int(rid) for rid in value.split(',') if rid]
        elif key == 'target_channel_id':
            guild_settings[guild_id]['channel'] = int(value)
    except Exception as e:
        print(f"Error saving guild setting: {e}")

def member_has_any_role(member, role_ids):
    """Check if member has any role from the list"""
    if not role_ids:
        return False
    member_role_ids = {role.id for role in member.roles}
    return any(rid in member_role_ids for rid in role_ids)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guild(s)')
    await init_database()
    await load_all_guild_settings()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.guild and message.channel.name and message.channel.name.startswith('ticket-'):
        guild_id = message.guild.id
        if guild_id not in claimed_tickets:
            claimed_tickets[guild_id] = set()

        if message.channel.id not in claimed_tickets[guild_id]:
            settings = guild_settings.get(guild_id, {})
            role_ids = settings.get('roles', [])
            target_channel_id = settings.get('channel')

            if target_channel_id and member_has_any_role(message.author, role_ids):
                await forward_message_to_channel(message, target_channel_id)
                claimed_tickets[guild_id].add(message.channel.id)

    await bot.process_commands(message)

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

@bot.command(name='loggerrole')
async def logger_role(ctx, *roles: discord.Role):
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    if not roles:
        await ctx.send("❌ Please mention at least one role. Example: `!loggerrole @staff @support`")
        return

    role_ids_str = ','.join(str(role.id) for role in roles)
    await save_guild_setting(ctx.guild.id, 'required_role_ids', role_ids_str)

    mentions = ' '.join(role.mention for role in roles)
    await ctx.send(f"✅ Logger roles set to: {mentions}\nOnly users with **any** of these roles will have their ticket messages forwarded.")

@bot.command(name='loggerchannel')
async def logger_channel(ctx, channel: discord.TextChannel):
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    await save_guild_setting(ctx.guild.id, 'target_channel_id', str(channel.id))
    await ctx.send(f"✅ Logger channel set to: {channel.mention}\nTicket messages will be forwarded here.")

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
