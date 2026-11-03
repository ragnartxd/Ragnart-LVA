// whatsappBot.js

const PORT = process.env.PORT || 3001; // Definir el puerto antes de usarlo

const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const openModule = require('open');
const open = openModule.default || openModule;
const QRCode = require('qrcode'); // Para generar el QR como imagen

// Crear la aplicación Express
const app = express();
app.use(express.json());

app.get('/status', (req, res) => {
    res.json({ running: true, whatsappReady: clienteListo });
});

// Inicializar el cliente de WhatsApp con LocalAuth
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox']
    }
});

let ultimoQR = null;
let clienteListo = false;
let qrMostrado = false; // Bandera para evitar mostrar QR múltiples veces

// Evento para mostrar el código QR en la consola
client.on('qr', async (qr) => {
    ultimoQR = qr;
    
    // Solo mostrar QR si no se ha mostrado antes
    if (!qrMostrado) {
        console.log('📱 Generando código QR y abriendo ventana local...');
        qrMostrado = true;
        
        try {
            // Generar el QR como Data URL
            const qrDataURL = await QRCode.toDataURL(qr);
            
            // Crear HTML completo con el QR embebido
            const htmlContent = `
                <!DOCTYPE html>
                <html>
                <head>
                    <title>QR de WhatsApp</title>
                    <meta charset="UTF-8">
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            display: flex;
                            flex-direction: column;
                            align-items: center;
                            justify-content: center;
                            min-height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #25D366, #128C7E);
                            color: white;
                        }
                        .container {
                            text-align: center;
                            background: rgba(255, 255, 255, 0.1);
                            padding: 30px;
                            border-radius: 15px;
                            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                            backdrop-filter: blur(10px);
                        }
                        h2 {
                            margin-bottom: 20px;
                            font-size: 24px;
                        }
                        .qr-image {
                            border: 10px solid white;
                            border-radius: 15px;
                            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
                            background: white;
                            padding: 10px;
                        }
                        .instructions {
                            margin-top: 20px;
                            font-size: 16px;
                            opacity: 0.9;
                        }
                        .refresh-btn {
                            margin-top: 20px;
                            padding: 10px 20px;
                            background: #25D366;
                            color: white;
                            border: none;
                            border-radius: 5px;
                            cursor: pointer;
                            font-size: 16px;
                            transition: background 0.3s;
                        }
                        .refresh-btn:hover {
                            background: #1ea952;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>🔗 Conectar WhatsApp</h2>
                        <img src="${qrDataURL}" class="qr-image" alt="QR Code" />
                        <div class="instructions">
                            <p>1. Abre WhatsApp en tu teléfono</p>
                            <p>2. Ve a <strong>Configuración → Dispositivos vinculados</strong></p>
                            <p>3. Toca <strong>Vincular un dispositivo</strong></p>
                            <p>4. Escanea este código QR</p>
                        </div>
                        <button class="refresh-btn" onclick="location.reload()">
                            🔄 Actualizar QR
                        </button>
                    </div>
                </body>
                </html>
            `;
            
            // Crear un data URL con el HTML completo
            const htmlDataURL = 'data:text/html;charset=utf-8,' + encodeURIComponent(htmlContent);
            
            // Abrir el navegador con el HTML embebido
            await open(`http://localhost:${PORT}/qr`);
            
            console.log('✅ Ventana del QR abierta en el navegador');
            
        } catch (error) {
            console.error('❌ Error al generar o abrir el QR:', error);
            // Fallback: abrir la ruta web normal
            open(`http://localhost:${PORT}/qr`);
        }
    } else {
        console.log('🔄 QR actualizado (ventana ya abierta)');
    }
});

// Evento cuando el cliente está listo
client.on('ready', () => {
    clienteListo = true;
    console.log('✅ Cliente de WhatsApp listo!');
});

// Manejo de fallos en la autenticación
client.on('auth_failure', (msg) => {
    console.error('🚨 Fallo de autenticación:', msg);
    clienteListo = false;
    qrMostrado = false; // Resetear para permitir mostrar QR nuevamente
});

// Evento para cuando se desconecta el cliente
client.on('disconnected', (reason) => {
    clienteListo = false;
    console.log('🔌 Cliente desconectado:', reason);
    // NO reinicializar automáticamente, mantener la sesión
});

// Inicializar el cliente (única llamada)
client.initialize();

// Endpoint para mostrar el QR en una página web (mantenido como fallback)
app.get('/qr', (req, res) => {
    if (!ultimoQR) {
        return res.send('<h2>No hay QR disponible. Espera a que se genere uno.</h2>');
    }
    QRCode.toDataURL(ultimoQR, (err, url) => {
        if (err) return res.send('Error generando el QR');
        res.send(`
            <html>
            <head><title>QR de WhatsApp</title></head>
            <body style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;">
                <h2>Escanea este código QR con WhatsApp</h2>
                <img src="${url}" />
            </body>
            </html>
        `);
    });
});

// Endpoint para enviar mensajes
app.post('/send', async (req, res) => {
    if (!clienteListo) {
        return res.status(503).json({ error: 'El cliente de WhatsApp no está listo. Escanea el QR y espera el mensaje de confirmación.' });
    }
    try {
        let { number, message } = req.body;
        
        // Validar que se envíen los parámetros requeridos
        if (!number || !message) {
            return res.status(400).json({ error: "Faltan parámetros: 'number' y 'message' son requeridos." });
        }

        // Asegurarse de que el número tenga el formato correcto (ej. +573XXXXXXXX)
        if (!number.startsWith('+')) {
            number = `+${number}`;
        }

        // Generar el chatId en el formato requerido: se eliminan caracteres no numéricos y se añade '@c.us'
        const chatId = number.replace(/[^0-9]/g, '') + '@c.us';

        // Enviar el mensaje
        const result = await client.sendMessage(chatId, message);
        console.log(`✅ Mensaje enviado a ${chatId}`);
        return res.status(200).json({ status: 'Mensaje enviado', result });
    } catch (error) {
        console.error('❌ Error al enviar el mensaje:', error);
        return res.status(500).json({ error: 'Error al enviar el mensaje', details: error.toString() });
    }
});

// Configurar y arrancar el servidor en el puerto 3500 (o el que definas)
app.listen(PORT, () => {
    console.log(`🚀 Servidor corriendo en el puerto ${PORT}`);
});