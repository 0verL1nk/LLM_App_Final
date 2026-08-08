from agent.adapters.paddle_structure import reconstruct_cross_page_document


class _Pipeline:
    def __init__(self):
        self.arguments = None

    def restructure_pages(self, results, **kwargs):
        self.arguments = (results, kwargs)
        return ["merged"]


def test_cross_page_reconstruction_uses_official_semantic_options():
    pipeline = _Pipeline()
    assert reconstruct_cross_page_document(["page-1", "page-2"], pipeline=pipeline) == ["merged"]
    assert pipeline.arguments == (["page-1", "page-2"], {"merge_tables": True, "relevel_titles": True, "concatenate_pages": False})
