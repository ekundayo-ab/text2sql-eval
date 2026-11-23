"""Runs every question under every condition and model, and scores each answer by its result.

  python run_eval.py --models haiku,sonnet            prints the plan and stops
  python run_eval.py --models haiku,sonnet --yes      runs it, writes results/runs.jsonl

Needs the Claude token at /secrets/claude-token (read-only mount) and shop.duckdb.
"""

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import duckdb

from questions import QUESTIONS
from t2s import Retriever, ask, extract_sql, prompt_for, run_sql, same_result, schema_text

HERE = Path(__file__).parent
CONDITIONS = ["bare", "full", "rag", "rag_fix"]
local = threading.local()


def con(db):
    if not hasattr(local, "con"):
        local.con = duckdb.connect(db, read_only=True)
    return local.con


def run_one(q, model, condition, db, schema, retriever, gold_rows):
    c = con(db)
    prompt, retrieved = prompt_for(q["q"], schema, condition, retriever)
    first = ask(prompt, model)
    sql = extract_sql(first["text"])
    rows, err = run_sql(c, sql)
    calls, fixed = [first], False
    if condition == "rag_fix" and (err or rows == []):
        problem = err or "the query returned no rows"
        second = ask(f"{prompt}\n\nYour query:\n```sql\n{sql}\n```\nfailed: {problem}\nReply with a corrected query.", model)
        calls.append(second)
        sql2 = extract_sql(second["text"])
        rows2, err2 = run_sql(c, sql2)
        sql, rows, err, fixed = sql2, rows2, err2, True
    return {
        "id": q["id"], "kind": q["kind"], "model": model, "condition": condition,
        "ok": same_result(gold_rows, rows, q.get("ordered", False)),
        "sql": sql, "error": err or next((x["error"] for x in calls if x["error"]), ""),
        "pred": [list(map(str, r)) for r in (rows or [])[:5]], "retrieved": retrieved, "fixed": fixed,
        "calls": len(calls), "seconds": round(sum(x["seconds"] for x in calls), 1),
        "input_tokens": sum(x["usage"].get("input_tokens", 0) + x["usage"].get("cache_read_input_tokens", 0)
                            + x["usage"].get("cache_creation_input_tokens", 0) for x in calls),
        "output_tokens": sum(x["usage"].get("output_tokens", 0) for x in calls),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="haiku,sonnet")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--only", default="", help="comma-separated question ids")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--db", default=str(HERE / "shop.duckdb"))
    ap.add_argument("--out", default=str(HERE / "results" / "runs.jsonl"))
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    models, conditions = a.models.split(","), a.conditions.split(",")
    qs = [q for q in QUESTIONS if not a.only or q["id"] in a.only.split(",")]
    jobs = [(q, m, c) for q in qs for m in models for c in conditions]
    print(f"{len(qs)} questions x {len(models)} models x {len(conditions)} conditions = {len(jobs)} runs "
          f"(rag_fix adds at most one call each: up to {len(jobs) + len(qs) * len(models)} model calls)")
    if not a.yes:
        print("plan only; add --yes to run")
        return

    base = duckdb.connect(a.db, read_only=True)
    schema, retriever = schema_text(base), Retriever()
    gold = {q["id"]: base.execute(q["gold"]).fetchall() for q in qs}
    Path(a.out).parent.mkdir(exist_ok=True)
    done = 0
    with open(a.out, "w") as f, ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(run_one, q, m, c, a.db, schema, retriever, gold[q["id"]]) for q, m, c in jobs]
        for fut in as_completed(futs):
            r = fut.result()
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            done += 1
            print(f"{done}/{len(jobs)} {r['id']} {r['model']} {r['condition']}: {'ok' if r['ok'] else 'WRONG'} {r['error'][:80]}")


if __name__ == "__main__":
    main()
