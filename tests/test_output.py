from london_scorer import output


def test_write_creates_md_and_csv(tmp_path):
    rows = [{"district": "A", "commute_am": 30, "commute_pm": 35, "primary_good": 4,
             "secondary_good": 2, "score": 0.8},
            {"district": "B", "commute_am": 45, "commute_pm": 50, "primary_good": 1,
             "secondary_good": 0, "score": 0.3}]
    md = tmp_path / "out.md"
    csv = tmp_path / "out.csv"
    output.write(rows, str(md), str(csv))
    text = md.read_text()
    assert "district" in text
    assert text.index("A") < text.index("B")   # A ranked higher (score 0.8 > 0.3)
    assert csv.exists()


def test_write_md_has_expected_columns(tmp_path):
    rows = [{"district": "N1", "commute_am": 25, "commute_pm": 30,
             "primary_good": 3, "score": 0.9}]
    md = tmp_path / "out.md"
    csv = tmp_path / "out.csv"
    output.write(rows, str(md), str(csv))
    text = md.read_text()
    for col in ("district", "commute_am", "commute_pm", "primary_good", "score"):
        assert col in text, f"Expected column '{col}' in Markdown output"


def test_write_csv_has_all_rows(tmp_path):
    rows = [{"district": "A", "score": 0.9},
            {"district": "B", "score": 0.5},
            {"district": "C", "score": 0.1}]
    md = tmp_path / "out.md"
    csv = tmp_path / "out.csv"
    output.write(rows, str(md), str(csv))
    lines = csv.read_text().splitlines()
    # header + 3 data lines
    assert len(lines) == 4


def test_write_creates_parent_dirs(tmp_path):
    """output.write should create intermediate directories if needed."""
    rows = [{"district": "X", "score": 0.5}]
    nested_md = tmp_path / "deep" / "nested" / "out.md"
    nested_csv = tmp_path / "deep" / "nested" / "out.csv"
    output.write(rows, str(nested_md), str(nested_csv))
    assert nested_md.exists()
    assert nested_csv.exists()


def test_write_ranked_by_score(tmp_path):
    """Rows are written in descending score order regardless of input order."""
    rows = [{"district": "LOW", "score": 0.1},
            {"district": "HIGH", "score": 0.95},
            {"district": "MID", "score": 0.5}]
    md = tmp_path / "out.md"
    csv = tmp_path / "out.csv"
    output.write(rows, str(md), str(csv))
    text = md.read_text()
    assert text.index("HIGH") < text.index("MID") < text.index("LOW")
