from celery import Celery
import redis, traceback, requests
from uuid import uuid4
from logger_config import logger
from setting import BOT_TOKEN, TELEGRAM_CHAT_ID, ERR_THREAD_ID, NOTIFICATION_THREAD_ID, WARNING_THREAD_ID, INFO_THREAD_ID
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from core import GetAPI, translate_json_to_persian, get_jalali_date_range
from database import SessionLocal
from dialogue import text, keyboard
from sqlalchemy.exc import IntegrityError
import functools
from crud import (insert_new_service_no_commit, add_user_service, get_user_services, remove_bill,
                  get_all_available_services, get_all_service_users, update_valid_until)
import jdatetime
from datetime import datetime, timezone

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

celery_app = Celery(
    "tasks",
    broker="pyamqp://guest@localhost//"
)

def jalali_to_gregorian(jalali_date: str, time_str: str) -> datetime:
    """
    Convert Jalali date (YYYY/MM/DD) + time (HH:MM) → Python datetime (UTC)
    """
    year, month, day = map(int, jalali_date.split("/"))
    hour, minute = map(int, time_str.split(":"))

    jdt = jdatetime.datetime(year, month, day, hour, minute)
    # convert to Gregorian datetime
    gdt = jdt.togregorian()
    return gdt.replace(tzinfo=timezone.utc)

def log_and_report_error(context: str, error: Exception, extra: dict = None):
    tb = traceback.format_exc()
    error_id = uuid4().hex
    extra["error_id"] = error_id
    logger.error(
        context, extra={"error": str(error), "traceback": tb, **extra}
    )
    err_msg = (
        f"🔴 {context}:"
        f"\n\nError type: {type(error)}"
        f"\nError reason: {str(error)}"
        f"\n\nExtera Info:"
        f"\n{extra}"
    )
    send_message_api.delay(err_msg)

async def report_to_admin(level, fun_name, msg, user_table=None):
    try:
        report_level = {
            'info': {'thread_id': INFO_THREAD_ID, 'emoji': '🔵'},
            'warning': {'thread_id': WARNING_THREAD_ID, 'emoji': '🟡'},
            'notification': {'thread_id': NOTIFICATION_THREAD_ID, 'emoji': '⚖️'}
        }

        emoji = report_level.get(level, {}).get('emoji', '🔵')
        thread_id = report_level.get(level, {}).get('thread_id', INFO_THREAD_ID)
        message = f"{emoji} Report {level.replace('_', ' ')} {fun_name}\n\n{msg}"

        if user_table:
            message += (
                "\n\n👤 User Info:"
                f"\nUser name: {user_table.first_name} {user_table.last_name}"
                f"\nUser ID: {user_table.chat_id}"
                f"\nUsername: @{user_table.username}"
            )

        send_message_api.delay(message, thread_id)
    except Exception as e:
        log_and_report_error(f'error in report to admin.\n{e}', e)

@celery_app.task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def send_message_api(msg, message_thread_id=ERR_THREAD_ID, chat_id=TELEGRAM_CHAT_ID):
    requests.post(
        url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={'chat_id': chat_id, 'text': msg[:4096], 'message_thread_id': message_thread_id},
        timeout=10
    )

def handle_task_errors(func):
    @functools.wraps(func)
    def wrapper(self, chat_id, *args, **kwargs):
        try:
            return func(self, chat_id, *args, **kwargs)

        except Exception as e:
            retries = getattr(self.request, "retries", None)
            max_retries = getattr(self, "max_retries", None)

            log_and_report_error(
                f"Celery task: {func.__name__}",
                e,
                extra={
                    "chat_id": chat_id,
                    "_args": args,
                    "_kwargs": kwargs,
                    "retries": retries,
                    "max_retries": max_retries,
                }
            )

            if retries is not None and max_retries is not None and retries >= max_retries:
                try:
                    send_message_api.delay(
                        chat_id=chat_id,
                        message_thread_id=None,
                        msg=text.get("task_failed", "task_failed")
                    )
                except Exception as notify_err:
                    log_and_report_error(
                        f"Failed to notify user {chat_id} about final retry",
                        notify_err
                    )
            raise
    return wrapper

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
@handle_task_errors
def send_bill_message(self, chat_id: int, user_bill_id: int, message_id: int):
    data = GetAPI().get_power_bill_data(user_bill_id)

    msg = text.get("are_you_sure_about_this_address", "are_you_sure_about_this_address")
    msg += "\n\n" + translate_json_to_persian(data['data'])

    key = [
        [
            InlineKeyboardButton(keyboard.get('no_cancle_it', "no_cancle_it"), callback_data=f'add_b4d_a5s__cancle__{user_bill_id}'),
            InlineKeyboardButton(keyboard.get('yes_im_sure', "yes_im_sure"), callback_data=f'add_b4d_a5s__confirm__{user_bill_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(key).to_dict()

    response = requests.post(
        f"{BASE_URL}/editMessageText",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": msg,
            "reply_markup": reply_markup
        }
    )

    return response.json()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
@handle_task_errors
def add_bill_id(self, chat_id: int, user_bill_id: int, message_id: int):
    with SessionLocal() as session:
        try:
            insert_new_service_no_commit(session, user_bill_id)
            session.commit()
        except IntegrityError:
            session.rollback()

        try:
            add_user_service(session, user_bill_id, chat_id)
            session.commit()
            msg = text.get("bill_id_succesfully_added", "bill_id_succesfully_added")
        except IntegrityError:
            session.rollback()
            msg = text.get("you_already_have_this_bill", "you_already_have_this_bill")


    key = [[InlineKeyboardButton(keyboard.get('home_button', "home_button"), callback_data='start_edit_message')]]
    reply_markup = InlineKeyboardMarkup(key).to_dict()

    response = requests.post(
        f"{BASE_URL}/editMessageText",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": msg,
            "reply_markup": reply_markup
        }
    )

    return response.json()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
@handle_task_errors
def get_all_user_bill_ids(self, chat_id: int, message_id: int):
    with SessionLocal() as session:
        all_bills = get_user_services(session, chat_id)
        if not all_bills:
            key = [[InlineKeyboardButton(keyboard.get("new_notification", "new_notification"), callback_data=f'ask_for_bill_id')]]
            msg = text.get("no_service_found", "no_service_found")
        else:
            key = [[InlineKeyboardButton(bill.bill_id, callback_data=f'find_my_bill__{bill.bill_id}')] for bill in all_bills]
            msg = text.get("select_your_bill", "select_your_bill")

        key.append([InlineKeyboardButton(keyboard.get("back", "back"), callback_data='start_edit_message')])
        reply_markup = InlineKeyboardMarkup(key).to_dict()
    response = requests.post(
        f"{BASE_URL}/editMessageText",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": msg,
            "reply_markup": reply_markup
        }
    )

    return response.json()



@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
@handle_task_errors
def find_my_bill(self, chat_id: int, bill_id: int, message_id: int):
    data = GetAPI().get_power_bill_data(bill_id)

    msg = text.get("your_service_detail", "your_service_detail")
    msg += "\n\n" + translate_json_to_persian(data['data'])

    key = [[InlineKeyboardButton(keyboard.get("back", "back"), callback_data='my_bill_ids'),
            InlineKeyboardButton(keyboard.get("remove", "remove"), callback_data=f'remove_bill_assure__{bill_id}')]]
    reply_markup = InlineKeyboardMarkup(key).to_dict()

    response = requests.post(
        f"{BASE_URL}/editMessageText",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": msg,
            "reply_markup": reply_markup
        }
    )

    return response.json()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
@handle_task_errors
def remove_bill_id(self, chat_id: int, bill_id: int, message_id: int):
    with SessionLocal() as session:
        remove_bill(session, bill_id, chat_id)
        session.commit()

    key = [[InlineKeyboardButton(keyboard.get("back", "back"), callback_data='my_bill_ids')]]
    reply_markup = InlineKeyboardMarkup(key).to_dict()
    msg = text.get("removed_successfully", "removed_successfully")

    response = requests.post(
        f"{BASE_URL}/editMessageText",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": msg,
            "reply_markup": reply_markup
        }
    )

    return response.json()


@celery_app.task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def check_all_bills():
    try:
        with SessionLocal() as session:
            all_services = get_all_available_services(session)
            print(all_services)
            for i, service in enumerate(all_services):
                print(service.bill_id)
                check_the_service.apply_async(
                    args=(service.bill_id,),
                    countdown=i * 10
                )
    except Exception as e:
        log_and_report_error(f"Celery task: check_all_bills", e)
        raise e


@celery_app.task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def check_the_service(bill_id):
    try:
        with SessionLocal() as session:
            users = get_all_service_users(session, bill_id)
            from_date, to_date = get_jalali_date_range()
            get_data = GetAPI().get_planned_blackout_report(bill_id, from_date, to_date)
            data = get_data.get("data")
            if data:
                date = data[0]["outage_date"]
                time = data[0]["outage_stop_time"]
                valid_until = jalali_to_gregorian(date, time)
                update_valid_until(session, bill_id, valid_until)
                # msg = text.get("removed_successfully", "removed_successfully")
                msg = data
                for user in users:
                    print(user.chat_id)
                    send_message_api.delay(f"hello{data}", None, user.chat_id)

    except Exception as e:
        log_and_report_error(
            f"Celery task: check_the_service",
            e, extra={"bill_id": bill_id}
        )
        raise e
