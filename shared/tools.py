"""The 12 tools both agents get. Never copy these into an agent folder.

The model never sees this code, only each tool's name, docstring and arguments.
So the docstring is the instruction manual the model uses to decide what to call.
"""

import ast
import operator
import random
from datetime import date

import wikipedia
from ddgs import DDGS
from langchain.tools import tool

# ---------------------------------------------------------------------------
# Useful tools (the research task needs these)
# ---------------------------------------------------------------------------


@tool
def web_search(query: str) -> str:
    """Search the web with DuckDuckGo. Use for recent news or developments.
    Returns the top 5 results with title, link and a short snippet."""
    try:
        results = DDGS().text(query, max_results=5)
    except Exception as e:  # network / rate-limit: tell the model instead of crashing the whole run
        return f"Search error: {e}. Try again or use wikipedia_lookup."
    return "\n\n".join(f"{r['title']}\n{r['href']}\n{r['body']}" for r in results) or "No results."


# ponytail: cap at 8000 chars so 5 topics fit the free-tier limits; still far above the
# 1500-char offload threshold, so the naive agent still gets flooded. Raise if needed.
WIKI_MAX_CHARS = 8000

# Wikipedia rate-limits (429) the library's default User-Agent because everyone shares it.
wikipedia.set_user_agent("context-engineering-agents/1.0 (learning project)")


@tool
def wikipedia_lookup(topic: str) -> str:
    """Get the Wikipedia article for a topic. Use to learn what something is and when it started.
    Returns a long article text."""
    try:
        return wikipedia.page(topic, auto_suggest=False).content[:WIKI_MAX_CHARS]
    except wikipedia.DisambiguationError as e:
        return f"'{topic}' is ambiguous. Try one of: {', '.join(e.options[:10])}"
    except wikipedia.PageError:
        return f"No Wikipedia page for '{topic}'. Try a more exact title."
    except Exception as e:  # network / rate-limit: tell the model instead of crashing the whole run
        return f"Wikipedia error: {e}. Try again later or use web_search."


NOTES: dict[str, str] = {}  # lives in memory for one run


@tool
def save_note(title: str, content: str) -> str:
    """Save a research finding as a note so you can use it later. Saving the same title overwrites it."""
    NOTES[title] = content
    return f"Saved note '{title}'. You have {len(NOTES)} notes."


@tool
def read_notes() -> str:
    """Read back all notes saved so far."""
    return "\n\n".join(f"## {t}\n{c}" for t, c in NOTES.items()) or "No notes yet."


# Only these math operations are allowed, so the model can't run arbitrary Python.
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("only numbers and + - * / ** % are allowed")


@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression, e.g. '2026 - 1991' or '(3 + 4) * 2'.
    Supports + - * / ** % and parentheses."""
    try:
        return str(_eval(ast.parse(expression, mode="eval").body))
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        return f"Error: {e}"


@tool
def get_current_date() -> str:
    """Return today's date (YYYY-MM-DD). Use to judge what counts as 'recent'."""
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Distractor tools (they work, but the research task never needs them)
# ---------------------------------------------------------------------------

# Everything converted through a base unit: meters for length, kilograms for weight.
_UNITS = {"m": 1, "km": 1000, "cm": 0.01, "mi": 1609.344, "ft": 0.3048,
          "kg": 1, "g": 0.001, "lb": 0.45359237}


@tool
def unit_converter(value: float, from_unit: str, to_unit: str) -> str:
    """Convert length or weight between units: m, km, cm, mi, ft, kg, g, lb."""
    if from_unit not in _UNITS or to_unit not in _UNITS:
        return f"Unknown unit. Supported: {', '.join(_UNITS)}"
    return f"{value} {from_unit} = {value * _UNITS[from_unit] / _UNITS[to_unit]:.4g} {to_unit}"


@tool
def word_count(text: str) -> str:
    """Count the words in a piece of text."""
    return str(len(text.split()))


@tool
def reverse_text(text: str) -> str:
    """Reverse a piece of text character by character."""
    return text[::-1]


@tool
def random_number(min: int, max: int) -> str:
    """Return a random whole number between min and max (inclusive)."""
    return str(random.randint(min, max))


@tool
def weather_stub(city: str) -> str:
    """Get the current weather for a city."""
    return f"Weather in {city}: 22°C, partly cloudy (dummy data)."


_RATES_TO_USD = {"USD": 1, "EUR": 1.08, "GBP": 1.27, "INR": 0.012, "JPY": 0.0067}


@tool
def currency_stub(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert money between currencies: USD, EUR, GBP, INR, JPY."""
    f, t = from_currency.upper(), to_currency.upper()
    if f not in _RATES_TO_USD or t not in _RATES_TO_USD:
        return f"Unknown currency. Supported: {', '.join(_RATES_TO_USD)}"
    return f"{amount} {f} = {amount * _RATES_TO_USD[f] / _RATES_TO_USD[t]:.2f} {t} (dummy rates)"


ALL_TOOLS = [
    web_search, wikipedia_lookup, save_note, read_notes, calculator, get_current_date,
    unit_converter, word_count, reverse_text, random_number, weather_stub, currency_stub,
]
