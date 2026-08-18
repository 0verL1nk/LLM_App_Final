from agent.paper_prompt import build_paper_system_prompt
from agent.prompts.base import build_base_agent_prompt
from agent.prompts.paper_domain import build_paper_domain_prompt


def test_base_prompt_is_generic_and_not_paper_specific():
    prompt = build_base_agent_prompt()

    assert "专业论文问答 Agent" not in prompt
    assert "search_document" not in prompt
    assert "<evidence>" not in prompt
    assert "输出语言默认跟随用户输入语言" in prompt


def test_paper_domain_prompt_carries_paper_specific_retrieval_rules():
    prompt = build_paper_domain_prompt(
        document_name="文档A",
        project_name="项目A",
        scope_summary="范围A",
    )

    assert "专业论文问答 Agent" not in prompt
    assert "search_document" in prompt
    assert "<evidence>" in prompt
    assert "不要再次检索" in prompt
    assert "should_stop" in prompt
    assert "delegate_task" in prompt
    assert "不能用来浏览大目录" in prompt
    assert "当前对话项目：项目A" in prompt


def test_paper_domain_prompt_defines_plan_and_delegation_triggers():
    prompt = build_paper_domain_prompt(
        document_name="文档A",
        project_name="项目A",
        scope_summary="范围A",
    )

    # 多步任务先建计划的触发规则
    assert "update_plan" in prompt
    assert "带依赖关系的执行计划" in prompt
    # 委派触发条件与同轮并行约束
    assert "对比 2 篇以上文档" in prompt
    assert "并行发出多个 delegate_task 调用" in prompt


def test_paper_system_prompt_combines_generic_base_domain_and_leader_role():
    prompt = build_paper_system_prompt(
        document_name="文档A",
        project_name="项目A",
        scope_summary="范围A",
    )

    assert "你是通用智能 Agent" in prompt
    assert "search_document" in prompt
    assert "你负责调度与最终回答" in prompt
