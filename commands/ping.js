const { SlashCommandBuilder } = require('discord.js');

module.exports = {
    // Slash command data
    data: new SlashCommandBuilder()
        .setName('ping')
        .setDescription('Replies with Pong and bot latency!'),
    
    // Traditional command info
    name: 'ping',
    description: 'Check bot latency',
    usage: '!ping',
    
    // Execute slash command
    async execute(interaction) {
        const sent = await interaction.reply({ content: 'Pinging...', fetchReply: true });
        const latency = sent.createdTimestamp - interaction.createdTimestamp;
        const apiLatency = Math.round(interaction.client.ws.ping);
        
        await interaction.editReply(
            `🏓 Pong!\n` +
            `**Latency:** ${latency}ms\n` +
            `**API Latency:** ${apiLatency}ms`
        );
    },
    
    // Execute traditional command
    async executeMessage(message, args) {
        const sent = await message.reply('Pinging...');
        const latency = sent.createdTimestamp - message.createdTimestamp;
        const apiLatency = Math.round(message.client.ws.ping);
        
        await sent.edit(
            `🏓 Pong!\n` +
            `**Latency:** ${latency}ms\n` +
            `**API Latency:** ${apiLatency}ms`
        );
    }
};
