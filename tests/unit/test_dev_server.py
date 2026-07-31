from __future__ import annotations

from scripts import dev_server


class _Process:
    def __init__(self, poll_results: list[int | None]) -> None:
        self._poll_results = iter(poll_results)
        self.returncode: int | None = None
        self.terminated = False

    def poll(self) -> int | None:
        value = next(self._poll_results, self.returncode)
        if value is not None:
            self.returncode = value
        return value

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return self.returncode or 0

    def kill(self) -> None:
        self.returncode = -9


def test_dev_server_keeps_running_after_normal_poll_timeout(monkeypatch) -> None:
    api = _Process([None, 0])
    web = _Process([None, None, None])
    processes = iter([api, web])
    sleeps: list[float] = []

    monkeypatch.setattr(dev_server.subprocess, "Popen", lambda *args, **kwargs: next(processes))
    monkeypatch.setattr(dev_server.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert dev_server.main() == 0
    assert sleeps == [0.2]
    assert web.terminated is True
