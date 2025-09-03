import models as model
from datetime import datetime, timezone

def create_user(session, user_detail):
    user = model.UserDetail(
        first_name=user_detail.first_name,
        last_name=user_detail.last_name,
        username=user_detail.username,
        chat_id=user_detail.id,
    )
    session.add(user)
    session.commit()

def get_user(session, chat_id):
    return session.query(model.UserDetail).filter(model.UserDetail.chat_id==chat_id).first()

def get_token(session, token_name):
    return (
        session.query(model.Tokens)
        .filter(model.Tokens.token_name == token_name)
        .order_by(model.Tokens.id.desc())
        .first()
    )

def insert_new_service_no_commit(session, bill_id):
    new_bill = model.Service(
        bill_id=bill_id,
    )
    session.add(new_bill)

def add_user_service(session, bill_id, chat_id, bill_name):
    user_service = model.UserService(
        chat_id=chat_id,
        bill_name=bill_name,
        bill_id=bill_id,
    )
    session.add(user_service)

def get_user_services(session, chat_id):
    return session.query(model.UserService).filter(model.UserService.chat_id==chat_id).all()


def remove_bill(session, bill_id, chat_id):
    rows = session.query(model.UserService).filter_by(
        bill_id=str(bill_id),
        chat_id=int(chat_id)
    ).delete(synchronize_session=False)
    return rows

def remove_service(session, bill_id):
    rows = session.query(model.Service).filter_by(
        bill_id=str(bill_id)
    ).delete(synchronize_session=False)
    session.commit()
    return rows


def get_all_available_services(session):
    now = datetime.now(timezone.utc)
    return (
        session.query(model.Service)
        .filter(model.Service.valid_until < now)
        .all()
    )


def get_all_service_users(session, bill_id):
    return (
        session.query(model.UserService)
        .filter(model.UserService.bill_id == bill_id)
        .all()
    )


def update_valid_until(session, bill_id: int, valid_until: datetime):
    service = session.query(model.Service).filter(model.Service.bill_id == bill_id).first()
    if not service:
        raise ValueError(f"Service {bill_id} not found")

    service.valid_until = valid_until
    session.add(service)
    session.commit()

def set_new_blackout_report_token(session, token):
    new_token = session.query(model.Tokens).filter(model.Tokens.token_name == "blackout_report_token").first()
    if not new_token:
        new_token = model.Tokens(
            token_name="blackout_report_token",
            token=token,
        )
    else:
        new_token.token = token

    session.add(new_token)
    session.commit()