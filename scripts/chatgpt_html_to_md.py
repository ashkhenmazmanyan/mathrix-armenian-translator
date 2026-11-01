"""Convert a saved ChatGPT conversation page (Ctrl+S) to Markdown.

ChatGPT only keeps part of a long conversation in the page (older messages are loaded
while scrolling), so the result may be incomplete; the script reports what it found.

Usage: python scripts/chatgpt_html_to_md.py SAVED_PAGE.html OUTPUT.md "Title"
"""
import re
import sys

from bs4 import BeautifulSoup
from markdownify import markdownify

src, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
soup = BeautifulSoup(open(src, encoding="utf-8", errors="replace").read(), "html.parser")
for t in soup(["script", "style", "svg", "noscript", "button"]):
    t.decompose()
blocks = soup.select("[data-chatgpt-search-message-ids]")
parts = [f"# {title}\n"]
for b in blocks:
    md = markdownify(str(b), heading_style="ATX").strip()
    if md.startswith("ChatGPT said:"):
        md = re.sub(r"^ChatGPT said:\s*(ChatGPT\s*)?", "", md)
        parts.append("\n## ChatGPT\n\n" + md + "\n")
    else:
        md = re.sub(r"^You said:\s*", "", md)
        parts.append("\n---\n\n## You\n\n" + md + "\n")
open(out, "w", encoding="utf-8").write(re.sub(r"\n{3,}", "\n\n", "\n".join(parts)))
print(f"{len(blocks)} messages -> {out}")
