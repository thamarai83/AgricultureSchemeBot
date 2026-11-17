import os
from pathlib import Path


def get_embeddings():
    from dotenv import load_dotenv
    from langchain_openai import OpenAIEmbeddings

    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        raise RuntimeError(
            "Set a valid OPENAI_API_KEY in the project .env file before processing PDFs."
        )

    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=api_key,
    )
