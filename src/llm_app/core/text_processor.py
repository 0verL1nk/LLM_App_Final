"""
Text processing module for the LLM App.

This module provides text extraction, analysis, and processing functionality
for academic papers and documents.
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple

from .database import DatabaseManager
from .file_handler import FileHandler
from ..api.llm_client import LLMClient


class TextProcessor:
    """Text extraction and processing manager."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        file_handler: Optional[FileHandler] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        """Initialize text processor.

        Args:
            db_manager: Database manager instance
            file_handler: File handler instance
            llm_client: LLM client instance
        """
        self.db = db_manager or DatabaseManager()
        self.file_handler = file_handler or FileHandler(self.db)
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)

    def set_llm_client(self, llm_client: LLMClient) -> None:
        """Set LLM client.

        Args:
            llm_client: LLM client to use
        """
        self.llm_client = llm_client

    def extract_text(self, file_path: str) -> Tuple[bool, str]:
        """Extract text from file.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (success, extracted_text)
        """
        result = self.file_handler.extract_text(file_path)
        if result["result"] == 1:
            return True, result["text"]
        return False, result["text"]

    def text_extraction(
        self, file_path: str, uid: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Extract and categorize text from paper.

        Args:
            file_path: Path to file
            uid: File UID

        Returns:
            Tuple of (success, message, extracted_content)
        """
        try:
            # Extract text from file
            success, file_content = self.extract_text(file_path)
            if not success:
                return False, "文件提取失败", None

            if not self.llm_client:
                return False, "LLM客户端未配置", None

            # Add header to content
            content_with_header = f"以下为一篇论文的原文:\n{file_content}"

            # Create messages for LLM
            messages = [
                {
                    "role": "system",
                    "content": content_with_header,
                },
                {
                    "role": "user",
                    "content": """
                    阅读论文，划出**关键语句**，并按照"研究背景，研究目的，研究方法，研究结果，未来展望"五个标签分类。
                    label为中文，text为原文，text可能有多句，并以json格式输出。
                    注意!!text内是论文原文!!。
                    以下为示例：
                    {'研究背景': ['text', ...], '研究目的': ['text', ...], ...}
                    """,
                },
            ]

            # Get response from LLM
            response = self.llm_client.chat_completion(messages)

            # Parse JSON response
            try:
                if "```json" in response:
                    start = response.find("```json") + 7
                    end = response.find("```", start)
                    json_str = response[start:end].strip()
                elif "```" in response:
                    start = response.find("```") + 3
                    end = response.find("```", start)
                    json_str = response[start:end].strip()
                else:
                    json_str = response

                extracted_data = json.loads(json_str)
            except json.JSONDecodeError:
                return False, "内容解析失败", None

            # Save to database
            content_str = json.dumps(extracted_data, ensure_ascii=False)
            self.db.save_content_to_database(
                uid=uid,
                file_path=file_path,
                content=content_str,
                content_type="file_extraction",
            )

            return True, "文本提取成功", extracted_data

        except Exception as e:
            self.logger.error(f"Text extraction error: {e}")
            return False, f"文本提取失败: {e!s}", None

    def file_summary(self, file_path: str, uid: str) -> Tuple[bool, str]:
        """Generate summary of file.

        Args:
            file_path: Path to file
            uid: File UID

        Returns:
            Tuple of (success, summary_text)
        """
        try:
            # Check if summary already exists
            existing_summary = self.db.get_content_by_uid(uid, "file_summary")
            if existing_summary:
                return True, existing_summary

            # Extract text from file
            success, file_content = self.extract_text(file_path)
            if not success:
                return False, "文件提取失败"

            if not self.llm_client:
                return False, "LLM客户端未配置"

            # Generate summary using LLM
            content_with_header = f"以下为一篇论文的原文:\n{file_content}"

            messages = [
                {
                    "role": "system",
                    "content": content_with_header,
                },
                {
                    "role": "user",
                    "content": """
                    请为这篇论文生成一个全面而简洁的总结。
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
                    """,
                },
            ]

            summary = self.llm_client.chat_completion(messages)

            # Save to database
            self.db.save_content_to_database(
                uid=uid,
                file_path=file_path,
                content=summary,
                content_type="file_summary",
            )

            return True, summary

        except Exception as e:
            self.logger.error(f"Summary generation error: {e}")
            return False, f"总结生成失败: {e!s}"

    def generate_mindmap(
        self, file_path: str, uid: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Generate mindmap data for file.

        Args:
            file_path: Path to file
            uid: File UID

        Returns:
            Tuple of (success, message, mindmap_data)
        """
        try:
            # Check if mindmap already exists
            existing_mindmap = self.db.get_content_by_uid(uid, "file_mindmap")
            if existing_mindmap:
                try:
                    mindmap_data = json.loads(existing_mindmap)
                    return True, "思维导图生成成功", mindmap_data
                except json.JSONDecodeError:
                    pass  # Continue to regenerate

            # Extract text from file
            success, file_content = self.extract_text(file_path)
            if not success:
                return False, "文件提取失败", None

            if not self.llm_client:
                return False, "LLM客户端未配置", None

            # Generate mindmap using LLM
            content_with_header = f"以下为一篇论文的原文:\n{file_content}"

            messages = [
                {
                    "role": "system",
                    "content": content_with_header,
                },
                {
                    "role": "user",
                    "content": """
                    请为这篇论文生成一个结构清晰的思维导图。
                    按照以下格式输出（严格的JSON格式）：
                    {
                        "name": "根节点名称",
                        "children": [
                            {
                                "name": "一级节点1",
                                "children": [
                                    {"name": "二级节点1", "children": []}
                                ]
                            }
                        ]
                    }
                    """,
                },
            ]

            response = self.llm_client.chat_completion(messages)

            # Parse JSON response
            try:
                if "```json" in response:
                    start = response.find("```json") + 7
                    end = response.find("```", start)
                    json_str = response[start:end].strip()
                elif "```" in response:
                    start = response.find("```") + 3
                    end = response.find("```", start)
                    json_str = response[start:end].strip()
                else:
                    json_str = response

                mindmap_data = json.loads(json_str)
            except json.JSONDecodeError:
                # Return basic structure if parsing fails
                mindmap_data = {
                    "name": "文档解析出错",
                    "children": [{"name": "内容解析失败", "children": []}],
                }

            # Save to database
            mindmap_str = json.dumps(mindmap_data, ensure_ascii=False)
            self.db.save_content_to_database(
                uid=uid,
                file_path=file_path,
                content=mindmap_str,
                content_type="file_mindmap",
            )

            return True, "思维导图生成成功", mindmap_data

        except Exception as e:
            self.logger.error(f"Mindmap generation error: {e}")
            return False, f"思维导图生成失败: {e!s}", None

    def answer_question(
        self, file_path: str, question: str, uid: str
    ) -> Tuple[bool, str]:
        """Answer question about file content.

        Args:
            file_path: Path to file
            question: Question to answer
            uid: File UID

        Returns:
            Tuple of (success, answer)
        """
        try:
            # Extract text from file
            success, file_content = self.extract_text(file_path)
            if not success:
                return False, "文件提取失败"

            if not self.llm_client:
                return False, "LLM客户端未配置"

            # Generate answer using LLM
            content_with_header = f"以下为一篇论文的原文:\n{file_content}"

            messages = [
                {
                    "role": "system",
                    "content": content_with_header,
                },
                {
                    "role": "user",
                    "content": f"基于上述论文内容，回答以下问题：\n{question}\n\n请提供准确、详细的回答，并引用相关原文。",
                },
            ]

            answer = self.llm_client.chat_completion(messages)
            return True, answer

        except Exception as e:
            self.logger.error(f"Q&A error: {e}")
            return False, f"问答处理失败: {e!s}"

    def get_extracted_content(self, uid: str) -> Optional[Dict[str, Any]]:
        """Get extracted content by UID.

        Args:
            uid: File UID

        Returns:
            Extracted content dictionary or None
        """
        content = self.db.get_content_by_uid(uid, "file_extraction")
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return None
        return None

    def get_summary(self, uid: str) -> Optional[str]:
        """Get summary by UID.

        Args:
            uid: File UID

        Returns:
            Summary text or None
        """
        return self.db.get_content_by_uid(uid, "file_summary")

    def get_mindmap(self, uid: str) -> Optional[Dict[str, Any]]:
        """Get mindmap data by UID.

        Args:
            uid: File UID

        Returns:
            Mindmap data dictionary or None
        """
        content = self.db.get_content_by_uid(uid, "file_mindmap")
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return None
        return None
