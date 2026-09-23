from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from backend.Config.config import _base_dir
from functools import lru_cache
from pathlib import Path
from backend.Agent.RAG.RRF import get_ensemble_retriever

@lru_cache(maxsize=1)
def init_reranker():
    rerank_path=Path(_base_dir/'Agent'/'RAG'/"embedding_models"/"reranker"/"models"/"BAAI--bge-reranker-base"/"snapshots"/'master')
    cross_encode=HuggingFaceCrossEncoder(model_name=str(rerank_path))
    reranker=CrossEncoderReranker(model=cross_encode,top_n=3)
    return reranker

@lru_cache(maxsize=1)
def preprocess_retriever():
    reranker=init_reranker()
    compression_retriever=ContextualCompressionRetriever(base_retriever=get_ensemble_retriever(),base_compressor=reranker)
    return compression_retriever

