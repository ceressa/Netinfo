const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const { addFailedAttempt, isLockedOut } = require('./utils/limiter');

const SECRET_KEY = process.env.JWT_SECRET;
if (!SECRET_KEY) {
    throw new Error('JWT_SECRET environment variable is required');
}
const HASHED_PASSWORD = process.env.ADMIN_BCRYPT_HASH;
if (!HASHED_PASSWORD) {
    throw new Error('ADMIN_BCRYPT_HASH environment variable is required');
}

async function login(req, res) {
    const { username, password } = req.body;

    // Kullanıcı IP'sine göre limit kontrolü
    const ip = req.ip;
    if (isLockedOut(ip)) {
        return res.status(429).json({ error: 'Çok fazla deneme, 10 dakika sonra tekrar deneyin.' });
    }

    const isPasswordValid = await bcrypt.compare(password, HASHED_PASSWORD);
    if (!isPasswordValid) {
        addFailedAttempt(ip);
        return res.status(401).json({ error: 'Geçersiz kullanıcı adı veya şifre' });
    }

    // JWT oluştur
    const token = jwt.sign({ id: username }, SECRET_KEY, { expiresIn: '1h' });
    res.json({ token });
}

module.exports = { login };
