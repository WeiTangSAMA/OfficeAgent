from app.schemas import TaskResult

def test_structured_result_roundtrip():
    result=TaskResult(summary="完成",findings=[],citations=[],warnings=[],artifact_ids=[])
    assert result.model_dump()["summary"]=="完成"
