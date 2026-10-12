from functools import lru_cache
from pathlib import Path

import chromadb
from langchain_chroma import Chroma
from langchain_huggingface.embeddings import HuggingFaceEmbeddings

from backend.Agent.RAG.load_document import load_document
from backend.Config.config import _base_dir

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VECTOR_DIR = _base_dir / 'Agent' / 'RAG' / 'vector_db'


@lru_cache(maxsize=1)
def init_embedding():
    embedding_path = str(_base_dir / 'Agent' / 'RAG' / 'embedding_models' / 'bge-base-zh-v1.5')
    embedding = HuggingFaceEmbeddings(
        model_name=embedding_path,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return embedding


def collection_size(path: Path) -> int:
    if not (path / 'chroma.sqlite3').exists():
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


@lru_cache(maxsize=1)
def resolve_vector_path() -> Path:

    if collection_size(VECTOR_DIR) > 0:
        return VECTOR_DIR
    candidates = sorted(
        (
            p for p in VECTOR_DIR.iterdir()
            if p.is_dir() and (p / 'chroma.sqlite3').exists()
        ),
        key=lambda p: p.name,
    )
    best_path, best_size = None, 0
    for candidate in candidates:
        size = collection_size(candidate)
        if size > best_size:  # 取条数最多的；条数相同则保留名字靠前的
            best_path, best_size = candidate, size

    if best_path is not None:
        logger.info('向量库实际数据位于：%s（%d 条）', best_path, best_size)
        return best_path

    return VECTOR_DIR


@lru_cache(maxsize=1)
def init_vector():
    embedding = init_embedding()
    vector_path = resolve_vector_path()
    vector = Chroma(
        embedding_function=embedding,
        persist_directory=str(vector_path),
    )

    # 只有空库才灌数据：这样既保证首次运行可用，也不会每次启动重复写库
    if collection_size(vector_path) == 0:
        doc = load_document()
        batch_size = 500
        total_size = len(doc)
        for i in range(0, total_size, batch_size):
            batch = doc[i:min(i + batch_size, total_size)]
            vector.add_documents(batch)
        logger.info('往向量库 %s 添加 %d 条数据', vector_path, total_size)

    return vector
