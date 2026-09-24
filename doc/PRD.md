# Context Engineering Agents — Naive vs Engineered

## 1. What this project is

A benchmark-style project that builds **the same research agent twice** and compares them on the **same task, same tools, same model**:

- **`naive_agent`** — no context management. Every tool is always visible, full chat history and raw tool outputs keep piling into the context.
- **`engineered_agent`** — identical agent, but with **context engineering applied through LangChain v1 middleware** (compress, select, write/offload, and optionally isolate).

The only difference between the two agents must be the context engineering layer. Everything else lives in `shared/` so the comparison stays fair.

**One-line pitch:** *Same agent, same task. Context engineering → fewer tokens, lower latency, fewer wrong tool calls, same or better output.*

## 2. What we are trying to prove

Measured with LangSmith tracing, the engineered agent should show:

- Lower **total tokens** (especially input tokens per LLM call)
- Lower or similar **latency**
- Fewer **irrelevant / wrong tool calls**
- Input context size per step that stays **flat** instead of growing linearly
- Final answer quality that is **equal or better**

Numbers do not have to be dramatic. Honest results with a clear explanation are the goal.

## 3. Non-goals (keep scope tight)

- **No RAG**, no embeddings, no vector DB. (Planned as a separate Part 2 later.)
- No frontend/UI. CLI scripts only.
- No company/private data. Only public web data and dummy data.
- No fine-tuning, no custom model hosting.

## 4. Tech stack

- Python **3.12** (venv at project root)
- **LangChain >= 1.0** (`create_agent`, tools, middleware)
- **OpenRouter** free model via `ChatOpenAI` with custom `base_url`
  - Default model: `deepseek/deepseek-v4-flash:free` (configurable via `.env`)
  - Do NOT use the `openrouter/free` random router — both agents must use the same fixed model
- **LangSmith** for tracing and metrics
- Free tools: DuckDuckGo search (`ddgs`), Wikipedia (`wikipedia`), plus simple custom Python tools

> Note for Claude Code: LangChain v1 APIs changed from 0.x. Before writing agent or middleware code, verify the current import paths and signatures against the official LangChain v1 docs (e.g. `from langchain.agents import create_agent`, `from langchain.agents.middleware import ...`). Do not use deprecated `AgentExecutor` / `initialize_agent` patterns.

## 5. Folder structure

```
context-engineering-agents/
├── shared/
│   ├── __init__.py
│   ├── llm.py            # get_llm(): same OpenRouter model for both agents
│   ├── tools.py          # the same 10-15 tools for both agents
│   └── task.py           # the same research task prompt(s)
├── naive_agent/
│   ├── __init__.py
│   └── agent.py
├── engineered_agent/
│   ├── __init__.py
│   ├── agent.py
│   └── middleware.py     # all context engineering logic
├── results/
│   ├── workspace/        # offloaded tool outputs (engineered agent only)
│   ├── screenshots/      # LangSmith trace screenshots
│   └── metrics.md        # final comparison table
├── .env                  # NOT committed
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 6. Setup

### requirements.txt
```
langchain>=1.0
langchain-openai
langsmith
python-dotenv
langchain-community
ddgs
wikipedia
```

### .env (root)
```
OPENROUTER_API_KEY=
MODEL_NAME=deepseek/deepseek-v4-flash:free
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
```
`LANGSMITH_PROJECT` is NOT in `.env`. Each agent sets its own project name at the top of its `agent.py` before any LangChain import:
- naive → `naive-agent`
- engineered → `engineered-agent`

### .gitignore
```
venv/
.env
__pycache__/
*.pyc
results/workspace/
```

### Run (always from project root)
```
python -m naive_agent.agent
python -m engineered_agent.agent
```

## 7. Shared components (identical for both agents)

### 7.1 `shared/llm.py`
- `load_dotenv()`
- `get_llm()` returns `ChatOpenAI(model=MODEL_NAME, base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)`
- Add basic retry handling for 429 rate-limit errors (free tier).

### 7.2 `shared/tools.py` — 10 to 15 tools
Mix of **useful** tools and **distractor** tools. Distractors matter: they make naive tool selection harder, which the engineered agent should fix.

Useful for the research task:
- `web_search(query)` — DuckDuckGo search
- `wikipedia_lookup(topic)` — Wikipedia summary/content (outputs are long on purpose)
- `save_note(title, content)` — store an intermediate finding
- `read_notes()` — read all saved notes
- `calculator(expression)` — safe math evaluation
- `get_current_date()`

Distractors (valid tools, but irrelevant to the task):
- `unit_converter(value, from_unit, to_unit)`
- `word_count(text)`
- `reverse_text(text)`
- `random_number(min, max)`
- `weather_stub(city)` — returns dummy data
- `currency_stub(amount, from, to)` — returns dummy data

Every tool needs a clear docstring (the model reads it).
Export `ALL_TOOLS` list. Both agents import from here — never copy tools into agent folders.

### 7.3 `shared/task.py`
A long multi-step research task that naturally fills context. Example:

> "Research these 5 topics: [topic list]. For each, find what it is, when it started, and one recent development. Save a note per topic. Then compare all 5 in a table and write a final 200-word summary."

Topics should be public and neutral (e.g. programming languages, databases, space missions). Export `RESEARCH_TASK` as a string. Optionally include 2–3 task variants for more robust comparison.

## 8. Naive agent (`naive_agent/agent.py`)

Deliberately unoptimized baseline:
- `create_agent(model=get_llm(), tools=ALL_TOOLS, system_prompt=...)`
- No middleware at all
- Full message history kept as-is
- Raw tool outputs go directly into context
- Runs `RESEARCH_TASK`, prints final answer
- Saves final answer to `results/naive_output.md`

Do not add any optimization here, even accidentally (no trimming, no truncation of tool outputs).

## 9. Engineered agent (`engineered_agent/`)

Same model, same tools, same task, same system prompt base — plus middleware. Implement strategies in this priority order (1–3 required, 4 optional):

### 9.1 Compress — history summarization (required)
- Use LangChain's built-in `SummarizationMiddleware` (verify exact parameters in docs).
- Trigger summarization when message history crosses a token threshold; keep the most recent messages intact.
- Summary model = same model from `get_llm()`.

### 9.2 Select — dynamic tool selection (required)
- Custom middleware that, before each model call, filters `ALL_TOOLS` down to only the relevant subset.
- Simple, explainable approach first: keyword/rule-based mapping from the task and latest messages to tool names. (An LLM-based selector is an optional upgrade.)
- The goal: distractor tools should not be shown to the model for this task.
- Use the v1 middleware hook that allows modifying the model request (e.g. a `wrap_model_call`-style hook) — verify in docs.

### 9.3 Write — offload large tool outputs (required)
- If a tool output exceeds a size threshold (e.g. ~1500 characters), save the full output to `results/workspace/<id>.txt`.
- Put only a short preview + file reference into the context.
- Provide a `read_workspace_file(file_id)` tool (engineered agent only) so the agent can fetch full content when it truly needs it.
- Implement either as a tool wrapper or as middleware — whichever is cleaner in v1.

### 9.4 Isolate — sub-agent (optional, only if time allows)
- A research sub-agent handles searching/reading per topic and returns only a compact summary to the main agent.
- Main agent never sees raw search/wiki output.

### 9.5 Files
- `middleware.py` — all custom middleware, each clearly commented with which strategy it implements.
- `agent.py` — builds the agent with middleware list, runs `RESEARCH_TASK`, saves output to `results/engineered_output.md`.

## 10. Measurement & evaluation

For each agent, run the same task **3 times** and average the numbers (free models are noisy).

Collect from LangSmith:
- Total tokens (input / output)
- Max input tokens in a single LLM call
- Number of LLM calls
- Number of tool calls + number of irrelevant (distractor) tool calls
- Total latency
- Errors / failed runs

Output quality (simple manual rubric, 1–5):
- Covered all 5 topics?
- Facts reasonable?
- Comparison table correct?
- Summary coherent?

Optional: a small script using the LangSmith client to pull run stats from both projects and write `results/metrics.md` automatically.

## 11. Final deliverables

- Working code for both agents
- `results/metrics.md` with a before/after comparison table
- LangSmith trace screenshots (naive = bloated trace, engineered = clean trace)
- `README.md` containing:
  - Problem: why context grows and hurts agents (context rot)
  - The 4 strategies: write, select, compress, isolate
  - What each middleware does
  - Results table + screenshots
  - Honest limitations (free model, small sample size, rule-based tool selection)
  - How to run
  - Future work: Part 2 with RAG post-retrieval pipeline (clustering, selection, reranking, compression)

## 12. Build order

1. Setup: venv, requirements, `.env`, LangSmith working with a one-line test call
2. `shared/llm.py`, `shared/tools.py`, `shared/task.py`
3. Naive agent → run → record baseline numbers
4. Engineered agent: add Compress → run → check numbers
5. Add Select → run → check
6. Add Write/offload → run → check
7. (Optional) Isolate
8. Final 3-run comparison, `metrics.md`, screenshots, README

Adding strategies one at a time lets us see how much each one contributes.

## 13. Rules for Claude Code

- Keep `shared/` as the single source of truth for model, tools, and task.
- Never change the model between naive and engineered runs.
- Keep code simple and readable — this is a learning + portfolio project, not a framework.
- Comment every middleware with *what problem it solves* and *which strategy* it maps to.
- Always run modules from root with `python -m`.
- Never commit `.env` or API keys.
- If a LangChain v1 API is unclear, check the official docs instead of guessing.
