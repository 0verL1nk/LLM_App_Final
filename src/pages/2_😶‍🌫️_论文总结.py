import time
import streamlit as st

from utils import is_token_expired, show_sidebar_api_key_setting
from utils.page_helpers import (
    check_api_key_configured,
    check_task_and_content,
    start_async_task,
    display_task_status,
)
from utils.tasks import task_file_summary

st.title("😶‍🌫️论文总结")

# 显示侧边栏 API Key 设置
show_sidebar_api_key_setting()


def main():
    # 检查API key
    is_configured, error_msg = check_api_key_configured()
    if not is_configured:
        st.warning(f"⚠️ {error_msg}")
        st.info('💡 请在左侧边栏的"设置"中配置您的 API Key 后刷新页面。')
        return

    if not st.session_state.files:
        st.write("### 还没上传文档哦")
    else:
        tabs = st.tabs([item["file_name"] for item in st.session_state.files])
        for index, item in enumerate(st.session_state.files):
            with tabs[index]:
                st.write("## " + item["file_name"] + "\n")

                # 检查内容和任务状态
                content_dict, task_status, task_id = check_task_and_content(
                    item["uid"], "file_summary", auto_start=True
                )

                if content_dict:
                    # 已有内容，直接显示
                    st.markdown("### 总结如下：")
                    st.write(content_dict.get("summary", content_dict))
                elif task_status:
                    # 有任务在进行中
                    from utils.task_queue import get_task_status

                    task_info = get_task_status(task_id) if task_id else None
                    error_msg = task_info.get("error_message") if task_info else None
                    display_task_status(task_status, error_msg)

                    # 如果任务完成，自动刷新显示内容
                    if task_status == "finished":
                        st.rerun()
                else:
                    # 没有内容也没有任务，启动新任务
                    st.info("🚀 开始生成总结，这可能需要一些时间...")
                    task_id = start_async_task(
                        item["uid"],
                        "file_summary",
                        task_file_summary,
                        item["file_path"],
                        item["uid"],
                    )

                    if task_id:
                        st.info("📋 任务已提交，正在处理中...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 启动任务失败，请检查配置后重试")


if (not st.session_state["token"]) or is_token_expired(st.session_state["token"]):
    st.error("还没登录哦")
else:
    main()
