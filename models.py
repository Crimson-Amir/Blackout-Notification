from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, BigInteger, ForeignKey
)
from sqlalchemy.orm import relationship
from database import Base

class UserService(Base):
    __tablename__ = "user_service"

    chat_id = Column(BigInteger, ForeignKey("user_detail.chat_id"), primary_key=True)
    bill_id = Column(String, ForeignKey("service.bill_id"), primary_key=True)

    # relationships back
    user = relationship("UserDetail", back_populates="user_services")
    service = relationship("Service", back_populates="service_users")

class UserDetail(Base):
    __tablename__ = "user_detail"

    user_id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    username = Column(String, unique=True)
    chat_id = Column(BigInteger, unique=True, nullable=False)
    active = Column(Boolean, default=True)
    wallet = Column(Integer, default=0)
    register_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user_services = relationship("UserService", back_populates="user")


class Service(Base):
    __tablename__ = "service"

    id = Column(Integer, primary_key=True)
    bill_id = Column(String, unique=True)
    active = Column(Boolean, default=True)
    valid_until = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    register_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    service_users = relationship("UserService", back_populates="service")


class Tokens(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True)
    token_name = Column(String)
    token = Column(String)

    register_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))