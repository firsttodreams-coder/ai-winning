from pathlib import Path


def test_supplier_and_marketplace_csv_importers_support_50_dynamic_rows():
    root = Path(__file__).resolve().parents[1]
    html = (root / "index.html").read_text(encoding="utf-8")

    assert "function getNumberedSlotCount(prefix)" in html
    assert "function ensureNumberedSlots(prefix,requestedCount)" in html
    assert "Math.min(50,Math.max(3,requestedCount))" in html
    assert 'ensureNumberedSlots("supplierQuote",parsed.length)' in html
    assert 'ensureNumberedSlots("marketplace",parsed.length)' in html
    assert html.count("records.length>50") == 3
    assert 'getNumberedSlotCount("supplierQuote")' in html
    assert 'getNumberedSlotCount("marketplace")' in html
    assert "records.length>3" not in html
    assert "Up to 50 rows are imported" in html
    assert "زیادہ سے زیادہ 50" in html

def test_csv_parser_supports_quoted_commas_escaped_quotes_and_multiline_fields():
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the inline CSV parser test")

    root = Path(__file__).resolve().parents[1]
    html = (root / "index.html").read_text(encoding="utf-8")
    start = html.index("function parseSupplierQuoteCsv(source){")
    end = html.index('$(\"downloadMarketCsvTemplate\")', start)
    parser = html[start:end]
    sample = 'name,description\r\nWidget,"large, blue"\r\n"Quoted ""item""","line 1\nline 2"\r\n'
    expected = [["name", "description"], ["Widget", "large, blue"], ['Quoted "item"', "line 1\nline 2"]]
    malformed = [
        ('a,b\nbad"quote,x', "quote inside unquoted field"),
        ('a,b\n"quoted"x,y', "unexpected character after closing quote"),
        ('a,b\n"unterminated,x', "unclosed quoted field"),
    ]
    script = parser + "\nconst assert = require('node:assert/strict');\n"
    script += "assert.deepStrictEqual(parseSupplierQuoteCsv(" + repr(sample) + "), " + repr(expected) + ");\n"
    for value, message in malformed:
        script += "assert.throws(() => parseSupplierQuoteCsv(" + repr(value) + "), /" + message + "/);\n"
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_csv_importers_report_record_numbers_and_reject_ambiguous_headers():
    root = Path(__file__).resolve().parents[1]
    html = (root / "index.html").read_text(encoding="utf-8")

    assert html.count("CSV headers must be non-empty and unique") == 3
    assert html.count("column count does not match header") == 3
    assert 'CSV record "+recordNumber+":"' in html
    assert "error.message" in html
