# Acknowledgments & Third-Party Credits

| Project | License | Usage in This Project |
|---------|---------|----------------------|
| [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) | MIT | Core tree-building algorithm (`lambda/pageindex/tree_builder.py`). Adapted for AWS Bedrock, async processing, on-demand summaries, and tree-assisted extraction. |
| [GAIK](https://github.com/Sankgreall/GAIK) | MIT | Inspired the double-pass text extraction approach in `lambda/router/handler.py` (PyPDF + PyMuPDF fallback for robust PDF parsing). |
| [PyPDF](https://github.com/py-pdf/pypdf) | BSD-3 | Primary PDF text extraction across Router, PageIndex, and API Lambdas. |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | AGPL-3.0 | Fallback PDF extraction for custom fonts and scanned documents. |
| [react-pdf](https://github.com/wojtekmaj/react-pdf) | MIT | In-browser PDF rendering for the document viewer. |
