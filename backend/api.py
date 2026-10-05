"""Run the local FastAPI development server."""

from pathlib import Path

from dotenv import load_dotenv

import uvicorn


backend_dir = Path(__file__).resolve().parent
repo_dir = backend_dir.parent
load_dotenv(repo_dir / ".env")
load_dotenv(backend_dir / ".env.local", override=True)
load_dotenv(backend_dir / ".env", override=True)


if __name__ == "__main__":
    uvicorn.run("sora_semantic.api:app", host="127.0.0.1", port=8000)
