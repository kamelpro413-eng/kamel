const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const config = require('../config/config.js');

module.exports = {
    // Slash command data
    data: new SlashCommandBuilder()
        .setName('help')
        .setDescription('Shows all available commands and their usage'),
    
    // Traditional command info
    name: 'help',
    description: 'Display help information',
    usage: '!help',
    
    // Execute slash command
    async execute(interaction) {
        const embed = this.createHelpEmbed(interaction.client);
        await interaction.reply({ embeds: [embed] });
    },
    
    // Execute traditional command
    async executeMessage(message, args) {
        const embed = this.createHelpEmbed(message.client);
        await message.reply({ embeds: [embed] });
    },
    
    // Helper method to create help embed
    createHelpEmbed(client) {
        const embed = new EmbedBuilder()
            .setTitle('🤖 Bot Commands')
            .setDescription('Here are all the available commands:')
            .setColor('#0099ff')
            .setTimestamp()
            .setFooter({ 
                text: `Bot made with Discord.js`, 
                iconURL: client.user.displayAvatarURL() 
            });

        // Get all commands from the client
        const commands = Array.from(client.commands.values());
        
        // Add fields for each command
        commands.forEach(command => {
            if (command.name && command.description) {
                embed.addFields({
                    name: `${config.prefix}${command.name}`,
                    value: `${command.description}\nUsage: \`${command.usage || config.prefix + command.name}\``,
                    inline: false
                });
            }
        });

        // Add slash commands info
        embed.addFields({
            name: '💡 Slash Commands',
            value: 'You can also use slash commands by typing `/` followed by the command name!',
            inline: false
        });

        return embed;
    }
};
