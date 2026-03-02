#!/usr/bin/env python3
"""
Generate Step Functions state machine diagram from the live AWS definition.

Fetches the current state machine definition and renders it as a clean
flow diagram using graphviz.

Output: docs/stepfunctions_graph.png
"""

import json
import subprocess
import sys

import boto3


def get_state_machine_definition():
    """Fetch the current state machine definition from AWS."""
    client = boto3.client("stepfunctions", region_name="us-west-2")
    resp = client.describe_state_machine(
        stateMachineArn="arn:aws:states:us-west-2:211125568838:stateMachine:financial-doc-processor"
    )
    return json.loads(resp["definition"])


# Color palette
COLORS = {
    "task": "#f97316",       # Orange - Lambda tasks
    "choice": "#8b5cf6",     # Purple - Choice states
    "parallel": "#3b82f6",   # Blue - Parallel states
    "map": "#06b6d4",        # Cyan - Map state
    "succeed": "#22c55e",    # Green - Success
    "fail": "#ef4444",       # Red - Fail
    "pass": "#64748b",       # Gray - Pass
    "edge": "#475569",       # Slate - edges
    "default_edge": "#94a3b8",  # Light slate - default transitions
}

# Human-readable labels for states
LABELS = {
    "ClassifyDocument": "1. Classify\nDocument\n(Router Lambda)",
    "ProcessingModeChoice": "Processing\nMode?",
    "PageIndexRouteChoice": "Has\nSections?",
    "ExtractionRouteChoice": "Extraction\nPlan?",
    "BuildPageIndexAsync": "2a. Build PageIndex\n(Async, Fire & Forget)",
    "BuildPageIndexSync": "2b. Build PageIndex\n(Sync, Understand-Only)",
    "IndexingComplete": "Indexing\nComplete",
    "LegacyDocumentTypeChoice": "Document\nType?",
    "MapExtraction": "3. Map Extraction\n(Plugin Sections)",
    "ParallelMortgageExtraction": "3. Parallel Extraction\n(Mortgage)",
    "ParallelCreditAgreementExtraction": "3. Parallel Extraction\n(Credit Agreement)",
    "ParallelLoanAgreementExtraction": "3. Parallel Extraction\n(Loan Agreement)",
    "NormalizeData": "4. Normalize\nData\n(Haiku 4.5)",
    "HandleError": "Handle\nError",
    "ProcessingFailed": "Processing\nFailed",
    "ProcessingComplete": "Processing\nComplete",
}


def state_shape(state_type):
    """Return graphviz shape and color for a state type."""
    t = state_type.lower()
    if t == "task":
        return "box", COLORS["task"], "white"
    elif t == "choice":
        return "diamond", COLORS["choice"], "white"
    elif t == "parallel":
        return "box", COLORS["parallel"], "white"
    elif t == "map":
        return "box", COLORS["map"], "white"
    elif t == "succeed":
        return "ellipse", COLORS["succeed"], "white"
    elif t == "fail":
        return "ellipse", COLORS["fail"], "white"
    elif t == "pass":
        return "box", COLORS["pass"], "white"
    else:
        return "box", "#94a3b8", "black"


def build_dot(definition):
    """Build a graphviz DOT string from the state machine definition."""
    lines = [
        'digraph StepFunctions {',
        '  bgcolor="#f8fafc";',
        '  fontname="Arial Bold";',
        '  fontsize=20;',
        '  label="Financial Doc Processor — Step Functions State Machine";',
        '  labelloc=t;',
        '  fontcolor="#1e293b";',
        '  rankdir=TB;',
        '  nodesep=0.6;',
        '  ranksep=0.8;',
        '  dpi=150;',
        '  node [fontname="Arial" fontsize=10 style=filled penwidth=2];',
        '  edge [fontname="Arial" fontsize=8 color="#475569"];',
        '',
        '  Start [shape=circle fillcolor="#22c55e" fontcolor=white label="Start" width=0.5];',
    ]

    states = definition.get("States", {})
    start_at = definition.get("StartAt", "")

    # Add nodes
    for name, state in states.items():
        stype = state.get("Type", "Task")
        shape, color, fontcolor = state_shape(stype)
        label = LABELS.get(name, name.replace("_", "\\n"))
        lines.append(
            f'  "{name}" [shape={shape} fillcolor="{color}" '
            f'fontcolor="{fontcolor}" label="{label}" pencolor="{color}"];'
        )

    lines.append("")

    # Start edge
    lines.append(f'  Start -> "{start_at}" [penwidth=2 color="#22c55e"];')

    # Add edges
    for name, state in states.items():
        stype = state.get("Type", "Task")

        if stype == "Choice":
            choices = state.get("Choices", [])
            default = state.get("Default")
            for i, choice in enumerate(choices):
                target = choice.get("Next", "")
                # Build edge label from condition
                var = choice.get("Variable", "")
                edge_label = ""
                if "StringEquals" in choice:
                    edge_label = f'{choice["StringEquals"]}'
                elif "BooleanEquals" in choice:
                    edge_label = f'{"Yes" if choice["BooleanEquals"] else "No"}'
                elif "And" in choice:
                    edge_label = "Has plan"

                lines.append(
                    f'  "{name}" -> "{target}" '
                    f'[label=" {edge_label}" color="{COLORS["choice"]}" '
                    f'fontcolor="{COLORS["choice"]}"];'
                )
            if default:
                lines.append(
                    f'  "{name}" -> "{default}" '
                    f'[label=" default" style=dashed color="{COLORS["default_edge"]}" '
                    f'fontcolor="{COLORS["default_edge"]}"];'
                )

        elif stype in ("Task", "Pass"):
            nxt = state.get("Next")
            if nxt:
                lines.append(f'  "{name}" -> "{nxt}" [penwidth=1.5];')
            catch = state.get("Catch", [])
            for c in catch:
                target = c.get("Next", "")
                lines.append(
                    f'  "{name}" -> "{target}" '
                    f'[style=dashed color="{COLORS["fail"]}" label=" error"];'
                )

        elif stype in ("Parallel", "Map"):
            nxt = state.get("Next")
            if nxt:
                lines.append(f'  "{name}" -> "{nxt}" [penwidth=1.5];')
            catch = state.get("Catch", [])
            for c in catch:
                target = c.get("Next", "")
                lines.append(
                    f'  "{name}" -> "{target}" '
                    f'[style=dashed color="{COLORS["fail"]}" label=" error"];'
                )

        elif stype == "Succeed":
            pass  # Terminal
        elif stype == "Fail":
            pass  # Terminal

    lines.append("}")
    return "\n".join(lines)


def main():
    print("Fetching state machine definition from AWS...")
    definition = get_state_machine_definition()
    print(f"Found {len(definition.get('States', {}))} states")

    dot_content = build_dot(definition)

    # Write DOT file for debugging
    dot_path = "docs/stepfunctions_graph.dot"
    with open(dot_path, "w") as f:
        f.write(dot_content)

    # Render PNG
    png_path = "docs/stepfunctions_graph.png"
    result = subprocess.run(
        ["dot", "-Tpng", "-o", png_path, dot_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: graphviz failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Step Functions diagram saved to {png_path}")


if __name__ == "__main__":
    main()
