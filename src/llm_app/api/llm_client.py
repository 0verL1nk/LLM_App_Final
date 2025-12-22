"""
LLM Client module for the LLM App.

This module provides a unified interface for interacting with various LLM APIs
including DashScope (Alibaba Cloud) and OpenAI-compatible APIs.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI

from ..config import Config


class LLMClient:
    """LLM API client for DashScope/OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """Initialize LLM client.

        Args:
            api_key: API key
            model_name: Model name (default: Config.DEFAULT_MODEL)
            base_url: API base URL (default: Config.API_BASE_URL)
        """
        self.api_key = api_key
        self.model_name = model_name or Config.DEFAULT_MODEL
        self.base_url = base_url or Config.API_BASE_URL
        self.logger = logging.getLogger(__name__)

        # Create client
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Union[str, Any]:
        """Send chat completion request.

        Args:
            messages: List of message dictionaries
            temperature: Temperature for response generation
            max_tokens: Maximum tokens for response

        Returns:
            Response content or full response object
        """
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return completion.choices[0].message.content
        except Exception as e:
            self.logger.error(f"LLM API error: {e}")
            raise

    def stream_completion(
        self, messages: List[Dict[str, str]], temperature: float = 0.7
    ):
        """Send streaming chat completion request.

        Args:
            messages: List of message dictionaries
            temperature: Temperature for response generation

        Yields:
            Streaming response chunks
        """
        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            self.logger.error(f"LLM streaming error: {e}")
            raise

    def extract_text_from_paper(self, file_content: str) -> Dict[str, Any]:
        """Extract and categorize key text from academic paper.

        Args:
            file_content: Full text content of the paper

        Returns:
            Dictionary with categorized key text
        """
        system_prompt = """你是一个专业的学术文献分析师。请仔细阅读以下论文内容，提取并分类关键原文。

按照以下五个标签分类：
1. 研究背景 - 介绍研究领域的背景信息、现状和问题
2. 研究目的 - 明确阐述研究要解决的核心问题或目标
3. 研究方法 - 详细描述研究采用的方法、技术路线、实验设计
4. 研究结果 - 呈现研究发现、实验结果、数据分析
5. 未来展望 - 讨论研究的局限性和未来研究方向

要求：
- label使用中文标签
- text为原文内容
- text可能包含多句
- 以严格的JSON格式输出
- 确保提取的内容准确反映原文含义

输出格式示例：
{"研究背景": ["text1", "text2", ...], "研究目的": [...], ...}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"以下是一篇论文的原文:\n{file_content}"},
        ]

        response = self.chat_completion(messages)
        return self._parse_json_response(response)

    def generate_paper_summary(self, file_content: str) -> str:
        """Generate summary of academic paper.

        Args:
            file_content: Full text content of the paper

        Returns:
            Generated summary
        """
        system_prompt = """你是一个专业的学术文献总结助手。请为给定的论文生成一个全面而简洁的总结。

总结应包括：
1. 研究背景和目的
2. 主要研究方法
3. 关键发现和结果
4. 结论和意义

要求：
- 保持客观和准确性
- 突出研究的创新点
- 控制在300字以内
- 使用学术语言但保持可读性
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"以下是需要总结的论文内容:\n{file_content}"},
        ]

        return self.chat_completion(messages)

    def answer_question(self, file_content: str, question: str) -> str:
        """Answer question about paper content.

        Args:
            file_content: Full text content of the paper
            question: Question to answer

        Returns:
            Answer text
        """
        system_prompt = """你是一个专业的学术助手，正在为用户解答关于某篇论文的问题。

请基于提供的论文内容回答问题。要求：
1. 准确引用论文中的相关信息
2. 回答要具体和深入
3. 如果问题超出论文范围，请明确说明
4. 保持客观和学术性
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"论文内容:\n{file_content}\n\n用户问题: {question}",
            },
        ]

        return self.chat_completion(messages)

    def optimize_text(self, text: str) -> str:
        """Optimize and paraphrase text.

        Args:
            text: Text to optimize

        Returns:
            Optimized text
        """
        system_prompt = """你是一个专业的论文优化助手。你的任务是：

1. 优化用户输入的文本，使其表达更加流畅、逻辑更加清晰
2. 替换同义词和调整句式，以降低查重率
3. 保证原文的核心意思不变
4. 保持论文专业性，包括用词的专业性和句式的专业性
5. 使文本更加符合语法规范，更像母语者写出来的文章

请按以下格式输出：
#### 优化后的文本
[优化后的内容]
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"用户输入: {text}"},
        ]

        return self.chat_completion(messages)

    def generate_mindmap_data(self, text: str) -> Dict[str, Any]:
        """Generate mindmap data from text content.

        Args:
            text: Text content to analyze

        Returns:
            Mindmap data in JSON format
        """
        system_prompt = """你是一个专业的文献分析专家。请分析给定的文献内容，生成一个结构清晰的思维导图。

分析要求：
1. 主题提取 - 准确识别文档的核心主题作为根节点
2. 结构设计
   - 第一层：识别文档的主要章节或核心概念（3-5个）
   - 第二层：提取每个主要章节下的关键要点（2-4个）
   - 第三层：补充具体的细节和示例（如果必要）
   - 最多不超过4层结构
3. 内容处理
   - 使用简洁的关键词或短语
   - 每个节点内容控制在15字以内
   - 保持逻辑连贯性和层次关系

输出格式：
必须是严格的JSON格式：
{
    "name": "根节点名称",
    "children": [
        {
            "name": "一级节点1",
            "children": [
                {
                    "name": "二级节点1",
                    "children": [...]
                }
            ]
        }
    ]
}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"以下是需要分析的文献内容：\n{text}"},
        ]

        response = self.chat_completion(messages)
        return self._parse_json_response(response)

    def translate_text(self, text: str, target_language: str = "English") -> str:
        """Translate text to target language.

        Args:
            text: Text to translate
            target_language: Target language

        Returns:
            Translated text
        """
        system_prompt = f"""你是一个专业的翻译助手。请将给定的文本翻译成{target_language}。

要求：
1. 保持原文的学术性和专业性
2. 确保翻译准确且流畅
3. 维护原文的逻辑结构
4. 使用适合目标语言的学术表达方式
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"需要翻译的文本:\n{text}"},
        ]

        return self.chat_completion(messages)

    @staticmethod
    def _parse_json_response(response: str) -> Dict[str, Any]:
        """Parse JSON response from LLM.

        Args:
            response: Raw response string

        Returns:
            Parsed JSON dictionary
        """
        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()

            return json.loads(response)
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Failed to parse JSON response: {e}")
            # Return a basic structure as fallback
            return {
                "name": "解析失败",
                "children": [{"name": "内容解析出错", "children": []}],
            }
