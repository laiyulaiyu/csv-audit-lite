#!/usr/bin/env python3
"""clean_csv_lite.py - free lite: CSV merge & cleanup with a per-change audit log.

Standard library only. Runs fully offline. Never modifies input files.
Exit codes: 0 ok, 1 unexpected error, 2 input/usage error,
            3 data conflict (schema, duplicate headers, malformed records),
            4 output directory conflict.

This is the free MIT lite. Paid-only features (dedupe, rename map, Excel-safe
copy, source columns, config file, utf-8-sig output) are intentionally absent.
"""
import argparse, csv, hashlib, io, json, os, re, shutil, sys

VERSION = "0.1.0"
MAX_FILES = 5
MAX_RECORDS = 10000
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
NUMERIC_RE = re.compile(r"^[+-]?(\d+([.,]\d+)?|\.\d+)([eE][+-]?\d+)?$")
SUPPORTED_ENCODINGS = {"auto", "utf-8", "utf-8-sig", "gb18030"}

csv.field_size_limit(10 * 1024 * 1024)


class UserError(Exception):
    code = 2


class ConflictError(Exception):
    code = 3


class OutputConflict(Exception):
    code = 4


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def decode(raw, encoding, name):
    if encoding == "auto":
        if raw.startswith(b"\xef\xbb\xbf"):
            return raw[3:].decode("utf-8"), "utf-8-sig"
        try:
            return raw.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            raise UserError(
                f"{name}: not valid UTF-8 and encoding could not be determined. "
                "If this is a Chinese GB18030/GBK file, re-run with --encoding gb18030.")
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError as e:
        raise UserError(f"{name}: cannot decode as {encoding}: {e}")
    if encoding == "gb18030" and text.startswith("\ufeff"):
        text = text[1:]
    if encoding == "utf-8" and text.startswith("\ufeff"):
        text = text[1:]
    return text, encoding


def detect_delimiter(text, delimiter, name):
    if delimiter in (",", "\t"):
        return delimiter
    if delimiter != "auto":
        raise UserError(f"unsupported delimiter {delimiter!r}; use ',' or 'tab'")
    first = text.split("\n", 1)[0]
    c, t = first.count(","), first.count("\t")
    if c and t:
        raise UserError(f"{name}: header contains both commas and tabs; "
                        "specify --delimiter ',' or --delimiter tab")
    return "\t" if t else ","


def read_file(path, args):
    name = os.path.basename(path)
    if not os.path.isfile(path):
        raise UserError(f"input not found: {path}")
    with open(path, "rb") as f:
        raw = f.read()
    if not raw.strip(b"\xef\xbb\xbf \r\n\t"):
        raise UserError(f"{name}: file is empty (no header, no records)")
    text, enc = decode(raw, args.encoding, name)
    delim = detect_delimiter(text, args.delimiter, name)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim, strict=True)
    try:
        rows = list(reader)
    except csv.Error as e:
        raise ConflictError(f"{name}: malformed CSV (line {reader.line_num}): {e}")
    while rows and rows[-1] == []:
        rows.pop()
    header = rows[0]
    records = rows[1:]
    dups = sorted({h for h in header if header.count(h) > 1})
    if dups:
        raise ConflictError(
            f"{name}: duplicate column names {dups}; rename them in a copy "
            "of the file and retry")
    bad = [(i + 1, len(r)) for i, r in enumerate(records) if len(r) != len(header)]
    if bad:
        sample = ", ".join(f"record {n} has {k} fields" for n, k in bad[:5])
        raise ConflictError(f"{name}: {len(bad)} record(s) do not match header width "
                            f"{len(header)} ({sample}). Nothing was written.")
    return {"path": path, "name": name, "encoding": enc, "delimiter": delim,
            "header": header, "records": records, "sha256": sha256_file(path)}


def is_formula_trigger(v):
    return bool(v) and v.startswith(FORMULA_PREFIXES) and not NUMERIC_RE.match(v.strip())


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Free lite: conservative CSV merge & cleanup with change log")
    p.add_argument("inputs", nargs="+", help="1-5 CSV files")
    p.add_argument("--out", required=True, help="new output directory (must not exist)")
    p.add_argument("--encoding", default="auto",
                   help="auto | utf-8 | utf-8-sig | gb18030")
    p.add_argument("--delimiter", default="auto", help="auto | , | tab")
    p.add_argument("--trim", default="", help="comma-separated columns, or * for all")
    p.add_argument("--null-markers", default="",
                   help="comma-separated exact tokens, e.g. NULL,N/A")
    p.add_argument("--null-columns", default="*",
                   help="columns for null markers (default *)")
    p.add_argument("--version", action="version", version=VERSION)
    a = p.parse_args(argv)

    def as_list(v):
        if v is None or v == "":
            return []
        return [x.strip() for x in str(v).split(",") if x.strip()]

    args = argparse.Namespace()
    args.inputs = a.inputs
    args.out = a.out
    args.encoding = a.encoding
    d = a.delimiter
    args.delimiter = "\t" if d in ("tab", "\\t", "\t") else d
    args.trim = as_list(a.trim)
    args.null_markers = [x for x in str(a.null_markers).split(",") if x != ""] if a.null_markers else []
    args.null_columns = as_list(a.null_columns) or ["*"]
    if args.encoding not in SUPPORTED_ENCODINGS:
        raise UserError(
            f"unsupported encoding {args.encoding}; use one of {sorted(SUPPORTED_ENCODINGS)}")
    if len(args.inputs) > MAX_FILES:
        raise UserError(f"{len(args.inputs)} files given; maximum is {MAX_FILES}")
    return args


def run(args):
    out = os.path.abspath(args.out)
    in_abs = [os.path.abspath(p) for p in args.inputs]
    if os.path.exists(out):
        raise OutputConflict(
            f"output path already exists: {args.out}. "
            "Choose a new directory; nothing was overwritten.")
    for p in in_abs:
        if os.path.commonpath([p, out]) == out:
            raise OutputConflict("output directory would contain an input file")
    if len(set(in_abs)) != len(in_abs):
        raise UserError("the same input file was given twice")

    files = [read_file(p, args) for p in args.inputs]
    total = sum(len(f["records"]) for f in files)
    if total > MAX_RECORDS:
        raise UserError(
            f"{total} data records in total; this version supports at most "
            f"{MAX_RECORDS}. Nothing was written.")
    if total == 0:
        raise UserError(
            "all inputs contain a header but no data records. Nothing was written.")

    changes = []
    base = files[0]["header"]
    diffs = []
    for f in files[1:]:
        missing = [c for c in base if c not in f["header"]]
        extra = [c for c in f["header"] if c not in base]
        if missing or extra:
            diffs.append({"file": f["name"], "missing_vs_first": missing,
                          "extra_vs_first": extra})
    if diffs:
        lines = [f"Column structures differ from {files[0]['name']} ({base}):"]
        for d in diffs:
            lines.append(
                f"  {d['file']}: missing {d['missing_vs_first']}, "
                f"extra {d['extra_vs_first']}")
        lines.append(
            "Nothing was merged. Align column names in the source files "
            "(or use the paid full version's --rename), then retry.")
        raise ConflictError("\n".join(lines))
    for col in args.trim:
        if col != "*" and col not in base:
            raise UserError(f"column {col!r} not found; available: {base}")
    for col in args.null_columns:
        if col != "*" and col not in base:
            raise UserError(f"column {col!r} not found; available: {base}")

    trim_all = "*" in args.trim
    null_all = "*" in args.null_columns
    markers = set(args.null_markers)
    rows = []
    anomalies = []
    for f in files:
        reorder = f["header"] != base
        for i, rec in enumerate(f["records"], start=1):
            row = dict(zip(f["header"], rec))
            for col in base:
                v = row[col]
                if (trim_all or col in args.trim) and v != v.strip():
                    nv = v.strip()
                    changes.append([f["name"], i, col, col, v, nv, "trim"])
                    row[col] = v = nv
                if markers and (null_all or col in args.null_columns) and v in markers:
                    changes.append([f["name"], i, col, col, v, "", "null_marker"])
                    row[col] = ""
                if is_formula_trigger(row[col]):
                    anomalies.append([
                        f["name"], i, col, row[col], "formula_trigger",
                        "value starts with = + - @ TAB or CR; may execute as a "
                        "formula in spreadsheet apps"])
            rows.append((f["name"], i, row))
        if reorder:
            changes.append([f["name"], "", "", "", "", "",
                            "columns_reordered_to_first_file"])

    tmp = out + ".partial"
    if os.path.exists(tmp):
        raise OutputConflict(
            f"leftover temporary directory exists: {tmp}; remove it manually")
    os.makedirs(tmp)
    try:
        def w(name, header, data):
            with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="") as fh:
                cw = csv.writer(fh, lineterminator="\r\n")
                cw.writerow(header)
                cw.writerows(data)

        merged = [[row[c] for c in base] for _, _, row in rows]
        w("merged.csv", base, merged)
        w("changes.csv",
          ["source_file", "source_record", "column", "old_column_name",
           "old_value", "new_value", "rule"],
          changes)
        w("anomalies.csv",
          ["source_file", "source_record", "column", "value", "type", "note"],
          anomalies)
        summary = {
            "tool_version": VERSION,
            "edition": "lite",
            "inputs": [{
                "file": f["name"], "sha256": f["sha256"], "encoding": f["encoding"],
                "delimiter": "tab" if f["delimiter"] == "\t" else ",",
                "records": len(f["records"])} for f in files],
            "records_in": total,
            "records_out": len(rows),
            "count_check": total == len(rows),
            "columns": base,
            "changes_logged": len(changes),
            "anomalies": {
                "formula_trigger": sum(1 for a in anomalies if a[4] == "formula_trigger")},
            "date_conversion": "never (all columns kept as text)",
        }
        with open(os.path.join(tmp, "summary.json"), "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
        with open(os.path.join(tmp, "summary.md"), "w", encoding="utf-8") as fh:
            fh.write(render_md(summary))
        if not summary["count_check"]:
            raise ConflictError("internal count check failed; output discarded")
        os.rename(tmp, out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return summary


def render_md(s):
    L = ["# CSV cleanup summary (lite)", "",
         f"Tool version: {s['tool_version']} ({s['edition']})", "",
         "## Inputs", "",
         "| file | records | encoding | delimiter | sha256 |",
         "|---|---|---|---|---|"]
    for i in s["inputs"]:
        L.append(
            f"| {i['file']} | {i['records']} | {i['encoding']} | "
            f"{i['delimiter']} | `{i['sha256'][:16]}…` |")
    L += ["", "## Counts", "",
          f"- Records in: {s['records_in']}",
          f"- Records out: {s['records_out']}",
          f"- Count check (in = out): {'OK' if s['count_check'] else 'FAILED'}",
          f"- Changes logged (trims, null markers, reorder): "
          f"{s['changes_logged']} (see changes.csv)",
          f"- Formula-trigger warnings: {s['anomalies']['formula_trigger']}",
          f"- Dates: {s['date_conversion']}", ""]
    return "\n".join(L) + "\n"


def main(argv=None):
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
        s = run(args)
        print(
            f"OK: {s['records_in']} records in, {s['records_out']} out. "
            f"{s['changes_logged']} change(s) logged, "
            f"{s['anomalies']['formula_trigger']} formula warning(s). "
            f"Output: {args.out}")
        return 0
    except (UserError, ConflictError, OutputConflict) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return e.code
    except Exception as e:  # pragma: no cover
        print(f"UNEXPECTED ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
