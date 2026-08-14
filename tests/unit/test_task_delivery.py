from agent.application import task_delivery


def test_outbox_transport_does_not_start_work_in_the_api_process(monkeypatch) -> None:
    monkeypatch.setenv("PAPERSAGE_TASK_TRANSPORT", "outbox")

    result = task_delivery.dispatch_task(task_uid="task-1")

    assert result is None


def test_unknown_task_transport_fails_configuration_fast(monkeypatch) -> None:
    monkeypatch.setenv("PAPERSAGE_TASK_TRANSPORT", "invalid")

    try:
        task_delivery.dispatch_task(task_uid="task-1")
    except ValueError as exc:
        assert "PAPERSAGE_TASK_TRANSPORT" in str(exc)
    else:
        raise AssertionError("Expected invalid transport configuration to fail")
