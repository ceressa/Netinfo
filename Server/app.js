require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const authRoutes = require('./routes/authRoutes');
const protectedRoutes = require('./routes/protectedRoutes');
const csrfMiddleware = require('./csrf');

const app = express();
const PORT = 3000;

// Middleware
app.use(bodyParser.json());
app.use(csrfMiddleware); // CSRF korumasını global olarak ekle

// Rotalar
app.use('/auth', authRoutes); // Giriş işlemleri
app.use('/protected', protectedRoutes); // Korunan işlemler

// Sunucu başlatma
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});
