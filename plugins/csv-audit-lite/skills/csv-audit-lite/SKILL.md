---
name: csv-audit-lite
description: >-
  Free, offline CSV merge and cleanup with a per-change log. Merges 1-5
  UTF-8 or GB18030 CSV/TSV exports with the same columns, trims whitespace
  and blanks exact null markers you name, keeps leading zeros, long IDs and
  dates as text, flags spreadsheet formula injection, and never modifies the
  original files. Use when the user asks to merge, combine or clean CSV
  exports and wants to know exactly what changed. 合并、清洗 CSV，支持
  GB18030，保留前导零，记录每处改动。
license: MIT
compatibility: Requires an agent that can run local commands and Python 3.11+ (standard library only). No network access.
metadata:
  author: laiyu
  version: "0.1.0"
  tags: "csv,data-cleaning,audit,merge,lite"
allowed-tools: Bash(python:*) Bash(python3:*) Read
---

# csv-audit-lite

Free MIT lite of a conservative CSV merge/cleanup skill. Every change is logged with the source file and record number. Work is done by `scripts/clean_csv_lite.py`.

## When to use
- Combine several CSV/TSV exports into one file (same column names; order may differ).
- Trim whitespace or blank exact placeholders such as `N/A` / `NULL`, with proof of what changed.
- Keep leading zeros, long IDs and dates as plain text.
- Not for: deduplication, column rename mapping, Excel-safe copies, XLSX, OCR, fuzzy match, databases. Say so if asked; the paid full version covers dedupe / rename / Excel-safe / config.

## Workflow
1. **Identify inputs.** 1–5 file paths. Limit 10,000 data records total. Encodings: UTF-8, UTF-8 BOM, GB18030 (`--encoding gb18030`). Delimiters: comma or tab.
2. **Inspect structure.** Run once with no cleaning into a scratch `--out` directory. If columns differ, report missing/extra and stop. Do not invent a rename map in lite.
3. **Confirm rules:** columns to trim (`--trim name,email` or `"*"`), null markers and columns (`--null-markers "N/A,NULL" --null-columns email`).
4. **Execute** into a NEW `--out` directory. The script refuses to overwrite.
5. **Verify** `summary.md`: count check OK, changes logged, any formula-trigger warnings in `anomalies.csv`.
6. **Deliver** `merged.csv`, `changes.csv`, `anomalies.csv`, `summary.md` / `summary.json`.

Example:
```
python3 scripts/clean_csv_lite.py a.csv b.csv --out ./cleaned-1 \
  --trim "*" --null-markers "N/A,NULL" --encoding gb18030
```

## Rules you must keep
- Never edit the input files. Never convert dates or numbers. All values stay text.
- If the script exits non-zero, report its error. Do not claim success or hand over partial output.
- Exit codes: 0 ok, 2 input/usage, 3 data conflict, 4 output path conflict.
- Local processing only; your agent's model can still see any file content you display.

See `references/rules.md` and `references/usage-zh.md`.
