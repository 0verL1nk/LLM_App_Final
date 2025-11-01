import json
import time
import streamlit as st
from streamlit_echarts import st_pyecharts
from pyecharts import options as opts
from pyecharts.charts import Tree
from utils import (
    is_token_expired, 
    delete_content_by_uid,
    show_sidebar_api_key_setting
)
from utils.page_helpers import (
    check_api_key_configured,
    check_task_and_content,
    start_async_task,
    display_task_status
)
from utils.tasks import task_generate_mindmap

# 设置页面布局为宽屏模式
st.set_page_config(
    page_title="思维导图",
    page_icon="",
    layout="wide"  # 使用宽屏模式
)

st.title('思维导图')

# 显示侧边栏 API Key 设置
show_sidebar_api_key_setting()

def create_mindmap(data):
    """创建思维导图"""
    tree = (
        Tree()
        .add(
            
            series_name="",
            data=[data],
            orient="LR",
            initial_tree_depth=3,
            layout="orthogonal",
            pos_left="3%",      # 设置左边距
            # pos_right="15%",    # 设置右边距
            width="65%",        # 控制图表宽度
            height="86%",    # 控制图表高度
            edge_fork_position="10%",  # 让分叉点靠近父节点
            symbol_size=7,      # 节点大小
            label_opts=opts.LabelOpts(
                position="right",
                horizontal_align="left",
                vertical_align="middle",
                font_size=14,
                padding=[0, 0, 0, -20],
            ),
            
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title="文献思维导图"),
            tooltip_opts=opts.TooltipOpts(trigger="item", trigger_on="mousemove"),
            toolbox_opts=opts.ToolboxOpts(
                is_show=True,
                pos_left="right",
                feature={
                    "zoom": {"is_show": True},
                    "restore": {"is_show": True},
                }
            )
        )
    )
    return tree

def main():
    # 检查API key
    is_configured, error_msg = check_api_key_configured()
    if not is_configured:
        st.warning(f'⚠️ {error_msg}')
        st.info('💡 请在左侧边栏的"设置"中配置您的 API Key 后刷新页面。')
        return
    
    if not st.session_state.files:
        st.write('### 还没上传文档哦')
        return

    # 操作区域（上方）
    selected_doc = st.selectbox(
        "选择文档",
        options=[file['file_name'] for file in st.session_state.files],
        key="selected_doc"
    )
    
    with st.sidebar:
        if st.button('重新生成', type="primary"):
            doc = next((doc for doc in st.session_state.files if doc['file_name'] == selected_doc), None)
            if doc:
                delete_content_by_uid(doc['uid'], 'file_mindmap')
                # 清除相关任务状态
                from utils.task_queue import get_task_status_by_uid, update_task_status, TaskStatus
                task_info = get_task_status_by_uid(doc['uid'], 'file_mindmap')
                if task_info:
                    update_task_status(task_info['task_id'], TaskStatus.FAILED, error_message="用户取消")
                st.rerun()
    
    # 思维导图展示区域（下方）
    st.write("---")  # 添加分隔线
    document = next((doc for doc in st.session_state.files if doc['file_name'] == selected_doc), None)
    if document:
        # 检查内容和任务状态
        content_dict, task_status, task_id = check_task_and_content(
            document['uid'], 
            'file_mindmap',
            auto_start=True
        )
        
        if content_dict:
            # 已有内容，直接显示
            if isinstance(content_dict, dict) and 'raw' not in content_dict:
                mindmap_data = content_dict
            else:
                mindmap_data = json.loads(content_dict.get('raw', '{}'))
            tree = create_mindmap(mindmap_data)
            st_pyecharts(
                tree,
                height="850px",
                width="120%",
                key=f"mindmap_{document['uid']}"
            )
        elif task_status:
            # 有任务在进行中
            from utils.task_queue import get_task_status
            task_info = get_task_status(task_id) if task_id else None
            error_msg = task_info.get('error_message') if task_info else None
            display_task_status(task_status, error_msg)
            
            # 如果任务完成，自动刷新显示内容
            if task_status == 'finished':
                st.rerun()
        else:
            # 没有内容也没有任务，启动新任务
            st.info('🚀 开始生成思维导图，这可能需要一些时间...')
            task_id = start_async_task(
                document['uid'],
                'file_mindmap',
                task_generate_mindmap,
                document['file_path'],
                document['uid']
            )
            
            if task_id:
                st.info('📋 任务已提交，正在处理中...')
                time.sleep(1)
                st.rerun()
            else:
                st.error('❌ 启动任务失败，请检查配置后重试')

if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
else:
    main()