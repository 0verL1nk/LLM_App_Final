"""
Text optimization module for the LLM App.

This module provides text optimization, paraphrasing, and enhancement functionality
using LLM APIs.
"""

import logging
from typing import Optional, Tuple

from .database import DatabaseManager
from ..api.llm_client import LLMClient


class TextOptimizer:
    """Text optimization and paraphrasing manager."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        """Initialize text optimizer.

        Args:
            db_manager: Database manager instance
            llm_client: LLM client instance
        """
        self.db = db_manager or DatabaseManager()
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)

    def set_llm_client(self, llm_client: LLMClient) -> None:
        """Set LLM client.

        Args:
            llm_client: LLM client to use
        """
        self.llm_client = llm_client

    def optimize_text(self, text: str) -> Tuple[bool, str]:
        """Optimize and paraphrase text.

        Args:
            text: Text to optimize

        Returns:
            Tuple of (success, optimized_text)
        """
        try:
            if not self.llm_client:
                return False, "LLM客户端未配置"

            # Use LLM client's optimize_text method
            optimized = self.llm_client.optimize_text(text)

            # Extract the optimized text from response
            if "#### 优化后的文本" in optimized:
                start = optimized.find("#### 优化后的文本")
                start = optimized.find("\n", start) + 1
                optimized_text = optimized[start:].strip()
            else:
                optimized_text = optimized

            return True, optimized_text

        except Exception as e:
            self.logger.error(f"Text optimization error: {e}")
            return False, f"文本优化失败: {e!s}"

    def reduce_similarity(
        self, text: str, original_text: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Reduce text similarity (paraphrase to avoid plagiarism).

        Args:
            text: Text to modify
            original_text: Original text for reference

        Returns:
            Tuple of (success, modified_text)
        """
        try:
            if not self.llm_client:
                return False, "LLM客户端未配置"

            system_prompt = """你是一个专业的学术写作助手。请对给定的文本进行改写，降低相似度但保持原意。

要求：
1. 使用不同的词汇和表达方式
2. 保持学术性和专业性
3. 维护原文的逻辑结构和论证
4. 确保改写后的文本流畅自然
5. 适当调整句式结构

请直接输出改写后的文本，不需要额外说明。
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"需要改写的文本:\n{text}"},
            ]

            modified = self.llm_client.chat_completion(messages)
            return True, modified.strip()

        except Exception as e:
            self.logger.error(f"Similarity reduction error: {e}")
            return False, f"文段改写失败: {e!s}"

    def translate_text(
        self, text: str, target_language: str = "English"
    ) -> Tuple[bool, str]:
        """Translate text to target language.

        Args:
            text: Text to translate
            target_language: Target language

        Returns:
            Tuple of (success, translated_text)
        """
        try:
            if not self.llm_client:
                return False, "LLM客户端未配置"

            translated = self.llm_client.translate_text(text, target_language)
            return True, translated.strip()

        except Exception as e:
            self.logger.error(f"Translation error: {e}")
            return False, f"翻译失败: {e!s}"

    def improve_clarity(self, text: str) -> Tuple[bool, str]:
        """Improve text clarity and readability.

        Args:
            text: Text to improve

        Returns:
            Tuple of (success, improved_text)
        """
        try:
            if not self.llm_client:
                return False, "LLM客户端未配置"

            system_prompt = """你是一个专业的学术写作助手。请改进给定文本的表达，使其更加清晰、流畅和易读。

要求：
1. 简化复杂的句子结构
2. 使用更清晰的表达方式
3. 改善逻辑连贯性
4. 保持学术专业性
5. 消除冗余和重复

请直接输出改进后的文本，不需要额外说明。
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"需要改进的文本:\n{text}"},
            ]

            improved = self.llm_client.chat_completion(messages)
            return True, improved.strip()

        except Exception as e:
            self.logger.error(f"Clarity improvement error: {e}")
            return False, f"文本改进失败: {e!s}"

    def enhance_academic_style(self, text: str) -> Tuple[bool, str]:
        """Enhance academic writing style.

        Args:
            text: Text to enhance

        Returns:
            Tuple of (success, enhanced_text)
        """
        try:
            if not self.llm_client:
                return False, "LLM客户端未配置"

            system_prompt = """你是一个专业的学术写作助手。请将给定的文本改写为更正式的学术写作风格。

要求：
1. 使用更正式的学术用词
2. 采用客观、严谨的表达方式
3. 使用第三人称视角
4. 适当使用学术连接词和短语
5. 保持原文的核心观点和逻辑

请直接输出改写后的文本，不需要额外说明。
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"需要改写的文本:\n{text}"},
            ]

            enhanced = self.llm_client.chat_completion(messages)
            return True, enhanced.strip()

        except Exception as e:
            self.logger.error(f"Academic style enhancement error: {e}")
            return False, f"学术风格改进失败: {e!s}"

    def expand_content(
        self, text: str, expansion_ratio: float = 1.5
    ) -> Tuple[bool, str]:
        """Expand text content while maintaining quality.

        Args:
            text: Text to expand
            expansion_ratio: Ratio of expansion (e.g., 1.5 means 50% more)

        Returns:
            Tuple of (success, expanded_text)
        """
        try:
            if not self.llm_client:
                return False, "LLM客户端未配置"

            system_prompt = f"""你是一个专业的学术写作助手。请对给定的文本进行适当的扩展，使其更加详细和深入。

要求：
1. 扩展到原来的 {expansion_ratio:.1f} 倍长度
2. 添加更多细节和解释
3. 引入相关的例子和证据
4. 保持学术严谨性
5. 维持原文的核心观点

请直接输出扩展后的文本，不需要额外说明。
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"需要扩展的文本:\n{text}"},
            ]

            expanded = self.llm_client.chat_completion(messages)
            return True, expanded.strip()

        except Exception as e:
            self.logger.error(f"Content expansion error: {e}")
            return False, f"内容扩展失败: {e!s}"

    def summarize_content(
        self, text: str, target_length: int = 200
    ) -> Tuple[bool, str]:
        """Summarize text to target length.

        Args:
            text: Text to summarize
            target_length: Target word count

        Returns:
            Tuple of (success, summarized_text)
        """
        try:
            if not self.llm_client:
                return False, "LLM客户端未配置"

            system_prompt = f"""你是一个专业的学术写作助手。请对给定的文本进行摘要，压缩到约 {target_length} 字。

要求：
1. 保留核心观点和关键信息
2. 删除冗余和次要内容
3. 保持逻辑连贯性
4. 使用简洁明了的表达
5. 维持学术客观性

请直接输出摘要文本，不需要额外说明。
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"需要摘要的文本:\n{text}"},
            ]

            summarized = self.llm_client.chat_completion(messages)
            return True, summarized.strip()

        except Exception as e:
            self.logger.error(f"Content summarization error: {e}")
            return False, f"内容摘要失败: {e!s}"
