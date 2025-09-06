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

# Global variable to store the required roles (list of Role objects)
required_roles = []

# Global variable to store the target channel ID
target_channel_id = 1408438201902698656  # Default channel ID (replace with your default)

# Authorized user ID for bot configuration commands
AUTHORIZED_USER_ID = 1005902785067372555

# Database connection URL (make sure it's set in environment variables)
DATABASE_URL = os.getenv('DATABASE_URL')

async def init_database():
    """Initialize database tables"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

async def load_data_from_db():
    """Load settings from database"""
    global required_roles, target_channel_id
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Load required roles IDs
        cur.execute("SELECT value FROM bot_settings WHERE key = 'required_role_id'")
        result = cur.fetchone()
        if result:
            role_ids = [int(rid) for rid in result[0].split(',')]
            # Map role IDs to Role objects for all guilds bot is in
            roles_found = []
            for guild in bot.guilds:
                for rid in role_ids:
                    role = guild.get_role(rid)
                    if role and role not in roles_found:
                        roles_found.append(role)
            required_roles = roles_found
            print("Loaded required roles:")
            for role in required_roles:
                print(f"- {role.name} (ID: {role.id})")

        # Load target channel ID
        cur.execute("SELECT value FROM bot_settings WHERE key = 'target_channel_id'")
        result = cur.fetchone()
        if result:
            target_channel_id = int(result[0])
            print(f"Loaded target channel ID: {target_channel_id}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error loading data from database: {e}")

async def save_required_roles_to_db(roles):
    """Save required roles to database"""
    try:
        role_ids_str = ','.join(str(role.id) for role in roles)
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO bot_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value
        ''', ('required_role_id', role_ids_str))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving required roles to database: {e}")

async def save_target_channel_to_db(channel_id):
    """Save target channel ID to database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO bot_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value
        ''', ('target_channel_id', str(channel_id)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving target channel to database: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guild(s)')
    await init_database()
    await load_data_from_db()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check if channel name starts with ticket-
    if message.channel.name and message.channel.name.startswith('ticket-'):
        guild_id = message.guild.id
        if guild_id not in claimed_tickets:
            claimed_tickets[guild_id] = set()

        if message.channel.id not in claimed_tickets[guild_id]:
            has_role = await user_has_required_role(message)
            print(f"[DEBUG] User {message.author} has required role? {has_role}")
            if has_role:
                print(f"[DEBUG] Forwarding message from {message.author} in {message.channel.name}")
                await forward_message_to_channel(message, target_channel_id)
                claimed_tickets[guild_id].add(message.channel.id)
            else:
                print(f"[DEBUG] User {message.author} does NOT have required role, skipping forwarding.")
    await bot.process_commands(message)

async def user_has_required_role(message):
    """Check if user has any of the required roles"""
    try:
        # Reload roles from DB in case they've changed (optional, can be optimized)
        # But here we just use the cached required_roles for performance
        if not required_roles:
            print("No required roles set. Use !loggerrole to set them.")
            return False

        member = message.guild.get_member(message.author.id)
        if member:
            # Check if user has ANY of the required roles
            return any(role.id in [r.id for r in required_roles] for role in member.roles)
        return False
    except Exception as e:
        print(f"Error checking required roles: {e}")
        return False

async def forward_message_to_channel(message, channel_id):
    """Forward a message to a specific channel"""
    try:
        target_channel = bot.get_channel(channel_id)
        if target_channel:
            forwarded_message = (
                "------------------------------\n"
                f"Ticket Number : {message.channel.name}\n"
                f"Staff Who Claimed : {message.author.mention}\n"
                f"Typed : {message.content}"
            )
            await target_channel.send(forwarded_message)
            print(f"[DEBUG] Message forwarded to {target_channel.name}")
        else:
            print(f"Target channel with ID {channel_id} not found or bot lacks access.")
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
    global required_roles
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    if not roles:
        await ctx.send("❌ Please mention at least one role. Example: `!loggerrole @staff @support`")
        return

    required_roles = list(roles)

    try:
        await save_required_roles_to_db(required_roles)
        mentions = ' '.join(role.mention for role in required_roles)
        await ctx.send(f"✅ Logger roles set to: {mentions}\nOnly users with **any** of these roles will have their ticket messages forwarded.")
        print(f"[INFO] Logger roles updated: {mentions}")
    except Exception as e:
        await ctx.send(f"❌ Failed to save roles: {e}")

@bot.command(name='loggerchannel')
async def logger_channel(ctx, channel_id: int):
    global target_channel_id
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        await ctx.send("❌ Invalid channel ID or bot has no access to this channel.")
        return

    target_channel_id = channel_id
    await save_target_channel_to_db(channel_id)
    await ctx.send(f"✅ Logger channel set to {channel.mention}")
    print(f"[INFO] Logger channel updated to: {channel.name} (ID: {channel_id})")

if __name__ == '__main__':
    keep_alive()
    bot.run(os.getenv('DISCORD_TOKEN'))
