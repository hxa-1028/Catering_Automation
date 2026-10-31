"""Temporary worker process kept alive until the job queue is implemented."""

from __future__ import annotations

import signal
from threading import Event
from types import FrameType


def main() -> None:
    """Wait for shutdown without claiming to process unimplemented jobs."""

    shutdown_requested = Event()

    def request_shutdown(_: int, __: FrameType | None) -> None:
        shutdown_requested.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    shutdown_requested.wait()


if __name__ == "__main__":
    main()
