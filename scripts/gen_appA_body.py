#!/usr/bin/env python3
"""Regenerate paper/appA_body.tex: per-category five-outcome breakdown for ALL 11
systems (9 models + 2 frameworks), from the mapping-aware results-percat JSONs.

Row order per category = leaderboard order (overall accuracy desc) then frameworks.
Category floor (fl) is a corpus constant, carried over from the existing appA_body.
Values are % of the category's fields; accuracy = match + correct-absence.
"""
import json, re, pathlib

PC = pathlib.Path.home() / "dev/fieldbench/data/results-percat"
BODY = pathlib.Path.home() / "dev/fieldbench/paper/appA_body.tex"

# display name -> results-percat filename ; order = leaderboard (overall desc), frameworks last
SYSTEMS = [
    ("gpt-4o-mini",      "gpt-4o-mini"),
    ("gemini-2.5-pro",   "gemini-2.5-pro"),
    ("gemini-2.5-flash", "gemini-2.5-flash"),
    ("Sonnet-4.5",       "sonnet-4-5"),
    ("deepseek-chat",    "deepseek-chat"),
    ("gpt-4o",           "gpt-4o"),
    ("llama-3.3-70b",    "llama-3.3-70b"),
    ("qwen-2.5-7b",      "qwen-2.5-7b"),
    ("llama-3.1-8b",     "llama-3.1-8b"),
    ("LlamaIndex",       "llamaindex"),
    ("LangChain",        "langchain"),
]

CATS = ["contracts", "insurance_certificates", "insurance_claims", "insurance_policies",
        "invoices", "irs_forms", "legal_filings", "medical_records", "receipts", "sec_filings"]

# carry over per-category floor (fl) from the existing body — a corpus constant
floor = {}
for line in BODY.read_text().splitlines():
    m = re.search(r"\\texttt\{([a-z_\\]+)\}~\{\\scriptsize\(fl ([0-9.]+), n(\d+)\)", line)
    if m:
        floor[m.group(1).replace("\\_", "_")] = m.group(2)

data = {name: json.load(open(PC / f"{fn}.json"))["by_category"] for name, fn in SYSTEMS}

def rates(fw):
    g = lambda k: 100 * fw.get(k, {}).get("rate", 0.0)
    acc = g("match") + g("correct_absence")
    return acc, g("match"), g("wrong_value"), g("miss"), g("hallucination"), g("correct_absence")

out = []
for ci, cat in enumerate(CATS):
    ncat = data["gpt-4o-mini"][cat]["docs"]
    fl = floor.get(cat, "0.0")
    label = f"\\texttt{{{cat.replace('_', chr(92)+'_')}}}~{{\\scriptsize(fl {fl}, n{ncat})}}"
    for si, (disp, _) in enumerate(SYSTEMS):
        acc, ma, wr, mi, ha, ca = rates(data[disp][cat]["four_way"])
        head = label if si == 0 else ""
        out.append(f"{head} & {disp} & {acc:.1f} & {ma:.1f} & {wr:.1f} & {mi:.1f} & {ha:.1f} & {ca:.1f} \\\\")
    if ci != len(CATS) - 1:
        out.append("\\midrule")

BODY.write_text("\n".join(out) + "\n")
print(f"wrote {BODY} : {len(CATS)} categories x {len(SYSTEMS)} systems")
