#!/usr/bin/env python3
"""Generate a synthetic 2-page invoice PDF for integration testing.

Output: tests/fixtures/test_invoice.pdf

Usage:
    uv run python scripts/generate-test-invoice.py

Requires reportlab.  If not installed:
    uv pip install reportlab
"""

import os
import sys

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except ImportError:
    print(
        "ERROR: reportlab is not installed.\n"
        "Install it with:  uv pip install reportlab\n"
        "Then re-run:      uv run python scripts/generate-test-invoice.py"
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "tests", "fixtures")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "test_invoice.pdf")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    "InvoiceTitle",
    parent=styles["Title"],
    fontSize=24,
    spaceAfter=12,
    textColor=colors.HexColor("#1a1a2e"),
)
heading_style = ParagraphStyle(
    "InvoiceHeading",
    parent=styles["Heading2"],
    fontSize=14,
    spaceBefore=12,
    spaceAfter=6,
)
normal_style = styles["Normal"]

# ---------------------------------------------------------------------------
# Invoice data (deterministic for assertions in tests)
# ---------------------------------------------------------------------------
VENDOR = "Acme Corp"
INVOICE_NUM = "INV-2026-001"
INVOICE_DATE = "2026-01-15"
BILL_TO = "Test Borrower"
LINE_ITEMS = [
    ("Widget A", 400.00),
    ("Service B", 534.56),
    ("Shipping", 300.00),
]
SUBTOTAL = sum(amt for _, amt in LINE_ITEMS)  # 1234.56
TAX = 0.00
TOTAL = SUBTOTAL + TAX  # 1234.56
PAYMENT_TERMS = "Net 30"


def build_pdf():
    """Build a 2-page invoice PDF using reportlab platypus."""
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    elements = []

    # ------------------------------------------------------------------
    # PAGE 1 -- Header + line items
    # ------------------------------------------------------------------
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Spacer(1, 12))

    # Metadata table (vendor, invoice #, date, bill-to)
    meta_data = [
        ["Vendor:", VENDOR],
        ["Invoice #:", INVOICE_NUM],
        ["Invoice Date:", INVOICE_DATE],
        ["Bill To:", BILL_TO],
    ]
    meta_table = Table(meta_data, colWidths=[1.5 * inch, 4 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 24))

    # Line items heading
    elements.append(Paragraph("Line Items", heading_style))
    elements.append(Spacer(1, 6))

    # Line items table
    li_header = ["#", "Description", "Amount"]
    li_rows = [li_header]
    for idx, (desc, amt) in enumerate(LINE_ITEMS, 1):
        li_rows.append([str(idx), desc, f"${amt:,.2f}"])
    li_table = Table(li_rows, colWidths=[0.5 * inch, 4 * inch, 1.5 * inch])
    li_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(li_table)

    # Force page break before totals (simulates a 2-page invoice)
    elements.append(Spacer(1, 350))

    # ------------------------------------------------------------------
    # PAGE 2 -- Totals + payment terms
    # ------------------------------------------------------------------
    elements.append(Paragraph("Summary", heading_style))
    elements.append(Spacer(1, 12))

    totals_data = [
        ["Subtotal:", f"${SUBTOTAL:,.2f}"],
        ["Tax:", f"${TAX:,.2f}"],
        ["Total Amount:", f"${TOTAL:,.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[2 * inch, 2 * inch])
    totals_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        # Bold + larger for total row
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 14),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 24))

    elements.append(Paragraph(
        f"<b>Payment Terms:</b> {PAYMENT_TERMS}",
        normal_style,
    ))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(
        "Thank you for your business.",
        normal_style,
    ))

    # Build PDF
    doc.build(elements)
    print(f"Generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
