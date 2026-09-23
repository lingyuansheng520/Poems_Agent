import hashlib
import json
from functools import lru_cache
from backend.Config.config import settings,_base_dir
from backend.Agent.RAG.load_document import load_document
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_ROOT = _base_dir / 'Agent' / 'RAG'/'vector_db'

@lru_cache(maxsize=1)
def init_embedding():
    embedding_path=settings.embedding_path
    embedding=HuggingFaceEmbeddings(model_name=embedding_path,model_kwargs = {"device": "cpu"} ,encode_kwargs = {"normalize_embeddings": True})
    return embedding

def fingerprint():
    h=hashlib.sha256()
    with open(str(settings.knowledge_path),'rb') as f:
        for byte_block in iter(lambda: f.read(4096),b""):
            h.update(byte_block)
        return hashlib.sha256(f'{h.hexdigest()}|{len(load_document())}|{settings.TEXT_FIELDS}|{settings.UNK}'.encode()).hexdigest()[:8]




def init_vector():
    doc=load_document()
    embedding=init_embedding()
    fp=fingerprint()
    vector_path=Path(f'{DATA_ROOT}/{fp}')
    if (vector_path/'version.json').exists():
        logger.info(f'复用向量库，指纹为{fp}')
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
        (vector_path/'version.json').write_text(json.dumps({'fingerprint':fp,'rows':len(doc)},
                                                           ensure_ascii=False),encoding='utf8')

        logger.info(f'成功创建向量知识库，指纹为{fp},往向量库添加{total_size}条数据')

        return vector









