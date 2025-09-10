from flask import Flask
import threading
import os
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Function to run the bot in a separate thread
def run_bot():
    try:
        logger.info("=== BOT THREAD STARTING ===")
        logger.info(f"BOT_TOKEN exists: {bool(os.environ.get('BOT_TOKEN'))}")
        logger.info(f"CREDENTIALS_BASE64 exists: {bool(os.environ.get('CREDENTIALS_BASE64'))}")
        
        # Import here to catch any import errors
        from bot import main
        logger.info("Bot module imported successfully")
        
        main()
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR in bot thread: {e}")
        logger.error("Full error traceback:", exc_info=True)
        # Keep restarting the bot thread if it crashes
        logger.info("Restarting bot thread in 5 seconds...")
        time.sleep(5)
        run_bot()

@app.route('/')
def home():
    return "Telegram Bot is running! ✅"

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    logger.info("=== APPLICATION STARTING ===")
    logger.info(f"PORT: {os.environ.get('PORT')}")
    logger.info(f"All environment variables: {list(os.environ.keys())}")
    
    # Get port from Render environment variable
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Using port: {port}")
    
    # Start the bot in a background thread
    bot_thread = threading.Thread(target=run_bot, name="TelegramBotThread")
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("Bot thread started. Starting Flask server...")
    
    # Start the Flask server
    app.run(host='0.0.0.0', port=port)
