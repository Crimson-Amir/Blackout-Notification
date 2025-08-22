import crud
from tasks import log_and_report_error
from utilities import UserNotFound, handle_error, ustart
from telegram import Update
from telegram.ext import ContextTypes
from setting import TELEGRAM_CHAT_ID, NEW_USER_THREAD_ID
from database import SessionLocal
from dialogue import text

@handle_error.handle_functions_error
async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE, in_new_message=False):
    user_detail = update.effective_chat

    try:
        await ustart(update, context, in_new_message, True)

    except UserNotFound:
        with SessionLocal() as session:
            with session.begin():
                crud.create_user(session, user_detail)
                photos = await context.bot.get_user_profile_photos(user_id=user_detail.id)

                start_text_notif = (f'👤 New Start IN Bot\n\n'
                                    f'User Name: {user_detail.first_name} {user_detail.last_name}\n'
                                    f'User ID: <a href=\"tg://user?id={user_detail.id}\">{user_detail.id}</a>\n'
                                    f'UserName: @{user_detail.username}\n')

                if photos.total_count > 0:
                    photo_file_id = photos.photos[0][-1].file_id
                    await context.bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=photo_file_id,
                                                 caption=start_text_notif, parse_mode='HTML',
                                                 message_thread_id=NEW_USER_THREAD_ID)
                else:
                    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                                                   text=start_text_notif + '\n\n• Without profile picture (or not public)',
                                                   parse_mode='HTML', message_thread_id=NEW_USER_THREAD_ID)
                await ustart(update, context)

    except Exception as e:
        log_and_report_error(
            "start: register_new_bot", e,
            {"first_name": user_detail.first_name,
             "last_name": user_detail.last_name, "username": user_detail.username, "user_id": user_detail.id})
        await context.bot.send_message(chat_id=user_detail.id, text=text.get("error_msg", "ERROR"), parse_mode='html')



async def just_for_show(update, context):
    query = update.callback_query
    await query.answer(text=text.get('just_for_show', 'ERROR'))


async def already_on_this(update, context):
    query = update.callback_query
    await query.answer(text=text.get('already_on_this', 'ERROR'))

