import hashlib
import json
from functools import lru_cache
from pathlib import Path

import chromadb
from langchain_chroma import Chroma
from langchain_huggingface.embeddings import HuggingFaceEmbeddings

from backend.Agent.RAG.load_document import load_document
from backend.Config.config import settings, _base_dir

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_ROOT = _base_dir / 'Agent' / 'RAG' / 'vector_db'


@lru_cache(maxsize=1)
def init_embedding():
    embedding_path = settings.embedding_path
    embedding = HuggingFaceEmbeddings(
        model_name=embedding_path,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return embedding


def collection_size(path: Path) -> int:
    if not path.exists() or not (path / 'chroma.sqlite3').exists():
        return 0
    try:
        client = chromadb.PersistentClient(path=str(path))
        total = 0
        for collection in client.list_collections():
            if isinstance(collection, str):  # 兼容旧版返回名字的 API
                collection = client.get_collection(collection)
            total += collection.count()
        return total
    except Exception as exc:  # 库损坏等情况一律当作空库，交给上层重建
        logger.warning('读取向量库 %s 失败：%s', path, exc)
        return 0


def fingerprint() -> str:
    h = hashlib.sha256()
    with open(str(settings.knowledge_path), 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            h.update(byte_block)
    return hashlib.sha256(
        f'{h.hexdigest()}|{len(load_document())}|{settings.TEXT_FIELDS}|{settings.UNK}'.encode()
    ).hexdigest()[:8]


@lru_cache(maxsize=1)
def init_vector():
    doc = load_document()
    embedding = init_embedding()
    fp = fingerprint()
    vector_path = Path(f'{DATA_ROOT}/{fp}')

    if (vector_path / 'version.json').exists():
        logger.info(f'复用向量库，指纹为{fp}')
        return Chroma(
            embedding_function=embedding,
            persist_directory=str(vector_path),
        )

    vector = Chroma(
        embedding_function=embedding,
        persist_directory=str(vector_path),
    )

    # 只有空库才灌数据：这样既保证首次运行可用，也不会每次启动重复写库
    if collection_size(vector_path) == 0:
        batch_size = 500
        total_size = len(doc)
        for i in range(0, total_size, batch_size):
            batch = doc[i:min(i + batch_size, total_size)]
            vector.add_documents(batch)
        (vector_path / 'version.json').write_text(
            json.dumps({'fingerprint': fp, 'rows': len(doc)}, ensure_ascii=False),
            encoding='utf8',
        )
        logger.info(f'成功创建向量知识库，指纹为{fp}，往向量库添加{total_size}条数据')

    return vector
