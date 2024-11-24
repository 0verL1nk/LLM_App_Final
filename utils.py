import json
import sqlite3
import logging
import os
from datetime import datetime
import textract
from openai import OpenAI
import streamlit as st

# init client
client = OpenAI(
    # 为了方便,先不设置环境变量
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
)
model_name = 'qwen-max'


def init_database(db_name: str) -> \
        (sqlite3.Connection, sqlite3.Cursor):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    # 创建表格存储文件信息（如果不存在）
    # 保存的文件名以随机uid重新命名
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_filename TEXT NOT NULL,
        uid TEXT NOT NULL,
        md5 TEXT NOT NULL,
        file_path TEXT NOT NULL
    )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contents (
            uid TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_extraction TEXT
        )
        """)
    conn.commit()
    return conn, cursor


def print_contents(content):
    for key, value in content.items():
        st.write('### ' + key + '\n')
        for i in value:
            st.write('- ' + i + '\n')


def save_content_to_database(uid: str,
                             file_path: str,
                             content: str,
                             content_type: str,
                             db_name='./database.sqlite', ):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(f"""
           INSERT INTO contents (uid, file_path, {content_type})
           VALUES (?, ?, ?)
           """, (uid, file_path, content))
    conn.commit()


def get_uid_by_md5(md5_value: str,
                   db_name='./database.sqlite'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT uid FROM files WHERE md5=?", (md5_value,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return None


def get_content_by_uid(uid: str,
                       content_type: str,
                       table_name='contents',
                       db_name='./database.sqlite'):
    """
    根据文件名获取文件的内容

    Args:
        uid (str): uid

    Returns:
        str: 文件内容，若未找到则返回 None
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(f"SELECT {content_type} FROM {table_name} WHERE uid = ?", (uid,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return None


def check_file_exists(md5: str,
                      db_name='./database.sqlite'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    """根据 MD5 值检查文件是否存在"""
    cursor.execute("SELECT 1 FROM files WHERE md5 = ?", (md5,))
    result = cursor.fetchone()
    return result is not None


def save_file_to_database(conn: sqlite3.Connection,
                          cursor: sqlite3.Cursor,
                          original_file_name: str,
                          uid: str,
                          md5_value: str,
                          full_file_path: str):
    # 插入文件信息到数据库
    cursor.execute("""
       INSERT INTO files (original_filename, uid,md5, file_path)
       VALUES (?, ?, ?,?)
       """, (original_file_name, uid, md5_value, full_file_path))
    conn.commit()


# Return a dict including result and text,judge the result,1:success,-1:failed.
def extract_files(file_path: str):
    file_type = file_path.split('.')[-1]
    if file_type in ['doc', 'docx', 'pdf', 'txt']:
        try:
            text = textract.process(file_path)
            return {'result': 1, 'text': text.decode('utf-8')}
        except Exception as e:
            print(e)
            return {'result': -1, 'text': e}
    else:
        return {'result': -1, 'text': 'Unexpect file type!'}


class LoggerManager:
    def __init__(self, log_dir="logs", log_level=logging.INFO):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_dir = os.path.join(base_dir, "logs")
        self.log_level = log_level
        os.makedirs(self.log_dir, exist_ok=True)

        # 动态生成日志文件名（按日期）
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"{current_date}.log")

        # 配置日志记录器
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(self.log_level)

        # 检查是否已添加处理器，避免重复
        if not self.logger.handlers:
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

            # 文件处理器
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

            # 控制台处理器（可选）
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    def get_logger(self):
        return self.logger


def text_extraction(file_path: str):
    res = extract_files(file_path)
    if res['result'] == 1:
        file_content = '以下为一篇论文的原文:\n' + res['text']
    else:
        return False,''
    messages = [
        {
            "role": "system",
            "content": file_content,  # <-- 这里，我们将抽取后的文件内容（注意是文件内容，而不是文件 ID）放置在请求中
        },
        {"role": "user",
         "content": '''
         阅读论文,划出**关键语句**,并按照“研究背景，研究目的，研究方法，研究结果，未来展望”五个标签分类.
         label为中文,text为原文,text可能有多句,并以json格式输出.
         注意!!text内是论文原文!!.
         以下为示例:
         {'label1':['text',...],'label2':['text',...],...}
         '''
         },
    ]

    completion = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    # 这边返回的就是json对象了
    return True, json.loads(completion.choices[0].message.content)
