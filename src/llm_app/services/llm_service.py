"""
LLM service for document processing using DashScope API.
"""

import json
from typing import Any, Dict, List, Optional

import httpx

from llm_app.core.logger import get_logger
from llm_app.core.config import settings

logger = get_logger(__name__)

DASHSCOPE_API_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
)


class LLMService:
    """Service for LLM-based document processing"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.dashscope_api_key
        if not self.api_key:
            raise ValueError("DashScope API key is required")

    async def _call_llm(
        self,
        prompt: str,
        model: str = "qwen-max",
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Make an async call to DashScope API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                DASHSCOPE_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": {"messages": [{"role": "user", "content": prompt}]},
                    "parameters": {
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                },
            )

            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                raise ValueError(f"LLM API error: {response.status_code}")

            data = response.json()
            return data.get("output", {}).get("text", "")

    def _call_llm_sync(
        self,
        prompt: str,
        model: str = "qwen-max",
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Make a sync call to DashScope API (for background tasks)."""
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                DASHSCOPE_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": {"messages": [{"role": "user", "content": prompt}]},
                    "parameters": {
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                },
            )

            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                raise ValueError(f"LLM API error: {response.status_code}")

            data = response.json()
            return data.get("output", {}).get("text", "")

    def generate_summary(
        self,
        text: str,
        summary_type: str = "brief",
        max_length: Optional[int] = None,
        focus_areas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a summary of the given text."""
        length_instruction = ""
        if max_length:
            length_instruction = f"控制摘要长度在{max_length}字符以内。"

        focus_instruction = ""
        if focus_areas:
            focus_instruction = f"重点关注以下方面: {', '.join(focus_areas)}。"

        type_instructions = {
            "brief": "生成一个简洁的摘要，突出核心要点。",
            "detailed": "生成一个详细的摘要，包含主要论点和支撑证据。",
            "custom": f"根据用户需求生成摘要。{focus_instruction}",
        }

        prompt = f"""请对以下文本进行摘要。

要求:
1. {type_instructions.get(summary_type, type_instructions["brief"])}
2. {length_instruction}
3. 提取3-5个关键要点
4. 使用清晰、专业的语言

文本内容:
{text[:8000]}

请按以下JSON格式输出:
{{
    "summary": "摘要内容",
    "key_points": ["要点1", "要点2", "要点3"]
}}"""

        response = self._call_llm_sync(prompt, max_tokens=2000)

        try:
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                result = json.loads(response[start_idx:end_idx])
                return {
                    "summary": result.get("summary", response),
                    "key_points": result.get("key_points", []),
                }
        except json.JSONDecodeError:
            pass

        return {
            "summary": response,
            "key_points": [],
        }

    def extract_key_points(self, text: str, count: int = 5) -> List[str]:
        """Extract key points from text."""
        prompt = f"""从以下文本中提取{count}个最重要的关键要点。

文本内容:
{text[:6000]}

请直接以JSON数组格式输出关键要点:
["要点1", "要点2", ...]"""

        response = self._call_llm_sync(prompt, max_tokens=1000)

        try:
            start_idx = response.find("[")
            end_idx = response.rfind("]") + 1
            if start_idx != -1 and end_idx > start_idx:
                return json.loads(response[start_idx:end_idx])
        except json.JSONDecodeError:
            pass

        return [response] if response else []

    def summarize_by_sections(
        self,
        sections: List[str],
        section_names: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Generate summaries for each section."""
        results = []
        for i, section in enumerate(sections[:10]):
            section_name = (
                section_names[i]
                if section_names and i < len(section_names)
                else f"Section {i + 1}"
            )

            if len(section) < 50:
                results.append({"section": section_name, "summary": section})
                continue

            prompt = f"""请用1-2句话简要概括以下段落的主要内容:

{section[:2000]}

只输出概括内容，不要有其他说明。"""

            summary = self._call_llm_sync(prompt, max_tokens=200, temperature=0.5)
            results.append({"section": section_name, "summary": summary.strip()})

        return results

    def calculate_summary_stats(
        self,
        original_text: str,
        summary_text: str,
    ) -> Dict[str, Any]:
        """Calculate statistics about the summary."""
        original_length = len(original_text)
        summary_length = len(summary_text)
        compression_ratio = (
            summary_length / original_length if original_length > 0 else 0
        )

        original_words = len(original_text.split())
        summary_words = len(summary_text.split())

        return {
            "original_length": original_length,
            "summary_length": summary_length,
            "compression_ratio": round(compression_ratio, 4),
            "word_count_original": original_words,
            "word_count_summary": summary_words,
        }

    def answer_question(
        self,
        text: str,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Answer a question based on document content."""
        history_context = ""
        if history:
            history_lines = []
            for item in history[-5:]:
                role = "用户" if item.get("role") == "user" else "助手"
                history_lines.append(f"{role}: {item.get('content', '')}")
            history_context = f"\n对话历史:\n" + "\n".join(history_lines) + "\n"

        prompt = f"""基于以下文档内容回答问题。

文档内容:
{text[:6000]}
{history_context}
问题: {question}

请按以下JSON格式输出:
{{
    "answer": "你的回答",
    "confidence": 0.85,
    "sources": [{{"section": "相关段落位置", "excerpt": "相关原文摘录"}}],
    "suggested_questions": ["相关问题1", "相关问题2"]
}}

如果文档中没有相关信息，请诚实说明并给出较低的置信度。"""

        response = self._call_llm_sync(prompt, max_tokens=1500)

        try:
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                result = json.loads(response[start_idx:end_idx])
                return {
                    "answer": result.get("answer", response),
                    "confidence": float(result.get("confidence", 0.5)),
                    "sources": result.get("sources", []),
                    "suggested_questions": result.get("suggested_questions", []),
                }
        except (json.JSONDecodeError, ValueError):
            pass

        return {
            "answer": response,
            "confidence": 0.5,
            "sources": [],
            "suggested_questions": [],
        }

    def rewrite_text(
        self,
        text: str,
        rewrite_type: str = "formal",
        tone: Optional[str] = None,
        length: str = "same",
        language: str = "zh",
    ) -> Dict[str, Any]:
        """Rewrite text in a different style."""
        type_instructions = {
            "academic": "学术风格，使用专业术语和严谨的表达",
            "casual": "轻松随意的风格，使用日常用语",
            "formal": "正式风格，使用规范的书面语言",
            "creative": "创意风格，使用生动形象的表达",
            "concise": "精简风格，去除冗余保留核心内容",
        }

        length_instructions = {
            "shorter": "将内容精简，使输出比原文短30%左右",
            "same": "保持与原文相近的长度",
            "longer": "适当扩展，增加细节和解释",
        }

        lang_instruction = "使用中文输出" if language == "zh" else "使用英文输出"
        tone_instruction = f"语气要{tone}" if tone else ""

        prompt = f"""请改写以下文本。

要求:
1. 风格: {type_instructions.get(rewrite_type, type_instructions["formal"])}
2. 长度: {length_instructions.get(length, length_instructions["same"])}
3. {lang_instruction}
4. {tone_instruction}

原文:
{text}

请按以下JSON格式输出:
{{
    "rewritten_text": "改写后的文本",
    "improvements": ["改进点1", "改进点2"]
}}"""

        response = self._call_llm_sync(prompt, max_tokens=2000)

        try:
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                result = json.loads(response[start_idx:end_idx])
                return {
                    "rewritten_text": result.get("rewritten_text", response),
                    "improvements": result.get("improvements", []),
                }
        except json.JSONDecodeError:
            pass

        return {
            "rewritten_text": response,
            "improvements": [],
        }

    def generate_mindmap(
        self,
        text: str,
        max_depth: int = 3,
        include_keywords: bool = True,
    ) -> Dict[str, Any]:
        """Generate a hierarchical mindmap from text."""
        prompt = f"""分析以下文本，生成一个层级思维导图结构。

要求:
1. 最大层级深度: {max_depth}
2. 提取主题和子主题
3. {"提取关键词" if include_keywords else ""}

文本内容:
{text[:6000]}

请按以下JSON格式输出:
{{
    "mindmap": {{
        "name": "主题",
        "children": [
            {{
                "name": "子主题1",
                "children": [
                    {{"name": "细节1"}},
                    {{"name": "细节2"}}
                ]
            }}
        ]
    }},
    "keywords": ["关键词1", "关键词2"]
}}"""

        response = self._call_llm_sync(prompt, max_tokens=2000)

        try:
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                result = json.loads(response[start_idx:end_idx])
                mindmap = result.get("mindmap", {"name": "Document", "children": []})
                keywords = result.get("keywords", [])

                def count_branches(node: dict) -> tuple:
                    if not node.get("children"):
                        return 0, 1
                    total_branches = len(node["children"])
                    max_d = 1
                    for child in node["children"]:
                        b, d = count_branches(child)
                        total_branches += b
                        max_d = max(max_d, d + 1)
                    return total_branches, max_d

                branches, depth = count_branches(mindmap)
                main_topics = [c.get("name", "") for c in mindmap.get("children", [])]

                return {
                    "mindmap": mindmap,
                    "keywords": keywords if include_keywords else [],
                    "structure": {
                        "total_branches": branches,
                        "max_depth": depth,
                        "main_topics": main_topics,
                    },
                }
        except json.JSONDecodeError:
            pass

        return {
            "mindmap": {"name": "Document", "children": []},
            "keywords": [],
            "structure": {
                "total_branches": 0,
                "max_depth": 1,
                "main_topics": [],
            },
        }
