from pydantic_settings import SettingsConfigDict,BaseSettings
from pathlib import Path

_base_dir=Path(__file__).resolve().parent.parent
print(_base_dir)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_base_dir/'.env'),env_file_encoding='utf-8')

    MIMO_API_KEY :str
    MIMO_BASE_URL :str = "https://api.xiaomimimo.com/v1"
    MIMO_MODEL :str = 'mimo-v2.5-pro'

    DEEPSEEK_API_KEY :str
    DEEPSEEK_BASE_URL :str = 'https://api.deepseek.com'
    DEEPSEEK_MODEL :str = 'deepseek-flash'

    DATABASE_URL : str
    PADDLEOCR_TOKEN :str

    knowledge_path : str =str(_base_dir/'RAG'/'knowledge'/'杜诗.csv')

settings = Settings()