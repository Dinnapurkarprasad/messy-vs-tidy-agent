import os

from dotenv import load_dotenv
from langchain.agents.middleware import ModelRetryMiddleware
from langchain_openai import ChatOpenAI

load_dotenv()

# Reliability, NOT context engineering: both agents get it so a free-tier hiccup doesn't kill a run.
# max_retries below only covers HTTP errors; OpenRouter sometimes sends errors like
# "504 A Timeout Occurred" inside a normal response, which only this catches.
RETRY = ModelRetryMiddleware(max_retries=4, initial_delay=5, on_failure="error")


def get_llm():
    """The one model both agents use. Never create a model anywhere else."""
    return ChatOpenAI(
        model=os.environ["MODEL_NAME"],
        base_url=os.environ["LLM_BASE_URL"],  # any OpenAI-compatible provider: OpenRouter, Groq, ...
        api_key=os.environ["LLM_API_KEY"],
        max_retries=6,  # free tier returns 429 often; client waits and retries with backoff
    )


if __name__ == "__main__":
    reply = get_llm().invoke("Say hello in 5 words.")
    print(reply.content)
    print(reply.usage_metadata)
