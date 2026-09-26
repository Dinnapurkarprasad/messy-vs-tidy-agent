"""All context engineering for the engineered agent lives here.

Each middleware says which of the 4 strategies (write, select, compress, isolate) it implements
and which problem it solves.
"""

import re
import uuid
from pathlib import Path

from langchain.agents.middleware import SummarizationMiddleware, wrap_model_call, wrap_tool_call
from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage

from shared.llm import get_llm

# ---------------------------------------------------------------------------
# Strategy: COMPRESS (history summarization)
#
# Problem: every model call re-sends the whole conversation, so input tokens grow with
# every step (the naive run went 3.9k -> 7k+ tokens within 2 topics).
# Fix: once the history passes TRIGGER tokens, older messages are replaced by one summary
# written by the same model. The most recent ~KEEP tokens of messages stay word-for-word.
# Saved notes are not lost: they live outside the context and read_notes() brings them back.
# ---------------------------------------------------------------------------
SUMMARIZE = SummarizationMiddleware(
    model=get_llm(),
    trigger=("tokens", 6000),  # the naive run passed 7k during topic 2
    keep=("tokens", 2500),
    trim_tokens_to_summarize=None,
)


# ---------------------------------------------------------------------------
# Strategy: SELECT (dynamic tool selection)
#
# Problem: every tool's name + description is sent on EVERY model call. The 6 distractor
# tools cost tokens each time and can tempt the model into wrong calls.
# Fix: before each model call, keep only the tools whose keywords appear in what the user
# asked. Simple rules, so it's easy to see why a tool was shown or hidden.
#
# Only user messages are checked (the task, or the summary that replaced it). Tool outputs
# are NOT checked: a Wikipedia article mentioning "weather" must not bring weather_stub back.
# ---------------------------------------------------------------------------
# ponytail: keyword rules only know the tools and task wording we have; an LLM-based selector
# is the upgrade if tasks get more varied.
TOOL_KEYWORDS = {
    # useful for research
    "web_search":       ["research", "recent", "latest", "news", "search", "development"],
    "wikipedia_lookup": ["research", "what it is", "started", "history", "background", "wikipedia"],
    "save_note":        ["note", "notes", "save"],
    "read_notes":       ["note", "notes"],
    "calculator":       ["calculate", "compute", "math", "how many", "year", "years"],
    "get_current_date": ["recent", "latest", "today", "current", "date"],
    # distractors: only shown if the user really asks for these things
    "unit_converter":   ["convert", "conversion", "unit", "units", "km", "miles", "kg", "pounds"],
    "word_count":       ["word count", "count words", "count the words"],
    "reverse_text":     ["reverse"],
    "random_number":    ["random"],
    "weather_stub":     ["weather", "temperature", "forecast"],
    "currency_stub":    ["currency", "exchange rate", "usd", "eur", "inr"],
}


def pick_tools(tools, messages):
    """Return only the tools whose keywords appear in the user messages.

    Tools without rules (like read_workspace_file) always stay. If no rule matches at all,
    return every tool rather than leave the model with nothing.
    """
    text = " ".join(m.text for m in messages if isinstance(m, HumanMessage)).lower()

    def wanted(t):
        # \b = whole words only, so "unit" doesn't match "community" and "sum" isn't in "summary"
        return t.name not in TOOL_KEYWORDS or any(
            re.search(rf"\b{re.escape(k)}\b", text) for k in TOOL_KEYWORDS[t.name])

    picked = [t for t in tools if wanted(t)]
    return picked if any(t.name in TOOL_KEYWORDS for t in picked) else tools


@wrap_model_call
def select_tools(request, handler):
    return handler(request.override(tools=pick_tools(request.tools, request.messages)))


# ---------------------------------------------------------------------------
# Strategy: WRITE (offload large tool outputs to files)
#
# Problem: one Wikipedia article is ~8000 chars (~2000 tokens), and once it's in the history
# the model re-reads it on every later call.
# Fix: if a tool result is longer than OFFLOAD_OVER_CHARS, save the full text to
# results/workspace/<file_id>.txt and put only a short preview + the file id in the context.
# The agent can fetch the full text with read_workspace_file() when it really needs it.
# ---------------------------------------------------------------------------
WORKSPACE = Path("results/workspace")
OFFLOAD_OVER_CHARS = 1500
PREVIEW_CHARS = 500


@tool
def read_workspace_file(file_id: str) -> str:
    """Read the full text of a large tool result that was saved to the workspace.
    Only use this when the short preview you got is not enough."""
    path = WORKSPACE / f"{file_id}.txt"
    # file_id must be a plain name, so the model can't read files outside the workspace
    if not re.fullmatch(r"[\w-]+", file_id) or not path.exists():
        return f"No workspace file '{file_id}'."
    return path.read_text(encoding="utf-8")


@wrap_tool_call(tools=[read_workspace_file])  # tools=[...] adds this tool to the agent
def offload_big_outputs(request, handler):
    result = handler(request)  # run the tool normally first
    name = request.tool_call["name"]
    # Never offload read_workspace_file's own output, or reading a file would just save it again.
    if not isinstance(result, ToolMessage) or name == "read_workspace_file":
        return result
    content = str(result.content)
    if len(content) <= OFFLOAD_OVER_CHARS:
        return result

    file_id = f"{name}-{uuid.uuid4().hex[:8]}"
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    (WORKSPACE / f"{file_id}.txt").write_text(content, encoding="utf-8")
    preview = (f"{content[:PREVIEW_CHARS]}...\n\n[Full output ({len(content)} chars) saved as "
               f"file_id='{file_id}'. Call read_workspace_file only if you need more than this.]")
    return result.model_copy(update={"content": preview})
