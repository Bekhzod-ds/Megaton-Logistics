import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("=== STARTING BOT DIRECTLY ===")
logger.info(f"PORT: {os.environ.get('PORT')}")

# Check essential environment variables
required_vars = ['BOT_TOKEN', 'CREDENTIALS_BASE64', 'SHEET1_ID', 'SHEET2_ID']
for var in required_vars:
    value = os.environ.get(var)
    logger.info(f"{var}: {'SET' if value else 'MISSING'} ({len(value) if value else 0} chars)")

# Import and run bot
try:
    from bot import main
    logger.info("Bot imported successfully, starting main()...")
    main()
except Exception as e:
    logger.error(f"Failed to start bot: {e}", exc_info=True)
