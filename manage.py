from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import tasks
from database import SessionLocal
from utilities import handle_error
from telegram.ext import ConversationHandler, CommandHandler, filters, MessageHandler, CallbackQueryHandler, ContextTypes
from dialogue import text, keyboard
from crud import set_new_blackout_report_token
from core import GetAPI

GET_BILL_ID, GET_BILL_NAME = range(2)

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
            text=text.get('input_should_be_number', 'input_should_be_number'),
            reply_markup=InlineKeyboardMarkup(key)
        )
        return GET_BILL_ID

    key = [[InlineKeyboardButton(keyboard.get('cancel_button', "cancel_button"), callback_data='cancel_add_new_bill')]]
    await context.bot.send_message(chat_id=user_detail.id, text=text.get("enter_bill_name", "enter_bill_name"), reply_markup=InlineKeyboardMarkup(key))
    context.user_data["bill_id"] = user_bill_id
    return GET_BILL_NAME

@handle_error.handle_conversetion_error
async def get_bill_name(update, context):
    user_detail = update.effective_chat
    bill_name = update.message.text

    if len(bill_name) > 15:
        key = [[InlineKeyboardButton(keyboard.get('cancel_button', "cancel_button"), callback_data='cancel_add_new_bill')]]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text.get('name_should_be_less_than_15', 'name_should_be_less_than_15'),
            reply_markup=InlineKeyboardMarkup(key)
        )
        return GET_BILL_NAME

    context.user_data["bill_name"] = bill_name
    bill_id = context.user_data['bill_id']
    msg = await context.bot.send_message(chat_id=user_detail.id, text=text.get("processing", "processing"))
    tasks.send_bill_message.delay(user_detail.id, int(bill_id), msg.message_id)
    return ConversationHandler.END

add_bill_id_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(ask_for_bill_id, pattern=r'ask_for_bill_id'),
        CommandHandler("new_bill_id", ask_for_bill_id),  # same function for command
    ],
    states={
        GET_BILL_ID: [MessageHandler(filters.TEXT, get_bill_id)],
        GET_BILL_NAME: [MessageHandler(filters.TEXT, get_bill_name)]
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

    bill_name = context.user_data["bill_name"]
    wait_msg = await query.edit_message_text(text=text.get("processing", "processing"), parse_mode='html')
    tasks.add_bill_id.delay(user_detail.id, int(bill_id), bill_name, wait_msg.message_id)


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

async def check_notification(context: ContextTypes.DEFAULT_TYPE):
    tasks.check_all_bills.delay()

async def set_blackout_report_token(update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_chat
    if user.id != 6450325872:
        return await context.bot.send_message(user.id, "you are not admin")
    with SessionLocal() as session:
        set_new_blackout_report_token(session, str(update.message.text.replace("/set_token ", "")))
        GetAPI().get_new_header()
        await context.bot.send_message(user.id, "set succesfully")