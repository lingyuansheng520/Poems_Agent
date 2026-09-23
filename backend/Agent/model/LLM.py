from langchain_openai import ChatOpenAI
from backend.Config.config import settings


llm=ChatOpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    model=settings.DEEPSEEK_MODEL,
    max_tokens=2048,
    temperature=0.0
)

rewrite_llm=ChatOpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    model=settings.DEEPSEEK_MODEL,
    max_tokens=2048,
    temperature=0.0,
    extra_body={
        'thinking':{'type':'disabled'}
    }
)