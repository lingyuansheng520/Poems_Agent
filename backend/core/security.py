from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from backend.Config.config import settings

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

# bcrypt 只处理前 72 个字节，超长口令需要提前拦截
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """把明文密码加密成可入库的哈希串。"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与数据库中的哈希是否匹配。"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        # 库里存了非法哈希时，一律按校验失败处理，不要抛出 500
        return False


def create_access_token(
    user_id: int,
    expires_minutes: int | None = None,
) -> str:
    """签发 JWT，sub 必须是字符串（PyJWT 规范要求）。"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        'sub': str(user_id),
        'iat': now,
        'exp': expire,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """解析 JWT，签名错误或过期会抛出 jwt 异常，由调用方处理。"""
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
