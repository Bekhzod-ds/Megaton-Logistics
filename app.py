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

# Initialize variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
application = None

if not WEBHOOK_URL:
    logger.warning("WEBHOOK_URL environment variable not set yet")
else:
    logger.info(f"WEBHOOK_URL: {WEBHOOK_URL}")

def run_async(coro):
    """Helper to run async functions in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def initialize_application():
    """Initialize the Telegram bot application"""
    global application
    try:
        from bot import TelegramBot
        logger.info("Initializing Telegram bot...")
        
        # Create your bot instance
        telegram_bot = TelegramBot(BOT_TOKEN)
        application = telegram_bot.application
        
        # Initialize the application properly
        run_async(application.initialize())
        logger.info("Telegram bot initialized successfully")
        
        return application
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise

@app.before_first_request
def before_first_request():
    """Initialize the application before first request"""
    if application is None:
        initialize_application()

@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Telegram Bot is running!"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if application is None:
            initialize_application()
            
        # Process webhook update
        update = Update.de_json(request.get_json(), application.bot)
        
        # Run the async process_update
        run_async(application.process_update(update))
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        if application is None:
            initialize_application()
            
        if not WEBHOOK_URL:
            return jsonify({"status": "error", "message": "WEBHOOK_URL not configured"}), 400
        
        # Create the correct webhook URL
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
        if application is None:
            initialize_application()
            
        webhook_info = run_async(application.bot.get_webhook_info())
        return jsonify({
            "status": "success",
            "webhook_info": {
                "url": webhook_info.url,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_message": webhook_info.last_error_message,
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Initialize on startup
try:
    if BOT_TOKEN and WEBHOOK_URL:
        initialize_application()
        
        # Set webhook on startup
        webhook_url = f"{WEBHOOK_URL}/webhook"
        run_async(application.bot.set_webhook(webhook_url))
        logger.info(f"Webhook set to: {webhook_url}")
        
except Exception as e:
    logger.error(f"Startup initialization failed: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
