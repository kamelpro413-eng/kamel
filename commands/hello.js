const { SlashCommandBuilder } = require('discord.js');

module.exports = {
    // Slash command data
    data: new SlashCommandBuilder()
        .setName('hello')
        .setDescription('Sends a friendly greeting!')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('User to greet')
                .setRequired(false)
        ),
    
    // Traditional command info
    name: 'hello',
    description: 'Send a friendly greeting',
    usage: '!hello [@user]',
    
    // Execute slash command
    async execute(interaction) {
        const targetUser = interaction.options.getUser('user');
        
        if (targetUser) {
            await interaction.reply(`👋 Hello, ${targetUser}! Nice to meet you!`);
        } else {
            await interaction.reply(`👋 Hello, ${interaction.user}! How are you doing today?`);
        }
    },
    
    // Execute traditional command
    async executeMessage(message, args) {
        const mentionedUser = message.mentions.users.first();
        
        if (mentionedUser) {
            await message.reply(`👋 Hello, ${mentionedUser}! Nice to meet you!`);
        } else {
            await message.reply(`👋 Hello, ${message.author}! How are you doing today?`);
        }
    }
};
