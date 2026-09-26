"""Tests for engineered_agent/middleware.py. No real model calls: a fake model writes the summary."""

from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage

from langchain.agents.middleware.types import ToolCallRequest

from engineered_agent import middleware
from engineered_agent.middleware import SUMMARIZE, offload_big_outputs, pick_tools, read_workspace_file
from shared.task import build_task
from shared.tools import ALL_TOOLS

USEFUL = {"web_search", "wikipedia_lookup", "save_note", "read_notes", "calculator", "get_current_date"}


def fake_history(rounds):
    """A task, then `rounds` model turns that each call 3 tools returning ~750 tokens apiece."""
    msgs = [HumanMessage("task", id="h")]
    for i in range(rounds):
        msgs.append(AIMessage("", id=f"a{i}", tool_calls=[
            {"name": "web_search", "args": {}, "id": f"c{i}{j}"} for j in range(3)]))
        msgs += [ToolMessage("x " * 1500, tool_call_id=f"c{i}{j}", id=f"t{i}{j}") for j in range(3)]
    return msgs


def summarizer():
    """Same trigger/keep settings as the real SUMMARIZE, but a fake model so nothing is sent anywhere."""
    return SummarizationMiddleware(model=FakeListChatModel(responses=["SUMMARY"]),
                                   trigger=SUMMARIZE.trigger, keep=SUMMARIZE.keep,
                                   trim_tokens_to_summarize=SUMMARIZE.trim_tokens_to_summarize)


def kept_messages(update):
    return [m for m in update["messages"] if not isinstance(m, RemoveMessage)]


def test_small_history_is_left_alone():
    assert summarizer().before_model({"messages": fake_history(1)}, None) is None


def test_big_history_gets_summarized():
    # Fails with the default trim_tokens_to_summarize: history becomes "too long to summarize".
    kept = kept_messages(summarizer().before_model({"messages": fake_history(4)}, None))
    assert isinstance(kept[0], HumanMessage) and "SUMMARY" in kept[0].content


def test_no_tool_result_kept_without_its_call():
    # The API rejects a tool result whose tool call was summarized away.
    kept = kept_messages(summarizer().before_model({"messages": fake_history(4)}, None))
    assert isinstance(kept[1], AIMessage)


def test_does_not_resummarize_right_away():
    # If keep were too close to trigger, every call would re-summarize (an extra LLM call each step).
    s = summarizer()
    kept = kept_messages(s.before_model({"messages": fake_history(4)}, None))
    assert s.before_model({"messages": kept}, None) is None


# --- SELECT -----------------------------------------------------------------

def names(tools):
    return {t.name for t in tools}


def test_research_task_shows_only_useful_tools():
    task = build_task(["Docker", "Kubernetes", "Linux"])
    assert names(pick_tools(ALL_TOOLS, [HumanMessage(task)])) == USEFUL


def test_distractor_shown_when_user_asks_for_it():
    picked = names(pick_tools(ALL_TOOLS, [HumanMessage("What's the weather in Pune? Save a note.")]))
    assert "weather_stub" in picked and "currency_stub" not in picked


def test_tool_outputs_dont_bring_distractors_back():
    task = HumanMessage(build_task(["Linux"]))
    wiki = ToolMessage("Linux runs weather stations and handles currency exchange.", tool_call_id="1")
    assert names(pick_tools(ALL_TOOLS, [task, wiki])) == USEFUL


def test_whole_words_only():
    # "summary" must not match "sum", "community" must not match "unit"
    picked = names(pick_tools(ALL_TOOLS, [HumanMessage("research the community, write a summary")]))
    assert "unit_converter" not in picked


def test_tools_without_rules_always_stay():
    picked = names(pick_tools(ALL_TOOLS + [read_workspace_file], [HumanMessage(build_task(["Linux"]))]))
    assert "read_workspace_file" in picked


def test_no_match_keeps_all_tools():
    assert len(pick_tools(ALL_TOOLS, [HumanMessage("hi")])) == len(ALL_TOOLS)


# --- WRITE ------------------------------------------------------------------

def run_offload(name, content):
    """Pretend a tool called `name` returned `content`, and pass it through the offload middleware."""
    request = ToolCallRequest(tool_call={"name": name, "args": {}, "id": "c1"}, tool=None, state={}, runtime=None)
    return offload_big_outputs.wrap_tool_call(request, lambda r: ToolMessage(content, tool_call_id="c1"))


def test_small_output_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(middleware, "WORKSPACE", tmp_path)  # write to a temp folder, not results/
    assert run_offload("web_search", "short").content == "short"
    assert not list(tmp_path.iterdir())


def test_big_output_saved_and_previewed(tmp_path, monkeypatch):
    monkeypatch.setattr(middleware, "WORKSPACE", tmp_path)
    big = "A" * 500 + "B" * 7500
    msg = run_offload("wikipedia_lookup", big)
    assert len(msg.content) < 1000 and "B" * 100 not in msg.content  # only the preview is in context
    (saved,) = tmp_path.iterdir()
    assert saved.read_text(encoding="utf-8") == big  # full text is on disk
    assert read_workspace_file.invoke({"file_id": saved.stem}) == big  # and the agent can get it back


def test_reading_a_file_is_not_offloaded_again(tmp_path, monkeypatch):
    monkeypatch.setattr(middleware, "WORKSPACE", tmp_path)
    big = "x" * 8000
    assert run_offload("read_workspace_file", big).content == big


def test_read_workspace_file_blocks_other_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(middleware, "WORKSPACE", tmp_path)
    assert read_workspace_file.invoke({"file_id": "../../.env"}).startswith("No workspace file")
