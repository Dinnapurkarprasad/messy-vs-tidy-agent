"""The run loop both agents share, so they are run and measured exactly the same way.

The agent's own file must set LANGSMITH_PROJECT *before* importing this (it imports LangChain).
"""

import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage

from shared.llm import get_llm
from shared.task import DEFAULT_TOPICS, SYSTEM_PROMPT, build_task
from shared.tools import ALL_TOOLS

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


def run(middleware: list, output_file: Path):
    """Build the agent with the given middleware, run it on the topics from the command line, save the answer."""
    topics = sys.argv[1:] or DEFAULT_TOPICS
    task = build_task(topics)
    print(f"Topics: {topics}")

    agent = create_agent(model=get_llm(), tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT, middleware=middleware)

    answer = None
    # stream() runs the loop and hands us each step as it happens.
    for step in agent.stream(
        {"messages": [{"role": "user", "content": task}]},
        config={"recursion_limit": RECURSION_LIMIT},
        stream_mode="updates",
    ):
        # step = {"model": {...}}, {"tools": {...}}, or a middleware step like
        # {"SummarizationMiddleware.before_model": {...}} when middleware rewrites the context.
        for node, update in step.items():
            if node not in ("model", "tools") and update:
                print(f"\n[middleware] {node} rewrote the context")
            for msg in (update or {}).get("messages", []):
                show(msg)
                if isinstance(msg, AIMessage):
                    answer = msg.content

    print("\n" + "=" * 60 + "\nFINAL ANSWER\n" + "=" * 60 + "\n" + answer)
    output_file.parent.mkdir(exist_ok=True)
    output_file.write_text(answer, encoding="utf-8")
    print(f"\nSaved to {output_file}")
