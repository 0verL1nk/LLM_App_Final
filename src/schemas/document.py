"""
Document processing Pydantic schemas for summarization, Q&A, rewrite, and mindmap.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SummaryType(str, Enum):
    """Types of document summaries"""

    BRIEF = "brief"
    DETAILED = "detailed"
    CUSTOM = "custom"


class SummarizeRequest(BaseModel):
    """Schema for summarization request"""

    summary_type: SummaryType = Field(
        default=SummaryType.BRIEF, description="Type of summary to generate"
    )
    max_length: Optional[int] = Field(
        default=None,
        ge=100,
        le=5000,
        description="Maximum length of summary in characters",
    )
    focus_areas: Optional[List[str]] = Field(
        default=None, description="Specific areas to focus on (for custom type)"
    )
    include_key_points: bool = Field(
        default=True, description="Whether to extract key points"
    )
    include_sections: bool = Field(
        default=True, description="Whether to include section-by-section summaries"
    )


class SectionSummary(BaseModel):
    """Schema for section summary"""

    section: str = Field(..., description="Section name or identifier")
    summary: str = Field(..., description="Summary of this section")


class SummaryStatistics(BaseModel):
    """Schema for summary statistics"""

    original_length: int = Field(..., description="Original text length in characters")
    summary_length: int = Field(..., description="Summary length in characters")
    compression_ratio: float = Field(
        ..., description="Compression ratio (summary/original)"
    )
    word_count_original: Optional[int] = Field(
        default=None, description="Original word count"
    )
    word_count_summary: Optional[int] = Field(
        default=None, description="Summary word count"
    )


class SummarizeResult(BaseModel):
    """Schema for summarization result"""

    summary: str = Field(..., description="Generated summary text")
    key_points: List[str] = Field(
        default_factory=list, description="Key points extracted from the document"
    )
    sections_summary: List[SectionSummary] = Field(
        default_factory=list, description="Section-by-section summaries"
    )
    statistics: SummaryStatistics = Field(..., description="Summary statistics")


class QARequest(BaseModel):
    """Schema for Q&A request"""

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Question to ask about the document",
    )
    history: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Chat history for context"
    )
    include_sources: bool = Field(
        default=True, description="Whether to include source citations"
    )
    include_suggestions: bool = Field(
        default=True, description="Whether to include suggested follow-up questions"
    )


class SourceCitation(BaseModel):
    """Schema for source citation"""

    page: Optional[int] = Field(default=None, description="Page number if available")
    section: Optional[str] = Field(default=None, description="Section name")
    excerpt: str = Field(..., description="Relevant excerpt from the document")


class QAResponse(BaseModel):
    """Schema for Q&A response"""

    answer: str = Field(..., description="Answer to the question")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    sources: List[SourceCitation] = Field(
        default_factory=list, description="Source citations for the answer"
    )
    suggested_questions: List[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )


class RewriteType(str, Enum):
    """Types of text rewriting"""

    ACADEMIC = "academic"
    CASUAL = "casual"
    FORMAL = "formal"
    CREATIVE = "creative"
    CONCISE = "concise"


class RewriteLength(str, Enum):
    """Length options for rewriting"""

    SHORTER = "shorter"
    SAME = "same"
    LONGER = "longer"


class RewriteRequest(BaseModel):
    """Schema for rewrite request"""

    text: str = Field(
        ..., min_length=10, max_length=10000, description="Text to rewrite"
    )
    rewrite_type: RewriteType = Field(
        default=RewriteType.FORMAL, description="Style of rewriting"
    )
    tone: Optional[str] = Field(default=None, description="Optional tone specification")
    length: RewriteLength = Field(
        default=RewriteLength.SAME, description="Desired length of output"
    )
    language: str = Field(default="zh", description="Target language (zh or en)")


class RewriteAlternative(BaseModel):
    """Schema for alternative rewrite"""

    text: str = Field(..., description="Alternative rewritten text")
    description: str = Field(..., description="Description of this alternative")


class RewriteResult(BaseModel):
    """Schema for rewrite result"""

    rewritten_text: str = Field(..., description="Rewritten text")
    original_length: int = Field(..., description="Original text length")
    rewritten_length: int = Field(..., description="Rewritten text length")
    improvements: List[str] = Field(
        default_factory=list, description="List of improvements made"
    )
    alternatives: List[RewriteAlternative] = Field(
        default_factory=list, description="Alternative versions"
    )


class MindmapRequest(BaseModel):
    """Schema for mindmap generation request"""

    max_depth: int = Field(
        default=3, ge=1, le=5, description="Maximum depth of the mindmap tree"
    )
    include_keywords: bool = Field(
        default=True, description="Whether to extract keywords"
    )
    group_by: Optional[str] = Field(
        default=None, description="Optional grouping strategy (topic, section, etc.)"
    )


class MindmapNode(BaseModel):
    """Schema for mindmap node"""

    name: str = Field(..., description="Node name/label")
    value: Optional[int] = Field(default=None, description="Node value/weight")
    children: List["MindmapNode"] = Field(
        default_factory=list, description="Child nodes"
    )


MindmapNode.model_rebuild()


class MindmapStructure(BaseModel):
    """Schema for mindmap structure metadata"""

    total_branches: int = Field(..., description="Total number of main branches")
    max_depth: int = Field(..., description="Actual maximum depth")
    main_topics: List[str] = Field(
        default_factory=list, description="List of main topics"
    )


class MindmapResult(BaseModel):
    """Schema for mindmap generation result"""

    mindmap: MindmapNode = Field(..., description="Hierarchical mindmap tree")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    structure: MindmapStructure = Field(..., description="Structure metadata")
