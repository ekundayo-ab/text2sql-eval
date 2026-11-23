"""Summarises results/runs.jsonl with pandas into results/report.md."""

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
ORDER = ["bare", "full", "rag", "rag_fix"]


def main():
    df = pd.DataFrame(json.loads(l) for l in (HERE / "results" / "runs.jsonl").read_text().splitlines())
    df["condition"] = pd.Categorical(df["condition"], ORDER, ordered=True)
    acc = df.pivot_table(index="model", columns="condition", values="ok", aggfunc="sum", observed=True)
    n = df.groupby("model")["id"].nunique()
    by_kind = df.pivot_table(index=["kind"], columns=["model", "condition"], values="ok", aggfunc="sum", observed=True)
    kinds = df.groupby("kind")["id"].nunique()
    cost = df.groupby(["model", "condition"], observed=True)[["input_tokens", "output_tokens", "seconds", "calls"]].mean().round(1)
    wrong = (df[~df["ok"]].groupby(["id", "kind"])
             .apply(lambda g: ", ".join(f"{m}/{c}" for m, c in zip(g["model"], g["condition"])), include_groups=False)
             .rename("wrong in").reset_index())

    lines = ["# Results", "", f"{len(df)} runs. Correct answers out of {int(n.iloc[0])} questions:", "",
             acc.to_markdown(), "", "## By kind of question (correct answers; questions per kind in brackets)", "",
             by_kind.rename(index=lambda k: f"{k} ({kinds[k]})").to_markdown(), "",
             "## Average per run", "", cost.to_markdown(), "", "## Wrong answers per question", "",
             wrong.to_markdown(index=False), ""]
    (HERE / "results" / "report.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
