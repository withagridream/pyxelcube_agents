"""Claude Code とつなぐ部品（pyxelcube_agents.py とは切り離した、単体の部品）。

tmux のセッションに claude を立てて文字を送り、会話の記録（jsonl）の追記を見張って、
プロンプト・道具の使用・返事・1回の返事の終わり・サブエージェントの開始と終わりを
イベントにして返す。本物の claude は自動では起動しない。
テストでは tmux と inotifywait をまねたもので動かせる作りにしてある。
標準ライブラリだけを使う（pyxel は使わない）。
"""

from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from pca_i18n import t

# 既定の値
DEFAULT_SESSION = "pyxelcube_agents"
DEFAULT_WORKDIR = str(Path(__file__).resolve().parent / "pca_work")  # このファイルと同じフォルダの pca_work
PASTE_BUFFER = "pca"  # tmux の貼り付け用のバッファの名前
SUMMARY_MAX = 60  # 道具の使用の要約の最大の文字数
TOOL_SUMMARY_KEYS = ("description", "command", "file_path", "pattern", "prompt")  # 要約に使う入力の項目（この順）
SINCE_MARGIN_SEC = 2.0  # 見張りの開始の少し前から（秒）
RESUME_LOOKBACK_SEC = 600.0  # つなぐときは、10分前から更新されたファイルを読む（秒）
SUBAGENT_PREFIX = "agent-"
TMUX_COLS = 98  # tmux の画面の桁数（窓に映したとき 1 行に収まるように）
TMUX_ROWS = 40  # tmux の画面の行数


# ---- イベント ----


@dataclass(frozen=True)
class Prompt:
    """利用者が打ったプロンプト。"""

    session: str
    text: str


@dataclass(frozen=True)
class Tool:
    """道具の使用（Bash・Edit など）。summary は入力の要約（60 文字まで）。"""

    session: str
    name: str
    summary: str


@dataclass(frozen=True)
class Reply:
    """返事の文。"""

    session: str
    text: str


@dataclass(frozen=True)
class TurnEnd:
    """1 回の返事の終わり。"""

    session: str


@dataclass(frozen=True)
class SubagentStart:
    """サブエージェントの開始。種類・説明・モデルは meta.json から（無ければ空）。"""

    agent_id: str
    agent_type: str
    description: str
    model: str


@dataclass(frozen=True)
class SubagentEnd:
    """サブエージェントの終わり（meta.json の finished が true になった）。"""

    agent_id: str


Event = Union[Prompt, Tool, Reply, TurnEnd, SubagentStart, SubagentEnd]


# ---- tmux ----


class TmuxControl:
    """tmux のセッションの操作。失敗は例外にせず、last_error に残して False を返す。"""

    def __init__(
        self,
        session: str = DEFAULT_SESSION,
        workdir: str = DEFAULT_WORKDIR,
        claude_cmd: str = "claude",
        tmux: str = "tmux",
        run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        """セッション名・作業フォルダ・起動するコマンド・tmux のコマンド・実行する関数（テストで差し替える）を受け取る。"""
        self.session: str = session
        self.workdir: str = workdir
        self.claude_cmd: str = claude_cmd
        self.tmux: str = tmux
        self._run = run
        self.last_error: str = ""

    def _call(self, args: list[str], input_text: str | None = None) -> bool:
        """tmux を1回呼ぶ。戻り値が 0 なら True。失敗なら last_error に標準エラーを残して False。"""
        result = self._run(
            [self.tmux, *args], input=input_text, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            self.last_error = (result.stderr or "").strip() or t("err_tmux_failed", code=result.returncode, args=' '.join(args))
            return False
        self.last_error = ""
        return True

    def exists(self) -> bool:
        """セッションがあれば True。無いのは正常なので、last_error は変えない。"""
        result = self._run(
            [self.tmux, "has-session", "-t", self.session],
            input=None,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def start(self) -> bool:
        """セッションを作り、中で claude_cmd を起動する。画面の大きさは TMUX_COLS×TMUX_ROWS に固定する。

        ほかの tmux につないでいると、-x・-y だけでは、そちらの大きさに合わされる（2026-11-21 実物で 127×26 になった）。
        そのため、このセッションだけ window-size を manual にしてから resize-window する（全体の設定 -g は変えない）。
        大きさの固定に失敗しても、起動できていれば True を返す（窓の表示が崩れるだけで、やりとりはできる）。
        """
        started = self._call(
            [
                "new-session",
                "-d",
                "-s",
                self.session,
                "-x",
                str(TMUX_COLS),
                "-y",
                str(TMUX_ROWS),
                "-c",
                self.workdir,
                self.claude_cmd,
            ]
        )
        if started:
            error = self.last_error
            if self._call(["set-option", "-t", self.session, "window-size", "manual"]):
                self._call(["resize-window", "-t", self.session, "-x", str(TMUX_COLS), "-y", str(TMUX_ROWS)])
            self.last_error = error  # 大きさの固定の失敗は、起動の失敗として残さない
        return started

    def send_keys(self, *keys: str) -> bool:
        """tmux のキー名（"Up"・"Enter"・"Escape"・"Tab"・"BSpace"・"Space" など）を順に送る。"""
        return self._call(["send-keys", "-t", self.session, *keys])

    def send_literal(self, text: str) -> bool:
        """文字をそのまま送る（Enter は付けない）。空なら何もせず True を返す。"""
        if text == "":
            return True
        return self._call(["send-keys", "-t", self.session, "-l", text])

    def send_prompt(self, text: str) -> bool:
        """text を貼り付けて Enter で送る。改行を含んでも途中で送信されないよう、bracketed paste を使う。

        空白だけの text は何もしない（True を返す）。
        """
        if text.strip() == "":
            return True
        if not self._call(["load-buffer", "-b", PASTE_BUFFER, "-"], input_text=text):
            return False
        if not self._call(["paste-buffer", "-p", "-d", "-b", PASTE_BUFFER, "-t", self.session]):
            return False
        return self._call(["send-keys", "-t", self.session, "Enter"])

    def send_escape(self) -> bool:
        """Escape を送る（claude の作業の中断に使う）。"""
        return self._call(["send-keys", "-t", self.session, "Escape"])

    def stop(self) -> None:
        """セッションを閉じる。無ければ何もしない。"""
        if not self.exists():
            return
        self._call(["kill-session", "-t", self.session])

    def capture(self) -> str | None:
        """画面の文字（tmux capture-pane -p の標準出力）。失敗なら None（last_error は変えない）。"""
        result = self._run(
            [self.tmux, "capture-pane", "-p", "-t", self.session],
            input=None,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout or ""


# ---- 会話の記録の場所 ----


def project_log_dir(workdir: str) -> Path:
    """作業フォルダの会話の記録の置き場所（~/.claude/projects/<名前>）。

    名前は絶対パスの英数字以外（/ _ . など）をすべて - に置き換えたもの。
    例：/home/user/projects/pyxel → -home-user-projects-pyxel
    例：/home/user/projects/work/sandbox → -home-user-projects-work-sandbox
    """
    absolute = str(Path(workdir).absolute())
    name = re.sub(r"[^A-Za-z0-9]", "-", absolute)
    return Path.home() / ".claude" / "projects" / name


# ---- 会話の記録を読む ----


def _tool_summary(tool_input: object) -> str:
    """道具の入力から要約を作る。description・command・file_path・pattern・prompt の最初に見つかったもの（60 文字まで）。無ければ空。"""
    if not isinstance(tool_input, dict):
        return ""
    for key in TOOL_SUMMARY_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value[:SUMMARY_MAX]
    return ""


def _text_field(meta: dict, key: str) -> str:
    """meta の項目を文字列で返す。無い・文字列でないときは空。"""
    value = meta.get(key)
    return value if isinstance(value, str) else ""


# ---- プロンプトの見せ方（会話記録の XML のようなタグを外して読める形にする） ----

_CMD_NAME_RE = re.compile(r"<command-name>(.*?)</command-name>", re.DOTALL)  # スラッシュコマンドの名前
_CMD_ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)  # スラッシュコマンドの引数
_LOCAL_OUT_RE = re.compile(r"<local-command-(stdout|stderr)>(.*?)</local-command-\1>", re.DOTALL)  # ローカルコマンドの出力
_TASK_RE = re.compile(r"<task-notification>.*?</task-notification>", re.DOTALL)  # サブエージェントの知らせ
_SUMMARY_RE = re.compile(r"<summary>(.*?)</summary>", re.DOTALL)
_STATUS_RE = re.compile(r"<status>(.*?)</status>", re.DOTALL)
_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9_:-]*/?>")  # <名前>・</名前>・<名前/> の形のタグ（属性なし）


def prompt_display(text: str) -> tuple[str, bool]:
    """プロンプトの文を、画面に見せる形にする。

    戻り値は (見せる文, 決まった形の知らせか)。知らせのときは True（履歴を灰色で出すため）。
    タグが無ければ text をそのまま返し、False を返す。
    """
    name_match = _CMD_NAME_RE.search(text)
    if name_match:
        name = name_match.group(1).strip()
        args_match = _CMD_ARGS_RE.search(text)
        args = args_match.group(1).strip() if args_match else ""
        return (f"{name} {args}" if args else name), True
    outputs = [body.strip() for _, body in _LOCAL_OUT_RE.findall(text)]
    if outputs:
        shown = "\n".join(out for out in outputs if out)
        return (shown if shown else t("notice_no_output")), True
    if _TASK_RE.search(text):
        summary_match = _SUMMARY_RE.search(text)
        status_match = _STATUS_RE.search(text)
        if summary_match and summary_match.group(1).strip():
            return t("notice_prefix") + summary_match.group(1).strip(), True
        if status_match and status_match.group(1).strip():
            return t("notice_prefix") + status_match.group(1).strip(), True
        return t("notice_subagent"), True
    if not _TAG_RE.search(text):
        return text, False
    body = _TAG_RE.sub("", text)
    lines = [line.rstrip() for line in body.split("\n") if line.strip()]  # 空行を詰める
    return "\n".join(lines).strip(), True


def _parse_main_line(session: str, line: str) -> list[Event]:
    """会話の記録の1行を、イベントの一覧にする。JSON でない・知らない種類は空。"""
    try:
        obj = json.loads(line)
    except ValueError:
        return []
    if not isinstance(obj, dict):
        return []
    kind = obj.get("type")
    message = obj.get("message")
    if kind == "user":
        # プロンプトは、文字列の内容で、サイドチェーンでも補助（isMeta）でもないもの
        if obj.get("isSidechain") or obj.get("isMeta"):
            return []
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if isinstance(content, str):
            return [Prompt(session, content)]
        return []  # 内容がリスト（道具の結果など）はプロンプトではない
    if kind == "assistant":
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if not isinstance(content, list):
            return []
        events: list[Event] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "tool_use":
                name = block.get("name")
                events.append(Tool(session, name if isinstance(name, str) else "", _tool_summary(block.get("input"))))
            elif block_type == "text":
                text = block.get("text")
                if isinstance(text, str):
                    events.append(Reply(session, text))
            # thinking などは無視する
        return events
    if kind == "system" and obj.get("subtype") == "turn_duration":
        return [TurnEnd(session)]
    return []  # attachment・api-request・queue-operation・mode など、ほかの種類は無視する


class LogReader:
    """会話の記録の、追記された分だけを読んでイベントにする。

    since より前に更新された、初めて見るファイルは無視する（その時点の末尾から読むので、後の追記は拾う）。
    since 以降に作られた・更新されたファイルは先頭から読む。
    """

    def __init__(self, log_dir: Path, since: float, skip_existing: bool = False) -> None:
        """会話の記録のフォルダと、この時刻（UNIX 秒）より後に更新されたファイルだけを対象にする時刻を受け取る。

        skip_existing が True（つなぐとき）：作った時点で既にあるファイルは、mtime に関係なく今の末尾から読む。
        既存のサブエージェントは既知として覚え、開始も終わりも出さない。
        skip_existing が False：mtime が since より前のファイルだけ、今の末尾から読む（それ以外は先頭から）。
        """
        self.log_dir: Path = log_dir
        self.since: float = since
        self._pos: dict[Path, int] = {}  # ファイルごとに読んだ位置（バイト）
        self._tail: dict[Path, bytes] = {}  # 改行で終わっていない最後の切れ端（次の feed でつなぐ）
        self._meta_seen: set[Path] = set()  # 初めて見た meta.json
        self._skipped_meta: set[Path] = set()  # since より前に更新されたので無視している meta.json
        self._agents: set[str] = set()  # 開始を出したサブエージェントの番号
        self._ended: set[str] = set()  # 終わりを出したサブエージェントの番号
        if skip_existing:
            self._scan_existing()
        else:
            self._scan_old_only()

    def _scan_old_only(self) -> None:
        """mtime が since より前のファイルだけ、今の末尾から読む（サブエージェントは開始を出さない）。log_dir が無ければ何もしない。"""
        if not self.log_dir.is_dir():
            return
        for path in self.log_dir.glob("*.jsonl"):
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_mtime < self.since:
                self._pos[path] = st.st_size
                self._tail[path] = b""
        for path in self.log_dir.glob("*/subagents/agent-*.jsonl"):
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_mtime < self.since:
                self._pos[path] = 0
        for path in self.log_dir.glob("*/subagents/agent-*.meta.json"):
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_mtime < self.since:
                self._meta_seen.add(path)
                self._skipped_meta.add(path)

    def _scan_existing(self) -> None:
        """作った時点で既にあるファイルは、mtime に関係なく今の末尾から読む（古い会話は流し直さない）。

        サブエージェントの jsonl と meta.json は、既知として覚えるだけで、開始も終わりも出さない。
        since は、このあと初めて現れたファイルにだけ使う。log_dir が無ければ何もしない。
        """
        if not self.log_dir.is_dir():
            return
        for path in self.log_dir.glob("*.jsonl"):
            try:
                st = path.stat()
            except OSError:
                continue
            self._pos[path] = st.st_size  # 今の末尾から読む（後から追記された分だけ拾う）
            self._tail[path] = b""
        for path in self.log_dir.glob("*/subagents/agent-*.jsonl"):
            self._pos[path] = 0  # 既知（_feed_sub は開始を出さない）
            self._agents.add(path.stem[len(SUBAGENT_PREFIX):])
        for path in self.log_dir.glob("*/subagents/agent-*.meta.json"):
            agent_id = path.name[len(SUBAGENT_PREFIX): -len(".meta.json")]
            self._meta_seen.add(path)
            self._skipped_meta.add(path)  # 読まない（開始も終わりも出さない）
            self._agents.add(agent_id)
            self._ended.add(agent_id)

    def feed(self, path: Path) -> list[Event]:
        """path のファイルの、前回の位置から末尾までを読み、イベントの一覧にする。読めない・消えたファイルは空。"""
        kind = self._kind(path)
        if kind is None:
            return []
        try:
            st = path.stat()
        except OSError:
            return []
        if kind == "main":
            return self._feed_main(path, st)
        if kind == "sub":
            return self._feed_sub(path, st)
        return self._feed_meta(path, st)

    def _kind(self, path: Path) -> str | None:
        """ファイルの種類。"main"（会話の本体）・"sub"（サブエージェントの jsonl）・"meta"（meta.json）・None（対象外）。"""
        if path.suffix == ".jsonl" and path.parent == self.log_dir:
            return "main"
        if path.parent.name == "subagents" and path.parent.parent.parent == self.log_dir:
            if not path.name.startswith(SUBAGENT_PREFIX):
                return None
            if path.name.endswith(".meta.json"):
                return "meta"
            if path.suffix == ".jsonl":
                return "sub"
        return None

    def _feed_main(self, path: Path, st) -> list[Event]:
        """会話の本体（log_dir 直下の jsonl）の追記分を読む。"""
        if path not in self._pos:
            old = st.st_mtime < self.since
            self._pos[path] = st.st_size if old else 0  # 古いファイルは末尾から読む
            self._tail[path] = b""
        session = path.stem
        events: list[Event] = []
        for line in self._read_new_lines(path, st):
            events.extend(_parse_main_line(session, line))
        return events

    def _read_new_lines(self, path: Path, st) -> list[str]:
        """前回の位置から末尾までを読み、完全な行だけを返す。途中までの行は次の feed に回す。"""
        pos = self._pos.get(path, 0)
        if st.st_size < pos:  # 小さくなった（作り直された）。先頭から読む
            pos = 0
            self._tail[path] = b""
        try:
            with path.open("rb") as f:
                f.seek(pos)
                data = f.read(max(0, st.st_size - pos))
        except OSError:
            return []
        self._pos[path] = pos + len(data)
        parts = (self._tail.get(path, b"") + data).split(b"\n")
        self._tail[path] = parts.pop()  # 改行で終わっていない最後の切れ端
        return [p.decode("utf-8", errors="replace") for p in parts if p]

    def _feed_sub(self, path: Path, st) -> list[Event]:
        """サブエージェントの jsonl。初めて見たときだけ開始を出す。中身の行はイベントにしない。"""
        if path in self._pos:
            return []
        self._pos[path] = 0
        if st.st_mtime < self.since:
            return []  # 起動前に更新された古いもの
        agent_id = path.stem[len(SUBAGENT_PREFIX):]
        meta = self._read_meta(path.with_name(path.stem + ".meta.json"))
        return self._emit_start(agent_id, meta)

    def _feed_meta(self, path: Path, st) -> list[Event]:
        """meta.json。読むたびに全体を読み直す。finished が true になったら終わりを1回だけ出す。"""
        if path in self._skipped_meta:
            if st.st_mtime < self.since:
                return []
            self._skipped_meta.discard(path)  # 後で更新されたので読む
        elif path not in self._meta_seen:
            self._meta_seen.add(path)
            if st.st_mtime < self.since:
                self._skipped_meta.add(path)
                return []
        agent_id = path.name[len(SUBAGENT_PREFIX): -len(".meta.json")]
        meta = self._read_meta(path)
        if not meta:
            return []
        events = self._emit_start(agent_id, meta)
        if meta.get("finished") is True and agent_id not in self._ended:
            self._ended.add(agent_id)
            events.append(SubagentEnd(agent_id))
        return events

    def _emit_start(self, agent_id: str, meta: dict) -> list[Event]:
        """まだ開始を出していないサブエージェントなら、開始のイベントを1つ返す（重複させない）。"""
        if agent_id in self._agents:
            return []
        self._agents.add(agent_id)
        return [
            SubagentStart(
                agent_id,
                _text_field(meta, "agentType"),
                _text_field(meta, "description"),
                _text_field(meta, "model"),
            )
        ]

    @staticmethod
    def _read_meta(path: Path) -> dict:
        """meta.json を読む。無い・壊れている・辞書でないときは空の辞書。"""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}


# ---- 見張り（別スレッド） ----


class LogWatcher:
    """会話の記録の書き込みを、inotifywait の標準出力で知らせる。読みは poll から行う（描画のループを止めない）。"""

    def __init__(
        self,
        log_dir: Path,
        reader: LogReader,
        inotify_cmd: list[str] | None = None,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    ) -> None:
        """会話の記録のフォルダ・読む人・見張りのコマンド（省略時は inotifywait）・プロセスを作る関数（テストで差し替える）を受け取る。"""
        self.log_dir: Path = log_dir
        self.reader: LogReader = reader
        self._inotify_cmd: list[str] | None = inotify_cmd
        self._popen = popen
        self._queue: queue.Queue[Path] = queue.Queue()
        self._pending: deque[Event] = deque()
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self.last_error: str = ""

    def _command(self) -> list[str]:
        """見張りのコマンド。log_dir が無ければ、作らずに親（~/.claude/projects）を見張る。"""
        if self._inotify_cmd is not None:
            return list(self._inotify_cmd)
        watch = self.log_dir if self.log_dir.is_dir() else self.log_dir.parent
        return ["inotifywait", "-m", "-r", "-q", "-e", "create,modify,moved_to", "--format", "%w%f", str(watch)]

    def start(self) -> None:
        """見張りのプロセスを始め、標準出力を読むスレッドを動かす。失敗したら last_error に残す。"""
        if self._proc is not None:
            return
        try:
            self._proc = self._popen(
                self._command(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
        except OSError as error:
            self._proc = None
            self.last_error = t("err_watch_failed", error=error)
            return
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        """標準出力を1行ずつ読み、log_dir の下のパスを queue に入れる。"""
        proc = self._proc
        stdout = proc.stdout if proc is not None else None
        if stdout is None:
            return
        try:
            for line in stdout:
                text = line.rstrip("\n")
                if not text:
                    continue
                path = Path(text)
                if path.is_relative_to(self.log_dir):
                    self._queue.put(path)
        except (OSError, ValueError):
            return

    def poll(self, max_events: int = 200) -> list[Event]:
        """たまったイベントを最大 max_events 個返す（ブロックしない）。同じパスは1回にまとめて読む。残りは次の poll へ。"""
        paths: dict[Path, None] = {}
        while True:
            try:
                paths[self._queue.get_nowait()] = None
            except queue.Empty:
                break
        for path in paths:
            self._pending.extend(self.reader.feed(path))
        out: list[Event] = []
        while self._pending and len(out) < max_events:
            out.append(self._pending.popleft())
        return out

    def stop(self) -> None:
        """見張りのプロセスを止め、スレッドを終わらせる。動いていなければ何もしない。"""
        proc = self._proc
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    proc.kill()
                except OSError:
                    pass
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        self._proc = None
        self._thread = None


# ---- まとめ役 ----


class Bridge:
    """tmux と見張りをまとめて、画面の側から使う窓口。"""

    def __init__(
        self,
        workdir: str,
        session: str = DEFAULT_SESSION,
        tmux: TmuxControl | None = None,
        watcher_factory: Callable[[Path, LogReader], LogWatcher] | None = None,
        clock: Callable[[], float] = time.time,
        claude_cmd: str = "claude",
    ) -> None:
        """作業フォルダとセッション名を受け取る。tmux・見張りの作り方・時計は、テストで差し替えられる。
        claude_cmd は tmux の中で起動するコマンド（許可の hook を --settings で渡すときに使う）。"""
        self.workdir: str = workdir
        self.session: str = session
        self.tmux: TmuxControl = (
            tmux if tmux is not None else TmuxControl(session=session, workdir=workdir, claude_cmd=claude_cmd)
        )
        self.log_dir: Path = project_log_dir(workdir)
        self._factory: Callable[[Path, LogReader], LogWatcher] = (
            watcher_factory if watcher_factory is not None else (lambda log_dir, reader: LogWatcher(log_dir, reader))
        )
        self._clock: Callable[[], float] = clock
        self.reader: LogReader | None = None
        self.watcher: LogWatcher | None = None

    def session_exists(self) -> bool:
        """セッションがあるか。"""
        return self.tmux.exists()

    def begin(self, mode: str) -> bool:
        """mode は "new"（無ければ作る）・"resume"（あるものにつなぐ。無ければ False）・"restart"（あれば閉じてから作る）。見張りもここで始める。

        見張りは、new と restart では2秒前から、resume では10分前から更新されたファイルを対象にする。
        """
        if mode not in ("new", "resume", "restart"):
            raise ValueError(t("err_bridge_mode", value=repr(mode)))
        self.end(kill_session=False)  # 前の見張りが残っていれば止める
        if mode == "restart":
            if self.tmux.exists():
                self.tmux.stop()
            if not self.tmux.start():
                return False
        elif mode == "new":
            if not self.tmux.exists() and not self.tmux.start():
                return False
        else:  # resume
            if not self.tmux.exists():
                self.tmux.last_error = t("err_no_session")
                return False
        lookback = RESUME_LOOKBACK_SEC if mode == "resume" else SINCE_MARGIN_SEC
        since = self._clock() - lookback
        self.reader = LogReader(self.log_dir, since, skip_existing=(mode == "resume"))
        self.watcher = self._factory(self.log_dir, self.reader)
        self.watcher.start()
        return True

    def send_prompt(self, text: str) -> bool:
        """プロンプトを claude に送る。"""
        return self.tmux.send_prompt(text)

    def send_escape(self) -> bool:
        """Escape を送る（中断）。"""
        return self.tmux.send_escape()

    def send_keys(self, *keys: str) -> bool:
        """tmux のキー名を順に送る（コマンドの窓のパネル操作に使う）。"""
        return self.tmux.send_keys(*keys)

    def send_literal(self, text: str) -> bool:
        """文字をそのまま送る（Enter は付けない）。"""
        return self.tmux.send_literal(text)

    def permission_screen_open(self) -> bool:
        """tmux の画面に許可の画面（"Do you want to" と "Esc to cancel" の両方）が出ているか。調べられなければ False。"""
        text = self.tmux.capture()
        if text is None:
            return False
        # Claude Code の画面（会話記録）が英語で出ることを前提にしている。Claude Code の language 設定で変わるのは返事の言語だけ（2.1.330 で確認）。画面が翻訳される版が出たら、ここを直す
        return "Do you want to" in text and "Esc to cancel" in text

    def poll(self) -> list[Event]:
        """見張りのたまったイベントを返す。見張りが無ければ空。"""
        if self.watcher is None:
            return []
        return self.watcher.poll()

    def end(self, kill_session: bool) -> None:
        """見張りを止める。kill_session なら tmux のセッションも閉じる。"""
        if self.watcher is not None:
            self.watcher.stop()
        self.watcher = None
        self.reader = None
        if kill_session:
            self.tmux.stop()
