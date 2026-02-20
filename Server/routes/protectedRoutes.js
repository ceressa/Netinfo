const express = require('express');
const { verifyJWT } = require('../middlewares');

const router = express.Router();

// Korunan bir rota
router.get('/dashboard', verifyJWT, (req, res) => {
    res.json({ message: `Hoşgeldin ${req.user.id}` });
});

module.exports = router;
