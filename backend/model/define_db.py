import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession,async_sessionmaker
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column,relationship
from backend.Config.config import settings
from sqlalchemy import String,BigInteger,DateTime,Enum,func,ForeignKey,UniqueConstraint,Index,Integer,Text,JSON,Numeric
from backend.Schema.schema import Gender,Role

DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass


class SysUser(Base):
    __tablename__ = 'system_user'
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_name : Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    password_hash : Mapped[str] = mapped_column(String(256), nullable=False)
    email : Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    gender : Mapped[Gender] = mapped_column(Enum(Gender),nullable=False)
    created_at : Mapped[datetime] = mapped_column(DateTime,nullable=False,server_default=func.now())
    update_at : Mapped[datetime] = mapped_column(DateTime,nullable=False,server_default=func.now(),onupdate=func.now())

    sessions : Mapped[list['ChatSession']] = relationship(
        back_populates='user', cascade="all, delete-orphan", passive_deletes=True)



class ChatSession(Base):
    __tablename__ = 'chat_session'

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('system_user.user_id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    session_title: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    user: Mapped["SysUser"] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.message_no",
    )

    __table_args__ = (
        Index('idx_user_updated', 'user_id', 'updated_at'),
    )


class ChatMessage(Base):
    __tablename__ = 'chat_message'

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('chat_session.session_id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('system_user.user_id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    message_no: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

    __table_args__ = (
        UniqueConstraint('session_id', 'message_no', name='uq_session_msg_no'),
        Index('idx_session_created', 'session_id', 'created_at'),
    )


