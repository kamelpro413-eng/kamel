import psycopg2
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

# Global variable to store the required role
required_role = None

# Global variable to store the target channel ID
target_channel_id = 1408438201902698656  # Default channel

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
    global required_role, target_channel_id
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("SELECT value FROM bot_settings WHERE key = 'required_role_id'")
        result = cur.fetchone()
        if result:
            role_id = int(result[0])
            for guild in bot.guilds:
                role = guild.get_role(role_id)
                if role:
                    required_role = role
                    print(f"Loaded required role: {role.name} (ID: {role.id})")
                    break

        cur.execute("SELECT value FROM bot_settings WHERE key = 'target_channel_id'")
        result = cur.fetchone()
        if result:
            target_channel_id = int(result[0])
            print(f"Loaded target channel ID: {target_channel_id}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error loading data from database: {e}")

async def save_required_role_to_db(role):
    """Save required role to database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO bot_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value
        ''', ('required_role_id', str(role.id)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving required role to database: {e}")

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
    print(f'Bot is in {len(bot.guilds)} guilds')
    await init_database()
    await load_data_from_db()

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
        if message.channel.id not in claimed_tickets[guild_id] and await user_has_required_role(message):
            await forward_message_to_channel(message, target_channel_id)
            claimed_tickets[guild_id].add(message.channel.id)  # Mark as claimed for this guild

    await bot.process_commands(message)

async def user_has_required_role(message):
    """Check if user has the required role"""
    if not required_role:
        print("No required role set. Use !loggerrole to set one.")
        return False

    member = message.guild.get_member(message.author.id)
    if member:
        return required_role in member.roles
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
async def logger_role(ctx, *, role_mention):
    global required_role
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    role = None
    if ctx.message.role_mentions:
        role = ctx.message.role_mentions[0]
    else:
        role = discord.utils.get(ctx.guild.roles, name=role_mention)

    if role:
        required_role = role
        await save_required_role_to_db(role)
        await ctx.send(f"✅ Logger role set to: {role.mention} ({role.name})\nOnly users with this role will have their ticket messages forwarded.")
    else:
        await ctx.send("❌ Role not found. Please mention the role like @new role or type the exact role name.")

@bot.command(name='loggerchannel')
async def logger_channel(ctx, channel_id: int):
    global target_channel_id
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    try:
        channel = bot.get_channel(channel_id)
        if channel:
            target_channel_id = channel_id
            await save_target_channel_to_db(channel_id)
            await ctx.send(f"✅ Logger channel set to: {channel.mention} ({channel.name})\nTicket messages will be forwarded to this channel.")
        else:
            await ctx.send("❌ Channel not found or bot doesn't have access to it. Please check the channel ID.")
    except Exception as e:
        await ctx.send(f"❌ Invalid channel ID format. Please provide a valid Discord channel ID (numbers only).")

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
