from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user, get_db
from backend.model.ai_service import ChatAgentService, sse_event
from backend.model.chat_service import ChatSessionService
from backend.model.define_db import SysUser
from backend.Schema.schema import (
    ChatAskIn,
    ChatMessageCreate,
    ChatMessageListOut,
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionListOut,
    ChatSessionOut,
    ChatSessionRename,
)

router = APIRouter(prefix='/sessions', tags=['会话'])


@router.post(
    '',
    response_model=ChatSessionOut,
    status_code=status.HTTP_201_CREATED,
    summary='新建会话',
)
async def create_session(
    payload: ChatSessionCreate | None = None,
    current_user: SysUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionOut:
    service = ChatSessionService(db)
    return await service.create_session(
        user_id=current_user.user_id,
        session_title=payload.session_title if payload else None,
    )


@router.get('', response_model=ChatSessionListOut, summary='我的会话列表')
async def list_sessions(
    limit: int = Query(20, ge=1, le=100, description='每页条数'),
    offset: int = Query(0, ge=0, description='偏移量'),
    current_user: SysUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionListOut:
    service = ChatSessionService(db)
    total, items = await service.list_sessions(
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )
    return ChatSessionListOut(total=total, items=items)


@router.get('/{session_id}', response_model=ChatSessionDetail, summary='会话详情（含消息）')
async def get_session(
    session_id: str,
    limit: int = Query(100, ge=1, le=500, description='消息条数'),
    offset: int = Query(0, ge=0, description='消息偏移量'),
    current_user: SysUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetail:
    service = ChatSessionService(db)
    return await service.get_session_detail(
        session_id=session_id,
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )


@router.patch('/{session_id}', response_model=ChatSessionOut, summary='重命名会话')
async def rename_session(
    session_id: str,
    payload: ChatSessionRename,
    current_user: SysUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionOut:
    service = ChatSessionService(db)
    return await service.rename_session(
        session_id=session_id,
        user_id=current_user.user_id,
        session_title=payload.session_title,
    )


@router.delete(
    '/{session_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='删除会话（连带消息）',
)
async def delete_session(
    session_id: str,
    current_user: SysUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = ChatSessionService(db)
    await service.delete_session(
        session_id=session_id,
        user_id=current_user.user_id,
    )


@router.get(
    '/{session_id}/messages',
    response_model=ChatMessageListOut,
    summary='会话消息列表',
)
async def list_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=500, description='每页条数'),
    offset: int = Query(0, ge=0, description='偏移量'),
    current_user: SysUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageListOut:
    service = ChatSessionService(db)
    total, items = await service.list_messages(
        session_id=session_id,
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )
    return ChatMessageListOut(total=total, items=items)


@router.post(
    '/{session_id}/messages',
    response_model=ChatMessageOut,
    status_code=status.HTTP_201_CREATED,
    summary='追加一条消息',
)
async def append_message(
    session_id: str,
    payload: ChatMessageCreate,
    current_user: SysUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageOut:
    """落库一条消息。role 只允许 user / assistant，system 会被拒绝。

    后续 Agent 问答链路接上后，服务端生成回复也走这个方法落库。
    """
    service = ChatSessionService(db)
    return await service.append_message(
        session_id=session_id,
        user_id=current_user.user_id,
        role=payload.role,
        content=payload.content,
    )


# 关闭各级缓冲，保证 token 能第一时间到浏览器
_SSE_HEADERS = {
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
}


@router.post('/{session_id}/chat', summary='流式问答（SSE）')
async def chat_stream(
    session_id: str,
    payload: ChatAskIn,
    current_user: SysUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """向会话提问并以 SSE 流式返回生成过程。

    事件类型：
        meta      —— 用户提问已落库
        status    —— 改写完成（含是否需要检索知识库）
        citations —— 命中的知识库条目（需要检索时才有）
        delta     —— 增量文本，**前端需自行累加**
        done      —— 生成结束，附带落库后的 assistant 消息与耗时
        error     —— 生成失败

    注意：用户提问在流开始前就已落库；若客户端中途断开，
    助手回复不会入库（提问仍在）。
    """
    # 先校验归属，越权在此直接返回 404（SSE 一旦开始就无法再改状态码）
    await ChatSessionService(db).ensure_owned(session_id, current_user.user_id)

    agent = ChatAgentService(db)

    async def event_stream():
        async for event_name, data in agent.stream_reply(
            session_id=session_id,
            user_id=current_user.user_id,
            content=payload.content,
        ):
            yield sse_event(event_name, data)

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers=_SSE_HEADERS,
    )
