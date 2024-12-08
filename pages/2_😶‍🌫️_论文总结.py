import streamlit as st
from langchain_community.chat_models import ChatTongyi
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils import extract_files, is_token_expired

system_prompt = """你是一个文书助手。你的客户会交给你一篇文章，你需要用尽可能简洁的语言，总结这篇文章的内容。不允许使用 markdown 记号。"""


st.title('😶‍🌫️论文总结')


def main():
    if not st.session_state.files:
        st.write('### 还没上传文档哦')
    else:
        document_names = [file['file_name']
                          for file in st.session_state['files']]
        selected_doc_name = st.selectbox("选择文档", document_names)
        # 根据选定的文档名称从数据库中获取内容
        document_content = extract_files(
            st.session_state['files'][document_names.index(selected_doc_name)]['file_path'])['text']
        
        # 定义系统提示，以提供文档内容作为上下文
        llm = ChatTongyi(model_name="qwen-max", streaming=True)

        map_prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt),
             ("user", document_content)
            ])
        map_chain = map_prompt | llm | StrOutputParser()
        summary = map_chain.invoke(
            {"document_content": document_content}
        )
        st.markdown("### 总结如下：")
        st.text(summary)


if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
else:
    main()
