from celery import Celery
import redis, traceback, requests
from uuid import uuid4
from logger_config import logger
from setting import BOT_TOKEN, TELEGRAM_CHAT_ID, ERR_THREAD_ID
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from core import GetAPI, translate_json_to_persian
from dialogue import text, keyboard

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

celery_app = Celery(
    "tasks",
    broker="pyamqp://guest@localhost//"
)

def log_and_report_error(context: str, error: Exception, extra: dict = None):
    tb = traceback.format_exc()
    error_id = uuid4().hex
    extra["error_id"] = error_id
    logger.error(
        context, extra={"error": str(error), "traceback": tb, **extra}
    )
    report_error.delay(context, error.__class__.__name__, str(error), extra)

def report_to_admin_api(msg, message_thread_id=ERR_THREAD_ID):
    requests.post(
        url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={'chat_id': TELEGRAM_CHAT_ID, 'text': msg[:4096], 'message_thread_id': message_thread_id},
        timeout=10
    )

@celery_app.task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def report_error(context, err_type, err_str, extra: dict = None):
    """
    Object of type ZeroDivisionError is not JSON serializable--cant send error object directly
    """
    err = (
        f"🔴 {context}:"
        f"\n\nError type: {err_type}"
        f"\nError reason: {err_str}"
        f"\n\nExtera Info:"
        f"\n{extra}"
    )
    report_to_admin_api(err)


@celery_app.task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def send_bill_message(chat_id: int, user_bill_id: int, message_id: int):
    data = GetAPI().get_power_bill_data(user_bill_id)

    msg = text.get("bill_ensurance_text", "ERROR")
    msg += "\n\n" + translate_json_to_persian(data['data'])

    key = [
        [
            InlineKeyboardButton(keyboard.get('yes_im_sure', "ERROR"), callback_data='confirm_change'),
            InlineKeyboardButton(keyboard.get('no_cancle_it', "ERROR"), callback_data='cancle_change')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(key)

    reply_markup_dict = reply_markup.to_dict()

    requests.post(
        f"{BASE_URL}/deleteMessage",
        json={
            "chat_id": chat_id,
            "message_id": message_id
        }
    )

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": msg,
            "reply_markup": reply_markup_dict
        }
    )
