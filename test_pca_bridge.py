"""pca_bridge.py（Claude Code とつなぐ部品）のテスト。

実行: .venv/bin/python test_pca_bridge.py
偽の run／popen と一時フォルダを使い、本物の tmux・inotifywait・claude は起動しない。
一時フォルダは消さずに、実行ごとに新しい名前（時刻つき）で作る。
"""
import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pca_bridge as B
from pca_i18n import set_lang, get_lang

set_lang("ja")  # 日本語の文を期待するテストが多いので、最初に ja を明示する

fail: list[str] = []
n_checks = 0

# 一時フォルダ（実行ごとに新しい名前。消さない）。既定はこのファイルと同じフォルダの .test_tmp/（環境変数 PCA_BRIDGE_TEST_TMP があればそれを使う）
TMP_ROOT = Path(os.environ.get(
    "PCA_BRIDGE_TEST_TMP",
    str(Path(__file__).resolve().parent / ".test_tmp")))
RUN_DIR = TMP_ROOT / f"run_{int(time.time() * 1000)}_{os.getpid()}"
RUN_DIR.mkdir(parents=True, exist_ok=True)
_dir_no = [0]


def new_dir(name: str = "d") -> Path:
    """この実行専用の新しい空のフォルダを作って返す。"""
    _dir_no[0] += 1
    p = RUN_DIR / f"{name}{_dir_no[0]}"
    p.mkdir(parents=True)
    return p


def check(c, msg):
    global n_checks
    n_checks += 1
    if not c:
        fail.append(msg)
        print("NG:", msg)


def jline(o) -> str:
    return json.dumps(o, ensure_ascii=False) + "\n"


def types(events) -> list[str]:
    return [type(e).__name__ for e in events]


def set_mtime(path: Path, t: float) -> None:
    os.utime(path, (t, t))


# ---------------------------------------------------------------------------
# 1. TmuxControl
# ---------------------------------------------------------------------------
class FakeRun:
    """tmux の代わり。呼ばれた記録を残し、セッションの有無と、失敗させるコマンドを持つ。"""

    def __init__(self):
        self.calls: list[tuple[list[str], str | None, dict]] = []
        self.session = False
        self.fail: dict[str, tuple[int, str]] = {}  # サブコマンド名 → (戻り値, 標準エラー)

    def __call__(self, cmd, input=None, **kw):
        self.calls.append((list(cmd), input, kw))
        sub = cmd[1] if len(cmd) > 1 else ""
        if sub in self.fail:
            code, err = self.fail[sub]
            return subprocess.CompletedProcess(cmd, code, "", err)
        if sub == "has-session":
            return subprocess.CompletedProcess(cmd, 0 if self.session else 1, "", "")
        if sub == "new-session":
            self.session = True
        if sub == "kill-session":
            self.session = False
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def cmds(self) -> list[list[str]]:
        return [c[0] for c in self.calls]

    def subs(self) -> list[str]:
        return [c[0][1] for c in self.calls]


fr = FakeRun()
tm = B.TmuxControl(session="S1", workdir="/w/d", claude_cmd="claude --x", tmux="tmux", run=fr)
# 1-1 exists：has-session の形、戻り値 0 で True
check(tm.exists() is False, "1: セッションが無いとき exists は False")
check(fr.cmds()[-1] == ["tmux", "has-session", "-t", "S1"], f"1: has-session のコマンド {fr.cmds()[-1]}")
fr.session = True
check(tm.exists() is True, "1: セッションがあるとき exists は True")
# exists の呼び方（run に渡す引数）
k = fr.calls[-1][2]
check(k.get("capture_output") is True and k.get("text") is True and k.get("check") is False,
      f"1: run の呼び方が capture_output=True,text=True,check=False でない {k}")
# 1-2 exists は last_error を変えない
tm.last_error = "前の失敗"
fr.session = False
tm.exists()
check(tm.last_error == "前の失敗", "1: exists が last_error を書き換えた")
tm.last_error = ""

# 1-3 start
fr.calls.clear()
check(tm.start() is True, "1: start 成功で True")
check(fr.cmds() == [
    ["tmux", "new-session", "-d", "-s", "S1", "-x", "98", "-y", "40", "-c", "/w/d", "claude --x"],
    ["tmux", "set-option", "-t", "S1", "window-size", "manual"],
    ["tmux", "resize-window", "-t", "S1", "-x", "98", "-y", "40"],
], f"1: new-session のあとに window-size manual と resize-window が続く {fr.cmds()}")
check(B.TMUX_COLS == 98 and B.TMUX_ROWS == 40, "1: 画面の大きさの定数は 98×40")
check(fr.session is True, "1: start のあと偽のセッションができる")

# 1-4 send_prompt：順番・引数・入力
fr.calls.clear()
text = "1行目\n2行目\n"
check(tm.send_prompt(text) is True, "1: send_prompt 成功で True")
check(fr.cmds() == [
    ["tmux", "load-buffer", "-b", "pca", "-"],
    ["tmux", "paste-buffer", "-p", "-d", "-b", "pca", "-t", "S1"],
    ["tmux", "send-keys", "-t", "S1", "Enter"],
], f"1: send_prompt のコマンドの順番 {fr.cmds()}")
check(fr.calls[0][1] == text, f"1: load-buffer に渡す標準入力が text そのまま（改行・末尾の改行も）でない {fr.calls[0][1]!r}")
check(fr.calls[1][1] is None and fr.calls[2][1] is None, "1: load-buffer 以外は標準入力を渡さない")
check(all(c[2].get("capture_output") is True and c[2].get("text") is True and c[2].get("check") is False for c in fr.calls),
      "1: send_prompt の run の引数が capture_output=True,text=True,check=False でない")
# 前後に空白のある文字は切らずに送る
fr.calls.clear()
tm.send_prompt("  hi  ")
check(fr.calls[0][1] == "  hi  ", "1: 前後に空白がある text を切って送った")

# 1-5 空白だけは何もしない（True）
for blank in ("", " ", "   ", "\n", "\n\n", "\t \n", "　", "　 \n"):
    fr.calls.clear()
    r = tm.send_prompt(blank)
    check(r is True and fr.calls == [], f"1: 空白だけ {blank!r} のとき何もしない／True でない（呼び出し {len(fr.calls)} 回）")

# 1-6 send_escape
fr.calls.clear()
check(tm.send_escape() is True and fr.cmds() == [["tmux", "send-keys", "-t", "S1", "Escape"]],
      f"1: send_escape のコマンド {fr.cmds()}")

# 1-7 失敗：例外にせず last_error と False。途中で失敗したらあとのコマンドは呼ばない
for failing, rest in (("load-buffer", ["load-buffer"]),
                      ("paste-buffer", ["load-buffer", "paste-buffer"]),
                      ("send-keys", ["load-buffer", "paste-buffer", "send-keys"])):
    fr2 = FakeRun()
    fr2.fail[failing] = (1, "エラー " + failing + "\n")
    t2 = B.TmuxControl(run=fr2)
    r = t2.send_prompt("x")
    check(r is False, f"1: {failing} 失敗で send_prompt が False でない")
    check(t2.last_error == "エラー " + failing, f"1: {failing} 失敗の last_error {t2.last_error!r}")
    check(fr2.subs() == rest, f"1: {failing} 失敗のあとに余計なコマンドを呼んだ {fr2.subs()}")
# 標準エラーが空なら代わりの文が入る（空のままにしない）
fr2 = FakeRun()
fr2.fail["send-keys"] = (2, "")
t2 = B.TmuxControl(run=fr2)
check(t2.send_escape() is False and t2.last_error != "", f"1: 標準エラーが空のとき last_error が空 {t2.last_error!r}")
check(t2.start() is True and t2.last_error == "", "1: 成功すると last_error が空に戻る")
fr2.fail["new-session"] = (1, "duplicate session")
check(t2.start() is False and t2.last_error == "duplicate session", f"1: start 失敗 {t2.last_error!r}")
# stderr が None でも落ちない
fr3 = FakeRun()


def run_none_err(cmd, input=None, **kw):
    return subprocess.CompletedProcess(cmd, 1, None, None)


t3 = B.TmuxControl(run=run_none_err)
check(t3.send_escape() is False and isinstance(t3.last_error, str), "1: stderr が None でも落ちない")

# 1-8 stop：無ければ has-session だけ。あれば kill-session
fr4 = FakeRun()
t4 = B.TmuxControl(session="S4", run=fr4)
t4.stop()
check(fr4.subs() == ["has-session"], f"1: セッションが無いときの stop は kill しない {fr4.subs()}")
fr4.session = True
fr4.calls.clear()
t4.stop()
check(fr4.subs() == ["has-session", "kill-session"] and fr4.cmds()[1] == ["tmux", "kill-session", "-t", "S4"],
      f"1: stop の kill-session {fr4.cmds()}")
check(fr4.session is False, "1: stop のあとセッションが無い")
fr4.session = True
fr4.fail["kill-session"] = (1, "kill 失敗")
try:
    t4.stop()
    check(t4.last_error == "kill 失敗", f"1: kill 失敗の last_error {t4.last_error!r}")
except Exception as e:  # noqa: BLE001
    check(False, f"1: stop の失敗が例外になった {e!r}")

# 1-9 tmux のコマンド名・既定値を差し替えられる
fr5 = FakeRun()
t5 = B.TmuxControl(tmux="/opt/tmux", run=fr5)
t5.exists()
check(fr5.cmds()[0][0] == "/opt/tmux", "1: tmux のコマンド名を差し替えられない")
check(t5.session == B.DEFAULT_SESSION == "pyxelcube_agents", "1: 既定のセッション名")

# ---------------------------------------------------------------------------
# 2. project_log_dir
# ---------------------------------------------------------------------------
base = Path.home() / ".claude" / "projects"
cases = {
    "/home/user/projects/pyxel": "-home-user-projects-pyxel",
    "/home/user/projects/work/sandbox": "-home-user-projects-work-sandbox",
    "/home/a/b_c": "-home-a-b-c",  # _ も - になる（英数字以外はすべて -）
    "/home/a/.venv-cube/x.y": "-home-a--venv-cube-x-y",  # . も -
    "/home/a/b c": "-home-a-b-c",  # 空白も -
    "/": "-",
    "/home/a/日本語/z": "-home-a-----z",  # 英数字でない文字は 1 文字ごとに -
}
for src, want in cases.items():
    got = B.project_log_dir(src)
    check(got.name == want, f"2: project_log_dir({src!r}) = {got.name!r}（期待 {want!r}）")
    check(got.parent == base, f"2: project_log_dir({src!r}) の親が ~/.claude/projects でない {got.parent}")
check(B.project_log_dir("/home/a/b/").name == "-home-a-b", f"2: 末尾の / {B.project_log_dir('/home/a/b/').name}")
rel = B.project_log_dir("some/rel")
want_rel = "".join(c if c.isascii() and c.isalnum() else "-" for c in str(Path("some/rel").absolute()))
check(rel.name == want_rel and rel.name.startswith("-"), f"2: 相対パスは絶対パスにしてから変える {rel.name!r}")
check(isinstance(B.project_log_dir("/x"), Path), "2: 戻り値は Path")

# ---------------------------------------------------------------------------
# 3. LogReader
# ---------------------------------------------------------------------------
# 3-1 各イベント
d = new_dir("reader")
main = d / "sess1.jsonl"
main.write_text("", encoding="utf-8")
rd = B.LogReader(d, since=0)
check(rd.feed(main) == [], "3: 空のファイルは何も返さない")
lines = [
    jline({"type": "user", "message": {"content": "こんにちは"}, "isSidechain": False}),
    jline({"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "考え"}, {"type": "text", "text": "はい"}]}}),
    jline({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}], "stop_reason": "tool_use"}}),
    jline({"type": "system", "subtype": "turn_duration", "durationMs": 100}),
]
with main.open("a", encoding="utf-8") as f:
    f.write("".join(lines))
ev = rd.feed(main)
check(ev == [B.Prompt("sess1", "こんにちは"), B.Reply("sess1", "はい"), B.Tool("sess1", "Bash", "ls"), B.TurnEnd("sess1")],
      f"3: 基本の4種のイベント {ev}")
check(rd.feed(main) == [], "3: 追記が無ければ何も返さない（二重に読まない）")

# 3-2 1 つの assistant メッセージに複数のブロック：順番どおり。thinking は無視
d = new_dir("reader")
p = d / "s.jsonl"
p.write_text(jline({"type": "assistant", "message": {"content": [
    {"type": "text", "text": "A"},
    {"type": "thinking", "thinking": "T"},
    {"type": "tool_use", "name": "Read", "input": {"file_path": "/x"}},
    {"type": "tool_use", "name": "Edit", "input": {}},
    {"type": "text", "text": "B"},
    {"type": "image"},
    "文字列のブロック",
]}}), encoding="utf-8")
ev = B.LogReader(d, 0).feed(p)
check(ev == [B.Reply("s", "A"), B.Tool("s", "Read", "/x"), B.Tool("s", "Edit", ""), B.Reply("s", "B")],
      f"3: 複数ブロックの順番・thinking の無視・要約なし {ev}")

# 3-3 道具の要約：優先順位・60 文字・文字列以外は飛ばす
def tool_summary(inp) -> str:
    d_ = new_dir("sum")
    p_ = d_ / "s.jsonl"
    p_.write_text(jline({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "T", "input": inp}]}}), encoding="utf-8")
    evs = B.LogReader(d_, 0).feed(p_)
    return evs[0].summary if evs and isinstance(evs[0], B.Tool) else "<なし>"


check(tool_summary({"prompt": "p", "pattern": "pa", "file_path": "f", "command": "c", "description": "d"}) == "d", "3: 要約は description が先")
check(tool_summary({"prompt": "p", "pattern": "pa", "file_path": "f", "command": "c"}) == "c", "3: description が無ければ command")
check(tool_summary({"prompt": "p", "pattern": "pa", "file_path": "f"}) == "f", "3: command が無ければ file_path")
check(tool_summary({"prompt": "p", "pattern": "pa"}) == "pa", "3: file_path が無ければ pattern")
check(tool_summary({"prompt": "p"}) == "p", "3: pattern が無ければ prompt")
check(tool_summary({"other": "x"}) == "", "3: 該当の項目が無ければ空")
check(tool_summary({}) == "", "3: input が空なら空")
check(tool_summary({"description": "", "command": "c"}) == "c", "3: 空の description は飛ばす")
check(tool_summary({"description": 5, "command": "c"}) == "c", "3: 文字列でない description は飛ばす")
check(tool_summary({"description": "x" * 100}) == "x" * 60, "3: 60 文字で切る")
check(tool_summary({"description": "あ" * 61}) == "あ" * 60, "3: 60 文字（バイトではなく文字）で切る")
check(tool_summary({"description": "y" * 60}) == "y" * 60, "3: ちょうど 60 文字はそのまま")
d_ = new_dir("sum")
p_ = d_ / "s.jsonl"
p_.write_text(jline({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "T", "input": "文字列"}, {"type": "tool_use", "input": {"command": "c"}}]}}), encoding="utf-8")
evs = B.LogReader(d_, 0).feed(p_)
check(evs == [B.Tool("s", "T", ""), B.Tool("s", "", "c")], f"3: input が辞書でない・name が無い {evs}")

# 3-4 プロンプトにならない user の行
d = new_dir("reader")
p = d / "s.jsonl"
p.write_text("".join([
    jline({"type": "user", "message": {"content": "メタ"}, "isMeta": True}),
    jline({"type": "user", "message": {"content": "サイド"}, "isSidechain": True}),
    jline({"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}}),
    jline({"type": "user", "message": {"content": [{"type": "text", "text": "リストの文字"}]}}),
    jline({"type": "user", "message": "文字列のメッセージ"}),
    jline({"type": "user"}),
    jline({"type": "user", "message": {"content": "isMeta false"}, "isMeta": False}),
    jline({"type": "user", "message": {"content": ""}}),
    jline({"type": "user", "message": {"content": "メタなし"}}),
]), encoding="utf-8")
ev = B.LogReader(d, 0).feed(p)
check(ev == [B.Prompt("s", "isMeta false"), B.Prompt("s", ""), B.Prompt("s", "メタなし")],
      f"3: isMeta・サイドチェーン・リスト内容は Prompt にしない {ev}")

# 3-5 無視する種類・壊れた行
d = new_dir("reader")
p = d / "s.jsonl"
p.write_text("".join([
    jline({"type": "attachment"}),
    jline({"type": "api-request"}),
    jline({"type": "queue-operation"}),
    jline({"type": "mode"}),
    jline({"type": "system", "subtype": "other"}),
    jline({"type": "system"}),
    jline({"nothing": 1}),
    jline([1, 2, 3]),
    jline("文字列"),
    jline(None),
    jline(123),
    "これは JSON ではない\n",
    "{\"type\": \"user\", \"message\": {\"content\": \"途\n",  # 壊れた行（改行で終わっている）
    "\n",  # 空行
    "\n\n",
    jline({"type": "assistant", "message": "文字列"}),
    jline({"type": "assistant", "message": {"content": "文字列"}}),
    jline({"type": "assistant", "message": {"content": [{"type": "text", "text": 5}]}}),
    jline({"type": "assistant"}),
    jline({"type": "user", "message": {"content": "最後の正常な行"}}),
]), encoding="utf-8")
ev = B.LogReader(d, 0).feed(p)
check(ev == [B.Prompt("s", "最後の正常な行")], f"3: 無視する種類・壊れた行のあとも正常な行を読む {ev}")
# 壊れたバイト列（UTF-8 でない）でも落ちない
p2 = d / "bin.jsonl"
p2.write_bytes(b'\xff\xfe\x00 broken\n' + jline({"type": "user", "message": {"content": "OK"}}).encode("utf-8"))
try:
    ev = B.LogReader(d, 0).feed(p2)
    check(ev == [B.Prompt("bin", "OK")], f"3: UTF-8 でないバイトの行のあとも読める {ev}")
except Exception as e:  # noqa: BLE001
    check(False, f"3: UTF-8 でないバイトで落ちた {e!r}")
# 日本語の文字が切れ端の境目で割れても、つなげば読める
d = new_dir("reader")
p = d / "s.jsonl"
full = jline({"type": "assistant", "message": {"content": [{"type": "text", "text": "日本語のへんじ"}]}}).encode("utf-8")
cut = full.index("本".encode("utf-8")) + 1  # 「本」の途中（3 バイトの 1 バイト目の後）
rd = B.LogReader(d, 0)
p.write_bytes(full[:cut])
check(rd.feed(p) == [], "3: 文字の途中で切れた行は返さない")
with p.open("ab") as f:
    f.write(full[cut:])
ev = rd.feed(p)
check(ev == [B.Reply("s", "日本語のへんじ")], f"3: 文字の途中で割れた切れ端がつながる {ev}")

# 3-6 切れ端（改行で終わっていない最後の行）を次の feed でつなぐ
d = new_dir("reader")
p = d / "s.jsonl"
rd = B.LogReader(d, 0)
line1 = jline({"type": "user", "message": {"content": "ひとつめ"}})
line2 = jline({"type": "assistant", "message": {"content": [{"type": "text", "text": "ふたつめ"}]}})
p.write_text(line1 + line2[:20], encoding="utf-8")
ev = rd.feed(p)
check(ev == [B.Prompt("s", "ひとつめ")], f"3: 切れ端は返さない {ev}")
with p.open("a", encoding="utf-8") as f:
    f.write(line2[20:-1])  # 改行の手前まで
check(rd.feed(p) == [], "3: 改行が来るまでは返さない")
with p.open("a", encoding="utf-8") as f:
    f.write("\n" + jline({"type": "system", "subtype": "turn_duration"})[:10])
ev = rd.feed(p)
check(ev == [B.Reply("s", "ふたつめ")], f"3: 改行が来たら前の切れ端とつないで返す {ev}")
with p.open("a", encoding="utf-8") as f:
    f.write(jline({"type": "system", "subtype": "turn_duration"})[10:])
check(rd.feed(p) == [B.TurnEnd("s")], "3: 次の切れ端もつながる")
# 1 バイトずつ追記しても、完全な行ごとに 1 回だけ返す
d = new_dir("reader")
p = d / "s.jsonl"
rd = B.LogReader(d, 0)
body = (jline({"type": "user", "message": {"content": "a"}}) + jline({"type": "user", "message": {"content": "b"}})).encode("utf-8")
got = []
p.write_bytes(b"")
for i in range(len(body)):
    with p.open("ab") as f:
        f.write(body[i:i + 1])
    got.extend(rd.feed(p))
check(got == [B.Prompt("s", "a"), B.Prompt("s", "b")], f"3: 1 バイトずつの追記でも 1 行 1 回 {got}")

# 3-7 ファイルが小さくなったら（作り直し）先頭から読む
d = new_dir("reader")
p = d / "s.jsonl"
p.write_text(jline({"type": "user", "message": {"content": "長い長い長い長い長い長い"}}), encoding="utf-8")
rd = B.LogReader(d, 0)
rd.feed(p)
p.write_text(jline({"type": "user", "message": {"content": "短"}}), encoding="utf-8")
ev = rd.feed(p)
check(ev == [B.Prompt("s", "短")], f"3: 小さくなったファイルは先頭から読み直す {ev}")

# 3-8 対象外・消えた・読めないファイル
d = new_dir("reader")
rd = B.LogReader(d, 0)
check(rd.feed(d / "none.jsonl") == [], "3: 無いファイルは空")
check(rd.feed(Path("/tmp/outside.jsonl")) == [], "3: log_dir の外のファイルは空")
(d / "notes.txt").write_text(jline({"type": "user", "message": {"content": "x"}}), encoding="utf-8")
check(rd.feed(d / "notes.txt") == [], "3: jsonl でないファイルは空")
(d / "sub").mkdir()
(d / "sub" / "deep.jsonl").write_text(jline({"type": "user", "message": {"content": "x"}}), encoding="utf-8")
check(rd.feed(d / "sub" / "deep.jsonl") == [], "3: log_dir の 1 つ下の jsonl（subagents でない）は空")
(d / "s9" / "subagents").mkdir(parents=True)
(d / "s9" / "subagents" / "other.jsonl").write_text("{}\n", encoding="utf-8")
(d / "s9" / "subagents" / "other.meta.json").write_text("{}", encoding="utf-8")
check(rd.feed(d / "s9" / "subagents" / "other.jsonl") == [] and rd.feed(d / "s9" / "subagents" / "other.meta.json") == [],
      "3: subagents の下でも agent- で始まらないファイルは空")
(d / "s9" / "subagents" / "deeper").mkdir()
(d / "s9" / "subagents" / "deeper" / "agent-z.jsonl").write_text("{}\n", encoding="utf-8")
check(rd.feed(d / "s9" / "subagents" / "deeper" / "agent-z.jsonl") == [], "3: subagents のさらに下は空")
(d / "s9" / "subagents" / "agent-q.txt").write_text("{}", encoding="utf-8")
check(rd.feed(d / "s9" / "subagents" / "agent-q.txt") == [], "3: agent- でも jsonl/meta.json でなければ空")
# ディレクトリを渡しても落ちない
try:
    r = rd.feed(d / "s9")
    check(r == [], "3: ディレクトリを feed しても空")
    r = rd.feed(d)
    check(r == [], "3: log_dir 自身を feed しても空")
except Exception as e:  # noqa: BLE001
    check(False, f"3: ディレクトリで落ちた {e!r}")
# jsonl の名前のディレクトリ
(d / "dirlike.jsonl").mkdir()
try:
    check(rd.feed(d / "dirlike.jsonl") == [], "3: jsonl という名前のフォルダは空")
except Exception as e:  # noqa: BLE001
    check(False, f"3: jsonl という名前のフォルダで落ちた {e!r}")

# 3-9 サブエージェント：開始・終わり・重複
d = new_dir("reader")
sub = d / "s1" / "subagents"
sub.mkdir(parents=True)
rd = B.LogReader(d, 0)
meta_a1 = sub / "agent-a1.meta.json"
jl_a1 = sub / "agent-a1.jsonl"
meta_a1.write_text(json.dumps({"agentType": "kakaricho", "description": "肌の色", "model": "sonnet"}), encoding="utf-8")
jl_a1.write_text(jline({"type": "user", "message": {"content": "x"}}), encoding="utf-8")
ev = rd.feed(jl_a1)
check(ev == [B.SubagentStart("a1", "kakaricho", "肌の色", "sonnet")], f"3: サブエージェントの開始（meta から種類・説明・モデル） {ev}")
check(rd.feed(jl_a1) == [], "3: 同じ jsonl をもう一度 feed しても開始は 1 回だけ")
with jl_a1.open("a", encoding="utf-8") as f:
    f.write(jline({"type": "assistant", "message": {"content": [{"type": "text", "text": "中身"}]}}))
check(rd.feed(jl_a1) == [], "3: サブエージェントの jsonl の中身の行はイベントにしない")
check(rd.feed(meta_a1) == [], "3: 開始済みで finished が無い meta は何も返さない（開始の重複なし）")
meta_a1.write_text(json.dumps({"agentType": "kakaricho", "description": "肌の色", "model": "sonnet", "finished": False}), encoding="utf-8")
check(rd.feed(meta_a1) == [], "3: finished が false でも何も返さない")
meta_a1.write_text(json.dumps({"agentType": "kakaricho", "finished": "true"}), encoding="utf-8")
check(rd.feed(meta_a1) == [], "3: finished が文字列 'true' は終わりにしない")
meta_a1.write_text(json.dumps({"agentType": "kakaricho", "finished": True}), encoding="utf-8")
check(rd.feed(meta_a1) == [B.SubagentEnd("a1")], "3: finished が true で SubagentEnd")
check(rd.feed(meta_a1) == [], "3: SubagentEnd は 1 回だけ")
meta_a1.write_text(json.dumps({"agentType": "kakaricho", "finished": True, "x": 1}), encoding="utf-8")
check(rd.feed(meta_a1) == [] and rd.feed(jl_a1) == [], "3: 終わったあと更新されても終わり・開始を重ねない")

# meta が jsonl より先：開始は meta で 1 回、jsonl で重複しない
meta_a2 = sub / "agent-a2.meta.json"
jl_a2 = sub / "agent-a2.jsonl"
meta_a2.write_text(json.dumps({"agentType": "yamada", "description": "検索", "model": "haiku"}), encoding="utf-8")
ev = rd.feed(meta_a2)
check(ev == [B.SubagentStart("a2", "yamada", "検索", "haiku")], f"3: meta が先なら meta で開始を出す {ev}")
jl_a2.write_text("{}\n", encoding="utf-8")
check(rd.feed(jl_a2) == [], "3: meta で開始済みなら jsonl で開始を重ねない")
# meta に finished がすでに true で最初に見たとき：開始と終わりを 1 回ずつ
meta_a3 = sub / "agent-a3.meta.json"
meta_a3.write_text(json.dumps({"agentType": "z", "finished": True}), encoding="utf-8")
ev = rd.feed(meta_a3)
check(ev == [B.SubagentStart("a3", "z", "", ""), B.SubagentEnd("a3")], f"3: 最初から finished の meta は開始→終わり {ev}")
check(rd.feed(meta_a3) == [], "3: そのあとは何も返さない")
# meta が無い jsonl：開始は空の種類・説明・モデル
jl_a4 = sub / "agent-a4.jsonl"
jl_a4.write_text("{}\n", encoding="utf-8")
ev = rd.feed(jl_a4)
check(ev == [B.SubagentStart("a4", "", "", "")], f"3: meta が無い jsonl の開始は空の項目 {ev}")
# 壊れた・辞書でない・読めない meta
for name, content in (("a5", "{壊れ"), ("a6", "[1,2]"), ("a7", '"文字列"'), ("a8", ""), ("a9", "null")):
    m = sub / f"agent-{name}.meta.json"
    m.write_text(content, encoding="utf-8")
    try:
        check(rd.feed(m) == [], f"3: 壊れた meta {content!r} は何も返さず落ちない")
    except Exception as e:  # noqa: BLE001
        check(False, f"3: 壊れた meta {content!r} で落ちた {e!r}")
# 壊れた meta が後で直ったら、開始を出せる
m5 = sub / "agent-a5.meta.json"
m5.write_text(json.dumps({"agentType": "ok", "finished": True}), encoding="utf-8")
ev = rd.feed(m5)
check(ev == [B.SubagentStart("a5", "ok", "", ""), B.SubagentEnd("a5")], f"3: 壊れた meta が直ったら開始と終わり {ev}")
# 項目が文字列でない meta
m10 = sub / "agent-a10.meta.json"
m10.write_text(json.dumps({"agentType": 5, "description": None, "model": ["x"]}), encoding="utf-8")
check(rd.feed(m10) == [B.SubagentStart("a10", "", "", "")], "3: 文字列でない項目は空にする")
# meta が消えた
m11 = sub / "agent-a11.meta.json"
check(rd.feed(m11) == [], "3: 無い meta は空")
# agent_id にハイフンやドットが入っても取り出せる
m12 = sub / "agent-ab-12.x.meta.json"
m12.write_text(json.dumps({"agentType": "t", "finished": True}), encoding="utf-8")
ev = rd.feed(m12)
check(ev and ev[0] == B.SubagentStart("ab-12.x", "t", "", "") and ev[-1] == B.SubagentEnd("ab-12.x"), f"3: agent_id の取り出し {ev}")
# 開始と終わりが重複しない：開始を jsonl で出し、終わりを meta で出し、その後 jsonl が追記されても開始しない
meta_b = sub / "agent-b.meta.json"
jl_b = sub / "agent-b.jsonl"
jl_b.write_text("{}\n", encoding="utf-8")
meta_b.write_text(json.dumps({"agentType": "q", "finished": True}), encoding="utf-8")
allev = rd.feed(jl_b) + rd.feed(meta_b) + rd.feed(jl_b) + rd.feed(meta_b)
check(types(allev) == ["SubagentStart", "SubagentEnd"], f"3: どの順で feed しても開始・終わりは 1 回ずつ {types(allev)}")
# 逆順（meta → jsonl → meta）
meta_c = sub / "agent-c.meta.json"
jl_c = sub / "agent-c.jsonl"
meta_c.write_text(json.dumps({"agentType": "q", "finished": True}), encoding="utf-8")
jl_c.write_text("{}\n", encoding="utf-8")
allev = rd.feed(meta_c) + rd.feed(jl_c) + rd.feed(meta_c) + rd.feed(jl_c)
check(types(allev) == ["SubagentStart", "SubagentEnd"], f"3: 逆順でも開始・終わりは 1 回ずつ {types(allev)}")
# 別々のサブエージェントは別々に数える。別の親セッションのフォルダでも同じ log_dir の下なら読む
sub2 = d / "s2" / "subagents"
sub2.mkdir(parents=True)
(sub2 / "agent-d.jsonl").write_text("{}\n", encoding="utf-8")
check(types(rd.feed(sub2 / "agent-d.jsonl")) == ["SubagentStart"], "3: 別のセッションのフォルダの下のサブエージェントも読む")

# 3-10 resume：since より前に更新された会話は、末尾から読む（昔の行を流し直さない）
d = new_dir("resume")
old = d / "old.jsonl"
old.write_text("".join(jline({"type": "user", "message": {"content": f"昔{i}"}}) for i in range(50)), encoding="utf-8")
subd = d / "old" / "subagents"
subd.mkdir(parents=True)
(subd / "agent-o1.jsonl").write_text("{}\n", encoding="utf-8")
(subd / "agent-o1.meta.json").write_text(json.dumps({"agentType": "x", "finished": True}), encoding="utf-8")
(subd / "agent-o2.meta.json").write_text(json.dumps({"agentType": "y", "finished": False}), encoding="utf-8")
(subd / "agent-o3.jsonl").write_text("{}\n", encoding="utf-8")
long_ago = time.time() - 3600
for q in (old, subd / "agent-o1.jsonl", subd / "agent-o1.meta.json", subd / "agent-o2.meta.json", subd / "agent-o3.jsonl"):
    set_mtime(q, long_ago)
fresh = d / "fresh.jsonl"  # since より後に更新されたもの（先頭から読む）
fresh.write_text(jline({"type": "user", "message": {"content": "いまの会話"}}), encoding="utf-8")
rd = B.LogReader(d, since=time.time() - 600)
check(rd.feed(old) == [], "3: since より前の会話は feed しても何も返さない（昔の行を流し直さない）")
check(rd.feed(old) == [], "3: 2 回目も何も返さない")
check(rd.feed(subd / "agent-o1.jsonl") == [] and rd.feed(subd / "agent-o3.jsonl") == [],
      "3: since より前のサブエージェントの jsonl は開始を出さない")
check(rd.feed(subd / "agent-o1.meta.json") == [] and rd.feed(subd / "agent-o2.meta.json") == [],
      "3: since より前の meta は読まない（終わりも出さない）")
check(rd.feed(fresh) == [B.Prompt("fresh", "いまの会話")], "3: since より後のファイルは先頭から読む")
# 昔の会話に 1 行追記（mtime が今になる）→ その行だけ拾う
with old.open("a", encoding="utf-8") as f:
    f.write(jline({"type": "user", "message": {"content": "つづき1"}}))
    f.write(jline({"type": "assistant", "message": {"content": [{"type": "text", "text": "つづき2"}]}}))
ev = rd.feed(old)
check(ev == [B.Prompt("old", "つづき1"), B.Reply("old", "つづき2")], f"3: 昔の会話の追記分だけ拾う {ev}")
check(rd.feed(old) == [], "3: 追記分は 1 回だけ")
# 昔の会話の追記の途中の行：切れ端として覚える
with old.open("a", encoding="utf-8") as f:
    f.write('{"type":"user","message":{"content":"切')
check(rd.feed(old) == [], "3: 追記の途中の行は返さない")
with old.open("a", encoding="utf-8") as f:
    f.write('れた"}}\n')
check(rd.feed(old) == [B.Prompt("old", "切れた")], "3: 追記の途中の行も後でつながる")
# 昔の meta が後で更新されて finished になれば、開始と終わりを 1 回ずつ
(subd / "agent-o2.meta.json").write_text(json.dumps({"agentType": "y", "finished": True}), encoding="utf-8")
ev = rd.feed(subd / "agent-o2.meta.json")
check(ev == [B.SubagentStart("o2", "y", "", ""), B.SubagentEnd("o2")], f"3: 昔の meta が後で終わりになれば開始と終わりを出す {ev}")
# 古いサブエージェントの jsonl が後から追記されても、開始は出さない
with (subd / "agent-o1.jsonl").open("a", encoding="utf-8") as f:
    f.write("{}\n")
check(rd.feed(subd / "agent-o1.jsonl") == [], "3: 昔のサブエージェントの jsonl が追記されても開始を出さない")
# 起動後に初めて現れ、mtime が since より前のファイルは、末尾から読む
late_old = d / "late_old.jsonl"
late_old.write_text(jline({"type": "user", "message": {"content": "最初から入っていた行"}}), encoding="utf-8")
set_mtime(late_old, long_ago)
check(rd.feed(late_old) == [], "3: 起動後に見つけた古いファイルも、既存の行は流さない")
with late_old.open("a", encoding="utf-8") as f:
    f.write(jline({"type": "user", "message": {"content": "足した行"}}))
set_mtime(late_old, time.time())
check(rd.feed(late_old) == [B.Prompt("late_old", "足した行")], "3: 起動後に見つけた古いファイルの追記分は拾う")
# log_dir が無くても落ちない
try:
    rd_none = B.LogReader(d / "nonexistent", since=0)
    check(rd_none.feed(d / "nonexistent" / "x.jsonl") == [], "3: log_dir が無くても落ちない")
except Exception as e:  # noqa: BLE001
    check(False, f"3: log_dir が無いと落ちる {e!r}")
# since=0 なら（古くても）先頭から読む
rd0 = B.LogReader(d, since=0)
check(len(rd0.feed(old)) == 50 + 3, f"3: since=0 なら古いファイルも先頭から読む")
# 作ったあとに since より前の mtime だが空のファイル：その後の追記は拾う
d = new_dir("resume")
e0 = d / "empty.jsonl"
e0.write_text("", encoding="utf-8")
set_mtime(e0, long_ago)
rd = B.LogReader(d, since=time.time() - 600)
with e0.open("a", encoding="utf-8") as f:
    f.write(jline({"type": "user", "message": {"content": "新規"}}))
check(rd.feed(e0) == [B.Prompt("empty", "新規")], "3: 空だった古いファイルへの追記は拾う")

# 3-11 skip_existing=True（resume）：作った時点で既にあるファイルは、10 分以内に更新されたものも末尾から読む
def mk_existing(name: str = "ex"):
    """既にある会話（本体 5 行・サブエージェント 3 つ）を持つフォルダを作る。mtime はどれも今。"""
    dd = new_dir(name)
    mp = dd / "cur.jsonl"
    mp.write_text("".join(jline({"type": "user", "message": {"content": f"既存{i}"}}) for i in range(5)), encoding="utf-8")
    sd = dd / "cur" / "subagents"
    sd.mkdir(parents=True)
    (sd / "agent-e1.jsonl").write_text("{}\n", encoding="utf-8")
    (sd / "agent-e1.meta.json").write_text(json.dumps({"agentType": "x", "finished": True}), encoding="utf-8")
    (sd / "agent-e2.jsonl").write_text("{}\n", encoding="utf-8")
    (sd / "agent-e2.meta.json").write_text(json.dumps({"agentType": "y", "finished": False}), encoding="utf-8")
    (sd / "agent-e3.meta.json").write_text(json.dumps({"agentType": "z"}), encoding="utf-8")  # jsonl より先に meta だけ
    return dd, mp, sd


d, mp, sd = mk_existing()
rd_old = B.LogReader(d, since=time.time() - 600)  # 既定（False）：10 分以内に更新されたものは先頭から読む（今までどおり）
check(len(rd_old.feed(mp)) == 5, "3: skip_existing 既定（False）では、10 分以内に更新された既存の会話は先頭から読む")
check(types(rd_old.feed(sd / "agent-e1.jsonl")) == ["SubagentStart"], "3: skip_existing 既定では既存のサブエージェントの開始も出る")
d, mp, sd = mk_existing()
rd = B.LogReader(d, since=time.time() - 600, skip_existing=True)
check(rd.feed(mp) == [], "3: skip_existing=True：10 分以内に更新された既存の会話を流し直さない")
check(rd.feed(mp) == [], "3: skip_existing=True：2 回目も空")
with mp.open("a", encoding="utf-8") as f:
    f.write(jline({"type": "user", "message": {"content": "追記1"}}))
    f.write(jline({"type": "assistant", "message": {"content": [{"type": "text", "text": "追記2"}]}}))
check(rd.feed(mp) == [B.Prompt("cur", "追記1"), B.Reply("cur", "追記2")], "3: skip_existing=True：追記分だけ拾う")
with mp.open("a", encoding="utf-8") as f:
    f.write('{"type":"user","message":{"content":"切')
check(rd.feed(mp) == [], "3: skip_existing=True：追記の途中の行は返さない")
with mp.open("a", encoding="utf-8") as f:
    f.write('れた"}}\n')
check(rd.feed(mp) == [B.Prompt("cur", "切れた")], "3: skip_existing=True：途中の行は後でつながる")
# mtime が since より前の既存ファイルも同じ（末尾から）
d2, mp2, sd2 = mk_existing("ex")
set_mtime(mp2, time.time() - 5000)
rd2 = B.LogReader(d2, since=time.time() - 600, skip_existing=True)
check(rd2.feed(mp2) == [], "3: skip_existing=True：古い既存の会話も流し直さない")
# 既存のサブエージェント：開始も終わりも出さない（jsonl・meta のどの順でも、meta の更新があっても）
for q in (sd / "agent-e1.jsonl", sd / "agent-e1.meta.json", sd / "agent-e2.jsonl", sd / "agent-e2.meta.json", sd / "agent-e3.meta.json"):
    check(rd.feed(q) == [], f"3: skip_existing=True：既存のサブエージェントのファイル {q.name} は何も返さない")
(sd / "agent-e2.meta.json").write_text(json.dumps({"agentType": "y", "finished": True}), encoding="utf-8")
(sd / "agent-e3.meta.json").write_text(json.dumps({"agentType": "z", "finished": True}), encoding="utf-8")
with (sd / "agent-e1.jsonl").open("a", encoding="utf-8") as f:
    f.write("{}\n")
now_ = time.time()
for q in (sd / "agent-e1.jsonl", sd / "agent-e2.meta.json", sd / "agent-e3.meta.json"):
    set_mtime(q, now_)
    check(rd.feed(q) == [], f"3: skip_existing=True：既存のサブエージェント {q.name} が更新されても開始も終わりも出さない")
# あとから現れたファイルは先頭から読む（本体・サブエージェント）
new_main = d / "later.jsonl"
new_main.write_text(jline({"type": "user", "message": {"content": "あとから1"}}) + jline({"type": "user", "message": {"content": "あとから2"}}), encoding="utf-8")
check(rd.feed(new_main) == [B.Prompt("later", "あとから1"), B.Prompt("later", "あとから2")], "3: skip_existing=True：あとから現れた会話は先頭から読む")
(sd / "agent-n1.meta.json").write_text(json.dumps({"agentType": "kakaricho", "description": "新しい", "model": "sonnet"}), encoding="utf-8")
(sd / "agent-n1.jsonl").write_text("{}\n", encoding="utf-8")
check(rd.feed(sd / "agent-n1.jsonl") == [B.SubagentStart("n1", "kakaricho", "新しい", "sonnet")], "3: skip_existing=True：あとから現れたサブエージェントは開始を出す")
(sd / "agent-n1.meta.json").write_text(json.dumps({"agentType": "kakaricho", "finished": True}), encoding="utf-8")
check(rd.feed(sd / "agent-n1.meta.json") == [B.SubagentEnd("n1")], "3: skip_existing=True：あとから現れたサブエージェントの終わりも出す")
(sd / "agent-n2.meta.json").write_text(json.dumps({"agentType": "q", "finished": True}), encoding="utf-8")
check(types(rd.feed(sd / "agent-n2.meta.json")) == ["SubagentStart", "SubagentEnd"], "3: skip_existing=True：あとから現れた meta だけのサブエージェントは開始と終わり")
# log_dir が無い／あとから作られる
dn = RUN_DIR / "never_made_1"
rd_n = B.LogReader(dn, since=time.time() - 600, skip_existing=True)
check(rd_n.feed(dn / "x.jsonl") == [], "3: skip_existing=True：log_dir が無くても落ちない")
dn.mkdir()
(dn / "x.jsonl").write_text(jline({"type": "user", "message": {"content": "最初から"}}), encoding="utf-8")
check(rd_n.feed(dn / "x.jsonl") == [B.Prompt("x", "最初から")], "3: skip_existing=True：log_dir があとから作られたら、その中のファイルは先頭から読む")
# 位置引数でも渡せる（since の次が skip_existing）
check(B.LogReader(d, 0).since == 0 and B.LogReader(d, 5.0, True).since == 5.0, "3: LogReader(log_dir, since, skip_existing) の形で作れる")

# Bridge：resume のときだけ skip_existing=True を渡す（動きで確かめる）
for mode, expect_skip in (("resume", True), ("new", False), ("restart", False)):
    dd, mp_, sd_ = mk_existing("brx")
    fr_ = FakeRun()
    fr_.session = True
    FakeWatcher_made = []

    class _W:
        def __init__(self, ld, rd):
            self.reader = rd
            FakeWatcher_made.append(self)

        def start(self):
            pass

        def stop(self):
            pass

        def poll(self, max_events=200):
            return []

    br = B.Bridge("/home/x/my_proj/q", session="SQ", tmux=B.TmuxControl(session="SQ", run=fr_),
                  watcher_factory=lambda ld, rd: _W(ld, rd), clock=time.time)
    br.log_dir = dd
    check(br.begin(mode) is True, f"3: Bridge.begin({mode!r}) が成功")
    got_ = br.reader.feed(mp_)
    if expect_skip:
        check(got_ == [], f"3: Bridge.begin('resume') は既存の会話を流し直さない {len(got_)}")
        check(br.reader.feed(sd_ / "agent-e1.jsonl") == [], "3: Bridge.begin('resume') は既存のサブエージェントの開始を出さない")
    else:
        check(len(got_) == 5, f"3: Bridge.begin({mode!r}) は今までどおり（2 秒前から。10 分以内の既存ファイルは先頭から） {len(got_)}")
        check(types(br.reader.feed(sd_ / "agent-e1.jsonl")) == ["SubagentStart"], f"3: Bridge.begin({mode!r}) は既存のサブエージェントの開始を出す")
    br.end(kill_session=False)

# ---------------------------------------------------------------------------
# 4. LogWatcher
# ---------------------------------------------------------------------------
class FakeProc:
    """inotifywait の代わり。標準出力は StringIO。terminate・wait・kill の呼ばれ方を数える。"""

    def __init__(self, text: str = ""):
        self.stdout = io.StringIO(text)
        self.terminated = 0
        self.killed = 0
        self.waited = 0

    def terminate(self):
        self.terminated += 1

    def wait(self, timeout=None):
        self.waited += 1
        return 0

    def kill(self):
        self.killed += 1


class PipeProc:
    """本物のパイプで標準出力をまねる。書き込み側を閉じるまで、読むスレッドはブロックする。"""

    def __init__(self):
        r, w = os.pipe()
        self.stdout = os.fdopen(r, "r", encoding="utf-8")
        self._w = os.fdopen(w, "w", encoding="utf-8")
        self.terminated = 0

    def write(self, s: str):
        self._w.write(s)
        self._w.flush()

    def terminate(self):
        self.terminated += 1
        try:
            self._w.close()  # 終わらせると読み側が EOF になる
        except OSError:
            pass

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminate()


class FakePopen:
    """Popen の代わり。呼ばれた引数を残し、決めた FakeProc を返す。"""

    def __init__(self, proc):
        self.proc = proc
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, cmd, **kw):
        self.calls.append((list(cmd), kw))
        return self.proc


def wait_for(cond, timeout=3.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def poll_until(w: "B.LogWatcher", n: int, timeout=3.0) -> list:
    """イベントが n 個たまるまで poll を繰り返す。"""
    out: list = []
    end = time.time() + timeout
    while time.time() < end and len(out) < n:
        out.extend(w.poll())
        if len(out) < n:
            time.sleep(0.01)
    return out


# 4-1 既定のコマンド：log_dir があるときは log_dir、無ければ親
d = new_dir("watch")
rd = B.LogReader(d, 0)
fp = FakePopen(FakeProc(""))
w = B.LogWatcher(d, rd, popen=fp)
w.start()
cmd, kw = fp.calls[0]
check(cmd == ["inotifywait", "-m", "-r", "-q", "-e", "create,modify,moved_to", "--format", "%w%f", str(d)],
      f"4: 既定の inotifywait のコマンド {cmd}")
check(kw.get("stdout") == subprocess.PIPE and kw.get("text") is True, f"4: Popen の引数（stdout=PIPE, text=True） {kw}")
check(kw.get("stderr") == subprocess.DEVNULL, "4: 標準エラーは捨てる")
w.stop()
missing = d / "not_yet"
fp = FakePopen(FakeProc(""))
w = B.LogWatcher(missing, B.LogReader(missing, 0), popen=fp)
w.start()
check(fp.calls[0][0][-1] == str(d) and not missing.exists(),
      f"4: log_dir が無ければ作らずに親を見張る {fp.calls[0][0][-1]} 存在={missing.exists()}")
w.stop()
# 差し替えたコマンドはそのまま使う
fp = FakePopen(FakeProc(""))
w = B.LogWatcher(d, rd, inotify_cmd=["echo", "x"], popen=fp)
w.start()
check(fp.calls[0][0] == ["echo", "x"], "4: inotify_cmd を差し替えられる")
w.stop()

# 4-2 まとめ：同じパスは 1 回に
d = new_dir("watch")
rd = B.LogReader(d, 0)
f1 = d / "a.jsonl"
f2 = d / "b.jsonl"
f1.write_text(jline({"type": "user", "message": {"content": "A"}}), encoding="utf-8")
f2.write_text(jline({"type": "user", "message": {"content": "B"}}), encoding="utf-8")
proc = FakeProc(f"{f1}\n{f1}\n{f2}\n{f1}\n{f2}\n")
w = B.LogWatcher(d, rd, popen=FakePopen(proc))
w.start()
check(wait_for(lambda: w._queue.qsize() >= 5), "4: 5 行がキューに入る")
ev = w.poll()
check(sorted(e.text for e in ev) == ["A", "B"] and types(ev) == ["Prompt", "Prompt"], f"4: 同じパスは 1 回にまとめて読む {ev}")
check(ev[0].text == "A", "4: 最初に出たパスの順")
check(w.poll() == [], "4: もう一度 poll しても空")
w.stop()

# 4-3 log_dir の下だけ使う
d = new_dir("watch")
other = new_dir("watch")
sibling = Path(str(d) + "-sibling")  # 名前が log_dir で始まるだけの別のフォルダ
sibling.mkdir()
ok_file = d / "ok.jsonl"
ng_file = other / "ng.jsonl"
sib_file = sibling / "sib.jsonl"
for q, t in ((ok_file, "OK"), (ng_file, "NG"), (sib_file, "SIB")):
    q.write_text(jline({"type": "user", "message": {"content": t}}), encoding="utf-8")
proc = FakeProc(f"{ng_file}\n{sib_file}\n\n/etc/passwd\nrelative.jsonl\n{ok_file}\n")
w = B.LogWatcher(d, B.LogReader(d, 0), popen=FakePopen(proc))
w.start()
ev = poll_until(w, 1)
time.sleep(0.1)
ev += w.poll()
check(ev == [B.Prompt("ok", "OK")], f"4: log_dir の下のパスだけ使う {ev}")
w.stop()
# サブエージェントのパス（log_dir の下の下）も使う
d = new_dir("watch")
subd = d / "s" / "subagents"
subd.mkdir(parents=True)
(subd / "agent-w.meta.json").write_text(json.dumps({"agentType": "t"}), encoding="utf-8")
w = B.LogWatcher(d, B.LogReader(d, 0), popen=FakePopen(FakeProc(f"{subd}/agent-w.meta.json\n")))
w.start()
ev = poll_until(w, 1)
check(ev == [B.SubagentStart("w", "t", "", "")], f"4: log_dir の下の下（subagents）のパスも使う {ev}")
w.stop()

# 4-4 poll はブロックしない・max_events・残りは次の poll へ
d = new_dir("watch")
f1 = d / "a.jsonl"
f1.write_text("".join(jline({"type": "user", "message": {"content": str(i)}}) for i in range(10)), encoding="utf-8")
pp = PipeProc()
w = B.LogWatcher(d, B.LogReader(d, 0), popen=FakePopen(pp))
w.start()
t0 = time.time()
r = w.poll()
check(r == [] and time.time() - t0 < 0.5, f"4: 何も来ていないとき poll はすぐ空を返す（{time.time() - t0:.2f}秒）")
pp.write(f"{f1}\n")
check(wait_for(lambda: w._queue.qsize() == 1), "4: パイプに書くとスレッドがキューに入れる")
first = w.poll(max_events=4)
check([e.text for e in first] == ["0", "1", "2", "3"], f"4: max_events で最大数に切る {[e.text for e in first]}")
second = w.poll(max_events=4)
check([e.text for e in second] == ["4", "5", "6", "7"], f"4: 残りは次の poll へ（パスが来なくても） {[e.text for e in second]}")
third = w.poll()
check([e.text for e in third] == ["8", "9"], f"4: 最後の残り {[e.text for e in third]}")
check(w.poll() == [], "4: 全部出したら空")
# 既定の max_events は 200
d = new_dir("watch")
f1 = d / "big.jsonl"
f1.write_text("".join(jline({"type": "user", "message": {"content": str(i)}}) for i in range(250)), encoding="utf-8")
pp2 = PipeProc()
w2 = B.LogWatcher(d, B.LogReader(d, 0), popen=FakePopen(pp2))
w2.start()
pp2.write(f"{f1}\n")
check(wait_for(lambda: w2._queue.qsize() == 1), "4: 大きなファイルのパスが入る")
check(len(w2.poll()) == 200 and len(w2.poll()) == 50, "4: 既定の max_events は 200")
# 続けて追記（modify）を書く
f3 = d / "more.jsonl"
f3.write_text(jline({"type": "user", "message": {"content": "more"}}), encoding="utf-8")
pp2.write(f"{f3}\n")
ev = poll_until(w2, 1)
check(ev == [B.Prompt("more", "more")], f"4: あとから来たパスも読める {ev}")

# 4-5 stop：terminate・スレッド終了。2 回呼んでも・start 前でも落ちない
th = w._thread
check(th is not None and th.is_alive(), "4: stop 前は読むスレッドが動いている")
w.stop()
check(pp.terminated >= 1, "4: stop で子プロセスを terminate する")
check(th is not None and not th.is_alive(), "4: stop でスレッドが終わる")
try:
    w.stop()
    check(True, "")
except Exception as e:  # noqa: BLE001
    check(False, f"4: stop を 2 回呼ぶと落ちる {e!r}")
w2.stop()
w3 = B.LogWatcher(d, B.LogReader(d, 0), popen=FakePopen(FakeProc("")))
try:
    w3.stop()
    check(w3.poll() == [], "4: start 前の stop・poll は何もしない")
except Exception as e:  # noqa: BLE001
    check(False, f"4: start 前の stop で落ちた {e!r}")
# 子プロセスが terminate に応じない（wait がタイムアウト）なら kill
class StubbornProc(FakeProc):
    def wait(self, timeout=None):
        self.waited += 1
        raise subprocess.TimeoutExpired("x", timeout)


sp = StubbornProc("")
w4 = B.LogWatcher(d, B.LogReader(d, 0), popen=FakePopen(sp))
w4.start()
w4.stop()
check(sp.terminated == 1 and sp.killed == 1, f"4: terminate に応じなければ kill する（terminate={sp.terminated} kill={sp.killed}）")
# start を 2 回呼んでも見張りは 1 つ
fp = FakePopen(FakeProc(""))
w5 = B.LogWatcher(d, B.LogReader(d, 0), popen=fp)
w5.start()
w5.start()
check(len(fp.calls) == 1, f"4: start を 2 回呼んでも Popen は 1 回 {len(fp.calls)}")
w5.stop()

# 4-6 Popen の失敗（inotifywait が無い）：落ちずに last_error
def popen_fail(cmd, **kw):
    raise FileNotFoundError("inotifywait")


w6 = B.LogWatcher(d, B.LogReader(d, 0), popen=popen_fail)
try:
    w6.start()
    check(w6.last_error != "" and w6.poll() == [], f"4: Popen 失敗で last_error が残り、poll は空 {w6.last_error!r}")
    w6.stop()
except Exception as e:  # noqa: BLE001
    check(False, f"4: Popen 失敗で落ちた {e!r}")

# ---------------------------------------------------------------------------
# 5. Bridge
# ---------------------------------------------------------------------------
class FakeWatcher:
    """見張りの代わり。start・stop の回数と、渡された log_dir・reader を残す。"""

    made: list["FakeWatcher"] = []

    def __init__(self, log_dir, reader):
        self.log_dir = log_dir
        self.reader = reader
        self.started = 0
        self.stopped = 0
        self.out: list = []
        FakeWatcher.made.append(self)

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1

    def poll(self, max_events=200):
        out, self.out = self.out, []
        return out


def make_bridge(session_exists: bool, workdir="/home/x/my_proj/p_q", now=10000.0):
    fr_ = FakeRun()
    fr_.session = session_exists
    FakeWatcher.made = []
    clock = [now]
    br = B.Bridge(workdir, session="SX", tmux=B.TmuxControl(session="SX", workdir=workdir, run=fr_),
                  watcher_factory=lambda ld, rd: FakeWatcher(ld, rd), clock=lambda: clock[0])
    return br, fr_, clock


# 5-1 new：無ければ作る・あればそのまま・since は 2 秒前
br, fr_, clock = make_bridge(False)
check(br.log_dir == B.project_log_dir("/home/x/my_proj/p_q"), "5: Bridge.log_dir は project_log_dir")
check(br.session_exists() is False and fr_.subs() == ["has-session"], "5: session_exists は tmux.exists")
check(br.poll() == [], "5: begin 前の poll は空")
check(br.begin("new") is True, "5: new（無い）は成功")
check("new-session" in fr_.subs(), f"5: new は無ければ new-session を呼ぶ {fr_.subs()}")
check(fr_.subs().count("new-session") == 1 and "kill-session" not in fr_.subs(), "5: new は kill しない・作るのは 1 回")
check(len(FakeWatcher.made) == 1 and FakeWatcher.made[0].started == 1, "5: begin で見張りが 1 つ始まる")
check(FakeWatcher.made[0].log_dir == br.log_dir and FakeWatcher.made[0].reader is br.reader, "5: 見張りに log_dir と reader を渡す")
check(br.reader.since == 10000.0 - B.SINCE_MARGIN_SEC == 9998.0, f"5: new の since は clock-2 {br.reader.since}")
check(br.reader.log_dir == br.log_dir, "5: reader の log_dir")

br, fr_, clock = make_bridge(True)
check(br.begin("new") is True and "new-session" not in fr_.subs() and "kill-session" not in fr_.subs(),
      f"5: new でセッションがあれば作らない・閉じない {fr_.subs()}")
check(br.reader.since == 9998.0, "5: new（あり）の since も clock-2")

# 5-2 resume：あればつなぐ（作らない）、since は 600 秒前。無ければ False
br, fr_, clock = make_bridge(True)
check(br.begin("resume") is True, "5: resume（あり）は成功")
check("new-session" not in fr_.subs() and "kill-session" not in fr_.subs(), f"5: resume は作らず閉じない {fr_.subs()}")
check(br.reader.since == 10000.0 - B.RESUME_LOOKBACK_SEC == 9400.0, f"5: resume の since は clock-600 {br.reader.since}")
check(len(FakeWatcher.made) == 1 and FakeWatcher.made[0].started == 1, "5: resume で見張りが始まる")
br, fr_, clock = make_bridge(False)
check(br.begin("resume") is False, "5: resume（無い）は False")
check("new-session" not in fr_.subs(), "5: resume は無くても作らない")
check(br.tmux.last_error != "", "5: resume の失敗は tmux.last_error に理由が残る")
check(FakeWatcher.made == [] and br.watcher is None and br.reader is None, "5: resume 失敗では見張りを作らない")
check(br.poll() == [], "5: 失敗のあとの poll は空")

# 5-3 restart：あれば閉じてから作る・無ければ作るだけ。since は 2 秒前
br, fr_, clock = make_bridge(True)
check(br.begin("restart") is True, "5: restart（あり）は成功")
subs_ = fr_.subs()
check("kill-session" in subs_ and "new-session" in subs_ and subs_.index("kill-session") < subs_.index("new-session"),
      f"5: restart は閉じてから作る {subs_}")
check(fr_.session is True, "5: restart のあとセッションがある")
check(br.reader.since == 9998.0, "5: restart の since は clock-2")
br, fr_, clock = make_bridge(False)
check(br.begin("restart") is True and "kill-session" not in fr_.subs() and fr_.subs().count("new-session") == 1,
      f"5: restart（無い）は閉じずに作る {fr_.subs()}")

# 5-4 start / kill の失敗
br, fr_, clock = make_bridge(False)
fr_.fail["new-session"] = (1, "起動できない")
check(br.begin("new") is False and br.tmux.last_error == "起動できない", f"5: new-session 失敗で begin が False {br.tmux.last_error!r}")
check(FakeWatcher.made == [] and br.watcher is None, "5: 起動失敗では見張りを作らない")
br, fr_, clock = make_bridge(True)
fr_.fail["new-session"] = (1, "x")
check(br.begin("restart") is False, "5: restart の作り直しに失敗したら False")
check(FakeWatcher.made == [], "5: restart 失敗では見張りを作らない")

# 5-5 不正な mode
br, fr_, clock = make_bridge(False)
try:
    br.begin("bogus")
    check(False, "5: 不正な mode が例外にならない")
except ValueError:
    check(True, "")
check(fr_.subs() == [], f"5: 不正な mode では tmux を触らない {fr_.subs()}")

# 5-6 begin を続けて呼ぶと前の見張りを止める
br, fr_, clock = make_bridge(False)
br.begin("new")
first_w = FakeWatcher.made[0]
clock[0] = 20000.0
br.begin("resume")
check(first_w.stopped == 1, "5: 2 回目の begin で前の見張りを止める")
check(len(FakeWatcher.made) == 2 and FakeWatcher.made[1].started == 1 and br.watcher is FakeWatcher.made[1], "5: 2 回目の見張りが始まる")
check(br.reader.since == 20000.0 - 600.0, "5: 2 回目の since は新しい clock から")
# 失敗した begin のあとは見張りが残らない
br.tmux.stop()
check(br.begin("resume") is False and br.watcher is None and FakeWatcher.made[1].stopped == 1, "5: 失敗した begin のあと前の見張りは止まっている")

# 5-7 send_prompt / send_escape / poll / end
br, fr_, clock = make_bridge(True)
br.begin("resume")
fr_.calls.clear()
check(br.send_prompt("やあ") is True and fr_.subs() == ["load-buffer", "paste-buffer", "send-keys"], f"5: send_prompt は tmux に渡る {fr_.subs()}")
check(fr_.calls[0][1] == "やあ", "5: send_prompt の text")
fr_.calls.clear()
check(br.send_escape() is True and fr_.cmds() == [["tmux", "send-keys", "-t", "SX", "Escape"]], "5: send_escape は tmux に渡る")
fr_.fail["send-keys"] = (1, "失敗")
check(br.send_escape() is False, "5: tmux の失敗は False で返る")
fr_.fail.clear()
FakeWatcher.made[0].out = [B.TurnEnd("s")]
check(br.poll() == [B.TurnEnd("s")], "5: poll は見張りのイベントを返す")
w_ = FakeWatcher.made[0]
fr_.calls.clear()
br.end(kill_session=False)
check(w_.stopped == 1 and br.watcher is None and br.reader is None, "5: end で見張りを止める")
check(fr_.calls == [], f"5: end(False) は tmux を触らない {fr_.subs()}")
check(fr_.session is True, "5: end(False) でセッションは残る")
check(br.poll() == [], "5: end のあとの poll は空")
br.end(kill_session=False)  # 2 回呼んでも落ちない
br.begin("resume")
br.end(kill_session=True)
check(fr_.session is False and "kill-session" in fr_.subs(), "5: end(True) でセッションを閉じる")
br.end(kill_session=True)  # 無くても落ちない
check(True, "")

# 5-8 既定の部品（本物の run を使うものを作るだけ。何も起動しない）
br_default = B.Bridge("/home/x/my_proj/d")
check(isinstance(br_default.tmux, B.TmuxControl) and br_default.tmux.session == B.DEFAULT_SESSION
      and br_default.tmux.workdir == "/home/x/my_proj/d", "5: 既定の TmuxControl は session・workdir を引き継ぐ")
br_s = B.Bridge("/home/x/my_proj/d", session="abc")
check(br_s.tmux.session == "abc" and br_s.session == "abc", "5: session 名を渡せる")
check(br_default.watcher is None and br_default.poll() == [], "5: 作っただけでは見張りは動かない")

# 5-9 実物の LogReader・LogWatcher と偽の popen で、Bridge の見張りから届くまでの通し
log_dir = new_dir("proj")
fr_ = FakeRun()
fr_.session = True
f_main = log_dir / "ses.jsonl"
f_main.write_text(jline({"type": "user", "message": {"content": "昔の行"}}), encoding="utf-8")
set_mtime(f_main, time.time() - 5000)
pp = PipeProc()
br = B.Bridge("/home/x/my_proj/zz", session="SZ", tmux=B.TmuxControl(session="SZ", run=fr_),
              watcher_factory=lambda ld, rd: B.LogWatcher(log_dir, rd, popen=FakePopen(pp)))
br.log_dir = log_dir  # begin が作る LogReader の場所を一時フォルダにする
check(br.begin("resume") is True, "5: 通し：resume")
pp.write(f"{f_main}\n")
time.sleep(0.2)
check(br.poll() == [], "5: 通し：resume で昔の行は流れない")
with f_main.open("a", encoding="utf-8") as f:
    f.write(jline({"type": "user", "message": {"content": "いまの行"}}))
pp.write(f"{f_main}\n")
ev = []
end = time.time() + 3
while time.time() < end and not ev:
    ev = br.poll()
    time.sleep(0.01)
check(ev == [B.Prompt("ses", "いまの行")], f"5: 通し：追記の行だけ届く {ev}")
br.end(kill_session=False)
check(br.watcher is None, "5: 通しのあと見張りが止まっている")

# ---------------------------------------------------------------------------
# 6. TmuxControl.capture と Bridge.permission_screen_open（tmux の画面に許可の画面が出ているか）
# ---------------------------------------------------------------------------
class FakeRunScreen(FakeRun):
    """capture-pane の標準出力（screen）を返せる FakeRun。screen が None なら標準出力は None。"""

    def __init__(self, screen: str | None = ""):
        super().__init__()
        self.screen = screen

    def __call__(self, cmd, input=None, **kw):
        res = super().__call__(cmd, input=input, **kw)
        sub = cmd[1] if len(cmd) > 1 else ""
        if sub == "capture-pane" and res.returncode == 0:
            return subprocess.CompletedProcess(cmd, 0, self.screen, "")
        return res


# 6-1 capture：コマンド・戻り値
frs = FakeRunScreen("1行目\n2行目\n")
tms = B.TmuxControl(session="S6", run=frs)
check(tms.capture() == "1行目\n2行目\n", f"6: capture が標準出力をそのまま返す {tms.capture()!r}")
check(frs.cmds()[0] == ["tmux", "capture-pane", "-p", "-t", "S6"], f"6: capture のコマンド {frs.cmds()[0]}")
kw = frs.calls[0][2]
check(frs.calls[0][1] is None and kw.get("capture_output") is True and kw.get("text") is True and kw.get("check") is False, f"6: capture の run の引数（input なし・capture_output・text・check=False） {kw}")
check(frs.subs() == ["capture-pane", "capture-pane"], f"6: capture は capture-pane だけを呼ぶ（has-session などは呼ばない） {frs.subs()}")
tms2 = B.TmuxControl(session="S7", tmux="/opt/tmux", run=frs)
frs.calls.clear()
tms2.capture()
check(frs.cmds()[0] == ["/opt/tmux", "capture-pane", "-p", "-t", "S7"], "6: tmux のコマンド名・セッション名を使う")
# 空の画面は ""（None ではない）。標準出力が None でも "" 
check(B.TmuxControl(run=FakeRunScreen("")).capture() == "", "6: 空の画面は空文字（None ではない）")
check(B.TmuxControl(run=FakeRunScreen(None)).capture() == "", "6: 標準出力が None でも空文字")
# 失敗は None・last_error は変えない
frf = FakeRunScreen("x")
frf.fail["capture-pane"] = (1, "can't find pane")
tmf = B.TmuxControl(run=frf)
tmf.last_error = "前のエラー"
check(tmf.capture() is None, "6: 失敗（戻り値 1）は None")
check(tmf.last_error == "前のエラー", f"6: capture の失敗では last_error を変えない {tmf.last_error!r}")
tmg = B.TmuxControl(run=FakeRunScreen("ok"))
tmg.last_error = "前のエラー"
check(tmg.capture() == "ok" and tmg.last_error == "前のエラー", "6: capture の成功でも last_error を変えない")
# 失敗のあとに成功
frf.fail.clear()
check(tmf.capture() == "x", "6: 失敗のあとでも次は読める")

# 6-2 permission_screen_open
PERM_SCREEN = "  Bash command\n    ls -la\n\n Do you want to proceed?\n ❯ 1. Yes\n   2. No\n\n Esc to cancel · Tab to amend\n"


def make_screen_bridge(screen):
    fr_ = FakeRunScreen(screen)
    br_ = B.Bridge("/home/x/my_proj/s6", session="S6", tmux=B.TmuxControl(session="S6", run=fr_),
                   watcher_factory=lambda ld, rd: FakeWatcher(ld, rd))
    return br_, fr_


br6, fr6 = make_screen_bridge(PERM_SCREEN)
check(br6.permission_screen_open() is True, "6: 「Do you want to」と「Esc to cancel」が両方あれば True")
check(fr6.cmds() == [["tmux", "capture-pane", "-p", "-t", "S6"]], f"6: 画面を1回だけ調べる（ほかの tmux コマンドを呼ばない） {fr6.cmds()}")
cases = [
    ("Do you want to のみ", "Do you want to proceed?\n1. Yes\n", False),
    ("Esc to cancel のみ", "something\nEsc to cancel\n", False),
    ("どちらも無い", "> ここに入力\n? for shortcuts\n", False),
    ("空の画面", "", False),
    ("同じ行に両方", "Do you want to proceed? Esc to cancel", True),
    ("離れた行に両方", "Do you want to a\n" + "x\n" * 50 + "Esc to cancel\n", True),
    ("小文字（do you want to）", "do you want to proceed?\nesc to cancel\n", False),
    ("大文字小文字が混ざる", "DO YOU WANT TO\nESC TO CANCEL\n", False),
    ("一部だけ（Do you want）", "Do you want\nEsc to cancel\n", False),
    ("一部だけ（Esc to）", "Do you want to\nEsc to\n", False),
    ("日本語の画面に含まれる", "許可しますか\nDo you want to proceed?\n2. No\nEsc to cancel · Tab to amend\n", True),
]
for label, screen, want in cases:
    b_, _ = make_screen_bridge(screen)
    check(b_.permission_screen_open() is want, f"6: {label} → {want}")
# capture が None（tmux 失敗）なら False
frx = FakeRunScreen(PERM_SCREEN)
frx.fail["capture-pane"] = (1, "no server")
bx = B.Bridge("/home/x/my_proj/s6", session="S6", tmux=B.TmuxControl(session="S6", run=frx))
check(bx.permission_screen_open() is False, "6: 画面を調べられなければ False（例外にしない）")
# Bridge が使う tmux の capture（差し替えた偽の capture）を呼ぶ・戻り値の型は bool
class FakeTmuxCap:
    def __init__(self, text):
        self.text, self.n = text, 0

    def capture(self):
        self.n += 1
        return self.text


bt = B.Bridge("/home/x/my_proj/s6", tmux=FakeTmuxCap("Do you want to\nEsc to cancel"))
r6 = bt.permission_screen_open()
check(r6 is True and isinstance(r6, bool) and bt.tmux.n == 1, f"6: tmux.capture を1回呼んで bool を返す {r6!r} {bt.tmux.n}")
bt2 = B.Bridge("/home/x/my_proj/s6", tmux=FakeTmuxCap(None))
check(bt2.permission_screen_open() is False, "6: tmux.capture が None なら False")
# 画面が変わったら答えも変わる（キャッシュしない）
bt3 = B.Bridge("/home/x/my_proj/s6", tmux=FakeTmuxCap("Do you want to\nEsc to cancel"))
check(bt3.permission_screen_open() is True, "6: 許可の画面が出ている")
bt3.tmux.text = "> \n"
check(bt3.permission_screen_open() is False, "6: 画面が変われば False に戻る（前の答えを覚えない）")

# ---------------------------------------------------------------------------
# 7. prompt_display：プロンプトの文を画面に見せる形にする（戻り値は (見せる文, 知らせか)）
# ---------------------------------------------------------------------------
# 7-a. スラッシュコマンド（実物の形）：名前＋引数
pd = B.prompt_display("<command-name>/clear</command-name>\n            <command-message>clear</command-message>\n            <command-args></command-args>")
check(pd == ("/clear", True), f"7: 引数が空のコマンドは名前だけ {pd!r}")
pd = B.prompt_display("<command-name>/model</command-name>\n<command-message>model</command-message>\n<command-args>opus</command-args>")
check(pd == ("/model opus", True), f"7: 引数ありは「名前 引数」 {pd!r}")
pd = B.prompt_display("<command-name>/x</command-name><command-args>  a b\n </command-args>")
check(pd == ("/x a b", True), f"7: 引数の前後の空白は削る {pd!r}")
# 7-b. ローカルコマンドの出力
pd = B.prompt_display("<local-command-stdout>Set model to opus</local-command-stdout>")
check(pd == ("Set model to opus", True), f"7: stdout は中身 {pd!r}")
pd = B.prompt_display("<local-command-stderr>エラーです</local-command-stderr>")
check(pd == ("エラーです", True), f"7: stderr も中身 {pd!r}")
pd = B.prompt_display("<local-command-stdout></local-command-stdout>")
check(pd == ("(出力なし)", True), f"7: 中身が空なら「(出力なし)」 {pd!r}")
pd = B.prompt_display("<local-command-stdout>  \n </local-command-stdout>")
check(pd == ("(出力なし)", True), f"7: 空白だけでも「(出力なし)」 {pd!r}")
pd = B.prompt_display("<local-command-stdout>一</local-command-stdout><local-command-stderr>二</local-command-stderr>")
check(pd == ("一\n二", True), f"7: 出力が2つなら改行でつなぐ {pd!r}")
# 7-c. サブエージェントの知らせ
pd = B.prompt_display("<task-notification>\n<task-id>abc</task-id>\n<status>completed</status>\n<summary>Agent \"調査\" completed</summary>\n<result>長い結果</result>\n</task-notification>")
check(pd == ('[知らせ] Agent "調査" completed', True), f"7: 知らせは「[知らせ] summary」 {pd!r}")
pd = B.prompt_display("<task-notification><task-id>a</task-id><status>failed</status></task-notification>")
check(pd == ("[知らせ] failed", True), f"7: summary が無ければ status {pd!r}")
pd = B.prompt_display("<task-notification><summary>  </summary><status>killed</status></task-notification>")
check(pd == ("[知らせ] killed", True), f"7: summary が空白だけなら status {pd!r}")
pd = B.prompt_display("<task-notification><task-id>a</task-id></task-notification>")
check(pd == ("[知らせ] サブエージェントの知らせ", True), f"7: どちらも無ければ決まり文句 {pd!r}")
# 7-d. タグの無い文はそのまま・False
for t in ("", "こんにちは", "a < b かつ c > d", "1 <2 and 3> 0", "  前後の空白もそのまま  \n二行目"):
    pd = B.prompt_display(t)
    check(pd == (t, False), f"7: タグの無い文はそのまま False {t!r} → {pd!r}")
check(B.prompt_display("if a<b and c>d:\n    pass") == ("if a<b and c>d:\n    pass", False), "7: 不等号を含むコードもそのまま")
# 7-e. ほかのタグ入りの普通の文：タグを外す
pd = B.prompt_display("<system-reminder>注意</system-reminder>\nこれをやって")
check(pd[0] == "注意\nこれをやって", f"7: ほかのタグは外す（空行は詰める） {pd!r}")
check(pd[1] is True, "7: タグを外したときの2つ目の値（実際の挙動：True）")
pd = B.prompt_display("<foo/>やって<bar>ね</bar>")
check(pd[0] == "やってね", f"7: 開閉・自己閉じのタグを外す {pd!r}")
# 7-e2. 限界（仕様の確認）：<y> のような「英字だけのタグの形」は、普通の文にあってもタグとして外す
pd = B.prompt_display("x<y>z は?")
check(pd == ("xz は?", True), f"7: 英字だけの <y> はタグ扱いで外れる（既知の限界） {pd!r}")
# 7-f. 優先順：command-name があれば他のタグより先
pd = B.prompt_display("<command-name>/a</command-name><local-command-stdout>x</local-command-stdout>")
check(pd == ("/a", True), f"7: command-name が先 {pd!r}")
# 7-g. 戻り値の型
check(isinstance(pd, tuple) and len(pd) == 2 and isinstance(pd[0], str) and isinstance(pd[1], bool), "7: (str, bool) の組")

# ---------------------------------------------------------------------------
# 8. send_keys・send_literal・start の画面の大きさの固定（スラッシュコマンドの窓）
# ---------------------------------------------------------------------------
# 8-a. send_keys：キー名を順に1回の send-keys で送る
fr8 = FakeRun()
t8 = B.TmuxControl(session="S8", run=fr8)
check(t8.send_keys("Up") is True and fr8.cmds() == [["tmux", "send-keys", "-t", "S8", "Up"]], f"8: send_keys 1つ {fr8.cmds()}")
fr8.calls.clear()
check(t8.send_keys("Down", "Enter") is True and fr8.cmds() == [["tmux", "send-keys", "-t", "S8", "Down", "Enter"]],
      f"8: send_keys 複数は1回にまとめて順に送る {fr8.cmds()}")
check(all(c[1] is None and c[2].get("capture_output") is True and c[2].get("text") is True and c[2].get("check") is False for c in fr8.calls),
      "8: send_keys は標準入力なし・capture_output=True,text=True,check=False")
fr8.calls.clear()
for name in ("Escape", "Tab", "BSpace", "Space", "PPage", "NPage", "Left", "Right"):
    t8.send_keys(name)
check([c[-1] for c in fr8.cmds()] == ["Escape", "Tab", "BSpace", "Space", "PPage", "NPage", "Left", "Right"], "8: tmux のキー名をそのまま渡す")
# 失敗：False と last_error
fr8b = FakeRun()
fr8b.fail["send-keys"] = (1, "キー失敗\n")
t8b = B.TmuxControl(session="S8", run=fr8b)
check(t8b.send_keys("Up") is False and t8b.last_error == "キー失敗", f"8: send_keys 失敗 {t8b.last_error!r}")
check(t8b.send_literal("a") is False and t8b.last_error == "キー失敗", "8: send_literal 失敗")
# 8-b. send_literal：-l で文字をそのまま。Enter は付けない。空なら何もせず True
fr8.calls.clear()
check(t8.send_literal("abc") is True and fr8.cmds() == [["tmux", "send-keys", "-t", "S8", "-l", "abc"]], f"8: send_literal {fr8.cmds()}")
check("Enter" not in fr8.cmds()[0], "8: send_literal は Enter を付けない")
fr8.calls.clear()
check(t8.send_literal("") is True and fr8.calls == [], "8: send_literal 空は何もせず True")
fr8.calls.clear()
t8.send_literal(" -x ;")
check(fr8.cmds() == [["tmux", "send-keys", "-t", "S8", "-l", " -x ;"]], f"8: send_literal は記号・空白もそのまま1つの引数 {fr8.cmds()}")
# 8-c. start：window-size manual の失敗では resize-window を呼ばず、それでも True・last_error は空
fr8c = FakeRun()
fr8c.fail["set-option"] = (1, "set-option 失敗")
t8c = B.TmuxControl(session="S8c", workdir="/w", claude_cmd="c", run=fr8c)
check(t8c.start() is True, "8: window-size の設定に失敗しても start は True")
check(fr8c.subs() == ["new-session", "set-option"], f"8: set-option が失敗したら resize-window は呼ばない {fr8c.subs()}")
check(t8c.last_error == "", f"8: 大きさの固定の失敗は last_error に残さない {t8c.last_error!r}")
# 8-d. resize-window の失敗でも True・last_error は空
fr8d = FakeRun()
fr8d.fail["resize-window"] = (1, "resize 失敗")
t8d = B.TmuxControl(session="S8d", workdir="/w", claude_cmd="c", run=fr8d)
check(t8d.start() is True and fr8d.subs() == ["new-session", "set-option", "resize-window"], f"8: resize-window 失敗でも True {fr8d.subs()}")
check(t8d.last_error == "", f"8: resize-window の失敗も last_error に残さない {t8d.last_error!r}")
# 8-e. new-session の失敗：False・last_error が残り、あとの大きさのコマンドは呼ばない
fr8e = FakeRun()
fr8e.fail["new-session"] = (1, "duplicate session")
t8e = B.TmuxControl(session="S8e", workdir="/w", claude_cmd="c", run=fr8e)
check(t8e.start() is False and fr8e.subs() == ["new-session"] and t8e.last_error == "duplicate session",
      f"8: new-session 失敗は False・大きさのコマンドは呼ばない {fr8e.subs()} {t8e.last_error!r}")
# 8-f. Bridge の薄い入口：self.tmux へそのまま渡す
fr8f = FakeRun()
br8 = B.Bridge("/home/x/my_proj/q8", session="S8f", tmux=B.TmuxControl(session="S8f", run=fr8f))
check(br8.send_keys("Up", "Enter") is True and fr8f.cmds() == [["tmux", "send-keys", "-t", "S8f", "Up", "Enter"]], f"8: Bridge.send_keys {fr8f.cmds()}")
fr8f.calls.clear()
check(br8.send_literal("xy") is True and fr8f.cmds() == [["tmux", "send-keys", "-t", "S8f", "-l", "xy"]], f"8: Bridge.send_literal {fr8f.cmds()}")
fr8f.fail["send-keys"] = (1, "x")
check(br8.send_keys("Up") is False and br8.send_literal("a") is False, "8: Bridge の入口は tmux の失敗をそのまま返す")

# ---------------------------------------------------------------------------
# 9. 言語（pca_i18n）：英語のとき、見せる文・エラー文が英語になる。終わったら ja に戻す
# ---------------------------------------------------------------------------
set_lang("en")
try:
    pd = B.prompt_display("<local-command-stdout></local-command-stdout>")
    check(pd == ("(no output)", True), f"9: 中身が空なら「(no output)」 {pd!r}")
    pd = B.prompt_display("<task-notification><task-id>a</task-id></task-notification>")
    check(pd == ("[notice] Subagent notification", True), f"9: どちらも無ければ英語の決まり文句 {pd!r}")
    pd = B.prompt_display("<task-notification><summary>done x</summary></task-notification>")
    check(pd == ("[notice] done x", True), f"9: 英語の知らせの頭 {pd!r}")
    br9 = B.Bridge.__new__(B.Bridge)
    try:
        B.Bridge.begin(br9, "bad")
        raised9 = ""
    except ValueError as e9:
        raised9 = str(e9)
    check("mode must be new, resume or restart" in raised9, f"9: begin の不正な mode のエラーが英語 {raised9!r}")
finally:
    set_lang("ja")
pd = B.prompt_display("<local-command-stdout></local-command-stdout>")
check(pd == ("(出力なし)", True) and get_lang() == "ja", f"9: ja に戻すと日本語 {pd!r}")

# ---------------------------------------------------------------------------
# 結果
# ---------------------------------------------------------------------------
print(f"（一時フォルダ {RUN_DIR}）")
if fail:
    print(f"\n失敗 {len(fail)} 件（全 {n_checks} 項目）:")
    for f in fail:
        print(" -", f)
    sys.exit(1)
print(f"{n_checks} 項目 全部成功")
sys.exit(0)
