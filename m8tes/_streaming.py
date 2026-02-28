"""RunStream — wraps AISDKStreamParser for developer-friendly streaming."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import TYPE_CHECKING

from .streaming import AISDKStreamParser, StreamAccumulator, StreamEvent

if TYPE_CHECKING:
    import requests


class RunStream:
    """Iterable stream of run events. Use as context manager or iterate directly.

    Usage:
        with client.runs.create(message="Do X") as stream:
            for event in stream:
                print(event.type, event.raw)
        print(stream.text)  # full accumulated text
    """

    def __init__(self, response: requests.Response):
        self._response = response
        self._accumulator = StreamAccumulator()
        self._closed = False

    def _close(self) -> None:
        """Close the underlying response (idempotent)."""
        if not self._closed:
            self._closed = True
            self._response.close()

    def __iter__(self) -> Iterator[StreamEvent]:
        try:
            for event in AISDKStreamParser.parse_stream(self._response):
                self._accumulator.process(event)
                yield event
        finally:
            self._close()

    def __enter__(self) -> RunStream:
        return self

    def __exit__(self, *_: object) -> None:
        self._close()

    @property
    def text(self) -> str:
        """Full accumulated assistant text after iteration."""
        return self._accumulator.get_text()

    @property
    def output(self) -> str:
        """Alias for text."""
        return self.text

    @property
    def run_id(self) -> int | None:
        """Run ID extracted from the metadata event.

        Available after the first metadata event arrives.
        """
        return self._accumulator.run_id

    def iter_text(self) -> Generator[str, None, None]:
        """Yield only text chunks — no event filtering needed.

        Usage:
            with client.runs.create(message="...") as stream:
                for chunk in stream.iter_text():
                    print(chunk, end="", flush=True)
            print(stream.run_id, stream.text)
        """
        from .streaming import TextDeltaEvent

        for event in self:
            if isinstance(event, TextDeltaEvent):
                yield event.delta
