import datetime
import hashlib
import json
import logging
import os
import random
import sqlite3
import string
import uuid
from typing import List, Tuple

import redis
import streamlit as st
import textract
from openai import OpenAI

# init client
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
)
model_name = 'qwen-max'
pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True)
rdb = redis.Redis(connection_pool=pool)


def init_database(db_name: str):
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
        file_path TEXT NOT NULL,
        uuid TEXT NOT NULL,
        created_at TEXT
    )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contents (
            uid TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_extraction TEXT,
            file_mindmap TEXT,
            file_summary TEXT
        )
        """)
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                uuid TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                api_key TEXT DEFAULT NULL
            )
            """)
    conn.commit()
    conn.close()


def get_user_files(uuid_value: str, db_name='./database.sqlite') -> list:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    # 执行查询，获取符合 uuid 的所有数据
    cursor.execute("SELECT * FROM files WHERE uuid = ?", (uuid_value,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def gen_random_str(length: int) -> str:
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))


def gen_uuid() -> str:
    return str(uuid.uuid4())


def save_token(user_id: str) -> str:
    # ttl;1天
    token = gen_random_str(32)
    rdb.setex(token, 60 * 60 * 24, user_id)
    return token


# 若成功,返回true,uuid,'',依次为result,token,error
def login(username: str, password: str, db_name='./database.sqlite') -> \
        Tuple[bool, str, str]:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    # 校验用户名是否存在
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    if (not user) or hashlib.sha256(password.encode('utf-8')).hexdigest() != user[2]:
        return False, '', '账号密码错误'
    return True, save_token(user[0]), ''

    # 若成功,返回true,uuid,'',依次为result,token,error


def register(username: str, password: str, db_name='./database.sqlite') -> Tuple[bool, str, str]:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    if cursor.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone():
        conn.close()
        return False, '', '用户名已存在'
    uid = gen_uuid()
    cursor.execute(f"""
           INSERT INTO users (uuid, username, password)
           VALUES (?, ?, ?)
           """, (uid, username, hashlib.sha256(password.encode('utf-8')).hexdigest()))
    conn.commit()
    conn.close()
    return True, save_token(uid), ''


def is_token_expired(token):
    # 检查 Token 是否在 Redis 中存在
    if not rdb.exists(token):
        return True  # 如果 Token 不存在，认为它已经过期或无效

    # 获取 Token 的剩余有效时间
    ttl = rdb.ttl(token)

    if ttl == -2:
        return True  # 如果 Token 不存在，返回过期
    elif ttl == -1:
        return False  # 如果没有设置过期时间，表示 token 永久有效
    else:
        return False  # 如果 TTL 大于 0，表示 Token 尚未过期


def print_contents(content):
    for key, value in content.items():
        st.write('### ' + key + '\n')
        for i in value:
            st.write('- ' + i + '\n')


def save_content_to_database(uid: str,
                           file_path: str,
                           content: str,
                           content_type: str,
                           db_name='./database.sqlite'):
    """保存内容到数据库，如果记录已存在则更新对应字段"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # 检查是否已存在记录
    cursor.execute("SELECT 1 FROM contents WHERE uid = ?", (uid,))
    exists = cursor.fetchone() is not None
    
    if exists:
        # 更新现有记录的特定字段
        cursor.execute(f"""
            UPDATE contents 
            SET {content_type} = ?
            WHERE uid = ?
        """, (content, uid))
    else:
        # 插入新记录
        cursor.execute(f"""
            INSERT INTO contents (uid, file_path, {content_type})
            VALUES (?, ?, ?)
        """, (uid, file_path, content))
    
    conn.commit()
    conn.close()

def get_uid_by_md5(md5_value: str,
                   db_name='./database.sqlite'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT uid FROM files WHERE md5=?", (md5_value,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    else:
        return None


def get_uuid_by_token(token: str) -> str:
    return rdb.get(token)


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
        :param uid:
        :param content_type:
        :param table_name:
        :param db_name:
        :param table_name:
        :param content_type:
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(f"SELECT {content_type} FROM {table_name} WHERE uid = ?", (uid,))
    result = cursor.fetchone()
    conn.close()
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
    conn.close()
    return result is not None


def save_file_to_database(original_file_name: str,
                          uid: str,
                          uuid_value: str,
                          md5_value: str,
                          full_file_path: str,
                          current_time: str,
                          ):
    conn = sqlite3.connect('./database.sqlite')
    cursor = conn.cursor()

    # 插入文件信息到数据库
    cursor.execute("""
       INSERT INTO files (original_filename, uid,md5, file_path,uuid,created_at)
       VALUES (?, ?, ?,?,?,?)
       """, (original_file_name, uid, md5_value, full_file_path, uuid_value, current_time))
    conn.commit()
    conn.close()


# Return a dict including result and text,judge the result,1:success,-1:failed.
def extract_files(file_path: str):
    file_type = file_path.split('.')[-1]
    if file_type in ['doc', 'docx', 'pdf', 'txt']:
        try:
            text = textract.process(file_path).decode('utf-8')
            # 替换'{'和'}'防止解析为变量
            safe_text=text.replace("{", "{{").replace("}", "}}")
            return {'result': 1, 'text': safe_text}
        except Exception as e:
            print(e)
            return {'result': -1, 'text': e}
    else:
        return {'result': -1, 'text': 'Unexpect file type!'}
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatTongyi
from langchain_core.output_parsers import StrOutputParser

def optimize_text(text: str):
    system_prompt = """你是一个专业的论文优化助手。你的任务是:
        1. 优化用户输入的文本，使其表达更加流畅、逻辑更加清晰
        2. 替换同义词和调整句式，以降低查重率
        3. 保证原文的核心意思不变
        4. 保证论文专业性,包括用词的专业性以及句式的专业性
        5. 使文本更加符合其语言的语法规范,更像母语者写出来的文章
        请按以下格式输出：
        #### 优化后的文本
        ...
        """
    llm = ChatTongyi(
            model_name="qwen-max",
            streaming=True
        )
    prompt_template = ChatPromptTemplate.from_messages([
        ('system',system_prompt),
        ('user','用户输入:'+text)
    ])
    chain = prompt_template | llm
    return chain.stream({'text':text})

def generate_mindmap_data(text: str)->dict:
    """生成思维导图数据"""
    system_prompt = """你是一个专业的文献分析专家。请分析给定的文献内容，生成一个结构清晰的思维导图。

    分析要求：
    1. 主题提取
       - 准确识别文档的核心主题作为根节点
       - 确保主题概括准确且简洁
    
    2. 结构设计
       - 第一层：识别文档的主要章节或核心概念（3-5个）
       - 第二层：提取每个主要章节下的关键要点（2-4个）
       - 第三层：补充具体的细节和示例（如果必要）
       - 最多不超过4层结构
    
    3. 内容处理
       - 使用简洁的关键词或短语
       - 每个节点内容控制在15字以内
       - 保持逻辑连贯性和层次关系
       - 确保专业术语的准确性
    
    4. 特殊注意
       - 研究类文献：突出研究背景、方法、结果、结论等关键环节
       - 综述类文献：强调研究现状、问题、趋势等主要方面
       - 技术类文献：注重技术原理、应用场景、优缺点等要素

    输出格式要求：
    必须是严格的JSON格式，不要有任何额外字符，结构如下：
    {{
        "name": "根节点名称",
        "children": [
            {{
                "name": "一级节点1",
                "children": [
                    {{
                        "name": "二级节点1",
                        "children": [...]
                    }}
                ]
            }}
        ]
    }}
    """
    
    llm = ChatTongyi(
        model_name="qwen-max"
    )
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "以下是需要分析的文献内容：\n {text}")
    ])
    
    chain = prompt_template | llm
    result = chain.invoke({"text": text})
    print(result.content)
    try:
        # 确保返回的是有效的JSON字符串
        json_str = extract_json_string(result.content)
        mindmap_data = json.loads(json_str)
        return mindmap_data
    except json.JSONDecodeError:
        # 如果��析失败，返回一个基本的结构
        return {
            "name": "解析失败",
            "children": [
                {
                    "name": "文档解析出错",
                    "children": []
                }
            ]
        }


class LoggerManager:
    def __init__(self, log_level=logging.INFO):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_dir = os.path.join(base_dir, "logs")
        self.log_level = log_level
        os.makedirs(self.log_dir, exist_ok=True)

        # 动态生成日志文件名（按日期）
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
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
        return False, ''
    messages = [
        {
            "role": "system",
            "content": file_content,  # <-- 这里，我们将抽取后的文件内容（注意是文件内容，不是文件 ID）放在请求中
        },
        {"role": "user",
         "content": '''
         阅读论文,划出**关键语句**,并按照"研究背景，研究目的，研究方法，研究结果，未来展望"五个标签分类.
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

def file_summary(file_path: str)->Tuple[bool,str]:
    res = extract_files(file_path)
    if res['result'] == 1:
        content = res['text']
    else:
        return False, ''
 
    system_prompt = """你是一个文书助手。你的客户会交给你一篇文章，你需要用尽可能简洁的语言，总结这篇文章的内容。不得使用 markdown 记号。"""

    llm = ChatTongyi(model_name="qwen-max", streaming=True)
    
    prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt),
             ("user", content)
            ])
    chain = prompt | llm | StrOutputParser()
    summary = chain.invoke({})
    st.markdown("### 总结如下：")
    st.text(summary)
    return True, summary
    


def delete_content_by_uid(uid: str, content_type: str, db_name='./database.sqlite'):
    """删除指定记录的特定内容类型
    
    Args:
        uid (str): 记录的唯一标识
        content_type (str): 要删除的内容类型 (如 'file_mindmap', 'file_extraction' 等)
        db_name (str): 数据库文件路径
    
    Returns:
        bool: 操作是否成功
    """
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        # 将指定字段设置为 NULL
        cursor.execute(f"""
            UPDATE contents 
            SET {content_type} = NULL
            WHERE uid = ?
        """, (uid,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"删除内容时出错: {e}")
        return False

def extract_json_string(text: str) -> str:
    """
    从字符串中提取有效的JSON部分
    Args:
        text: 包含JSON的字符串
    Returns:
        str: 提取出的JSON字符串
    """
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        return text[start:end + 1]
    return text


def detect_language(text: str) -> str:
    """
    检测文本语言类型
    返回 'zh' 表示中文，'en' 表示英文，'other' 表示其他语言
    """
    # 统计中文字符数量
    chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
    # 统计英文字符数量
    english_chars = len([c for c in text if c.isascii() and c.isalpha()])
    
    # 计算中英文字符占比
    total_chars = len(text.strip())
    chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
    english_ratio = english_chars / total_chars if total_chars > 0 else 0
    
    # 判断语言类型
    if chinese_ratio > 0.3:  # 如果中文字符占比超过30%，认为是中文文本
        return 'zh'
    elif english_ratio > 0.5:  # 如果英文字符占比超过50%，认为是英文文本
        return 'en'
    else:
        return 'other'

def translate_text(text: str, temperature: float, model_name: str, optimization_history: list) -> str:
    """智能翻译的具体实现"""
    llm = ChatTongyi(
        model_name=model_name,
        streaming=True
    )
    
    # 检测源语言
    source_lang = detect_language(text)
    target_lang = 'en' if source_lang == 'zh' else 'zh'
    
    prompt = f"""请将以下文本从{'中文' if source_lang == 'zh' else '英文'}翻译成{'英文' if target_lang == 'en' else '中文'}。
优化历史:
{optimization_history}
原文：{text}

要求：
1. 保持专业术语的准确性
2. 确保译文流畅自然
3. 保持原文的语气和风格
4. 适当本地化表达方式
5. 注意上下文连贯性

注意!!警告!!提示!!返回要求:只返回翻译后的文本,不要有多余解释,不要有多余的话.
"""
    response = llm.invoke(prompt, temperature=temperature)
    return response.content

def process_multy_optimization(
    text: str,
    opt_type: str,
    temperature: float,
    optimization_steps: list,
    keywords: list,
    special_reqs: str
) -> List[Tuple[str, str]]:
    """
    根据选择的优化步骤进行处理，并记录优化历史
    """
    current_text = text
    model_name = "qwen-max" if detect_language(text) == 'zh' else "llama3.1-405b-instruct"
    
    step_functions = {
        "表达优化": (optimize_expression, "分析：需要改善文本的基础表达方式，使其更加流畅自然。"),
        "专业优化": (professionalize_text, "分析：需要优化专业术语，提升文本的学术性。"),
        "降重处理": (reduce_similarity, "分析：需要通过同义词替换和句式重组降低重复率。"),
        "智能翻译": (translate_text, "分析：需要进行中英互译转换。")
    }
    
    optimization_history = []
    
    for step in optimization_steps:
        try:
            func, thought = step_functions[step]
            
            # 添加优化参数信息到思考过程
            thought += f"\n优化类型：{opt_type}"
            thought += f"\n调整程度：{temperature}"
            if keywords:
                thought += f"\n保留关键词：{', '.join(keywords)}"
            if special_reqs:
                thought += f"\n特殊要求：{special_reqs}"
            
            # 记录当前步骤的优化历史
            history = {
                "step": step,
                "before": current_text,
                "parameters": {
                    "optimization_type": opt_type,
                    "temperature": temperature,
                    "keywords": keywords,
                    "special_requirements": special_reqs
                }
            }
            
            # 执行优化
            current_text = func(current_text, temperature, model_name,optimization_history)
            
            # 更新历史记录
            history["after"] = current_text
            optimization_history.append(history)
            
            yield thought, current_text
            
        except Exception as e:
            print(f"Error in step {step}: {str(e)}")
            yield f"优化过程中出现错误: {str(e)}", current_text

def optimize_expression(text: str,temperature: float,model_name: str,optimization_history: list) -> str:
    """改善表达的具体实现"""
    llm = ChatTongyi(
        model_name=model_name,
        streaming=True
    )
    
    prompt = f"""请改善以下文本的表达方式，使其更加流畅自然,重要提示：**必须使用与原文相同的语言进行回复！中文或英文或其他语言**
优化历史:
{optimization_history}
原文：{text}

要求：
1. 必须使用与原文完全相同的语言
2. 调整句式使表达更流畅
3. 优化用词使其更自然
4. 保持原有意思不变
5. 确保逻辑连贯性

注意!!警告!!提示!!返回要求:只返回降重后的文本,不要有多余解释,不要有多余的话.
"""
    response = llm.invoke(prompt,temperature=temperature)
    return response.content

def professionalize_text(text: str,temperature: float,model_name: str,optimization_history: list) -> str:
    """专业化处理的具体实现"""
    llm = ChatTongyi(
        model_name=model_name,
        streaming=True,
    )
    
    prompt = f"""请对以下文本进行专业化处理，优化适当的专业术语和学术表达,重要提示：**必须使用与原文相同的语言进行回复！中文或英文或其它语言**
优化历史:
{optimization_history}
原文：{text}

要求：
1. 必须使用与原文完全相同的语言
2. 优化合适的专业术语
3. 使用更学术的表达方式
4. 保持准确性和可读性
5. 确保专业性和权威性

注意!!警告!!提示!!返回要求:只返回降重后的文本,不要有多余解释,不要有多余的话.
"""
    response = llm.invoke(prompt,temperature=temperature)
    return response.content

def reduce_similarity(text: str,temperature: float,model_name: str,optimization_history: list) -> str:
    """降重处理的具体实现"""
    llm = ChatTongyi(
        model_name=model_name,
        streaming=True
    )
    
    prompt = f"""请对以下原文的内容进行降重处理，通过同义词替换和句式重组等方式降低重复率,重要提示：**必须使用与原文相同的语言进行回复！中文或英文或其它语言**
优化历史:
{optimization_history}
**原文**：{text}
--原文结束--
要求：
1. 必须使用与原文完全相同的语言
2. 使用同义词替换
3. 调整句式结构
4. 保持原意不变
5. 确保文本通顺

注意!!警告!!提示!!返回要求:只返回降重后的文本,不要有多余解释,不要有多余的话.
"""
    response = llm.invoke(prompt,temperature=temperature)
    return response.content

def save_api_key(uuid: str, api_key: str, db_name='./database.sqlite'):
    """保存用户的 API key"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # 更新用户的 API key
    cursor.execute("""
        UPDATE users SET api_key = ? WHERE uuid = ?
    """, (api_key, uuid))
    
    conn.commit()
    conn.close()

def get_api_key(uuid: str, db_name='./database.sqlite') -> str:
    """获取用户的 API key"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute("SELECT api_key FROM users WHERE uuid = ?", (uuid,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else ''
