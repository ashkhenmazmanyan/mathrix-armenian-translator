"""Convert a saved Claude conversation page (Ctrl+S, "Webpage, Complete") to Markdown.

Copy-paste of very long chats silently loses messages, so the chat transcripts in
chats/ were produced from the saved share page with this script. Message text is kept
unedited; only page chrome (buttons, menus, screen-reader labels) is removed.

Usage: python scripts/claude_html_to_md.py SAVED_PAGE.html OUTPUT.md "Title"
"""
import re
import sys

from bs4 import BeautifulSoup
from markdownify import markdownify

src, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
soup = BeautifulSoup(open(src, encoding="utf-8", errors="replace").read(), "html.parser")
for t in soup(["script", "style", "svg", "noscript"]):
    t.decompose()
# Tool-use summaries ("Ran 2 commands, read files ...") are buttons; keep their text.
for pill in soup.select('[data-testid="tool-status-pill"]'):
    label = pill.get_text(" ", strip=True)
    marker = soup.new_tag("p")
    marker.string = f"[{label}]" if label else ""
    marker["data-tool"] = "1"
    pill.replace_with(marker)
for t in soup("button"):
    t.decompose()
for t in soup.select(".sr-only"):                       # "You said:", "Claude responded:"
    t.decompose()
for sel in ["user-message-actions", "message-actions", "failed-send-status-region"]:
    for t in soup.select(f'[data-testid="{sel}"]'):
        t.decompose()

rows = soup.select_one('[data-testid="transcript-list"]').find_all(recursive=False)
parts, n_user, n_claude = [f"# {title}\n"], 0, 0
for row in rows:
    files = [f.get_text(" ", strip=True) for f in row.select('[data-testid="file-thumbnail"]')]
    user = row.select_one('[data-testid="user-message"]')
    if user:
        n_user += 1
        parts.append("\n---\n\n## You\n")
        if files:
            parts.append("*Attached: " + "; ".join(files) + "*\n")
        parts.append(markdownify(str(user), heading_style="ATX").strip() + "\n")
        continue
    if row.select_one('[data-testid="assistant-message"]'):
        tools = [t.get_text(strip=True) for t in row.select("[data-tool]") if t.get_text(strip=True)]
        body = row.select(".font-claude-response")
        if not body and not tools:
            continue
        n_claude += 1
        parts.append("\n## Claude\n")
        for t in tools:
            parts.append(f"*{t}*\n")
        for b in body:
            parts.append(markdownify(str(b), heading_style="ATX").strip() + "\n")

text = "\n".join(parts)
text = re.sub(r"\n{3,}", "\n\n", text)
open(out, "w", encoding="utf-8").write(text)
print(f"{n_user} user messages, {n_claude} Claude replies -> {out}")
