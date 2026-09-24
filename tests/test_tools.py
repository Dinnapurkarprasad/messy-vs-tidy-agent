"""Tests for shared/tools.py.

We call each tool with .invoke({...}), exactly the way the agent calls it.
Run from the project root:  venv\\Scripts\\python -m pytest
"""

import pytest

from shared import tools
from shared.tools import (
    ALL_TOOLS, calculator, currency_stub, get_current_date, random_number, read_notes,
    reverse_text, save_note, unit_converter, weather_stub, web_search, wikipedia_lookup,
    word_count,
)



def test_there_are_12_tools_with_descriptions():
    assert len(ALL_TOOLS) == 12
    for t in ALL_TOOLS:
        assert t.description, f"{t.name} has no docstring, the model won't know what it does"


# --- calculator -------------------------------------------------------------

def test_calculator_basic_math():
    assert calculator.invoke({"expression": "2026 - 1991"}) == "35"
    assert calculator.invoke({"expression": "(3 + 4) * 2"}) == "14"
    assert calculator.invoke({"expression": "2 ** 10"}) == "1024"


def test_calculator_blocks_python_code():
    # Safety: the model must not be able to run real Python through this tool.
    assert calculator.invoke({"expression": "__import__('os')"}).startswith("Error")


def test_calculator_handles_bad_input():
    assert calculator.invoke({"expression": "1/0"}).startswith("Error")
    assert calculator.invoke({"expression": "2 +"}).startswith("Error")


# --- notes ------------------------------------------------------------------

def test_save_and_read_notes():
    tools.NOTES.clear()  # start empty so other tests can't affect this one
    assert read_notes.invoke({}) == "No notes yet."
    save_note.invoke({"title": "Python", "content": "Started 1991"})
    save_note.invoke({"title": "Rust", "content": "Started 2010"})
    notes = read_notes.invoke({})
    assert "## Python\nStarted 1991" in notes
    assert "## Rust\nStarted 2010" in notes


def test_save_note_same_title_overwrites():
    tools.NOTES.clear()
    save_note.invoke({"title": "Python", "content": "old"})
    save_note.invoke({"title": "Python", "content": "new"})
    assert read_notes.invoke({}) == "## Python\nnew"


# --- small tools ------------------------------------------------------------

def test_get_current_date_format():
    d = get_current_date.invoke({})
    assert len(d) == 10 and d[4] == "-" and d[7] == "-"  # YYYY-MM-DD


def test_unit_converter():
    assert unit_converter.invoke({"value": 1, "from_unit": "km", "to_unit": "m"}) == "1.0 km = 1000 m"
    assert unit_converter.invoke({"value": 5, "from_unit": "xx", "to_unit": "m"}).startswith("Unknown unit")


def test_word_count():
    assert word_count.invoke({"text": "one two  three"}) == "3"


def test_reverse_text():
    assert reverse_text.invoke({"text": "abc"}) == "cba"


def test_random_number_in_range():
    for _ in range(50):
        assert 1 <= int(random_number.invoke({"min": 1, "max": 3})) <= 3


def test_weather_stub():
    assert "Pune" in weather_stub.invoke({"city": "Pune"})


def test_currency_stub():
    assert currency_stub.invoke({"amount": 10, "from_currency": "usd", "to_currency": "usd"}).startswith("10.0 USD = 10.00 USD")
    assert currency_stub.invoke({"amount": 1, "from_currency": "ABC", "to_currency": "USD"}).startswith("Unknown currency")


# --- internet tools (skip offline with: -m "not network") --------------------

@pytest.mark.network
def test_web_search_returns_results():
    out = web_search.invoke({"query": "Rust programming language"})
    assert out != "No results."
    assert "http" in out


@pytest.mark.network
def test_wikipedia_lookup_is_long_but_capped():
    out = wikipedia_lookup.invoke({"topic": "Python (programming language)"})
    assert 1500 < len(out) <= tools.WIKI_MAX_CHARS  # long enough to trigger offloading later


@pytest.mark.network
def test_wikipedia_lookup_unknown_page():
    assert wikipedia_lookup.invoke({"topic": "Qwxzzy Nonexistent Page 12345"}).startswith("No Wikipedia page")
