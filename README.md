# csv-audit-lite

免费、离线的 CSV 合并清洗技能（Agent Skill），每处改动都有记录。支持 UTF-8 与 GB18030。
A free, offline Agent Skill to merge and clean CSV exports, with a log of every change. UTF-8 and GB18030 supported.

## 它做什么 / What it does
- 合并 1–5 个列名相同的 CSV/TSV（列顺序可以不同；编码 UTF-8 / UTF-8 BOM / GB18030）。
  Merges 1–5 CSV/TSV files with the same columns (any order; UTF-8 / UTF-8 BOM / GB18030).
- 前导零、长编号、日期一律按原文保留，不做类型转换。
  Keeps leading zeros, long IDs and dates exactly as text.
- 只清理你指定的列：去首尾空格、把你列出的空值标记（如 N/A）置空。
  Trims whitespace and blanks the exact null markers you list, only in the columns you name.
- 每处改动都写进 changes.csv；公式注入风险写进 anomalies.csv。
  Every change goes to changes.csv; formula-injection risks go to anomalies.csv.
- 不修改原文件，不覆盖已有目录，出错不留半成品。
  Never edits inputs, never overwrites an existing folder, leaves no partial output on error.

不做：去重、改列名映射、Excel 安全副本、配置文件复跑、XLSX。
Not included: deduplication, column rename mapping, Excel-safe copy, config-file runs, XLSX.

## 安装 / Install
- Claude Code:
  ```
  claude plugin marketplace add laiyulaiyu/csv-audit-lite
  claude plugin install csv-audit-lite@laiyu-data-tools
  ```
- 其他支持 Agent Skills 的 agent：把 `plugins/csv-audit-lite/skills/csv-audit-lite/` 复制到它的技能目录。
  Other Agent Skills–compatible agents: copy that folder into the agent's skills directory.
- 也可以直接运行 / Or run directly:
  ```
  python3 plugins/csv-audit-lite/skills/csv-audit-lite/scripts/clean_csv_lite.py \
    a.csv b.csv --out ./cleaned-1 --trim "*" --null-markers "N/A,NULL"
  ```
  国内 GB18030 文件加上 `--encoding gb18030`。

## 测试情况 / Test status
- 自动化测试 **28** 条，在 Linux 上的 Python 3.11 和 3.13 下全部通过（2026-10-19，见 CHANGELOG / `20-github-lite-test-report.md`）。
  **28** automated tests pass on Linux with Python 3.11 and 3.13.
- Windows、macOS 没测过。Claude Code、Codex、Cursor 里的实际使用也没测过。
  Windows and macOS are untested. Real use inside Claude Code, Codex or Cursor is untested.
- 只用 Python 标准库，脚本不联网。注意：你让 agent 显示出来的文件内容，模型是能看到的。
  Standard library only; the script makes no network calls. Your agent's model can still see any file content it displays.

## 完整版 / Full version
如果你需要按关键列去重（先预览分组，再选保留第一条或最后一条）、改列名映射、Excel 安全副本、来源列或配置文件复跑，有一个付费的完整版：
If you need key-based dedupe with preview, rename mapping, an Excel-safe copy, source columns or re-runnable configs, there is a paid full version:
- CSV Cleanup Audit — Gumroad (USD 9): https://gipsonia1.gumroad.com/l/csv-cleanup-audit · SkillHQ (EUR 9): https://skillhq.dev/skills/laiyu/csv-cleanup-audit

同一作者还有一个银行流水和账本对账的技能（付费）：
The same author also sells a bank-statement vs. ledger reconciler (paid):
- Bank-Ledger Reconciler — https://gipsonia1.gumroad.com/l/bank-ledger-reconciler · https://skillhq.dev/skills/laiyu/bank-ledger-reconciler

## 协议 / License
MIT（只适用于本仓库）。付费版用单独的协议。
MIT (this repository only). The paid versions are under a separate license.

## 反馈 / Feedback
欢迎提 Issue：说清楚你的数据场景（不要上传真实数据）。
Issues welcome. Describe your use case, and please do not upload real data.
