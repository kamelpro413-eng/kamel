# Overview

This is a Python Discord bot built with discord.py that works with Ticket Tool. The bot detects messages in ticket channels (named "ticket-xxxx"), tracks the first and second users who send messages in each ticket, and logs this information to a designated channel. It includes a Flask webserver with keep_alive functionality for 24/7 uptime on Replit with UptimeRobot monitoring.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **discord.py**: Modern Python Discord API wrapper
- **Flask Integration**: Web server for keep_alive functionality and 24/7 uptime
- **Gateway Intents**: Configured with message_content, guilds intents for ticket detection

## Core Functionality
- **Ticket Detection**: Automatically detects messages in channels named "ticket-xxxx"
- **User Tracking**: Records first and second unique users who message in each ticket
- **Automated Logging**: Sends formatted log messages to designated channel when second user messages
- **Memory Storage**: Uses in-memory dictionary to track ticket states during bot runtime

## Web Server Integration
- **Flask Server**: Runs on port 5000 for UptimeRobot monitoring
- **Health Endpoints**: `/` and `/status` routes for uptime checking
- **Threading**: Flask runs in separate daemon thread to not block bot
- **Keep Alive**: Ensures bot stays online 24/7 on Replit

## Application Structure
```
├── main.py               # Main bot file with all functionality
├── .env.example          # Environment variable template
└── replit.md            # Project documentation
```

## Message Processing
- **Event-driven**: Uses discord.py on_message event for real-time detection
- **Channel Filtering**: Only processes messages in channels starting with "ticket-"
- **User Validation**: Ensures first and second users are different
- **Automatic Cleanup**: Tracker persists until bot restart

# External Dependencies

## Core Dependencies
- **discord.py v2.6.2**: Primary Python Discord API library
- **Flask v3.1.2**: Web framework for keep_alive server functionality
- **Python 3.11**: Runtime environment

## Discord API Integration
- **Discord Gateway**: Real-time event handling and message processing
- **Discord REST API**: User mentions and channel message sending
- **Message Content Intent**: Required for reading message content in ticket channels

## Environment Variables Required
- **DISCORD_TOKEN**: Bot authentication token (required)
- **LOG_CHANNEL_NAME**: Name of channel for logging (optional, defaults to "ticket-logs")

## Bot Features
- **Ticket Detection**: Monitors channels with "ticket-" prefix
- **User Tracking**: Records first and second message senders per ticket
- **Log Channel Integration**: Sends formatted messages to designated log channel
- **Basic Commands**: !ping and !ticket_status for testing and monitoring
- **24/7 Uptime**: Flask server enables UptimeRobot monitoring