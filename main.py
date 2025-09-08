from start import register_user
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from setting import BOT_TOKEN
import dialogue
from tasks import log_and_report_error
from utilities import ustart
from manage import (add_bill_id_handler, add_bill_id_address, my_bill_ids, find_my_bill,
                    remove_bill_assure, remove_bill, check_notification, set_blackout_report_token)


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
    application.add_handler(CommandHandler('set_token', set_blackout_report_token))

    # Bot Main Menu
    application.add_handler(CallbackQueryHandler(ustart, pattern='start_edit_message'))
    # application.add_handler(CallbackQueryHandler(start_reFactore.start, pattern='start(.*)'))

    # Manage
    application.add_handler(CallbackQueryHandler(add_bill_id_address, pattern='add_b4d_a5s__(.*)'))
    application.add_handler(CallbackQueryHandler(my_bill_ids, pattern='my_bill_ids'))
    application.add_handler(CallbackQueryHandler(find_my_bill, pattern='find_my_bill__(.*)'))
    application.add_handler(CallbackQueryHandler(remove_bill_assure, pattern='remove_bill_assure__(.*)'))
    application.add_handler(CallbackQueryHandler(remove_bill, pattern='r4e_t2s_b2l__(.*)'))
    application.add_handler(add_bill_id_handler)
    application.job_queue.run_repeating(check_notification, interval=60 * 60, first=0)


    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))
    application.run_polling()
