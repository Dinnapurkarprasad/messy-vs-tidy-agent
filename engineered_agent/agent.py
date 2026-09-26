"""Engineered agent: same model, tools, task and prompt as the naive agent, plus context engineering.

Strategies (all in middleware.py):
    [x] Compress  - SUMMARIZE: summarize old history once it gets big
    [x] Select    - select_tools: hide tools the task doesn't need
    [x] Write     - offload_big_outputs: big tool results go to a file, only a preview stays

To measure one strategy at a time, remove the others from the list below.

Run from the project root:
    python -m engineered_agent.agent                     # default 5 topics
    python -m engineered_agent.agent "Docker" "Linux"    # your own topics
"""

import os

# Must be set before LangChain is imported, so every trace lands in this LangSmith project.
os.environ["LANGSMITH_PROJECT"] = "engineered-agent"

from pathlib import Path

from engineered_agent.middleware import SUMMARIZE, offload_big_outputs, select_tools
from shared.llm import RETRY
from shared.runner import run

if __name__ == "__main__":
    run(middleware=[RETRY, SUMMARIZE, select_tools, offload_big_outputs],
        output_file=Path("results/engineered_output.md"))
