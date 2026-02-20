const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const { addFailedAttempt, isLockedOut } = require('./utils/limiter');

const SECRET_KEY = process.env.JWT_SECRET || 'your_secret_key'; // .env dosyasından alınır
const HASHED_PASSWORD = '$2b$10$yourHashedPassword'; // Conquer34 için hashlenmiş hali

// Şifre hashleme (Bir kere çalıştır, .env'e koy)
bcrypt.hash('Conquer34', 10).then(console.log); // => Hash sonucu

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
