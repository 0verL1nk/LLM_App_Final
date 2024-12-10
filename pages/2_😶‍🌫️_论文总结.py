import streamlit as st
from langchain_community.chat_models import ChatTongyi
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils import extract_files, is_token_expired

system_prompt = """你是一个专业的文献分析助手。请你对给定的文章进行全面而简洁的总结，需要包含以下要点：

1. 核心观点：用1-2句话概括文章的主要论点或发现
2. 研究方法：简述作者采用的研究方法或分析框架
3. 关键结论：列出2-3个最重要的研究结论
4. 创新点：指出文章的创新之处或独特贡献

要求：
- 使用清晰、准确的语言
- 保持客观中立的语气
- 突出文章的实质性内容
- 总结篇幅控制在300-500字之间
- 避免使用过于专业的术语

请按照上述结构输出内容，确保内容既专业又易于理解。"""


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
        st.write(summary)


if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
else:
    main()
