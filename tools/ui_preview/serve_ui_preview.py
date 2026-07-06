#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from render_ui_preview import DEFAULT_DATA, OUT, check_layout, load_data, render_pages


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def build_gallery_html(paths: Iterable[Path], host: str, port: int) -> str:
    page_paths = list(paths)
    warnings = check_layout(page_paths)
    phone_host = local_ip() if host in {"0.0.0.0", "::"} else host
    cards = "\n".join(
        f"""
        <figure class="page">
          <img src="{html.escape(path.name)}" alt="{html.escape(path.name)}" width="400" height="300">
          <figcaption>{html.escape(path.name)}</figcaption>
        </figure>
        """
        for path in page_paths
    )
    warning_html = ""
    if warnings:
        warning_html = "<section class=\"warnings\"><h2>Layout warnings</h2><ul>" + "".join(
            f"<li>{html.escape(item)}</li>" for item in warnings
        ) + "</ul></section>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="8">
  <title>GoTim Ink UI Preview</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #171717;
      --paper: #f7f7f2;
      --line: #d8d8ce;
      --panel: #ffffff;
      --accent: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      padding: 20px clamp(16px, 4vw, 40px) 14px;
      border-bottom: 1px solid var(--line);
      background: #fff;
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(22px, 4vw, 34px);
      line-height: 1.05;
      letter-spacing: 0;
    }}
    .meta {{
      margin-top: 6px;
      font-size: 13px;
      color: #555;
    }}
    .url {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
      color: var(--accent);
      white-space: nowrap;
    }}
    main {{
      padding: 18px clamp(12px, 3vw, 32px) 36px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      align-items: start;
    }}
    .page {{
      margin: 0;
      padding: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 0 rgba(0,0,0,.04);
    }}
    .page img {{
      display: block;
      width: 100%;
      max-width: 400px;
      height: auto;
      image-rendering: pixelated;
      border: 1px solid #111;
      margin: 0 auto;
      background: white;
    }}
    figcaption {{
      padding-top: 8px;
      font-size: 12px;
      color: #555;
      text-align: center;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .warnings {{
      margin-bottom: 16px;
      padding: 12px 14px;
      border: 1px solid #111;
      background: #fff;
    }}
    .warnings h2 {{
      margin: 0 0 8px;
      font-size: 16px;
    }}
    .warnings ul {{
      margin: 0;
      padding-left: 18px;
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>GoTim Ink UI Preview</h1>
      <div class="meta">400 x 300 monochrome e-paper preview, auto refresh every 8s</div>
    </div>
    <div class="url">手机访问: http://{html.escape(phone_host)}:{port}/</div>
  </header>
  <main>
    {warning_html}
    <section class="grid">
      {cards}
    </section>
  </main>
</body>
</html>
"""


def write_index(paths: list[Path], out: Path, host: str, port: int) -> None:
    (out / "index.html").write_text(build_gallery_html(paths, host, port), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve GoTim e-paper UI previews for desktop and phone browsers.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()

    data = load_data(args.data)
    paths = render_pages(data, args.out)
    write_index(paths, args.out, args.host, args.port)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *handler_args, **handler_kwargs):
            super().__init__(*handler_args, directory=str(args.out), **handler_kwargs)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Preview: http://127.0.0.1:{args.port}/")
    print(f"Phone:   http://{local_ip()}:{args.port}/")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
