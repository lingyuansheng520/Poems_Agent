from langchain_classic.retrievers import EnsembleRetriever
from backend.RAG.BM25Retriever import get_bm25_retriever
from backend.RAG.vector_retriever import get_vector_retriever
from functools import lru_cache


@lru_cache(maxsize=1)
def get_ensemble_retriever():
    ensemble_retriever = EnsembleRetriever(
        retrievers=[get_bm25_retriever(),get_vector_retriever()],
        weights=[0.4,0.6])
    return ensemble_retriever



