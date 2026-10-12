from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user, get_db
from backend.model.define_db import SysUser
from backend.model.get_service import AuthService
from backend.Schema.schema import TokenResponse, UserOut, UserRegister

router = APIRouter(prefix='/auth', tags=['认证'])


@router.post(
    '/register',
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary='用户注册',
)
async def register(
    payload: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """注册成功即返回 token，前端无需再调一次登录。"""
    service = AuthService(db)
    return await service.register_user(
        user_name=payload.user_name,
        password=payload.password,
        email=payload.email,
        gender=payload.gender,
    )


@router.post('/login', response_model=TokenResponse, summary='用户登录')
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    return await service.login_user(
        user_name=form.username,
        password=form.password,
    )


@router.get('/me', response_model=UserOut, summary='获取当前登录用户')
async def read_me(current_user: SysUser = Depends(get_current_user)) -> SysUser:
    """凭 Bearer Token 换取当前用户资料，用于前端校验登录态。"""
    return current_user
