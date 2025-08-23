from database import SessionLocal
import crud
from telegram.ext import ConversationHandler
import functools
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from dialogue import text, keyboard
from tasks import log_and_report_error

class HandleErrors:
    def handle_functions_error(self, func):
        @functools.wraps(func)
        async def wrapper(update, context, **kwargs):
            user_detail = update.effective_chat
            try:
                return await func(update, context, **kwargs)
            except Exception as e:
                if 'Message is not modified' in str(e): return await update.callback_query.answer()
                log_and_report_error(
                    f'An error occurred in {func.__name__}:',
                    e, extra={
                        "first_name": user_detail.first_name,
                        "last_name": user_detail.last_name,
                        "username": user_detail.username,
                        "user_id": user_detail.id
                    })
                await self.handle_error_message_for_user(update, context)

        return wrapper

    def handle_conversetion_error(self, func):
        @functools.wraps(func)
        async def wrapper(update, context, **kwargs):
            user_detail = update.effective_chat
            try:
                return await func(update, context, **kwargs)
            except Exception as e:
                log_and_report_error(
                    f'An error occurred in {func.__name__}:',
                    e, extra={
                        "first_name": user_detail.first_name,
                        "last_name": user_detail.last_name,
                        "username": user_detail.username,
                        "user_id": user_detail.id
                    })
                await self.handle_error_message_for_user(update, context)
                return ConversationHandler.END
        return wrapper

    @staticmethod
    async def handle_error_message_for_user(update, context, message_text=None):
        user_id = update.effective_chat.id
        message_text = message_text if message_text else text.get('error_msg')
        if update.callback_query:
            return await update.callback_query.answer(message_text)
        await context.bot.send_message(text=message_text, chat_id=user_id)

async def ustart(update, context, in_new_message=False, raise_error=False):
    query = update.callback_query
    user_detail = update.effective_chat
    is_user_exist_in_bot(user_detail.id)
    msg = text.get('start_message', 'start_message')
    try:
        main_keyboard = [
            [InlineKeyboardButton(keyboard.get("new_notification", "new_notification"), callback_data='ask_for_bill_id'),
             InlineKeyboardButton(keyboard.get("my_bills", "my_bills"), callback_data='my_bill_ids')],
        ]

        if update.callback_query and "start_in_new_message" not in update.callback_query.data and not in_new_message:
            return await query.edit_message_text(text=msg, reply_markup=InlineKeyboardMarkup(main_keyboard), parse_mode='html')
        if query:
            if 'start_in_new_message_delete_previos' in query.data:
                await query.delete_message()
            await query.answer()
        return await context.bot.send_message(chat_id=user_detail.id, text=msg, reply_markup=InlineKeyboardMarkup(main_keyboard), parse_mode='html')

    except Exception as e:
        if raise_error: raise e
        log_and_report_error(
            "start: register_new_bot", e,
            {"first_name": user_detail.first_name,
             "last_name": user_detail.last_name, "username": user_detail.username, "user_id": user_detail.id})
        await context.bot.send_message(chat_id=user_detail.id, text=text.get("error_msg", "ERROR"), parse_mode='html')

class UserNotFound(Exception):
    def __init__(self): super().__init__("user was't register in bot!")

users = set()

def is_user_exist_in_bot(chat_id):
    if chat_id in users:
        return
    with SessionLocal() as session:
        if crud.get_user(session, chat_id):
            users.add(chat_id)
            return
    raise UserNotFound

handle_error = HandleErrors()
