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
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

celery_app = Celery(
    "tasks",
    broker="pyamqp://guest@localhost//"
)


@celery_app.task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def send_message_api(msg, message_thread_id=ERR_THREAD_ID, chat_id=TELEGRAM_CHAT_ID, bill_id=None, reply_markup=None, parse_mode=True):
    try:
        json_data = {
            'chat_id': chat_id,
            'text': msg[:4000]
        }
        if reply_markup:
            json_data["reply_markup"] = reply_markup
        if message_thread_id:
            json_data['message_thread_id'] = message_thread_id
        if parse_mode:
            json_data["parse_mode"] = "HTML"

        resp = requests.post(
            url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=json_data,
            timeout=10
        )
        logger.info(f"{msg}")
        data = resp.json()
        if not data.get("ok", False) and bill_id and data.get("description", None) == "Forbidden: bot was blocked by the user":
            with SessionLocal() as session:
                remove_bill(session, bill_id, chat_id)
                session.execute()
    except Exception as e:
        log_and_report_error("tasks: send_message_api", e, extra={"chat_id": chat_id, "message": msg})


def get_next_future_outage(data: list) -> dict | None:
    """
    From the API data list, return the first outage that is in the future.
    If none found, return None.
    """
    now = datetime.now(timezone.utc)

    for item in data:
        date = item["outage_date"]
        time = item["outage_stop_time"]

        # convert Jalali+time → UTC datetime
        outage_dt = jalali_to_gregorian(date, time)

        if outage_dt > now:
            return item
    return None



def jalali_to_gregorian(jalali_date: str, time_str: str) -> datetime:
    """
    Convert Jalali date (YYYY/MM/DD) + time (HH:MM) → Python datetime in UTC
    """
    year, month, day = map(int, jalali_date.split("/"))
    hour, minute = map(int, time_str.split(":"))
    jdt = jdatetime.datetime(year, month, day, hour, minute)
    gdt = jdt.togregorian()
    tehran_time = gdt.replace(tzinfo=ZoneInfo("Asia/Tehran"))
    return tehran_time.astimezone(timezone.utc)


def log_and_report_error(context: str, error: Exception, extra: dict = None):
    try:
        tb = traceback.format_exc()
        error_id = uuid4().hex
        extra = extra or {}
        extra["error_id"] = error_id
        logger.error(
            context, extra={"error": str(error), "traceback": tb, **extra}
        )
        err_msg = (
            f"[🔴 ERROR] {context}:"
            f"\n\nError type: {type(error)}"
            f"\nError reason: {str(error)}"
            f"\n\nExtera Info:"
            f"\n{extra}"
        )
        send_message_api.delay(str(err_msg), parse_mode=False)
    except Exception as e:
        send_message_api.delay(f'error in report to admin.\n{e}', parse_mode=False)


def format_outages(data):
    today = jdatetime.date.today()
    persian_weekdays = ["دوشنبه","سه‌شنبه","چهارشنبه","پنج‌شنبه","جمعه","شنبه","یکشنبه"]

    grouped = defaultdict(list)

    # Group outages by outage_date
    for outage in data:
        grouped[outage["outage_date"]].append(outage)

    lines = []

    # Iterate sorted by date
    for date_str in sorted(grouped.keys()):
        year, month, day = map(int, date_str.split("/"))
        outage_date = jdatetime.date(year, month, day)
        delta = (outage_date - today).days

        # Label selection
        if delta == 0:
            label = f"امروز ({date_str})"
        elif delta == 1:
            label = f"فردا ({date_str})"
        elif delta == 2:
            label = f"پس‌فردا ({date_str})"
        else:
            weekday = persian_weekdays[outage_date.weekday()]
            label = f"{weekday} ({date_str})"

        lines.append(label + ":")
        lines.append("")
        for outage in grouped[date_str]:
            lines.append(f"شروع: {outage['outage_start_time']}")
            lines.append(f"پایان: {outage['outage_stop_time']}")
            lines.append("")  # blank line between outages

    return "\n".join(lines).strip()


def report_to_admin(level, fun_name, msg, user_table=None):
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

        send_message_api.delay(message, thread_id, parse_mode=False)
    except Exception as e:
        log_and_report_error(f'error in report to admin.\n{e}', e)

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
                        msg=text.get("task_failed", "task_failed"),
                        parse_mode=False
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

            msg_ = ("New Bill ID Registered!"
                    f"\nchat_id: {chat_id}"
                    f"\nbill_id: {user_bill_id}")
            report_to_admin("info", "add_bill_id", msg_)

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

    msg_ = ("Bill ID Removed!"
            f"\nchat_id: {chat_id}"
            f"\nbill_id: {bill_id}")
    report_to_admin("info", "remove_bill_id", msg_)

    return response.json()


@celery_app.task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def check_all_bills():
    try:
        with SessionLocal() as session:
            all_services = get_all_available_services(session)
            for i, service in enumerate(all_services):
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
                next_outage = get_next_future_outage(data)

                if next_outage:
                    date = next_outage["outage_date"]
                    time = next_outage["outage_stop_time"]
                    valid_until = jalali_to_gregorian(date, time)
                else:
                    valid_until = (datetime.now(ZoneInfo("Asia/Tehran")) + timedelta(days=1)).astimezone(timezone.utc)

                update_valid_until(session, bill_id, valid_until)

                msg = text.get("outage_report", "outage_report").format(bill_id)
                msg += "\n\n" + format_outages([next_outage])  # show only the next one
                for user in users:
                    send_message_api.delay(msg, None, user.chat_id, bill_id=bill_id)

                msg_ = (
                    "Service Checked!"
                    f"\nbill_id: {bill_id}"
                    f"\nvalid_until: {valid_until}"
                )
                report_to_admin("info", "check_the_service", msg_)


    except Exception as e:
        log_and_report_error(
            f"Celery task: check_the_service",
            e, extra={"bill_id": bill_id}
        )
        raise e
