from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_base_dir = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_base_dir / '.env'),
        env_file_encoding='utf-8',
        extra='ignore',
    )

    # ---------------- 大模型服务 ----------------
    MIMO_API_KEY: str
    MIMO_BASE_URL: str = 'https://api.xiaomimimo.com/v1'
    MIMO_MODEL: str = 'mimo-v2.5-pro'

    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = 'https://api.deepseek.com'
    DEEPSEEK_MODEL: str = 'deepseek-flash'

    # ---------------- 数据与第三方服务 ----------------
    DATABASE_URL: str
    PADDLEOCR_TOKEN: str

    # ---------------- 认证 / JWT ----------------
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    JWT_SECRET_KEY: str = Field(
        validation_alias=AliasChoices('JWT_SECRET_KEY', 'JWT_SECRET', 'SECRET_KEY'),
    )

    # ---------------- 检索语料 ----------------
    knowledge_path: str = str(_base_dir / 'Agent' / 'RAG' / 'knowledge' / '杜诗.csv')


settings = Settings()
