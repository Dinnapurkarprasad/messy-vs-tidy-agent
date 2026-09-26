# Context Engineering Agents: Naive vs Engineered

**Same agent. Same task. Same tools. Same model.**
One agent manages its context and the other doesn't. What changes?

---

## 1. What is this project?

We build **one research agent twice**:

- **Naive agent**: no context management. Everything piles up.
- **Engineered agent**: the same agent, plus **context engineering** (LangChain v1 middleware).

Both get the same job, for example:

> *"Research Docker, Kubernetes and Linux. For each: what it is, when it started, one recent development. Save a note per topic. Then make a comparison table and a 200-word summary."*

Both agents use the same model, tools, task and prompt from `shared/`. We then compare their tokens, time and tool calls in LangSmith.

### Why does context matter?

An LLM has **no memory**. On every step, the agent re-sends the **whole conversation**: instructions, task, every earlier message and every tool result. That pile is the **context**, and it gets bigger with every step.

A bigger context means more tokens (cost), slower answers, and a model that gets confused by noise.

### How an agent works

- A **tool** is a Python function the model can use. The model only sees its **name and description**.
- The model **asks** for a tool, LangChain **runs** it, and the result goes back to the model.
- This repeats until the model writes a final answer.

**Middleware** is code that runs inside this loop, before a model call or around a tool call. That's where the engineered agent cleans up the context.

---

## 2. What we want to see

If context engineering works, the engineered agent should show:

| What | Expected |
|---|---|
| Total tokens | Lower |
| Input tokens per model call | Stays flat instead of climbing |
| Time | Lower or about the same |
| Wrong (decoy) tool calls | Fewer |
| Answer quality | Same or better |

The numbers don't need to be dramatic. **Honest results with a clear explanation** are the goal.

---

## 3. Shared parts: the same for both agents

Everything both agents use lives in `shared/`, so the comparison is fair.

| File | What it does |
|---|---|
| `shared/llm.py` | `get_llm()`: the one model both agents use. `RETRY` re-sends failed calls |
| `shared/tools.py` | The 12 tools |
| `shared/task.py` | The system prompt and `build_task(topics)` |
| `shared/runner.py` | The run loop: build the agent, print each step, save the answer |

**The 12 tools:**

| 6 useful | 6 decoys (work fine, but the task never needs them) |
|---|---|
| `web_search`: DuckDuckGo search | `unit_converter` |
| `wikipedia_lookup`: article text, up to 8,000 chars | `word_count` |
| `save_note`: save a finding | `reverse_text` |
| `read_notes`: read saved notes | `random_number` |
| `calculator`: safe math | `weather_stub` (fake data) |
| `get_current_date` | `currency_stub` (fake data) |

**Why decoys?** Real agents often have many tools, and most don't matter for any given job. Each tool description is sent on every call, which costs tokens, and decoys can tempt the model into wrong calls.

---

## 4. Naive agent

`naive_agent/agent.py`, the baseline. It deliberately does **nothing** to manage context:

- sees **all 12 tools** on every call
- keeps the **full history** forever
- **raw tool outputs** (whole Wikipedia articles) go straight into the context

```python
run(middleware=[RETRY], output_file=Path("results/naive_output.md"))
```

`RETRY` only re-sends a call when the free model fails. It never changes the context, and both agents have it.

Expected: input tokens per call keep climbing with every step.

---

## 5. Engineered agent

`engineered_agent/agent.py`: the same agent plus 3 context engineering strategies. All logic is in `engineered_agent/middleware.py`.

```python
run(middleware=[RETRY, SUMMARIZE, select_tools, offload_big_outputs],
    output_file=Path("results/engineered_output.md"))
```

**Compared to the naive agent, the only difference is this middleware list.**

Before each model call, Compress and Select clean up what the model will see. After each tool call, Write shrinks big results.

### Compress: summarize old history (`SUMMARIZE`)

**Problem:** the history keeps growing, and every call re-sends all of it.

**Fix:** once the history passes **6,000 tokens**, the old messages are replaced by a short summary written by the same model. The newest **~2,500 tokens** stay word-for-word.

Saved notes aren't lost: they live outside the context, and `read_notes` brings them back.

Expected: input tokens grow, drop after a summary, then grow again, instead of climbing forever.

Built on LangChain's `SummarizationMiddleware`.

### Select: show only the tools needed (`select_tools`)

**Problem:** all 12 tool descriptions are sent on every call, including the 6 decoys.

**Fix:** each tool has keywords. A tool is shown only if one of its keywords appears in the user's request. Our task mentions words like "research", "started", "recent" and "note", so only the 6 useful tools are shown and the 6 decoys are hidden.

- Only **user messages** are checked. If a Wikipedia article mentions "weather", the weather tool doesn't come back.
- **Whole words only**, so "summary" doesn't match "sum".
- If nothing matches, all tools are shown, so the model is never left with none.

Built with `@wrap_model_call`.

### Write: move big results to files (`offload_big_outputs`)

**Problem:** one Wikipedia article is ~8,000 characters, and once it's in the history the model re-reads it on every later call.

**Fix:** any tool result over **1,500 characters** is saved to `results/workspace/<id>.txt`. The context only gets the first 500 characters and the file id.

If the preview isn't enough, the agent can call the extra tool `read_workspace_file(file_id)` to get the full text.

Built with `@wrap_tool_call`.

### Strategies used

| Strategy | Status |
|---|---|
| Compress | Done |
| Select | Done |
| Write | Done |
| Isolate (a sub-agent does the research and returns only a summary) | Optional, not built |

---

## 6. Project structure

```
context-engineering-agents/
├── shared/              # same for both agents: model, tools, task, run loop
├── naive_agent/         # baseline, no context management
├── engineered_agent/
│   ├── agent.py         # the middleware list
│   └── middleware.py    # Compress, Select, Write
├── tests/               # pytest: tools + middleware (fake model, no tokens used)
├── results/             # final answers, metrics, screenshots
│   └── workspace/       # offloaded tool outputs (not committed)
└── doc/PRD.md           # the original plan
```

---

## 7. How to run

**1. Set up (once)**
```
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**2. Create `.env`** by copying `.env.example`:
```
LLM_BASE_URL=https://openrouter.ai/api/v1      # or https://api.groq.com/openai/v1
LLM_API_KEY=your_key
MODEL_NAME=a_model_that_supports_tool_calling
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
```

**3. Check the connection**
```
python -m shared.llm
```

**4. Run both agents** with the **same topics**
```
python -m naive_agent.agent "Docker" "Kubernetes" "Linux"
python -m engineered_agent.agent "Docker" "Kubernetes" "Linux"
```
With no topics, both use 5 defaults. Traces go to the LangSmith projects **naive-agent** and **engineered-agent**.

**5. Run the tests**
```
python -m pytest -v -m "not network"    # offline, a few seconds
python -m pytest -v                     # includes internet tests
```

---

## 8. Results
