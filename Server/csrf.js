const crypto = require('crypto');

function csrfMiddleware(req, res, next) {
    if (req.method === 'POST') {
        const clientCsrfToken = req.headers['x-csrf-token'];
        const serverCsrfToken = req.session.csrfToken;

        if (!clientCsrfToken || clientCsrfToken !== serverCsrfToken) {
            return res.status(403).json({ error: 'CSRF doğrulaması başarısız' });
        }
    } else {
        req.session.csrfToken = crypto.randomBytes(16).toString('hex');
    }
    next();
}

module.exports = csrfMiddleware;
