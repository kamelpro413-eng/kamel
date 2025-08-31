const { Client, GatewayIntentBits, REST, Routes, Collection } = require('discord.js');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const config = require('./config/config.js');
const logger = require('./utils/logger.js');
const commandHandler = require('./handlers/commandHandler.js');
const eventHandler = require('./handlers/eventHandler.js');

// Create Discord client with necessary intents
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

// Create collections for commands
client.commands = new Collection();
client.slashCommands = new Collection();

// Load commands and event handlers
commandHandler.loadCommands(client);
eventHandler.registerEvents(client);

// Register slash commands with Discord
async function registerSlashCommands() {
    try {
        const commands = [];
        const commandFiles = fs.readdirSync('./commands').filter(file => file.endsWith('.js'));

        for (const file of commandFiles) {
            const command = require(`./commands/${file}`);
            if (command.data) {
                commands.push(command.data.toJSON());
            }
        }

        const rest = new REST({ version: '10' }).setToken(config.token);

        logger.info('Started refreshing application (/) commands.');

        await rest.put(
            Routes.applicationCommands(config.clientId),
            { body: commands }
        );

        logger.info('Successfully reloaded application (/) commands.');
    } catch (error) {
        logger.error('Error registering slash commands:', error);
    }
}

// Bot ready event
client.once('ready', async () => {
    logger.info(`Bot is ready! Logged in as ${client.user.tag}`);
    logger.info(`Bot is in ${client.guilds.cache.size} servers`);
    
    // Register slash commands
    await registerSlashCommands();
});

// Handle unhandled promise rejections
process.on('unhandledRejection', error => {
    logger.error('Unhandled promise rejection:', error);
});

// Handle uncaught exceptions
process.on('uncaughtException', error => {
    logger.error('Uncaught exception:', error);
    process.exit(1);
});

// Login to Discord
client.login(config.token).catch(error => {
    logger.error('Failed to login:', error);
    process.exit(1);
});

module.exports = client;
