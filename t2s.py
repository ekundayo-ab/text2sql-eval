"""Text-to-SQL pieces: schema text, catalog retrieval, the model call, SQL extraction and scoring.

Four ways to ask the model, from least to most help:
  bare     the schema only (table and column names and types)
  full     the schema plus the whole catalog (column notes and business rules)
  rag      the schema plus the 6 catalog entries most similar to the question (TF-IDF)
  rag_fix  rag, then the query is run; on an error or an empty result the model
           gets the error once and may answer again (it never sees the gold answer)
"""

import json
import math
import os
import re
import subprocess
import time
from datetime import date, datetime
from decimal import Decimal
from itertools import permutations
from pathlib import Path

import duckdb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HERE = Path(__file__).parent
CATALOG = json.loads((HERE / "catalog.json").read_text())
SYSTEM = ("You translate business questions into one DuckDB SQL query. "
          "Reply with exactly one ```sql code block and nothing else.")
BUILTIN = "Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,Task,NotebookEdit,TodoWrite"
TOP_K = 6


def schema_text(con: duckdb.DuckDBPyConnection) -> str:
    rows = con.execute("select table_name, column_name, data_type from information_schema.columns "
                       "where table_schema = 'main' order by table_name, ordinal_position").fetchall()
    tables: dict[str, list[str]] = {}
    for t, c, ty in rows:
        tables.setdefault(t, []).append(f"{c} {ty.lower()}")
    return "\n".join(f"{t}({', '.join(cols)})" for t, cols in tables.items())


class Retriever:
    def __init__(self, entries=CATALOG, k=TOP_K):
        self.entries, self.k = entries, k
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
        self.matrix = self.vec.fit_transform(e["text"] for e in entries)

    def top(self, question: str) -> list[dict]:
        sims = cosine_similarity(self.vec.transform([question]), self.matrix)[0]
        order = sorted(range(len(sims)), key=lambda i: -sims[i])[: self.k]
        return [self.entries[i] for i in order]


def prompt_for(question: str, schema: str, condition: str, retriever: Retriever) -> tuple[str, list[str]]:
    if condition == "bare":
        notes = []
    elif condition == "full":
        notes = CATALOG
    else:
        notes = retriever.top(question)
    parts = [f"Schema:\n{schema}"]
    if notes:
        parts.append("Notes on the data:\n" + "\n".join(f"- {n['text']}" for n in notes))
    parts.append(f"Question: {question}")
    return "\n\n".join(parts), [n["id"] for n in notes]


def ask(prompt: str, model: str, timeout=180) -> dict:
    """One completion through the Claude Code CLI, no tools, one turn."""
    args = ["claude", "-p", "--model", model, "--output-format", "json", "--max-turns", "1",
            "--system-prompt", SYSTEM, "--disallowedTools", BUILTIN, "--strict-mcp-config"]
    env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": Path("/secrets/claude-token").read_text().strip()}
    t = time.time()
    r = subprocess.run(args, input=prompt, capture_output=True, text=True, timeout=timeout, env=env, cwd="/tmp")
    try:
        out = json.loads(r.stdout)
    except ValueError:
        return {"text": "", "usage": {}, "seconds": round(time.time() - t, 1), "error": (r.stderr or r.stdout)[-300:]}
    return {"text": out.get("result", ""), "usage": out.get("usage", {}), "seconds": round(time.time() - t, 1),
            "error": out.get("result", "")[:300] if out.get("is_error") else ""}


def extract_sql(text: str) -> str:
    blocks = re.findall(r"```(?:sql)?\s*(.*?)```", text or "", re.S | re.I)
    return blocks[-1].strip().rstrip(";") if blocks else ""


def run_sql(con: duckdb.DuckDBPyConnection, sql: str, limit=1000):
    """Returns (rows, error). Read-only connection; more than `limit` rows counts as an error."""
    if not sql:
        return None, "no SQL in the answer"
    try:
        rows = con.execute(sql).fetchmany(limit + 1)
    except Exception as e:  # noqa: BLE001 - any database error is a wrong answer, with its message kept
        return None, f"{type(e).__name__}: {str(e).splitlines()[0][:300]}"
    if len(rows) > limit:
        return None, f"more than {limit} rows"
    return rows, ""


# --- scoring: compare result sets, not SQL text ---

def _norm(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float, Decimal)):
        f = float(v)
        return None if math.isnan(f) else f
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v).strip().lower()


def _close(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= 0.01 + 1e-4 * abs(b)
    return a == b


def _key(row):
    return tuple((0, round(x, 2)) if isinstance(x, float) else (1, "" if x is None else str(x)) for x in row)


def same_result(gold, pred, ordered=False) -> bool:
    """True when pred holds the gold answer: same rows, and every gold column found
    among pred's columns (extra columns such as an id next to a name are allowed)."""
    if gold is None or pred is None or len(gold) != len(pred):
        return False
    if not gold:
        return True
    g = [tuple(_norm(x) for x in r) for r in gold]
    p = [tuple(_norm(x) for x in r) for r in pred]
    ng, np_ = len(g[0]), len(p[0])
    if np_ < ng or np_ > 8:
        return False
    for cols in permutations(range(np_), ng):
        proj = [tuple(r[j] for j in cols) for r in p]
        a, b = (g, proj) if ordered else (sorted(g, key=_key), sorted(proj, key=_key))
        if all(_close(x, y) for ra, rb in zip(a, b) for x, y in zip(ra, rb)):
            return True
    return False
