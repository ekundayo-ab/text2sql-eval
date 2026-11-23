# text2sql-eval

How much does a Text-to-SQL model need to know about a company's data before its answers can be trusted? This repo asks 30 business questions of a small retail database, four ways, with two Claude models, and scores every answer by running the SQL and comparing the result with a hand-written gold query. It never compares SQL text.

## The result

240 runs: 30 questions × 4 ways of asking × Claude Haiku and Claude Sonnet, one run each.

| model | schema only | schema + all notes | schema + 6 retrieved notes | retrieved + one retry on error |
|:-|-:|-:|-:|-:|
| Haiku | 20 / 30 | 29 / 30 | 29 / 30 | 29 / 30 |
| Sonnet | 20 / 30 | **30 / 30** | 29 / 30 | 29 / 30 |

What that means:

- **The schema alone isn't enough.** Both models got the same 10 wrong, and none of them was a SQL mistake. They were business-rule mistakes: `city = 'Munich'` when the data says `München` (answer: 0 customers); revenue that left out cancelled orders but kept refunded ones; units sold counted on unpaid orders. The SQL ran fine and the numbers looked plausible, so nobody downstream would catch them.
- **A few lines of notes fix almost all of it.** The catalog is 20 short notes, the kind a data team writes as column comments: what "revenue" means, that money is in cents, which status counts as a sale. With them, 9 or 10 of the 10 come right.
- **Retrieval matched the full catalog.** Six notes picked by TF-IDF did as well as all twenty, minus one question. With 20 notes you would just send them all; retrieval starts to matter when the catalog is too big for the prompt.
- **The retry never fired.** It only triggers on an error or an empty result, and with notes no query failed that way. The wrong answers were wrong *values*, which a retry on errors can't see.

The two answers still marked wrong are arguably my gold's fault, and I've left them scored as wrong rather than move the target after the run:

- **q15**, revenue per month of 2026: Sonnet returned all 12 months with November and December at 0; the gold has 10 rows because the data ends in October.
- **q19**, list price vs. the price "actually paid": Haiku subtracted line discounts from the price paid, the gold doesn't. Haiku's reading is defensible.

That is the real lesson for production: the eval set needs the same care as the model, and every "wrong" needs reading before it counts.

## The database

`build_db.py` generates a German retail chain from a fixed seed into DuckDB: 8 stores, 2,000 customers, 120 products, 15,000 orders, 32,342 order lines, 1,699 returns. It carries the traps real company data has, each written down in [catalog.json](catalog.json):

- money in euro cents, and a list price that isn't the price paid
- `paid`, `cancelled` and `refunded` orders; only `paid` is a sale
- soft-deleted customers (`deleted_at`) and German city names
- online orders with no store, 15 abandoned orders with no lines, partial returns

## How a run works

1. Build the prompt: the schema (from `information_schema`), plus none, all, or the top 6 catalog notes by TF-IDF similarity to the question (scikit-learn).
2. Ask the model for one DuckDB query, through the Claude Code CLI with no tools and one turn.
3. Run it on a read-only connection. In the retry condition, an error or an empty result goes back to the model once.
4. Score: same number of rows, and every gold column found among the answer's columns (an extra id next to a name is fine), numbers within a cent. Row order counts only where the question asks for an order.

## Testing the harness before spending tokens

`tests/test_eval.py` runs with no model calls, 11 checks: every gold query runs and returns no NULLs; the scorer accepts reordered rows and extra columns and rejects cents-for-euros; each trap really changes the answer; and the "which one had the most" questions have no tie. That last check caught two unfair questions before the run (a tie for 5th-best product, two refunds of the same size), and both were rewritten.

## Files

- [build_db.py](build_db.py), [catalog.json](catalog.json), [questions.py](questions.py): data, notes, 30 questions with gold SQL
- [t2s.py](t2s.py): schema text, retrieval, the model call, SQL extraction, scoring
- [run_eval.py](run_eval.py): runs the grid in parallel, writes `results/runs.jsonl` (every prompt's notes, SQL, first rows, tokens, seconds)
- [report.py](report.py): pandas summary into [results/report.md](results/report.md)

## What a production version would add

- **Value checks, not just error checks.** Every remaining failure was a plausible wrong number. A second pass that asks "does this query apply the revenue rule?" against the retrieved notes would catch more than retrying on errors.
- **A bigger, adversarial question set** written with the people who use the numbers, and several runs per question to measure variance. One run each is enough to see a 20 to 29 jump, not a 29 to 30 one.
- **Notes kept where the data lives**, as table and column comments in the catalog (on Databricks, Unity Catalog), so the model and people read the same definitions.

## Run it

Python 3.11+, and the Claude Code CLI logged in for the model calls:

```
pip install -r requirements.txt
python build_db.py
python -m unittest discover -s tests       # no model calls
python run_eval.py --models haiku,sonnet   # prints the plan; add --yes to run
python report.py
```

The `Dockerfile` has everything; in it the token is read from `/secrets/claude-token`.
