from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.model.define_db import ChatMessage, ChatSession
from backend.Schema.schema import (
    ChatMessageOut,
    ChatSessionDetail,
    ChatSessionOut,
    Role,
)

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail='会话不存在',
)

# message_no 分配冲突时的重试次数（同一会话并发写入时才会触发）
_MSG_NO_MAX_RETRY = 3


class ChatSessionService:
    """会话与消息的业务逻辑。

    所有方法都带 user_id 参数，并在查询条件里强制过滤，
    保证 A 用户永远拿不到 B 用户的会话（越权时统一返回 404，不泄露会话是否存在）。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- 内部工具 ----------------

    @staticmethod
    def _to_out(session: ChatSession, message_count: int = 0) -> ChatSessionOut:
        return ChatSessionOut(
            session_id=session.session_id,
            session_title=session.session_title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=message_count,
        )

    async def _get_owned(self, session_id: str, user_id: int) -> ChatSession:
        """按 (session_id, user_id) 取会话，取不到一律 404。"""
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.session_id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise _NOT_FOUND
        return session

    async def ensure_owned(self, session_id: str, user_id: int) -> str:
        """只做归属校验，供流式接口在建立 SSE 之前先返回 404。"""
        await self._get_owned(session_id, user_id)
        return session_id

    async def _count_messages(self, session_id: str) -> int:
        return (
            await self.db.execute(
                select(func.count())
                .select_from(ChatMessage)
                .where(ChatMessage.session_id == session_id)
            )
        ).scalar_one()

    async def _touch(self, session_id: str) -> None:
        """更新会话的 updated_at，让会话列表按最近活跃排序。"""
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(updated_at=func.now())
        )

    # ---------------- 会话 ----------------

    async def create_session(
        self,
        user_id: int,
        session_title: str | None = None,
    ) -> ChatSessionOut:
        session = ChatSession(
            session_id=uuid4().hex,
            user_id=user_id,
            session_title=session_title,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return self._to_out(session, 0)

    async def list_sessions(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[ChatSessionOut]]:
        total = (
            await self.db.execute(
                select(func.count())
                .select_from(ChatSession)
                .where(ChatSession.user_id == user_id)
            )
        ).scalar_one()

        # 子查询算出每个会话的消息数，避免 N+1
        counter = (
            select(
                ChatMessage.session_id.label('session_id'),
                func.count(ChatMessage.message_id).label('cnt'),
            )
            .group_by(ChatMessage.session_id)
            .subquery()
        )
        rows = await self.db.execute(
            select(ChatSession, func.coalesce(counter.c.cnt, 0))
            .outerjoin(counter, counter.c.session_id == ChatSession.session_id)
            .where(ChatSession.user_id == user_id)
            # DateTime 只精确到秒，同一秒内可能并列，用 session_id 兜底保证顺序稳定
            .order_by(ChatSession.updated_at.desc(), ChatSession.session_id.desc())
            .limit(limit)
            .offset(offset)
        )

        items = [self._to_out(session, int(cnt)) for session, cnt in rows.all()]
        return int(total), items

    async def get_session_detail(
        self,
        session_id: str,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> ChatSessionDetail:
        session = await self._get_owned(session_id, user_id)
        total_messages = await self._count_messages(session_id)
        messages = await self._fetch_messages(session_id, limit, offset)
        return ChatSessionDetail(
            session=self._to_out(session, total_messages),
            total_messages=total_messages,
            messages=messages,
        )

    async def rename_session(
        self,
        session_id: str,
        user_id: int,
        session_title: str,
    ) -> ChatSessionOut:
        session = await self._get_owned(session_id, user_id)
        session.session_title = session_title
        await self.db.commit()
        # updated_at 由 onupdate=func.now() 自动刷新，refresh 后重新读回来
        await self.db.refresh(session)
        return self._to_out(session, await self._count_messages(session_id))

    async def delete_session(self, session_id: str, user_id: int) -> None:
        await self._get_owned(session_id, user_id)
        # 显式两步删除，不依赖 ORM 级联，避免异步下的懒加载问题
        await self.db.execute(
            delete(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        await self.db.execute(
            delete(ChatSession).where(ChatSession.session_id == session_id)
        )
        await self.db.commit()

    # ---------------- 消息 ----------------

    async def _fetch_messages(
        self,
        session_id: str,
        limit: int,
        offset: int,
    ) -> list[ChatMessageOut]:
        rows = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.message_no.asc())
            .limit(limit)
            .offset(offset)
        )
        return [ChatMessageOut.model_validate(m) for m in rows.scalars().all()]

    async def list_messages(
        self,
        session_id: str,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[ChatMessageOut]]:
        await self._get_owned(session_id, user_id)
        total = await self._count_messages(session_id)
        return total, await self._fetch_messages(session_id, limit, offset)

    async def append_message(
        self,
        session_id: str,
        user_id: int,
        role: Role,
        content: str,
    ) -> ChatMessageOut:
        """向会话追加一条消息，message_no 自增。

        Agent 问答链路后续接上时，直接调用这个方法落库即可。
        """
        await self._get_owned(session_id, user_id)

        for attempt in range(_MSG_NO_MAX_RETRY):
            next_no = (
                await self.db.execute(
                    select(func.coalesce(func.max(ChatMessage.message_no), 0)).where(
                        ChatMessage.session_id == session_id
                    )
                )
            ).scalar_one() + 1

            message = ChatMessage(
                session_id=session_id,
                user_id=user_id,
                message_no=next_no,
                role=role,
                content=content,
            )
            self.db.add(message)
            try:
                await self.db.flush()
                await self._touch(session_id)
                await self.db.commit()
            except IntegrityError:
                # 同一会话并发送来时 message_no 撞车，回滚后重新分配
                await self.db.rollback()
                if attempt == _MSG_NO_MAX_RETRY - 1:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail='消息写入冲突，请重试',
                    )
                continue

            await self.db.refresh(message)
            return ChatMessageOut.model_validate(message)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='消息写入冲突，请重试',
        )
