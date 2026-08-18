"""Scripted answers and evidence payloads for the scenario calibration runner.

These payloads exist only to calibrate the scoring pipeline and judge; they are
canned data, not live agent behavior.
"""

import json
from typing import Any

from agent.application.evals import AgentEvalCase


def _answer_for_case(case: AgentEvalCase) -> str:
    answers = {
        "project_rag_fact_001": (
            "基于当前项目文档，RAG 的核心价值是先检索再生成，用外部证据降低幻觉并提升回答相关性。"
            "<evidence>chunk-1|p1|o0-10</evidence>"
        ),
        "project_compare_001": (
            "结合当前项目文档，RAG 实现更直接、接入成本更低；Self-RAG 增加了自反思与纠错链路，但工程复杂度更高。"
            "<evidence>chunk-1|p1|o0-10</evidence>"
            "<evidence>chunk-2|p2|o0-10</evidence>"
            "如果当前阶段优先追求稳定落地，建议先以 RAG 为主，再把 Self-RAG 作为后续试点方向。"
        ),
        "project_scope_boundary_001": (
            "只看当前项目文档，我不会引用外部最新资料。现有材料已经说明 Self-RAG 值得关注，但还不足以直接支持现在就正式引入主链路。"
            "<evidence>chunk-1|p1|o0-10</evidence>"
        ),
        "project_gap_001": (
            "如果只看当前项目文档，现阶段最大的缺口是缺少针对本项目真实延迟、复杂度和运维成本的落地评估。"
            "<evidence>chunk-1|p1|o0-10</evidence>"
            "因此证据还不足以做完整落地决策，下一步应先补一个面向本项目的试点评估方案。"
        ),
        "project_compare_constraints_001": (
            "结合当前项目文档，在更看重稳定交付和较低工程复杂度的前提下，RAG 仍然应该优先于 Self-RAG。"
            "<evidence>chunk-1|p1|o0-10</evidence>"
            "<evidence>chunk-2|p2|o0-10</evidence>"
            "原因是 Self-RAG 的自反思链路会带来额外编排和调试成本，而当前约束更偏向尽快稳定落地。"
        ),
        "web_latest_001": (
            "基于本次联网检索到的 2025 年以来公开资料（含 2025-06 综述与 2025-11 工程实践记录），Self-RAG 的最新进展集中在两点。"
            "结论一：多个 2024-2025 年后续工作在相同开放域问答基准上报告了超过 Self-RAG 的结果。"
            "结论二：关注点已从论文指标转向系统集成，延迟预算与成本观测成为主要议题。"
        ),
        "web_recency_001": (
            "结合本次联网检索（2025-06 综述、2025-11 工程实践记录），我的判断是研究关注点已经明显从论文指标转向系统落地，但不是完全替代。"
            "依据是检索到的资料中，集成成本、延迟预算和可观测性被反复强调，而不只是效果分数。"
        ),
        "web_tradeoff_001": (
            "依据本次联网检索（2025-06 综述），近年 Self-RAG 的主要收益是更强的自校验与纠错能力；"
            "主要代价是自反思链路带来更高延迟与工程复杂度，二者构成明确 tradeoff。"
        ),
        "hybrid_research_001": (
            "结合当前项目文档与近期公开资料，Self-RAG 有机会提升答案自校验能力，但也会显著增加编排复杂度与延迟预算。"
            "<evidence>chunk-1|p1|o0-10</evidence>"
            "<evidence>chunk-2|p2|o0-10</evidence>"
            "近期公开经验同样强调真实系统中的成本、观测和稳定性约束，因此更适合先做小范围 pilot，再决定是否纳入正式 roadmap。"
        ),
        "hybrid_rollout_001": (
            "结合项目文档和近期公开资料，我建议 Self-RAG 先做试点而不是立即全面纳入。"
            "<evidence>chunk-1|p1|o0-10</evidence>"
            "<evidence>chunk-2|p2|o0-10</evidence>"
            "近期公开经验显示它的收益往往伴随更高的系统成本，因此分阶段 rollout 应先做离线评估和小流量实验，再观察收益、延迟与成本，最后再决定是否进入正式路线图。"
        ),
        "hybrid_guardrail_001": (
            "如果项目要试点 Self-RAG，至少要先补齐回答质量回归评估、延迟与成本观测，以及失败案例分析这几类 guardrail。"
            "<evidence>chunk-1|p1|o0-10</evidence>"
            "<evidence>chunk-2|p2|o0-10</evidence>"
            "结合近期公开资料，社区也越来越强调 observability、成本监控和失败样本复盘，否则更复杂的执行链路很难稳定落地，因此这些 guardrail 必须先补齐。"
        ),
        "hybrid_reject_001": (
            "如果团队当前只能接受很低的复杂度和延迟开销，我倾向于建议暂缓 Self-RAG。"
            "<evidence>chunk-1|p1|o0-10</evidence>"
            "<evidence>chunk-2|p2|o0-10</evidence>"
            "这是因为项目内约束和近期公开经验都表明，它的收益通常要用额外的系统复杂度、时延预算和观测建设来交换，在当前条件下 tradeoff 并不划算。"
        ),
        "project_contradiction_001": (
            "ReAct 依赖行动-观察轨迹循环改进，不引入语言化自我反思"
            "<evidence>chunk-1|p1|o0-10</evidence><evidence>chunk-2|p1|o0-10</evidence>；"
            "Reflexion 显式生成语言化反思并注入下一轮上下文"
            "<evidence>chunk-3|p2|o0-10</evidence><evidence>chunk-4|p2|o0-10</evidence>。"
            "结论：两者在「是否用语言化反馈改进」上不一致，但目标互补而非矛盾。"
        ),
        "project_false_premise_001": (
            "这个前提需要更正：self-consistency 解码出自 Self-Consistency 论文，不是 Tree-of-Thoughts"
            "<evidence>chunk-1|p1|o0-10</evidence>。"
            "Tree-of-Thoughts 提出的是树状探索与前瞻评估，因此不存在其论文中的 self-consistency 温度设置。"
        ),
        "project_abstain_001": (
            "当前项目文档中没有系统讨论多智能体协作框架设计的论文，无法在不编造引用的情况下给出结论。"
            "建议补充相关文献，或允许联网检索后再回答。"
        ),
        "web_overturn_001": (
            "截至 2026-08 的公开资料，Self-RAG 的领先结论不再无条件成立。"
            "依据一：《Retrieval-Augmented Generation: A Survey of Self-Reflective Variants》"
            "（2025-06，example.com/surveys/self-reflective-rag-2025）指出多个 2024-2025 年后续工作"
            "在相同开放域问答基准上报告了超过 Self-RAG 的结果。"
            "依据二：《Production Notes on Self-Reflective RAG Adoption》"
            "（2025-11，example.com/blogs/self-rag-production-2025）将其收益放在更高延迟与复杂度的代价下讨论。"
        ),
        "routing_discrimination_local_001": (
            "根据项目文档，Toolformer 的消融实验主要评估移除工具调用数据筛选与自监督损失等设计后的性能变化"
            "<evidence>chunk-1|p1|o0-10</evidence>。本回答只基于项目文档，未使用外部资料。"
        ),
        "routing_discrimination_web_001": (
            "依据本次联网检索的两份资料：《Tool Use After Toolformer: Native Function Calling Becomes Default》"
            "（2024-09，example.com/blogs/native-function-calling-2024）与"
            "《Training Paradigms for Internalized Tool Use》（2025-03，example.com/blogs/internalized-tool-use-2025），"
            "2023 年之后的演进主要是：原生函数调用接口成为标配、模型内化工具使用的训练范式（工具使用对齐数据）、"
            "以及 agent 框架层的并行工具编排；这些与 Toolformer 的自监督标注思路形成对照。"
        ),
        "project_delegation_scaling_001": (
            "RAG：检索增强生成基础范式<evidence>chunk-1|p1|o0-10</evidence>；"
            "Chain-of-Thought：思维链提示<evidence>chunk-2|p1|o0-10</evidence>；"
            "Self-Consistency：多路径采样投票<evidence>chunk-3|p1|o0-10</evidence>；"
            "ReAct：推理与行动交织<evidence>chunk-4|p1|o0-10</evidence>；"
            "Toolformer：模型自学工具调用<evidence>chunk-5|p1|o0-10</evidence>；"
            "Reflexion：语言化自我反思<evidence>chunk-6|p1|o0-10</evidence>；"
            "Tree-of-Thoughts：树状探索搜索<evidence>chunk-7|p1|o0-10</evidence>；"
            "Self-RAG：按需检索与自我批判<evidence>chunk-8|p1|o0-10</evidence>。"
            "与 RAG 主题相关度排序及依据：RAG 直接定义检索增强范式（chunk-1）；"
            "Self-RAG 在检索增强之上叠加自反思与自我批判（chunk-8）；"
            "ReAct 的行动-观察循环依赖检索证据驱动推理（chunk-4）；"
            "Reflexion 的语言化反思服务于推理改进而非检索链路（chunk-6）；"
            "Toolformer 聚焦工具调用能力的自监督习得，与检索无直接关系（chunk-5）；"
            "Tree-of-Thoughts 是推理搜索结构（chunk-7）；"
            "Self-Consistency 与 Chain-of-Thought 仅涉及推理路径采样与思维链（chunk-3、chunk-2），离 RAG 最远。"
        ),
    }
    return answers.get(
        case.case_id,
        "结合当前材料，建议先做小范围验证，再决定是否扩大投入。",
    )


def _tool_calls_for_case(case: AgentEvalCase) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for tool_name in case.process_contract.required_tool_names:
        if tool_name == "delegate_task":
            continue
        tool_calls.append(
            {
                "id": f"tool-{len(tool_calls) + 1}",
                "name": tool_name,
                "args": {"query": case.prompt},
                "type": "tool_call",
            }
        )
    if not tool_calls and case.process_contract.requires_evidence:
        tool_calls.append(
            {
                "id": "tool-search-document",
                "name": "search_document",
                "args": {"query": case.prompt},
                "type": "tool_call",
            }
        )
    return tool_calls


def _search_document_evidence(case: AgentEvalCase) -> dict[str, Any]:
    """Simulated corpus payloads with substantive text matching canned answers.

    Evidence content must be real-looking sentences, not placeholders: the
    quote-anchored judge inspects chunk text and rejects vacuous citations.
    """
    single_evidence_sets = {
        "project_rag_fact_001": [
            "RAG 将预训练语言模型与检索组件结合，在生成前先从外部知识源检索相关文档，以外部证据降低幻觉并提升回答的事实性与相关性。"
        ],
        "project_scope_boundary_001": [
            "项目文档显示 Self-RAG 值得关注，但语料中缺少针对本项目延迟、复杂度与运维成本的落地评估，尚不足以直接支持引入主链路。"
        ],
        "project_gap_001": [
            "现有语料对 Self-RAG 的介绍停留在方法层面，缺少针对本项目真实延迟、复杂度和运维成本的落地评估数据。"
        ],
        "project_false_premise_001": [
            "Self-Consistency 提出对同一思维链问题采样多条推理路径并对最终答案投票，self-consistency 解码即出自本文，而非 Tree-of-Thoughts。"
        ],
        "routing_discrimination_local_001": [
            "Toolformer 的消融实验评估了移除自监督工具调用损失与工具调用数据筛选等设计后的性能变化，显示两者对工具调用能力均有贡献。"
        ],
    }
    pair_evidence_sets = {
        "project_compare_001": [
            "RAG 通过检索增强生成，把外部文档拼入上下文，实现直接、接入成本较低的检索增强方案。",
            "Self-RAG 在生成过程中按需检索并对每一步进行自我反思与批判，带来更强的自校验能力，同时显著增加工程复杂度。",
        ],
        "project_compare_constraints_001": [
            "RAG 的实现更直接，主要工程量在检索链路本身，适合追求稳定交付的团队。",
            "Self-RAG 的自反思与纠错链路需要额外的控制流与调试成本，工程复杂度更高。",
        ],
        "hybrid_research_001": [
            "项目文档显示 Self-RAG 能提升答案自校验能力，但链路更长、延迟与编排复杂度更高。",
            "近期公开经验强调引入 Self-RAG 类方法前必须先建设成本观测与失败案例复盘机制。",
        ],
        "hybrid_rollout_001": [
            "项目文档建议对 Self-RAG 类自反思检索先做小范围试点，评估收益后再扩大。",
            "公开资料中的分阶段实践普遍先做离线评估与小流量实验，再进入正式路线。",
        ],
        "hybrid_guardrail_001": [
            "项目文档指出自反思链路的失败模式需要逐案复盘，缺少观测时难以定位。",
            "公开经验把回答质量回归评估、延迟与成本观测列为试点前置条件。",
        ],
        "hybrid_reject_001": [
            "项目文档显示 Self-RAG 的收益伴随更高的系统复杂度与时延预算。",
            "公开资料同样表明其收益通常要用额外的观测建设与运维成本来交换。",
        ],
    }
    contradiction_evidence = [
        "ReAct 将推理与行动交织，通过行动-观察轨迹与环境交互并迭代改进，不在轨迹中生成语言化自我反思。",
        "ReAct 的改进来自外部观察反馈进入下一轮推理，而非模型对自己失败的显式语言总结。",
        "Reflexion 在任务失败后生成语言化反思文本，总结失败原因与改进方向。",
        "Reflexion 将反思文本注入下一轮尝试的上下文，实现基于语言反馈的自我改进。",
    ]
    scaling_evidence = [
        "RAG：先检索再生成，用外部证据降低幻觉并提升相关性。",
        "Chain-of-Thought：让模型在给出答案前生成中间推理步骤。",
        "Self-Consistency：对多条采样推理路径的最终答案投票。",
        "ReAct：推理与行动交织，以行动-观察轨迹驱动决策。",
        "Toolformer：用自监督损失让模型自己学会何时调用何种工具。",
        "Reflexion：失败后生成语言化反思并注入下一轮上下文。",
        "Tree-of-Thoughts：把推理组织为树状探索，支持前瞻与回溯。",
        "Self-RAG：按需检索并对检索内容与自身答案进行自我批判。",
    ]

    def _payload(chunk_texts: list[str]) -> dict[str, Any]:
        return {
            "evidences": [
                {"chunk_id": f"chunk-{index}", "text": text, "page_no": index}
                for index, text in enumerate(chunk_texts, start=1)
            ]
        }

    if case.case_id in single_evidence_sets:
        return _payload(single_evidence_sets[case.case_id])
    if case.case_id in pair_evidence_sets:
        return _payload(pair_evidence_sets[case.case_id])
    if case.case_id == "project_contradiction_001":
        return _payload(contradiction_evidence)
    if case.case_id == "project_delegation_scaling_001":
        return _payload(scaling_evidence)
    return {"evidences": []}


def _web_search_payload(case: AgentEvalCase) -> str:
    """Simulated web results with dates; content matches each case's topic."""
    if case.case_id == "routing_discrimination_web_001":
        payload = {
            "results": [
                {
                    "title": "Tool Use After Toolformer: Native Function Calling Becomes Default",
                    "snippet": "2024 年以来，主流模型把原生函数调用接口作为标配，工具调用能力从外挂提示工程转为模型内建契约。",
                    "url": "https://example.com/blogs/native-function-calling-2024",
                    "date": "2024-09",
                },
                {
                    "title": "Training Paradigms for Internalized Tool Use",
                    "snippet": "2025 年的公开工作更多通过工具使用对齐数据让模型内化工具选择，agent 框架层则转向并行工具编排。",
                    "url": "https://example.com/blogs/internalized-tool-use-2025",
                    "date": "2025-03",
                },
            ]
        }
        return json.dumps(payload, ensure_ascii=False)
    payload = {
        "results": [
            {
                "title": "Retrieval-Augmented Generation: A Survey of Self-Reflective Variants",
                "snippet": "综述对比了 Self-RAG 及其后续方法：多个 2024-2025 年工作在相同开放域问答基准上报告超过 Self-RAG 的结果，同时指出自反思链路带来更高延迟与工程复杂度。",
                "url": "https://example.com/surveys/self-reflective-rag-2025",
                "date": "2025-06",
            },
            {
                "title": "Production Notes on Self-Reflective RAG Adoption",
                "snippet": "工程实践记录显示，Self-RAG 类方法的落地关注点已从论文指标转向系统集成：延迟预算、成本观测与失败案例复盘成为主要议题。",
                "url": "https://example.com/blogs/self-rag-production-2025",
                "date": "2025-11",
            },
        ]
    }
    return json.dumps(payload, ensure_ascii=False)
