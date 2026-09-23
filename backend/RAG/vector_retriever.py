from backend.RAG.define_rag import init_vector
from functools import lru_cache

@lru_cache(maxsize=1)
def get_vector_retriever():
    vector=init_vector()
    vector_retriever=vector.as_retriever(k=10)
    return vector_retriever