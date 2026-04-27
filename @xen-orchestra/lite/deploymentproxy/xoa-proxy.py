#!/usr/bin/env python3
"""
xoa-proxy.py — XOA Deploy Proxy for XCP-ng Dom0
════════════════════════════════════════════════════════════════════════════════
Bridges the two hard limitations of XAPI's VM.import:
  1. VM.import only speaks HTTP, not HTTPS
  2. VM.import cannot consume gzip-compressed streams

This proxy:
  • Listens on HTTP at 127.0.0.1:<PORT>
  • Accepts: GET /image.xva?src=<https-url-of-the-xva.gz>
  • Fetches the remote .xva.gz via HTTPS (cert verification on by default;
    pass --no-verify-ssl or set XOA_PROXY_NO_VERIFY_SSL=1 for self-signed certs)
  • Decompresses with gzip on-the-fly (zero buffering of the full file)
  • Streams the raw .xva bytes back over HTTP to XAPI

Deployment:
  cp  xoa-proxy.py          /opt/xensource/www/
  cp  xoa-proxy.service     /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now xoa-proxy

Requirements: Python 3.6+ (stdlib only — no pip installs needed)
════════════════════════════════════════════════════════════════════════════════
"""

import argparse
import gzip
import http.server
import logging
import os
import signal
import ssl
import sys
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

# ── Configuration ──────────────────────────────────────────────────────────────
PORT = 9001          # Avoids clash with Vite dev (3000), XAPI (443/80)
BIND = "127.0.0.1"  # Loopback only — XAPI is on the same host, no external exposure needed
CHUNK_SIZE = 64 * 1024  # 64 KiB — large enough to keep the pipeline fed, small enough to stay lean

# Populated by main() after CLI/env parsing; read by XoaProxyHandler._stream_xva().
SSL_VERIFY: bool = True

logging.basicConfig(
    level=logging.INFO,
    format="[xoa-proxy] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("xoa-proxy")


# ── Request handler ────────────────────────────────────────────────────────────

class XoaProxyHandler(http.server.BaseHTTPRequestHandler):
    """Handles a single GET /image.xva?src=<url> request."""

    server_version = "xoa-proxy/1.0"
    sys_version = ""  # Suppress Python version from the Server response header

    # ── Routing ────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != "/image.xva":
            self._error(404, f"Unknown path '{parsed.path}'. Expected /image.xva")
            return

        params = parse_qs(parsed.query)
        src_list = params.get("src")

        if not src_list:
            self._error(400, "Missing required query parameter: src")
            return

        src_url = src_list[0]

        if not src_url.startswith("https://"):
            self._error(400, f"src must start with https://, got: {src_url[:40]}")
            return

        self._stream_xva(src_url)

    # ── Core pipeline ──────────────────────────────────────────────────────────

    def _stream_xva(self, src_url: str) -> None:
        """
        Fetch src_url (HTTPS .xva.gz), decompress, stream as HTTP to XAPI.

        HTTP/1.0 semantics: no Content-Length (unknown after decompression),
        connection closed when done. libcurl (used internally by VM.import)
        reads until EOF — this is spec-compliant and universally supported.
        """
        log.info("Starting stream  src=%s", src_url)

        # Build the SSL context according to the --no-verify-ssl flag.
        # Verification is ON by default; disable only for self-signed certs.
        if SSL_VERIFY:
            # Uses the host's system CA bundle (/etc/pki/tls/certs/ on XCP-ng).
            ssl_ctx = ssl.create_default_context()
        else:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            log.warning("SSL certificate verification DISABLED — self-signed cert mode")

        req = urllib.request.Request(
            src_url,
            headers={
                "User-Agent": "xoa-lite-proxy/1.0",
                # Tell the upstream not to apply an extra layer of HTTP-level
                # gzip compression on top of the already-.gz file content.
                "Accept-Encoding": "identity",
            },
        )

        try:
            with urllib.request.urlopen(req, context=ssl_ctx) as upstream:
                log.info(
                    "Upstream connected  status=%d content-type=%s",
                    upstream.status,
                    upstream.headers.get("Content-Type", "unknown"),
                )

                # Send response headers before we start reading/decompressing.
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Connection", "close")
                # No Content-Length — we don't know the decompressed size.
                self.end_headers()

                bytes_sent = 0
                with gzip.GzipFile(fileobj=upstream) as gz:
                    while True:
                        chunk = gz.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        bytes_sent += len(chunk)

                log.info("Stream complete  bytes_sent=%d (%.1f MiB)", bytes_sent, bytes_sent / 1024 ** 2)

        except urllib.error.URLError as exc:
            # Headers not sent yet — we can still return a proper HTTP error.
            log.error("Upstream fetch failed: %s", exc)
            self._error(502, f"Failed to fetch upstream image: {exc}")

        except (OSError, EOFError) as exc:
            # gzip decompression failure (OSError covers BadGzipFile on Py < 3.8)
            # Headers likely already sent — log and let connection close abruptly.
            log.error("Decompression error (headers may already be sent): %s", exc)

        except BrokenPipeError:
            # XAPI cancelled the request or the import was aborted from the UI.
            log.warning("Client (XAPI) closed connection before stream completed")

        except Exception as exc:  # noqa: BLE001
            log.exception("Unexpected error during stream: %s", exc)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _error(self, code: int, detail: str) -> None:
        """Send a plain-text HTTP error response."""
        body = (detail + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        log.warning("HTTP %d: %s", code, detail)

    def log_message(self, fmt: str, *args) -> None:  # type: ignore[override]
        """Suppress the default per-request access log line (we log ourselves)."""
        pass


# ── Server bootstrap ───────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="XOA Deploy Proxy — HTTPS+gunzip bridge for XAPI VM.import",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment variables (override defaults, CLI flags take precedence):\n"
            "  XOA_PROXY_NO_VERIFY_SSL=1   Disable SSL certificate verification\n"
            "  XOA_PROXY_PORT=<n>          Listening port (default: 9001)\n"
            "  XOA_PROXY_BIND=<addr>       Bind address  (default: 127.0.0.1)\n"
        ),
    )
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        default=os.environ.get("XOA_PROXY_NO_VERIFY_SSL", "0") not in ("", "0", "false", "no"),
        help=(
            "Disable upstream TLS certificate verification. "
            "Use when the XOA image is hosted behind a self-signed certificate. "
            "Also enabled by setting XOA_PROXY_NO_VERIFY_SSL=1."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("XOA_PROXY_PORT", PORT)),
        metavar="PORT",
        help=f"Port to listen on (default: {PORT}, env: XOA_PROXY_PORT)",
    )
    parser.add_argument(
        "--bind",
        default=os.environ.get("XOA_PROXY_BIND", BIND),
        metavar="ADDR",
        help=f"Address to bind to (default: {BIND}, env: XOA_PROXY_BIND)",
    )
    return parser.parse_args()


def main() -> None:
    global SSL_VERIFY  # noqa: PLW0603

    args = _parse_args()
    SSL_VERIFY = not args.no_verify_ssl

    server = http.server.HTTPServer((args.bind, args.port), XoaProxyHandler)

    def _on_signal(sig: int, _frame) -> None:
        log.info("Received signal %d, shutting down", sig)
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    log.info(
        "Listening on http://%s:%d/image.xva?src=<https://...xva.gz>  ssl_verify=%s",
        args.bind,
        args.port,
        SSL_VERIFY,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
