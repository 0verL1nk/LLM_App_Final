from langchain_text_splitters import RecursiveCharacterTextSplitter

from agent.adapters.ocr_profile import OcrProfile, paddlex_cache_dir, select_ocr_profile
from agent.adapters.paddle_ocr import (
    _office_kind,
    _persist_preview_pages,
    _render_document_pages,
    extract_document_with_paddle_ocr,
)
from agent.rag.hybrid import _build_project_doc_index_artifact


class _FakePipeline:
    def __init__(self, pages):
        self.pages = iter(pages)

    def predict(self, _path):
        return [next(self.pages)]


class _FakeEmbeddings:
    def embed_documents(self, values):
        return [[0.1, 0.2] for _ in values]


def test_paddle_ocr_preserves_coordinates_across_pages(monkeypatch, tmp_path):
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"pdf")
    images = [tmp_path / "page-1.png", tmp_path / "page-2.png"]
    monkeypatch.setattr(
        "agent.adapters.paddle_ocr._render_document_pages",
        lambda _file_path, _output_dir: images,
    )
    pipeline = _FakePipeline(
        [
            {
                "rec_texts": ["第一页"],
                "rec_scores": [0.99],
                "rec_polys": [[[0, 0], [20, 0], [20, 10], [0, 10]]],
            },
            {
                "rec_texts": ["第二页"],
                "rec_scores": [0.98],
                "rec_polys": [[[0, 20], [20, 20], [20, 30], [0, 30]]],
            },
        ]
    )

    payload = extract_document_with_paddle_ocr(
        str(source),
        pipeline_factory=lambda _profile: pipeline,
    )

    assert payload["text"] == "第一页\n\n第二页"
    assert payload["source_spans"][0]["page_no"] == 1
    assert payload["source_spans"][0]["start"] == 0
    assert payload["source_spans"][1]["page_no"] == 2
    assert payload["source_spans"][1]["start"] == 5


def test_index_metadata_keeps_multiple_page_locations():
    artifact = _build_project_doc_index_artifact(
        project_uid="p1",
        doc_uid="d1",
        doc_name="paper.pdf",
        normalized_text="第一页\n\n第二页",
        source_spans=[
            {"start": 0, "end": 3, "page_no": 1, "polygon": [[0, 0]]},
            {"start": 5, "end": 8, "page_no": 2, "polygon": [[0, 20]]},
        ],
        settings_signature="test",
        text_hash="hash",
        splitter=RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=0, add_start_index=True),
        embeddings=_FakeEmbeddings(),
    )

    metadata = artifact["metadatas"][0]
    assert metadata["page_no"] == 1
    assert [item["page_no"] for item in metadata["ocr_locations"]] == [1, 2]


class _StructuredResult:
    markdown = {"markdown_texts": "# 跨页标题\n\n连续表格"}

    def json(self):
        return {
            "page_index": 0,
            "parsing_res_list": [
                {"block_content": "跨页标题", "block_bbox": [10, 20, 110, 60]},
                {"block_content": "连续表格", "block_bbox": [10, 80, 200, 180]},
            ],
        }


class _StructuredPipeline:
    def predict(self, _paths):
        return ["page-one", "page-two"]

    def restructure_pages(self, _results, **_kwargs):
        return [_StructuredResult()]


def test_cross_page_vl_keeps_layout_locations(monkeypatch, tmp_path):
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"pdf")
    monkeypatch.setattr(
        "agent.adapters.paddle_ocr._render_document_pages",
        lambda _file_path, _output_dir: [tmp_path / "page-1.png", tmp_path / "page-2.png"],
    )
    monkeypatch.setattr(
        "agent.adapters.paddle_ocr.select_ocr_profile",
        lambda: OcrProfile("high_accuracy", "det", "rec", "gpu:0"),
    )
    monkeypatch.setattr(
        "agent.adapters.paddle_ocr.create_cross_page_pipeline",
        lambda *, device: _StructuredPipeline(),
    )
    monkeypatch.setattr("agent.adapters.paddle_ocr._can_use_cross_page_vl", lambda _profile: True)

    payload = extract_document_with_paddle_ocr(str(source))

    assert payload["parser"] == "paddleocr-vl-cross-page"
    assert payload["format"] == "markdown"
    assert payload["text"] == "# 跨页标题\n\n连续表格"
    assert payload["source_spans"] == [
        {
            "start": 2,
            "end": 6,
            "page_no": 1,
            "polygon": [[10.0, 20.0], [110.0, 20.0], [110.0, 60.0], [10.0, 60.0]],
            "confidence": None,
        },
        {
            "start": 8,
            "end": 12,
            "page_no": 1,
            "polygon": [[10.0, 80.0], [200.0, 80.0], [200.0, 180.0], [10.0, 180.0]],
            "confidence": None,
        },
    ]


def test_office_com_converter_selects_supported_file_kinds(tmp_path):
    assert _office_kind(tmp_path / "paper.docx") == "word"
    assert _office_kind(tmp_path / "slides.pptx") == "powerpoint"
    assert _office_kind(tmp_path / "data.xlsx") == "excel"
    assert _office_kind(tmp_path / "paper.pdf") is None


def test_persisted_preview_pages_match_ocr_page_order(tmp_path):
    pages = [tmp_path / "source-one.png", tmp_path / "source-two.png"]
    pages[0].write_bytes(b"one")
    pages[1].write_bytes(b"two")

    persisted = _persist_preview_pages(pages, tmp_path / "previews")

    assert persisted == [
        {"page_no": 1, "file_name": "page-00001.png"},
        {"page_no": 2, "file_name": "page-00002.png"},
    ]
    assert (tmp_path / "previews/page-00001.png").read_bytes() == b"one"


def test_plain_text_is_typeset_into_a_preview_page(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("A locally rendered text document can be highlighted.", encoding="utf-8")

    pages = _render_document_pages(str(source), tmp_path / "rendered")

    assert [page.name for page in pages] == ["page-00001.png"]
    assert pages[0].is_file()


def _fake_runtime(monkeypatch, providers, memory_gib=16.0, cuda_driver=True):
    import sys
    from types import SimpleNamespace

    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(get_available_providers=lambda: providers),
    )
    monkeypatch.setitem(
        sys.modules,
        "psutil",
        SimpleNamespace(virtual_memory=lambda: SimpleNamespace(total=memory_gib * 1024**3)),
    )
    monkeypatch.setattr("agent.adapters.ocr_profile._cuda_runtime_usable", lambda: cuda_driver)


def test_gpu_profile_requires_nvidia_driver(monkeypatch):
    _fake_runtime(
        monkeypatch,
        ["CUDAExecutionProvider", "CPUExecutionProvider"],
        cuda_driver=False,
    )
    assert select_ocr_profile().device == "cpu"

    _fake_runtime(
        monkeypatch,
        ["CUDAExecutionProvider", "CPUExecutionProvider"],
        cuda_driver=True,
    )
    assert select_ocr_profile().device == "gpu:0"

    from agent.adapters.ocr_profile import ocr_runtime_capability

    assert ocr_runtime_capability() == {
        "profile": "high_accuracy",
        "device": "gpu:0",
        "gpu_enabled": True,
        "driver_available": True,
    }


def test_gpu_pipeline_failure_falls_back_to_cpu(monkeypatch, tmp_path):
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"pdf")
    monkeypatch.setattr(
        "agent.adapters.paddle_ocr._render_document_pages",
        lambda _file_path, _output_dir: [tmp_path / "page-1.png"],
    )
    monkeypatch.setattr(
        "agent.adapters.paddle_ocr.select_ocr_profile",
        lambda: OcrProfile("high_accuracy", "det", "rec", "gpu:0"),
    )
    monkeypatch.setattr("agent.adapters.paddle_ocr._can_use_cross_page_vl", lambda _profile: False)

    requested_devices = []

    def factory(profile):
        requested_devices.append(profile.device)
        if profile.device.startswith("gpu"):
            raise RuntimeError("CUDA session creation failed")
        return _FakePipeline(
            [
                {
                    "rec_texts": ["文本"],
                    "rec_scores": [0.9],
                    "rec_polys": [[[0, 0], [10, 0], [10, 10], [0, 10]]],
                }
            ]
        )

    payload = extract_document_with_paddle_ocr(str(source), pipeline_factory=factory)

    assert requested_devices == ["gpu:0", "cpu"]
    assert payload["text"] == "文本"
    assert payload["ocr_profile"] == "balanced"


def test_cache_dir_prefers_models_root(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENT_OCR_CACHE_DIR", raising=False)
    monkeypatch.setenv("LOCAL_MODELS_ROOT", str(tmp_path))
    assert paddlex_cache_dir() == tmp_path / "paddleocr"

    override = tmp_path / "custom-cache"
    monkeypatch.setenv("AGENT_OCR_CACHE_DIR", str(override))
    assert paddlex_cache_dir() == override
