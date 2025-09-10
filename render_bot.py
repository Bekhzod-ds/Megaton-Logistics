import os
import logging
import asyncio

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

async def run_bot_async():
    """Run the bot using async."""
    try:
        logger.info("Importing bot module...")
        from bot import TelegramBot
        import os
        
        # Get bot token
        bot_token = os.getenv("BOT_TOKEN")
        logger.info(f"Creating bot instance with token length: {len(bot_token) if bot_token else 0}")
        
        # Create bot instance
        bot = TelegramBot(bot_token)
        logger.info("Starting async bot polling...")
        
        # Run the async polling
        await bot.application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ FAILED TO START BOT: {e}")
        logger.error("Full error:", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("=== STARTING TELEGRAM BOT ON RENDER ===")
    
    # Check environment variables first
    if not check_environment():
        logger.error("Missing required environment variables! Bot cannot start.")
        exit(1)
    
    # Run the async bot
    try:
        asyncio.run(run_bot_async())
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        exit(1)
