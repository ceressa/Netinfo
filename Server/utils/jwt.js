const jwt = require('jsonwebtoken');

function createJWT(payload, secret, expiresIn) {
    return jwt.sign(payload, secret, { expiresIn });
}

function verifyJWT(token, secret) {
    return jwt.verify(token, secret);
}

module.exports = { createJWT, verifyJWT };
