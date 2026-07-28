"""A failed run must be loud when the caller asks for it.

`create_and_wait` returned a `failed` Run normally, so the documented quickstart
usage — `print(result.output)` — printed the platform's generic failure sentence
in exactly the place the agent's answer belongs. The server-side twin of this fix
stamps `error`/`error_code` onto the run so there is something to raise WITH.

`raise_on_error` is opt-in, matching `runs.create(..., raise_on_error=True)` on
the streaming path, so nothing existing changes behaviour.
"""

from unittest.mock import MagicMock, patch

import pytest

from m8tes import RunFailedError
from m8tes._resources.runs import Runs
from m8tes._types import Run


def _run(status: str, **kw) -> Run:
    return Run.from_dict(
        {
            "id": 10853,
            "status": status,
            "output": kw.get("output"),
            "error": kw.get("error"),
            "error_code": kw.get("error_code"),
        }
    )


def _runs_with(run: Run) -> Runs:
    r = Runs(MagicMock())
    r.get = MagicMock(return_value=run)  # type: ignore[method-assign]
    return r


def test_poll_returns_failed_run_by_default():
    """Default is unchanged — this is what makes the flag non-breaking."""
    failed = _run("failed", error="The run stopped: its sandbox could not be provisioned.")
    assert _runs_with(failed).poll(10853).status == "failed"


def test_poll_raises_when_asked():
    failed = _run(
        "failed",
        error="The run stopped: its sandbox could not be provisioned.",
        error_code="sandbox_unavailable",
    )
    with pytest.raises(RunFailedError) as exc:
        _runs_with(failed).poll(10853, raise_on_error=True)
    assert "sandbox could not be provisioned" in str(exc.value)
    assert exc.value.details["error_code"] == "sandbox_unavailable"
    assert exc.value.details["run_id"] == 10853


def test_completed_run_never_raises():
    done = _run("completed", output="here is your draft")
    assert _runs_with(done).poll(10853, raise_on_error=True).output == "here is your draft"


def test_message_falls_back_to_output_when_error_is_null():
    """Legacy rows predate the server-side error stamping and have error=None."""
    failed = _run("failed", output="An error occurred during agent execution setup")
    with pytest.raises(RunFailedError) as exc:
        _runs_with(failed).poll(10853, raise_on_error=True)
    assert "An error occurred during agent execution setup" in str(exc.value)


def test_create_and_wait_propagates_the_flag():
    """The flag is useless if create_and_wait swallows it — the quickstart path."""
    failed = _run("failed", error="boom", error_code="sandbox_unavailable")
    r = Runs(MagicMock())
    r.create = MagicMock(return_value=_run("running"))  # type: ignore[method-assign]
    r.get = MagicMock(return_value=failed)  # type: ignore[method-assign]
    with patch("time.sleep"), pytest.raises(RunFailedError):
        r.create_and_wait(message="hi", raise_on_error=True)
