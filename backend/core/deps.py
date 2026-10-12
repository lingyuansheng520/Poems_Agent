from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import decode_token
from backend.model.define_db import SysUser, async_session

# tokenUrl 指向登录接口，Swagger 的 Authorize 按钮会据此发起表单登录
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/login')

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='登录状态已失效，请重新登录',
    headers={'WWW-Authenticate': 'Bearer'},
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """每个请求一个数据库会话，请求结束自动关闭。"""
    async with async_session() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> SysUser:
    """从 Bearer Token 解析出当前登录用户。"""
    try:
        payload = decode_token(token)
        user_id = int(payload['sub'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise _credentials_exception

    user = await db.get(SysUser, user_id)
    if user is None:
        raise _credentials_exception
    return user
