from flask import Flask
import threading
import os
from bot import main  # Import your main function

app = Flask(__name__)

# Function to run the bot in a separate thread
def run_bot():
    print("Starting Telegram Bot...")
    main()

@app.route('/')
def home():
    return "Telegram Bot is running! ✅"

if __name__ == '__main__':
    # Start the bot in a background thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True  # This thread will exit when the main thread exits
    bot_thread.start()
    print("Bot thread started. Starting Flask server...")
    
    # Start the Flask server
    app.run(host='0.0.0.0', port=10000)
