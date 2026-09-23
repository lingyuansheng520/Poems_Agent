from functools import lru_cache
from backend.Config.config import _base_dir
from backend.RAG.load_document import load_document
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def init_embedding():
    embedding_path=str(_base_dir/'embedding_models'/'bge-base-zh-v1.5')
    embedding=HuggingFaceEmbeddings(model_name=embedding_path,model_kwargs = {"device": "cpu"} ,encode_kwargs = {"normalize_embeddings": True})
    return embedding

def init_vector():
    doc=load_document()
    embedding=init_embedding()
    vector_path=Path(_base_dir/'vector_db')
    if vector_path.exists():
        vector = Chroma(
            embedding_function=embedding,
            persist_directory=str(vector_path)
        )
        return vector

    else:
        vector = Chroma(
            embedding_function=embedding,
            persist_directory=str(vector_path)
        )
        BATCH_SIZE=500
        total_size=len(doc)
        for i in range(0,total_size,BATCH_SIZE):
            batch=doc[i:min(i+BATCH_SIZE,total_size)]
            vector.add_documents(batch)

        logger.info(f'往向量库添加{total_size}条数据')

        return vector









