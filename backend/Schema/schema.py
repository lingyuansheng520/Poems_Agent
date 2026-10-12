import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Agent 检索重写结果
# ---------------------------------------------------------------------------


class RewriteResult(BaseModel):
    is_search: bool = Field(
        description='是否需要检索知识库。如果用户问题涉及具体知识、事实、文档内容等需要外部信息才能回答，返回 True；'
                    '如果是闲聊、打招呼、纯逻辑推理、或仅基于上下文即可回答，返回 False'
    )
    rewrite_content: str = Field(
        description='重写后的独立检索问题。如果 search_knowledge 为 False，此字段返回空字符串'
    )


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------


class Role(str, enum.Enum):
    USER = 'user'
    ASSISTANT = 'assistant'
    SYSTEM = 'system'


class Gender(enum.Enum):
    MALE = 1
    FEMALE = 0


# ---------------------------------------------------------------------------
# 认证相关请求 / 响应模型
# ---------------------------------------------------------------------------

# 不引入 email-validator 依赖，用轻量正则做基本格式校验
_EMAIL_PATTERN = r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'
_BCRYPT_MAX_BYTES = 72


class UserRegister(BaseModel):
    """注册请求体。"""

    user_name: str = Field(min_length=2, max_length=20, description='用户名')
    password: str = Field(min_length=6, max_length=64, description='密码')
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=50, description='邮箱')
    gender: Gender = Field(description='性别：1=男，0=女')

    @field_validator('password')
    @classmethod
    def _check_password_bytes(cls, v: str) -> str:
        if len(v.encode('utf-8')) > _BCRYPT_MAX_BYTES:
            raise ValueError('密码过长（编码后不能超过 72 字节）')
        return v

    @field_validator('user_name')
    @classmethod
    def _check_user_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('用户名不能为空')
        if ' ' in v:
            raise ValueError('用户名不能包含空格')
        return v


class UserLogin(BaseModel):
    """登录请求体（JSON 方式；当前路由走 OAuth2 表单，此模型备用）。"""

    user_name: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=64)


class TokenResponse(BaseModel):
    """注册 / 登录成功后的统一返回体。"""

    code: int = 200
    messages: str
    access_token: str
    token_type: str = 'Bearer'
    user_id: int
    user_name: str


class UserOut(BaseModel):
    """对外暴露的用户信息（绝不包含 password_hash）。"""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_name: str
    email: str
    gender: Gender
    created_at: datetime


# ---------------------------------------------------------------------------
# 会话 / 消息
# ---------------------------------------------------------------------------


class ChatSessionCreate(BaseModel):
    """新建会话请求体。标题可省略，前端可先显示「新会话」，首条消息后再回填。"""

    session_title: str | None = Field(default=None, max_length=200)


class ChatSessionRename(BaseModel):
    """重命名会话请求体。"""

    session_title: str = Field(min_length=1, max_length=200)

    @field_validator('session_title')
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('会话标题不能为空')
        return v


class ChatSessionOut(BaseModel):
    """会话摘要（列表 / 详情共用）。"""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    session_title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatSessionListOut(BaseModel):
    total: int
    items: list[ChatSessionOut]


class ChatMessageCreate(BaseModel):
    """写入一条消息请求体。"""

    role: Role = Role.USER
    content: str = Field(min_length=1, max_length=10000)

    @field_validator('role')
    @classmethod
    def _reject_system_role(cls, v: Role) -> Role:
        # 禁止外部写入 system 角色，避免绕过服务端的提示词控制
        if v is Role.SYSTEM:
            raise ValueError('不允许通过接口写入 system 角色的消息')
        return v


class ChatMessageOut(BaseModel):
    """单条消息。"""

    model_config = ConfigDict(from_attributes=True)

    message_id: int
    session_id: str
    message_no: int
    role: Role
    content: str
    created_at: datetime


class ChatMessageListOut(BaseModel):
    total: int
    items: list[ChatMessageOut]


class ChatSessionDetail(BaseModel):
    """会话详情：会话信息 + 分页消息。"""

    session: ChatSessionOut
    total_messages: int
    messages: list[ChatMessageOut]


class ChatAskIn(BaseModel):
    """流式问答请求体：只需要用户这一句话，角色固定为 user。"""

    content: str = Field(min_length=1, max_length=2000, description='用户提问')

    @field_validator('content')
    @classmethod
    def _strip_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('提问内容不能为空')
        return v

