"""Naive agent: the baseline. NO context management on purpose.

- sees all 12 tools on every call
- keeps the full message history
- raw tool outputs go straight into the context

Do not add any optimization here. That's the engineered agent's job.
(The only middleware is RETRY from shared/llm.py: it re-sends failed calls and never touches context.)

Run from the project root:
    python -m naive_agent.agent                     # default 5 topics
    python -m naive_agent.agent "Docker" "Linux"    # your own topics
"""

import os

# Must be set before LangChain is imported, so every trace lands in this LangSmith project.
os.environ["LANGSMITH_PROJECT"] = "naive-agent"

from pathlib import Path

from shared.llm import RETRY
from shared.runner import run

if __name__ == "__main__":
    run(middleware=[RETRY], output_file=Path("results/naive_output.md"))
