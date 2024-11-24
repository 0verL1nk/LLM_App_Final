import hashlib
import os
import uuid
import streamlit as st
from utils import LoggerManager, init_database, \
    save_file_to_database, check_file_exists, \
    get_uid_by_md5

# init
base_dir = os.path.dirname(os.path.abspath(__file__))
save_dir = os.path.join(base_dir, "uploads")
os.makedirs(save_dir, exist_ok=True)  # 创建 uploads 目录（如果不存在）
Logger = LoggerManager().get_logger()


# 计算文件 MD5
def calculate_md5(file):
    md5_hash = hashlib.md5()
    # 读取文件内容进行 MD5 计算
    for chunk in iter(lambda: file.read(4096), b""):
        md5_hash.update(chunk)
    return md5_hash.hexdigest()


# init database
conn, cursor = init_database('./database.sqlite')
# TODO
# 输入用户名密码,加载文件列表
# 标题
st.title('文档阅读助手')
if 'files' not in st.session_state:
    st.session_state['files'] = []
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
    save_file_to_database(conn, cursor, original_filename, uid, md5_value, file_path)
    st.toast("文档上传成功", icon="👌")
    Logger.info(f'uploaded file: {original_filename}')
    # 添加path到session
    st.session_state['files'].append({'file_path': file_path,
                                      'file_name': file_name,
                                      'uid': uid,
                                      })
