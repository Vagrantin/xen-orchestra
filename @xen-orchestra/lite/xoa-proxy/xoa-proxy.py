#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import gzip
import http.server
import logging
import os
import signal
import socketserver
import ssl
import sys
import threading
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

# ── Configuration ──────────────────────────────────────────────────────────────
PORT = 9001          # Avoids clash with Vite dev (3000), XAPI (443/80)
BIND = "127.0.0.1"  # Loopback only — XAPI is on the same host, no external exposure needed
CHUNK_SIZE = 64 * 1024  # 64 KiB — large enough to keep the pipeline fed, small enough to stay lean

# Populated by main() after CLI/env parsing; read by XoaProxyHandler._stream_xva().
SSL_VERIFY: bool = True

# A non-blocking lock that ensures only one XVA stream is active at a time.
# A second concurrent request receives HTTP 409 immediately.
_import_lock = threading.Lock()


# ── Server ─────────────────────────────────────────────────────────────────────

class XoaProxyServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Threaded HTTP server — each request runs in its own daemon thread.

    daemon_threads=True means worker threads are killed automatically when the
    main thread exits, so Ctrl+C / SIGTERM shuts down instantly regardless of
    whether a multi-minute stream is in progress.
    Concurrent imports are intentionally blocked via _import_lock.
    """
    daemon_threads = True
    allow_reuse_address = True

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

        Only one import may run at a time — a second concurrent request receives
        HTTP 409 Conflict immediately. HTTP/1.0 semantics: no Content-Length
        (unknown after decompression), connection closed when done. libcurl
        (used internally by VM.import) reads until EOF — spec-compliant.
        """
        if not _import_lock.acquire(blocking=False):
            self._error(409, "An import is already in progress. Only one concurrent import is allowed.")
            return

        try:
            self._do_stream(src_url)
        finally:
            _import_lock.release()

    def _do_stream(self, src_url: str) -> None:
        """Inner stream logic — called only when the import lock is held."""
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
                    "Upstream connected  status=%d content-length=%s content-type=%s",
                    upstream.status,
                    upstream.headers.get("Content-Length", "unknown"),  # log expected size
                    upstream.headers.get("Content-Type", "unknown"),
                )

                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Connection", "close")
                self.end_headers()

                bytes_sent = 0
                stream_complete = False  # ← track clean completion

                try:
                    with gzip.GzipFile(fileobj=upstream) as gz:
                        while True:
                            chunk = gz.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            bytes_sent += len(chunk)
                    # If we exit the `with gz` block without exception,
                    # the gzip footer was validated — stream is complete.
                    stream_complete = True

                except EOFError as exc:
                    # gzip stream ended before the footer — upstream truncated
                    log.error(
                        "Upstream truncated mid-stream after %.1f MiB: %s",
                        bytes_sent / 1024 ** 2,
                        exc,
                    )
                    # Connection is already open to XAPI — close it abruptly
                    # so XAPI gets a connection reset rather than a clean EOF,
                    # making the failure mode more explicit on the XAPI side.
                    return

                except OSError as exc:
                    log.error("Gzip decompression error after %.1f MiB: %s", bytes_sent / 1024 ** 2, exc)
                    return

                finally:
                    if stream_complete:
                        log.info(
                            "Stream complete  bytes_sent=%d (%.1f MiB)",
                            bytes_sent,
                            bytes_sent / 1024 ** 2,
                        )
                    else:
                        log.error(
                            "Stream INCOMPLETE  bytes_sent=%d (%.1f MiB) — "
                            "XAPI will receive premature EOF and fail with INTERNAL_ERROR",
                            bytes_sent,
                            bytes_sent / 1024 ** 2,
                        )

        except urllib.error.URLError as exc:
            log.error("Upstream fetch failed: %s", exc)
            self._error(502, f"Failed to fetch upstream image: {exc}")

        except BrokenPipeError:
            log.warning("Client (XAPI) closed connection before stream completed")

        except Exception as exc:
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

    server = XoaProxyServer((args.bind, args.port), XoaProxyHandler)

    def _on_signal(sig: int, _frame) -> None:
        log.info("Received signal %d, shutting down immediately", sig)
        # sys.exit() kills the main thread instantly; daemon worker threads
        # (including any in-progress stream) are reaped by the OS automatically.
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
