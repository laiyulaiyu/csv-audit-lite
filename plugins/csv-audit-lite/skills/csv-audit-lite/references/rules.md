# Cleaning rules and output formats (csv-audit-lite v0.1.0)

## Reading
- Encodings: `auto` = UTF-8 BOM → `utf-8-sig`; valid UTF-8 → `utf-8`; anything else → error asking for `--encoding gb18030`. Explicit: `utf-8`, `utf-8-sig`, `gb18030`.
- Delimiter: `auto` inspects the header. Only commas → `,`; only tabs → tab; both → error.
- RFC-4180 quoting. Unbalanced quotes or wrong field count → exit 3, nothing written.
- Empty file → exit 2. Header with no data records → exit 2.
- Limits: 1–5 files, ≤10,000 data records total.

## Columns
- Duplicate column names inside a file → exit 3.
- All files must have the same set of column names. Order may differ: later files are reordered to the first file's order (logged as `columns_reordered_to_first_file`). Different sets → exit 3 with missing/extra lists.
- No `--rename` in lite.

## Values (in order, per cell)
1. Trim (`--trim col1,col2` or `*`): strip leading/trailing whitespace. Logged as `trim`.
2. Null markers (`--null-markers`, exact, case-sensitive, after step 1) in `--null-columns` (default all) → empty string. Logged as `null_marker`.
3. Nothing else. No date parsing, no number formatting, no case changes, no dedupe.

## Formula triggers
A value that starts with `=`, `+`, `-`, `@`, TAB or CR and is not a plain number is listed in `anomalies.csv` as `formula_trigger`. `merged.csv` keeps it unchanged. (Excel-safe copy is paid-only.)

## Output safety
- `--out` must not exist. Written to `<out>.partial`, renamed only after count check passes. On error the partial dir is deleted.
- Inputs opened read-only. `summary.json` records each input SHA-256.
- Same inputs + same options → byte-identical outputs.

## changes.csv columns
`source_file, source_record, column, old_column_name, old_value, new_value, rule`
`source_record` is 1-based data record number in that file.
