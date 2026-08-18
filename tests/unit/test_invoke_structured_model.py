from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from agent.llm_provider import invoke_structured_model


class _Verdict(BaseModel):
    score: bool
    comment: str = ""


class _ScriptedLLM:
    """Returns queued contents in order; raises when the queue is empty."""

    def __init__(self, contents: list[str]) -> None:
        self._contents = list(contents)
        self.call_count = 0

    def invoke(self, messages: Any) -> SimpleNamespace:
        self.call_count += 1
        return SimpleNamespace(content=self._contents.pop(0))


def test_invoke_structured_model_retries_malformed_json_once() -> None:
    llm = _ScriptedLLM(
        [
            '{"reasoning": "long text with a break here", "score": false',  # malformed
            '{"score": true, "comment": "ok"}',
        ]
    )

    verdict = invoke_structured_model(llm, _Verdict, [{"role": "user", "content": "判定"}])

    assert verdict.score is True
    assert llm.call_count == 2


def test_invoke_structured_model_raises_after_second_failure() -> None:
    llm = _ScriptedLLM(["{not json", "{also not json"])

    with pytest.raises(Exception):
        invoke_structured_model(llm, _Verdict, [{"role": "user", "content": "判定"}])

    assert llm.call_count == 2


def test_invoke_structured_model_parses_first_valid_response() -> None:
    llm = _ScriptedLLM(['{"score": false, "comment": "fail"}'])

    verdict = invoke_structured_model(llm, _Verdict, [{"role": "user", "content": "判定"}])

    assert verdict.score is False
    assert llm.call_count == 1
