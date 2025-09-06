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

# Authorized user ID for bot configuration commands
AUTHORIZED_USER_ID = 1005902785067372555

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')

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

async def init_database():
    """Initialize database tables"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id BIGINT PRIMARY KEY,
                required_role_ids TEXT,
                target_channel_id BIGINT
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

async def get_guild_settings(guild_id):
    """Fetch required roles and target channel ID for a guild from the database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT required_role_ids, target_channel_id FROM guild_settings WHERE guild_id = %s", (guild_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if result:
            role_ids = [int(rid) for rid in result[0].split(',')] if result[0] else []
            channel_id = result[1]
            return role_ids, channel_id
        return [], None
    except Exception as e:
        print(f"Error loading guild settings: {e}")
        return [], None

async def save_guild_settings(guild_id, role_ids=None, channel_id=None):
    """Save or update required roles and/or target channel ID for a guild in the database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # Check if guild exists already
        cur.execute("SELECT required_role_ids, target_channel_id FROM guild_settings WHERE guild_id = %s", (guild_id,))
        existing = cur.fetchone()

        new_role_ids = ','.join(str(rid) for rid in role_ids) if role_ids is not None else (existing[0] if existing else None)
        new_channel_id = channel_id if channel_id is not None else (existing[1] if existing else None)

        if existing:
            cur.execute('''
                UPDATE guild_settings
                SET required_role_ids = %s, target_channel_id = %s
                WHERE guild_id = %s
            ''', (new_role_ids, new_channel_id, guild_id))
        else:
            cur.execute('''
                INSERT INTO guild_settings (guild_id, required_role_ids, target_channel_id)
                VALUES (%s, %s, %s)
            ''', (guild_id, new_role_ids, new_channel_id))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving guild settings: {e}")

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

        # Initialize set for this guild if needed
        if guild_id not in claimed_tickets:
            claimed_tickets[guild_id] = set()

        # Only forward if this ticket hasn't been claimed in this server
        if message.channel.id not in claimed_tickets[guild_id]:
            role_ids, target_channel_id = await get_guild_settings(guild_id)

            if not target_channel_id:
                print(f"No target channel set for guild {guild_id}")
                return

            member = message.guild.get_member(message.author.id)
            if member and any(role.id in role_ids for role in member.roles):
                target_channel = bot.get_channel(target_channel_id)
                if target_channel:
                    forwarded_message = (
                        "------------------------------\n"
                        f"Ticket Number : {message.channel.name}\n"
                        f"Staff Who Claimed : {message.author.mention}\n"
                        f"Typed : {message.content}"
                    )
                    await target_channel.send(forwarded_message)
                    claimed_tickets[guild_id].add(message.channel.id)  # Mark as claimed
                else:
                    print(f"Target channel {target_channel_id} not found in guild {guild_id}")
            else:
                print(f"User {message.author} does not have any of the required roles in guild {guild_id}")

    await bot.process_commands(message)

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

    role_ids = [role.id for role in roles]

    await save_guild_settings(ctx.guild.id, role_ids=role_ids)
    mentions = ' '.join(role.mention for role in roles)
    await ctx.send(f"✅ Logger roles set to: {mentions}\nOnly users with **any** of these roles will have their ticket messages forwarded.")

@bot.command(name='loggerchannel')
async def logger_channel(ctx, channel: discord.TextChannel):
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    await save_guild_settings(ctx.guild.id, channel_id=channel.id)
    await ctx.send(f"✅ Logger channel set to: {channel.mention}")

# Start the Flask server for keep_alive
keep_alive()

# Run your bot token here
bot.run(os.getenv('DISCORD_TOKEN'))
