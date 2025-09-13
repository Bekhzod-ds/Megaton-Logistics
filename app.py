import os
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, ContextTypes

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize bot with your existing code
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')  # Just the base URL, without /webhook

if not WEBHOOK_URL:
    logger.warning("WEBHOOK_URL environment variable not set yet")
else:
    logger.info(f"WEBHOOK_URL: {WEBHOOK_URL}")

# Import and initialize your existing TelegramBot class
from bot import TelegramBot

# Create your bot instance
telegram_bot = TelegramBot(BOT_TOKEN)
application = telegram_bot.application

# Create a thread-safe way to run async functions
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Telegram Bot is running!"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Process webhook update using YOUR existing bot handlers
        update = Update.de_json(request.get_json(), application.bot)
        
        # Run the async process_update in a thread-safe way
        run_async(application.process_update(update))
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        if not WEBHOOK_URL:
            return jsonify({"status": "error", "message": "WEBHOOK_URL not configured"}), 400
        
        # Create the correct webhook URL by adding /webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        # Set webhook
        success = run_async(application.bot.set_webhook(webhook_url))
        
        return jsonify({
            "status": "success", 
            "webhook_set": success, 
            "url": webhook_url
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get_webhook_info', methods=['GET'])
def get_webhook_info():
    try:
        webhook_info = run_async(application.bot.get_webhook_info())
        return jsonify({
            "status": "success",
            "webhook_info": {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_date": webhook_info.last_error_date,
                "last_error_message": webhook_info.last_error_message,
                "max_connections": webhook_info.max_connections,
                "allowed_updates": webhook_info.allowed_updates
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def initialize_bot():
    """Initialize bot with webhook"""
    try:
        if WEBHOOK_URL:
            # Create the correct webhook URL by adding /webhook
            webhook_url = f"{WEBHOOK_URL}/webhook"
            
            # Remove any existing webhook first
            run_async(application.bot.delete_webhook())
            
            # Set new webhook
            run_async(application.bot.set_webhook(webhook_url))
            
            logger.info(f"Webhook set to: {webhook_url}")
            
            # Get webhook info to verify
            webhook_info = run_async(application.bot.get_webhook_info())
            logger.info(f"Webhook info: {webhook_info.url}")
            
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
