import os
import logging
from flask import Flask, request, jsonify
import telegram
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google_sheets import GoogleSheetsHelper  # Keep your existing import

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize bot
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL') + '/webhook'  # Render provides URL

# Initialize your bot application
application = Application.builder().token(BOT_TOKEN).build()

# Add your existing handlers (simplified version)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! Bot is working with webhooks!')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f'You said: {update.message.text}')

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Telegram Bot is running!"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Process webhook update
        update = Update.de_json(request.get_json(), application.bot)
        application.process_update(update)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        # Set webhook URL
        webhook_url = f"{WEBHOOK_URL}"
        success = application.bot.set_webhook(webhook_url)
        return jsonify({"status": "success", "webhook_set": success, "url": webhook_url})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def initialize_bot():
    """Initialize bot with webhook"""
    try:
        # Set webhook on startup
        webhook_url = f"{WEBHOOK_URL}"
        application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Initialize when app starts
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':  # Avoid double initialization
    initialize_bot()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
