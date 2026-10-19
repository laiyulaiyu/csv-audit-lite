"""Acceptance tests for csv-audit-lite. Run:
  python3 -m unittest -v tests.test_clean_csv_lite
from the repo root (or set PKG_DIR).
"""
import csv, hashlib, json, os, shutil, subprocess, sys, tempfile, time, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.environ.get("PKG_DIR") or os.path.join(
    ROOT, "plugins", "csv-audit-lite", "skills", "csv-audit-lite")
TIMINGS = {}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="csvaudit-lite-")
        cls.pkg = os.path.join(cls.root, "csv-audit-lite")
        shutil.copytree(PKG, cls.pkg)
        cls.script = os.path.join(cls.pkg, "scripts", "clean_csv_lite.py")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        self.d = tempfile.mkdtemp(dir=self.root)

    def write(self, name, data, enc="utf-8"):
        p = os.path.join(self.d, name)
        with open(p, "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode(enc))
        return p

    def run_tool(self, *args):
        t = time.perf_counter()
        r = subprocess.run(
            [sys.executable, self.script, *args],
            capture_output=True, text=True, cwd=self.d)
        r.elapsed = time.perf_counter() - t
        return r

    def out(self, name="out"):
        return os.path.join(self.d, name)

    def read(self, outdir, name, enc="utf-8"):
        with open(os.path.join(outdir, name), encoding=enc, newline="") as f:
            return list(csv.reader(f))


class T01LeadingZeros(Base):
    def test_leading_zeros_and_long_ids(self):
        p = self.write("a.csv", "id,acct,zip\n00123,123456789012345678901234,02134\n0007,9007199254740993,00501\n")
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.read(self.out(), "merged.csv")
        self.assertEqual(rows[1], ["00123", "123456789012345678901234", "02134"])
        self.assertEqual(rows[2], ["0007", "9007199254740993", "00501"])


class T02Encodings(Base):
    TEXT = "编号,姓名,城市\n001,张三,北京\n002,李四,Zürich\n"

    def _ok(self, p, *extra):
        r = self.run_tool(p, "--out", self.out(), *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.read(self.out(), "merged.csv")
        self.assertEqual(rows[0], ["编号", "姓名", "城市"])
        self.assertEqual(rows[2], ["002", "李四", "Zürich"])
        return json.load(open(os.path.join(self.out(), "summary.json"), encoding="utf-8"))

    def test_utf8(self):
        s = self._ok(self.write("u.csv", self.TEXT))
        self.assertEqual(s["inputs"][0]["encoding"], "utf-8")

    def test_utf8_bom(self):
        s = self._ok(self.write("b.csv", b"\xef\xbb\xbf" + self.TEXT.encode()))
        self.assertEqual(s["inputs"][0]["encoding"], "utf-8-sig")

    def test_gb18030_explicit(self):
        s = self._ok(self.write("g.csv", self.TEXT, "gb18030"), "--encoding", "gb18030")
        self.assertEqual(s["inputs"][0]["encoding"], "gb18030")

    def test_gb18030_auto_errors_clearly(self):
        p = self.write("g.csv", self.TEXT, "gb18030")
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 2)
        self.assertIn("--encoding gb18030", r.stderr)
        self.assertFalse(os.path.exists(self.out()))

    def test_tab_delimited(self):
        p = self.write("t.tsv", "id\tname\n001\ta,b\n")
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read(self.out(), "merged.csv")[1], ["001", "a,b"])

    def test_ambiguous_delimiter_errors(self):
        p = self.write("x.csv", "id,name\tx\n1,2\t3\n")
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 2)
        self.assertIn("--delimiter", r.stderr)


class T03Quoting(Base):
    def test_quotes_commas_newlines(self):
        data = 'id,note\n1,"hello, world"\n2,"line1\nline2"\n3,"say ""hi"""\n'
        p = self.write("q.csv", data)
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.read(self.out(), "merged.csv")
        self.assertEqual(len(rows) - 1, 3)
        self.assertEqual(rows[2][1], "line1\nline2")
        self.assertEqual(rows[3][1], 'say "hi"')
        s = json.load(open(os.path.join(self.out(), "summary.json")))
        self.assertEqual(s["records_in"], 3)

    def test_malformed_width_rejected(self):
        p = self.write("m.csv", "a,b\n1,2\n3\n")
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 3)
        self.assertFalse(os.path.exists(self.out()))


class T04PaidFlagsRejected(Base):
    def test_dedupe_flag_unrecognized(self):
        p = self.write("a.csv", "id,v\n1,a\n")
        r = self.run_tool(p, "--out", self.out(), "--dedupe-keys", "id")
        self.assertEqual(r.returncode, 2)
        self.assertIn("unrecognized arguments", r.stderr)
        self.assertNotIn("buy", r.stderr.lower())
        self.assertNotIn("gumroad", r.stderr.lower())
        self.assertFalse(os.path.exists(self.out()))

    def test_rename_flag_unrecognized(self):
        p = self.write("a.csv", "id,v\n1,a\n")
        r = self.run_tool(p, "--out", self.out(), "--rename", '{"a":"b"}')
        self.assertEqual(r.returncode, 2)
        self.assertIn("unrecognized arguments", r.stderr)


class T05Schema(Base):
    def test_different_columns_reported(self):
        a = self.write("a.csv", "id,name,email\n1,a,x\n")
        b = self.write("b.csv", "id,name,phone\n2,b,y\n")
        r = self.run_tool(a, b, "--out", self.out())
        self.assertEqual(r.returncode, 3)
        self.assertIn("missing ['email']", r.stderr)
        self.assertIn("extra ['phone']", r.stderr)
        self.assertFalse(os.path.exists(self.out()))

    def test_duplicate_column_names(self):
        a = self.write("a.csv", "id,name,name\n1,a,b\n")
        r = self.run_tool(a, "--out", self.out())
        self.assertEqual(r.returncode, 3)
        self.assertIn("duplicate column names ['name']", r.stderr)

    def test_reorder_same_columns(self):
        a = self.write("a.csv", "id,email\n1,x\n")
        b = self.write("b.csv", "email,id\ny,2\n")
        r = self.run_tool(a, b, "--out", self.out())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read(self.out(), "merged.csv"),
                         [["id", "email"], ["1", "x"], ["2", "y"]])
        rules = [c[6] for c in self.read(self.out(), "changes.csv")[1:]]
        self.assertIn("columns_reordered_to_first_file", rules)


class T06DatesNulls(Base):
    def test_dates_untouched_nulls_only_explicit(self):
        data = "d,v,w\n03/04/2024,NULL,NULLABLE\n2024-4-3,N/A,none\n 01.02.03 ,,NULL \n"
        p = self.write("x.csv", data)
        r = self.run_tool(p, "--out", self.out(), "--null-markers", "NULL,N/A")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.read(self.out(), "merged.csv")
        self.assertEqual(rows[1], ["03/04/2024", "", "NULLABLE"])
        self.assertEqual(rows[2], ["2024-4-3", "", "none"])
        self.assertEqual(rows[3], [" 01.02.03 ", "", "NULL "])

    def test_trim_then_null(self):
        p = self.write("x.csv", "a,b\n NULL ,  keep me \n")
        r = self.run_tool(p, "--out", self.out(), "--trim", "*", "--null-markers", "NULL")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read(self.out(), "merged.csv")[1], ["", "keep me"])
        self.assertEqual(len(self.read(self.out(), "changes.csv")) - 1, 3)


class T07Formula(Base):
    def test_formula_warning_no_safe_copy(self):
        p = self.write("f.csv", 'id,v\n1,=SUM(A1:A2)\n2,-12.5\n3,@cmd\n4,+1+1\n5,normal\n')
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 0, r.stderr)
        merged = self.read(self.out(), "merged.csv")
        self.assertEqual(merged[1][1], "=SUM(A1:A2)")
        an = [a for a in self.read(self.out(), "anomalies.csv")[1:] if a[4] == "formula_trigger"]
        self.assertEqual(sorted(a[3] for a in an), ["+1+1", "=SUM(A1:A2)", "@cmd"])
        self.assertFalse(os.path.exists(os.path.join(self.out(), "merged.excel-safe.csv")))


class T08EmptyOversize(Base):
    def test_empty_file(self):
        p = self.write("e.csv", "")
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 2)
        self.assertIn("empty", r.stderr)
        self.assertFalse(os.path.exists(self.out()))

    def test_header_only(self):
        p = self.write("h.csv", "a,b\n")
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 2)
        self.assertIn("no data records", r.stderr)
        self.assertFalse(os.path.exists(self.out()))

    def test_over_10000(self):
        p = self.write("big.csv", "id\n" + "".join(f"{i}\n" for i in range(10001)))
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 2)
        self.assertIn("at most 10000", r.stderr)
        self.assertFalse(os.path.exists(self.out()))

    def test_too_many_files(self):
        ps = [self.write(f"f{i}.csv", "a\n1\n") for i in range(6)]
        r = self.run_tool(*ps, "--out", self.out())
        self.assertEqual(r.returncode, 2)


class T09Scale(Base):
    def test_10000_records(self):
        lines = ["id,name,city,amount"]
        for i in range(10000):
            lines.append(f'{i:06d}, name {i} ,"City, {i % 50}",{i * 1.5}')
        p1 = self.write("p1.csv", "\n".join(lines[:5001]) + "\n")
        p2 = self.write("p2.csv", "\n".join([lines[0]] + lines[5001:]))
        r = self.run_tool(p1, p2, "--out", self.out(), "--trim", "name")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = json.load(open(os.path.join(self.out(), "summary.json")))
        self.assertEqual(s["records_in"], 10000)
        self.assertEqual(s["records_out"], 10000)
        self.assertEqual(s["changes_logged"], 10000)
        TIMINGS["10000_records_seconds"] = round(r.elapsed, 3)


class T10Determinism(Base):
    def test_repeat_identical_and_source_unchanged(self):
        a = self.write("a.csv", "id,v\n001, x \n001,y\n002,=1\n")
        b = self.write("b.csv", b"\xef\xbb\xbfid,v\n003,z\n")
        before = (sha(a), sha(b))
        args = ["--trim", "v"]
        r1 = self.run_tool(a, b, "--out", self.out("o1"), *args)
        r2 = self.run_tool(a, b, "--out", self.out("o2"), *args)
        self.assertEqual((r1.returncode, r2.returncode), (0, 0), r1.stderr + r2.stderr)
        f1, f2 = sorted(os.listdir(self.out("o1"))), sorted(os.listdir(self.out("o2")))
        self.assertEqual(f1, f2)
        for n in f1:
            self.assertEqual(sha(os.path.join(self.out("o1"), n)),
                             sha(os.path.join(self.out("o2"), n)), n)
        self.assertEqual((sha(a), sha(b)), before)
        s = json.load(open(os.path.join(self.out("o1"), "summary.json")))
        self.assertEqual(s["inputs"][0]["sha256"], before[0])


class T11OutputConflict(Base):
    def test_existing_output_dir(self):
        p = self.write("a.csv", "a\n1\n")
        os.makedirs(self.out())
        marker = os.path.join(self.out(), "keep.txt")
        open(marker, "w").write("user file")
        r = self.run_tool(p, "--out", self.out())
        self.assertEqual(r.returncode, 4)
        self.assertEqual(os.listdir(self.out()), ["keep.txt"])

    def test_error_leaves_no_partial_output(self):
        a = self.write("a.csv", "a,b\n1,2\n")
        b = self.write("b.csv", "a,c\n1,2\n")
        r = self.run_tool(a, b, "--out", self.out())
        self.assertEqual(r.returncode, 3)
        self.assertFalse(os.path.exists(self.out()))
        self.assertFalse(os.path.exists(self.out() + ".partial"))

    def test_missing_input(self):
        r = self.run_tool("nope.csv", "--out", self.out())
        self.assertEqual(r.returncode, 2)
        self.assertIn("not found", r.stderr)


class T12BundledSample(Base):
    def test_bundled_sample_matches_expected(self):
        assets = os.path.join(self.pkg, "assets")
        r = self.run_tool(
            os.path.join(assets, "sample-input.csv"),
            os.path.join(assets, "sample-input-2.csv"),
            "--out", self.out(),
            "--trim", "name",
            "--null-markers", "N/A,NULL",
            "--null-columns", "email")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            open(os.path.join(self.out(), "merged.csv"), "rb").read(),
            open(os.path.join(assets, "sample-expected.csv"), "rb").read())


class T13ReadmeCommand(Base):
    def test_readme_style_command_runs(self):
        a = self.write("a.csv", "id,name\n1, Alice \n")
        b = self.write("b.csv", "id,name\n2,N/A\n")
        r = self.run_tool(a, b, "--out", self.out("cleaned-1"),
                          "--trim", "*", "--null-markers", "N/A,NULL")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.read(self.out("cleaned-1"), "merged.csv")
        self.assertEqual(rows[1], ["1", "Alice"])
        self.assertEqual(rows[2], ["2", ""])


def tearDownModule():
    print("\nTIMINGS:", json.dumps(TIMINGS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
