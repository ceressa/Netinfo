const failedAttempts = new Map();

function addFailedAttempt(ip) {
    const attempts = failedAttempts.get(ip) || { count: 0, time: Date.now() };
    attempts.count += 1;

    if (attempts.count >= 3) {
        attempts.time = Date.now();
    }
    failedAttempts.set(ip, attempts);
}

function isLockedOut(ip) {
    const attempts = failedAttempts.get(ip);
    if (!attempts) return false;

    const elapsedTime = Date.now() - attempts.time;
    return attempts.count >= 3 && elapsedTime < 10 * 60 * 1000; // 10 dakika
}

module.exports = { addFailedAttempt, isLockedOut };
