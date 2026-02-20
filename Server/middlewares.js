const jwt = require('jsonwebtoken');
const { logAccess } = require('./utils/logger');

const SECRET_KEY = process.env.JWT_SECRET;
if (!SECRET_KEY) {
    throw new Error('JWT_SECRET environment variable is required');
}

function verifyJWT(req, res, next) {
    const token = req.headers.authorization?.split(' ')[1];
    if (!token) return res.status(401).json({ error: 'Yetkisiz erişim' });

    try {
        req.user = jwt.verify(token, SECRET_KEY);
        logAccess(req.user.id, req.ip); // Giriş yapan kullanıcı loglanır
        next();
    } catch (err) {
        return res.status(401).json({ error: 'Geçersiz veya süresi dolmuş token' });
    }
}

module.exports = { verifyJWT };
