"""pca_perm_hook.py（Claude Code の hook から呼ばれ、許可の依頼をツールへ渡すスクリプト）のテスト。

実行: .venv/bin/python test_pca_perm_hook.py

- 本番と同じ `python3 -I <フルパス> PermissionRequest|Notification` で動かす。
- 記録の追記先（LOG_PATH）は定数でコマンドから変えられないので、hook の写しを一時フォルダに作り、
  LOG_PATH の文字列だけを一時フォルダの中に置き換えて動かす（本物の pca_hook_log.jsonl は一度も開かない）。
  本物のファイルは、最後に大きさと更新時刻が変わっていないことを確かめる。
- つなぐ先は環境変数 PCA_PERM_SOCKET の別名（実行ごと）にした偽のサーバー（スレッド）。本番の名前には絶対につながない。
- 一時フォルダは消さずに、実行ごとに新しい名前（時刻つき）で作る。
"""
import ast
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))
import pca_perm_hook as H

fail: list[str] = []
n_checks = 0

# 一時フォルダの既定はこのファイルと同じフォルダの .test_tmp/（環境変数 PCA_HOOK_TEST_TMP があればそれを使う）
TMP_ROOT = Path(os.environ.get(
    "PCA_HOOK_TEST_TMP",
    str(HERE / ".test_tmp")))
RUN_DIR = TMP_ROOT / f"run_{int(time.time() * 1000)}_{os.getpid()}"
RUN_DIR.mkdir(parents=True, exist_ok=True)
HOOK_SRC = HERE / "pca_perm_hook.py"
REAL_LOG = HERE / "pca_hook_log.jsonl"
real_before = (REAL_LOG.stat().st_size, REAL_LOG.stat().st_mtime_ns) if REAL_LOG.exists() else None
PID = os.getpid()
_no = [0]


def check(c, msg):
    global n_checks
    n_checks += 1
    if not c:
        fail.append(msg)
        print("NG:", msg)


def sock_name() -> str:
    """この実行専用の待ち受けの名前（\\0 なし）。"""
    _no[0] += 1
    return f"pca_test_hook_{PID}_{_no[0]}"


# ---- hook の写し（記録の追記先だけ一時フォルダへ） ----
src_text = HOOK_SRC.read_text(encoding="utf-8")
# hook の LOG_PATH の式（__file__ の隣の pca_hook_log.jsonl）を、一時フォルダの記録の場所の式へ置き換える
REAL_LOG_STR = 'Path(__file__).resolve().with_name("pca_hook_log.jsonl")'
check(src_text.count(REAL_LOG_STR) == 1, "前提：hook の中に本物の記録の場所の式が1つだけある")
LOG_FILE = RUN_DIR / "hook_log.jsonl"
COPY = RUN_DIR / "pca_perm_hook.py"
COPY.write_text(src_text.replace(REAL_LOG_STR, f"Path({str(LOG_FILE)!r})"), encoding="utf-8")
LOG_FILE_BAD = RUN_DIR / "no_such_dir" / "log.jsonl"  # 親フォルダが無い＝追記に失敗する
COPY_BAD = RUN_DIR / "pca_perm_hook_badlog.py"
COPY_BAD.write_text(src_text.replace(REAL_LOG_STR, f"Path({str(LOG_FILE_BAD)!r})"), encoding="utf-8")
check(REAL_LOG_STR not in COPY.read_text(encoding="utf-8") and str(LOG_FILE) in COPY.read_text(encoding="utf-8"), "前提：写しは本物の記録の場所を含まない")


# ---- 偽のサーバー ----
class FakeServer:
    """1回だけ接続を受ける偽のツール。届いた1行を got に入れ、reply（バイト列）を返す。None なら返さない。"""

    def __init__(self, name: str, reply: bytes | None = None, hold_sec: float = 0.0, wait_close: bool = False, chunks: list[bytes] | None = None):
        self.name = name
        self.reply = reply
        self.hold_sec = hold_sec
        self.wait_close = wait_close
        self.chunks = chunks
        self.got: list[bytes] = []
        self.closed_by_peer = threading.Event()
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind("\0" + name)
        self.srv.listen(4)
        self.srv.settimeout(20)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        try:
            conn, _ = self.srv.accept()
        except OSError:
            return
        conn.settimeout(20)
        buf = bytearray()
        try:
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
        except OSError:
            pass
        self.got.append(bytes(buf))
        if self.hold_sec:
            time.sleep(self.hold_sec)
        try:
            if self.chunks is not None:
                for c in self.chunks:
                    conn.sendall(c)
            elif self.reply is not None:
                conn.sendall(self.reply)
            if self.wait_close:
                try:
                    if conn.recv(1) == b"":
                        self.closed_by_peer.set()
                except OSError:
                    pass
        except OSError:
            pass
        conn.close()

    def request(self) -> dict | None:
        return json.loads(self.got[0].decode("utf-8")) if self.got and self.got[0] else None

    def close(self) -> None:
        self.thread.join(timeout=25)
        self.srv.close()


def run_hook(kind: str | None, stdin: bytes | str, name: str | None, wait: str | None = None, script: Path = COPY, lang_env: str | None = None) -> tuple[int, str, float]:
    """hook の写しを python3 -I で動かす。戻り値は (終了コード, 標準出力, 秒数)。name が None なら PCA_PERM_SOCKET を付けない（※使わない）。"""
    env = dict(os.environ)
    env.pop("PCA_PERM_SOCKET", None)
    env.pop("PCA_PERM_WAIT", None)
    env.pop("PCA_LANG", None)  # 言語は環境変数 PCA_LANG で渡す。外の値を受け継がない
    if lang_env is not None:
        env["PCA_LANG"] = lang_env
    assert name is not None, "本番の名前につながないよう、必ず別名を渡す"
    env["PCA_PERM_SOCKET"] = name
    if wait is not None:
        env["PCA_PERM_WAIT"] = wait
    args = ["python3", "-I", str(script)] + ([kind] if kind is not None else [])
    t0 = time.monotonic()
    proc = subprocess.run(args, input=stdin if isinstance(stdin, bytes) else stdin.encode("utf-8"), capture_output=True, env=env, timeout=60)
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace"), time.monotonic() - t0


def log_lines() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    return [json.loads(x) for x in LOG_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]


PAYLOAD = {
    "tool_name": "Bash",
    "tool_input": {"command": "ls 日本語 -la", "description": "一覧"},
    "session_id": "sess-1",
    "transcript_path": "/x/t.jsonl",
    "cwd": "/home/x/pca_work",
    "hook_event_name": "PermissionRequest",
    "permission_mode": "default",
}
PAYLOAD_TEXT = json.dumps(PAYLOAD, ensure_ascii=False)
ALLOW_OUT = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}
DENY_OUT = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "deny", "message": "ユーザーがツールの中で断りました"}}}
DENY_OUT_EN = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "deny", "message": "The user denied this in the pyxelcube_agents tool"}}}

# ---------------------------------------------------------------------------
# 1. 定数・純粋な関数（この中で import した本物のモジュール。記録や接続はしない）
# ---------------------------------------------------------------------------
check(H.SOCKET_NAME == "\0pyxelcube_agents_perm", f"1: SOCKET_NAME {H.SOCKET_NAME!r}")
check(H.WAIT_SEC == 300.0 and H.CONNECT_TIMEOUT == 1.0, f"1: WAIT_SEC=300・CONNECT_TIMEOUT=1.0 {H.WAIT_SEC} {H.CONNECT_TIMEOUT}")
check(H.LOG_PATH == REAL_LOG.resolve(), f"1: 記録の追記先は pca_hook_log.jsonl {H.LOG_PATH}")
check(H.DENY_MESSAGES == {"ja": "ユーザーがツールの中で断りました", "en": "The user denied this in the pyxelcube_agents tool"}, "1: 拒否の理由文（ja・en）")
check(json.loads(H.decision_output("deny", None, "en")) == DENY_OUT_EN, "1: decision_output(deny, en) は英語")
check(H.LANG_ENV_NAME == "PCA_LANG", "1: 言語の環境変数の名前")
_saved_lang = os.environ.get("PCA_LANG")
try:
    for val, want in (("en", "en"), ("ja", "ja"), ("fr", "ja"), ("", "ja"), (None, "ja")):
        if val is None:
            os.environ.pop("PCA_LANG", None)
        else:
            os.environ["PCA_LANG"] = val
        check(H.hook_lang() == want, f"1: hook_lang() PCA_LANG={val!r} → {want}")
finally:
    if _saved_lang is None:
        os.environ.pop("PCA_LANG", None)
    else:
        os.environ["PCA_LANG"] = _saved_lang
check(json.loads(H.decision_output("deny", None, "fr")) == DENY_OUT, "1: decision_output(deny, fr) は日本語")
_saved_env = {k: os.environ.get(k) for k in ("PCA_PERM_SOCKET", "PCA_PERM_WAIT")}
try:
    os.environ.pop("PCA_PERM_SOCKET", None)
    check(H.socket_name() == "\0pyxelcube_agents_perm", "1: 環境変数が無ければ既定の名前")
    os.environ["PCA_PERM_SOCKET"] = ""
    check(H.socket_name() == "\0pyxelcube_agents_perm", "1: 環境変数が空なら既定の名前")
    os.environ["PCA_PERM_SOCKET"] = "abc"
    check(H.socket_name() == "\0abc", "1: 環境変数の名前の先頭に \\0 を付ける")
    os.environ.pop("PCA_PERM_WAIT", None)
    check(H.wait_sec() == 300.0, "1: PCA_PERM_WAIT が無ければ WAIT_SEC")
    os.environ["PCA_PERM_WAIT"] = "2.5"
    check(H.wait_sec() == 2.5, "1: PCA_PERM_WAIT があればそれ")
    os.environ["PCA_PERM_WAIT"] = "ばか"
    check(H.wait_sec() == 300.0, "1: PCA_PERM_WAIT が数でなければ WAIT_SEC")
    os.environ["PCA_PERM_WAIT"] = ""
    check(H.wait_sec() == 300.0, "1: PCA_PERM_WAIT が空なら WAIT_SEC")
finally:
    for k, v in _saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
check(H.parse_payload('{"a": 1}') == {"a": 1}, "1: parse_payload：JSON")
check(H.parse_payload("こわれた{") == {"raw": "こわれた{"}, "1: parse_payload：壊れていれば raw に全文")
check(H.parse_payload("") == {"raw": ""}, "1: parse_payload：空は raw が空")
check(H.item({"a": 1}, "a") == 1 and H.item({"a": 1}, "b") is None and H.item([1], "a") is None and H.item(None, "a") is None, "1: item：辞書以外・無い項目は None")
check(json.loads(H.decision_output("allow")) == ALLOW_OUT, "1: decision_output(allow)")
check(json.loads(H.decision_output("deny")) == DENY_OUT, "1: decision_output(deny)")
for a in ("tmux", None, "", "ALLOW", "yes", "allow ", 1):
    check(H.decision_output(a) is None, f"1: decision_output({a!r}) は None（何も出さない）")
for a in ("allow", "deny"):
    check("\n" not in H.decision_output(a), f"1: {a} の出力は1行")
    d = H.decision_output(a)
    check(all(k not in d for k in ("updatedInput", "updatedPermissions", "interrupt")), f"1: {a} の出力に updatedInput・updatedPermissions・interrupt を含まない")
# 実行ファイルの決まり
first = src_text.split("\n", 1)[0]
check(first == "#!/usr/bin/env python3", f"1: 先頭は #!/usr/bin/env python3 {first!r}")
check(os.access(HOOK_SRC, os.X_OK), "1: 実行できる（chmod +x）")
tree = ast.parse(src_text)
mods = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        mods.update(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        mods.add(node.module.split(".")[0])
check(mods <= {"json", "os", "socket", "sys", "time", "pathlib"} and mods <= set(sys.stdlib_module_names), f"1: 標準ライブラリだけを使う {mods}")
# always のときだけ updatedPermissions を返す仕様になったので、updatedPermissions は書いてよい（updatedInput・interrupt は今までどおり書かない）
check("updatedInput" not in src_text and '"interrupt"' not in src_text and src_text.count('"updatedPermissions"') == 1, "1: ソースに updatedInput・interrupt を書いていない（updatedPermissions は always の1か所だけ）")

# ---------------------------------------------------------------------------
# 2. PermissionRequest：allow・deny・tmux・それ以外
# ---------------------------------------------------------------------------
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "allow"}\n')
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
check(rc == 0, f"2: allow：終了コード 0 {rc}")
check(out.endswith("\n") and out.count("\n") == 1 and json.loads(out) == ALLOW_OUT, f"2: allow：標準出力 {out!r}")
req = fs.request()
check(fs.got[0].endswith(b"\n") and fs.got[0].count(b"\n") == 1, "2: 依頼は末尾 \\n の1行")
check("日本語".encode("utf-8") in fs.got[0] and b"\\u" not in fs.got[0], "2: 依頼は UTF-8（ensure_ascii=False）")
check(req == {"type": "permission", "tool_name": "Bash", "tool_input": PAYLOAD["tool_input"], "session_id": "sess-1", "transcript_path": "/x/t.jsonl", "cwd": "/home/x/pca_work", "permission_suggestions": None}, f"2: 依頼の中身（type・tool_name・tool_input・session_id・transcript_path・cwd・permission_suggestions だけ。案が無ければ null） {req}")

nm = sock_name()
fs = FakeServer(nm, b'{"answer": "deny"}\n')
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
check(rc == 0 and json.loads(out) == DENY_OUT, f"2: deny：判定と理由文 {rc} {out!r}")
check("updatedInput" not in out and "updatedPermissions" not in out and "interrupt" not in out, "2: deny の出力に updatedInput などを含まない")

for label, reply in (
    ("tmux", b'{"answer": "tmux"}\n'),
    ("知らない答え", b'{"answer": "maybe"}\n'),
    ("答えが数", b'{"answer": 1}\n'),
    ("答えが null", b'{"answer": null}\n'),
    ("answer 無し", b'{"x": 1}\n'),
    ("大文字の ALLOW", b'{"answer": "ALLOW"}\n'),
    ("辞書でない返事", b'[1, 2]\n'),
    ("壊れた JSON", "{こわれ\n".encode("utf-8")),
    ("文字でない返事", b'\xff\xfe\n'),
    ("空行だけ", b'\n'),
):
    nm = sock_name()
    fs = FakeServer(nm, reply)
    rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
    fs.close()
    check(rc == 0 and out == "", f"2: {label}：何も出さず終了コード 0 {rc} {out!r}")

# 返事の前に切断・何も返さず閉じる
nm = sock_name()
fs = FakeServer(nm, None)
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
check(rc == 0 and out == "" and sec < 10, f"2: 返事なしで切断：何も出さず速やかに終わる {rc} {out!r} {sec:.1f}")
# 改行の無い返事で切断（途中まで）
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "allow"}')
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
check(rc == 0 and out == "", f"2: 改行の無い返事（切断）は何も出さない {out!r}")
# 返事を分けて送っても読める
nm = sock_name()
fs = FakeServer(nm, chunks=[b'{"ans', b'wer": "al', b'low"}\n'])
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
check(rc == 0 and json.loads(out or "null") == ALLOW_OUT, f"2: 返事が分かれて届いても allow {out!r}")
# 返事の1行目だけを見る（後ろに余計な行があっても）
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "deny"}\n{"answer": "allow"}\n')
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
check(rc == 0 and json.loads(out or "null") == DENY_OUT, "2: 返事は1行目だけを使う")
# 長すぎる返事（MAX_LINE_BYTES 超え・改行なし）は捨てる
nm = sock_name()
fs = FakeServer(nm, chunks=[b"x" * 70000], wait_close=True)
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
check(rc == 0 and out == "", f"2: 長すぎる返事は何も出さない {out!r}")
# 時間切れ（PCA_PERM_WAIT を短くする）
nm = sock_name()
fs = FakeServer(nm, None, hold_sec=0.0, wait_close=True)
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm, wait="0.6")
fs.close()
check(rc == 0 and out == "" and 0.5 <= sec < 8, f"2: 時間切れ：何も出さず 0.6 秒あたりで終わる {rc} {out!r} {sec:.2f}")
check(fs.closed_by_peer.is_set(), "2: 時間切れのあと hook が接続を閉じる")
# 時間切れの前に答えが来れば待たずに出す（待ちの上限が長くても）
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "allow"}\n', hold_sec=0.3)
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm, wait="30")
fs.close()
check(rc == 0 and json.loads(out) == ALLOW_OUT and sec < 10, f"2: 0.3 秒後の答えをすぐ受け取る（待ち上限 30 秒） {sec:.2f}")
# サーバー無し：何も出さず終了コード 0（いつもの許可画面になる）
nm = sock_name()
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
check(rc == 0 and out == "" and sec < 8, f"2: サーバー無しは何も出さず終了コード 0 {rc} {out!r} {sec:.2f}")

# ---------------------------------------------------------------------------
# 3. stdin が足りない・壊れている
# ---------------------------------------------------------------------------
for label, stdin, want_req in (
    ("空の辞書", "{}", {"type": "permission", "tool_name": None, "tool_input": None, "session_id": None, "transcript_path": None, "cwd": None, "permission_suggestions": None}),
    ("壊れた JSON", "こわれ{", {"type": "permission", "tool_name": None, "tool_input": None, "session_id": None, "transcript_path": None, "cwd": None, "permission_suggestions": None}),
    ("空の stdin", "", {"type": "permission", "tool_name": None, "tool_input": None, "session_id": None, "transcript_path": None, "cwd": None, "permission_suggestions": None}),
    ("配列の JSON", "[1, 2]", {"type": "permission", "tool_name": None, "tool_input": None, "session_id": None, "transcript_path": None, "cwd": None, "permission_suggestions": None}),
    ("一部の項目だけ", '{"tool_name": "Read"}', {"type": "permission", "tool_name": "Read", "tool_input": None, "session_id": None, "transcript_path": None, "cwd": None, "permission_suggestions": None}),
):
    nm = sock_name()
    fs = FakeServer(nm, b'{"answer": "deny"}\n')
    rc, out, sec = run_hook("PermissionRequest", stdin, nm)
    fs.close()
    check(rc == 0 and fs.request() == want_req, f"3: {label}：無い項目は null で送る {fs.request()}")
    check(json.loads(out or "null") == DENY_OUT, f"3: {label}：それでも返事は判定になる {out!r}")
# 文字として壊れたバイト列でも落ちない
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "allow"}\n')
rc, out, sec = run_hook("PermissionRequest", b'{"tool_name": "B\xff\xfe"}', nm)
fs.close()
check(rc == 0 and fs.request() is not None and json.loads(out or "null") == ALLOW_OUT, f"3: UTF-8 として壊れた stdin でも落ちない {rc} {out!r}")
# 大きな入力
nm = sock_name()
big = {"tool_name": "Write", "tool_input": {"content": "あ" * 30000}, "cwd": "/x"}
fs = FakeServer(nm, b'{"answer": "allow"}\n')
rc, out, sec = run_hook("PermissionRequest", json.dumps(big, ensure_ascii=False), nm)
fs.close()
check(rc == 0 and fs.request() is not None and fs.request()["tool_input"]["content"] == "あ" * 30000 and json.loads(out) == ALLOW_OUT, "3: 大きな入力でも全文が届く")

# ---------------------------------------------------------------------------
# 4. Notification：1行送って、返事を待たずに閉じる。何も出さない
# ---------------------------------------------------------------------------
NOTE = {"notification_type": "permission_prompt", "message": "Claude needs your permission to use Bash", "session_id": "sess-1", "cwd": "/home/x/pca_work", "hook_event_name": "Notification", "transcript_path": "/x/t.jsonl"}
nm = sock_name()
fs = FakeServer(nm, None, wait_close=True)
rc, out, sec = run_hook("Notification", json.dumps(NOTE, ensure_ascii=False), nm, wait="30")
fs.close()
check(rc == 0 and out == "", f"4: Notification：何も出さず終了コード 0 {rc} {out!r}")
check(sec < 10, f"4: 返事を待たずに終わる（待ち上限 30 秒でも） {sec:.2f}")
check(fs.request() == {"type": "notification", "notification_type": "permission_prompt", "message": "Claude needs your permission to use Bash", "session_id": "sess-1", "cwd": "/home/x/pca_work"}, f"4: 通知の中身 {fs.request()}")
check(fs.got[0].endswith(b"\n") and fs.closed_by_peer.is_set(), "4: 末尾 \\n の1行を送って閉じる")
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "allow"}\n')
rc, out, sec = run_hook("Notification", "{}", nm)
fs.close()
check(rc == 0 and out == "" and fs.request() == {"type": "notification", "notification_type": None, "message": None, "session_id": None, "cwd": None}, f"4: 返事が来ても何も出さない・無い項目は null {out!r} {fs.request()}")
nm = sock_name()
rc, out, sec = run_hook("Notification", json.dumps(NOTE), nm)
check(rc == 0 and out == "" and sec < 8, f"4: Notification でサーバー無しでも何も出さず終了コード 0 {rc} {out!r}")
rc, out, sec = run_hook("Notification", "こわれ{", sock_name())
check(rc == 0 and out == "", "4: Notification で stdin が壊れていても落ちない")

# ---------------------------------------------------------------------------
# 5. 引数が不明・無し：つながない・何も出さない
# ---------------------------------------------------------------------------
for label, kind in (("引数なし", None), ("知らない種類", "Stop"), ("小文字", "permissionrequest"), ("空文字", "")):
    nm = sock_name()
    fs = FakeServer(nm, b'{"answer": "allow"}\n')
    rc, out, sec = run_hook(kind, PAYLOAD_TEXT, nm)
    check(rc == 0 and out == "" and not fs.got, f"5: {label}：つながず何も出さず終了コード 0 {rc} {out!r} {fs.got}")
    try:
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.connect("\0" + nm)
        c.close()
    except OSError:
        pass
    fs.close()

# ---------------------------------------------------------------------------
# 6. 記録（pca_hook_log.jsonl の写しの先）：argv・t・data・answer
# ---------------------------------------------------------------------------
n0 = len(log_lines())
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "allow"}\n')
t0 = time.time()
run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
ls = log_lines()
check(len(ls) == n0 + 1, f"6: 呼ぶたびに1行追記 {n0} → {len(ls)}")
rec = ls[-1]
check(set(rec) == {"argv", "t", "data", "answer"}, f"6: 項目は argv・t・data・answer {set(rec)}")
check(rec["argv"] == ["PermissionRequest"] and rec["data"] == PAYLOAD and rec["answer"] == "allow", f"6: allow の記録 {rec['argv']} {rec['answer']}")
check(t0 - 1 <= rec["t"] <= time.time() + 1, "6: t は呼ばれた時刻（秒）")
raw_line = LOG_FILE.read_text(encoding="utf-8").splitlines()[-1]
check("日本語" in raw_line, "6: 記録は ensure_ascii=False の1行")
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "deny"}\n')
run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
check(log_lines()[-1]["answer"] == "deny", "6: deny の記録")
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "tmux"}\n')
run_hook("PermissionRequest", PAYLOAD_TEXT, nm)
fs.close()
check(log_lines()[-1]["answer"] == "tmux", "6: tmux の記録（返事の文字そのまま）")
run_hook("PermissionRequest", PAYLOAD_TEXT, sock_name())
check(log_lines()[-1]["answer"] is None, "6: サーバー無しの answer は null")
nm = sock_name()
fs = FakeServer(nm, None)
run_hook("Notification", json.dumps(NOTE, ensure_ascii=False), nm)
fs.close()
rec = log_lines()[-1]
check(rec["argv"] == ["Notification"] and rec["data"] == NOTE and rec["answer"] is None, "6: Notification の記録（answer は null）")
run_hook("PermissionRequest", "こわれ{", sock_name())
check(log_lines()[-1]["data"] == {"raw": "こわれ{"}, f"6: 壊れた stdin は {{raw: 全文}} で記録 {log_lines()[-1]['data']}")
run_hook(None, "{}", sock_name())
check(log_lines()[-1]["argv"] == [] and log_lines()[-1]["data"] == {}, "6: 引数なしも記録する")
# 記録に失敗しても結果は変わらない
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "allow"}\n')
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm, script=COPY_BAD)
fs.close()
check(rc == 0 and json.loads(out or "null") == ALLOW_OUT and not LOG_FILE_BAD.exists(), f"6: 記録に失敗しても判定は出て終了コード 0 {rc} {out!r}")
rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, sock_name(), script=COPY_BAD)
check(rc == 0 and out == "", "6: 記録に失敗しサーバーも無くても終了コード 0")

# ---------------------------------------------------------------------------
# 7. settings.local.json（pca_work/.claude/settings.local.json）が指示書どおり
# ---------------------------------------------------------------------------
SETTINGS = HERE / "pca_work" / ".claude" / "settings.local.json"
# 配布版では hook を起動時に --settings で渡すため、このファイルは無いのがふつう。あるときだけ中身を確かめる
if SETTINGS.exists():
    st = json.loads(SETTINGS.read_text(encoding="utf-8"))
    hook_path = str(HOOK_SRC)
    want_hooks = {
        "PermissionRequest": [{"matcher": "*", "hooks": [{"type": "command", "command": f"python3 -I {hook_path} PermissionRequest", "timeout": 330}]}],
        "Notification": [{"matcher": "*", "hooks": [{"type": "command", "command": f"python3 -I {hook_path} Notification", "timeout": 10}]}],
    }
    check(st.get("hooks") == want_hooks, f"7: hooks が指示書どおり {st.get('hooks')}")
    check(st["hooks"]["PermissionRequest"][0]["hooks"][0]["timeout"] > H.WAIT_SEC, "7: PermissionRequest の timeout（330）が hook の待ち（300）より長い")
    check(set(st) == {"hooks"}, f"7: hooks のほかに項目を足していない {set(st)}")
else:
    print("7: pca_work/.claude/settings.local.json が無いので飛ばす（配布版では不要）")

# ---------------------------------------------------------------------------
# 8. always（いつも許可）：Claude Code の案（permission_suggestions）を updatedPermissions に返す
# ---------------------------------------------------------------------------
SUG_MODE = {"type": "setMode", "mode": "acceptEdits", "destination": "session"}
SUG_RULES = {"type": "addRules", "rules": [{"toolName": "Bash", "ruleContent": "npm run lint"}], "behavior": "allow", "destination": "localSettings"}


def always_out(rules) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow", "updatedPermissions": rules}}}


# 8-a. decision_output の純粋な部分
check(json.loads(H.decision_output("always", [SUG_MODE])) == always_out([SUG_MODE]), "8: always：案の辞書が updatedPermissions に入る")
check(json.loads(H.decision_output("always", [SUG_MODE, SUG_RULES])) == always_out([SUG_MODE, SUG_RULES]), "8: always：案が2つなら順に両方入る")
check(json.loads(H.decision_output("always", [SUG_MODE, "文字", 3, None, SUG_RULES])) == always_out([SUG_MODE, SUG_RULES]), "8: always：辞書でないものは外し、辞書だけを入れる")
for label, sg in (("案なし（None）", None), ("空の list", []), ("辞書を含まない list", ["a", 1, None]), ("list でない（辞書）", SUG_MODE), ("list でない（文字）", "x"), ("list でない（数）", 5)):
    check(H.decision_output("always", sg) is None, f"8: always で{label}は何も出さない")
check(H.decision_output("always") is None, "8: always で案の引数を省くと何も出さない")
out_always = H.decision_output("always", [SUG_MODE, SUG_RULES])
check("\n" not in out_always and "updatedInput" not in out_always and "interrupt" not in out_always, "8: always の出力は1行で、updatedInput・interrupt を含まない")
# allow・deny は案があっても updatedPermissions を出さない
for a in ("allow", "deny"):
    check("updatedPermissions" not in H.decision_output(a, [SUG_MODE]), f"8: {a} は案があっても updatedPermissions を出さない")
check(H.always_rules([SUG_MODE, "x"]) == [SUG_MODE] and H.always_rules(None) == [] and H.always_rules({"a": 1}) == [], "8: always_rules は list の辞書だけ")
# 8-b. 本番と同じ起動：案つきの依頼は permission_suggestions をそのままツールへ送り、always で updatedPermissions を出す
payload_s = dict(PAYLOAD, permission_suggestions=[SUG_MODE, SUG_RULES])
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "always"}\n')
rc, out, sec = run_hook("PermissionRequest", json.dumps(payload_s, ensure_ascii=False), nm)
fs.close()
check(rc == 0 and fs.request()["permission_suggestions"] == [SUG_MODE, SUG_RULES], f"8: 依頼に permission_suggestions がそのまま入る {fs.request()}")
check(out.count("\n") == 1 and json.loads(out) == always_out([SUG_MODE, SUG_RULES]), f"8: always：updatedPermissions に案の辞書だけ {out!r}")
check(log_lines()[-1]["answer"] == "always", "8: 記録の answer は always")
# 案に辞書以外が混じっていても、依頼にはそのまま送り、返すのは辞書だけ
payload_m = dict(PAYLOAD, permission_suggestions=["x", SUG_MODE])
nm = sock_name()
fs = FakeServer(nm, b'{"answer": "always"}\n')
rc, out, sec = run_hook("PermissionRequest", json.dumps(payload_m, ensure_ascii=False), nm)
fs.close()
check(fs.request()["permission_suggestions"] == ["x", SUG_MODE] and json.loads(out) == always_out([SUG_MODE]), f"8: 依頼にはそのまま・返事は辞書だけ {out!r}")
# 案なし・案が空・辞書なし・list でない：always でも何も出さない（いつもの許可画面）
for label, pl in (("案の項目なし", PAYLOAD), ("案が null", dict(PAYLOAD, permission_suggestions=None)), ("案が空 list", dict(PAYLOAD, permission_suggestions=[])),
                  ("辞書なし", dict(PAYLOAD, permission_suggestions=["a", 1])), ("list でない", dict(PAYLOAD, permission_suggestions="x"))):
    nm = sock_name()
    fs = FakeServer(nm, b'{"answer": "always"}\n')
    rc, out, sec = run_hook("PermissionRequest", json.dumps(pl, ensure_ascii=False), nm)
    fs.close()
    check(rc == 0 and out == "", f"8: always でも{label}は何も出さず終了コード 0 {rc} {out!r}")
# 案つきでも allow・deny の出力は今までどおり（updatedPermissions なし）
for ans, want in ((b"allow", ALLOW_OUT), (b"deny", DENY_OUT)):
    nm = sock_name()
    fs = FakeServer(nm, b'{"answer": "' + ans + b'"}\n')
    rc, out, sec = run_hook("PermissionRequest", json.dumps(payload_s, ensure_ascii=False), nm)
    fs.close()
    check(rc == 0 and json.loads(out) == want and "updatedPermissions" not in out, f"8: 案つきの依頼でも {ans.decode()} は今までの出力 {out!r}")
# 本物の settings.local.json の許可の項目は変えていない（読むだけ）。この節では本物の記録も開いていない（最後の確認で見る）

# ---------------------------------------------------------------------------
# 9. 言語（環境変数 PCA_LANG）：操作→deny の message の言語
# ---------------------------------------------------------------------------
for label, lenv, want in (("PCA_LANG=en", "en", DENY_OUT_EN), ("PCA_LANG なし", None, DENY_OUT), ("PCA_LANG=fr", "fr", DENY_OUT), ("PCA_LANG=ja", "ja", DENY_OUT), ("PCA_LANG 空", "", DENY_OUT)):
    nm = sock_name()
    fs = FakeServer(nm, b'{"answer": "deny"}\n')
    rc, out, sec = run_hook("PermissionRequest", PAYLOAD_TEXT, nm, lang_env=lenv)
    fs.close()
    check(rc == 0 and json.loads(out) == want, f"9: PermissionRequest {label} の deny の message {out!r}")

# ---------------------------------------------------------------------------
# 結果
# ---------------------------------------------------------------------------
real_after = (REAL_LOG.stat().st_size, REAL_LOG.stat().st_mtime_ns) if REAL_LOG.exists() else None
check(real_before == real_after, f"本物の pca_hook_log.jsonl は変わっていない {real_before} {real_after}")
print(f"（一時フォルダ {RUN_DIR}）")
if fail:
    print(f"\n失敗 {len(fail)} 件（全 {n_checks} 項目）:")
    for f in fail:
        print(" -", f)
    sys.exit(1)
print(f"{n_checks} 項目 全部成功")
sys.exit(0)
