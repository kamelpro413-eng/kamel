const fs = require('fs');
const path = require('path');
const logger = require('../utils/logger.js');

module.exports = {
    // Load all commands from the commands directory
    loadCommands(client) {
        try {
            const commandsPath = path.join(__dirname, '..', 'commands');
            const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));

            let loadedCommands = 0;

            for (const file of commandFiles) {
                const filePath = path.join(commandsPath, file);
                const command = require(filePath);

                // Load traditional command
                if (command.name) {
                    client.commands.set(command.name, command);
                    loadedCommands++;
                }

                // Load slash command
                if (command.data) {
                    client.slashCommands.set(command.data.name, command);
                }
            }

            logger.info(`Loaded ${loadedCommands} commands successfully`);
        } catch (error) {
            logger.error('Error loading commands:', error);
        }
    },

    // Handle traditional message commands
    async handleMessageCommand(message) {
        const config = require('../config/config.js');
        
        // Ignore messages from bots or messages that don't start with prefix
        if (message.author.bot || !message.content.startsWith(config.prefix)) {
            return;
        }

        // Parse command and arguments
        const args = message.content.slice(config.prefix.length).trim().split(/ +/);
        const commandName = args.shift().toLowerCase();

        // Get command
        const command = message.client.commands.get(commandName);

        if (!command) {
            return message.reply(`❌ Unknown command: \`${commandName}\`. Use \`${config.prefix}help\` to see available commands.`);
        }

        try {
            logger.info(`Executing command: ${commandName} by ${message.author.tag} in ${message.guild?.name || 'DM'}`);
            
            if (command.executeMessage) {
                await command.executeMessage(message, args);
            } else {
                await message.reply('❌ This command is not available as a text command. Please use the slash command version.');
            }
        } catch (error) {
            logger.error(`Error executing command ${commandName}:`, error);
            
            const errorMessage = '❌ There was an error executing this command. Please try again later.';
            
            if (message.replied || message.deferred) {
                await message.followUp(errorMessage);
            } else {
                await message.reply(errorMessage);
            }
        }
    },

    // Handle slash commands
    async handleSlashCommand(interaction) {
        if (!interaction.isChatInputCommand()) return;

        const command = interaction.client.slashCommands.get(interaction.commandName);

        if (!command) {
            return interaction.reply({
                content: '❌ This command is not recognized.',
                ephemeral: true
            });
        }

        try {
            logger.info(`Executing slash command: ${interaction.commandName} by ${interaction.user.tag} in ${interaction.guild?.name || 'DM'}`);
            await command.execute(interaction);
        } catch (error) {
            logger.error(`Error executing slash command ${interaction.commandName}:`, error);
            
            const errorMessage = '❌ There was an error executing this command. Please try again later.';
            
            if (interaction.replied || interaction.deferred) {
                await interaction.followUp({ content: errorMessage, ephemeral: true });
            } else {
                await interaction.reply({ content: errorMessage, ephemeral: true });
            }
        }
    }
};
