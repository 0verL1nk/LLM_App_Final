from agent.application.a2ui_fragments import A2UIFragmentStreamParser, parse_ui_fragment


def test_stream_parser_keeps_markdown_and_hides_complete_ui_fragment() -> None:
    text: list[str] = []
    fragments = []
    errors: list[str] = []
    parser = A2UIFragmentStreamParser(on_text=text.append, on_fragment=fragments.append, on_error=errors.append)

    for token in ["结论。\n<ui type=\"research-", "map\"><map title=\"结构\"><node label=\"论文\"><evidence ref=\"chunk-1\" />", "</node></map></ui>\n继续。"]:
        parser.feed(token)
    parser.finish()

    assert "".join(text) == "结论。\n\n继续。"
    assert not errors
    assert fragments[0].payload["root"]["citation_ids"] == ["chunk-1"]


def test_stream_parser_discards_incomplete_ui_fragment() -> None:
    text: list[str] = []
    errors: list[str] = []
    parser = A2UIFragmentStreamParser(on_text=text.append, on_fragment=lambda _item: None, on_error=errors.append)
    parser.feed("正文\n<ui type=\"research-map\"><map title=\"x\">")
    parser.finish()

    assert "".join(text) == "正文\n"
    assert errors == ["UI fragment ended before its closing tag"]


def test_fragment_rejects_unknown_xml_elements() -> None:
    assert parse_ui_fragment("research-map", '<map title="x"><script /></map>') is None


def test_stream_parser_leaves_ui_examples_inside_fenced_code_untouched() -> None:
    text: list[str] = []
    parser = A2UIFragmentStreamParser(
        on_text=text.append,
        on_fragment=lambda _item: None,
        on_error=lambda _message: None,
    )
    parser.feed('```xml\n<ui type="research-map">\n</ui>\n```')
    parser.finish()

    assert "".join(text) == '```xml\n<ui type="research-map">\n</ui>\n```'
