import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm():
    """The one model both agents use. Never create a model anywhere else."""
    return ChatOpenAI(
        model=os.environ["MODEL_NAME"],
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        max_retries=6,  # free tier returns 429 often; client waits and retries with backoff
    )


if __name__ == "__main__":
    reply = get_llm().invoke("Say hello in 5 words.")
    print(reply.content)
    print(reply.usage_metadata)
