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

# Compatibility fallback
required_role = None

# Default target channel ID
target_channel_id = 1408438201902698656

AUTHORIZED_USER_ID = 1005902785067372555
DATABASE_URL = os.getenv('DATABASE_URL')

async def init_database():
    """Ensure database table exists."""
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
    """Load roles and channel settings from the database."""
    global required_role, target_channel_id
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Load roles
        cur.execute("SELECT value FROM bot_settings WHERE key = 'required_role_id'")
        result = cur.fetchone()
        if result:
            role_ids = [int(rid) for rid in result[0].split(',')]
            for guild in bot.guilds:
                roles = [guild.get_role(rid) for rid in role_ids if guild.get_role(rid)]
                if roles:
                    required_role = roles[0]
                    print("Loaded required roles:")
                    for role in roles:
                        print(f"- {role.name} (ID: {role.id})")
                    break

        # Load target channel
        cur.execute("SELECT value FROM bot_settings WHERE key = 'target_channel_id'")
        result = cur.fetchone()
        if result:
            target_channel_id = int(result[0])
            print(f"Loaded target channel ID: {target_channel_id}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error loading data from database: {e}")

async def save_required_role_to_db(role_ids_str):
    """Save multiple role IDs."""
    try:
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
        print(f"Error saving required role to database: {e}")

async def save_target_channel_to_db(channel_id):
    """Save the target logging channel."""
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
    print(f'{bot.user} connected — in {len(bot.guilds)} guild(s)')
    await init_database()
    await load_data_from_db()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name and message.channel.name.startswith('ticket-'):
        guild_id = message.guild.id
        claimed_tickets.setdefault(guild_id, set())
        if message.channel.id not in claimed_tickets[guild_id] and await user_has_required_role(message):
            await forward_message_to_channel(message, target_channel_id)
            claimed_tickets[guild_id].add(message.channel.id)

    await bot.process_commands(message)

async def user_has_required_role(message):
    """Return True if user has any of the assigned roles."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_settings WHERE key = 'required_role_id'")
        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            print("No required roles set.")
            return False

        role_ids = [int(rid) for rid in result[0].split(',')]
        member = message.guild.get_member(message.author.id)
        if not member:
            return False

        # Diagnostics
        print("Checking user roles:", [r.id for r in member.roles])
        print("Against required:", role_ids)

        return any(role.id in role_ids for role in member.roles)
    except Exception as e:
        print(f"Error checking required roles: {e}")
        return False

async def forward_message_to_channel(message, channel_id):
    """Forward ticket message."""
    try:
        target = bot.get_channel(channel_id)
        if target:
            await target.send(
                f"------------------------------\n"
                f"Ticket Number : {message.channel.name}\n"
                f"Staff Who Claimed : {message.author.mention}\n"
                f"Typed : {message.content}"
            )
        else:
            print(f"Target channel {channel_id} not found")
    except Exception as e:
        print(f"Error forwarding message: {e}")

# Flask keep-alive
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running!"
@app.route('/status')
def status(): return {
    "status": "online",
    "bot_name": str(bot.user),
    "guilds": len(bot.guilds) if bot.is_ready() else 0
}

def run_flask():
    app.run(host='0.0.0.0', port=5000)
def keep_alive():
    Thread(target=run_flask, daemon=True).start()

# Commands
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! Latency: {round(bot.latency * 1000)}ms")

@bot.command()
async def send_to_channel(ctx, channel_id: int, *, msg):
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(msg)
        await ctx.send(f"Message sent to {channel.name}!")
    else:
        await ctx.send("Channel not found or missing permissions.")

@bot.command()
async def loggerrole(ctx, *roles: discord.Role):
    global required_role
    if ctx.author.id != AUTHORIZED_USER_ID:
        return await ctx.send("❌ You don't have permission.")
    if not roles:
        return await ctx.send("❌ Mention at least one role.")
    required_role = roles[0]
    role_ids_str = ','.join(str(r.id) for r in roles)
    await save_required_role_to_db(role_ids_str)
    await ctx.send(f"✅ Logger roles set: {' '.join(r.mention for r in roles)}")

@bot.command()
async def loggerchannel(ctx, channel_id: int):
    global target_channel_id
    if ctx.author.id != AUTHORIZED_USER_ID:
        return await ctx.send("❌ You don't have permission.")
    channel = bot.get_channel(channel_id)
    if channel:
        target_channel_id = channel_id
        await save_target_channel_to_db(channel_id)
        await ctx.send(f"✅ Logger channel set to: {channel.mention}")
    else:
        await ctx.send("❌ Channel not found or missing permissions.")

@bot.command()
async def testerole(ctx):
    allowed = await user_has_required_role(ctx.message)
    await ctx.send(f"Has required role? {'Yes' if allowed else 'No'}")

if __name__ == '__main__':
    keep_alive()
    bot.run(os.getenv('DISCORD_TOKEN'))
