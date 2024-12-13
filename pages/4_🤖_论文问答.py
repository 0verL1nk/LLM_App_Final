import streamlit as st
from langchain.agents import ConversationalChatAgent, AgentExecutor
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.memory import ConversationBufferMemory
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.tools import Tool
from langchain_community.vectorstores import FAISS
from langchain_community.callbacks import StreamlitCallbackHandler
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from langchain_community.chat_models import ChatTongyi
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.runnables import RunnableConfig

from utils import is_token_expired, extract_files

st.set_page_config(page_title="论文问答", page_icon="🤖")
st.title('🤖论文问答')






def show_chat(msgs):
    avatars = {"human": "user", "ai": "assistant"}
    for idx, msg in enumerate(msgs.messages):
        with st.chat_message(avatars[msg.type]):
            # Render intermediate steps if any were saved
            for step in st.session_state.steps.get(str(idx), []):
                if step[0].tool == "_Exception":
                    continue
                with st.status(f"**{step[0].tool}**: {step[0].tool_input}", state="complete"):
                    st.write(step[0].log)
                    st.write(step[1])
            st.write(msg.content)

def reset_chat_history(msgs):
    """重置聊天历史"""
    msgs.clear()
    if 'steps' in st.session_state:
        st.session_state.steps = {}
    # 清除文档相关的缓存
    if 'current_doc' in st.session_state:
        del st.session_state.current_doc
    if 'vectorstore' in st.session_state:
        del st.session_state.vectorstore

def main():
    msgs = StreamlitChatMessageHistory()
    memory = ConversationBufferMemory(
        chat_memory=msgs, return_messages=True, memory_key="chat_history", output_key="output"
    )
    
    # 初始化 selected_doc_index
    if 'selected_doc_index' not in st.session_state:
        st.session_state.selected_doc_index = 0
    
    # 通过下拉框选择文档
    document_names = [file['file_name'] for file in st.session_state['files']]
    selected_doc_name = st.selectbox(
        "选择文档", 
        document_names,
        index=st.session_state.selected_doc_index,  # 使用保存的索引
        on_change=lambda: reset_chat_history(msgs),
        key='doc_selector'  # 添加唯一的key
    )
    
    # 更新选中的文档索引
    st.session_state.selected_doc_index = document_names.index(selected_doc_name)
    
    # 检查是否需要重新加载文档
    current_doc = st.session_state.get('current_doc', {})
    if current_doc.get('name') != selected_doc_name:
        # 只在文档改变时重新加载
        document_result = extract_files(st.session_state['files'][document_names.index(selected_doc_name)]['file_path'])
        
        if document_result['result'] == 1:
            # 缓存文档内容和名称
            st.session_state.current_doc = {
                'name': selected_doc_name,
                'content': document_result['text']
            }
            
            # 创建向量存储
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?"]
            )
            chunks = text_splitter.split_text(document_result['text'])
            
            embeddings = DashScopeEmbeddings(model='text-embedding-v1')
            st.session_state.vectorstore = FAISS.from_texts(chunks, embeddings)
        else:
            st.error("文档加载失败：" + str(document_result['text']))
            return
    
    # 使用缓存的文档内容和向量存储
    if 'current_doc' in st.session_state and 'vectorstore' in st.session_state:
        document_content = st.session_state.current_doc['content']
        retriever = st.session_state.vectorstore.as_retriever(search_kwargs={"k": 5})

        def search_doc(query: str) -> str:
            """使用该工具在文档中搜索相关内容"""
            docs = retriever.get_relevant_documents(query)
            return "\n".join([doc.page_content for doc in docs])

        tools = [
            Tool(
                name="SearchDocument",
                func=search_doc,
                description="当需要查找文档中的具体内容时使用此工具,输入具体的问题或关键词"
            ),
            DuckDuckGoSearchRun(name="Search"),
        ]

        if len(msgs.messages) <= 1:
            msgs.clear()
            # 转义文档内容中的花括号
            safe_content = document_content.replace("{", "{{").replace("}", "}}")
            
            system_message = """你是一个专业的论文问答助手。

我会给你一篇论文内容：

{}

请基于以上论文内容回答用户问题。回答时请注意:
1. 优先使用论文中的内容回答
2. 使用 SearchDocument 工具查找具体细节
3. 仅当论文内容无法回答时,才使用 Search 工具联网查询
4. 回答要简洁清晰,并标注信息来源

输出格式要求：
1. 使用 Markdown 格式输出
2. 重要内容使用**加粗**标记
3. 使用适当的标题层级(###, ####)组织内容
4. 数学公式使用 LaTeX 格式：
   - 行内公式使用单个$包裹
   - 独立公式块使用$$包裹
5. 如有必要使用列表或表格增强可读性
6. 引用原文时使用>引用格式
7. 关键概念或术语使用`代码块`标记""".format(safe_content)

            msgs.add_ai_message(f"已加载文档 {selected_doc_name},我已经阅读了全文,请问有什么问题?")
            st.session_state.steps = {}
        else:
            system_message = """你是一个专业的论文问答助手。回答问题时请遵循以下策略:
1. 优先使用 SearchDocument 工具在文档中搜索相关内容
2. 如果搜索结果不完整,可以追加搜索其他相关内容
3. 仅当文档内搜索无法解答时,才使用 Search 工具联网查询
4. 回答要简洁清晰,并标注信息来源

输出格式要求：
1. 使用 Markdown 格式输出
2. 重要内容使用**加粗**标记
3. 使用适当的标题层级(###, ####)组织内容
4. 数学公式使用 LaTeX 格式：
   - 行内公式使用单个$包裹
   - 独立公式块使用$$包裹
5. 如有必要使用列表或表格增强可读性
6. 引用原文时使用>引用格式
7. 关键概念或术语使用`代码块`标记"""

        show_chat(msgs)
        if prompt := st.chat_input():
            st.chat_message("user").write(prompt)
            llm = ChatTongyi(model_name="qwen-max", streaming=True)
            chat_agent = ConversationalChatAgent.from_llm_and_tools(
                llm=llm,
                tools=tools,
                system_message=system_message,
                input_variables=["input", "chat_history", "agent_scratchpad"]  # 明确指定输入变量
            )

            executor = AgentExecutor.from_agent_and_tools(
                agent=chat_agent,
                memory=memory,
                return_intermediate_steps=True,
                handle_parsing_errors=True,
                verbose=True,
                tools=tools
            )
            
            with st.chat_message("assistant"):
                st_cb = StreamlitCallbackHandler(st.container(), expand_new_thoughts=False)
                cfg = RunnableConfig()
                cfg["callbacks"] = [st_cb]
                response = executor.invoke(
                    {
                        "input": prompt,
                        "chat_history": memory.chat_memory.messages,
                    }, 
                    cfg
                )
                st.markdown(response["output"])
                st.session_state.steps[str(len(msgs.messages) - 1)] = response["intermediate_steps"]


# init
if 'files' not in st.session_state:
    st.session_state.files = []

if 'current_doc' not in st.session_state:
    st.session_state.current_doc = {}

if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = None


if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
elif not st.session_state.files:
    st.write('### 还没上传文档哦')
else:
    main()
