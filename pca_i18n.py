"""画面の表示と Claude へ送る文の、日本語・英語の切り替え。

言語は起動のときに1回だけ決める（set_lang）。各所は t("キー") で文を引く。
"""
import os
from collections.abc import Mapping

LANGS: tuple[str, ...] = ("ja", "en")
_lang: str = "ja"

MESSAGES: dict[str, dict[str, str]] = {
    # 画面の文・Claude へ送る文
    "handoff_prompt": {
        "ja": "今日の作業の引き継ぎメモを書いてください。",
        "en": "Please write a handoff memo for today's work.",
    },
    "dialog_resume": {"ja": "1: 続きから", "en": "1: Continue"},
    "dialog_restart": {"ja": "2: 前のを終わらせて新しく始める", "en": "2: End the previous one and start new"},
    "dialog_cancel": {"ja": "3: やめる", "en": "3: Cancel"},
    "dialog_title": {"ja": "前のセッションが残っています", "en": "A previous session is still running"},
    "perm_wait_note": {
        "ja": "(許可の答えを待っています。送信は止めています)",
        "en": "(Waiting for a permission answer. Sending is paused)",
    },
    "perm_keys": {"ja": "Y:許可  N:断る  T:tmuxで答える", "en": "Y:Allow  N:Deny  T:Answer in tmux"},
    "perm_keys_always": {
        "ja": "Y:許可  A:いつも許可  N:断る  T:tmuxで答える",
        "en": "Y:Allow  A:Always allow  N:Deny  T:Answer in tmux",
    },
    "perm_always_confirm": {
        "ja": "もう一度 A:いつも許可する  ほかのキー:やめる",
        "en": "A again: Always allow  Other key: Cancel",
    },
    "perm_always_question": {"ja": "いつも許可しますか？", "en": "Always allow this?"},
    "scope_local": {
        "ja": "作業フォルダの設定（.claude/settings.local.json）",
        "en": "work folder settings (.claude/settings.local.json)",
    },
    "scope_project": {
        "ja": "作業フォルダの共有の設定（.claude/settings.json）",
        "en": "work folder shared settings (.claude/settings.json)",
    },
    "scope_user": {
        "ja": "あなたの全体の設定（~/.claude/settings.json）",
        "en": "your user settings (~/.claude/settings.json)",
    },
    "scope_session": {"ja": "このセッションだけ", "en": "this session only"},
    "menu_guide": {
        "ja": "↑↓:選ぶ  Enter:決める  Esc:やめる（選んだ値は新しいセッションの既定にも保存されます）",
        "en": "↑↓:Select  Enter:OK  Esc:Cancel (the choice is also saved as the default for new sessions)",
    },
    "slash_guide_panel": {
        "ja": "キーは Claude Code に送られます（Esc で閉じる）",
        "en": "Keys are sent to Claude Code (Esc to close)",
    },
    "slash_guide_static": {"ja": "Esc・Enter・クリックで閉じる", "en": "Esc, Enter or click to close"},
    "err_seat_yaw": {"ja": "seat_yaw は 0 か 180 のみ対応: {value}", "en": "seat_yaw must be 0 or 180: {value}"},
    "err_desk_seat": {
        "ja": "机の数と席の数が一致しない",
        "en": "The number of desks and seats do not match",
    },
    "talk_page_guide": {"ja": "↑↓:前後のやりとり", "en": "↑↓:Previous/next exchange"},
    "err_spot_reserved": {
        "ja": "人 {index} は既に行き先を予約している",
        "en": "Agent {index} has already reserved a destination",
    },
    "err_request_timeout": {"ja": "依頼の時間切れ", "en": "Request timed out"},
    "err_peer_closed": {"ja": "相手が閉じた", "en": "The other side closed the connection"},
    "err_request_too_long": {"ja": "依頼が長すぎる", "en": "Request is too long"},
    "perm_server_busy": {
        "ja": "許可の受け取りを使えません（ほかで使用中）",
        "en": "Cannot receive permission requests (already in use elsewhere)",
    },
    "err_request_not_dict": {"ja": "依頼が辞書でない", "en": "Request is not a dict"},
    "err_unknown_kind": {"ja": "種類が不明", "en": "Unknown kind"},
    "suggest_accept_edits": {
        "ja": "このセッションの間、ファイルの編集を聞かずに許す",
        "en": "Allow file edits without asking for this session",
    },
    "suggest_set_mode": {
        "ja": "このセッションの間、許可のモードを {mode} にする",
        "en": "Set the permission mode to {mode} for this session",
    },
    "suggest_destination": {"ja": "（保存先：{destination}）", "en": " (saved to: {destination})"},
    "suggest_add_rules": {"ja": "次の決まりを {where} に足す：{names}", "en": "Add these rules to {where}: {names}"},
    "suggest_add_dirs": {
        "ja": "次のフォルダを作業の範囲に足す：{shown}",
        "en": "Add this folder to the working directories: {shown}",
    },
    "list_sep": {"ja": "、", "en": ", "},
    "perm_input_label": {"ja": "入力", "en": "Input"},
    "err_layout": {"ja": "layout は {choices} のどれか: {value}", "en": "layout must be one of {choices}: {value}"},
    "hist_esc_interrupt": {"ja": "(Esc: 中断を送る)", "en": "(Esc: sends an interrupt)"},
    "hist_no_exit": {
        "ja": "(/exit・/quit は使えません。終わるときは F1 で終業してください)",
        "en": "(/exit and /quit are disabled. To finish, press F1 to clock out)",
    },
    "hist_not_started": {
        "ja": "(始業していません。F1 で始業してください)",
        "en": "(Not clocked in. Press F1 to clock in)",
    },
    "hist_usage_reading": {
        "ja": "(利用制限を読んでいます。終わったら送ります)",
        "en": "(Reading usage limits. Will send when done)",
    },
    "hist_start_resumed": {
        "ja": "始業：前のセッションにつなぎました",
        "en": "Clocked in: reconnected to the previous session",
    },
    "hist_start_new": {"ja": "始業：Claude Code を起動しました", "en": "Clocked in: started Claude Code"},
    "hist_start_failed": {"ja": "始業できませんでした：{error}", "en": "Could not clock in: {error}"},
    "hist_ending": {
        "ja": "終業：引き継ぎメモを書いてもらっています",
        "en": "Clocking out: asking for a handoff memo",
    },
    "hist_ended": {"ja": "終業しました", "en": "Clocked out"},
    "hist_claude_exited": {"ja": "Claude Code が終了しました", "en": "Claude Code has exited"},
    "log_handoff_wait": {
        "ja": "引き継ぎメモを待っています（最大{sec}秒）…",
        "en": "Waiting for the handoff memo (up to {sec} s)…",
    },
    "log_handoff_received": {"ja": "引き継ぎメモを受け取りました", "en": "Received the handoff memo"},
    "log_handoff_timeout": {"ja": "待ち時間を過ぎたので閉じます", "en": "Timed out; closing"},
    "log_usage_send_failed": {
        "ja": "利用制限：/usage を送れませんでした",
        "en": "Usage: could not send /usage",
    },
    "hist_unsent_prompts": {
        "ja": "(送れなかったプロンプトがあります)",
        "en": "(Some prompts could not be sent)",
    },
    "log_usage_timeout": {
        "ja": "利用制限：{sec} 秒たっても読めませんでした（前の値のまま）",
        "en": "Usage: could not read after {sec} s (keeping the previous values)",
    },
    "log_usage_not_closed": {
        "ja": "利用制限：/usage の画面が閉じませんでした",
        "en": "Usage: the /usage screen did not close",
    },
    "hist_perm_unavailable": {
        "ja": "(注意：許可の受け取りが使えません。許可は tmux に出て、送信も止まりません)",
        "en": "(Note: permission requests cannot be received here. They will appear in tmux, and sending will not pause)",
    },
    "hist_perm_timeout": {
        "ja": "(許可の答えが時間切れ。tmux で答えてください：{summary})",
        "en": "(Permission answer timed out. Answer in tmux: {summary})",
    },
    "hist_perm_withdrawn": {
        "ja": "(許可の依頼が取り下げられました：{summary})",
        "en": "(Permission request withdrawn: {summary})",
    },
    "hist_perm_went_to_main": {
        "ja": "(許可の依頼が来たので、メインのところへ行きました)",
        "en": "(A permission request arrived, so you walked to Main)",
    },
    "hist_perm_click_main": {
        "ja": "(許可の依頼が来ました。メインの近くに立つ場所が無いので、メインをクリックしてください)",
        "en": "(A permission request arrived. There is no free spot near Main, so click Main)",
    },
    "hist_perm_to_walk": {
        "ja": "(許可の依頼が来たので、WALK に切り替えました。入力中の文字は残っています)",
        "en": "(A permission request arrived, so switched to WALK. Your typed text is kept)",
    },
    "hist_answer_in_tmux": {"ja": "tmux で答えてください：{summary}", "en": "Answer in tmux: {summary}"},
    "hist_allowed": {"ja": "許可しました：{summary}", "en": "Allowed: {summary}"},
    "hist_denied": {"ja": "断りました：{summary}", "en": "Denied: {summary}"},
    "hist_answer_not_delivered": {
        "ja": "(答えが届きませんでした。tmux で答えてください：{summary})",
        "en": "(The answer was not delivered. Answer in tmux: {summary})",
    },
    "hist_always_allowed": {"ja": "いつも許可しました：{summary}", "en": "Always allowed: {summary}"},
    "slash_read_failed": {"ja": "(画面を読めませんでした)", "en": "(Could not read the screen)"},
    "slash_command_label": {"ja": "コマンド：", "en": "Command: "},
    "menu_title_model": {"ja": "モデルを選ぶ", "en": "Select model"},
    "menu_title_effort": {"ja": "effort を選ぶ", "en": "Select effort"},
    "main_name": {"ja": "メイン", "en": "Main"},
    "dialog_main_page": {"ja": "メイン  {page}/{total}", "en": "Main  {page}/{total}"},
    "talk_none_yet": {"ja": "(まだ話していません)", "en": "(No conversation yet)"},
    "talk_waiting_reply": {"ja": "(返事を待っています)", "en": "(Waiting for a reply)"},
    "perm_asking": {"ja": "許可を求めています（残り {count} 件）", "en": "Asking for permission ({count} left)"},
    "perm_tool": {"ja": "道具：{name}", "en": "Tool: {name}"},
    "subagent_name": {"ja": "サブエージェント", "en": "Subagent"},
    "hist_called": {"ja": "  [呼ばれた] {label}: {desc}", "en": "  [called] {label}: {desc}"},
    "button_clock_out": {"ja": "[F1] 終業", "en": "[F1] Clock out"},
    "button_clock_in": {"ja": "[F1] 始業", "en": "[F1] Clock in"},
    "status_model": {"ja": "現在のモデル:{model}  effort:{effort}", "en": "Model:{model}  effort:{effort}"},
    "ime_converting": {"ja": "変換中", "en": "Converting"},
    "notice_prefix": {"ja": "[知らせ] ", "en": "[notice] "},
    "notice_subagent": {"ja": "[知らせ] サブエージェントの知らせ", "en": "[notice] Subagent notification"},
    "err_tmux_failed": {"ja": "tmux 失敗 {code}: {args}", "en": "tmux failed {code}: {args}"},
    "notice_no_output": {"ja": "(出力なし)", "en": "(no output)"},
    "err_watch_failed": {"ja": "見張りを始められない: {error}", "en": "Could not start watching: {error}"},
    "err_bridge_mode": {
        "ja": "mode は new・resume・restart のどれか: {value}",
        "en": "mode must be new, resume or restart: {value}",
    },
    "err_no_session": {"ja": "つなぐセッションが無い", "en": "No session to connect to"},
    # 起動オプションの説明（--help）
    "arg_fps": {"ja": "目標 FPS（1〜60）", "en": "Target FPS (1-60)"},
    "arg_seed": {"ja": "乱数の種（省略可）", "en": "Random seed (optional)"},
    "arg_layout": {
        "ja": "配置（office: 製品版の配置、席18。既定 / proto: 試作・テスト用の机3つ。--claude は使えない）",
        "en": "Layout (office: the full office, 18 seats, default / proto: a small prototype with 3 desks for testing; --claude cannot be used)",
    },
    "err_claude_needs_office": {
        "ja": "--claude は --layout office のときだけ使えます",
        "en": "--claude can only be used with --layout office",
    },
    "arg_agents": {
        "ja": "人数（既定は18。席の数より多いときは席の数にする。office は1〜18、proto は1〜3）",
        "en": "Number of agents (default 18; capped at the number of seats. office: 1-18, proto: 1-3)",
    },
    "arg_config": {
        "ja": "設定ファイル（省略時は pyxelcube_agents.py と同じフォルダの pyxelcube_agents.toml）",
        "en": "Config file (default: pyxelcube_agents.toml next to pyxelcube_agents.py)",
    },
    "arg_speed": {
        "ja": "行き先・会話のタイマーの早回し倍率（0 以下は 1.0）。歩く速さは変わらない",
        "en": "Speed-up factor for destination and talk timers (0 or less means 1.0). Walking speed does not change",
    },
    "arg_claude": {
        "ja": "本物の Claude Code とつなぐ（office の既定。つながずに眺めるだけなら --no-claude。proto では使えない。F1 で始業・終業）",
        "en": "Connect to the real Claude Code (default for office; use --no-claude to just watch without connecting; not available with proto. F1 to clock in/out)",
    },
    "arg_workdir": {
        "ja": "Claude Code を動かすフォルダ（省略時はこのファイルと同じフォルダの pca_work。例：~/projects/myapp。許可の hook は起動のときに --settings で渡すので、作業フォルダの設定は変えなくてよい）",
        "en": "Folder to run Claude Code in (default: pca_work next to this file, e.g. ~/projects/myapp. The permission hook is passed with --settings at launch, so the folder's settings need no change)",
    },
    "arg_session": {"ja": "tmux のセッション名", "en": "tmux session name"},
    "arg_lang": {
        "ja": "表示の言語（ja / en。省略時は環境変数 LANG などから決める）",
        "en": "Display language (ja / en. Default: decided from LANG and related environment variables)",
    },
}


def detect_lang(environ: Mapping[str, str] | None = None) -> str:
    """環境変数 LC_ALL → LC_MESSAGES → LANG の順に、空でない最初のものを見る。"ja" で始まれば "ja"、それ以外（空も含む）は "en"。"""
    env: Mapping[str, str] = os.environ if environ is None else environ
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(name, "")
        if value:
            return "ja" if value.startswith("ja") else "en"
    return "en"


def set_lang(lang: str) -> None:
    """使う言語を決める。LANGS に無い値は ValueError。"""
    global _lang
    if lang not in LANGS:
        raise ValueError(f"lang は {list(LANGS)} のどれか: {lang!r}")
    _lang = lang


def get_lang() -> str:
    """いまの言語を返す。"""
    return _lang


def t(key: str, **kwargs: object) -> str:
    """キーの文を、いまの言語で返す。kwargs があれば str.format で差し込む。キーが無ければ KeyError。"""
    text = MESSAGES[key][_lang]
    return text.format(**kwargs) if kwargs else text
