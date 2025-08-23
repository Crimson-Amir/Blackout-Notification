from telegram import InlineKeyboardMarkup, InlineKeyboardButton

import tasks
from utilities import handle_error
from telegram.ext import ConversationHandler, CommandHandler, filters, MessageHandler, CallbackQueryHandler
from core import GetAPI, translate_json_to_persian
from dialogue import text, keyboard

GET_BILL_ID, GET_ASSURNACE = range(2)

async def cancel(update, context):
    query = update.callback_query
    await query.delete_message()
    user_detail = update.effective_chat
    await context.bot.send_message(chat_id=user_detail.id, text=text.get('action_canceled', 'ERROR'))
    return ConversationHandler.END

@handle_error.handle_conversetion_error
async def ask_for_bill_id(update, context):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.delete_message()
    user_detail = update.effective_chat
    key = [[InlineKeyboardButton(keyboard.get('cancel_button', "ERROR"), callback_data='cancel_add_new_bill')]]
    msg = text.get('ask_for_bill_id', 'ERROR')
    await context.bot.send_message(text=msg, chat_id=user_detail.id, parse_mode='html', reply_markup=InlineKeyboardMarkup(key))
    return GET_BILL_ID


@handle_error.handle_conversetion_error
async def get_bill_id(update, context):
    user_detail = update.effective_chat
    user_bill_id = update.message.text

    try:
        user_bill_id = int(user_bill_id)
    except ValueError:
        # not a number
        key = [[InlineKeyboardButton(keyboard.get('cancel_button', "ERROR"), callback_data='cancel_add_new_bill')]]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text.get('input_should_be_number'),
            reply_markup=InlineKeyboardMarkup(key)
        )
        return GET_BILL_ID

    msg = await context.bot.send_message(chat_id=user_detail.id, text='has done')
    tasks.send_bill_message(user_detail.id, int(user_bill_id), msg.message_id)
    return ConversationHandler.END


@handle_error.handle_conversetion_error
async def set_bill_data(update, context):
    user_detail = update.effective_chat
    query = update.callback_query
    new_user_id = context.user_data['user_bill_id']
    await query.delete_message()

    if query.data == 'cancel_change':
        await context.bot.send_message(chat_id=user_detail.id, text=text.get('action_cancled', 'ERROR'))
        return ConversationHandler.END

    key = [[InlineKeyboardButton(keyboard.get('home_button', "ERROR"), callback_data='start_in_new_message')]]

    await context.bot.send_message(chat_id=user_detail.id, text='ok', reply_markup=InlineKeyboardMarkup(key))
    return ConversationHandler.END


add_bill_id_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(ask_for_bill_id, pattern=r'ask_for_bill_id'),
        CommandHandler("ask_for_bill_id", ask_for_bill_id),  # same function for command
    ],
    states={
        GET_BILL_ID: [MessageHandler(filters.TEXT, get_bill_id)],
        GET_ASSURNACE: [
            CallbackQueryHandler(set_bill_data, pattern='^(confirm_change|cancel_change)$')
        ],
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern='cancel_add_new_bill')],
    conversation_timeout=600,
)
