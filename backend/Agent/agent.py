import uuid
import asyncio
from backend.Agent.model.LLM import llm
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
import time
from backend.Agent.langgraph_state.State import State
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.memory import MemorySaver
from backend.Agent.RAG.recall_search import retriever,rewrite_query
from langchain_core.messages import HumanMessage,AIMessage

def model_call(state:State):
    memory=state['messages'][-11:]
    if state['is_search']:
        recall_knowledge=state['search_content']
    else:
        recall_knowledge='本轮未检索到相关知识库内容'
    system_prompt = ChatPromptTemplate(
        [
            ('system',
             "你是一位深耕杜甫诗词与唐代文学研究的资深学者，治学严谨、考据扎实。"
             "你的核心任务是：当用户提出杜甫诗词或唐代文学相关学术问题时，依据下方【知识库内容】作答。\n\n"
             "【知识库里检索到的内容】\n{recall_knowledge}\n\n"
             "回答要求：\n"
             "1. 先判断用户意图：若用户只是问候、寒暄、自我介绍、感谢、询问你的能力范围等，不涉及具体学术问题，请直接自然、友好地回应；不要引用知识库，也不要主动说明「知识库为空」「检索不到资料」等检索状态。\n"
             "2. 若用户提出杜甫诗词或唐代文学相关学术问题，则严格依据知识库内容作答，不得虚构、臆测或引入知识库之外的信息。\n"
             "3. 对学术问题，若知识库内容为空或不足以回答，请简短说明「根据现有资料无法确定」，并提示用户可补充的信息，如具体篇目、仇兆鳌《杜诗详注》等注本条目、相关史料或研究议题；切勿自行编造。\n"
             "4. 引用诗句时须逐字准确，保留原文标点；涉及字词含义、创作背景、诗人生平时，优先引用知识库中的原文表述。\n"
             "5. 回答应条理清晰、文雅凝练，可适当分点或分段，兼具学术性与可读性。\n"
             "6. 使用简体中文作答。"
             ),
            MessagesPlaceholder(variable_name='memory')
        ]
    )
    prompt_template=system_prompt.format_messages(recall_knowledge=recall_knowledge,memory=memory)

    resp=llm.invoke(prompt_template)
    result=resp.content
    return {'messages':[AIMessage(result)]}

def search_router(state:State):
    if state['is_search']:
        return 'retriever'
    return 'model_call'

build_graph=StateGraph(State)

build_graph.add_node('rewrite',rewrite_query)
build_graph.add_node('retriever',retriever)
build_graph.add_node('model_call',model_call)
build_graph.add_edge(START,'rewrite')
build_graph.add_conditional_edges('rewrite',search_router,{'retriever':'retriever','model_call':'model_call'})
build_graph.add_edge('rewrite','retriever')
build_graph.add_edge('retriever','model_call')
build_graph.add_edge('model_call',END)


memory=MemorySaver()
graph_app=build_graph.compile(checkpointer=memory)


async def start_recall(state:State):
    thread_id=str(uuid.uuid4())
    config={
        "configurable":{"thread_id":thread_id}
    }
    while True:
        user_query=input('请用户输入问题:')
        if user_query=='exit':
            break
        if user_query.strip()=='':
            continue

        start_time=time.perf_counter()
        complete_answer=''
        async for token in graph_app.astream_events(input={'messages':[HumanMessage(user_query)]},config=config,version='v2'):
            event=token['event']
            if event=='on_chat_model_stream':
                node_name=token['metadata']['langgraph_node']
                if node_name=='model_call':
                    chunk=token['data']['chunk'].content
                    print(chunk,flush=True,end='')
                    complete_answer+=str(chunk)

        end_time=time.perf_counter()

        print(f'\n\n总共耗费时间:{end_time-start_time}s')



if __name__=='__main__':
    asyncio.get_event_loop().run_until_complete(start_recall(state=State))












