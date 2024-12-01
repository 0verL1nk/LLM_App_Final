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
    # if document_content:
    #     st.write(f"已加载文档：{selected_doc_name}")
    # else:
    #     st.write("当前无文档.")
    # 定义系统提示，以提供文档内容作为上下文
    system_prompt = f"""你是一个 AI 助手。请根据以下文档内容回答问题：
    {document_content}

    如果你无法在文档中找到答案，可以联网搜索,并指明是搜索得来的信息。"""
    if len(msgs.messages) == 0 or st.sidebar.button("Reset chat history"):
        msgs.clear()
        msgs.add_ai_message(f"当前已加载文档 {selected_doc_name},快来提问吧.")
        st.session_state.steps = {}
        system_prompt = f"""请根据以下文档内容回答问题：
            {document_content}

            如果你无法在文档中找到答案，可以联网搜索,并指明是搜索得来的信息。"""
    show_chat(msgs)
    if prompt := st.chat_input():
        st.chat_message("user").write(prompt)
        llm = ChatTongyi(model_name="qwen-max", streaming=True)
        tools = [DuckDuckGoSearchRun(name="Search")]
        chat_agent = ConversationalChatAgent.from_llm_and_tools(llm=llm,
                                                                tools=tools,
                                                                system_prompt=system_prompt)
        executor = AgentExecutor.from_agent_and_tools(
            agent=chat_agent,
            tools=tools,
            memory=memory,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
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
