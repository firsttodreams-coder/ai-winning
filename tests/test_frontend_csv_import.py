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
    assert 'required=["marketplace","price"]' in html
    assert 'allowed=["marketplace","price","shipping_cost","listing_url","observed_sold_count","captured_at"]' in html
    assert "CSV must include marketplace and price columns" in html
    assert "CSV contains unsupported columns:" in html
    assert html.count("column count does not match header") == 3
    assert 'CSV record "+recordNumber+":' in html
    assert "error.message" in html

def test_supplier_catalog_preview_survives_browser_storage_failure():
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the supplier catalog storage helper test")

    root = Path(__file__).resolve().parents[1]
    html = (root / "index.html").read_text(encoding="utf-8")
    start = html.index("async function saveSupplierCatalogSafely(")
    end = html.index("\nconst supplierCatalogEscape", start)
    helper = html[start:end]
    handler_start = html.index('$("runSupplierCatalogImport").addEventListener')
    handler_end = html.index("\n});\nrenderSavedSupplierCatalog();", handler_start)
    handler = html[handler_start:handler_end]

    assert 'const saved=await saveSupplierCatalogSafely(rows,savedAt)' in handler
    assert 'box.innerHTML=rows.length?' in handler
    assert 't.supplierCatalogSaveWarning' in handler

    script = """
let shouldFail = false;
let captured = null;
async function supplierCatalogStore(...args) {
    captured = args;
    if (shouldFail) throw new Error("storage quota exceeded");
}
const console = { warn: () => {} };
const assert = require("node:assert/strict");
""" + helper + """
(async () => {
    const rows = [{supplier_id:"zambeel",country:"PK",product_id:"BL-01",title:"Blender"}];
    assert.equal(await saveSupplierCatalogSafely(rows,"2026-11-22T00:00:00Z"),true);
    assert.equal(captured[0],"readwrite");
    assert.equal(captured[2][0].record_id,"zambeel::PK::BL-01");
    assert.equal(captured[2][0].saved_at,"2026-11-22T00:00:00Z");
    shouldFail = true;
    assert.equal(await saveSupplierCatalogSafely(rows,"2026-11-22T00:00:00Z"),false);
})().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
