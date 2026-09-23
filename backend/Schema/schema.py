from pydantic import BaseModel,Field



class RewriteResult(BaseModel):
    is_search : bool=Field(description='是否需要检索知识库。如果用户问题涉及具体知识、事实、文档内容等需要外部信息才能回答，返回 True；'
                    '如果是闲聊、打招呼、纯逻辑推理、或仅基于上下文即可回答，返回 False')
    rewrite_content: str=Field(description="重写后的独立检索问题。如果 search_knowledge 为 False，此字段返回空字符串")