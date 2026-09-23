from backend.Agent.RAG.Rerank import preprocess_retriever
from backend.Agent.langgraph_state.State import State
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from backend.Agent.model.LLM import rewrite_llm
from backend.Schema.schema import RewriteResult
from backend.Config.config import settings

def rewrite_query(state: State):
    llm_memory=state['messages'][:-1][-10:]
    user_query=state['messages'][-1].content
    system_prompt=ChatPromptTemplate(
        [
        ("system",
         "你是一个查询重写助手。你的唯一任务是把对话中最后一条用户消息改写成一句"
         "语义完整、适合检索的独立问题。\n"
         "规则：\n"
         "1. 把代词（它、他、这个、那个等）替换成对话历史中明确指代的事物；\n"
         "2. 修正错别字和语义不通顺的地方；\n"
         "3. 保持原意，不要添加新信息，不要回答问题；\n"
         "4. 只输出重写后的那一句话，不要任何解释、前缀或引号。"
         "用户输入是你需要重写的内容,并且只需要你重写用户的输入，不需要你去回答任何内容"),
        MessagesPlaceholder(variable_name="llm_memory"),
        ('human','{user_query}')
        ]
    )

    rewrite_chain=system_prompt|rewrite_llm.with_structured_output(RewriteResult,method='function_calling')
    resp=rewrite_chain.invoke(input={'user_query':user_query,'llm_memory':llm_memory})
    is_search=resp.is_search
    rewrite_content=resp.rewrite_content

    print(f'是否需要知识库检索:{is_search}')
    print(f'大模型重构的问题:{rewrite_content}')
    return {'rewrite_content':rewrite_content,'is_search':is_search}


def _head(m):
    bits=[]
    for label,key in [('出处','source'),('版本','edition'),('体裁','genre'),
                       ('创作','time'),('地点','place')]:
        v=m.get(key,'')
        if v and v not in settings.UNK:
            bits.append(f'{label}:{v}')

    return '|'.join(bits) if bits else settings.UNK[1]




def retriever(state:State):
    user_query=state['rewrite_content']
    docs=preprocess_retriever().invoke(user_query)
    r_content=[]
    origin_content=[]
    for i,doc in enumerate(docs,start=1):
        m=doc.metadata
        title=m['title']
        r_content.append(f'【{i}】 《{title}》 ({_head(m)}  {doc.page_content})')
        origin_content.append({
                'ref': i,
                'doc_id': m.get('poem_id', ''),
                'title': m.get('title', ''),
                'source': m.get('source', '未著录'),
                'edition': m.get('edition', '未著录'),
                'time': m.get('time', ''),
                'place': m.get('place', ''),
            })
    return {"search_content":'\n\n'.join(r_content),'citations':origin_content}







