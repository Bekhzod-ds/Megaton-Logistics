from flask import Flask
import threading
import os
import logging
from bot import main  # Import your main function

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Function to run the bot in a separate thread
def run_bot():
    try:
        logger.info("Starting Telegram Bot...")
        main()
    except Exception as e:
        logger.error(f"Error in bot thread: {e}")
        logger.error("Bot thread crashed!")

@app.route('/')
def home():
    return "Telegram Bot is running! ✅"

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    logger.info("Starting application...")
    
    # Get port from Render environment variable, default to 10000 for local testing
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Using port: {port}")
    
    # Start the bot in a background thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("Bot thread started. Starting Flask server...")
    
    # Start the Flask server with the correct port
    app.run(host='0.0.0.0', port=port)
