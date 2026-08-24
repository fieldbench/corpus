#!/usr/bin/env bash
# Render docs/annotation-guidelines.md -> docs/annotation-guidelines.pdf.
#
# The markdown is the source of truth (it diffs and renders on GitHub); the PDF
# is a generated, reader-facing artifact. Regenerate whenever the guidelines
# change.
#
# Requires: pandoc and tectonic (a self-contained LaTeX engine — no system
# TeX install needed; it fetches packages on first run). See
# scripts/guidelines-header.tex for the LaTeX tweaks.
set -euo pipefail

cd "$(dirname "$0")/.."

command -v pandoc   >/dev/null || { echo "error: pandoc not found" >&2; exit 1; }
command -v tectonic >/dev/null || { echo "error: tectonic not found" >&2; exit 1; }

pandoc docs/annotation-guidelines.md \
  --pdf-engine=tectonic \
  -H scripts/guidelines-header.tex \
  -V geometry:margin=1in \
  -V fontsize=10pt \
  -V colorlinks=true -V linkcolor=RoyalBlue -V urlcolor=RoyalBlue \
  -o docs/annotation-guidelines.pdf

echo "wrote docs/annotation-guidelines.pdf"
