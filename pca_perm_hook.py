#!/usr/bin/env python3
"""Claude Code の hook から呼ばれ、許可の依頼をツール（pyxelcube_agents.py）へ渡すスクリプト。

使い方: python3 -I pca_perm_hook.py PermissionRequest（または Notification）。stdin に hook の JSON。
言語は環境変数 PCA_LANG（"ja" または "en"）で受け取る。無ければ "ja"。

PermissionRequest のとき:
  1. ツールの待ち受け（Linux の抽象名前空間の AF_UNIX ソケット）へつなぐ。つながらなければ何も出さない。
  2. 依頼の1行 JSON を送り、返事の1行を WAIT_SEC 秒まで待つ。
  3. 返事が "allow" なら許可、"deny" なら拒否の判定を標準出力に出す。
     "always" のときは、stdin の permission_suggestions（Claude Code の案）が辞書を1つ以上含む list のときだけ、
     その辞書を updatedPermissions に入れた許可の判定を出す（「いつも許可」と同じ）。案が無ければ何も出さない。
     それ以外の返事は何も出さない。
Notification のとき: 通知の1行 JSON を送って閉じる。何も出さない。

どの場合も終了コードは 0。記録（pca_hook_log.jsonl への1行追記）の失敗は無視する。
標準ライブラリのみを使う。
"""

import json
import os
import socket
import sys
import time
from pathlib import Path

# ツールとつなぐ名前。先頭の \0 は Linux の抽象名前空間（ファイルを作らない）
SOCKET_NAME: str = "\0pyxelcube_agents_perm"
# 環境変数の名前（確認用に別の名前へ変えられる）
SOCKET_ENV_NAME: str = "PCA_PERM_SOCKET"
# 返事を待つ最大の秒数（pyxelcube_agents.py の PERM_WAIT_SEC 290 より長くする）
WAIT_SEC: float = 300.0
# 待ち受けへつなぐときの時間切れ（秒）
CONNECT_TIMEOUT: float = 1.0
# 記録の追記先（この hook と同じフォルダ）
LOG_PATH: Path = Path(__file__).resolve().with_name("pca_hook_log.jsonl")
# 返事の1行の最大の長さ（バイト）
MAX_LINE_BYTES: int = 65536
# 言語を渡す環境変数の名前（claude を起動するときに設定する）
LANG_ENV_NAME: str = "PCA_LANG"
# 拒否のときに返す理由文（言語ごと）。言語は環境変数 PCA_LANG で選ぶ
DENY_MESSAGES: dict[str, str] = {"ja": "ユーザーがツールの中で断りました", "en": "The user denied this in the pyxelcube_agents tool"}


def socket_name() -> str:
    """つなぐ名前。環境変数 PCA_PERM_SOCKET があればそれを使い（先頭に \\0 を付ける）、無ければ SOCKET_NAME。"""
    value = os.environ.get(SOCKET_ENV_NAME, "")
    if not value:
        return SOCKET_NAME
    return value if value.startswith("\0") else "\0" + value


def wait_sec() -> float:
    """返事を待つ秒数。環境変数 PCA_PERM_WAIT（確認用）があればそれ、無ければ WAIT_SEC。"""
    value = os.environ.get("PCA_PERM_WAIT", "")
    try:
        return float(value) if value else WAIT_SEC
    except ValueError:
        return WAIT_SEC


def parse_payload(text: str) -> object:
    """stdin の文字列を JSON として解釈する。壊れていれば {"raw": 全文} とする。"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"raw": text}


def item(data: object, key: str) -> object:
    """data が辞書なら key の値を返す。無ければ None。"""
    return data.get(key) if isinstance(data, dict) else None


def connect() -> socket.socket | None:
    """ツールの待ち受けへつなぐ。つながらなければ None を返す。"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(CONNECT_TIMEOUT)
        sock.connect(socket_name())
        return sock
    except OSError:
        sock.close()
        return None


def send_line(sock: socket.socket, payload: dict[str, object]) -> None:
    """1行の JSON（末尾 \\n、UTF-8、ensure_ascii=False）を送る。"""
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    sock.sendall(line.encode("utf-8"))


def recv_line(sock: socket.socket, timeout_sec: float) -> str:
    """返事を1行読む。全体で timeout_sec 秒まで。時間切れ・切断・長すぎるときは例外。"""
    deadline = time.monotonic() + timeout_sec
    buf = bytearray()
    while b"\n" not in buf:
        remain = deadline - time.monotonic()
        if remain <= 0:
            raise TimeoutError("返事の時間切れ")
        sock.settimeout(remain)
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("相手が閉じた")
        buf += chunk
        if len(buf) > MAX_LINE_BYTES:
            raise ValueError("返事が長すぎる")
    return bytes(buf).split(b"\n", 1)[0].decode("utf-8")


def ask_permission(data: object) -> str | None:
    """ツールへ許可の依頼を送り、返事（"allow"・"deny"・"tmux" など）を返す。つながらない・失敗のときは None。"""
    sock = connect()
    if sock is None:
        return None
    try:
        payload: dict[str, object] = {
            "type": "permission",
            "tool_name": item(data, "tool_name"),
            "tool_input": item(data, "tool_input"),
            "session_id": item(data, "session_id"),
            "transcript_path": item(data, "transcript_path"),
            "cwd": item(data, "cwd"),
            "permission_suggestions": item(data, "permission_suggestions"),
        }
        send_line(sock, payload)
        reply = json.loads(recv_line(sock, wait_sec()))
        answer = item(reply, "answer")
        return answer if isinstance(answer, str) else None
    except BaseException:
        return None
    finally:
        sock.close()


def notify(data: object) -> None:
    """ツールへ通知を1行送って閉じる。返事は待たない。つながらなければ何もしない。"""
    sock = connect()
    if sock is None:
        return
    try:
        payload: dict[str, object] = {
            "type": "notification",
            "notification_type": item(data, "notification_type"),
            "message": item(data, "message"),
            "session_id": item(data, "session_id"),
            "cwd": item(data, "cwd"),
        }
        send_line(sock, payload)
    except BaseException:
        pass
    finally:
        sock.close()


def always_rules(suggestions: object) -> list[dict[str, object]]:
    """permission_suggestions から辞書だけを並べた list を返す。list でなければ空の list。"""
    if not isinstance(suggestions, list):
        return []
    return [s for s in suggestions if isinstance(s, dict)]


def hook_lang() -> str:
    """言語（環境変数 PCA_LANG）。"ja"・"en" 以外や無いときは "ja" にする。"""
    value = os.environ.get(LANG_ENV_NAME, "")
    return value if value in DENY_MESSAGES else "ja"


def decision_output(answer: str | None, suggestions: object = None, lang: str = "ja") -> str | None:
    """返事から、標準出力に出す判定の JSON を作る。許可・拒否・いつも許可以外は None（何も出さない）。

    "always" は、suggestions（Claude Code の案）に辞書が1つ以上あるときだけ、その辞書を updatedPermissions に入れて許可する。
    """
    if answer == "allow":
        behavior: dict[str, object] = {"behavior": "allow"}
    elif answer == "deny":
        behavior = {"behavior": "deny", "message": DENY_MESSAGES.get(lang, DENY_MESSAGES["ja"])}
    elif answer == "always":
        rules = always_rules(suggestions)
        if not rules:
            return None
        behavior = {"behavior": "allow", "updatedPermissions": rules}
    else:
        return None
    output: dict[str, object] = {
        "hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": behavior}
    }
    return json.dumps(output)


def append_record(data: object, answer: str | None) -> None:
    """1行の JSON として pca_hook_log.jsonl に追記する。"argv"・"t"・"data" に加えて "answer"。"""
    record: dict[str, object] = {
        "argv": sys.argv[1:],
        "t": time.time(),
        "data": data,
        "answer": answer,
    }
    line = json.dumps(record, ensure_ascii=False)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    """引数に応じて依頼・通知を処理する。終了コードは常に 0。"""
    kind = sys.argv[1] if len(sys.argv) > 1 else ""
    data: object = None
    answer: str | None = None
    try:
        text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = parse_payload(text)
        if kind == "PermissionRequest":
            answer = ask_permission(data)
            output = decision_output(answer, item(data, "permission_suggestions"), hook_lang())
            if output is not None:
                print(output, flush=True)
        elif kind == "Notification":
            notify(data)
    except BaseException:
        pass
    try:
        append_record(data, answer)
    except BaseException:
        pass  # 記録の失敗は無視する
    return 0


if __name__ == "__main__":
    sys.exit(main())
