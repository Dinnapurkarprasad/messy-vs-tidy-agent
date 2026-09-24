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

import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage

from shared.llm import RETRY, get_llm
from shared.task import DEFAULT_TOPICS, SYSTEM_PROMPT, build_task
from shared.tools import ALL_TOOLS

OUTPUT_FILE = Path("results/naive_output.md")
RECURSION_LIMIT = 100  # max graph steps; each model call and each tool round counts as one


def show(msg):
    """Print one step so you can watch the agent think. Printing only, doesn't change the context."""
    if isinstance(msg, AIMessage):
        u = msg.usage_metadata or {}
        print(f"\n[model] input={u.get('input_tokens')} output={u.get('output_tokens')} tokens")
        for call in msg.tool_calls:
            print(f"  -> wants {call['name']}({str(call['args'])[:100]})")
    elif isinstance(msg, ToolMessage):
        print(f"[tool]  {msg.name} returned {len(msg.content)} chars")


def main():
    topics = sys.argv[1:] or DEFAULT_TOPICS
    task = build_task(topics)
    print(f"Topics: {topics}")

    # RETRY only re-sends a failed call; it never changes the context.
    agent = create_agent(model=get_llm(), tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT, middleware=[RETRY])

    last = None
    # stream() runs the loop and hands us each step as it happens.
    for step in agent.stream(
        {"messages": [{"role": "user", "content": task}]},
        config={"recursion_limit": RECURSION_LIMIT},
        stream_mode="updates",
    ):
        for update in step.values():  # step = {"model": {...}} or {"tools": {...}}
            for msg in (update or {}).get("messages", []):
                show(msg)
                last = msg

    answer = last.content
    print("\n" + "=" * 60 + "\nFINAL ANSWER\n" + "=" * 60 + "\n" + answer)

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(answer, encoding="utf-8")
    print(f"\nSaved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
