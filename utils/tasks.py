"""
异步任务执行函数 - 这些函数会在后台工作进程中执行
"""
import json
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 注意：这些导入需要在 worker 进程中工作
# 使用绝对导入以确保在 RQ worker 中正常工作
try:
    from utils.utils import (
        extract_files, 
        get_openai_client, 
        get_user_api_key,
        save_content_to_database,
        get_api_key,
        get_model_name,
        extract_json_string
    )
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.utils import (
        extract_files, 
        get_openai_client, 
        get_user_api_key,
        save_content_to_database,
        get_api_key,
        get_model_name,
        extract_json_string
    )

from langchain_community.chat_models import ChatTongyi
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

try:
    from utils.task_queue import update_task_status, TaskStatus
except ImportError:
    from task_queue import update_task_status, TaskStatus

def task_text_extraction(task_id: str, file_path: str, uid: str, user_uuid: str):
    """
    异步执行文本提取任务
    
    Args:
        task_id: 任务ID
        file_path: 文件路径
        uid: 文件UID
        user_uuid: 用户UUID
    """
    try:
        update_task_status(task_id, TaskStatus.STARTED)
        
        # 提取文件内容
        res = extract_files(file_path)
        if res['result'] != 1:
            update_task_status(task_id, TaskStatus.FAILED, error_message="文件提取失败")
            return False, ''
        
        file_content = '以下为一篇论文的原文:\n' + res['text']
        messages = [
            {
                "role": "system",
                "content": file_content,
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

        # 获取用户 API key 和模型名称
        api_key = get_api_key(user_uuid)
        if not api_key:
            update_task_status(task_id, TaskStatus.FAILED, error_message="请先在设置中配置您的 API Key")
            return False, "请先在设置中配置您的 API Key"
        
        model_name = get_model_name(user_uuid)
        
        # 创建客户端并调用
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
        )
        
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = json.loads(completion.choices[0].message.content)
        
        # 保存到数据库
        save_content_to_database(
            uid=uid,
            file_path=file_path,
            content=json.dumps(content),
            content_type='file_extraction'
        )
        
        update_task_status(task_id, TaskStatus.FINISHED)
        return True, content
        
    except Exception as e:
        error_msg = str(e)
        update_task_status(task_id, TaskStatus.FAILED, error_message=error_msg)
        return False, error_msg


def task_file_summary(task_id: str, file_path: str, uid: str, user_uuid: str):
    """
    异步执行文件总结任务
    
    Args:
        task_id: 任务ID
        file_path: 文件路径
        uid: 文件UID
        user_uuid: 用户UUID
    """
    try:
        update_task_status(task_id, TaskStatus.STARTED)
        
        # 提取文件内容
        res = extract_files(file_path)
        if res['result'] != 1:
            update_task_status(task_id, TaskStatus.FAILED, error_message="文件提取失败")
            return False, ''
        
        content = res['text']
        system_prompt = """你是一个文书助手。你的客户会交给你一篇文章，你需要用尽可能简洁的语言，总结这篇文章的内容。不得使用 markdown 记号。"""

        # 获取用户 API key 和模型名称
        api_key = get_api_key(user_uuid)
        if not api_key:
            update_task_status(task_id, TaskStatus.FAILED, error_message="请先在设置中配置您的 API Key")
            return False, "请先在设置中配置您的 API Key"
        
        model_name = get_model_name(user_uuid)
        llm = ChatTongyi(model_name=model_name, streaming=True, dashscope_api_key=api_key)
        
        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt),
             ("user", content)
            ])
        chain = prompt | llm | StrOutputParser()
        summary = chain.invoke({})
        
        # 保存到数据库
        save_content_to_database(
            uid=uid,
            file_path=file_path,
            content=summary,
            content_type='file_summary'
        )
        
        update_task_status(task_id, TaskStatus.FINISHED)
        return True, summary
        
    except Exception as e:
        error_msg = str(e)
        update_task_status(task_id, TaskStatus.FAILED, error_message=error_msg)
        return False, error_msg


def task_generate_mindmap(task_id: str, file_path: str, uid: str, user_uuid: str):
    """
    异步执行生成思维导图任务
    
    Args:
        task_id: 任务ID
        file_path: 文件路径
        uid: 文件UID
        user_uuid: 用户UUID
    """
    try:
        update_task_status(task_id, TaskStatus.STARTED)
        
        # 提取文件内容
        res = extract_files(file_path)
        if res['result'] != 1:
            update_task_status(task_id, TaskStatus.FAILED, error_message="文件提取失败")
            return False, None
        
        text = res['text']
        
        # 获取用户 API key 和模型名称
        api_key = get_api_key(user_uuid)
        if not api_key:
            update_task_status(task_id, TaskStatus.FAILED, error_message="请先在设置中配置您的 API Key")
            return False, None
        
        model_name = get_model_name(user_uuid)
        
        # 生成思维导图（extract_json_string 已在顶部导入）
        
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
            model_name=model_name,
            dashscope_api_key=api_key
        )
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "以下是需要分析的文献内容：\n {text}")
        ])
        
        chain = prompt_template | llm
        result = chain.invoke({"text": text})
        
        try:
            json_str = extract_json_string(result.content)
            mindmap_data = json.loads(json_str)
            
            # 保存到数据库
            save_content_to_database(
                uid=uid,
                file_path=file_path,
                content=json.dumps(mindmap_data),
                content_type='file_mindmap'
            )
            
            update_task_status(task_id, TaskStatus.FINISHED)
            return True, mindmap_data
        except json.JSONDecodeError:
            error_msg = "思维导图JSON解析失败"
            update_task_status(task_id, TaskStatus.FAILED, error_message=error_msg)
            return False, None
        
    except Exception as e:
        error_msg = str(e)
        update_task_status(task_id, TaskStatus.FAILED, error_message=error_msg)
        return False, None

