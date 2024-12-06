import streamlit as st

from langchain_community.callbacks import StreamlitCallbackHandler
from langchain_core.runnables import RunnableConfig
from utils import is_token_expired, optimize_text

st.set_page_config(page_title="文段优化", page_icon="✒️")
st.title("✒️文段优化")

def main():
    # 输入框
    user_input = st.text_area(
        "请输入需要优化的文本：",
        height=200,
        placeholder="在此输入你想要优化的文本..."
    )
    
    # 开始按钮
    if st.button("开始优化", type="primary"):
        if not user_input:
            st.warning("请先输入文本")
            return
        # 输出框
        st.markdown("## 优化结果")
        st.write_stream(optimize_text(user_input))

if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
else:
    main()
