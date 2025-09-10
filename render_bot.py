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

async def run_bot():
    """Run the bot with proper asyncio event loop."""
    try:
        logger.info("Importing bot module...")
        from bot import main
        
        logger.info("Starting main bot function...")
        await main()  # If your main() is async
        
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
    
    # Run the bot with proper asyncio event loop
    try:
        asyncio.run(run_bot())
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        # Exit with error code so Render can restart it
        exit(1)
