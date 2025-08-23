from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import tasks
from utilities import handle_error
from telegram.ext import ConversationHandler, CommandHandler, filters, MessageHandler, CallbackQueryHandler
from dialogue import text, keyboard

GET_BILL_ID, GET_ASSURNACE = range(2)

async def cancel(update, context):
    query = update.callback_query
    await query.delete_message()
    user_detail = update.effective_chat
    await context.bot.send_message(chat_id=user_detail.id, text=text.get('action_canceled', 'action_canceled'))
    return ConversationHandler.END

@handle_error.handle_conversetion_error
async def ask_for_bill_id(update, context):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.delete_message()
    user_detail = update.effective_chat
    key = [[InlineKeyboardButton(keyboard.get('cancel_button', "cancel_button"), callback_data='cancel_add_new_bill')]]
    msg = text.get('please_send_your_bill_id', 'please_send_your_bill_id')
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
        key = [[InlineKeyboardButton(keyboard.get('cancel_button', "cancel_button"), callback_data='cancel_add_new_bill')]]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text.get('input_should_be_number'),
            reply_markup=InlineKeyboardMarkup(key)
        )
        return GET_BILL_ID

    msg = await context.bot.send_message(chat_id=user_detail.id, text=text.get("processing", "processing"))
    tasks.send_bill_message.delay(user_detail.id, int(user_bill_id), msg.message_id)
    return ConversationHandler.END


add_bill_id_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(ask_for_bill_id, pattern=r'ask_for_bill_id'),
        CommandHandler("new_bill_id", ask_for_bill_id),  # same function for command
    ],
    states={
        GET_BILL_ID: [MessageHandler(filters.TEXT, get_bill_id)]
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern='cancel_add_new_bill')],
    conversation_timeout=600,
)

@handle_error.handle_functions_error
async def add_bill_id_address(update, context):
    query = update.callback_query
    user_detail = update.effective_chat
    add_status, bill_id = str(query.data.replace('add_b4d_a5s__', '')).split("__")

    if add_status == "cancle":
        key = [[InlineKeyboardButton(keyboard.get('home_button', "home_button"), callback_data='start_edit_message')]]
        msg = text.get("action_canceled", "action_canceled")
        return await query.edit_message_text(text=msg, parse_mode='html', reply_markup=InlineKeyboardMarkup(key))

    wait_msg = await query.edit_message_text(text=text.get("processing", "processing"), parse_mode='html')
    tasks.add_bill_id.delay(user_detail.id, int(bill_id), wait_msg.message_id)


@handle_error.handle_functions_error
async def my_bill_ids(update, context):
    query = update.callback_query
    user_detail = update.effective_chat
    await query.answer(text.get("wait", "wait"))
    tasks.get_all_user_bill_ids.delay(int(user_detail.id), query.message.message_id)

@handle_error.handle_functions_error
async def find_my_bill(update, context):
    query = update.callback_query
    user_detail = update.effective_chat
    bill_id = str(query.data.replace('find_my_bill__', ''))
    await query.answer(text.get("wait", "wait"))
    tasks.find_my_bill.delay(int(user_detail.id), bill_id, query.message.message_id)


@handle_error.handle_functions_error
async def remove_bill_assure(update, context):
    query = update.callback_query
    bill_id = str(query.data.replace('remove_bill_assure__', ''))
    key = [[InlineKeyboardButton(keyboard.get('yes_im_sure', "yes_im_sure"), callback_data=f'r4e_t2s_b2l__{bill_id}'),
            InlineKeyboardButton(keyboard.get('no_cancle_it', "no_cancle_it"), callback_data='my_bill_ids')]]
    msg = text.get('are_you_sure_about_remove_this_address', 'are_you_sure_about_remove_this_address')
    return await query.edit_message_text(text=msg, reply_markup=InlineKeyboardMarkup(key), parse_mode='html')

@handle_error.handle_functions_error
async def remove_bill(update, context):
    query = update.callback_query
    user_detail = update.effective_chat
    bill_id = str(query.data.replace('r4e_t2s_b2l__', ''))
    await query.answer(text.get("wait", "wait"))
    tasks.remove_bill_id.delay(int(user_detail.id), bill_id, query.message.message_id)
