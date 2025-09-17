import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    ConversationHandler, 
    MessageHandler, 
    filters, 
    CallbackQueryHandler
)
from google_sheets import GoogleSheetsHelper
from datetime import datetime, timedelta
import pytz

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
SELECTING_ACTION, SELECTING_DATE, SELECTING_KOD, ENTERING_ADDRESS, ENTERING_TRANSPORT, ENTERING_PHONE, \
ENTERING_CARD, ENTERING_AMOUNT, CONFIRMING_OVERWRITE, EDITING_FIELD, \
REVIEW_SUMMARY = range(11)  # Removed SELECTING_PAYMENT_STATUS

# Initialize Google Sheets helper
sheets_helper = GoogleSheetsHelper()

class TelegramBot:
    def __init__(self, token):
        """Initialize the Telegram bot."""
        self.token = token
        self.application = Application.builder().token(token).build()
        
        # Add conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                SELECTING_ACTION: [
                    MessageHandler(filters.Regex("^(Yangi Buyurtma|Eski Buyurtma)$"), self.select_action)
                ],
                SELECTING_DATE: [
                    CallbackQueryHandler(self.select_date, pattern="^(yesterday|today|tomorrow|back_to_action|change_action)$")
                ],
                SELECTING_KOD: [
                    CallbackQueryHandler(self.select_kod),
                    CallbackQueryHandler(self.back_to_date, pattern="^back_to_date$")
                ],
                ENTERING_ADDRESS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_address),
                    CallbackQueryHandler(self.back_to_kod, pattern="^back_to_kod$")
                ],
                ENTERING_TRANSPORT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_transport),
                    CallbackQueryHandler(self.back_to_address, pattern="^back_to_address$")
                ],
                ENTERING_PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_phone),
                    CallbackQueryHandler(self.back_to_transport, pattern="^back_to_transport$")
                ],
                ENTERING_CARD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_card),
                    CallbackQueryHandler(self.back_to_phone, pattern="^back_to_phone$")
                ],
                ENTERING_AMOUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_amount),
                    CallbackQueryHandler(self.back_to_card, pattern="^back_to_card$")
                ],
                REVIEW_SUMMARY: [
                    CallbackQueryHandler(self.process_summary_action, pattern="^(confirm_submit|edit_field:.+)$"),
                    CallbackQueryHandler(self.back_to_amount, pattern="^back_to_amount$")
                ],
                CONFIRMING_OVERWRITE: [
                    CallbackQueryHandler(self.confirm_overwrite, pattern="^(edit|overwrite)$")
                ],
                EDITING_FIELD: [
                    CallbackQueryHandler(self.edit_field),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.update_field),
                    CallbackQueryHandler(self.back_to_summary, pattern="^back_to_summary$")
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            allow_reentry=True
        )
        
        self.application.add_handler(conv_handler)
        
        # Add a separate handler for /start command that can interrupt any conversation
        #1 self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("change", self.change_action))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("start", self.force_start))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Send message on `/start` and ask user to choose an action. Completely resets the conversation."""
        user = update.message.from_user
        logger.info("User %s started the conversation.", user.first_name)
        
        # Clear all user data thoroughly
        context.user_data.clear()
        
        # Initialize fresh navigation stack
        context.user_data["navigation_stack"] = [SELECTING_ACTION]
        context.user_data["last_activity"] = datetime.now()
        
        # Create keyboard with options
        reply_keyboard = [["Yangi Buyurtma", "Eski Buyurtma"]]
        
        # Check if we need to edit an existing message or send a new one
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                "🔄 Assalomu alaykum! Bot yangilandi.\n"
                "Quyidagilardan birini tanlang:",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, 
                    one_time_keyboard=True, 
                    input_field_placeholder="Yangi Buyurtma yoki Eski Buyurtma?"
                ),
            )
        else:
            await update.message.reply_text(
                "Assalomu alaykum! Botimizga xush kelibsiz.\n"
                "Quyidagilardan birini tanlang:",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, 
                    one_time_keyboard=True, 
                    input_field_placeholder="Yangi Buyurtma yoki Eski Buyurtma?"
                ),
            )
        
        return SELECTING_ACTION

    # Add this method to handle /start commands that interrupt conversations
    async def force_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Force start a new conversation regardless of current state."""
        # Clear all user data
        context.user_data.clear()
        
        # Call the regular start method
        return await self.start(update, context)

    async def change_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Allow user to change their action selection (Yangi/Eski)."""
        # Clear relevant user data but keep navigation stack
        keys_to_keep = ["navigation_stack"]
        keys_to_remove = [key for key in context.user_data.keys() if key not in keys_to_keep]
        
        for key in keys_to_remove:
            if key in context.user_data:
                del context.user_data[key]
        
        # Create keyboard with options
        reply_keyboard = [["Yangi Buyurtma", "Eski Buyurtma"]]
        
        # Check if this is a callback query or regular message
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            await query.answer()
            
            await query.edit_message_text(
                "Qaysi amalni tanlamoqchisiz?\n"
                "Quyidagilardan birini tanlang:",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, 
                    one_time_keyboard=True, 
                    input_field_placeholder="Yangi Buyurtma yoki Eski Buyurtma?"
                ),
            )
        else:
            await update.message.reply_text(
                "Qaysi amalni tanlamoqchisiz?\n"
                "Quyidagilardan birini tanlang:",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, 
                    one_time_keyboard=True, 
                    input_field_placeholder="Yangi Buyurtma yoki Eski Buyurtma?"
                ),
            )
        
        # Update navigation stack - keep only SELECTING_ACTION
        if "navigation_stack" in context.user_data:
            context.user_data["navigation_stack"] = [SELECTING_ACTION]
        else:
            context.user_data["navigation_stack"] = [SELECTING_ACTION]
        
        return SELECTING_ACTION

    async def select_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ask user to select a date."""
        user_choice = update.message.text
        
        # Initialize navigation stack if not exists
        if "navigation_stack" not in context.user_data:
            context.user_data["navigation_stack"] = []
        
        # Store user choice
        context.user_data["action"] = user_choice
        
        # Show date selection buttons
        keyboard = [
            [InlineKeyboardButton("Kecha", callback_data="yesterday")],
            [InlineKeyboardButton("Bugun", callback_data="today")],
            [InlineKeyboardButton("Ertaga", callback_data="tomorrow")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Iltimos, sanani tanlang:",
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        context.user_data["navigation_stack"].append(SELECTING_DATE)
        
        return SELECTING_DATE

    async def select_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle date selection and show available KODs."""
        query = update.callback_query
        await query.answer()
        
        date_choice = query.data
        
        # Handle back navigation
        if date_choice == "back_to_action":
            return await self.back_to_action(update, context)
        
        # Handle change action request
        if date_choice == "change_action":
            return await self.change_action(update, context)
        
        # Calculate the selected date WITH UZBEKISTAN TIMEZONE
        uzb_timezone = pytz.timezone('Asia/Tashkent')
        now_uzb = datetime.now(uzb_timezone)
        today = now_uzb.date()
        
        if date_choice == "yesterday":
            selected_date = today - timedelta(days=1)
        elif date_choice == "today":
            selected_date = today
        elif date_choice == "tomorrow":
            selected_date = today + timedelta(days=1)
        
        date_str = selected_date.strftime("%Y-%m-%d")

        # Store selected date
        context.user_data["selected_date"] = date_str
        
        # Determine if we need KODs with or without info based on user action
        user_action = context.user_data.get("action", "")
        only_empty = user_action == "Yangi Buyurtma"  # True for new orders, False for existing orders
        
        # Get KODs from Excel based on the action type
        kods = sheets_helper.get_available_kods(date_str, only_empty=only_empty)
        
        if not kods:
            if only_empty:
                message = (f"{date_str} sanasi uchun barcha KODlar allaqachon to'ldirilgan yoki hech qanday KOD mavjud emas.")
            else:
                message = (f"{date_str} sanasi uchun hech qanday to'ldirilgan KOD topilmadi.")
            
            await query.edit_message_text(
                f"{message}\n\nIltimos, boshqa sana tanlang yoki keyinroq urunib ko'ring."
            )
            return ConversationHandler.END
        
        # Create inline keyboard with KOD options
        keyboard = []
        for kod in kods:
            keyboard.append([InlineKeyboardButton(kod, callback_data=kod)])
        
        # Add back button and change action button
        keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_date")])
        keyboard.append([InlineKeyboardButton("🔄 Tanlovni o'zgartirish", callback_data="change_action")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if only_empty:
            message_text = (f"Tanlangan sana: {date_str}\n\n"
                           "Quyidagi KODlardan transport va telefon ma'lumotlarini kiritishingiz kerak:\n\n"
                           "Iltimos, KODni tanlang:")
        else:
            message_text = (f"Tanlangan sana: {date_str}\n\n"
                           "Quyidagi to'ldirilgan KODlarni tahrirlashingiz mumkin:\n\n"
                           "Iltimos, KODni tanlang:")
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        context.user_data["navigation_stack"].append(SELECTING_KOD)
        
        return SELECTING_KOD

    async def back_to_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Navigate back to date selection."""
        query = update.callback_query
        await query.answer()
        
        # Update navigation stack
        if "navigation_stack" in context.user_data and SELECTING_KOD in context.user_data["navigation_stack"]:
            context.user_data["navigation_stack"].remove(SELECTING_KOD)
        
        # Show date selection buttons again
        keyboard = [
            [InlineKeyboardButton("Kecha", callback_data="yesterday")],
            [InlineKeyboardButton("Bugun", callback_data="today")],
            [InlineKeyboardButton("Ertaga", callback_data="tomorrow")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Iltimos, sanani tanlang:",
            reply_markup=reply_markup
        )
        
        return SELECTING_DATE

    async def back_to_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Navigate back to action selection."""
        query = update.callback_query
        await query.answer()
        
        # Update navigation stack
        if "navigation_stack" in context.user_data and SELECTING_DATE in context.user_data["navigation_stack"]:
            context.user_data["navigation_stack"].remove(SELECTING_DATE)
        
        # Create keyboard with options
        reply_keyboard = [["Yangi Buyurtma", "Eski Buyurtma"]]
        
        await query.edit_message_text(
            "Quyidagilardan birini tanlang:",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, 
                one_time_keyboard=True, 
                input_field_placeholder="Yangi Buyurtma yoki Eski Buyurtma?"
            ),
        )
        
        return SELECTING_ACTION

    async def select_kod(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle KOD selection and check if it already exists."""
        query = update.callback_query
        await query.answer()
        
        # Handle back button first
        if query.data == "back_to_date":
            return await self.back_to_date(update, context)
        
        kod = query.data
        
        # Store selected KOD
        context.user_data["kod"] = kod
        
        # Get selected date
        selected_date = context.user_data.get("selected_date", datetime.now().strftime("%Y-%m-%d"))
        
        # Get user action to determine the flow
        user_action = context.user_data.get("action", "")
        
        # For "Eski Buyurtma", check if order exists in Sheet1
        if user_action == "Eski Buyurtma":
            existing_order = sheets_helper.get_existing_order(kod, selected_date)
            
            if existing_order:
                # Show existing order and ask for confirmation to edit/overwrite
                tolov_summasi = existing_order.get('To\'lov_summasi', 'N/A')
                
                order_text = (
                    f"Mavjud buyurtma:\n"
                    f"Sana: {selected_date}\n"
                    f"KOD: {existing_order.get('KOD', 'N/A')}\n"
                    f"Manzil: {existing_order.get('Manzil', 'N/A')}\n"
                    f"Transport raqami: {existing_order.get('Transport_raqami', 'N/A')}\n"
                    f"Haydovchi telefon: {existing_order.get('Haydovchi_telefon', 'N/A')}\n"
                    f"Karta raqami: {existing_order.get('Karta_raqami', 'N/A')}\n"
                    f"To'lov summasi: {tolov_summasi}\n\n"
                    "Mavjud yozuv bor. O'zgartirasizmi yoki ustidan yozasizmi?"
                )
                
                keyboard = [
                    [
                        InlineKeyboardButton("O'zgartirish", callback_data="edit"),
                        InlineKeyboardButton("Ustidan yozish", callback_data="overwrite")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text=order_text,
                    reply_markup=reply_markup
                )
                
                # Store existing order data for potential editing
                context.user_data["existing_order"] = existing_order
                
                return CONFIRMING_OVERWRITE
            else:
                # No existing order found for "Eski Buyurtma"
                await query.edit_message_text(
                    text=f"❌ {selected_date} sanasida '{kod}' KODi uchun buyurtma topilmadi.\n\n"
                         "Iltimos, boshqa KOD yoki sana tanlang.\n\n"
                         "Yangi buyurtma uchun /start ni bosing."
                )
                return ConversationHandler.END
                    
        else:  # "Yangi Buyurtma" - existing logic
            # ... keep the existing Yangi Buyurtma logic ...
            existing_order = sheets_helper.get_existing_order(kod, selected_date)
            
            if existing_order:
                # Existing order found for "Yangi Buyurtma" - ask what to do
                keyboard = [
                    [
                        InlineKeyboardButton("O'zgartirish", callback_data="edit"),
                        InlineKeyboardButton("Ustidan yozish", callback_data="overwrite")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text=f"⚠️ {selected_date} sanasida '{kod}' KODi uchun allaqachon buyurtma mavjud.\n\n"
                         "O'zgartirasizmi yoki ustidan yozasizmi?",
                    reply_markup=reply_markup
                )
                
                # Store existing order data
                context.user_data["existing_order"] = existing_order
                
                return CONFIRMING_OVERWRITE
            else:
                # New order, proceed with data collection
                await query.edit_message_text(
                    text=f"Tanlangan KOD: {kod}\nSana: {selected_date}\n\nIltimos, manzilni kiriting:"
                )
                
                # Update navigation stack
                if "navigation_stack" in context.user_data:
                    context.user_data["navigation_stack"].append(ENTERING_ADDRESS)
                
                return ENTERING_ADDRESS

    async def enter_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Store address and ask for transport number."""
        if update.callback_query and update.callback_query.data == "back_to_kod":
            return await self.back_to_kod(update, context)
            
        address = update.message.text
        
        # Store address
        context.user_data["manzil"] = address
        
        # Create keyboard with back button
        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_address")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Manzil qabul qilindi.\n\nIltimos, transport raqamini kiriting:",
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data:
            context.user_data["navigation_stack"].append(ENTERING_TRANSPORT)
        
        return ENTERING_TRANSPORT

    async def back_to_kod(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Navigate back to KOD selection."""
        query = update.callback_query
        await query.answer()
        
        selected_date = context.user_data.get("selected_date", datetime.now().strftime("%Y-%m-%d"))
        
        # Determine if we need KODs with or without info based on user action
        user_action = context.user_data.get("action", "")
        only_empty = user_action == "Yangi Buyurtma"  # True for new orders, False for existing orders
        
        # Get KODs again
        kods = sheets_helper.get_available_kods(selected_date, only_empty=only_empty)
        
        if not kods:
            if only_empty:
                message = (f"{selected_date} sanasi uchun barcha KODlar allaqachon to'ldirilgan.")
            else:
                message = (f"{selected_date} sanasi uchun hech qanday to'ldirilgan KOD topilmadi.")
            
            await query.edit_message_text(
                f"{message}\n\nIltimos, boshqa sana tanlang yoki keyinroq urunib ko'ring."
            )
            return ConversationHandler.END
        
        # Create inline keyboard with KOD options
        keyboard = []
        for kod in kods:
            keyboard.append([InlineKeyboardButton(kod, callback_data=kod)])
        
        # Add back button
        keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_date")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if only_empty:
            message_text = (f"Tanlangan sana: {selected_date}\n\n"
                           "Quyidagi KODlardan transport va telefon ma'lumotlarini kiritishingiz kerak:\n\n"
                           "Iltimos, KODni tanlang:")
        else:
            message_text = (f"Tanlangan sana: {selected_date}\n\n"
                           "Quyidagi to'ldirilgan KODlarni tahrirlashingiz mumkin:\n\n"
                           "Iltimos, KODni tanlang:")
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data and ENTERING_ADDRESS in context.user_data["navigation_stack"]:
            context.user_data["navigation_stack"].remove(ENTERING_ADDRESS)
        
        return SELECTING_KOD

    async def enter_transport(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Store transport number and ask for driver phone."""
        if update.callback_query and update.callback_query.data == "back_to_address":
            return await self.back_to_address(update, context)
            
        # Get pre-filled transport if available (for Eski Buyurtma)
        pre_filled_transport = context.user_data.get("transport", "")
        
        if update.message.text:
            transport = update.message.text
            # Store transport number
            context.user_data["transport"] = transport
        
        # Create message with pre-filled value
        prompt = "Transport raqamini kiriting:"
        if pre_filled_transport:
            prompt = f"Mavjud transport: {pre_filled_transport}\nYangi transport raqamini kiriting (agar o'zgartirmoqchi bo'lsangiz):"
        
        # Create keyboard with back button
        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_transport")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            prompt,
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data:
            context.user_data["navigation_stack"].append(ENTERING_PHONE)
        
        return ENTERING_PHONE
        
    async def back_to_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Navigate back to address entry."""
        query = update.callback_query
        await query.answer()
        
        kod = context.user_data.get("kod", "")
        selected_date = context.user_data.get("selected_date", datetime.now().strftime("%Y-%m-%d"))
        
        # Create keyboard with back button
        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_kod")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=f"Tanlangan KOD: {kod}\nSana: {selected_date}\n\nIltimos, manzilni kiriting:",
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data and ENTERING_TRANSPORT in context.user_data["navigation_stack"]:
            context.user_data["navigation_stack"].remove(ENTERING_TRANSPORT)
        
        return ENTERING_ADDRESS

    async def enter_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Validate and store phone number, then ask for card number."""
        if update.callback_query and update.callback_query.data == "back_to_transport":
            return await self.back_to_transport(update, context)
            
        phone = update.message.text
        
        # Remove all non-digit characters for validation
        phone_digits = ''.join(filter(str.isdigit, phone))
        
        # Simple phone validation (only digits, check length)
        if not phone_digits.isdigit() or len(phone_digits) < 9:
            await update.message.reply_text(
                "Telefon raqami noto'g'ri formatda. Iltimos, faqat raqamlar kiriting (kamida 9 ta):\n\n"
                "Masalan: 99 008 44 06 yoki 990084406"
            )                      
            return ENTERING_PHONE
        
        # Store both formatted and digits-only versions
        context.user_data["telefon"] = phone  # Store the formatted version
        context.user_data["telefon_digits"] = phone_digits  # Store digits-only for validation
        
        # Create keyboard with back button
        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_phone")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Telefon raqami qabul qilindi.\n\nIltimos, karta raqamini kiriting:",
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data:
            context.user_data["navigation_stack"].append(ENTERING_CARD)
        
        return ENTERING_CARD

    async def back_to_transport(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Navigate back to transport entry."""
        query = update.callback_query
        await query.answer()
        
        # Create keyboard with back button
        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_address")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Transport raqamini kiriting:",
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data and ENTERING_PHONE in context.user_data["navigation_stack"]:
            context.user_data["navigation_stack"].remove(ENTERING_PHONE)
        
        return ENTERING_TRANSPORT

    async def enter_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Store card number (any format), then ask for payment amount."""
        if update.callback_query and update.callback_query.data == "back_to_phone":
            return await self.back_to_phone(update, context)
            
        card = update.message.text
        
        # Store the card number as-is (accept any format)
        context.user_data["karta"] = card
        
        # Create keyboard with back button
        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_card")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send the amount prompt message and store its ID
        amount_message = await update.message.reply_text(
            "Karta raqami qabul qilindi.\n\nIltimos, to'lov summasini kiriting:",
            reply_markup=reply_markup
        )
        
        # Store the message ID so we can edit it later when navigating back
        context.user_data["amount_message_id"] = amount_message.message_id
        
        # Update navigation stack
        if "navigation_stack" in context.user_data:
            context.user_data["navigation_stack"].append(ENTERING_AMOUNT)
        
        return ENTERING_AMOUNT

    async def back_to_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Navigate back to phone entry."""
        query = update.callback_query
        await query.answer()
        
        # Create keyboard with back button
        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_transport")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Haydovchi telefon raqamini kiriting:",
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data and ENTERING_CARD in context.user_data["navigation_stack"]:
            context.user_data["navigation_stack"].remove(ENTERING_CARD)
        
        return ENTERING_PHONE

    async def enter_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Validate and store payment amount, then show summary."""
        if update.callback_query and update.callback_query.data == "back_to_card":
            return await self.back_to_card(update, context)
            
        amount = update.message.text
        
        # Remove thousand separators but keep decimal point
        cleaned_amount = amount.replace(" ", "").replace(",", "").replace(".", "")
        
        # For decimal values, we need a different approach
        # Let's check if it's a valid number by trying to convert to float
        try:
            # First, remove thousand separators but keep the last dot as decimal
            temp_amount = amount.replace(" ", "").replace(",", "")
            
            # Count dots to handle thousand separators vs decimal point
            dot_count = temp_amount.count('.')
            if dot_count > 1:
                # Multiple dots - treat as thousand separators except the last one
                parts = temp_amount.split('.')
                decimal_part = parts[-1] if len(parts[-1]) <= 2 else ''  # Assume max 2 decimal places
                integer_part = ''.join(parts[:-1]) if decimal_part else ''.join(parts)
                if decimal_part:
                    temp_amount = f"{integer_part}.{decimal_part}"
                else:
                    temp_amount = integer_part
            
            amount_num = float(temp_amount)
            
        except ValueError:
            await update.message.reply_text(
                "To'lov summasi noto'g'ri formatda. Iltimos, faqat raqamlar kiriting:\n\n"
                "Masalan:\n"
                "• 1 500 000\n"
                "• 1,500,000\n"
                "• 1500000\n"
                "• 1.500.000\n"
                "• 1500000.50 (o'nlik kasrlar uchun)"
            )
            return ENTERING_AMOUNT
        
        # Format amount with thousand separators for display
        if amount_num.is_integer():
            formatted_amount = "{:,.0f}".format(amount_num).replace(",", " ")
        else:
            formatted_amount = "{:,.2f}".format(amount_num).replace(",", " ")
        
        # Store both original and formatted versions
        context.user_data["summa"] = formatted_amount
        context.user_data["summa_raw"] = amount_num  # Store raw number for calculations
        
        # Show summary for confirmation
        return await self.show_summary(update, context)

    async def back_to_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Navigate back to card entry."""
        query = update.callback_query
        await query.answer()
        
        # Get the stored message ID
        amount_message_id = context.user_data.get("amount_message_id")
        
        # Create keyboard with back button for card entry
        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_phone")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if amount_message_id:
            # Edit the existing amount prompt message to become card entry prompt
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=amount_message_id,
                text="Karta raqamini kiriting:",
                reply_markup=reply_markup
            )
        else:
            # Fallback: send a new message
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Karta raqamini kiriting:",
                reply_markup=reply_markup
            )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data and ENTERING_AMOUNT in context.user_data["navigation_stack"]:
            context.user_data["navigation_stack"].remove(ENTERING_AMOUNT)
        
        return ENTERING_CARD

    async def show_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Show order summary for confirmation before submission."""
        # Handle callback query if coming from amount entry
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            await query.answer()
        # Otherwise, it's coming from enter_amount method
        
        # Get all data
        selected_date = context.user_data.get("selected_date", "")
        kod = context.user_data.get("kod", "")
        manzil = context.user_data.get("manzil", "")
        transport = context.user_data.get("transport", "")
        telefon = context.user_data.get("telefon", "")
        karta = context.user_data.get("karta", "")
        summa = context.user_data.get("summa", "")
        
        # Create summary message
        summary_text = (
            "📋 Buyurtma ma'lumotlari:\n\n"
            f"📅 Sana: {selected_date}\n"
            f"🔢 KOD: {kod}\n"
            f"📍 Manzil: {manzil}\n"
            f"🚚 Transport: {transport}\n"
            f"📞 Telefon: {telefon}\n"
            f"💳 Karta: {karta}\n"
            f"💰 Summa: {summa} so'm\n\n"
            "Ma'lumotlar to'g'rimi?"
        )
        
        # Create inline keyboard for confirmation and editing
        keyboard = [
            [InlineKeyboardButton("✅ Ha, jo'natish", callback_data="confirm_submit")],
            [InlineKeyboardButton("✏️ Manzil", callback_data="edit_field:Manzil")],
            [InlineKeyboardButton("✏️ Transport", callback_data="edit_field:Transport_raqami")],
            [InlineKeyboardButton("✏️ Telefon", callback_data="edit_field:Haydovchi_telefon")],
            [InlineKeyboardButton("✏️ Karta", callback_data="edit_field:Karta_raqami")],
            [InlineKeyboardButton("✏️ Summa", callback_data="edit_field:To'lov_summasi")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_amount")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                text=summary_text,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text=summary_text,
                reply_markup=reply_markup
            )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data:
            context.user_data["navigation_stack"].append(REVIEW_SUMMARY)
        
        return REVIEW_SUMMARY

    async def back_to_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Navigate back to amount entry."""
        query = update.callback_query
        await query.answer()
        
        # Create keyboard with back button
        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_card")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "To'lov summasini kiriting:",
            reply_markup=reply_markup
        )
        
        # Update navigation stack
        if "navigation_stack" in context.user_data and REVIEW_SUMMARY in context.user_data["navigation_stack"]:
            context.user_data["navigation_stack"].remove(REVIEW_SUMMARY)
        
        return ENTERING_AMOUNT

    async def process_summary_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process actions from the summary screen."""
        query = update.callback_query
        await query.answer()
        
        action = query.data
        
        if action == "confirm_submit":
            # Proceed with saving the order
            return await self.save_order(update, context)
        elif action.startswith("edit_field:"):
            # Extract field name from callback data
            field = action.split(":")[1]
            
            # Store which field is being edited
            context.user_data["editing_field"] = field
            
            # Ask for new value with appropriate message
            field_prompts = {
                "Manzil": "Yangi manzilni kiriting:",
                "Transport_raqami": "Yangi transport raqamini kiriting:",
                "Haydovchi_telefon": "Yangi haydovchi telefon raqamini kiriting:",
                "Karta_raqami": "Yangi karta raqamini kiriting:",
                "To'lov_summasi": "Yangi to'lov summasini kiriting:"
            }
            
            prompt = field_prompts.get(field, "Yangi qiymatni kiriting:")
            
            # For text fields, ask for input
            keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_summary")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=prompt,
                reply_markup=reply_markup
            )
            
            return EDITING_FIELD
        
        return REVIEW_SUMMARY

    async def back_to_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Navigate back to summary from editing."""
        query = update.callback_query
        await query.answer()
        
        return await self.show_summary(update, context)

    async def save_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Save the complete order to Google Sheets."""
        query = update.callback_query
        await query.answer()
        
        # Get selected date
        selected_date = context.user_data.get("selected_date", datetime.now().strftime("%Y-%m-%d"))
        
        # Prepare order data
        order_data = {
            "Sana": selected_date,
            "KOD": context.user_data.get("kod"),
            "Manzil": context.user_data.get("manzil"),
            "Transport_raqami": context.user_data.get("transport"),
            "Haydovchi_telefon": context.user_data.get("telefon"),
            "Karta_raqami": context.user_data.get("karta"),
            "To'lov_summasi": context.user_data.get("summa")
        }
        
        # Save to Sheet1
        success_sheet1 = sheets_helper.add_order_to_sheet1(order_data)
        
        # Update transport info in Sheet2
        success_sheet2 = False
        sheet2_message = ""
        
        if success_sheet1:
            success_sheet2, sheet2_message = sheets_helper.update_sheet2_transport_info(
                order_data["KOD"], 
                order_data["Transport_raqami"], 
                order_data["Haydovchi_telefon"],
                selected_date
            )
        
        if success_sheet1:
            # Create a formatted message
            tolov_summasi = order_data["To'lov_summasi"]
            
            message_text = (
                "✅ Buyurtma muvaffaqiyatli saqlandi!\n\n"
                f"Sana: {selected_date}\n"
                f"KOD: {order_data['KOD']}\n"
                f"Manzil: {order_data['Manzil']}\n"
                f"Transport raqami: {order_data['Transport_raqami']}\n"
                f"Haydovchi telefon: {order_data['Haydovchi_telefon']}\n"
                f"Karta raqami: {order_data['Karta_raqami']}\n"
                f"To'lov summasi: {tolov_summasi} so'm"
            )
            
            # Add Sheet2 status message
            if sheet2_message:
                message_text += f"\n\n{sheet2_message}"
            else:
                message_text += "\n\n✅ Google Sheet 2 ham muvaffaqiyatli yangilandi"
                
            message_text += "\n\nYangi buyurtma uchun /start ni bosing."
            
            await query.edit_message_text(text=message_text)
        else:
            await query.edit_message_text(
                text="❌ Xatolik yuz berdi. Buyurtma saqlanmadi. Iltimos, qayta urunib ko'ring."
            )
        
        # Clear user data
        if context.user_data:
            context.user_data.clear()
        
        return ConversationHandler.END

    async def confirm_overwrite(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle user choice to edit or overwrite existing order."""
        query = update.callback_query
        await query.answer()
        
        choice = query.data
        
        if choice == "overwrite":
            # Proceed with overwriting (collect all data again)
            await query.edit_message_text(
                text="Mavjud yozuv ustiga yozish tanlandi.\n\nIltimos, yangi manzilni kiriting:"
            )
            
            # Update navigation stack
            if "navigation_stack" in context.user_data:
                context.user_data["navigation_stack"].append(ENTERING_ADDRESS)
            
            return ENTERING_ADDRESS
            
        else:  # edit
            # Show field selection for editing
            keyboard = [
                [InlineKeyboardButton("Manzil", callback_data="Manzil")],
                [InlineKeyboardButton("Transport raqami", callback_data="Transport_raqami")],
                [InlineKeyboardButton("Haydovchi telefon", callback_data="Haydovchi_telefon")],
                [InlineKeyboardButton("Karta raqami", callback_data="Karta_raqami")],
                [InlineKeyboardButton("To'lov summasi", callback_data="To'lov_summasi")],
                [InlineKeyboardButton("Barchasini saqlash", callback_data="save_all")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text="Qaysi maydonni o'zgartirmoqchisiz?",
                reply_markup=reply_markup
            )
            
            # Update navigation stack
            if "navigation_stack" in context.user_data:
                context.user_data["navigation_stack"].append(EDITING_FIELD)
            
            return EDITING_FIELD

    async def edit_field(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle field selection for editing."""
        query = update.callback_query
        await query.answer()
        
        # Handle back to summary
        if query.data == "back_to_summary":
            return await self.back_to_summary(update, context)
        
        # Handle regular field selection
        field = query.data
        
        if field == "save_all":
            # Save all changes
            order_data = context.user_data.get("existing_order", {}).copy()
            
            # Update with any changed values
            for key in ["manzil", "transport", "telefon", "karta", "summa"]:
                if key in context.user_data:
                    mapped_key = {
                        "manzil": "Manzil",
                        "transport": "Transport_raqami",
                        "telefon": "Haydovchi_telefon",
                        "karta": "Karta_raqami",
                        "summa": "To'lov_summasi"
                    }[key]
                    order_data[mapped_key] = context.user_data[key]
            
            # Get selected date
            selected_date = context.user_data.get("selected_date", datetime.now().strftime("%Y-%m-%d"))
            
            # Update the order in Sheet1
            success = sheets_helper.update_order_in_sheet1(
                context.user_data.get("kod"), 
                order_data
            )
            
            # Update transport info in Sheet2 if relevant fields changed
            if success and ("transport" in context.user_data or "telefon" in context.user_data):
                transport = order_data.get("Transport_raqami", "")
                phone = order_data.get("Haydovchi_telefon", "")
                sheets_helper.update_sheet2_transport_info(
                    context.user_data.get("kod"), 
                    transport, 
                    phone,
                    selected_date
                )
            
            if success:
                # Create a formatted message
                tolov_summasi = order_data.get("To'lov_summasi", "")
                
                message_text = (
                    "✅ Buyurtma muvaffaqiyatli yangilandi!\n\n"
                    f"Sana: {selected_date}\n"
                    f"KOD: {order_data.get('KOD', '')}\n"
                    f"Manzil: {order_data.get('Manzil', '')}\n"
                    f"Transport raqami: {order_data.get('Transport_raqami', '')}\n"
                    f"Haydovchi telefon: {order_data.get('Haydovchi_telefon', '')}\n"
                    f"Karta raqami: {order_data.get('Karta_raqami', '')}\n"
                    f"To'lov summasi: {tolov_summasi}\n\n"
                    f"Yangi buyurtma uchun /start ni bosing."
                )
                
                await query.edit_message_text(text=message_text)
            else:
                await query.edit_message_text(
                    text="❌ Xatolik yuz berdi. Buyurtma yangilanmadi. Iltimos, qayta urunib ko'ring."
                )
            
            # Clear user data
            if context.user_data:
                context.user_data.clear()
            
            return ConversationHandler.END
            
        else:
            # Store which field is being edited
            context.user_data["editing_field"] = field
            
            # Ask for new value
            field_name_uz = {
                "Manzil": "manzil",
                "Transport_raqami": "transport raqami",
                "Haydovchi_telefon": "haydovchi telefon raqami",
                "Karta_raqami": "karta raqami",
                "To'lov_summasi": "to'lov summasi"
            }.get(field, field)
            
            keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_summary")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=f"Yangi {field_name_uz}ni kiriting:",
                reply_markup=reply_markup
            )
            
            return EDITING_FIELD

    async def update_field(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Update the field being edited."""
        new_value = update.message.text
        
        field = context.user_data.get("editing_field")
        
        # Validate input based on field type
        if field in ["Haydovchi_telefon", "Karta_raqami"] and not new_value.isdigit():
            await update.message.reply_text(
                f"{field} faqat raqamlardan iborat bo'lishi kerak. Iltimos, qayta kiriting:"
            )
            return EDITING_FIELD
            
        if field == "To'lov_summasi":
            # Clean and format amount
            amount_clean = new_value.replace(",", "").replace(".", "")
            if not amount_clean.isdigit():
                await update.message.reply_text(
                    "To'lov summasi noto'g'ri formatda. Iltimos, faqat raqamlar kiriting:"
                )
                return EDITING_FIELD
            
            try:
                amount_num = float(amount_clean)
                new_value = "{:,.0f}".format(amount_num).replace(",", " ")
            except:
                pass  # Keep original value if formatting fails
        
        # Map field name to storage key
        storage_key = {
            "Manzil": "manzil",
            "Transport_raqami": "transport",
            "Haydovchi_telefon": "telefon",
            "Karta_raqami": "karta",
            "To'lov_summasi": "summa"
        }.get(field, field.lower())
        
        # Store the updated value
        context.user_data[storage_key] = new_value
        
        # Return to summary
        return await self.show_summary(update, context)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel and end the conversation."""
        user = update.message.from_user
        logger.info("User %s canceled the conversation.", user.first_name)
        
        # Clear user data
        if context.user_data:
            context.user_data.clear()
        
        await update.message.reply_text(
            "❌ Buyurtma bekor qilindi. Yangi buyurtma uchun /start ni bosing.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ConversationHandler.END

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        await update.message.reply_text(
            "Yordam:\n"
            "/start - Botni ishga tushirish yoki har qanday vaqt yangidan boshlash\n"
            "/change - Yangi/Eski buyurtma tanlovini o'zgartirish\n"
            "/cancel - Joriy amalni bekor qilish\n"
            "/help - Yordam ko'rsatish\n\n"
            "Har qanday bosqichda /start ni bosish orqali yangidan boshlashingiz mumkin.\n"
            "/change buyrug'i orqali Yangi/Eski buyurtma tanlovini o'zgartirishingiz mumkin."
        )

    def run(self):
        """Run the bot."""
        self.application.run_polling()

def main():
    """Start the bot."""
    # Get bot token from environment variable
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable not set")
    
    # Create and run bot
    bot = TelegramBot(bot_token)
    bot.run()

if __name__ == "__main__":
    main()
