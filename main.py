from start import register_user
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from setting import BOT_TOKEN
import dialogue
from tasks import log_and_report_error
from utilities import handle_error
from manage import add_bill_id_handler

@handle_error.handle_functions_error
async def some(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_chat
    text = ''
    keyboard = [
        [InlineKeyboardButton("", callback_data='vpn_recive_test_service')],
    ]
    return await update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='html')

async def unknown_message(update, context):
    try:
        user = update.effective_chat
        text = dialogue.text.get('unknown_input', dialogue.text.get("error_msg", "ERROR"))
        await context.bot.send_message(chat_id=user.id, text=text, parse_mode='html')
    except Exception as e:
        log_and_report_error("main: unknown_message", e)


if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler('start', register_user))
    application.add_handler(CommandHandler('new_bill_id', register_user))

    # Bot Main Menu
    # application.add_handler(CallbackQueryHandler(start_reFactore.start, pattern='start(.*)'))

    # application.job_queue.run_repeating(vpn_notification.notification_timer, interval=10 * 60, first=0)
    application.add_handler(add_bill_id_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))
    application.run_polling()
