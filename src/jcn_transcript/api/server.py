"""Server entrypoint for running the API."""

import uvicorn

from ..config import settings


def run():
    uvicorn.run(
        "jcn_transcript.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    run()
