from agent.application.response_stream import ResponseStreamPartRouter


def test_routes_split_think_tags_to_reasoning_without_leaking_tags() -> None:
    text: list[str] = []
    reasoning: list[str] = []
    router = ResponseStreamPartRouter(on_text=text.append, on_reasoning=reasoning.append)

    for token in ["<th", "ink>先核验", "资料</th", "ink>\n结论"]:
        router.feed(token)
    router.finish()

    assert "".join(reasoning) == "先核验资料"
    assert "".join(text) == "\n结论"


def test_preserves_plain_markdown_that_is_not_a_reasoning_protocol_tag() -> None:
    text: list[str] = []
    router = ResponseStreamPartRouter(on_text=text.append, on_reasoning=lambda _value: None)

    router.feed("Use <evidence>chunk-1</evidence> in the answer.")
    router.finish()

    assert "".join(text) == "Use <evidence>chunk-1</evidence> in the answer."
