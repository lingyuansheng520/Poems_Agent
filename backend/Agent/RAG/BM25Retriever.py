from langchain_community.retrievers import BM25Retriever
from backend.Agent.RAG.load_document import load_document
from functools import lru_cache
import jieba


@lru_cache(maxsize=1)

def chinese_cut(document):
    return list(jieba.cut(document))

def get_bm25_retriever():
    doc=load_document()
    bm25_retriever = BM25Retriever.from_documents(documents=doc,k=10,preprocess_func=chinese_cut)
    return bm25_retriever
