from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import create_access_token, hash_password, verify_password
from backend.model.define_db import SysUser
from backend.Schema.schema import Gender


class AuthService:
    """认证相关的业务逻辑：注册 / 登录。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- 内部工具 ----------------

    async def _get_by_name(self, user_name: str) -> SysUser | None:
        result = await self.db.execute(
            select(SysUser).where(SysUser.user_name == user_name)
        )
        return result.scalar_one_or_none()

    async def _get_by_email(self, email: str) -> SysUser | None:
        result = await self.db.execute(
            select(SysUser).where(SysUser.email == email)
        )
        return result.scalar_one_or_none()

    # ---------------- 注册 ----------------

    async def register_user(
        self,
        user_name: str,
        password: str,
        email: str,
        gender: Gender,
    ) -> dict:
        if await self._get_by_name(user_name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'用户名 {user_name} 已被注册',
            )
        if await self._get_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'邮箱 {email} 已被注册',
            )

        u_new = SysUser(
            user_name=user_name,
            email=email,
            gender=gender,
            password_hash=hash_password(password),
        )
        self.db.add(u_new)
        try:
            await self.db.commit()
        except IntegrityError:
            # 并发注册时上面的查重可能失效，靠数据库唯一约束兜底
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='用户名或邮箱已被注册',
            )

        await self.db.refresh(u_new)
        token = create_access_token(user_id=u_new.user_id)
        return {
            'code': 200,
            'messages': f'用户注册成功，用户名为 {u_new.user_name}',
            'access_token': token,
            'token_type': 'Bearer',
            'user_id': u_new.user_id,
            'user_name': u_new.user_name,
        }

    # ---------------- 登录 ----------------

    async def login_user(self, user_name: str, password: str) -> dict:
        user = await self._get_by_name(user_name)
        # 用户不存在与密码错误返回同一条提示，避免被枚举出有效用户名
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='用户名或密码错误',
                headers={'WWW-Authenticate': 'Bearer'},
            )

        token = create_access_token(user_id=user.user_id)
        return {
            'code': 200,
            'messages': '用户登录成功',
            'access_token': token,
            'token_type': 'Bearer',
            'user_id': user.user_id,
            'user_name': user.user_name,
        }
