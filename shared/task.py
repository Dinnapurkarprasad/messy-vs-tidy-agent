"""The system prompt and research task both agents run. Change them here only.

Both agents must get the SAME topics for a fair comparison.
"""

SYSTEM_PROMPT = (
    "You are a careful research assistant. Use the available tools to gather facts, "
    "save your findings as notes, and base your final answer on your notes. "
    "Only call a tool when it helps the task."
)

# Used when you don't pass topics on the command line.
DEFAULT_TOPICS = ["Python (programming language)", "Rust (programming language)", "PostgreSQL",
                  "MongoDB", "James Webb Space Telescope"]


def build_task(topics: list[str]) -> str:
    """Turn a list of topics into the research task text the agent receives."""
    return f"""Research these {len(topics)} topics: {", ".join(topics)}.

For each topic find:
1. What it is (one sentence)
2. When it started (year)
3. One recent development

Save one note per topic as you go.

When all {len(topics)} are done, read your notes and produce:
- A markdown comparison table with columns: Topic | What it is | Started | Recent development
- A final summary of about 200 words comparing all of them."""
