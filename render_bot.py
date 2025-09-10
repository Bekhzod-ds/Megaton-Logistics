import os
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if all required environment variables are set."""
    logger.info("=== CHECKING ENVIRONMENT VARIABLES ===")
    
    required_vars = ['BOT_TOKEN', 'CREDENTIALS_BASE64', 'SHEET1_ID', 'SHEET2_ID']
    all_set = True
    
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            logger.info(f"✅ {var}: SET ({len(value)} characters)")
        else:
            logger.error(f"❌ {var}: MISSING")
            all_set = False
    
    return all_set

if __name__ == "__main__":
    logger.info("=== STARTING TELEGRAM BOT ON RENDER ===")
    
    # Check environment variables first
    if not check_environment():
        logger.error("Missing required environment variables! Bot cannot start.")
        exit(1)
    
    # Import and run the bot
    try:
        logger.info("Importing and starting bot...")
        
        # Import your bot components
        from bot import TelegramBot
        import os
        
        # Get bot token
        bot_token = os.getenv("BOT_TOKEN")
        logger.info(f"Creating bot instance with token length: {len(bot_token) if bot_token else 0}")
        
        # Create and run bot
        bot = TelegramBot(bot_token)
        logger.info("Starting bot polling...")
        bot.run()
        
    except Exception as e:
        logger.error(f"❌ FAILED TO START BOT: {e}")
        logger.error("Full error:", exc_info=True)
        # Exit with error code so Render can restart it
        exit(1)
