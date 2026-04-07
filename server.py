#!/usr/bin/env python3
import json
import os
import queue
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import psycopg2

ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
HOST = "127.0.0.1"
PORT = 8787


class CommandManager:
    def __init__(self):
        self.proc = None
        self.proc_lock = threading.Lock()
        self.logs = []
        self.logs_lock = threading.Lock()
        self.subscribers = []
        self.subscribers_lock = threading.Lock()
        self.last_command = ""
        self.last_run_lines = []
        self.last_run_lock = threading.Lock()

    def _publish(self, line):
        with self.logs_lock:
            self.logs.append(line)
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]

        dead = []
        with self.subscribers_lock:
            for q in self.subscribers:
                try:
                    q.put_nowait(line)
                except Exception:
                    dead.append(q)
            for q in dead:
                if q in self.subscribers:
                    self.subscribers.remove(q)

    def subscribe(self):
        q = queue.Queue(maxsize=200)
        with self.subscribers_lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self.subscribers_lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def snapshot_logs(self):
        with self.logs_lock:
            return list(self.logs)

    def is_running(self):
        with self.proc_lock:
            return self.proc is not None and self.proc.poll() is None

    def start(self, command):
        with self.proc_lock:
            if self.proc is not None and self.proc.poll() is None:
                raise RuntimeError("Ja existe um comando em execucao.")

            with self.last_run_lock:
                self.last_command = command
                self.last_run_lines = []

            self._publish(f"$ {command}")
            self.proc = subprocess.Popen(
                command,
                shell=True,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=os.environ.copy(),
            )

            thread = threading.Thread(target=self._read_output, daemon=True)
            thread.start()

    def _read_output(self):
        proc = None
        with self.proc_lock:
            proc = self.proc
        if proc is None or proc.stdout is None:
            return

        for line in proc.stdout:
            clean = line.rstrip("\n")
            self._publish(clean)
            with self.last_run_lock:
                self.last_run_lines.append(clean)
                if len(self.last_run_lines) > 2000:
                    self.last_run_lines = self.last_run_lines[-2000:]

        exit_code = proc.wait()
        self._publish(f"[processo finalizado] exit_code={exit_code}")
        with self.last_run_lock:
            self.last_run_lines.append(f"[processo finalizado] exit_code={exit_code}")

    def stop(self):
        with self.proc_lock:
            if self.proc is None or self.proc.poll() is not None:
                return False
            self.proc.terminate()
            return True

    def get_last_run(self):
        with self.last_run_lock:
            return {
                "command": self.last_command,
                "lines": list(self.last_run_lines),
            }


class TagStore:
    def __init__(self):
        self.cfg = {
            "host": os.getenv("PM3_PGHOST", "192.168.31.229"),
            "port": int(os.getenv("PM3_PGPORT", "5432")),
            "dbname": os.getenv("PM3_PGDATABASE", "proxmark"),
            "user": os.getenv("PM3_PGUSER", "proxmark"),
            "password": os.getenv("PM3_PGPASSWORD", "proxmark123"),
        }
        self._setup_done = False
        self._setup_lock = threading.Lock()

    def _conn(self):
        return psycopg2.connect(
            host=self.cfg["host"],
            port=self.cfg["port"],
            dbname=self.cfg["dbname"],
            user=self.cfg["user"],
            password=self.cfg["password"],
        )

    def ensure_setup(self):
        if self._setup_done:
            return
        with self._setup_lock:
            if self._setup_done:
                return
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS tag_reads (
                          id BIGSERIAL PRIMARY KEY,
                          frequency TEXT NOT NULL,
                          uid TEXT,
                          source_command TEXT NOT NULL,
                          raw_output TEXT NOT NULL,
                          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                        """
                    )
            self._setup_done = True

    def save_read(self, frequency, uid, source_command, raw_output):
        self.ensure_setup()
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tag_reads (frequency, uid, source_command, raw_output)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, created_at;
                    """,
                    (frequency, uid, source_command, raw_output),
                )
                row = cur.fetchone()
        return {"id": row[0], "created_at": row[1].isoformat()}

    def list_reads(self, limit=50):
        self.ensure_setup()
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, frequency, uid, source_command, created_at
                    FROM tag_reads
                    ORDER BY id DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "frequency": r[1],
                "uid": r[2] or "",
                "source_command": r[3],
                "created_at": r[4].isoformat(),
            }
            for r in rows
        ]


def infer_frequency(command, lines):
    c = command.lower()
    joined = "\n".join(lines).lower()
    if "hf " in c or "13.56" in joined:
        return "HF 13.56MHz"
    if "lf " in c or "125" in joined or "134" in joined:
        return "LF 125/134KHz"
    return "DESCONHECIDA"


def infer_uid(lines):
    patterns = [
        r"\bUID[:\s]+([0-9A-Fa-f ]{4,})",
        r"\bCard UID[:\s]+([0-9A-Fa-f ]{4,})",
        r"\bcsn[:\s]+([0-9A-Fa-f ]{4,})",
    ]
    text = "\n".join(lines)
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            return " ".join(m.group(1).split()).upper()
    return ""


manager = CommandManager()
store = TagStore()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/status":
            return self._json({"running": manager.is_running()})

        if parsed.path == "/api/logs":
            return self._json({"lines": manager.snapshot_logs()})

        if parsed.path == "/api/tags":
            try:
                query = parse_qs(parsed.query or "")
                limit = int(query.get("limit", ["50"])[0])
                limit = max(1, min(limit, 200))
                rows = store.list_reads(limit=limit)
                return self._json({"rows": rows})
            except Exception as e:
                return self._json({"error": str(e)}, status=500)

        if parsed.path == "/api/stream":
            return self._sse_stream()

        return self._serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else ""
        body = parse_qs(raw)

        if parsed.path == "/api/start":
            command = body.get("command", [""])[0].strip()
            if not command:
                return self._json({"error": "command vazio"}, status=400)
            try:
                manager.start(command)
                return self._json({"ok": True})
            except RuntimeError as e:
                return self._json({"error": str(e)}, status=409)
            except Exception as e:
                return self._json({"error": str(e)}, status=500)

        if parsed.path == "/api/stop":
            stopped = manager.stop()
            return self._json({"ok": True, "stopped": stopped})

        if parsed.path == "/api/save-last-read":
            try:
                run = manager.get_last_run()
                lines = run["lines"]
                if not lines:
                    return self._json({"error": "nao ha leitura para salvar"}, status=400)
                frequency = infer_frequency(run["command"], lines)
                uid = infer_uid(lines)
                raw_output = "\n".join(lines)
                saved = store.save_read(
                    frequency=frequency,
                    uid=uid,
                    source_command=run["command"],
                    raw_output=raw_output,
                )
                return self._json({"ok": True, "saved": saved, "frequency": frequency, "uid": uid})
            except Exception as e:
                return self._json({"error": str(e)}, status=500)

        return self._json({"error": "rota nao encontrada"}, status=404)

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        file_path = (PUBLIC_DIR / path.lstrip("/")).resolve()

        if not str(file_path).startswith(str(PUBLIC_DIR.resolve())):
            self.send_error(403)
            return

        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return

        ctype = "text/plain; charset=utf-8"
        if file_path.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        elif file_path.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"

        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _json(self, payload, status=200):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _sse_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        q = manager.subscribe()
        try:
            for line in manager.snapshot_logs():
                self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
            self.wfile.flush()

            while True:
                line = q.get()
                self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                self.wfile.flush()
        except Exception:
            pass
        finally:
            manager.unsubscribe(q)


def main():
    print(f"Painel Proxmark em http://{HOST}:{PORT}")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
