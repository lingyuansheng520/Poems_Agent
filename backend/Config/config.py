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

    knowledge_path : str =str(_base_dir/'Agent'/'RAG'/'knowledge'/'杜诗.csv')
    embedding_path:str=str(_base_dir/'Agent'/'RAG'/'embedding_models'/'bge-base-zh-v1.5')

    UNK :list[str] = ['暂时未录入', '待考证', '未收集','未著录']
    TEXT_FIELDS :list[str]= ['诗歌篇名', '诗文正文', '体裁', '创作时间', '创作地点',
                   '相关人物', '相关地点', '典故', '意象', '历史事件', '注释', '评点']
settings = Settings()