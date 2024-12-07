import streamlit as st

from langchain_community.callbacks import StreamlitCallbackHandler
from langchain_core.runnables import RunnableConfig
from utils import is_token_expired, optimize_text_with_params

st.set_page_config(page_title="文段优化", page_icon="✒️", layout="wide")
st.title("✒️文段优化")

def main():
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 输入框
        user_input = st.text_area(
            "请输入需要优化的文本：",
            height=300,
            placeholder="在此输入你想要优化的文本..."
        )
    
    with col2:
        st.markdown("### 优化参数设置")
        optimization_type = st.selectbox(
            "优化类型",
            ["论文优化", "文案优化", "报告优化"],
            help="选择不同的优化类型会采用不同的优化策略"
        )
        
        style_level = st.slider(
            "文风调整程度",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.1,
            help="数值越大，改写程度越大"
        )
        
        advanced_options = st.expander("高级选项")
        with advanced_options:
            keep_keywords = st.text_input(
                "保留关键词",
                placeholder="多个关键词用逗号分隔",
                help="这些关键词在优化时会被保留"
            )
            
            special_requirements = st.text_area(
                "特殊要求",
                placeholder="输入任何特殊的优化要求...",
                height=100
            )
    
    # 开始按钮
    if st.button("开始优化", type="primary"):
        if not user_input:
            st.warning("请先输入文本")
            return
            
        # 显示对比结果
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 原文")
            st.markdown(user_input)
            
        with col2:
            with st.spinner("正在优化中..."):
                # 调用优化函数
                optimized_text = optimize_text_with_params(
                    text=user_input,
                    opt_type=optimization_type,
                    style_level=style_level,
                    keywords=keep_keywords.split(",") if keep_keywords else [],
                    special_reqs=special_requirements
                )
                st.write_stream(optimized_text)

if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
else:
    main()
