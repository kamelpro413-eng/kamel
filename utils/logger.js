const fs = require('fs');
const path = require('path');

class Logger {
    constructor() {
        this.logLevel = process.env.LOG_LEVEL || 'info';
        this.logLevels = {
            error: 0,
            warn: 1,
            info: 2,
            debug: 3
        };
        
        // Ensure logs directory exists
        const logsDir = path.join(__dirname, '..', 'logs');
        if (!fs.existsSync(logsDir)) {
            fs.mkdirSync(logsDir, { recursive: true });
        }
        
        this.logFile = path.join(logsDir, `bot-${new Date().toISOString().split('T')[0]}.log`);
    }

    // Get current timestamp
    getTimestamp() {
        return new Date().toISOString();
    }

    // Format log message
    formatMessage(level, message, extra = null) {
        const timestamp = this.getTimestamp();
        const baseMessage = `[${timestamp}] [${level.toUpperCase()}] ${message}`;
        
        if (extra) {
            return `${baseMessage}\n${JSON.stringify(extra, null, 2)}`;
        }
        
        return baseMessage;
    }

    // Check if log level should be output
    shouldLog(level) {
        return this.logLevels[level] <= this.logLevels[this.logLevel];
    }

    // Write to file and console
    writeLog(level, message, extra = null) {
        if (!this.shouldLog(level)) return;

        const formattedMessage = this.formatMessage(level, message, extra);
        
        // Write to file
        try {
            fs.appendFileSync(this.logFile, formattedMessage + '\n');
        } catch (error) {
            console.error('Failed to write to log file:', error);
        }

        // Write to console with colors
        const colors = {
            error: '\x1b[31m', // Red
            warn: '\x1b[33m',  // Yellow
            info: '\x1b[36m',  // Cyan
            debug: '\x1b[35m'  // Magenta
        };
        
        const reset = '\x1b[0m';
        const coloredMessage = `${colors[level] || ''}${formattedMessage}${reset}`;
        
        console.log(coloredMessage);
    }

    // Log methods
    error(message, extra = null) {
        this.writeLog('error', message, extra);
    }

    warn(message, extra = null) {
        this.writeLog('warn', message, extra);
    }

    info(message, extra = null) {
        this.writeLog('info', message, extra);
    }

    debug(message, extra = null) {
        this.writeLog('debug', message, extra);
    }
}

module.exports = new Logger();
