const commandHandler = require('./commandHandler.js');
const logger = require('../utils/logger.js');

module.exports = {
    // Register all event handlers
    registerEvents(client) {
        // Handle message events for traditional commands
        client.on('messageCreate', async (message) => {
            try {
                await commandHandler.handleMessageCommand(message);
            } catch (error) {
                logger.error('Error handling message:', error);
            }
        });

        // Handle interaction events for slash commands
        client.on('interactionCreate', async (interaction) => {
            try {
                await commandHandler.handleSlashCommand(interaction);
            } catch (error) {
                logger.error('Error handling interaction:', error);
            }
        });

        // Handle bot joining/leaving guilds
        client.on('guildCreate', (guild) => {
            logger.info(`Joined new guild: ${guild.name} (${guild.id}) with ${guild.memberCount} members`);
        });

        client.on('guildDelete', (guild) => {
            logger.info(`Left guild: ${guild.name} (${guild.id})`);
        });

        // Handle errors
        client.on('error', (error) => {
            logger.error('Discord client error:', error);
        });

        client.on('warn', (warning) => {
            logger.warn('Discord client warning:', warning);
        });

        // Handle rate limits
        client.on('rateLimit', (rateLimitData) => {
            logger.warn('Rate limit hit:', rateLimitData);
        });

        logger.info('Event handlers registered successfully');
    }
};
