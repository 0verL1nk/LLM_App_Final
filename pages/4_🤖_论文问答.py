import os

import streamlit as st
from utils import is_token_expired, extract_files
from langchain.agents import ConversationalChatAgent, AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain_community.callbacks import StreamlitCallbackHandler
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.runnables import RunnableConfig
from langchain_community.chat_models import ChatTongyi
from langchain.tools import Tool

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


def main():
    msgs = StreamlitChatMessageHistory()
    memory = ConversationBufferMemory(
        chat_memory=msgs, return_messages=True, memory_key="chat_history", output_key="output"
    )
    # 通过下拉框选择文档
    document_names = [file['file_name'] for file in st.session_state['files']]
    selected_doc_name = st.selectbox("选择文档", document_names)
    # 根据选定的文档名称从数据库中获取内容
    document_content = extract_files(st.session_state['files'][document_names.index(selected_doc_name)]['file_path'])
    
    # 添加查看文档内容的工具
    def get_document_content(file=None):
        """当需要查看完整文档内容时使用此工具"""
        return document_content

    tools = [
        DuckDuckGoSearchRun(name="Search"),
        Tool(
            name="ViewDocument",
            func=get_document_content,
            description="当你需要查看当前文档的完整内容时使用此工具,无需输入,该工具返回整篇文档,你应该自行判断正文以及无关内容.若已经查看过文档,就不用再使用此工具"
        )
    ]
    
    # prefix = f"""你是一个 AI 助手。请根据以下文档内容回答问题：
    # {document_content}

    # 如果你无法在文档中找到答案，可以使用以下工具：
    # 1. Search工具进行联网搜索，并指明是搜索得来的信息
    # 2. ViewDocument工具查看完整的文档内容

    # 请优先使用文档中的内容回答问题。"""

    if len(msgs.messages) <= 1 or st.sidebar.button("Reset chat history"):
        msgs.clear()
        msgs.add_ai_message(f"当前已加载文档 {selected_doc_name},快来提问吧.")
        st.session_state.steps = {}
        # prefix = f"""你是一个 AI 助手。请根据以下文档内容回答问题：
        #     {document_content}

        #     如果你无法在文档中找到答案，可以使用以下工具：
        #     1. Search工具进行联网搜索，并指明是搜索得来的信息
        #     2. ViewDocument工具查看完整的文档内容

        #     请优先使用文档中的内容回答问题。"""
    show_chat(msgs)
    if prompt := st.chat_input():
        st.chat_message("user").write(prompt)
        llm = ChatTongyi(model_name="qwen-max", streaming=True)
        chat_agent = ConversationalChatAgent.from_llm_and_tools(
            llm=llm,
            tools=tools,
        )

        executor = AgentExecutor.from_agent_and_tools(
            agent=chat_agent,
            tools=tools,
            memory=memory,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            verbose=True
        )
        with st.chat_message("assistant"):
            st_cb = StreamlitCallbackHandler(st.container(), expand_new_thoughts=False)
            cfg = RunnableConfig()
            cfg["callbacks"] = [st_cb]
            response = executor.invoke(prompt, cfg)
            st.write(response["output"])
            st.session_state.steps[str(len(msgs.messages) - 1)] = response["intermediate_steps"]


if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
elif not st.session_state.files:
    st.write('### 还没上传文档哦')
else:
    main()
