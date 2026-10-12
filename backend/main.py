from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.model.define_db import Base, engine
from backend.router import auth, chat

STATIC_DIR = Path(__file__).resolve().parent / 'static'


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时确保表结构存在（已存在的表不会被改动，不会丢数据）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title='杜诗智能问答 API',
    description='杜诗项目后端：用户认证、会话管理与检索问答',
    version='0.1.0',
    lifespan=lifespan,
)

# 前后端分离需要跨域；认证靠请求头里的 Bearer Token，
# 不依赖 Cookie，因此 allow_credentials 保持 False（与 allow_origins=['*'] 才不冲突）
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth.router)
app.include_router(chat.router)

# 简易前端单页（Vue 3，vue.global.prod.js 已内置到本地，不依赖外网）
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


@app.get('/', include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / 'index.html'))


@app.get('/health', tags=['系统'], summary='健康检查')
async def health() -> dict:
    return {'status': 'ok'}
