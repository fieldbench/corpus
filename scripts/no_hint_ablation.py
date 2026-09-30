#!/usr/bin/env python3
"""No-hint ablation: re-run extraction with the field descriptions/options
(the GT-convention hints) REMOVED from the prompt, on the 60-doc IAA sample.

Same runner and windowing (max_doc_chars=120000) as the with-hint baseline
(examples.*:make_windowed_runner), so the only difference is the prompt. Compare
the resulting accuracy to the baseline preds to measure how much of each model's
accuracy depends on the schema hints (rubric-following) vs extraction.

  ANTHROPIC/OPENAI keys in env; then:
  python scripts/no_hint_ablation.py --model gpt-4o-mini --provider openai --out ../data/preds-nohint/gpt-4o-mini
"""
import argparse, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "dev/fieldbench/fieldbench/src"))
import fieldbench.run as fbrun          # noqa: E402
from fieldbench.run import LLMRunner    # noqa: E402
import yaml                             # noqa: E402

CORPUS = Path.home() / "dev/fieldbench/corpus"

def no_hint_prompt(doc_text: str, schema: dict) -> str:
    """The default extraction prompt with descriptions AND options stripped —
    only field name and type remain."""
    lines = []
    for name, spec in (schema.get("fields") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        typ = spec.get("type", "string")
        lines.append(f"- {name} ({typ})")
    fields_block = "\n".join(lines)
    return (
        "Extract structured data from the document below.\n"
        "Return ONLY a JSON object with EXACTLY these fields. "
        "Use null when a field is not present in the document — do not guess.\n\n"
        f"Fields:\n{fields_block}\n\n"
        f"Document:\n{doc_text}\n\nJSON:"
    )

def openai_complete(model):
    from openai import OpenAI
    c = OpenAI()
    def complete(prompt):
        r = c.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}],
                                      temperature=0, response_format={"type": "json_object"})
        return r.choices[0].message.content or "{}"
    return complete

def anthropic_complete(model):
    from anthropic import Anthropic
    c = Anthropic()
    def complete(prompt):
        r = c.messages.create(model=model, max_tokens=4096, temperature=0,
                              messages=[{"role": "user", "content": prompt}])
        return r.content[0].text if r.content else "{}"
    return complete

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--provider", choices=["openai", "anthropic"], required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    fbrun.build_extraction_prompt = no_hint_prompt   # the ablation
    complete = {"openai": openai_complete, "anthropic": anthropic_complete}[args.provider](args.model)
    runner = LLMRunner(complete, max_doc_chars=120000)

    wl = json.load(open(CORPUS / "iaa" / "worklist.json"))
    args.out.mkdir(parents=True, exist_ok=True)
    scache = {}
    n = 0
    for e in wl:
        stem, cat = e["stem"], e["category"]
        op = args.out / f"{stem}.json"
        if op.exists():
            continue
        man = json.loads((CORPUS / cat / "manifests" / f"{stem}.json").read_text())
        sref = man.get("schema")
        doc = CORPUS / cat / "documents" / f"{stem}.md"
        schema = scache.setdefault(sref, yaml.safe_load((CORPUS / sref).read_text()) or {})
        try:
            pred = runner.extract(doc.read_text(), schema, stem)
            op.write_text(json.dumps(pred, ensure_ascii=False, indent=2))
            n += 1
        except Exception as ex:
            print(f"  err {stem}: {ex}", file=sys.stderr)
    print(f"wrote {n} no-hint preds to {args.out}")

if __name__ == "__main__":
    main()
