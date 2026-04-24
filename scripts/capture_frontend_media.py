#!/usr/bin/env python3
"""
Capture PNGs and a time-scrubber GIF of the fire risk app (headless Chromium).

Prerequisites: `pip install -r requirements.txt` and `python -m playwright install chromium`
"""
from __future__ import annotations

import argparse
import contextlib
import http.server
import os
import socket
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@contextlib.contextmanager
def http_server_127(root: Path, port: int) -> Iterator[int]:
    """Serve ``root`` at http://127.0.0.1:<port>. If port is 0, pick a free port."""
    bind_port = _free_port() if port == 0 else port
    old = os.getcwd()
    old_dir = old
    os.chdir(root)
    try:
        httpd = http.server.HTTPServer(
            ("127.0.0.1", bind_port), http.server.SimpleHTTPRequestHandler
        )
    except OSError as e:  # pragma: no cover
        os.chdir(old_dir)
        raise e

    def run() -> None:
        try:
            httpd.serve_forever()
        except (OSError, SystemExit):  # pragma: no cover
            pass

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.2)
    try:
        yield bind_port
    finally:
        httpd.shutdown()
        t.join(timeout=3)
        os.chdir(old_dir)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Screenshot / GIF the frontend from a local HTTP server."
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "outputs" / "frontend-captures",
        help="Output directory (default: outputs/frontend-captures)",
    )
    ap.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local server port; 0 = pick a free port",
    )
    ap.add_argument(
        "--viewport",
        default="1400x900",
        help="Width x height for the browser (default: 1400x900)",
    )
    ap.add_argument(
        "--gif-frames",
        type=int,
        default=7,
        help="Number of time-scrubber positions for the GIF (default: 7)",
    )
    ap.add_argument(
        "--gif-ms",
        type=int,
        default=750,
        help="Frame duration in ms (default: 750)",
    )
    ap.add_argument(
        "--no-gif",
        action="store_true",
        help="Only write PNG screenshots, skip animated GIF",
    )
    ap.add_argument(
        "--url-path",
        default="frontend/index.html",
        help="Path under repo root to open (default: frontend/index.html)",
    )
    args = ap.parse_args()

    if Image is None or sync_playwright is None:
        print(
            "Install: pip install -r requirements.txt && python -m playwright install chromium",
            file=sys.stderr,
        )
        return 1

    try:
        w, h = map(int, str(args.viewport).lower().split("x"))
    except (ValueError, TypeError) as e:
        ap.error(f"bad --viewport: {e}")

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    with http_server_127(REPO_ROOT, args.port) as port:
        base = f"http://127.0.0.1:{port}/"
        url = base + args.url_path.lstrip("/")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": w, "height": h},
                    device_scale_factor=1,
                )
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=120_000)
                page.wait_for_function(
                    """() => {
                      const t = document.querySelector("#map-status")?.textContent || "";
                      return t.includes("cells with a row") || t.includes("No dates");
                    }""",
                    timeout=120_000,
                )
                time.sleep(1.2)
                p_map = out / "map_overview.png"
                page.screenshot(path=str(p_map), full_page=False)
                # Full page: chart + text below fold
                p_full = out / "app_full.png"
                page.screenshot(path=str(p_full), full_page=True)
                if not args.no_gif:
                    mx = int(
                        page.locator("#date-slider").get_attribute("max") or 0
                    )
                    n = min(max(args.gif_frames, 2), 32)
                    if mx < 1:
                        print(
                            "WARNING: date slider has no range; skip GIF",
                            file=sys.stderr,
                        )
                    else:
                        step_positions = [
                            int(round(i * (mx - 1) / (n - 1))) for i in range(n)
                        ]
                        frame_files: list[Path] = []
                        for i, pos in enumerate(step_positions):
                            page.evaluate(
                                """(v) => {
  const el = document.querySelector("#date-slider");
  if (el) {
    el.value = String(v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }
}""",
                                pos,
                            )
                            time.sleep(0.55)
                            fpath = out / f"gif_frame_{i:02d}.png"
                            page.screenshot(path=str(fpath), full_page=False)
                            frame_files.append(fpath)
                        gifs: list[Image.Image] = []
                        for fp in frame_files:
                            with Image.open(fp) as im:
                                gifs.append(
                                    im.convert("RGB").copy()
                                    if im.mode in ("RGBA", "P")
                                    else im.copy()
                                )
                        for fp in frame_files:
                            fp.unlink(missing_ok=True)
                        if gifs:
                            (out / "map_timelapse.gif").unlink(missing_ok=True)
                            gif_path = out / "map_timelapse.gif"
                            gifs[0].save(
                                gif_path,
                                save_all=True,
                                append_images=gifs[1:],
                                duration=int(args.gif_ms),
                                loop=0,
                            )
            finally:
                browser.close()
    if not (out / "map_overview.png").is_file():
        return 1
    print("Wrote:")
    for name in (
        "map_overview.png",
        "app_full.png",
        "map_timelapse.gif",
    ):
        pth = out / name
        if pth.is_file():
            print(f"  {pth}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
