import datetime
import hashlib
import os
import uuid

import pandas as pd
import streamlit as st
from streamlit_extras.row import row
from utils import LoggerManager, init_database, \
    save_file_to_database, check_file_exists, \
    get_uid_by_md5, is_token_expired, login, register, \
    get_uuid_by_token, get_user_files


# 计算文件 MD5
def calculate_md5(file):
    md5_hash = hashlib.md5()
    # 读取文件内容进行 MD5 计算
    for chunk in iter(lambda: file.read(4096), b""):
        md5_hash.update(chunk)
    return md5_hash.hexdigest()


def upload_file():
    uploaded_file = st.file_uploader('请上传文档:', type=['txt', 'doc', 'docx', 'pdf'])
    if uploaded_file is not None:
        # 计算md5
        md5_value = calculate_md5(uploaded_file)
        # 生成随机uid作为新文件名,若重复,则沿用
        if not check_file_exists(md5_value):
            uid = str(uuid.uuid4())
        else:
            uid = get_uid_by_md5(md5_value)
        # 获取文件名和文件后缀,保存文件
        original_filename = uploaded_file.name
        file_extension = os.path.splitext(original_filename)[-1]
        file_name = os.path.splitext(original_filename)[0]
        saved_filename = f"{uid}{file_extension}"
        file_path = os.path.join(save_dir, saved_filename)
        # 将文件保存到本地
        if not check_file_exists(file_path):
            uploaded_file.seek(0)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
        # 保存到数据库,这里的filename都是带后缀的,后续还会带用户id
        # 获取当前时间
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_file_to_database(original_filename,
                              uid,
                              st.session_state['uuid'],
                              md5_value,
                              file_path,
                              current_time)
        st.toast("文档上传成功", icon="👌")
        Logger.info(f'uploaded file: {original_filename}')
        # 添加path到session
        st.session_state['files'].append({'file_path': file_path,
                                          'file_name': file_name,
                                          'uid': uid,
                                          'created_at': current_time
                                          })


def load_files():
    files = get_user_files(st.session_state['uuid'])
    st.session_state['files'] = []
    for file in files:
        st.session_state['files'].append({'file_path': file[4],
                                          'file_name': file[1],
                                          'uid': file[2],
                                          'created_at': file[6]
                                          })


def print_file_list():
    file_table = {
        '文件名': [],
        '创建时间': []
    }
    for file in st.session_state['files']:
        file_table['文件名'].append(file['file_name'])
        file_table['创建时间'].append(file['created_at'])
    df = pd.DataFrame(file_table)
    rows = row(1)
    rows.dataframe(df, use_container_width=True)


def main():
    if 'files' not in st.session_state:
        st.session_state['files'] = []
    upload_file()
    load_files()
    if st.session_state['files']:
        print_file_list()


def user_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input('输入用户名:')
        password = st.text_input('输入密码:', type='password')
    button_rows = row([1, 1, 1, 1], vertical_align="center")
    button_rows.write("")
    if button_rows.button('登录', use_container_width=True):
        result, token, error = login(username, password)
        if not result:
            st.error(error)
        else:
            st.toast('✅登陆成功')
            st.session_state['token'] = token
            st.rerun()

    if button_rows.button('注册', use_container_width=True):
        st.session_state['LoginOrRegister'] = 'register'
        st.rerun()


def user_register():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input('输入用户名:')
        password = st.text_input('输入密码:', type='password')
        re_password = st.text_input('再次输入密码:', type='password')
    bt_rows = row([1, 1, 1, 1], vertical_align="center")
    bt_rows.write("")
    if bt_rows.button('返回登录', use_container_width=True):
        st.session_state['LoginOrRegister'] = 'login'
        st.rerun()
    if bt_rows.button('注册', use_container_width=True):
        if password != re_password:
            st.error('两次密码不一致')
        else:
            result, token, error = register(username, password)
            if not result:
                st.error(error)
            else:
                st.success('登陆成功')
                st.session_state['token'] = token
                st.session_state['LoginOrRegister'] = 'login'
                st.rerun()


# init
base_dir = os.path.dirname(os.path.abspath(__file__))
save_dir = os.path.join(base_dir, "uploads")
os.makedirs(save_dir, exist_ok=True)  # 创建 uploads 目录（如果不存在）
Logger = LoggerManager().get_logger()
# init database
init_database('./database.sqlite')

# 标题
# 使用自定义 CSS 来居中标题
st.markdown("""
    <style>
        .title {
            text-align: center;
        }
        .center-button {
            display: flex;
            justify-content: center;
            align-items: center;
        }
    </style>
""", unsafe_allow_html=True)
# 使用 CSS 类来设置标题

# session data
if 'token' not in st.session_state:
    st.session_state['token'] = ''
if 'LoginOrRegister' not in st.session_state:
    st.session_state['LoginOrRegister'] = 'login'
if 'uuid' not in st.session_state:
    st.session_state['uuid'] = ''
# TODO
# 输入用户名密码,加载文件列表

if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    if st.session_state['LoginOrRegister'] == 'login':
        st.markdown('<h2 class="title">🤗 登录</h2>', unsafe_allow_html=True)
        user_login()
    else:
        st.markdown('<h2 class="title">😊 注册</h2>', unsafe_allow_html=True)
        user_register()
else:
    st.title('文档阅读助手')
    st.session_state['uuid'] = get_uuid_by_token(st.session_state['token'])
    main()
