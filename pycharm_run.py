"""PyCharm one-click launcher for the Office Document Agent.

Create a normal Python Run Configuration and select this file as the script.
The launcher starts both the FastAPI server and the background task worker.
"""

from __future__ import annotations

import multiprocessing
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"

# Make `app` importable regardless of PyCharm's configured working directory.
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _run_worker() -> None:
    """Child-process entry point; it must stay at module scope on Windows."""
    from app.worker import main

    main()


class OfficeDocumentAgentApplication:
    """Starts the API and worker as a single local desktop application."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        start_worker: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.start_worker = start_worker
        self._worker: multiprocessing.Process | None = None

    def run(self) -> None:
        # Settings uses a relative `.env` and data directory by default.
        os.chdir(PROJECT_ROOT)
        multiprocessing.freeze_support()

        # Importing the FastAPI app initializes the SQLite schema. Do this in
        # the parent before spawning the worker to avoid concurrent CREATE
        # TABLE races on a brand-new local database.
        from app.main import app

        if self.start_worker:
            self._worker = multiprocessing.Process(
                target=_run_worker,
                name="office-document-agent-worker",
                daemon=True,
            )
            self._worker.start()
            print(f"Worker 已启动，PID: {self._worker.pid}")

        import uvicorn

        print("\n办公文档 Agent 已启动")
        print(f"工作台: http://{self.host}:{self.port}")
        print(f"API 文档: http://{self.host}:{self.port}/docs")
        print("按 Ctrl+C 停止 API 和 worker。\n")

        try:
            uvicorn.run(app, host=self.host, port=self.port, log_level="info")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the child worker when PyCharm stops the run configuration."""
        if self._worker and self._worker.is_alive():
            self._worker.terminate()
            self._worker.join(timeout=5)
        self._worker = None


if __name__ == "__main__":
    OfficeDocumentAgentApplication().run()
