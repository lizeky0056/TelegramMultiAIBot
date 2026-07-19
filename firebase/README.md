# ☁️ Despliegue en Firebase de Boty Generator

Este directorio contiene la versión **Serverless** de Boty Generator, diseñada para correr gratis 24/7 en **Firebase Cloud Functions** e integrarse con **Firebase Firestore** como base de datos.

## ⚠️ Requisitos Críticos
1. **Plan Blaze de Firebase**: Para que la Cloud Function pueda hacer llamadas HTTP salientes a las APIs externas (Telegram API, Gemini API, OpenAI, Claude, Grok), debes actualizar tu proyecto de Firebase del plan gratuito *Spark* al plan de pago por uso *Blaze* (es gratuito para consumos bajos, pero requiere añadir método de pago).
2. **Firestore Database**: Asegúrate de haber creado tu base de datos Firestore en la consola de Firebase.

## 🚀 Pasos para Desplegar

### 1. Despliegue en Firebase
Abre una terminal en esta carpeta (`D:\TelegramMultiAIBot\firebase`) y corre el comando:
```bash
firebase deploy --only functions
```
Cuando finalice, Firebase te mostrará la URL pública de tu Cloud Function, por ejemplo:
`https://us-central1-tikreader-e4c39.cloudfunctions.net/boty_generator`

### 2. Configurar Variables de Entorno en Cloud Functions
Para que tu función en la nube conozca el Token de tu bot y su propia URL, configúralas en la consola de Google Cloud Run / Firebase, o simplemente añádelas como variables en la nube:
- `BOT_TOKEN` = `8886104559:AAHclO0tYWadm4eMMrPB1C3PjQI6uqOps4U`
- `WEB_URL` = `https://<TU_REGION>-<TU_PROYECTO>.cloudfunctions.net/boty_generator`

### 3. Registrar el Webhook en Telegram
Para avisarle a Telegram que redirija todos los mensajes de tu bot a la nube, corre nuestro script automatizado:
```bash
python set_webhook.py
```
Pega la URL de tu función cuando te la pida y ¡listo! Telegram confirmará el registro.
