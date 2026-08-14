from agent.rag.project_chunking import markdown_documents


def test_markdown_chunks_preserve_emitted_heading_path_and_neighbors() -> None:
    documents = markdown_documents(
        text="# 介绍\n\n第一段。\n\n## 方法\n\n第二段。",
        chunk_size=100,
        chunk_overlap=0,
    )

    assert [item.metadata["section_path"] for item in documents] == ["介绍", "介绍 > 方法"]
    assert documents[0].metadata["next_chunk_id"] == "chunk_1"
    assert documents[1].metadata["prev_chunk_id"] == "chunk_0"
