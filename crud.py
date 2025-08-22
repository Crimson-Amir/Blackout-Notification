import models as model

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