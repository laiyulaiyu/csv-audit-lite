# csv-audit-lite 中文用法（v0.1.0）

免费、离线的 CSV 合并清洗。每处改动写入 `changes.csv`。脚本：`scripts/clean_csv_lite.py`。

## 基本命令
```
python3 scripts/clean_csv_lite.py a.csv b.csv --out ./cleaned-1 \
  --trim "*" --null-markers "N/A,NULL"
```

国内导出常是 GB18030：
```
python3 scripts/clean_csv_lite.py export.csv --out ./cleaned-1 --encoding gb18030
```

## 会做 / 不会做
- 会：合并列名相同的 1–5 个文件；去首尾空格；把你指定的空值标记置空；保留前导零与日期原文；警告公式注入；不改原文件。
- 不会：去重、改列名映射、Excel 安全副本、配置文件复跑。这些在付费完整版。

## 退出码
0 成功；2 用法/输入问题；3 列结构冲突或坏行；4 输出目录已存在。
