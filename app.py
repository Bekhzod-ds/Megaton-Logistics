import os
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, ContextTypes

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize bot with your existing code
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Handle WEBHOOK_URL gracefully - it might not be set initially
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
if WEBHOOK_URL:
    WEBHOOK_URL += '/webhook'
else:
    logger.warning("WEBHOOK_URL environment variable not set yet")

# Import and initialize your existing TelegramBot class
from bot import TelegramBot

# Create your bot instance
telegram_bot = TelegramBot(BOT_TOKEN)
application = telegram_bot.application

@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Telegram Bot is running!"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Process webhook update using YOUR existing bot handlers
        update = Update.de_json(request.get_json(), application.bot)
        application.process_update(update)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        if not WEBHOOK_URL:
            return jsonify({"status": "error", "message": "WEBHOOK_URL not configured"}), 400
        
        success = application.bot.set_webhook(WEBHOOK_URL)
        return jsonify({"status": "success", "webhook_set": success, "url": WEBHOOK_URL})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def initialize_bot():
    """Initialize bot with webhook"""
    try:
        if WEBHOOK_URL:
            application.bot.set_webhook(WEBHOOK_URL)
            logger.info(f"Webhook set to: {WEBHOOK_URL}")
        else:
            logger.warning("Skipping webhook setup - WEBHOOK_URL not available")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Initialize when app starts
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    initialize_bot()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
