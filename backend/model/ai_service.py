"""流式问答服务：把 LangGraph Agent 的输出转成 SSE 事件，并负责消息落库。

设计要点：
1. 图不带 checkpointer —— 对话历史统一从数据库读取后整体喂给图。
   好处是服务重启后上下文不丢，也不会出现「数据库 + 内存」双份历史导致重复。
2. 图与检索依赖全部懒加载，避免拖慢 FastAPI 启动（首次请求会慢一些）。
3. 每个事件都是 (event_name, payload) 二元组，由路由层拼成 SSE 文本，
   这样服务层不关心传输格式。
"""

import json
import time
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.model.chat_service import ChatSessionService
from backend.model.define_db import ChatMessage
from backend.Schema.schema import Role

# 喂给图的历史消息条数；agent 内部本身只取最近 11 条
_HISTORY_LIMIT = 20


@lru_cache(maxsize=1)
def get_graph():
    """首次调用时才加载 langgraph 与检索依赖（chromadb / 向量库等）。"""
    from backend.Agent.agent import build_graph

    return build_graph.compile()


def _chunk_text(obj) -> str:
    """从 LangChain 的 chunk / 消息 / ChatResult 里稳妥地取出文本。"""
    if obj is None:
        return ''
    content = getattr(obj, 'content', None)
    if content is None and hasattr(obj, 'generations'):
        generations = list(getattr(obj, 'generations') or [])
        if generations:
            content = getattr(getattr(generations[0], 'message', None), 'content', None)

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # 部分模型返回分段内容（如 [{'type': 'text', 'text': '...'}]）
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get('text') or '')
        return ''.join(parts)
    return ''


def sse_event(event: str, data: dict) -> str:
    """按 SSE 协议拼一条事件；ensure_ascii=False 保证中文可读。"""
    payload = json.dumps(data, ensure_ascii=False)
    return f'event: {event}\ndata: {payload}\n\n'


class ChatAgentService:
    """把「用户提问 -> Agent 生成 -> 落库」串成一条事件流。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- 历史消息 ----------------

    async def _load_history(self, session_id: str, limit: int = _HISTORY_LIMIT):
        """按时间正序取最近 limit 条消息，转成 LangChain 消息对象。"""
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        rows = (
            await self.db.execute(
                select(ChatMessage.role, ChatMessage.content)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.message_no.desc())
                .limit(limit)
            )
        ).all()

        mapping = {
            'user': HumanMessage,
            'assistant': AIMessage,
            'system': SystemMessage,
        }

        history = []
        for role, content in reversed(rows):
            key = role.value if isinstance(role, Role) else str(role)
            message_cls = mapping.get(key)
            if message_cls is not None:
                history.append(message_cls(content=content))
        return history

    # ---------------- 主流程 ----------------

    async def stream_reply(
        self,
        session_id: str,
        user_id: int,
        content: str,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        """产出 (事件名, 数据) 序列。

        事件顺序：
            meta -> status(改写完成) -> citations(命中知识库时) -> delta* -> done
        出错时以 error 收尾。
        """
        sessions = ChatSessionService(self.db)

        # 先把用户提问落库，这样即使后续生成失败，提问也不会丢
        user_message = await sessions.append_message(
            session_id, user_id, Role.USER, content
        )
        yield 'meta', {
            'session_id': session_id,
            'user_message': user_message.model_dump(mode='json'),
        }

        history = await self._load_history(session_id)
        graph = get_graph()
        config = {'configurable': {'thread_id': session_id}}

        started = time.perf_counter()
        pieces: list[str] = []
        citations: list[dict] = []
        is_search: bool | None = None

        try:
            async for event in graph.astream_events(
                {'messages': history}, config=config, version='v2'
            ):
                kind = event.get('event')
                node = (event.get('metadata') or {}).get('langgraph_node')
                name = event.get('name')

                if kind == 'on_chat_model_stream':
                    # 只透出最终作答节点的 token，忽略改写节点的内部流
                    if node != 'model_call':
                        continue
                    text = _chunk_text(event.get('data', {}).get('chunk'))
                    if text:
                        pieces.append(text)
                        yield 'delta', {'text': text}

                elif kind == 'on_chain_end':
                    # 必须同时匹配节点名，否则会把节点内部子链的结束事件也算进来
                    if name != node or not isinstance(event.get('data', {}).get('output'), dict):
                        continue
                    output = event['data']['output']
                    if node == 'rewrite':
                        is_search = bool(output.get('is_search'))
                        yield 'status', {
                            'stage': 'rewrite',
                            'is_search': is_search,
                            'rewrite_content': output.get('rewrite_content') or '',
                        }
                    elif node == 'retriever':
                        citations = output.get('citations') or []
                        yield 'citations', {'citations': citations}

                elif kind == 'on_chat_model_end' and node == 'model_call':
                    # 兜底：某些模型或版本不吐逐 token 事件时，用完整输出补一次
                    if not pieces:
                        text = _chunk_text(event.get('data', {}).get('output'))
                        if text:
                            pieces.append(text)
                            yield 'delta', {'text': text}

        except Exception as exc:  # noqa: BLE001 - 任何异常都要转成前端可读的错误
            yield 'error', {'detail': f'生成失败：{type(exc).__name__}: {exc}'}
            return

        answer = ''.join(pieces).strip()
        if not answer:
            yield 'error', {'detail': '模型没有返回内容，请重试'}
            return

        assistant_message = await sessions.append_message(
            session_id, user_id, Role.ASSISTANT, answer
        )
        yield 'done', {
            'message': assistant_message.model_dump(mode='json'),
            'citations': citations,
            'is_search': is_search,
            'elapsed_ms': int((time.perf_counter() - started) * 1000),
        }
