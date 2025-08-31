require('dotenv').config();

module.exports = {
    // Discord bot token (required)
    token: process.env.DISCORD_TOKEN,
    
    // Discord client ID (required for slash commands)
    clientId: process.env.DISCORD_CLIENT_ID,
    
    // Command prefix for traditional commands
    prefix: process.env.PREFIX || '!',
    
    // Development guild ID (optional, for faster slash command updates during development)
    devGuildId: process.env.DEV_GUILD_ID || null,
    
    // Bot settings
    settings: {
        // Maximum number of commands to process per minute per user
        commandRateLimit: 60,
        
        // Whether to delete command messages after execution
        deleteCommandMessages: false,
        
        // Default embed color
        embedColor: '#0099ff',
        
        // Bot status
        status: {
            type: 'WATCHING',
            name: 'for commands | !help'
        }
    },
    
    // Validate required environment variables
    validate() {
        const required = ['DISCORD_TOKEN', 'DISCORD_CLIENT_ID'];
        const missing = required.filter(key => !process.env[key]);
        
        if (missing.length > 0) {
            throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
        }
        
        return true;
    }
};

// Validate configuration on load
try {
    module.exports.validate();
} catch (error) {
    console.error('Configuration validation failed:', error.message);
    console.error('Please check your .env file and ensure all required variables are set.');
    process.exit(1);
}
