const fs = require('fs');
const path = require('path');

const logFile = path.join(__dirname, '../../logs/access.log');

function logAccess(userId, ip) {
    const logEntry = `${new Date().toISOString()} - Kullanıcı: ${userId}, IP: ${ip}\n`;
    fs.appendFileSync(logFile, logEntry);
}

module.exports = { logAccess };
