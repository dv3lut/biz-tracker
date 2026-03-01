"""Simple CLI helper to extract text from PDF files using pdfminer.six."""

from __future__ import annotations

import sys
from pathlib import Path

from pdfminer.high_level import extract_text


def main() -> None:
	if len(sys.argv) < 2:
		print("Usage: extract_pdf_text.py <pdf_path>", file=sys.stderr)
		sys.exit(1)

	path = Path(sys.argv[1]).expanduser().resolve()
	if not path.is_file():
		print(f"File not found: {path}", file=sys.stderr)
		sys.exit(1)

	text = extract_text(str(path))
	print(text)


if __name__ == "__main__":
	main()
