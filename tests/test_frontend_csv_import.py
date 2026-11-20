from pathlib import Path


def test_supplier_and_marketplace_csv_importers_support_50_dynamic_rows():
    root = Path(__file__).resolve().parents[1]
    html = (root / "index.html").read_text(encoding="utf-8")

    assert "function getNumberedSlotCount(prefix)" in html
    assert "function ensureNumberedSlots(prefix,requestedCount)" in html
    assert "Math.min(50,Math.max(3,requestedCount))" in html
    assert 'ensureNumberedSlots("supplierQuote",parsed.length)' in html
    assert 'ensureNumberedSlots("marketplace",parsed.length)' in html
    assert html.count("records.length>50") == 2
    assert 'getNumberedSlotCount("supplierQuote")' in html
    assert 'getNumberedSlotCount("marketplace")' in html
    assert "records.length>3" not in html
    assert "Up to 50 rows are imported" in html
    assert "زیادہ سے زیادہ 50" in html
