import streamlit as st

from utils import is_token_expired, process_multy_optimization

st.set_page_config(page_title="文段改写", page_icon="✒️", layout="wide")

def main():

    st.title("✒️ 文段改写")
    
    # 创建两列布局
    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.container():
            user_input = st.text_area(
                "请输入需要优化的文本：",
                height=300,
                placeholder="在此输入你想要优化的文本...",
                help="支持中英文文本优化，建议输入100-1000字的文本"
            )
    
    with col2:
        with st.container():
            st.markdown("### 优化参数设置")
            
            # 基础设置
            optimization_type = st.selectbox(
                "优化类型",
                ["论文优化", "文案优化", "报告优化", "通用优化"],
                help="选择不同的优化类型会采用不同的优化策略和专业术语"
            )
            
            optimization_steps = st.multiselect(
                "优化步骤",
                options=["表达优化", "专业优化", "降重处理", "智能翻译"],
                default=["表达优化", "专业优化", "降重处理"],
                help="选择需要执行的优化步骤：\n- 表达优化：改善文本流畅度\n- 专业优化：提升专业性\n- 降重处理：降低重复率\n- 智能翻译：中英互译"
            )
            
            temperature = st.slider(
                "调整程度",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.1,
                help="数值越小生成的文本越稳定保守,数值越大生成的文本越有创意多样。建议从小到大逐步尝试"
            )
            
            # 高级选项
            advanced_options = st.expander("高级选项")
            with advanced_options:
                keep_keywords = st.text_input(
                    "保留关键词",
                    placeholder="多个关键词用逗号分隔",
                    help="这些关键词在优化过程中会被保留"
                )
                
                special_requirements = st.text_area(
                    "特殊要求",
                    placeholder="输入任何特殊的优化要求...",
                    height=100,
                    help="例如：'保持学术性'、'使用更简单的表达'等"
                )
                
                show_thought_process = st.checkbox(
                    "显示思考过程",
                    value=True,
                    help="展示Agent每一轮的思考过程和决策原因"
                )

    if st.button("开始优化", type="primary", use_container_width=True):
        if not user_input:
            st.warning("⚠️ 请先输入需要优化的文本")
            return
        
        if len(user_input) < 10:
            st.warning("⚠️ 文本太短，建议输入更多内容以获得更好的优化效果")
            return
            
        # 创建结果展示区
        st.markdown("---")
        result_cols = st.columns(2)
        
        with result_cols[0]:
            st.markdown("### 📝 原文")
            st.write(user_input)
            
        with result_cols[1]:
            st.markdown("### ✨ 优化结果")
            
            # 创建进度展示
            progress_container = st.empty()
            progress_bar = st.progress(0)
            current_result = st.empty()
            progress_container.markdown("""
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <h4>🔄 优化进度：第 """+str(0)+"/"+str(len(optimization_steps))+""" 步</h4>
                            <div class="spinner"></div>
                        </div>
                        
                        <style>
                            .spinner {
                                width: 20px;
                                height: 20px;
                                border: 3px solid #f3f3f3;
                                border-top: 3px solid #3498db;
                                border-radius: 50%;
                                animation: spin 1s linear infinite;
                            }
                            
                            @keyframes spin {
                                0% { transform: rotate(0deg); }
                                100% { transform: rotate(360deg); }
                            }
                        </style>
                    """, unsafe_allow_html=True)
            try:
                # 使用Agent进行优化
                for i, (thought, result) in enumerate(process_multy_optimization(
                    text=user_input,
                    opt_type=optimization_type,
                    temperature=temperature,
                    optimization_steps=optimization_steps,
                    keywords=keep_keywords.split(",") if keep_keywords else [],
                    special_reqs=special_requirements
                )):
                    # 更新进度
                    progress = (i + 1) / len(optimization_steps)
                    progress_bar.progress(progress)
                    progress_container.markdown("""
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <h4>🔄 优化进度：第 """+str((i+1))+"/"+str(len(optimization_steps))+""" 步</h4>
                            <div class="spinner"></div>
                        </div>
                        
                        <style>
                            .spinner {
                                width: 20px;
                                height: 20px;
                                border: 3px solid #f3f3f3;
                                border-top: 3px solid #3498db;
                                border-radius: 50%;
                                animation: spin 1s linear infinite;
                            }
                            
                            @keyframes spin {
                                0% { transform: rotate(0deg); }
                                100% { transform: rotate(360deg); }
                            }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    # 显示思考过程
                    if show_thought_process:
                        st.markdown(f"""
                        <div style='background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0;'>
                            <div style='font-weight: bold; margin-bottom: 0.5rem;'>
                                🤔 思考过程 - 第 {i+1} 轮
                            </div>
                            <div style='color: #555; font-size: 0.95em;'>
                                {thought}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # 更新当前结果
                    current_result.write(result)
                
                # 完成提示
                progress_bar.empty()
                progress_container.empty()
                st.toast("✅ 优化完成！")
                
            except Exception as e:
                st.error(f"优化过程中出现错误: {str(e)}")
                progress_container.error("❌ 优化失败")

if (not st.session_state.get('token')) or is_token_expired(st.session_state.get('token')):
    st.error('还没登录哦')
else:
    main()
