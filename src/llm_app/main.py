"""
Main application entry point for the LLM App.

This module serves as the central entry point for the Streamlit application.
"""

import streamlit as st
from streamlit_extras.row import row

from .config import Config
from .core.database import DatabaseManager
from .core.auth import AuthManager
from .core.file_handler import FileHandler
from .core.logger import LoggerManager
from .core.text_processor import TextProcessor
from .core.optimizer import TextOptimizer


def initialize_session_state() -> None:
    """Initialize Streamlit session state variables."""
    if "token" not in st.session_state:
        st.session_state["token"] = None
    if "uuid" not in st.session_state:
        st.session_state["uuid"] = None
    if "files" not in st.session_state:
        st.session_state["files"] = []


def show_sidebar_settings() -> None:
    """Display sidebar settings for API key and model configuration."""
    with st.sidebar:
        st.header("⚙️ 设置")

        # API Key configuration
        if st.session_state.get("uuid"):
            db = DatabaseManager()
            api_key = db.get_user_api_key(st.session_state["uuid"])

            if not api_key:
                st.warning("请配置您的 API Key")
                new_api_key = st.text_input(
                    "DashScope API Key", type="password", key="api_key_input"
                )
                if st.button("保存 API Key"):
                    if new_api_key:
                        db.update_user_api_key(st.session_state["uuid"], new_api_key)
                        st.success("API Key 保存成功!")
                        st.rerun()
                    else:
                        st.error("请输入有效的 API Key")
            else:
                st.success("✅ API Key 已配置")

            # Model selection
            current_model = db.get_user_model_name(st.session_state["uuid"])
            new_model = st.selectbox(
                "选择模型",
                options=["qwen-max", "qwen-plus", "qwen-turbo"],
                index=["qwen-max", "qwen-plus", "qwen-turbo"].index(current_model),
                key="model_selector",
            )

            if new_model != current_model:
                # Update model preference in database
                import sqlite3

                conn = sqlite3.connect(Config.DATABASE_PATH)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET model_name = ? WHERE uuid = ?",
                    (new_model, st.session_state["uuid"]),
                )
                conn.commit()
                conn.close()
                st.rerun()


def upload_file_section(file_handler: FileHandler) -> None:
    """Display file upload section.

    Args:
        file_handler: File handler instance
    """
    st.subheader("📁 上传文档")

    uploaded_file = st.file_uploader(
        "请上传文档:", type=["txt", "doc", "docx", "pdf"], key="file_uploader"
    )

    if uploaded_file is not None:
        success, message, file_info = file_handler.process_uploaded_file(
            uploaded_file, st.session_state["uuid"]
        )

        if success:
            st.toast(message, icon="👌")
            LoggerManager.log_user_action(
                st.session_state["uuid"], "file_upload", f"File: {uploaded_file.name}"
            )

            # Add to session state
            st.session_state["files"].append(file_info)
            st.rerun()
        else:
            st.error(message)


def display_file_list() -> None:
    """Display list of uploaded files."""
    st.subheader("📄 文档列表")

    if st.session_state["files"]:
        file_table = {
            "文件名": [f["file_name"] for f in st.session_state["files"]],
            "创建时间": [f["created_at"] for f in st.session_state["files"]],
        }

        import pandas as pd

        df = pd.DataFrame(file_table)
        rows = row(1)
        rows.table(df)
    else:
        st.info("暂无上传文档")


def user_login() -> bool:
    """Display and handle user login form.

    Returns:
        True if user is logged in, False otherwise
    """
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 用户登录")

        with st.form("login_form"):
            username = st.text_input("用户名", key="login_username")
            password = st.text_input("密码", type="password", key="login_password")
            submit_button = st.form_submit_button("登录")

            if submit_button:
                auth = AuthManager()
                success, token, error = auth.login(username, password)

                if success:
                    st.session_state["token"] = token
                    st.session_state["uuid"] = auth.get_uuid_by_token(token)

                    LoggerManager.log_user_action(
                        st.session_state["uuid"], "login", f"User: {username}"
                    )

                    st.success("登录成功!")
                    st.rerun()
                else:
                    st.error(error)

        st.markdown("---")
        st.write("还没有账号？")

        with st.form("register_form"):
            st.subheader("📝 用户注册")
            new_username = st.text_input("新用户名", key="reg_username")
            new_password = st.text_input("新密码", type="password", key="reg_password")
            register_button = st.form_submit_button("注册")

            if register_button:
                auth = AuthManager()
                success, token, error = auth.register(new_username, new_password)

                if success:
                    st.session_state["token"] = token
                    st.session_state["uuid"] = auth.get_uuid_by_token(token)

                    LoggerManager.log_user_action(
                        st.session_state["uuid"], "register", f"User: {new_username}"
                    )

                    st.success("注册成功并自动登录!")
                    st.rerun()
                else:
                    st.error(error)

    return False


def main() -> None:
    """Main application function."""
    # Configure page
    st.set_page_config(page_title="文献阅读助手", page_icon="📚", layout="wide")

    # Initialize session state
    initialize_session_state()

    # Check authentication
    auth = AuthManager()
    is_logged_in = st.session_state.get("token") and auth.is_token_valid(
        st.session_state["token"]
    )

    if not is_logged_in:
        user_login()
        return

    # Initialize components
    db = DatabaseManager()
    file_handler = FileHandler(db)
    text_processor = TextProcessor(db, file_handler)
    optimizer = TextOptimizer(db)

    # Configure LLM client if API key is set
    api_key = db.get_user_api_key(st.session_state["uuid"])
    if api_key:
        from .api.llm_client import LLMClient

        model_name = db.get_user_model_name(st.session_state["uuid"])
        llm_client = LLMClient(api_key, model_name)
        text_processor.set_llm_client(llm_client)
        optimizer.set_llm_client(llm_client)

    # Main UI
    st.title("📚 文献阅读助手")

    # Sidebar settings
    show_sidebar_settings()

    # Main content
    upload_file_section(file_handler)

    # Display files
    display_file_list()


if __name__ == "__main__":
    # Initialize database
    Config.ensure_directories()
    LoggerManager().get_logger(__name__)

    # Run main application
    main()
