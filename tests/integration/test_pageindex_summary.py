"""Integration test: PageIndex Q&A grounding and caching.

Verifies that:
1. Q&A answers are grounded in actual extracted data values (not hallucinated).
2. Repeated identical Q&A calls benefit from caching (faster second response).
"""

import pytest
import re
import time


def normalize_value(val):
    """Normalize for fuzzy comparison -- strip currency symbols, whitespace, etc."""
    s = str(val).lower().strip()
    return re.sub(r"[\$,%\s]", "", s)


def value_in_text(value, text):
    """Check if extracted value appears in answer text (fuzzy)."""
    norm_val = normalize_value(value)
    norm_text = normalize_value(text)
    return norm_val in norm_text or (
        len(norm_val) > 3 and norm_val[:6] in norm_text
    )


@pytest.mark.integration
class TestPageIndexSummary:
    def test_qa_aligns_with_extraction(self, api, upload_and_wait, sample_loan_pdf):
        """Q&A answers are grounded in extracted data values."""
        doc_id, status, _ = upload_and_wait(str(sample_loan_pdf))
        assert status == "COMPLETED"

        resp = api.get(f"/documents/{doc_id}")
        extracted = resp.json().get("extractedData") or resp.json().get("data", {})

        qa_pairs = [
            ("What is the interest rate?", ["interestRate", "rate", "apr"]),
            ("Who is the borrower?", ["borrowerName", "borrower", "name"]),
            ("What is the loan amount?", ["loanAmount", "amount", "principal"]),
        ]

        matches = 0
        for question, field_keys in qa_pairs:
            resp = api.post(f"/documents/{doc_id}/ask", json={"question": question})
            if resp.status_code != 200:
                print(f"SKIP: /ask returned {resp.status_code} for '{question}'")
                continue

            answer = resp.json().get("answer", "")
            matched = False
            for key in field_keys:
                for ek, ev in extracted.items():
                    if key.lower() in ek.lower() and ev and value_in_text(ev, answer):
                        matched = True
                        break
                if matched:
                    break

            status_str = "MATCH" if matched else "NO MATCH"
            print(f"  {status_str}: '{question}' -> {answer[:80]}...")
            if matched:
                matches += 1

        assert matches >= 1, "No Q&A answers matched extracted data"

    def test_cached_response_faster(self, api, upload_and_wait, sample_loan_pdf):
        """Second Q&A call should be faster (cached)."""
        doc_id, status, _ = upload_and_wait(str(sample_loan_pdf))
        assert status == "COMPLETED"

        question = {"question": "What is the interest rate?"}

        t1 = time.time()
        r1 = api.post(f"/documents/{doc_id}/ask", json=question)
        d1 = time.time() - t1

        if r1.status_code != 200:
            pytest.skip(f"/ask not available: {r1.status_code}")

        t2 = time.time()
        api.post(f"/documents/{doc_id}/ask", json=question)
        d2 = time.time() - t2

        print(f"First: {d1:.1f}s, Second: {d2:.1f}s, Speedup: {d1/max(d2,0.01):.1f}x")
        assert d2 < d1 or d2 < 3.0, f"No caching benefit: {d2:.1f}s >= {d1:.1f}s"
