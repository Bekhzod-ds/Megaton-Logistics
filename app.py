import os
import logging
from flask import Flask, request, jsonify

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Get environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')

if not WEBHOOK_URL:
    logger.warning("WEBHOOK_URL environment variable not set yet")

@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Telegram Bot is running!"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # This will be handled by your bot's webhook setup
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        if not WEBHOOK_URL:
            return jsonify({"status": "error", "message": "WEBHOOK_URL not configured"}), 400
        
        # Import here to avoid circular imports
        from bot import TelegramBot
        
        # Initialize bot and set webhook
        bot = TelegramBot(BOT_TOKEN)
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        # Set webhook using your bot's method
        success = bot.set_webhook(webhook_url)
        
        return jsonify({
            "status": "success", 
            "webhook_set": success, 
            "url": webhook_url
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
