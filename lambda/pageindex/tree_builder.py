"""PageIndex tree builder — adapted from VectifyAI/PageIndex (MIT license).

Builds a hierarchical tree index from PDF documents using Claude Haiku 4.5
via AWS Bedrock. The tree maps document structure (sections, subsections)
to physical page ranges, enabling:
  1. Document understanding (browsable TOC with summaries)
  2. Tree-assisted extraction (precise section→page targeting)

Adapted from: https://github.com/VectifyAI/PageIndex
License: MIT (Copyright 2025 Vectify AI)
"""

from __future__ import annotations

import json
import re
import time
from io import BytesIO
from typing import Any

from llm_client import (
    bedrock_converse,
    bedrock_converse_threaded,
    bedrock_converse_with_stop,
)
from token_counter import count_tokens

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_TOC_CHECK_PAGES = 20
DEFAULT_MAX_PAGES_PER_NODE = 10
DEFAULT_MAX_TOKENS_PER_NODE = 20000
MAX_CHARS_PER_PAGE = 3000  # Truncate very long pages for LLM calls
MAX_GROUP_TOKENS = 20000   # Token budget per LLM batch


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------
def extract_json(text: str) -> Any:
    """Extract JSON from LLM response, handling markdown fences and quirks."""
    if not text or text == "Error":
        return None
    # Strip markdown code fences
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = text.strip()
    # Fix common LLM JSON issues
    text = text.replace("None", "null").replace("True", "true").replace("False", "false")
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object or array in the text
        for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    continue
        return None


# ---------------------------------------------------------------------------
# PDF text extraction (reuses existing PyPDF + PyMuPDF pattern)
# ---------------------------------------------------------------------------
def extract_page_texts(pdf_bytes: bytes) -> list[dict]:
    """Extract text from each page of a PDF.

    Returns list of {page_num (1-based), text, tokens}.
    Uses PyPDF2 first, falls back to PyMuPDF for pages with no text.
    """
    pages = []
    texts_pypdf = _extract_with_pypdf(pdf_bytes)
    texts_fitz = None  # lazy load

    for i, text in enumerate(texts_pypdf):
        page_num = i + 1
        if len(text.strip()) < 50:
            # Fallback to PyMuPDF
            if texts_fitz is None:
                texts_fitz = _extract_with_fitz(pdf_bytes)
            if i < len(texts_fitz) and len(texts_fitz[i].strip()) > len(text.strip()):
                text = texts_fitz[i]

        truncated = text[:MAX_CHARS_PER_PAGE]
        pages.append({
            "page_num": page_num,
            "text": truncated,
            "tokens": count_tokens(truncated),
        })
    return pages


def _extract_with_pypdf(pdf_bytes: bytes) -> list[str]:
    """Extract text using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(BytesIO(pdf_bytes))
        return [page.extract_text() or "" for page in reader.pages]
    except Exception as e:
        print(f"[PageIndex] PyPDF2 extraction failed: {e}")
        return []


def _extract_with_fitz(pdf_bytes: bytes) -> list[str]:
    """Extract text using PyMuPDF (fitz)."""
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        texts = [doc[i].get_text() or "" for i in range(len(doc))]
        doc.close()
        return texts
    except Exception as e:
        print(f"[PageIndex] PyMuPDF extraction failed: {e}")
        return []


# ---------------------------------------------------------------------------
# TOC Detection
# ---------------------------------------------------------------------------
TOC_DETECT_PROMPT = """Your job is to detect if there is a table of contents provided in the given text.
Given text:
{content}

Return JSON: {{"thinking": "<your reasoning>", "toc_detected": "<yes or no>"}}
Note: abstract, summary, notation list, figure list, table list, etc. are not table of contents."""


def find_toc_pages(
    pages: list[dict], max_check: int = DEFAULT_TOC_CHECK_PAGES, model: str = ""
) -> list[int]:
    """Scan first N pages for table of contents. Returns list of page numbers."""
    toc_pages = []
    check_limit = min(max_check, len(pages))

    for page in pages[:check_limit]:
        if len(page["text"].strip()) < 30:
            continue
        prompt = TOC_DETECT_PROMPT.format(content=page["text"])
        result = extract_json(bedrock_converse(prompt, model=model))
        if result and str(result.get("toc_detected", "")).lower() == "yes":
            toc_pages.append(page["page_num"])
            print(f"[PageIndex] TOC detected on page {page['page_num']}")

    return toc_pages


# ---------------------------------------------------------------------------
# TOC Extraction & Transformation
# ---------------------------------------------------------------------------
TOC_EXTRACT_PROMPT = """Your job is to extract the full table of contents from the given text.
Replace any "..." or "....." with ":".
Given text:
{content}

Directly return the full table of contents content."""

TOC_HAS_PAGE_NUMBERS_PROMPT = """You will be given a table of contents. Your job is to detect if there are page numbers/indices given.
Given text:
{toc_content}

Return JSON: {{"thinking": "<your reasoning>", "page_index_given_in_toc": "<yes or no>"}}"""

TOC_TRANSFORM_PROMPT = """Transform the whole table of contents into a JSON format:
{{"table_of_contents": [{{"structure": "x.x.x", "title": "<section title>", "page": <page_number_or_null>}}, ...]}}

Table of contents:
{toc_content}

Transform the full table of contents in one go. Return only valid JSON."""


def extract_toc_content(
    pages: list[dict], toc_page_nums: list[int], model: str = ""
) -> str:
    """Extract raw TOC text from identified TOC pages."""
    toc_text = ""
    for page in pages:
        if page["page_num"] in toc_page_nums:
            toc_text += page["text"] + "\n"

    prompt = TOC_EXTRACT_PROMPT.format(content=toc_text)
    result, status = bedrock_converse_with_stop(prompt, model=model)

    # Continue generation if truncated
    if status == "max_output_reached":
        history = [
            {"role": "user", "content": [{"text": prompt}]},
            {"role": "assistant", "content": [{"text": result}]},
        ]
        continuation, _ = bedrock_converse_with_stop(
            "Please continue the generation of the table of contents. Directly output the remaining part.",
            model=model,
            chat_history=history,
        )
        result += continuation

    return result


def detect_toc_has_page_numbers(toc_content: str, model: str = "") -> bool:
    """Check if the extracted TOC contains page numbers."""
    prompt = TOC_HAS_PAGE_NUMBERS_PROMPT.format(toc_content=toc_content)
    result = extract_json(bedrock_converse(prompt, model=model))
    return result and str(result.get("page_index_given_in_toc", "")).lower() == "yes"


def transform_toc_to_json(
    toc_content: str, model: str = ""
) -> list[dict] | None:
    """Transform raw TOC text into structured JSON."""
    prompt = TOC_TRANSFORM_PROMPT.format(toc_content=toc_content)
    result, status = bedrock_converse_with_stop(prompt, model=model)

    if status == "max_output_reached":
        history = [
            {"role": "user", "content": [{"text": prompt}]},
            {"role": "assistant", "content": [{"text": result}]},
        ]
        continuation, _ = bedrock_converse_with_stop(
            "Please continue. Output only the remaining JSON entries.",
            model=model,
            chat_history=history,
        )
        result += continuation

    parsed = extract_json(result)
    if isinstance(parsed, dict):
        return parsed.get("table_of_contents", [])
    if isinstance(parsed, list):
        return parsed
    return None


# ---------------------------------------------------------------------------
# Page number mapping (TOC with page numbers → physical pages)
# ---------------------------------------------------------------------------
def calculate_page_offset(
    toc_entries: list[dict], pages: list[dict], model: str = ""
) -> int:
    """Calculate offset between TOC page numbers and physical PDF page indices.

    Some documents have roman-numeral front matter, so page "1" in the TOC
    might be physical page 5 in the PDF.
    """
    # Find first TOC entry with a page number
    for entry in toc_entries:
        toc_page = entry.get("page")
        if toc_page is None:
            continue
        toc_page = int(toc_page)
        title = entry.get("title", "")

        # Search nearby physical pages for the title
        for offset in range(-5, 20):
            phys = toc_page + offset
            if 1 <= phys <= len(pages):
                page_text = pages[phys - 1]["text"].lower()
                title_lower = title.lower().strip()
                # Fuzzy: check if first 40 chars of title appear in page
                check = title_lower[:40]
                if check and check in page_text:
                    print(f"[PageIndex] Page offset: {offset} "
                          f"(TOC page {toc_page} = physical page {phys})")
                    return offset
    return 0


def apply_page_offset(toc_entries: list[dict], offset: int) -> list[dict]:
    """Apply calculated offset to TOC page numbers → physical indices."""
    for entry in toc_entries:
        if entry.get("page") is not None:
            entry["physical_index"] = int(entry["page"]) + offset
    return toc_entries


# ---------------------------------------------------------------------------
# Structure generation (no TOC path)
# ---------------------------------------------------------------------------
GENERATE_STRUCTURE_PROMPT = """You are an expert in extracting hierarchical tree structure from documents.

Given the following document text with <physical_index_X> page markers, generate a hierarchical
tree structure in JSON format.

Document text:
{text}

Return JSON array:
[{{"structure": "1", "title": "<section title>", "physical_index": <page_number>}},
 {{"structure": "1.1", "title": "<subsection>", "physical_index": <page_number>}},
 ...]

Rules:
- Use the "structure" field for hierarchy (1, 1.1, 1.2, 2, 2.1, etc.)
- physical_index should reference the <physical_index_X> tag where that section starts
- Capture ALL major sections and subsections
- Return only valid JSON array"""

CONTINUE_STRUCTURE_PROMPT = """Continue generating the hierarchical tree structure for the next part of the document.

Previous structure generated so far:
{previous}

New document text:
{text}

Return ONLY the additional JSON entries (not the previous ones).
Continue the numbering from where the previous part left off."""


def group_pages_for_llm(pages: list[dict], max_tokens: int = MAX_GROUP_TOKENS) -> list[str]:
    """Split pages into token-bounded groups with <physical_index_X> markers."""
    groups = []
    current_group = ""
    current_tokens = 0

    for page in pages:
        tagged = f"<physical_index_{page['page_num']}>\n{page['text']}\n"
        page_tokens = page["tokens"] + 10  # overhead for tags
        if current_tokens + page_tokens > max_tokens and current_group:
            groups.append(current_group)
            current_group = tagged
            current_tokens = page_tokens
        else:
            current_group += tagged
            current_tokens += page_tokens

    if current_group:
        groups.append(current_group)
    return groups


def generate_structure_no_toc(
    pages: list[dict], model: str = ""
) -> list[dict] | None:
    """Generate hierarchical structure when no TOC is found."""
    groups = group_pages_for_llm(pages)
    all_entries: list[dict] = []

    for i, group_text in enumerate(groups):
        if i == 0:
            prompt = GENERATE_STRUCTURE_PROMPT.format(text=group_text)
        else:
            prev_json = json.dumps(all_entries[-10:])  # last 10 for context
            prompt = CONTINUE_STRUCTURE_PROMPT.format(
                previous=prev_json, text=group_text
            )

        result, _ = bedrock_converse_with_stop(prompt, model=model)
        parsed = extract_json(result)
        if isinstance(parsed, list):
            all_entries.extend(parsed)
        print(f"[PageIndex] Structure group {i + 1}/{len(groups)}: "
              f"{len(parsed or [])} entries")

    return all_entries if all_entries else None


# ---------------------------------------------------------------------------
# TOC without page numbers — locate sections in document body
# ---------------------------------------------------------------------------
LOCATE_SECTION_PROMPT = """You are given a partial document with <physical_index_X> page markers and a list of sections.
Check if each section title starts in this part of the document.

Sections to find:
{sections_json}

Document text:
{text}

Return JSON array:
[{{"structure": "...", "title": "...", "start": "yes" or "no", "physical_index": <physical_index_X or null>}}, ...]"""


def locate_sections_in_body(
    toc_entries: list[dict], pages: list[dict], model: str = ""
) -> list[dict]:
    """For TOC without page numbers: locate where sections start in the body."""
    groups = group_pages_for_llm(pages)

    for group_text in groups:
        # Only process entries that don't have a physical_index yet
        unlocated = [e for e in toc_entries if e.get("physical_index") is None]
        if not unlocated:
            break

        sections_json = json.dumps([
            {"structure": e["structure"], "title": e["title"]}
            for e in unlocated[:20]  # batch limit
        ])
        prompt = LOCATE_SECTION_PROMPT.format(
            sections_json=sections_json, text=group_text
        )
        result = extract_json(bedrock_converse(prompt, model=model))
        if not isinstance(result, list):
            continue

        # Update entries with found indices
        found_map = {
            r["structure"]: r.get("physical_index")
            for r in result
            if str(r.get("start", "")).lower() == "yes" and r.get("physical_index")
        }
        for entry in toc_entries:
            if entry["structure"] in found_map and entry.get("physical_index") is None:
                entry["physical_index"] = found_map[entry["structure"]]

    return toc_entries


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
VERIFY_PROMPT = """Check if the given section appears or starts in the given page text.
Do fuzzy matching, ignore space inconsistency, case differences, minor formatting changes.

Section title: {title}
Page text:
{page_text}

Return JSON: {{"thinking": "<your reasoning>", "answer": "yes" or "no"}}"""


def verify_structure(
    entries: list[dict], pages: list[dict], model: str = "", sample_size: int = 15
) -> float:
    """Verify section→page mappings by sampling. Returns accuracy 0.0-1.0."""
    verifiable = [e for e in entries if e.get("physical_index") is not None]
    if not verifiable:
        return 0.0

    # Sample entries
    import random
    sample = random.sample(verifiable, min(sample_size, len(verifiable)))

    # Build verification prompts
    prompts = []
    for entry in sample:
        phys = int(entry["physical_index"])
        if 1 <= phys <= len(pages):
            page_text = pages[phys - 1]["text"][:2000]
            prompts.append(VERIFY_PROMPT.format(
                title=entry["title"], page_text=page_text
            ))
        else:
            prompts.append(None)

    # Run concurrent verification
    valid_prompts = [p for p in prompts if p is not None]
    if not valid_prompts:
        return 0.0

    results = bedrock_converse_threaded(valid_prompts, model=model)
    correct = 0
    for resp in results:
        parsed = extract_json(resp)
        if parsed and str(parsed.get("answer", "")).lower() == "yes":
            correct += 1

    accuracy = correct / len(valid_prompts)
    print(f"[PageIndex] Verification: {correct}/{len(valid_prompts)} "
          f"= {accuracy:.0%}")
    return accuracy


# ---------------------------------------------------------------------------
# List → Tree conversion
# ---------------------------------------------------------------------------
def list_to_tree(entries: list[dict], total_pages: int) -> list[dict]:
    """Convert flat structure list to nested tree with start/end indices.

    Input:  [{"structure": "1", "title": "...", "physical_index": 5}, ...]
    Output: [{"title": "...", "start_index": 5, "end_index": 12, "nodes": [...]}, ...]
    """
    if not entries:
        return []

    # Sort by physical_index, then structure
    valid = [e for e in entries if e.get("physical_index") is not None]
    valid.sort(key=lambda e: (int(e["physical_index"]), e.get("structure", "")))

    # Build tree using structure hierarchy
    root_nodes: list[dict] = []
    node_stack: list[tuple[str, dict]] = []  # (structure_prefix, node)

    for entry in valid:
        struct = entry.get("structure", "")
        node = {
            "title": entry.get("title", "Untitled"),
            "start_index": int(entry["physical_index"]),
            "end_index": total_pages,  # will be refined
            "nodes": [],
        }

        # Find parent by matching structure prefix
        depth = struct.count(".") if struct else 0
        while node_stack and _depth(node_stack[-1][0]) >= depth:
            node_stack.pop()

        if node_stack:
            parent = node_stack[-1][1]
            parent["nodes"].append(node)
        else:
            root_nodes.append(node)

        node_stack.append((struct, node))

    # Calculate end_index for each node based on next sibling's start
    _calculate_end_indices(root_nodes, total_pages)

    return root_nodes


def _depth(structure: str) -> int:
    """Get depth from structure string (e.g., '1.2.3' → 2)."""
    return structure.count(".") if structure else 0


def _calculate_end_indices(nodes: list[dict], parent_end: int) -> None:
    """Recursively set end_index based on sibling start_index."""
    for i, node in enumerate(nodes):
        if i + 1 < len(nodes):
            node["end_index"] = nodes[i + 1]["start_index"] - 1
        else:
            node["end_index"] = parent_end

        # Ensure end >= start
        if node["end_index"] < node["start_index"]:
            node["end_index"] = node["start_index"]

        if node["nodes"]:
            _calculate_end_indices(node["nodes"], node["end_index"])


# ---------------------------------------------------------------------------
# Node IDs (depth-first sequential)
# ---------------------------------------------------------------------------
def assign_node_ids(nodes: list[dict], counter: list[int] | None = None) -> None:
    """Assign zero-padded node IDs via depth-first traversal."""
    if counter is None:
        counter = [0]
    for node in nodes:
        node["node_id"] = f"{counter[0]:04d}"
        counter[0] += 1
        if node.get("nodes"):
            assign_node_ids(node["nodes"], counter)


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------
SUMMARY_PROMPT = """You are given a part of a document. Generate a concise description (1-3 sentences)
of what main points are covered in this section.

Section title: {title}
Pages {start}-{end}

Partial document text:
{text}

Directly return the description. No JSON wrapper needed."""

DOC_DESCRIPTION_PROMPT = """Generate a single-sentence description for this document that distinguishes it
from other documents. Be specific about parties, dates, and document type.

Document structure:
{structure}

Directly return the one-sentence description."""


def generate_summaries(
    nodes: list[dict], pages: list[dict], model: str = ""
) -> None:
    """Generate summaries for all leaf and branch nodes concurrently."""
    flat = _flatten_nodes(nodes)
    prompts = []
    node_refs = []

    for node in flat:
        start = node["start_index"]
        end = min(node["end_index"], len(pages))
        text_parts = []
        for p in pages[start - 1 : end]:
            text_parts.append(p["text"][:1500])
        text = "\n---\n".join(text_parts)
        # Truncate to avoid huge prompts
        text = text[:8000]

        prompts.append(SUMMARY_PROMPT.format(
            title=node.get("title", ""), start=start, end=end, text=text
        ))
        node_refs.append(node)

    if not prompts:
        return

    print(f"[PageIndex] Generating {len(prompts)} summaries...")
    results = bedrock_converse_threaded(prompts, model=model)
    for node, summary in zip(node_refs, results):
        if summary and summary != "Error":
            node["summary"] = summary


def generate_doc_description(
    nodes: list[dict], model: str = ""
) -> str:
    """Generate a one-sentence document description."""
    # Build compact structure representation
    structure_lines = []
    for node in _flatten_nodes(nodes)[:20]:  # limit context
        indent = "  " * (len(node.get("node_id", "")) // 2)
        structure_lines.append(
            f"{indent}{node.get('title', '')} (pp. {node['start_index']}-{node['end_index']})"
        )
    structure = "\n".join(structure_lines)

    prompt = DOC_DESCRIPTION_PROMPT.format(structure=structure)
    return bedrock_converse(prompt, model=model)


def _flatten_nodes(nodes: list[dict]) -> list[dict]:
    """Flatten tree to list (depth-first)."""
    flat = []
    for node in nodes:
        flat.append(node)
        if node.get("nodes"):
            flat.extend(_flatten_nodes(node["nodes"]))
    return flat


# ---------------------------------------------------------------------------
# Recursive subdivision of large nodes
# ---------------------------------------------------------------------------
def subdivide_large_nodes(
    nodes: list[dict],
    pages: list[dict],
    max_pages: int = DEFAULT_MAX_PAGES_PER_NODE,
    max_tokens: int = DEFAULT_MAX_TOKENS_PER_NODE,
    model: str = "",
) -> None:
    """Recursively split nodes that exceed page/token thresholds."""
    for node in nodes:
        if node.get("nodes"):
            subdivide_large_nodes(
                node["nodes"], pages, max_pages, max_tokens, model
            )

        node_pages = node["end_index"] - node["start_index"] + 1
        node_tokens = sum(
            pages[i]["tokens"]
            for i in range(node["start_index"] - 1, min(node["end_index"], len(pages)))
        )

        if (node_pages > max_pages or node_tokens > max_tokens) and not node.get("nodes"):
            print(f"[PageIndex] Subdividing '{node.get('title', '')}' "
                  f"({node_pages} pages, {node_tokens} tokens)")
            sub_pages = pages[node["start_index"] - 1 : node["end_index"]]
            sub_entries = generate_structure_no_toc(sub_pages, model=model)
            if sub_entries:
                # Adjust physical indices to global page numbers
                offset = node["start_index"] - 1
                for entry in sub_entries:
                    if entry.get("physical_index") is not None:
                        entry["physical_index"] = int(entry["physical_index"]) + offset
                sub_tree = list_to_tree(sub_entries, node["end_index"])
                if sub_tree:
                    node["nodes"] = sub_tree


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def build_tree(
    pdf_bytes: bytes,
    doc_name: str = "document.pdf",
    model: str = "",
    toc_check_page_num: int = DEFAULT_TOC_CHECK_PAGES,
    max_page_num_each_node: int = DEFAULT_MAX_PAGES_PER_NODE,
    max_token_num_each_node: int = DEFAULT_MAX_TOKENS_PER_NODE,
    generate_summaries_flag: bool = True,
    generate_description_flag: bool = True,
) -> dict[str, Any]:
    """Build a PageIndex tree from PDF bytes.

    Returns the tree JSON structure ready for DynamoDB storage.
    """
    start_time = time.time()
    print(f"[PageIndex] Building tree for {doc_name}")

    # Step 1: Extract text from all pages
    pages = extract_page_texts(pdf_bytes)
    total_pages = len(pages)
    print(f"[PageIndex] Extracted text from {total_pages} pages")

    if total_pages == 0:
        return _empty_tree(doc_name, model, start_time)

    # Step 2: Detect TOC
    toc_pages = find_toc_pages(pages, max_check=toc_check_page_num, model=model)

    # Step 3: Route to appropriate processing mode
    entries = None
    if toc_pages:
        toc_content = extract_toc_content(pages, toc_pages, model=model)
        has_page_nums = detect_toc_has_page_numbers(toc_content, model=model)

        if has_page_nums:
            # Mode A: TOC with page numbers
            print("[PageIndex] Mode A: TOC with page numbers")
            entries = transform_toc_to_json(toc_content, model=model)
            if entries:
                offset = calculate_page_offset(entries, pages, model=model)
                entries = apply_page_offset(entries, offset)
        else:
            # Mode B: TOC without page numbers
            print("[PageIndex] Mode B: TOC without page numbers")
            entries = transform_toc_to_json(toc_content, model=model)
            if entries:
                entries = locate_sections_in_body(entries, pages, model=model)
    else:
        # Mode C: No TOC — generate structure from scratch
        print("[PageIndex] Mode C: No TOC detected, generating structure")
        entries = generate_structure_no_toc(pages, model=model)

    if not entries:
        print("[PageIndex] WARNING: No structure generated, creating single-node tree")
        entries = [{"structure": "1", "title": doc_name, "physical_index": 1}]

    # Step 4: Verify
    accuracy = verify_structure(entries, pages, model=model)
    if accuracy < 0.6 and toc_pages:
        # Fallback to Mode C if TOC-based approach has low accuracy
        print(f"[PageIndex] Low accuracy ({accuracy:.0%}), falling back to Mode C")
        entries = generate_structure_no_toc(pages, model=model)
        if entries:
            accuracy = verify_structure(entries, pages, model=model)

    # Step 5: Build tree
    tree_nodes = list_to_tree(entries or [], total_pages)

    # Step 6: Subdivide large nodes
    subdivide_large_nodes(
        tree_nodes, pages,
        max_pages=max_page_num_each_node,
        max_tokens=max_token_num_each_node,
        model=model,
    )

    # Step 7: Assign node IDs
    assign_node_ids(tree_nodes)

    # Step 8: Generate summaries (concurrent)
    if generate_summaries_flag and tree_nodes:
        generate_summaries(tree_nodes, pages, model=model)

    # Step 9: Generate document description
    doc_description = ""
    if generate_description_flag and tree_nodes:
        doc_description = generate_doc_description(tree_nodes, model=model)

    elapsed = time.time() - start_time
    print(f"[PageIndex] Tree built in {elapsed:.1f}s: "
          f"{len(_flatten_nodes(tree_nodes))} nodes, {total_pages} pages")

    return {
        "doc_name": doc_name,
        "doc_description": doc_description,
        "structure": tree_nodes,
        "total_pages": total_pages,
        "model": model or "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "build_duration_seconds": round(elapsed, 1),
        "verification_accuracy": round(accuracy, 2),
    }


def _empty_tree(doc_name: str, model: str, start_time: float) -> dict:
    """Return an empty tree for documents with no extractable text."""
    return {
        "doc_name": doc_name,
        "doc_description": "Document contains no extractable text",
        "structure": [],
        "total_pages": 0,
        "model": model or "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "build_duration_seconds": round(time.time() - start_time, 1),
        "verification_accuracy": 0.0,
    }
