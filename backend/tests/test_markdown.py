import hashlib
import uuid

import pytest

from app.services.markdown import parse_markdown


def test_chunks_preserve_exact_text_lines_and_heading_hierarchy() -> None:
    content = "# 项目\r\n\r\n第一段。\r\n下一行。\r\n\r\n## 决策\r\n- 使用事务\r\n  - 保留证据\r\n\r\n- 重试\r\n\r\n```python\r\n# 不是标题\r\nprint(1)\r\n```\r\n\r\n## 结果\r\n完成。"
    source_id = uuid.uuid4()
    chunks = parse_markdown(content, source_id=source_id)
    assert [chunk.kind for chunk in chunks] == [
        "heading", "paragraph", "heading", "list", "code", "heading", "paragraph",
    ]
    assert [(chunk.start_line, chunk.end_line) for chunk in chunks] == [
        (1, 1), (3, 4), (6, 6), (7, 10), (12, 15), (17, 17), (18, 18),
    ]
    assert chunks[3].heading_path == ["项目", "决策"]
    assert chunks[-1].heading_path == ["项目", "结果"]
    lines = content.splitlines(keepends=True)
    for chunk in chunks:
        assert chunk.content == "".join(lines[chunk.start_line - 1:chunk.end_line])
        assert chunk.content_sha256 == hashlib.sha256(chunk.content.encode()).hexdigest()
    assert parse_markdown(content, source_id=source_id) == chunks
    assert parse_markdown(content, source_id=uuid.uuid4())[0].id != chunks[0].id


@pytest.mark.parametrize(("content", "kinds", "paths"), [
    ("\ufeff标题\n====\n\n小节\n----\n内容", ["heading", "heading", "paragraph"], [["标题"], ["标题", "小节"], ["标题", "小节"]]),
    ("# 根\n### 跳级 ###\n## 同级替换\n# 新根\n", ["heading"] * 4, [["根"], ["根", "跳级"], ["根", "同级替换"], ["新根"]]),
    ("~~~\n## 代码标题\n- 代码列表", ["code"], [[]]),
    ("````js\n```\n# 内部\n````\n外部", ["code", "paragraph"], [[], []]),
    ("普通段落\n\n---\n\n- 列表\n\n后文", ["paragraph", "paragraph", "list", "paragraph"], [[], [], [], []]),
    ("#无空格\n\n1. 一\n2. 二", ["paragraph", "list"], [[], []]),
    ("\n \n", [], []),
])
def test_structural_subset(content: str, kinds: list[str], paths: list[list[str]]) -> None:
    chunks = parse_markdown(content, source_id=uuid.uuid4())
    assert [chunk.kind for chunk in chunks] == kinds
    assert [chunk.heading_path for chunk in chunks] == paths
