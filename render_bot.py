import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("=== BOT STARTING ===")

# Check environment variables
required_vars = ['BOT_TOKEN', 'CREDENTIALS_BASE64', 'SHEET1_ID', 'SHEET2_ID']
for var in required_vars:
    value = os.getenv(var)
    logger.info(f"{var}: {'SET' if value else 'MISSING'}")

# Import and run the bot directly
try:
    from bot import TelegramBot
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("NO BOT_TOKEN!")
        exit(1)
    
    logger.info("Creating bot instance...")
    bot = TelegramBot(bot_token)
    logger.info("Starting bot polling...")
    bot.run()  # This should be a synchronous method
    
except Exception as e:
    logger.error(f"ERROR: {e}")
    logger.error("Full traceback:", exc_info=True)
    exit(1)
