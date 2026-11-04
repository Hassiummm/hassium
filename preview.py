#!/usr/bin/env python3
"""
Local preview server for the Jekyll site.

The deployed site is built by Jekyll on GitHub Pages.  This script provides a
zero-dependency local preview: it serves the static files directly and renders
the small Liquid-driven parts (latest entries, category lists and reading-group
pages) from the same `_notes`, `_reading_notes` and `_reading_groups` folders.

Usage:
    python3 preview.py [port]

Then open http://127.0.0.1:8000/ (or the port you chose).  Edits are read on
every request, so refreshing the browser is enough.
"""

from __future__ import annotations

import html
import re
import sys
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
FRONT_MATTER_END = re.compile(r"^---\s*$")
MARKER_RE = re.compile(
    r"<!-- preview:([a-z0-9-]+) -->.*?<!-- /preview:\1 -->", re.DOTALL
)
ASSIGN_LINE_RE = re.compile(r"^\s*\{%\s*assign\b")
ITEM_RE = re.compile(r"^/math/reading-group/([^/]+)/(?:index\.html)?$")


def split_front_matter(text):
    """Return (front_matter_dict, body) for a Jekyll markdown/html document."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end = None
    for index in range(1, len(lines)):
        if FRONT_MATTER_END.match(lines[index].strip()):
            end = index
            break
    if end is None:
        return {}, text

    fields = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"').strip("'")
        fields[key.strip()] = value

    return fields, "\n".join(lines[end + 1 :])


def load_collection(folder_name):
    folder = ROOT / folder_name
    if not folder.is_dir():
        return []

    documents = []
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith("."):
            continue
        fields, body = split_front_matter(path.read_text(encoding="utf-8"))
        if not fields.get("title"):
            continue
        fields["slug"] = path.stem
        fields["body"] = body.strip()
        documents.append(fields)

    documents.sort(key=lambda doc: doc.get("date", ""))
    return documents


def format_date(value):
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%b %Y")
    except ValueError:
        return value


def latest_entry(document, href, meta):
    if not document:
        return ""
    return f"""
                <a class="entry-row" href="{html.escape(href)}">
                    <span class="entry-title">{html.escape(document["title"])}</span>
                    <span class="entry-meta">{html.escape(meta)}</span>
                </a>
"""


def notes_list(documents):
    rows = []
    for document in reversed(documents):
        rows.append(
            f"""
            <div class="entry-row entry-row--static">
                <span class="entry-title">{html.escape(document["title"])}</span>
                <span class="entry-meta">No. {html.escape(document.get("number", ""))}</span>
            </div>"""
        )
    return "\n".join(rows)


def reading_notes_list(documents):
    rows = []
    for document in reversed(documents):
        rows.append(
            f"""
            <div class="entry-row entry-row--static">
                <span class="entry-title">{html.escape(document["title"])}</span>
                <span class="entry-meta">{html.escape(format_date(document.get("date", "")))}</span>
            </div>"""
        )
    return "\n".join(rows)


def reading_groups_list(documents):
    rows = []
    for document in reversed(documents):
        rows.append(
            f"""
            <a class="entry-row" href="{html.escape(document["slug"])}/">
                <span class="entry-title">{html.escape(document["title"])}</span>
                <span class="entry-meta">{html.escape(document.get("term", ""))}</span>
            </a>"""
        )
    return "\n".join(rows)


def render_marked_page(relative_path, snippets):
    """Read an HTML page with Jekyll markup and substitute preview markers."""
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    text = split_front_matter(text)[1]
    text = "\n".join(
        line for line in text.splitlines() if not ASSIGN_LINE_RE.match(line)
    )

    def replace(match):
        name = match.group(1)
        if name not in snippets:
            raise RuntimeError(f"preview marker has no data: {name}")
        return snippets[name]

    text = MARKER_RE.sub(replace, text)
    if "{%" in text or "{{" in text:
        raise RuntimeError(
            f"{relative_path} contains Liquid that preview.py does not understand"
        )
    return text


def render_inline_markup(text):
    """Render the small subset of Markdown used by the reading-group pages.

    Emphasis is applied only to text outside HTML tags and math delimiters, so
    ``$C^\\ast$`` and other formulas are left for MathJax.
    """
    parts = re.split(
        r"(<[^>]+>|\$\$.*?\$\$|\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\])",
        text,
        flags=re.DOTALL,
    )
    for index, part in enumerate(parts):
        if not part or part.startswith(("<", "$", r"\(", r"\[")):
            continue
        part = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", part, flags=re.DOTALL)
        part = re.sub(
            r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
            r"<em>\1</em>",
            part,
            flags=re.DOTALL,
        )
        parts[index] = part
    return "".join(parts)


def render_group_page(document):
    layout = (ROOT / "_layouts" / "reading-group.html").read_text(encoding="utf-8")
    title = html.escape(document["title"])
    layout = layout.replace("{{ page.title | escape }}", title)
    layout = layout.replace("{{ page.title }}", title)
    content = render_inline_markup(document["body"])
    return layout.replace("{{ content }}", content)


def collection_snapshot():
    notes = load_collection("_notes")
    reading_notes = load_collection("_reading_notes")
    reading_groups = load_collection("_reading_groups")
    return notes, reading_notes, reading_groups


def render_path(path):
    notes, reading_notes, reading_groups = collection_snapshot()

    math_snippets = {
        "latest-reading-notes": latest_entry(
            reading_notes[-1] if reading_notes else None,
            "reading-notes/",
            format_date(reading_notes[-1].get("date", "")) if reading_notes else "",
        ),
        "latest-notes": latest_entry(
            notes[-1] if notes else None,
            "notes/",
            "No. " + notes[-1].get("number", "") if notes else "",
        ),
        "latest-reading-group": latest_entry(
            reading_groups[-1] if reading_groups else None,
            "reading-group/" + reading_groups[-1]["slug"] + "/" if reading_groups else "",
            reading_groups[-1].get("term", "") if reading_groups else "",
        ),
    }

    if path in ("/math/", "/math/index.html"):
        return render_marked_page("math/index.html", math_snippets)

    if path in ("/math/notes/", "/math/notes/index.html"):
        return render_marked_page(
            "math/notes/index.html", {"notes-list": notes_list(notes)}
        )

    if path in ("/math/reading-notes/", "/math/reading-notes/index.html"):
        return render_marked_page(
            "math/reading-notes/index.html",
            {"reading-notes-list": reading_notes_list(reading_notes)},
        )

    if path in ("/math/reading-group/", "/math/reading-group/index.html"):
        return render_marked_page(
            "math/reading-group/index.html",
            {"reading-groups-list": reading_groups_list(reading_groups)},
        )

    match = ITEM_RE.match(path)
    if match:
        slug = match.group(1)
        for document in reading_groups:
            if document["slug"] == slug:
                return render_group_page(document)

    return None


class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        try:
            rendered = render_path(path)
        except Exception as error:  # Show the error instead of an opaque 500
            message = f"preview.py error:\n\n{error}\n".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)
            return

        if rendered is None:
            return super().do_GET()

        data = rendered.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    server = ThreadingHTTPServer(("127.0.0.1", port), PreviewHandler)
    print(f"Previewing at http://127.0.0.1:{port}/")
    print("Edit files and refresh the browser. Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
