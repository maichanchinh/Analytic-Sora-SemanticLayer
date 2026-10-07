"""Run the local FastAPI development server."""

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

import uvicorn


backend_dir = Path(__file__).resolve().parent
repo_dir = backend_dir.parent
load_dotenv(repo_dir / ".env")
load_dotenv(backend_dir / ".env.local", override=True)
load_dotenv(backend_dir / ".env", override=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Sora Semantic Layer API locally.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show detailed application and Uvicorn debug logs.",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(
        "sora_semantic.api:app",
        host="127.0.0.1",
        port=8000,
        log_level="debug" if args.debug else "info",
        access_log=True,
    )
