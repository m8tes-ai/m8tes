"""The package entry example must work with the new API-account defaults."""

from pathlib import Path
import re

import pytest

from m8tes import RunFailedError
from m8tes.testing import MockM8tes, StreamBuilder


@pytest.mark.parametrize("failed", [False, True])
def test_readme_first_run_is_scoped_and_surfaces_failures(monkeypatch, capsys, failed):
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text()
    snippet = re.search(r"```python\n(.*?)```", readme, re.S)
    assert snippet
    client = MockM8tes()
    stream = StreamBuilder().metadata(run_id=42)
    stream = stream.error("Provider unavailable") if failed else stream.text("Hello")
    client.mock.add("POST", "/runs/", stream=stream.done())
    monkeypatch.setattr("m8tes.M8tes", lambda: client)
    if failed:
        with pytest.raises(RunFailedError):
            exec(snippet.group(1), {})
    else:
        exec(snippet.group(1), {})
        assert "Hello" in capsys.readouterr().out
    assert len(client.mock.calls) == 1  # No persistent account-setting mutation.
    assert client.mock.calls[0].json["user_id"] == "hello_world"
    assert client.mock.calls[0].json["model"] == "deepseek-v4-1-flash"
