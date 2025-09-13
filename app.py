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
WEBHOOK_URL = os.environ.get('WEBHOOK_URL') + '/webhook'

# Import and initialize your existing TelegramBot class
from bot import TelegramBot

# Create your bot instance (this will initialize with all your handlers)
telegram_bot = TelegramBot(BOT_TOKEN)
application = telegram_bot.application  # Get the application from your bot instance

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
        webhook_url = f"{WEBHOOK_URL}"
        success = application.bot.set_webhook(webhook_url)
        return jsonify({"status": "success", "webhook_set": success, "url": webhook_url})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def initialize_bot():
    """Initialize bot with webhook"""
    try:
        webhook_url = f"{WEBHOOK_URL}"
        application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
        logger.info("Bot initialized with all your existing handlers")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Initialize when app starts
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    initialize_bot()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
