"""Pyxel Cube で作る小さな3Dオフィスの試作。

3人のキャラクターが自分の席の周りをうろつき、スペースキーで順に作業状態へ切り替わる。
行動の計算は描画しない Agent、3D の描画は Node 継承クラスに分けている。
キャラは肩・肘・足の付け根・膝が曲がる人型で、姿勢は Pose にまとめる。
起動例: python pyxelcube_agents.py --fps 30 --seed 1
本番に近い配置: python pyxelcube_agents.py --layout office --agents 18
office の配置には、左・右・手前の壁、REST ROOM のドア（D キーで開閉）、奥の壁の掲示板、書棚・観葉植物・丸テーブルを置く。
利用制限の値は設定ファイル pyxelcube_agents.toml（--config で変更可）の json_path から読む。キー 1〜4 で手動に変えられる。
office では、キャラが席を離れて行き先（コーヒー・書棚・植木）へ道を探して行き、1人か会話で過ごして席へ戻る。
道は障害物を避けて A* で探す。--time-scale で行き先と会話の時間だけを早回しできる（歩く速さは変わらない）。
"""

import argparse
import atexit
import heapq
import json
import math
import queue
import random
import re
import select
import shlex
import socket
import struct
import threading
import time
import tomllib
import unicodedata
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pyxel
from pyxel.cube import Camera, Mat4, Node, Shading, Vec3

from pca_bridge import Bridge, Prompt, Reply, SubagentEnd, SubagentStart, Tool, TurnEnd, _tool_summary, prompt_display
from pca_perm_hook import socket_name as perm_socket_name
from pca_splash import Splash
from pca_i18n import LANGS, detect_lang, get_lang, set_lang, t

# アプリの名前と版（窓の題・起動時の表示に使う）
APP_NAME = "pyxelcube_agents"
APP_VERSION = "0.90"

# 許可の hook のスクリプト（pca_perm_hook.py の絶対パス）
HOOK_PATH = Path(__file__).resolve().with_name("pca_perm_hook.py")


def hook_settings_json(hook_path: Path) -> str:
    """claude --settings に渡す hook の設定（JSON の文字列）を返す。許可（PermissionRequest）と通知（Notification）の2つ。

    作業フォルダの設定ファイルは変えず、起動のときだけ hook を足す。コマンドのパスは shlex.quote で囲む。
    """
    command = "python3 -I " + shlex.quote(str(Path(hook_path).resolve()))
    settings = {
        "hooks": {
            "PermissionRequest": [
                {"matcher": "*", "hooks": [{"type": "command", "command": command + " PermissionRequest", "timeout": 330}]}
            ],
            "Notification": [
                {"matcher": "*", "hooks": [{"type": "command", "command": command + " Notification", "timeout": 10}]}
            ],
        }
    }
    return json.dumps(settings, ensure_ascii=False)


def claude_command(hook_path: Path, lang: str = "ja") -> str:
    """tmux の new-session で起動する claude のコマンド文字列を返す。

    tmux は最後の引数をシェルで解釈するため、JSON の文字列を shlex.quote で囲む。
    言語は環境変数 PCA_LANG で hook に渡す（hook のコマンドを変えないため。コマンドが同じなら作業フォルダの設定に同じ hook があっても1回しか呼ばれない）。
    """
    return "PCA_LANG=" + shlex.quote(lang) + " claude --settings " + shlex.quote(hook_settings_json(hook_path))

# 画面サイズ（ピクセル）
SCREEN_W = 256
SCREEN_H = 192

# 状態を表す文字列定数
WANDER = "WANDER"  # 待機（席の周りをうろつく）
WORKING = "WORKING"  # 作業中（席に戻って座る）
GOING = "GOING"  # 行き先へ向かう（office だけ）
AT_SPOT = "AT_SPOT"  # 行き先の立つ場所にいる（office だけ）
RETURNING = "RETURNING"  # 行き先から席へ戻る（office だけ）
LEAVING = "LEAVING"  # 部屋から出ていく（--claude のとき、ドアの内側まで歩く）

# 床の範囲（x と z）。単位は 100 単位 = 1m
FLOOR_X_MIN = -380.0
FLOOR_X_MAX = 380.0
FLOOR_Z_MIN = -280.0
FLOOR_Z_MAX = 280.0

# うろつきの z の下限。机の手前の面 z=-70 より手前に限り、机をすり抜けないようにする
WANDER_Z_MIN = -50.0

# 行動のパラメータ
WANDER_RADIUS = 120.0  # うろつく半径（単位）
WANDER_SPEED = 60.0  # うろつくときの速さ（単位/秒）
WORK_SPEED = 120.0  # 席へ戻る速さ（単位/秒）
WAIT_MIN = 1.0  # 立ち止まる時間の最小（秒）
WAIT_MAX = 3.0  # 立ち止まる時間の最大（秒）
WORK_HOLD_SEC = 5.0  # 席に着いてから WANDER に戻るまでの時間（秒）

# 当たり判定（床を上から見た x-z 平面。高さは見ない）
AGENT_RADIUS = 14.0  # キャラの半径（腕を含めた体の幅に合わせる）
STUCK_RATIO = 0.3  # 予定の距離のこの割合より進めなければ「進めないフレーム」とみなす
STUCK_SEC = 1.0  # 進めないフレームがこの時間続いたら、新しい目標を選び直す（秒）
TARGET_TRIES = 20  # うろつきの目標を障害物を避けて選ぶ最大回数
COLLISION_ITERATIONS = 3  # 1フレームに「障害物→人どうし」の押し出しを繰り返す回数

# 机と床の寸法・色
DESK_XS = (-250.0, 0.0, 250.0)
DESK_Y = 19.0  # 机の中心の高さ。机の外形の高さ 38 の半分
DESK_Z = -100.0
DESK_SIZE = Vec3(120.0, 38.0, 60.0)  # 机の外形（天板＋左右の側板）
DESK_COLOR = 13  # 机の天板と側板の色。Pyxel 既定パレットの 13 番 A3A3A3（灰色）
# 天板と側板の寸法・位置。x・z は机の中心からの位置、y は床からの高さ
DESK_TOP_SIZE = Vec3(120.0, 4.0, 60.0)
DESK_TOP_Y = 36.0  # 天板の中心の高さ（天板の上面は 38）
DESK_SIDE_SIZE = Vec3(4.0, 34.0, 60.0)
DESK_SIDE_Y = 17.0  # 側板の中心の高さ（床から 0〜34）
DESK_SIDE_X = DESK_SIZE.x / 2.0 - DESK_SIDE_SIZE.x / 2.0  # 側板の中心の x（机の中心から左右 ±58）
FLOOR_CENTER = Vec3(0.0, -5.0, 0.0)
FLOOR_SIZE = Vec3(800.0, 10.0, 600.0)
FLOOR_COLOR = 1

# 席の位置（机の手前）
SEAT_Z = -30.0

# 椅子の寸法（席の位置が原点、yaw=0 で -Z が前＝机の方）
CHAIR_SEAT_CENTER = Vec3(0.0, 14.0, -25.0)  # 座面の中心（人が引いて座る位置。机の方へ 25 ずれる）
CHAIR_SEAT_SIZE = Vec3(30.0, 4.0, 30.0)
CHAIR_BACK_CENTER = Vec3(0.0, 31.0, -10.0)  # 背もたれの中心（座面の後ろ側）
CHAIR_BACK_SIZE = Vec3(30.0, 30.0, 4.0)
CHAIR_COLOR = 4  # 椅子の座面と背もたれの色。Pyxel 既定パレットの 4 番

# 肌の色。頭と両腕に使う（Pyxel 既定パレットの 15 番 EDC7B0、うすい肌色）
SKIN_COLOR = 15

# キャラの見た目の寸法（キャラのローカル座標。足の裏が y=0、yaw=0 で -Z が前）
HIP_X = 7.0  # 脚の付け根の x（左右は ±）
HIP_Y = 40.0  # 脚の付け根の高さ
THIGH_LEN = 20.0  # 太ももの長さ
THIGH_THICK = 10.0  # 太ももの太さ
SHIN_LEN = 20.0  # すねの長さ
SHIN_THICK = 9.0  # すねの太さ
BODY_CENTER = Vec3(0.0, 53.0, 0.0)  # 胴の中心（y=40〜66）
BODY_SIZE = Vec3(28.0, 26.0, 16.0)
HEAD_CENTER = Vec3(0.0, 75.0, 0.0)  # 頭の中心（y=66〜84）
HEAD_SIZE = Vec3(18.0, 18.0, 18.0)
SHOULDER_X = 18.0  # 肩の x（左右は ±）
SHOULDER_Y = 64.0  # 肩の高さ
UPPER_ARM_LEN = 16.0  # 上腕の長さ
UPPER_ARM_THICK = 8.0  # 上腕の太さ
FOREARM_LEN = 15.0  # 前腕の長さ
FOREARM_THICK = 7.0  # 前腕の太さ

# 座ったときに足の裏を床に付けるための体全体の上下のずらし
SIT_BODY_Y = -20.0
# 座ったときに体を前（-Z 側）へずらす量。人が椅子を机の方へ引いて座り、肩が机の縁に届くようにする
SIT_BODY_Z = -25.0

# 関節の角度の範囲（度）
SHOULDER_RANGE = (-60.0, 150.0)
ELBOW_RANGE = (0.0, 150.0)
HIP_RANGE = (-60.0, 120.0)
KNEE_RANGE = (0.0, 150.0)

STRIDE = 40.0  # 歩幅（単位）。この距離進むと歩行の位相が1周期（2π）進む
TYPING_PERIOD_SEC = 0.3  # 作業中にキーボードを打つ動きの周期（秒）

# 行き先（office だけ）の時間・くじの重み・身ぶり
OUTING_WANDER_SEC = 5.0  # うろつきの時間がこれを超えたら、行き先を選ぶ（秒）
OUTING_COOLDOWN_SEC = 60.0  # 席へ戻ったあと、次に出かけるまでの休み（秒）
ALONE_SEC = 30.0  # 行き先に1人でいる時間（秒）。過ぎたら席へ戻る
TALK_SEC = 60.0  # 行き先で会話している時間（秒）。過ぎたら席へ戻る
SPEAKER_MIN_SEC = 4.0  # 話し手を交代するまでの時間の最小（秒）
SPEAKER_MAX_SEC = 6.0  # 話し手を交代するまでの時間の最大（秒）
GESTURE_MIN_SEC = 2.0  # 話し手が身ぶりを選び直すまでの時間の最小（秒）
GESTURE_MAX_SEC = 4.0  # 話し手が身ぶりを選び直すまでの時間の最大（秒）
LISTEN_MIN_SEC = 3.0  # 聞き手が姿勢を選び直すまでの時間の最小（秒）
LISTEN_MAX_SEC = 6.0  # 聞き手が姿勢を選び直すまでの時間の最大（秒）
SPOT_WEIGHT_COFFEE = 50.0  # 行き先のくじの重み（コーヒー）
SPOT_WEIGHT_SHELF = 25.0  # 行き先のくじの重み（書棚2つ合わせて）
SPOT_WEIGHT_PLANT = 25.0  # 行き先のくじの重み（植木2つ合わせて）
KIND_COFFEE = "coffee"
KIND_SHELF = "shelf"
KIND_PLANT = "plant"
GESTURE_BOTH_UP = "BOTH_UP"  # 身ぶり：両手を上げる
GESTURE_POINT_LISTENER = "POINT_LISTENER"  # 身ぶり：片手を聞き手に向ける
GESTURE_POINT_DESK = "POINT_DESK"  # 身ぶり：メインの机を指す
GESTURE_KINDS: tuple[str, ...] = (GESTURE_BOTH_UP, GESTURE_POINT_LISTENER, GESTURE_POINT_DESK)

# 行き先の位置。center は体を向ける先、slots は立つ場所の (x, z)
SPOT_COFFEE_CENTER = (0.0, 180.0)
SPOT_COFFEE_RADIUS = 80.0  # 立つ場所の円の半径（丸テーブルの外側）
SPOT_COFFEE_ANGLES = (0.0, 60.0, 120.0, 180.0, 240.0, 300.0)  # 立つ場所の角度（度）
SPOT_SHELF_L_CENTER = (-700.0, -580.0)
SPOT_SHELF_L_SLOTS = ((-740.0, -538.0), (-700.0, -538.0), (-660.0, -538.0))
SPOT_SHELF_R_CENTER = (700.0, -580.0)
SPOT_SHELF_R_SLOTS = ((660.0, -538.0), (700.0, -538.0), (740.0, -538.0))
SPOT_PLANT_L_CENTER = (-740.0, 540.0)
SPOT_PLANT_L_SLOTS = ((-686.0, 540.0), (-740.0, 486.0))
SPOT_PLANT_R_CENTER = (740.0, 540.0)
SPOT_PLANT_R_SLOTS = ((686.0, 540.0), (740.0, 486.0))

# 道探し（office だけ）
NAV_CELL = 20.0  # 道探しのマス目の大きさ（単位）
NAV_MARGIN = 4.0  # 障害物から余分に離す距離（単位。AGENT_RADIUS に足す）
NAV_MAX_PER_FRAME = 1  # 1フレームに道を探す人数の上限（超えた人は列で順番を待つ）
NAV_PERSON_RADIUS = 2.0 * AGENT_RADIUS  # 道探しで人をよける半径（人の中心どうしの距離）
NAV_NEAR_DIST = 60.0  # 引っかかって道を探し直すとき、この距離より近い人も障害物に入れる
SIDESTEP_AFTER = 3  # 引っかかりがこの回数続いたら横へよける
SIDESTEP_SEC = 1.0  # 横へよける時間（秒）
SIDESTEP_PROBE = 30.0  # よける向きを選ぶとき、この距離先が通れるかを調べる
SQRT2 = math.sqrt(2.0)
NEIGHBORS_8 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
# 8方向の (di, dj, 斜めか, 移動の距離)。A* の内側の繰り返しで使う
NAV_STEPS = tuple(
    (di, dj, di != 0 and dj != 0, SQRT2 if di != 0 and dj != 0 else 1.0)
    for di, dj in NEIGHBORS_8
)
WORK_PATH_MIN_DIST = 150.0  # 席からこれより遠いとき、作業に戻る道を探す（単位）
DEFAULT_TIME_SCALE = 1.0  # 時間の早回し倍率の既定値（行き先・会話のタイマーだけに効く）

# 人間（ユーザーの分身。office だけ）
HUMAN_SKIN_COLOR = 7  # 人間の頭と腕（白）
HUMAN_BODY_COLOR = 8  # 人間の胴と脚（赤紫 #D4186C）
HUMAN_START = (0.0, 40.0)  # 人間の最初の位置 (x, z)。島の左右の列の間・丸テーブルより奥
HUMAN_SPEED = WORK_SPEED  # 人間の歩く速さ（単位/秒）
MARKER_COLOR = 10  # 頭の上の▼の色（金 #E9C35B）。陰影なしで描く
MARKER_Y = 104.0  # ▼の中心の高さ
MARKER_BOB = 4.0  # ▼が上下に揺れる幅（±）
MARKER_BOB_SEC = 1.2  # 揺れの周期（秒）
MARKER_HALF = 7.0  # ▼の上面の正方形の半分の幅
MARKER_DEPTH = 14.0  # ▼の高さ（上面から下の頂点まで）
PICK_CENTER_Y = 45.0  # クリックでエージェントを選ぶ球の中心の高さ
PICK_RADIUS = 30.0  # その球の半径
TALK_FRONT_GAP = 60.0  # 座っている相手の机の中心から、机の正面に立つ位置までの距離
TALK_SIDE_DIST = 60.0  # 相手のまわりに立つ位置を探すときの距離
TALK_DIRECTIONS = 12  # 相手のまわりに立つ位置を探す方向の数
HEAD_YAW_LIMIT = 70.0  # 座っている相手が頭だけを回す角度の上限（度、左右とも）
TALK_CAM_PITCH = 25.0  # 会話のカメラの見下ろす角度（度）
TALK_CAM_MIN_DIST = 320.0  # 会話のカメラの距離の下限
TALK_CAM_DIST_RATIO = 2.5  # 会話のカメラの距離＝2人の間の距離×この値（下限あり）
TALK_CAM_TARGET_Y = 45.0  # 会話のカメラが見る高さ（胸のあたり）
CAM_BLEND_SEC = 0.5  # カメラの切り替えにかける時間（秒）
FOLLOW_RATE = 6.0  # ふだんのカメラが人間を追う速さ（大きいほど速い。1 - exp(-FOLLOW_RATE*dt) で近づく）
FOLLOW_REPLAN_SEC = 1.0  # 会話相手が歩いているとき、人間が道を探し直す間隔（秒）
TALK_CLEAR = 12.0  # 会話で立つ位置は、相手以外の人から 2*AGENT_RADIUS + この値 以上離す（重なって見えないように）
TALK_MIN_SCREEN_GAP = 24.0  # 会話のカメラで、2人の頭の画面上の横の差がこれ以上になるようにする（画面の点）
TALK_YAW_OFFSETS = (20.0, -20.0, 40.0, -40.0)  # 会話のカメラの yaw をずらして試す量（度、この順）

# office の画面の配分（3D の範囲と、下の履歴・入力欄）。proto は 256×192 のまま
OFFICE_SCREEN_W = 640
OFFICE_SCREEN_H = 500
OFFICE_DISPLAY_SCALE = 2
VIEW3D_H = 296  # 3D を描く範囲の高さ（0,0,640,296）
UI_FONT_PATH = Path(pyxel.__file__).parent / "examples" / "assets" / "PixelMplus12-Regular.ttf"
UI_FONT_SIZE = 12
UI_LINE_H = 14  # 1行の高さ
UI_CHAR_W = 6  # 半角1文字の幅（全角は12）
UI_PAD = 6
HISTORY_ROWS = 9
INPUT_ROWS = 3
INPUT_TEXT_ROWS_CLAUDE = 2  # --claude のとき入力の文字を見せる行数（いちばん下の行は今のモデルと effort）
HISTORY_MAX = 500  # 履歴に残す行数の上限（古い行から捨てる）
SCROLLBAR_W = 6
HISTORY_X = 4
HISTORY_Y = VIEW3D_H + 4
HISTORY_W = 632
HISTORY_H = HISTORY_ROWS * UI_LINE_H + UI_PAD * 2
INPUT_Y = HISTORY_Y + HISTORY_H + 4
INPUT_H = INPUT_ROWS * UI_LINE_H + UI_PAD * 2
UI_COLS = (HISTORY_W - UI_PAD * 2 - SCROLLBAR_W - 2) // UI_CHAR_W  # 1行の桁数（全角は2桁）
COMPOSING_LABEL_RIGHT = 620  # 「変換中」の札の右端の x（スクロールバーの溝 x 624〜629 より左）

# モード（office だけ）。WALK は3Dの操作、PROMPT は文字の入力
MODE_WALK = "WALK"
MODE_PROMPT = "PROMPT"
# WALK → PROMPT のキー。PROMPT → WALK は Ctrl+E（_prompt_exit_pressed）
PROMPT_ENTER_KEY = pyxel.KEY_P
# 日本語入力（fcitx5＋mozc）の「変換中」の推測。実機で分かった事実：
# - 日本語入力がオンのとき、英字キーを押しても pyxel.input_text は来ない（変換中の文字は窓の外に出る）
# - 変換中に押した Enter・Backspace・Esc は、日本語入力が使うのと同時に Pyxel にも届く
# - 確定の Enter は、Enter の次のフレームに確定した文字が input_text で届く
# - 日本語入力がオフのとき、英字は押したフレームに input_text で届く
IME_GRACE_FRAMES = 1  # 英字キーを押してから、文字が届くのを待つフレーム数
IME_ENTER_WAIT = 2  # Enter のあと、確定した文字が届くのを待つフレーム数
# 日本語入力がオンのとき、押しても文字が届かないキー（英字と数字とマイナス）
IME_PRINTABLE_KEYS: tuple[int, ...] = tuple(
    getattr(pyxel, f"KEY_{c}") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
) + (pyxel.KEY_MINUS,)

# キャラの設定（名前, 色, 机のx）。席は机の手前。
AGENT_SETUP: tuple[tuple[str, int, float], ...] = (
    ("A", 8, DESK_XS[0]),
    ("B", 11, DESK_XS[1]),
    ("C", 12, DESK_XS[2]),
)

# office（本番に近い配置）の寸法
OFFICE_FLOOR_CENTER = Vec3(0.0, -5.0, 0.0)
OFFICE_FLOOR_SIZE = Vec3(1600.0, 10.0, 1200.0)
OFFICE_WALL_CENTER = Vec3(0.0, 100.0, -605.0)
OFFICE_WALL_SIZE = Vec3(1600.0, 200.0, 10.0)
OFFICE_WALL_COLOR = 5
# office のキャラの色。床1・椅子4・壁5・机13・肌15 を避ける。席番号の順に繰り返す
OFFICE_AGENT_COLORS = (2, 3, 6, 7, 8, 9, 10, 11, 12, 14)
OFFICE_WANDER_X = (-780.0, 780.0)  # うろつきの x の範囲
OFFICE_WANDER_Z = (-580.0, 580.0)  # うろつきの z の範囲
OFFICE_CAMERA_EYE = Vec3(0.0, 1100.0, 1300.0)

# office の窓際の机（z=-430）と、その席（z=-500、机と壁の間）
WINDOW_DESK_XS = (-150.0, 150.0)
WINDOW_DESK_Z = -430.0
WINDOW_SEAT_Z = -500.0

# office の島（中心 (cx, cz)）と、島の中の机の位置（中心からのずれ）
ISLAND_CENTERS = ((-450.0, -20.0), (450.0, -20.0), (-450.0, 380.0), (450.0, 380.0))
ISLAND_DESK_OFFSETS = ((-62.0, -32.0), (62.0, -32.0), (-62.0, 32.0), (62.0, 32.0))
ISLAND_SEAT_OFFSET = 100.0  # 島の机から席までの距離（z 方向）

# office の壁（左・右・手前）。色は OFFICE_WALL_COLOR
OFFICE_LEFT_WALL_CENTER = Vec3(-805.0, 100.0, 0.0)
OFFICE_RIGHT_WALL_CENTER = Vec3(805.0, 100.0, 0.0)
OFFICE_SIDE_WALL_SIZE = Vec3(10.0, 200.0, 1220.0)
OFFICE_FRONT_WALL_CENTER = Vec3(0.0, 22.5, 605.0)  # 手前の壁は低い
OFFICE_FRONT_WALL_SIZE = Vec3(1620.0, 45.0, 10.0)

# REST ROOM のドア（左の壁に付く）。蝶番は奥側の端 (DOOR_X, 0, DOOR_Z - DOOR_WIDTH/2)
DOOR_Z = -350.0  # ドアの中心の z
DOOR_WIDTH = 80.0  # ドアの幅（閉じたとき +Z 方向へ伸びる長さ）
DOOR_HEIGHT = 160.0
DOOR_THICK = 6.0
DOOR_X = -797.0  # 壁の内側の面 x=-800 のすぐ内側
DOOR_COLOR = 9
DOOR_OPEN_ANGLE = 90.0  # 開いたときの角度（度）
DOOR_SPEED = 180.0  # 開け閉めの速さ（度/秒）
DOOR_SIGN_Y = 175.0  # ドアの上の札の中心の高さ（動かない）
DOOR_SIGN_SIZE = Vec3(4.0, 16.0, 70.0)
SIGN_COLOR = 7
# ドアが回る範囲の当たり判定（x の範囲と、z の中心からの半分の幅）。ドアが開いても閉じても障害物
DOOR_AREA_X = (-800.0, -720.0)
DOOR_AREA_HALF_Z = 40.0

# office の奥の壁の掲示板（利用制限の棒グラフ）。文字は描かない
BOARD_CENTER = Vec3(0.0, 145.0, -598.0)
BOARD_SIZE = Vec3(240.0, 70.0, 2.0)
BOARD_COLOR = 7
BAR_MAX_LEN = 200.0  # 100% のときの棒の長さ
BAR_LEFT_X = -100.0  # 棒の左端の x
BAR_Z = -596.0  # 板より手前
BAR_DEPTH = 2.0
BAR_HEIGHT = 14.0
FIVE_HOUR_BAR_Y = 160.0
FIVE_HOUR_BAR_COLOR = 10
WEEK_BAR_Y = 128.0
WEEK_BAR_COLOR = 8
BAR_FRAME_W = 2.0  # 100% の枠の太さ（棒の外側に置く細い箱）
BAR_FRAME_COLOR = 0  # 枠の色（黒。白い板の上で目立つ）
# 利用制限を /usage の画面から読む（--claude のとき）
USAGE_COMMAND = "/usage"  # 送るコマンド
USAGE_POLL_SEC = 0.2  # 画面を読む間隔（秒）
USAGE_CLOSE_SEC = 2.0  # 画面が閉じるまで待つ時間（秒）。残れば Escape をもう一度送る
USAGE_TIMEOUT_SEC = 5.0  # 値が取れるまでの上限（秒）
USAGE_AFTER_TURN_SEC = 1.0  # メインの返事の終わりから読むまでの時間（秒）
# Claude Code の画面（会話記録）が英語で出ることを前提にしている。Claude Code の language 設定で変わるのは返事の言語だけ（2.1.330 で確認）。画面が翻訳される版が出たら、ここを直す
USAGE_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)% used")  # 画面の「NN% used」

# office の小物：書棚・観葉植物・丸テーブル・コーヒーメーカー
BOOKSHELF_XS = (-700.0, 700.0)
BOOKSHELF_Y = 90.0  # 本体の中心の高さ（床から 0〜180）
BOOKSHELF_Z = -580.0
BOOKSHELF_SIZE = Vec3(120.0, 180.0, 36.0)
BOOKSHELF_COLOR = 4
BOOK_Z = -560.0  # 本の段は本体の手前に少し出す
BOOK_SIZE = Vec3(110.0, 30.0, 4.0)
BOOK_YS = (40.0, 90.0, 140.0)  # 本の段の中心の高さ（下から）
BOOK_COLORS = (12, 11, 10)
PLANT_POSITIONS = ((-740.0, 540.0), (740.0, 540.0))
PLANT_POT_SIZE = Vec3(40.0, 40.0, 40.0)
PLANT_POT_Y = 20.0
PLANT_POT_COLOR = 9
PLANT_LEAF_Y = 70.0
PLANT_LEAF_RADIUS = 30.0
PLANT_LEAF_COLOR = 3
PLANT_HALF = 30.0  # 当たり判定の半分の幅（x・z とも）
TABLE_X = 0.0
TABLE_Z = 180.0
TABLE_RADIUS = 50.0  # 天板の半径
TABLE_Y = 72.0  # 天板の高さ
TABLE_COLOR = 13
TABLE_LEG_SIZE = Vec3(10.0, 72.0, 10.0)
TABLE_LEG_Y = 36.0
TABLE_BASE_Y = 1.0
TABLE_BASE_DIAMETER = 50.0
COFFEE_BODY_SIZE = Vec3(24.0, 32.0, 18.0)
COFFEE_BODY_COLOR = 0
COFFEE_LAMP_POS = Vec3(8.0, TABLE_Y + 34.0, 171.0)
COFFEE_LAMP_SIZE = Vec3(4.0, 4.0, 4.0)
COFFEE_LAMP_COLOR = 8

# 利用制限（掲示板の棒）の設定。設定ファイルが無い・壊れているときの既定値
DEFAULT_CONFIG_PATH = Path(__file__).resolve().with_name("pyxelcube_agents.toml")
DEFAULT_RATE_JSON_PATH = "~/.cache/pixel_office/rate_limits.json"
DEFAULT_RELOAD_SEC = 3.0
RATE_KEY_STEP = 10.0  # キー 1〜4 で一度に変える量（%）


# 本物の Claude Code とつなぐ（--claude のときだけ使う）
PARK_X = -900.0  # 見えていない人の置き場所（REST ROOM の中。z はドアの z）
ENTER_INSIDE_X = DOOR_AREA_X[1] + 20.0  # ドアの内側の点の x（部屋の中）
SUB_LEAVE_SEC = 300.0  # サブエージェントが仕事を終えてから帰るまで（秒）。その間はうろうろする
IDLE_LEAVE_SEC = 600.0  # メインが作業を止めて帰るまで（秒。tmux は動かしたまま）
HANDOFF_WAIT_SEC = 300.0  # 終業（と窓の×）で引き継ぎメモを待つ時間（秒）
SESSION_CHECK_SEC = 2.0  # 始業している間、Claude Code のセッションがあるかを確かめる間隔（秒）
HANDOFF_PROMPT = "handoff_prompt"
BUBBLE_SEC = 6.0  # 吹き出しを出す時間（秒）
BUBBLE_CHARS = 24  # 吹き出しに出す文字数（それより長ければ「…」）
DOOR_IDLE_CLOSE_SEC = 2.0  # 出入りが終わってからドアを閉めるまで（秒）
SUB_SLOT_FIRST = 2  # サブエージェントの席の番号の範囲（この番号から）
SUB_SLOT_END = 18  # 同（この番号の手前まで）
BUTTON_Y = 40  # 始業・終業のボタンの高さ
DEFAULT_PCA_WORKDIR = Path(__file__).resolve().with_name("pca_work")  # Claude Code を動かすフォルダ
MAIN_INDEX = 0  # メイン（Claude Code の本体につながる人）の番号
CLAUDE_TALK_PANEL_W = 200  # 話しかけたときの様子の札の幅（今は使っていない。製品版では右上の札を描かない）
LEAVE_ARRIVE_DIST = 30.0  # 部屋を出る人は、出口の点からこの距離以内に入れば着いたことにする
LEAVE_MAX_SEC = 40.0  # 部屋を出ようとして、これだけ続いたら、その場で置き場所へ戻す（念のため）
# ダイアログの選び方（キーの 1〜3 とクリック）。空の文字列は「やめる」
CLAUDE_DIALOG_OPTIONS: tuple[tuple[str, str], ...] = (
    ("resume", "dialog_resume"),
    ("restart", "dialog_restart"),
    ("", "dialog_cancel"),
)
# 許可の依頼（hook から届く）。PERM_WAIT_SEC は hook の待ち（300 秒）より短くして、hook が先に切れたあとに Y が押せないようにする
PERM_WAIT_SEC = 290.0
PERM_KEY_GUARD_SEC = 0.5  # 自動でワープしたあと Y・N・T を受け付けない時間（秒）。直前に押していたキーで答えてしまわないように
PERM_KEY_GUARD_PROMPT_SEC = 1.0  # 入力欄で打っている最中に自動で WALK に切り替えたときの、Y・N・T を受け付けない時間（秒）。打ちかけの y などで答えてしまわないように長めにする
PERM_ACCEPT_SEC = 0.3  # 待ち受けの accept を止められるか確かめる間隔（秒）
PERM_READ_SEC = 2.0  # 接続して依頼の1行を読むまでの時間（秒）
PERM_MAX_LINE = 65536  # 依頼の1行の最大バイト数
PERM_WAIT_NOTE = "perm_wait_note"
PERM_KEYS_TEXT = "perm_keys"
PERM_KEYS_ALWAYS_TEXT = "perm_keys_always"  # 案（permission_suggestions）がある依頼の案内
PERM_ALWAYS_CONFIRM_TEXT = "perm_always_confirm"  # 「いつも許可」の確かめの案内
PERM_ALWAYS_QUESTION = "perm_always_question"  # 確かめの1行目（黄色）
PERM_ALWAYS_COLOR = 10  # 黄色（確かめの文と案内）
PERM_SUGGEST_COLOR = 13  # 灰色（履歴に出す案の行）
# 案の保存先の言葉。ここに無いものはそのまま出す
PERM_RULE_SCOPE: dict[str, str] = {
    "localSettings": "scope_local",
    "projectSettings": "scope_project",
    "userSettings": "scope_user",
    "session": "scope_session",
}
# 確かめの間に押されたら、確かめをやめるキー・マウスのボタン（A 以外の全部）
PERM_CANCEL_BUTTONS: tuple[int, ...] = tuple(
    getattr(pyxel, name)
    for name in dir(pyxel)
    if name.startswith(("KEY_", "MOUSE_BUTTON_")) and name != "KEY_A"
)
# 会話のダイアログ（3D の範囲の下寄り。x 16〜624、y 170〜288。3D は y 0〜295。上の絵が見えるように下に置く）
# 背景だけ半透明（pyxel.dither(0.5)）、枠・文字・スクロールバーは通常の濃さで描く。高さ 119 は行数の計算（DLG_BODY_ROWS など）にも使う
DLG_X = 16
DLG_Y = 170
DLG_W = 608
DLG_H = 119
DLG_COLS = (DLG_W - UI_PAD * 2 - SCROLLBAR_W - 2) // UI_CHAR_W  # 中身の1行の桁数
DLG_WHEEL_ROWS = 3  # ホイール1ノッチで動かす行数
DLG_BODY_ROWS = (DLG_H - UI_PAD * 2) // UI_LINE_H  # 中身が出せる行数（最後の行を除く前）

# 今のモデルと effort（--claude のとき。画面の文字から読む・/model と /effort の結果から覚える）
STATE_READ_SEC = 15.0  # 始業したあと、画面から今のモデルを読む時間（秒）。見つかったら読むのをやめる
STATE_READ_EVERY_SEC = 0.5  # 画面を読む間隔（秒）
# Claude Code の画面（会話記録）が英語で出ることを前提にしている。Claude Code の language 設定で変わるのは返事の言語だけ（2.1.330 で確認）。画面が翻訳される版が出たら、ここを直す
STATE_RE = re.compile(r"(Opus|Sonnet|Fable|Haiku) (\d+(?:\.\d+)?)(?: with (\w+) effort)?")  # 画面の表示行（例 Opus 5.5 with medium effort）
SET_MODEL_RE = re.compile(r"(?:Set model to|Kept model as) `([^`]+)`")  # 会話記録の /model の結果
SET_EFFORT_RE = re.compile(r"Set effort level to (\w+)")  # 会話記録の /effort の結果
STATE_DEFAULT_EFFORT = "medium"  # 画面に effort の表示が無いときの既定
# 選ぶメニュー（--claude のとき、入力欄に「/model」「/effort」だけを送ったら出す）。(表示名, 送る引数)
MENU_MODEL_CHOICES: tuple[tuple[str, str], ...] = (
    ("Default", "default"),
    ("Opus 5.5", "claude-opus-5-5"),
    ("Sonnet 5.5", "claude-sonnet-5-5"),
    ("Fable 5.2", "claude-fable-5-2"),
    ("Haiku 5.5", "claude-haiku-5-5"),
)
MENU_EFFORT_CHOICES: tuple[tuple[str, str], ...] = (
    ("low", "low"),
    ("medium", "medium"),
    ("high", "high"),
    ("xhigh", "xhigh"),
    ("max", "max"),
)
MENU_GUIDE = "menu_guide"

# コマンドの窓（SLASH）。--claude で「/」で始まる文を送ったあとに、3D の範囲の中（MODE の札の下）へ出す
SLASH_X = 16
SLASH_Y = 22
SLASH_W = 608
SLASH_H = 268  # y 22〜289
SLASH_POLL_SEC = 0.25  # 画面を読む間隔（秒）
SLASH_CLOSE_SEC = 0.5  # パネルの案内が消えてから閉じるまで（秒）
SLASH_STATIC_SEC = 2.0  # パネルを一度も見ないまま、結果だけの窓に切り替えるまで（秒）
SLASH_DITHER = 0.75  # 背景を少し透かす（pyxel.dither の値）
SLASH_COLS = (SLASH_W - UI_PAD * 2 - SCROLLBAR_W - 2) // UI_CHAR_W  # 画面の行の1行の桁数
SLASH_BODY_ROWS = (SLASH_H - UI_PAD * 2) // UI_LINE_H - 2  # 画面の行が出せる行数（1行目はコマンド、最後は案内）
SLASH_EXIT_CMDS = ("/exit", "/quit")  # この文は窓を出さない（_send_input で BLOCKED_CMDS に止められるので、今は届かない。そのまま残す）
# --claude のとき、Claude Code に送らせない文（終わるときは F1 の終業を使う）
BLOCKED_CMDS = ("/exit", "/quit")


def _is_blocked_command(text: str) -> bool:
    """送る文が BLOCKED_CMDS か（前後の空白を除き、小文字にして、先頭の語が /exit・/quit のとき。「/exit now」も含む。「/exits」「/exit2」は含まない）。"""
    parts = text.strip().lower().split(maxsplit=1)
    return bool(parts) and parts[0] in BLOCKED_CMDS
SLASH_GUIDE_PANEL = "slash_guide_panel"
SLASH_GUIDE_STATIC = "slash_guide_static"
# 窓の中で tmux へ送るキー：(pyxel のキー, tmux のキー名, 押しっぱなしで繰り返すか)
SLASH_KEYS: tuple[tuple[int, str, bool], ...] = (
    (pyxel.KEY_UP, "Up", True),
    (pyxel.KEY_DOWN, "Down", True),
    (pyxel.KEY_LEFT, "Left", True),
    (pyxel.KEY_RIGHT, "Right", True),
    (pyxel.KEY_RETURN, "Enter", False),
    (pyxel.KEY_KP_ENTER, "Enter", False),
    (pyxel.KEY_ESCAPE, "Escape", False),
    (pyxel.KEY_TAB, "Tab", False),
    (pyxel.KEY_BACKSPACE, "BSpace", True),
    (pyxel.KEY_SPACE, "Space", False),
    (pyxel.KEY_PAGEUP, "PPage", True),
    (pyxel.KEY_PAGEDOWN, "NPage", True),
)


@dataclass(frozen=True)
class Layout:
    """配置の定義。床・壁・机・席・うろつきの範囲・カメラをまとめる。"""

    floor_center: Vec3
    floor_size: Vec3
    desks: tuple[Vec3, ...]  # 机の中心の一覧
    walls: tuple[tuple[Vec3, Vec3, int], ...]  # 壁の (中心, 大きさ, 色)
    seats: tuple[tuple[Vec3, float, int], ...]  # 席の (位置, 座ったときの yaw, キャラの色)
    wander_x: tuple[float, float]  # うろつきの x の範囲
    wander_z: tuple[float, float]  # うろつきの z の範囲
    camera_eye: Vec3
    camera_target: Vec3
    zoom_min: float  # マウスホイールで寄れる最短のカメラ距離
    zoom_max: float  # マウスホイールで引ける最長のカメラ距離
    has_props: bool = False  # 壁・ドア・掲示板・小物・丸い障害物を置くか（office だけ True）


def _office_color(index: int) -> int:
    """office の席番号 index のキャラの色。床・机・壁・肌と重ならない色を、順に繰り返して割り当てる。"""
    return OFFICE_AGENT_COLORS[index % len(OFFICE_AGENT_COLORS)]


def _office_desks() -> tuple[Vec3, ...]:
    """office の机の中心の一覧。窓際2つ、続いて島4つ×4つ。"""
    desks = [Vec3(x, DESK_Y, WINDOW_DESK_Z) for x in WINDOW_DESK_XS]
    for cx, cz in ISLAND_CENTERS:
        for dx, dz in ISLAND_DESK_OFFSETS:
            desks.append(Vec3(cx + dx, DESK_Y, cz + dz))
    return tuple(desks)


def _office_seats() -> tuple[tuple[Vec3, float, int], ...]:
    """office の席の一覧（位置, 座ったときの yaw, 色）。窓際2つ→島の16席の順。

    yaw 180 は +Z（部屋の方）、yaw 0 は -Z（机の方）を向く。
    """
    raw: list[tuple[Vec3, float]] = [
        (Vec3(x, 0.0, WINDOW_SEAT_Z), 180.0) for x in WINDOW_DESK_XS
    ]
    for cx, cz in ISLAND_CENTERS:
        for dx, dz in ISLAND_DESK_OFFSETS:
            if dz < 0.0:
                # 奥の列の机は、机の奥側（-Z 側）に席を置き +Z を向く
                raw.append((Vec3(cx + dx, 0.0, cz - ISLAND_SEAT_OFFSET), 180.0))
            else:
                # 手前の列の机は、机の手前側（+Z 側）に席を置き -Z を向く
                raw.append((Vec3(cx + dx, 0.0, cz + ISLAND_SEAT_OFFSET), 0.0))
    return tuple((seat, yaw, _office_color(i)) for i, (seat, yaw) in enumerate(raw))


PROTO_LAYOUT = Layout(
    floor_center=FLOOR_CENTER,
    floor_size=FLOOR_SIZE,
    desks=tuple(Vec3(desk_x, DESK_Y, DESK_Z) for desk_x in DESK_XS),
    walls=(),
    seats=tuple(
        (Vec3(desk_x, 0.0, SEAT_Z), 0.0, color) for _, color, desk_x in AGENT_SETUP
    ),
    wander_x=(FLOOR_X_MIN, FLOOR_X_MAX),
    wander_z=(WANDER_Z_MIN, FLOOR_Z_MAX),
    camera_eye=Vec3(0.0, 450.0, 650.0),
    camera_target=Vec3(0.0, 0.0, -50.0),
    zoom_min=120.0,
    zoom_max=1500.0,
)

OFFICE_LAYOUT = Layout(
    floor_center=OFFICE_FLOOR_CENTER,
    floor_size=OFFICE_FLOOR_SIZE,
    desks=_office_desks(),
    walls=(
        (OFFICE_WALL_CENTER, OFFICE_WALL_SIZE, OFFICE_WALL_COLOR),
        (OFFICE_LEFT_WALL_CENTER, OFFICE_SIDE_WALL_SIZE, OFFICE_WALL_COLOR),
        (OFFICE_RIGHT_WALL_CENTER, OFFICE_SIDE_WALL_SIZE, OFFICE_WALL_COLOR),
        (OFFICE_FRONT_WALL_CENTER, OFFICE_FRONT_WALL_SIZE, OFFICE_WALL_COLOR),
    ),
    seats=_office_seats(),
    wander_x=OFFICE_WANDER_X,
    wander_z=OFFICE_WANDER_Z,
    camera_eye=OFFICE_CAMERA_EYE,
    camera_target=Vec3(0.0, 0.0, -50.0),
    zoom_min=150.0,
    zoom_max=3000.0,
    has_props=True,
)

LAYOUTS: dict[str, Layout] = {"proto": PROTO_LAYOUT, "office": OFFICE_LAYOUT}


@dataclass(frozen=True)
class Spot:
    """行き先1つ。kind は KIND_COFFEE・KIND_SHELF・KIND_PLANT のどれか。

    center は体を向ける先、slots は立つ場所 (x, z) の一覧。上限人数は slots の数。
    """

    name: str
    kind: str
    center: tuple[float, float]
    slots: tuple[tuple[float, float], ...]


def _office_spots() -> tuple[Spot, ...]:
    """office の行き先の一覧。コーヒー1つ、書棚2つ、植木2つ。コーヒーの立つ場所は中心の円の上に並べる。"""
    coffee_slots = tuple(
        (
            SPOT_COFFEE_CENTER[0] + SPOT_COFFEE_RADIUS * math.cos(math.radians(angle)),
            SPOT_COFFEE_CENTER[1] + SPOT_COFFEE_RADIUS * math.sin(math.radians(angle)),
        )
        for angle in SPOT_COFFEE_ANGLES
    )
    return (
        Spot("coffee", KIND_COFFEE, SPOT_COFFEE_CENTER, coffee_slots),
        Spot("shelf_l", KIND_SHELF, SPOT_SHELF_L_CENTER, SPOT_SHELF_L_SLOTS),
        Spot("shelf_r", KIND_SHELF, SPOT_SHELF_R_CENTER, SPOT_SHELF_R_SLOTS),
        Spot("plant_l", KIND_PLANT, SPOT_PLANT_L_CENTER, SPOT_PLANT_L_SLOTS),
        Spot("plant_r", KIND_PLANT, SPOT_PLANT_R_CENTER, SPOT_PLANT_R_SLOTS),
    )


OFFICE_SPOTS = _office_spots()


@dataclass(frozen=True)
class Rect:
    """床を上から見た、軸にそった長方形（x と z の範囲）。"""

    xmin: float
    xmax: float
    zmin: float
    zmax: float


@dataclass(frozen=True)
class Obstacle:
    """障害物1つ。owner は席の番号（机と椅子は席 i の持ち物）。壁は None。"""

    rect: Rect
    owner: int | None


def _desk_rect(desk_center: Vec3) -> Rect:
    """机の中心から、机の外形の半分ずつ広げた長方形。"""
    half_x = DESK_SIZE.x / 2.0
    half_z = DESK_SIZE.z / 2.0
    return Rect(
        desk_center.x - half_x,
        desk_center.x + half_x,
        desk_center.z - half_z,
        desk_center.z + half_z,
    )


def _chair_rect(seat: Vec3, seat_yaw: float) -> Rect:
    """席の椅子（座面と背もたれをまとめた）長方形。

    席のローカル座標の範囲を、席の向きに合わせて世界の座標にする。
    seat_yaw は 0（-Z が前）か 180（+Z が前）だけを扱う。
    """
    half_x = CHAIR_SEAT_SIZE.x / 2.0  # 座面の左右の半分（背もたれも同じ幅）
    local_z_min = CHAIR_SEAT_CENTER.z - CHAIR_SEAT_SIZE.z / 2.0  # 座面の奥の端（-40）
    local_z_max = CHAIR_BACK_CENTER.z + CHAIR_BACK_SIZE.z / 2.0  # 背もたれの手前の端（-8）
    if seat_yaw == 0.0:
        z_min = seat.z + local_z_min
        z_max = seat.z + local_z_max
    elif seat_yaw == 180.0:
        # 180 度回すと z の向きが反転する（x は左右対称なので変わらない）
        z_min = seat.z - local_z_max
        z_max = seat.z - local_z_min
    else:
        raise ValueError(t("err_seat_yaw", value=repr(seat_yaw)))
    return Rect(seat.x - half_x, seat.x + half_x, z_min, z_max)


def _wall_rect(wall_center: Vec3, wall_size: Vec3) -> Rect:
    """壁の中心と大きさから作る長方形。"""
    half_x = wall_size.x / 2.0
    half_z = wall_size.z / 2.0
    return Rect(
        wall_center.x - half_x,
        wall_center.x + half_x,
        wall_center.z - half_z,
        wall_center.z + half_z,
    )


def _build_obstacles(layout: Layout) -> list[Obstacle]:
    """配置の机・椅子・壁から障害物の一覧を作る。机 i と椅子 i は席 i の持ち物（owner = i）。"""
    if len(layout.desks) != len(layout.seats):
        raise ValueError(t("err_desk_seat"))
    obstacles: list[Obstacle] = []
    for i, desk_center in enumerate(layout.desks):
        obstacles.append(Obstacle(_desk_rect(desk_center), i))
    for i, (seat, seat_yaw, _) in enumerate(layout.seats):
        obstacles.append(Obstacle(_chair_rect(seat, seat_yaw), i))
    for wall_center, wall_size, _ in layout.walls:
        obstacles.append(Obstacle(_wall_rect(wall_center, wall_size), None))
    if layout.has_props:
        # ドアが回る範囲は、ドアが開いていても閉じていても障害物にする
        door_rect = Rect(
            DOOR_AREA_X[0], DOOR_AREA_X[1], DOOR_Z - DOOR_AREA_HALF_Z, DOOR_Z + DOOR_AREA_HALF_Z
        )
        obstacles.append(Obstacle(door_rect, None))
        for shelf_x in BOOKSHELF_XS:
            shelf_rect = _rect_from_center(
                shelf_x, BOOKSHELF_Z, BOOKSHELF_SIZE.x / 2.0, BOOKSHELF_SIZE.z / 2.0
            )
            obstacles.append(Obstacle(shelf_rect, None))
        for plant_x, plant_z in PLANT_POSITIONS:
            plant_rect = _rect_from_center(plant_x, plant_z, PLANT_HALF, PLANT_HALF)
            obstacles.append(Obstacle(plant_rect, None))
    return obstacles


def _rect_from_center(cx: float, cz: float, half_x: float, half_z: float) -> Rect:
    """中心 (cx, cz) から、x と z のそれぞれ half_x・half_z の半分ずつ広げた長方形。"""
    return Rect(cx - half_x, cx + half_x, cz - half_z, cz + half_z)


def _build_circles(layout: Layout) -> list[tuple[float, float, float]]:
    """配置の丸い障害物（中心の x, z, 半径）の一覧。丸いものは has_props の配置（丸テーブル）だけ。"""
    if not layout.has_props:
        return []
    return [(TABLE_X, TABLE_Z, TABLE_RADIUS)]

TEXT_COLOR = 7
NOTICE_COLOR = 13  # 決まった形の知らせ（コマンドの結果・サブエージェントの知らせ）を履歴に出す灰色
TALK_PROMPT_COLOR = 6  # 会話のダイアログのプロンプトの青（黒い背景で読みやすい明るい青。Pyxel の既定パレット 6 = #A9C1FF）
TALK_PAGE_MAX = 200  # 会話のダイアログで覚えるやりとりのページの数（超えたら古いものから捨てる）
TALK_PAGE_GUIDE = "talk_page_guide"  # ページが2つ以上あるとき、ダイアログの一番下に出す案内

# ズーム（マウスホイール）。1ノッチごとの距離の倍率と、遠方クリップの余裕（単位）
ZOOM_STEP = 0.9
FAR_MARGIN = 2500.0

# カーソルキーで視点を回す。速さ（毎秒の度）と、見下ろす角度（pitch）の範囲（度）
CAM_YAW_SPEED = 90.0
CAM_PITCH_SPEED = 60.0
CAM_PITCH_MIN = 10.0
CAM_PITCH_MAX = 85.0


def _clamp(value: float, low: float, high: float) -> float:
    """値を low〜high の範囲に収める。"""
    return min(max(value, low), high)


def push_out_of_rect(
    x: float, z: float, r: float, rect: Rect
) -> tuple[float, float]:
    """半径 r の円（中心 (x, z)）が長方形に重なっていれば、重ならない位置まで最短の向きに押し出した (x, z) を返す。

    重なっていなければ、元の (x, z) をそのまま返す。
    中心が長方形の中にあるときは、いちばん近い辺の外へ押し出す。
    """
    # 長方形の中で、円の中心にいちばん近い点
    cx = _clamp(x, rect.xmin, rect.xmax)
    cz = _clamp(z, rect.zmin, rect.zmax)
    dx = x - cx
    dz = z - cz
    dist_sq = dx * dx + dz * dz
    if dist_sq >= r * r:
        return (x, z)
    if dist_sq > 0.0:
        # 外から重なっている。近い点から中心へ向かう向きに、半径 r の位置まで出す
        dist = math.sqrt(dist_sq)
        return (cx + dx / dist * r, cz + dz / dist * r)
    # 中心が長方形の中にある。いちばん近い辺から r だけ外へ出す
    left = x - rect.xmin
    right = rect.xmax - x
    down = z - rect.zmin
    up = rect.zmax - z
    nearest = min(left, right, down, up)
    if nearest == left:
        return (rect.xmin - r, z)
    if nearest == right:
        return (rect.xmax + r, z)
    if nearest == down:
        return (x, rect.zmin - r)
    return (x, rect.zmax + r)


def push_out_of_circle(
    x: float, z: float, r: float, cx: float, cz: float, cr: float
) -> tuple[float, float]:
    """半径 r の円（中心 (x, z)）が、中心 (cx, cz)・半径 cr の円に重なっていれば、距離 r+cr の位置まで外へ押し出した (x, z) を返す。

    重なっていなければ、元の (x, z) をそのまま返す。中心が完全に同じときは +X へ押し出す。
    """
    dx = x - cx
    dz = z - cz
    dist = math.hypot(dx, dz)
    limit = r + cr
    if dist >= limit:
        return (x, z)
    if dist > 0.0:
        return (cx + dx / dist * limit, cz + dz / dist * limit)
    # 中心が同じ。x 方向に押し出す
    return (cx + limit, cz)


def _as_finite_float(value: object) -> float | None:
    """bool を除く数なら有限の float にして返す。数でない・NaN・無限大・大きすぎる値は None。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def load_rate_settings(config_path: Path) -> tuple[str, float]:
    """設定ファイルから (json_path, reload_sec) を読む。ファイルが無い・壊れている・項目が無いときは既定値を使う。"""
    json_path = DEFAULT_RATE_JSON_PATH
    reload_sec = DEFAULT_RELOAD_SEC
    try:
        with config_path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, ValueError):
        return (json_path, reload_sec)
    section = data.get("rate_limits")
    if not isinstance(section, dict):
        return (json_path, reload_sec)
    path_value = section.get("json_path")
    if isinstance(path_value, str) and path_value:
        json_path = path_value
    sec = _as_finite_float(section.get("reload_sec"))
    if sec is not None and sec > 0.0:
        reload_sec = sec
    return (json_path, reload_sec)


def _parse_usage(lines: list[str]) -> tuple[float | None, float | None, str | None, str | None]:
    """/usage の画面の行から、5時間と週間の使った割合（%）と、その次の「Resets」の行を取る。

    見出し（Current session・Current week）の次の行から探し、次の見出しの前までに限る。見つからないものは None。
    """
    results: list[tuple[float | None, str | None]] = []
    # Claude Code の画面（会話記録）が英語で出ることを前提にしている。Claude Code の language 設定で変わるのは返事の言語だけ（2.1.330 で確認）。画面が翻訳される版が出たら、ここを直す
    for title in ("Current session", "Current week"):
        pct: float | None = None
        reset: str | None = None
        start = next((i for i, line in enumerate(lines) if title in line), None)
        if start is not None:
            for line in lines[start + 1 :]:
                if "Current " in line:
                    break  # 次の見出しに入った
                if pct is None:
                    found = USAGE_PCT_RE.search(line)
                    if found is not None:
                        pct = float(found.group(1))
                elif "Resets" in line:
                    reset = line.strip()
                    break
        results.append((pct, reset))
    (five, reset_5h), (week, reset_week) = results
    return five, week, reset_5h, reset_week


def _read_used_percentage(data: object, key: str) -> float:
    """data[key]["used_percentage"] を 0〜100 に収めた値で返す。項目が無い・数でないときは 0.0。"""
    if not isinstance(data, dict):
        return 0.0
    item = data.get(key)
    if not isinstance(item, dict):
        return 0.0
    number = _as_finite_float(item.get("used_percentage"))
    if number is None:
        return 0.0
    return _clamp(number, 0.0, 100.0)


def separate(
    ax: float,
    az: float,
    bx: float,
    bz: float,
    r: float,
    a_fixed: bool,
    b_fixed: bool,
) -> tuple[float, float, float, float]:
    """半径とも r の2つの円が重なっていたら引き離し、(ax, az, bx, bz) を返す。

    両方動けるなら半分ずつ動かす。片方が固定なら、もう片方だけ全部動かす。
    両方固定なら動かさない。中心が完全に同じなら x 方向に引き離す。
    """
    dx = bx - ax
    dz = bz - az
    dist = math.hypot(dx, dz)
    overlap = 2.0 * r - dist
    if overlap <= 0.0:
        return (ax, az, bx, bz)
    if a_fixed and b_fixed:
        return (ax, az, bx, bz)

    if dist > 0.0:
        nx = dx / dist
        nz = dz / dist
    else:
        # 中心が同じ。x 方向に引き離す
        nx = 1.0
        nz = 0.0

    if a_fixed:
        return (ax, az, bx + nx * overlap, bz + nz * overlap)
    if b_fixed:
        return (ax - nx * overlap, az - nz * overlap, bx, bz)
    half = overlap / 2.0
    return (ax - nx * half, az - nz * half, bx + nx * half, bz + nz * half)


def _view_dir(yaw: float, pitch: float) -> Vec3:
    """カメラの目の方向の単位ベクトル。yaw は Y軸まわりの向き（度）、pitch は水平からの見下ろし角（度、90 で真上）。

    yaw=0 のとき +Z 側から見る（目は +Z 側にある）。
    """
    yaw_rad = math.radians(yaw)
    pitch_rad = math.radians(pitch)
    return Vec3(
        math.cos(pitch_rad) * math.sin(yaw_rad),
        math.sin(pitch_rad),
        math.cos(pitch_rad) * math.cos(yaw_rad),
    )


def facing_yaw(fx: float, fz: float, tx: float, tz: float, default: float = 0.0) -> float:
    """(fx, fz) から (tx, tz) の方を向くときの yaw（度）。_step_toward と同じ式を使う。同じ点なら default を返す。"""
    dx = tx - fx
    dz = tz - fz
    if dx == 0.0 and dz == 0.0:
        return default
    return math.degrees(math.atan2(-dx, -dz))


class NavGrid:
    """床を NAV_CELL のマス目に分け、障害物を避ける道を A* で探す。作るのは App の初期化で1回だけ。

    マスの中心が、障害物を AGENT_RADIUS + NAV_MARGIN だけ広げた範囲に入るマスは通れない。
    """

    def __init__(
        self,
        x_range: tuple[float, float],
        z_range: tuple[float, float],
        rects: list[Rect],
        circles: list[tuple[float, float, float]],
    ) -> None:
        """床の範囲（x・z）と障害物（長方形・丸）から、通れるマスの表を作る。"""
        self.x0: float = x_range[0]
        self.z0: float = z_range[0]
        # find_path の探している間だけ、よける人の中心（x, z）の列を入れる。普段は空
        self._tmp_people: Sequence[tuple[float, float]] = ()
        self.nx: int = max(1, math.ceil((x_range[1] - x_range[0]) / NAV_CELL))
        self.nz: int = max(1, math.ceil((z_range[1] - z_range[0]) / NAV_CELL))
        margin = AGENT_RADIUS + NAV_MARGIN
        # 人の半径と余白ぶん広げた障害物（点がこの中に入ると、人の中心を置けない）
        self._boxes: list[tuple[float, float, float, float]] = [
            (r.xmin - margin, r.xmax + margin, r.zmin - margin, r.zmax + margin) for r in rects
        ]
        self._round: list[tuple[float, float, float]] = [
            (cx, cz, cr + margin) for cx, cz, cr in circles
        ]
        # 点の判定を速くするため、マス目と同じ大きさの箱ごとに、その箱に重なる障害物を覚える。
        # 空の箱は空のタプルを共有するので、メモリはほとんど増えない
        size = self.nx * self.nz
        boxes_in: list[list[tuple[float, float, float, float]]] = [[] for _ in range(size)]
        round_in: list[list[tuple[float, float, float]]] = [[] for _ in range(size)]
        for box in self._boxes:
            i0, j0 = self._cell_of(box[0], box[2])
            i1, j1 = self._cell_of(box[1], box[3])
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    boxes_in[j * self.nx + i].append(box)
        for rnd in self._round:
            i0, j0 = self._cell_of(rnd[0] - rnd[2], rnd[1] - rnd[2])
            i1, j1 = self._cell_of(rnd[0] + rnd[2], rnd[1] + rnd[2])
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    round_in[j * self.nx + i].append(rnd)
        self._bucket_boxes: list[tuple[tuple[float, float, float, float], ...]] = [
            tuple(b) for b in boxes_in
        ]
        self._bucket_round: list[tuple[tuple[float, float, float], ...]] = [
            tuple(b) for b in round_in
        ]
        # 通れるマスの表。添え字は j * nx + i（j は z の列、i は x の列）。1 が通れる、0 が通れない。
        # マスの中心が置けるかで決める
        self._free_cells: bytearray = bytearray(size)
        for j in range(self.nz):
            for i in range(self.nx):
                cx, cz = self._centre(i, j)
                self._free_cells[j * self.nx + i] = 1 if self._point_free(cx, cz) else 0

    def find_path(
        self,
        start_xz: tuple[float, float],
        goal_xz: tuple[float, float],
        people: Sequence[tuple[float, float]] = (),
    ) -> list[tuple[float, float]] | None:
        """start_xz から goal_xz までの道の点の列を返す。道が無ければ None。

        スタートかゴールのマスが通れないときは、いちばん近い通れるマスを使う。
        点の列は、まっすぐ行ける先の点まで飛ばしたもの。最後の点は goal_xz そのもの。
        goal_xz へ直線で行けないときは、最後のマスの中心を残して、その後ろに goal_xz を足す。
        それも行けないときは、最後の点をゴールのマスの中心にする。
        people は、ほかの人の中心 (x, z) の列。人の中心から NAV_PERSON_RADIUS 未満のマスと直線は通らない。
        people をよけて道が見つからなければ、people なしでもう一度探す。
        """
        if people:
            points = self._find_path_avoiding(start_xz, goal_xz, people)
            if points is not None:
                return points
        return self._find_path_avoiding(start_xz, goal_xz, ())

    def _find_path_avoiding(
        self,
        start_xz: tuple[float, float],
        goal_xz: tuple[float, float],
        people: Sequence[tuple[float, float]],
    ) -> list[tuple[float, float]] | None:
        """find_path の本体。探している間だけ self._tmp_people に people を入れ、戻るときは必ず空に戻す。"""
        self._tmp_people = people
        try:
            start_cell = self._nearest_free(*self._cell_of(*start_xz))
            goal_raw = self._cell_of(*goal_xz)
            goal_cell = self._nearest_free(*goal_raw)
            if start_cell is None or goal_cell is None:
                return None
            if start_cell == goal_cell:
                return [self._centre(*goal_cell)]
            blocked = self._blocked_by_people(people, start_cell, goal_cell)
            cells = self._astar(start_cell, goal_cell, blocked)
            if cells is None:
                return None
            points = self._simplify([self._centre(i, j) for i, j in cells])
            # 最後の点は goal_xz。直線で行けないときは、かわりの点を使う（docstring のとおり）
            if len(points) >= 2 and self._clear(points[-2], goal_xz):
                points[-1] = goal_xz
            elif self._clear(points[-1], goal_xz):
                points.append(goal_xz)
            else:
                points[-1] = self._centre(*goal_cell)
            return points
        finally:
            self._tmp_people = ()

    def _blocked_by_people(
        self,
        people: Sequence[tuple[float, float]],
        start_cell: tuple[int, int],
        goal_cell: tuple[int, int],
    ) -> set[int]:
        """ほかの人の周りのマスのうち、中心が人の中心から NAV_PERSON_RADIUS 未満のマスの番号（j * nx + i）の集まり。

        人ごとに周りのマスだけを調べる。start_cell と goal_cell は除く。
        """
        r = NAV_PERSON_RADIUS
        blocked: set[int] = set()
        for px, pz in people:
            i0, j0 = self._cell_of(px - r, pz - r)
            i1, j1 = self._cell_of(px + r, pz + r)
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    cx, cz = self._centre(i, j)
                    if math.hypot(cx - px, cz - pz) < r:
                        blocked.add(j * self.nx + i)
        blocked.discard(start_cell[1] * self.nx + start_cell[0])
        blocked.discard(goal_cell[1] * self.nx + goal_cell[0])
        return blocked

    def _cell_of(self, x: float, z: float) -> tuple[int, int]:
        """点 (x, z) を含むマスの (i, j)。床の外は一番近いマスにする。"""
        i = int(math.floor((x - self.x0) / NAV_CELL))
        j = int(math.floor((z - self.z0) / NAV_CELL))
        return (min(max(i, 0), self.nx - 1), min(max(j, 0), self.nz - 1))

    def _free(self, i: int, j: int) -> bool:
        """マス (i, j) が通れるか。"""
        return self._free_cells[j * self.nx + i] == 1

    def _point_free(self, x: float, z: float) -> bool:
        """人の中心を点 (x, z) に置けるか（障害物を人の半径と余白ぶん広げた範囲の外か）。

        点を含む箱に登録された障害物だけを調べる。結果は全部の障害物を調べるのと同じ。
        """
        i, j = self._cell_of(x, z)
        for xmin, xmax, zmin, zmax in self._bucket_boxes[j * self.nx + i]:
            if xmin < x < xmax and zmin < z < zmax:
                return False
        for cx, cz, cr in self._bucket_round[j * self.nx + i]:
            if math.hypot(x - cx, z - cz) < cr:
                return False
        return True

    def _centre(self, i: int, j: int) -> tuple[float, float]:
        """マス (i, j) の中心の (x, z)。"""
        return (self.x0 + (i + 0.5) * NAV_CELL, self.z0 + (j + 0.5) * NAV_CELL)

    def _nearest_free(self, i: int, j: int) -> tuple[int, int] | None:
        """マス (i, j) が通れればそれを返す。通れなければ幅優先で近い通れるマスを探す。無ければ None。"""
        if self._free(i, j):
            return (i, j)
        seen = {(i, j)}
        queue: deque[tuple[int, int]] = deque([(i, j)])
        while queue:
            ci, cj = queue.popleft()
            for di, dj in NEIGHBORS_8:
                ni, nj = ci + di, cj + dj
                if not (0 <= ni < self.nx and 0 <= nj < self.nz) or (ni, nj) in seen:
                    continue
                if self._free(ni, nj):
                    return (ni, nj)
                seen.add((ni, nj))
                queue.append((ni, nj))
        return None

    @staticmethod
    def _octile(a: tuple[int, int], b: tuple[int, int]) -> float:
        """マス a から b までの推定距離（8方向で動くときの最短に近い値）。A* の評価に使う。"""
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        return max(dx, dy) + (SQRT2 - 1.0) * min(dx, dy)

    def _astar(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        blocked: set[int] | frozenset[int] = frozenset(),
    ) -> list[tuple[int, int]] | None:
        """通れるマスで、blocked に入っていないマスだけを使って、start から goal までのマスの列を A* で探す。8方向。斜めは縦と横の2マスが通れて blocked でもないときだけ。"""
        nx, nz = self.nx, self.nz
        free = self._free_cells
        start_idx = start[1] * nx + start[0]
        goal_idx = goal[1] * nx + goal[0]
        gi, gj = goal
        # マスの番号（添え字）ごとの値を list で持つ。dict より速い
        best: list[float] = [math.inf] * (nx * nz)  # ここまでの最小の距離
        came: list[int] = [-1] * (nx * nz)  # 手前のマスの番号
        best[start_idx] = 0.0
        heap: list[tuple[float, float, int]] = [(self._octile(start, goal), 0.0, start_idx)]
        found = False
        push = heapq.heappush
        pop = heapq.heappop
        while heap:
            _, cost, cur = pop(heap)
            if cur == goal_idx:
                found = True
                break
            if cost > best[cur]:
                continue  # 古い候補
            ci, cj = cur % nx, cur // nx
            for di, dj, diagonal, step in NAV_STEPS:
                ni, nj = ci + di, cj + dj
                if ni < 0 or ni >= nx or nj < 0 or nj >= nz:
                    continue
                nidx = nj * nx + ni
                if not free[nidx] or nidx in blocked:
                    continue
                if diagonal:
                    # 角の2マスも通れて、よける人のマスでもないときだけ斜めに進める
                    side_a = cj * nx + ni
                    side_b = nj * nx + ci
                    if not (free[side_a] and free[side_b]) or side_a in blocked or side_b in blocked:
                        continue  # 角をすり抜けない
                new_cost = cost + step
                if new_cost < best[nidx]:
                    best[nidx] = new_cost
                    came[nidx] = cur
                    # オクタイル距離（_octile と同じ式。max・min の呼び出しを避けて分岐にしている）
                    dx = ni - gi if ni >= gi else gi - ni
                    dy = nj - gj if nj >= gj else gj - nj
                    if dx > dy:
                        h = dx + (SQRT2 - 1.0) * dy
                    else:
                        h = dy + (SQRT2 - 1.0) * dx
                    push(heap, (new_cost + h, new_cost, nidx))
        if not found:
            return None
        cells: list[tuple[int, int]] = []
        idx = goal_idx
        while True:
            cells.append((idx % self.nx, idx // self.nx))
            if idx == start_idx:
                break
            idx = came[idx]
        cells.reverse()
        return cells

    def _simplify(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """まっすぐ行ける一番遠い点まで飛ばして、点の数を減らす。先頭と末尾は必ず残す。

        遠い側から調べる。近い側から1つずつ調べるより、直線の判定の回数が少なくて済む。
        どの区間も _clear で確かめるので、障害物に触れる直線は使わない。
        """
        last = len(points) - 1
        if last < 2:
            return list(points)
        out = [points[0]]
        cur = 0
        while cur < last:
            nxt = cur + 1  # まっすぐ行ける点が無ければ、次の点へ進む
            for k in range(last, cur + 1, -1):
                if self._clear(points[cur], points[k]):
                    nxt = k
                    break
            out.append(points[nxt])
            cur = nxt
        return out

    def _clear(self, p: tuple[float, float], q: tuple[float, float]) -> bool:
        """点 p から q までの直線を、人の中心が置けない場所とほかの人の周りを通らずに行けるか。NAV_CELL / 4 ごとに調べる。"""
        length = math.hypot(q[0] - p[0], q[1] - p[1])
        steps = max(1, math.ceil(length / (NAV_CELL / 4.0)))
        # _point_free と同じ判定を、呼び出しを減らして速くするため展開している（結果は同じ）
        px, pz = p
        dx = q[0] - px
        dz = q[1] - pz
        nx, nz = self.nx, self.nz
        bucket_boxes = self._bucket_boxes
        bucket_round = self._bucket_round
        people = self._tmp_people
        for k in range(1, steps + 1):
            t = k / steps
            x = px + dx * t
            z = pz + dz * t
            i = min(max(math.floor((x - self.x0) / NAV_CELL), 0), nx - 1)
            j = min(max(math.floor((z - self.z0) / NAV_CELL), 0), nz - 1)
            idx = j * nx + i
            for xmin, xmax, zmin, zmax in bucket_boxes[idx]:
                if xmin < x < xmax and zmin < z < zmax:
                    return False
            for cx, cz, cr in bucket_round[idx]:
                if math.hypot(x - cx, z - cz) < cr:
                    return False
            for ox, oz in people:
                if math.hypot(x - ox, z - oz) < NAV_PERSON_RADIUS:
                    return False
        return True


class SpotManager:
    """行き先の予約を管理する。1つの立つ場所には1人だけ。GOING・AT_SPOT の人が予約を持ち、RETURNING で外す。"""

    def __init__(self, spots: tuple[Spot, ...], rng: random.Random) -> None:
        """行き先の一覧と乱数生成器（App の rng を渡す）を受け取り、予約の無い状態で始める。"""
        self.spots: tuple[Spot, ...] = spots
        self.rng: random.Random = rng
        self._holder: dict[tuple[str, int], int] = {}  # (行き先の名前, 立つ場所の番号) → 予約した人の番号
        self._reserved: dict[int, tuple[Spot, int]] = {}  # 人の番号 → (行き先, 立つ場所の番号)

    def count(self, spot: Spot) -> int:
        """行き先 spot の予約数（使われている立つ場所の数）。"""
        return len(spot.slots) - len(self._free_slots(spot))

    def _free_slots(self, spot: Spot) -> list[int]:
        """行き先 spot の空いている立つ場所の番号の一覧。"""
        return [k for k in range(len(spot.slots)) if (spot.name, k) not in self._holder]

    def reserve(self, agent_index: int) -> tuple[Spot, int] | None:
        """空いている行き先の立つ場所を1つ予約して (行き先, 立つ場所の番号) を返す。空きが無ければ None。

        くじの重みは coffee 50、書棚2つ合わせて 25、植木2つ合わせて 25。
        空きの無い行き先は外し、残りの中から重みで選ぶ。同じ人の二重予約は ValueError。
        """
        if agent_index in self._reserved:
            raise ValueError(t("err_spot_reserved", index=agent_index))
        free_shelves = sum(1 for s in self.spots if s.kind == KIND_SHELF and self._free_slots(s))
        free_plants = sum(1 for s in self.spots if s.kind == KIND_PLANT and self._free_slots(s))
        candidates: list[tuple[Spot, float]] = []
        for spot in self.spots:
            if not self._free_slots(spot):
                continue
            if spot.kind == KIND_COFFEE:
                weight = SPOT_WEIGHT_COFFEE
            elif spot.kind == KIND_SHELF:
                weight = SPOT_WEIGHT_SHELF / free_shelves  # 空いている書棚で分ける
            else:
                weight = SPOT_WEIGHT_PLANT / free_plants  # 空いている植木で分ける
            candidates.append((spot, weight))
        if not candidates:
            return None
        pick = self.rng.uniform(0.0, sum(w for _, w in candidates))
        chosen = candidates[-1][0]  # 丸め誤差の保険に最後の候補
        acc = 0.0
        for spot, weight in candidates:
            acc += weight
            if pick < acc:
                chosen = spot
                break
        slot = self.rng.choice(self._free_slots(chosen))
        self._holder[(chosen.name, slot)] = agent_index
        self._reserved[agent_index] = (chosen, slot)
        return (chosen, slot)

    def release(self, agent_index: int) -> None:
        """人の予約を外す。予約が無ければ何もしない。"""
        entry = self._reserved.pop(agent_index, None)
        if entry is not None:
            spot, slot = entry
            self._holder.pop((spot.name, slot), None)


@dataclass
class Chatter:
    """行き先で会話中の1人の状態。話し手なら身ぶり、聞き手なら飲む・立つの切り替えに使う。"""

    gesture: str = ""  # 話し手の身ぶり（話し手のときだけ。空なら未選択）
    gesture_listener: int = -1  # 身ぶりの相手の番号（-1 なら未選択）
    gesture_timer: float = 0.0  # 身ぶりを選び直すまでの残り時間（秒）
    listen_timer: float = 0.0  # 聞き手の姿勢を選び直すまでの残り時間（秒）
    listen_drink: bool = False  # 聞き手が今「飲む姿勢」か


@dataclass
class Pose:
    """人型の関節の角度（度）と、体全体の上下のずらし。

    肩は正で腕を前へ振る。肘は曲げる量で、前腕が前（-Z 側）へ曲がる。
    足の付け根は正で脚を前へ振る。膝は曲げる量で、すねが後ろ（+Z 側）へ曲がる。
    左は -X 側、右は +X 側（キャラの正面は -Z）。
    """

    shoulder_l: float
    shoulder_r: float
    elbow_l: float
    elbow_r: float
    hip_l: float
    hip_r: float
    knee_l: float
    knee_r: float
    body_y: float  # 体全体の上下のずらし（立っているとき 0）
    body_z: float = 0.0  # 体全体の前後のずらし。キャラの向きに対して（負＝前＝-Z 側）
    head_yaw: float = 0.0  # 頭だけの Y 軸まわりの回転（度）。正の向きは Mat4.from_axis_angle(Vec3.UP, 角度) と同じ

    def clamped(self) -> "Pose":
        """各角度を関節の範囲内に収めた新しい Pose を返す。head_yaw はそのまま引き継ぐ。"""
        return Pose(
            shoulder_l=_clamp(self.shoulder_l, *SHOULDER_RANGE),
            shoulder_r=_clamp(self.shoulder_r, *SHOULDER_RANGE),
            elbow_l=_clamp(self.elbow_l, *ELBOW_RANGE),
            elbow_r=_clamp(self.elbow_r, *ELBOW_RANGE),
            hip_l=_clamp(self.hip_l, *HIP_RANGE),
            hip_r=_clamp(self.hip_r, *HIP_RANGE),
            knee_l=_clamp(self.knee_l, *KNEE_RANGE),
            knee_r=_clamp(self.knee_r, *KNEE_RANGE),
            body_y=self.body_y,
            body_z=self.body_z,
            head_yaw=self.head_yaw,
        )


def stand_pose() -> Pose:
    """立っている姿勢。肘だけ少し曲げる。"""
    return Pose(
        shoulder_l=0.0,
        shoulder_r=0.0,
        elbow_l=5.0,
        elbow_r=5.0,
        hip_l=0.0,
        hip_r=0.0,
        knee_l=0.0,
        knee_r=0.0,
        body_y=0.0,
        body_z=0.0,
    ).clamped()


def walk_pose(phase: float) -> Pose:
    """歩いている姿勢。phase は歩行の位相（ラジアン）。左右の脚と腕は逆に振れる。"""
    s = math.sin(phase)
    return Pose(
        shoulder_l=-20.0 * s,
        shoulder_r=20.0 * s,
        elbow_l=15.0,
        elbow_r=15.0,
        hip_l=25.0 * s,
        hip_r=-25.0 * s,
        knee_l=30.0 * max(0.0, -s),  # 後ろへ下がる脚のひざを曲げる
        knee_r=30.0 * max(0.0, s),
        body_y=0.0,
        body_z=0.0,
    ).clamped()


def sit_pose(t: float) -> Pose:
    """座って作業している姿勢。t は席に着いてからの秒数。両手でキーボードを打つ動きを付ける。"""
    wave = 5.0 * math.sin(2.0 * math.pi * t / TYPING_PERIOD_SEC)
    return Pose(
        shoulder_l=80.0,  # 肩を前へ大きく振り、机の縁まで腕を届かせる
        shoulder_r=80.0,
        # 肘は 15±5 度。肩を 80 にしてあるので、前腕が天板の上面（高さ 38）より下へ沈まない
        elbow_l=15.0 + wave,
        elbow_r=15.0 - wave,
        hip_l=90.0,  # 太ももを水平に前へ
        hip_r=90.0,
        knee_l=90.0,  # すねを垂直に下へ
        knee_r=90.0,
        body_y=SIT_BODY_Y,
        body_z=SIT_BODY_Z,
    ).clamped()


def drink_pose() -> Pose:
    """飲む姿勢。右肩を前へ上げ、右肘を大きく曲げる。左は立ち姿勢のまま。"""
    pose = stand_pose()
    pose.shoulder_r = 40.0
    pose.elbow_r = 120.0
    return pose.clamped()


def shelf_pose() -> Pose:
    """本を取る姿勢。右肩を前へ大きく上げ、右肘を曲げて手を伸ばす。左は立ち姿勢のまま。"""
    pose = stand_pose()
    pose.shoulder_r = 110.0
    pose.elbow_r = 10.0
    return pose.clamped()


def plant_pose() -> Pose:
    """かがむ姿勢。足の付け根 40・膝 80 を左右とも、肩 20。足の裏が床に付くように体を下げる。"""
    hip = 40.0
    knee = 80.0
    pose = stand_pose()
    pose.shoulder_l = 20.0
    pose.shoulder_r = 20.0
    pose.hip_l = hip
    pose.hip_r = hip
    pose.knee_l = knee
    pose.knee_r = knee
    # 太ももとすねの高さの分だけ体を下げる（立ったときの足の裏の高さ 0 に合わせる）
    pose.body_y = (
        THIGH_LEN * math.cos(math.radians(hip))
        + SHIN_LEN * math.cos(math.radians(hip - knee))
    ) - (THIGH_LEN + SHIN_LEN)
    return pose.clamped()


def spot_pose(kind: str) -> Pose:
    """行き先に1人でいるときの姿勢。コーヒーは飲む、書棚は本を取る、植木はかがむ。"""
    if kind == KIND_COFFEE:
        return drink_pose()
    if kind == KIND_SHELF:
        return shelf_pose()
    return plant_pose()


def gesture_pose(kind: str) -> Pose:
    """話し手の身ぶりの姿勢。両手を上げる、片手を向ける、机を指す。"""
    pose = stand_pose()
    if kind == GESTURE_BOTH_UP:
        pose.shoulder_l = 150.0
        pose.shoulder_r = 150.0
        pose.elbow_l = 20.0
        pose.elbow_r = 20.0
    elif kind == GESTURE_POINT_LISTENER:
        pose.shoulder_r = 80.0
        pose.elbow_r = 10.0
    else:  # GESTURE_POINT_DESK
        pose.shoulder_r = 95.0
        pose.elbow_r = 0.0
    return pose.clamped()


class Agent:
    """キャラ1人の行動ロジック。描画はしない。

    状態は WANDER（待機）と WORKING（作業中）に加え、office だけの GOING（行き先へ向かう）・
    AT_SPOT（行き先にいる）・RETURNING（席へ戻る）。行き先の予約と会話の判断は App が行う。
    位置 pos は床の上（y=0）に置き、姿勢は pose で別に持つ（体の上下のずらしは pose.body_y）。
    """

    def __init__(
        self,
        name: str,
        seat: Vec3,
        rng: random.Random,
        seat_yaw: float = 0.0,
        wander_x: tuple[float, float] = (FLOOR_X_MIN, FLOOR_X_MAX),
        wander_z: tuple[float, float] = (WANDER_Z_MIN, FLOOR_Z_MAX),
        obstacles: tuple[Rect, ...] = (),
        circles: tuple[tuple[float, float, float], ...] = (),
        nav: NavGrid | None = None,
        on_path_request: Callable[[], None] | None = None,
    ) -> None:
        """名前・席の位置・乱数生成器を受け取り、席に座った状態で初期化する。

        seat_yaw は席に着いたときの向き（度）。wander_x・wander_z はうろつく範囲。
        obstacles は避ける障害物の長方形。circles は避ける丸い障害物（中心の x, z, 半径）。
        nav は道探しの地図、on_path_request は道を探してほしいときに呼ぶ関数（App の列に並べる）。
        省略時は障害物なし。既定値は proto の動きと同じ。
        """
        self.name = name
        self.seat = seat
        self.rng = rng
        self.seat_yaw: float = seat_yaw  # 席に着いたときの向き（度）
        self.wander_x: tuple[float, float] = wander_x  # うろつきの x の範囲
        self.wander_z: tuple[float, float] = wander_z  # うろつきの z の範囲
        self.obstacles: tuple[Rect, ...] = obstacles  # うろつきの目標が避ける障害物
        self.circles: tuple[tuple[float, float, float], ...] = circles  # うろつきの目標が避ける丸い障害物
        self.intended_move: float = 0.0  # このフレームで進もうとした距離（_step_toward が入れる）
        self.state: str = WANDER
        self.pos: Vec3 = Vec3(seat.x, 0.0, seat.z)
        self.yaw: float = 0.0  # Y軸回転の角度（度）。0 のとき -Z（机の方向）を向く
        self.pose: Pose = stand_pose()  # 今の姿勢（描画が読む）
        self.walk_phase: float = 0.0  # 歩行の位相（ラジアン）
        self._target: Vec3 | None = None  # 待機中の目標点
        self._wait: float = 0.0  # 立ち止まる残り時間（秒）
        self._seated_time: float = 0.0  # 席に着いてからの経過時間（秒）
        self._arrived: bool = False  # 作業中に席へ着いたかどうか
        # ここから office だけの項目。proto では使わない（nav が None なら道探しはしない）
        self.nav: NavGrid | None = nav  # 道を探す地図
        self._on_path_request: Callable[[], None] | None = on_path_request  # 道の依頼先（App の列）
        self.path_wait: bool = False  # 道を探す順番待ち。立って待ち、歩かない
        self.spot: Spot | None = None  # 行き先（GOING・AT_SPOT・RETURNING のとき）
        self.slot_index: int = 0  # 行き先で使う立つ場所の番号
        self.wander_time: float = 0.0  # うろついている時間（秒）。App が数える
        self.cooldown: float = 0.0  # 席へ戻ったあとの休みの残り（秒）。App が減らす
        self.alone_time: float = 0.0  # 行き先に1人でいる時間（秒）。App が数える
        self.talk_time: float = 0.0  # 行き先で会話している時間（秒）。App が数える
        self._path: list[Vec3] = []  # 道の点（先頭から順に進む）
        self._goal: Vec3 | None = None  # 道の最後の目標（席または立つ場所）
        self.avoid_near: bool = False  # 次に道を探すとき、近くの人もよけてほしい
        self._sidestep_time: float = 0.0  # 横へよけている残り時間（秒）。0 のときはよけていない
        self._sidestep_dir: tuple[float, float] = (0.0, 0.0)  # 横へよける向き（単位ベクトル）
        self.hold: bool = False  # 会話の相手になっている間 True（App が入れる）。作業中の5秒で立ち上がらない
        # --claude のときの項目。visible が False の人は、描かず・動かさず、部屋の外（PARK_X）に置く
        self.visible: bool = True
        self.busy: bool = False  # 作業中のまま（Claude Code が作業している間）。True の間は5秒で立ち上がらない
        self.role: str = ""  # "main"（メイン）・"sub"（サブエージェント）・""
        self.label: str = ""  # 頭の上に出す名前の札（--claude のとき）
        self._busy_hold_time: float = 0.0  # busy が False になってから座っている時間（秒）

    def start_work(self) -> None:
        """作業状態へ切り替える。席へ戻るところから始める。道探しのある配置で席から遠ければ、道を探す。"""
        self.state = WORKING
        self._target = None
        self._wait = 0.0
        self._seated_time = 0.0
        self._busy_hold_time = 0.0
        self._arrived = False
        self.spot = None
        self._path = []
        self.path_wait = False
        self._sidestep_time = 0.0
        self.avoid_near = False
        self._goal = Vec3(self.seat.x, 0.0, self.seat.z)
        if (
            self.nav is not None
            and math.hypot(self.seat.x - self.pos.x, self.seat.z - self.pos.z) > WORK_PATH_MIN_DIST
        ):
            self._ask_path()  # 席から遠い。道を探してもらう（列の順番が来るまで立って待つ）

    @property
    def is_seated(self) -> bool:
        """作業中で席に着いているか。着いている間は他のキャラに押されない。"""
        return self.state == WORKING and self._arrived

    @property
    def is_fixed(self) -> bool:
        """他のキャラに押されないか。席に着いている人と、行き先の立つ場所にいる人。
        会話の相手（hold が True）も、作業中（WORKING）でなければ押されない。席へ歩いている途中の相手は今までどおり押される。
        """
        return self.is_seated or self.state == AT_SPOT or (self.hold and self.state != WORKING)

    @property
    def sidestepping(self) -> bool:
        """横へよけている最中か。よけている間は道を使わず、決めた向きへ歩く。"""
        return self._sidestep_time > 0.0

    def begin_sidestep(self, ux: float, uz: float) -> None:
        """向き (ux, uz) へ SIDESTEP_SEC 秒だけ横によける。今の道は捨てる。"""
        self._sidestep_time = SIDESTEP_SEC
        self._sidestep_dir = (ux, uz)
        self._path = []

    def update(self, dt: float) -> None:
        """dt 秒ぶん行動を進める。"""
        self.intended_move = 0.0
        if self.path_wait:
            # 道を探す順番待ち。その場で立って待つ（歩かない）
            self.pose = stand_pose()
            return
        if self._sidestep_time > 0.0:
            # 横へよけている最中。決めた向きへ進み、時間が過ぎたら道を探し直してもらう
            if self.state in (GOING, RETURNING, WORKING):
                ux, uz = self._sidestep_dir
                d = WANDER_SPEED * dt
                self._step_toward(Vec3(self.pos.x + ux * d, 0.0, self.pos.z + uz * d), d)
            self._sidestep_time -= dt
            if self._sidestep_time <= 0.0:
                self._sidestep_time = 0.0
                self.avoid_near = True  # 次の道探しでは、近くの人もよける
                self.request_replan()
            return
        if self.state == WANDER:
            self._update_wander(dt)
        elif self.state == GOING:
            self._update_going(dt)
        elif self.state == AT_SPOT:
            pass  # 姿勢と向きは App が毎フレーム決める
        elif self.state == RETURNING:
            self._update_returning(dt)
        elif self.state == LEAVING:
            self._follow_path(WANDER_SPEED * dt)  # ドアの内側まで歩く（着いたら App が置き場所に戻す）
        else:
            self._update_working(dt)

    @property
    def leaving_done(self) -> bool:
        """部屋を出る道を歩き終えたか。道が空になったか、出口の点（_goal）から LEAVE_ARRIVE_DIST 以内に入ったとき。"""
        if self.state != LEAVING:
            return False
        if not self._path:
            return True
        if self._goal is not None:
            return math.hypot(self.pos.x - self._goal.x, self.pos.z - self._goal.z) <= LEAVE_ARRIVE_DIST
        return False

    def begin_leaving(self, goal: Vec3) -> bool:
        """goal（ドアの内側）へ部屋を出る道を探して LEAVING にする。道が無ければ False（その場合は App が置き場所に戻す）。"""
        self.state = LEAVING
        self.spot = None
        self._target = None
        self._wait = 0.0
        self._arrived = False
        self._path = []
        self._goal = goal
        self.avoid_near = False
        self.path_wait = False  # 道探しの順番待ちからは外れる（_leave が待ち列からも外す）
        if not self._plan(goal, []):
            self._path = []
            return False
        return True

    def park(self) -> None:
        """見えていない人の置き場所（PARK_X、ドアの z）へ戻し、ふだんの状態にする。道・予約・時間は空にする。"""
        self.visible = False
        self.busy = False
        self.hold = False
        self.state = WANDER
        self.pos = Vec3(PARK_X, 0.0, DOOR_Z)
        self.pose = stand_pose()
        self.spot = None
        self._target = None
        self._wait = 0.0
        self._arrived = False
        self._path = []
        self._goal = None
        self.path_wait = False
        self.avoid_near = False
        self._sidestep_time = 0.0
        self.wander_time = 0.0
        self.cooldown = 0.0
        self.alone_time = 0.0
        self.talk_time = 0.0

    def _update_wander(self, dt: float) -> None:
        """席の周りをうろつく。目標に着いたら1〜3秒立ち止まり、次の目標を選ぶ。"""
        if self._wait > 0.0:
            self._wait -= dt
            self.pose = stand_pose()  # 立ち止まっている間は立つ
            if self._wait > 0.0:
                return
            self._wait = 0.0

        if self._target is None:
            self._choose_target()
            if self._target is None:
                return  # 目標が見つからず、_choose_target が1秒の待ちを入れている

        if self._step_toward(self._target, WANDER_SPEED * dt):
            self._target = None
            self._wait = self.rng.uniform(WAIT_MIN, WAIT_MAX)
            self.pose = stand_pose()

    def _update_working(self, dt: float) -> None:
        """席へ戻り、着いたら席の向き（seat_yaw）を向いて座る。キーボードを打ちながら5秒たったら待機に戻る。"""
        if not self._arrived:
            if self._path:
                self._follow_path(WORK_SPEED * dt)  # 道の途中（席の近くまで）
                return
            if self._step_toward(self.seat, WORK_SPEED * dt):
                self._arrived = True
                self.yaw = self.seat_yaw  # 席の向きを向く
                self.pose = sit_pose(0.0)
            return

        self._seated_time += dt
        self.pose = sit_pose(self._seated_time)
        # busy の間は数えない。busy が False になった時点から5秒数えて立つ（busy が無いときは、座ってからの5秒と同じ）
        if self.busy:
            self._busy_hold_time = 0.0
        else:
            self._busy_hold_time += dt
        # 会話の相手（hold）の間は、5秒たっても立ち上がらない。キーを打つ動きは続ける
        if self._busy_hold_time >= WORK_HOLD_SEC and not self.hold and not self.busy:
            self._return_to_wander()

    def _return_to_wander(self) -> None:
        """待機状態に戻し、目標をリセットして立ち上がる。"""
        self.state = WANDER
        self._target = None
        self._wait = 0.0
        self._arrived = False
        self.wander_time = 0.0
        self.path_wait = False
        self._sidestep_time = 0.0
        self.avoid_near = False
        self.pose = stand_pose()

    def begin_going(self, spot: Spot, slot_index: int) -> bool:
        """行き先 spot の立つ場所 slot_index へ GOING にして、道を探してもらう。

        道は App の列の順番が来てから探す（その間は立って待つ）。道が見つからなければ WANDER に戻る。
        戻り値は GOING になったかどうか（nav が無いときは False。依頼先が無いときは道の結果で決まる）。
        """
        if self.nav is None:
            return False
        slot_x, slot_z = spot.slots[slot_index]
        self.state = GOING
        self.spot = spot
        self.slot_index = slot_index
        self._target = None
        self._wait = 0.0
        self.alone_time = 0.0
        self.talk_time = 0.0
        self._path = []
        self._goal = Vec3(slot_x, 0.0, slot_z)
        self._ask_path()
        return self.state == GOING

    def begin_returning(self) -> bool:
        """行き先から席へ戻る道を探してもらい、RETURNING にする。道が無ければあきらめて WANDER に戻し、False を返す。"""
        self.state = RETURNING
        self.spot = None
        self._path = []
        self._goal = Vec3(self.seat.x, 0.0, self.seat.z)
        if self.nav is None:
            self.give_up()
            return False
        self._ask_path()
        return self.state == RETURNING

    def request_replan(self) -> bool:
        """引っかかったとき、今の位置から目標までの道を探し直してもらう（列に並ぶ）。目標が無ければ False。"""
        if self._goal is None:
            return False
        self._ask_path()
        return True

    def _ask_path(self) -> None:
        """道を探してほしいと頼む。依頼先（App の列）があれば並ぶだけで、探すのは順番が来てから。依頼先が無ければその場で探す。"""
        self.path_wait = True
        if self._on_path_request is not None:
            self._on_path_request()
        elif not self.serve_path():
            self.path_failed()

    def serve_path(self, people: Sequence[tuple[float, float]] = ()) -> bool:
        """順番が来たので、今の位置から目標までの道を探す（App が呼ぶ）。見つかれば True。

        people は、よけるほかの人の中心 (x, z) の列。省略時は人をよけない（今までどおり）。
        """
        self.path_wait = False
        if self._goal is None:
            return False
        return self._plan(self._goal, people)

    def path_failed(self) -> bool:
        """道が見つからなかったときの後始末。WORKING は道を空にして席へまっすぐ進む（今までどおり）。

        GOING・RETURNING はあきらめて WANDER に戻し、True を返す（App が行き先の予約を外す）。
        """
        if self.state == WORKING:
            self._path = []
            return False
        self.give_up()
        return True

    def give_up(self) -> None:
        """行き先へ行けずにあきらめ、WANDER に戻す。RETURNING からなら休みをつけ、GOING からなら休みは0。"""
        self._end_outing(OUTING_COOLDOWN_SEC if self.state == RETURNING else 0.0)

    def reset_outing_timers(self) -> None:
        """行き先のタイマー（うろつき・休み・1人・会話）を0にする。スペースキーで作業に切り替えるときに使う。"""
        self.wander_time = 0.0
        self.cooldown = 0.0
        self.alone_time = 0.0
        self.talk_time = 0.0

    def _end_outing(self, cooldown: float) -> None:
        """行き先の状態を終えて WANDER に戻す。休みは cooldown、うろつきの時間は0にする。"""
        self.state = WANDER
        self.spot = None
        self._path = []
        self._goal = None
        self._target = None
        self._wait = 0.0
        self._arrived = False
        self.path_wait = False
        self._sidestep_time = 0.0
        self.avoid_near = False
        self.wander_time = 0.0
        self.cooldown = cooldown
        self.pose = stand_pose()

    def _update_going(self, dt: float) -> None:
        """行き先の立つ場所へ道を進む。着いたら AT_SPOT になり、行き先の中心を向く。"""
        if not self._follow_path(WANDER_SPEED * dt):
            return
        self.state = AT_SPOT
        self.pose = stand_pose()
        if self.spot is not None:
            center_x, center_z = self.spot.center
            self.yaw = facing_yaw(self.pos.x, self.pos.z, center_x, center_z, default=self.yaw)

    def _update_returning(self, dt: float) -> None:
        """席へ戻る道を進む。着いたら WANDER に戻り、休み（OUTING_COOLDOWN_SEC）をつける。"""
        if self._follow_path(WANDER_SPEED * dt):
            self._end_outing(OUTING_COOLDOWN_SEC)

    def _follow_path(self, distance: float) -> bool:
        """道の点を順に、合計 distance だけ進む。道の最後まで進み切ったら True（道が空のときも True）。"""
        remaining = distance
        moved = 0.0
        while self._path and remaining > 0.0:
            target = self._path[0]
            dist = math.hypot(target.x - self.pos.x, target.z - self.pos.z)
            step = min(dist, remaining)
            if self._step_toward(target, step):
                self._path.pop(0)
            moved += step
            remaining -= step
        self.intended_move = moved  # 途中の点ごとに書き換わるので、合計を入れ直す
        return not self._path

    def _plan(self, goal: Vec3, people: Sequence[tuple[float, float]] = ()) -> bool:
        """今の位置から goal までの道を探す。people は避ける人の中心の列。見つかれば道と目標を入れて True。見つからなければ何も変えず False。"""
        if self.nav is None:
            return False
        points = self.nav.find_path((self.pos.x, self.pos.z), (goal.x, goal.z), people)
        if points is None:
            return False
        self._path = [Vec3(x, 0.0, z) for x, z in points]
        self._goal = goal
        return True

    def repick_target(self) -> None:
        """引っかかったときに App が呼ぶ。待ち時間は0のまま、すぐ別の目標を選んで歩き出す。"""
        self._wait = 0.0
        self._choose_target()

    def _choose_target(self) -> None:
        """新しい目標を選ぶ。見つからなければ、目標なしで1秒立ち止まる。"""
        target = self._pick_wander_target()
        if target is None:
            self._target = None
            self._wait = 1.0
            self.pose = stand_pose()
        else:
            self._target = target

    def _pick_wander_target(self) -> Vec3 | None:
        """席から半径 WANDER_RADIUS 以内のランダムな点を選ぶ。うろつきの範囲に収める。

        障害物を AGENT_RADIUS だけ広げた範囲に入らない点を、最大 TARGET_TRIES 回まで探す。見つからなければ None。
        """
        for _ in range(TARGET_TRIES):
            angle = self.rng.uniform(0.0, 2.0 * math.pi)
            radius = WANDER_RADIUS * math.sqrt(self.rng.random())
            x = _clamp(self.seat.x + radius * math.cos(angle), *self.wander_x)
            z = _clamp(self.seat.z + radius * math.sin(angle), *self.wander_z)
            if not self._overlaps_obstacle(x, z):
                return Vec3(x, 0.0, z)
        return None

    def _overlaps_obstacle(self, x: float, z: float) -> bool:
        """点 (x, z) が、いずれかの障害物を AGENT_RADIUS だけ広げた範囲に入っていれば True。丸い障害物も同じ。"""
        for rect in self.obstacles:
            if (
                rect.xmin - AGENT_RADIUS < x < rect.xmax + AGENT_RADIUS
                and rect.zmin - AGENT_RADIUS < z < rect.zmax + AGENT_RADIUS
            ):
                return True
        for cx, cz, cr in self.circles:
            if math.hypot(x - cx, z - cz) < cr + AGENT_RADIUS:
                return True
        return False

    def _step_toward(self, target: Vec3, distance: float) -> bool:
        """目標へ distance だけ進む。着いたら True を返す。

        進んだ分だけ歩行の位相を進め、歩きの姿勢にする。進むときは進行方向を向く。
        """
        dx = target.x - self.pos.x
        dz = target.z - self.pos.z
        dist = math.hypot(dx, dz)
        if dist <= distance:
            moved = dist
            self.pos = Vec3(target.x, 0.0, target.z)
            arrived = True
        else:
            moved = distance
            ux = dx / dist
            uz = dz / dist
            self.pos = Vec3(self.pos.x + ux * distance, 0.0, self.pos.z + uz * distance)
            # 前方は -Z を基準にする。Y軸回転 θ で前方は (-sinθ, 0, -cosθ) になる。
            self.yaw = math.degrees(math.atan2(-ux, -uz))
            arrived = False

        self.intended_move = moved  # 押し出し前に進もうとした距離（App の引っかかり判定に使う）
        self.walk_phase += moved / STRIDE * 2.0 * math.pi
        self.pose = walk_pose(self.walk_phase)
        return arrived


class Human(Agent):
    """ユーザーの分身。クリックした場所へ道を探して歩く。行き先・作業・うろうろはしない。"""

    def __init__(
        self,
        seat: Vec3,
        rng: random.Random,
        wander_x: tuple[float, float],
        wander_z: tuple[float, float],
        obstacles: tuple[Rect, ...],
        circles: tuple[tuple[float, float, float], ...],
        nav: NavGrid | None,
        name: str = "YOU",
    ) -> None:
        """最初の位置 seat に立たせる。道探しと障害物は App と同じものを使う。依頼先（列）は持たず、道は walk_to で直接探す。"""
        super().__init__(
            name,
            seat,
            rng,
            wander_x=wander_x,
            wander_z=wander_z,
            obstacles=obstacles,
            circles=circles,
            nav=nav,
            on_path_request=None,
        )

    @property
    def walking(self) -> bool:
        """道を歩いている最中か（道の点が残っているか）。"""
        return len(self._path) > 0

    def update(self, dt: float) -> None:
        """道があれば HUMAN_SPEED で進み、進み切ったら立つ。道がなければ立っている。うろつき・行き先・作業はしない。"""
        self.intended_move = 0.0
        if self._path:
            if self._follow_path(HUMAN_SPEED * dt):
                self.pose = stand_pose()
        else:
            self.pose = stand_pose()

    def walk_to(self, x: float, z: float, people: Sequence[tuple[float, float]]) -> bool:
        """(x, z) へ道を探して歩く。見つかれば True。見つからなければ道を空にして False。people は避ける人の中心の列。"""
        ok = self._plan(Vec3(x, 0.0, z), people)
        if not ok:
            self._path = []
            return False
        # 先頭の点が後ろにあると、いったん戻ってから進む（逆走）。2つ目の点へ直線で行けるなら先頭を捨てる
        if len(self._path) >= 2 and self.nav is not None:
            second = self._path[1]
            if self.nav._clear((self.pos.x, self.pos.z), (second.x, second.z)):
                self._path.pop(0)
        return True

    def warp(self, x: float, z: float, yaw: float) -> None:
        """(x, z) へ瞬間移動して、向き yaw で立つ。道は空にする。"""
        self.pos = Vec3(x, 0.0, z)
        self.yaw = yaw
        self._path = []
        self.pose = stand_pose()

    def stop(self) -> None:
        """歩くのをやめる。道は空にして、立ち姿勢にする。位置と向きは変えない。"""
        self._path = []
        self.pose = stand_pose()


class AgentView(Node):
    """Agent の位置・向き・姿勢を読んで、人型（胴・頭・両腕・両脚）を箱で描く Node。"""

    def __init__(self, agent: Agent, color: int, skin_color: int = SKIN_COLOR) -> None:
        """描画対象の Agent と、胴・脚の色、頭と腕の肌の色を受け取る。"""
        super().__init__()
        self.agent = agent
        self.color = color
        self.skin_color = skin_color

    def on_update(self) -> None:
        """Agent の位置・姿勢の上下のずら・向きを変換行列に反映する。"""
        a = self.agent
        position = Vec3(a.pos.x, a.pose.body_y, a.pos.z)
        # 位置 → 向き → 体の前後のずらし の順（キャラの向きに対して前後にずらす）
        self.transform = (
            Mat4.from_translation(position)
            * Mat4.from_axis_angle(Vec3.UP, a.yaw)
            * Mat4.from_translation(Vec3(0.0, 0.0, a.pose.body_z))
        )

    def on_draw(self) -> None:
        """頭と両腕は肌色、胴と両脚はキャラの色で描く。腕脚は関節の角度に合わせて描く。"""
        if not self.agent.visible:
            return  # 見えていない人は描かない（--claude のとき）
        p = self.agent.pose
        self.box(Mat4.from_translation(BODY_CENTER), BODY_SIZE, self.color)
        # 頭は自分の中心のまわりに head_yaw だけ回す（体は回さない）
        head = Mat4.from_translation(HEAD_CENTER) * Mat4.from_axis_angle(Vec3.UP, p.head_yaw)
        self.box(head, HEAD_SIZE, self.skin_color)

        # 左右それぞれの腕と脚。角度は親の関節に対する相対の値
        for x_sign, shoulder, elbow, hip, knee in (
            (-1.0, p.shoulder_l, p.elbow_l, p.hip_l, p.knee_l),
            (1.0, p.shoulder_r, p.elbow_r, p.hip_r, p.knee_r),
        ):
            shoulder_joint = Mat4.from_translation(
                Vec3(x_sign * SHOULDER_X, SHOULDER_Y, 0.0)
            )
            elbow_joint = self._limb(
                shoulder_joint, shoulder, UPPER_ARM_LEN, UPPER_ARM_THICK, self.skin_color
            )
            # 前腕は肘から前へ曲がる（角度を正に加える）
            self._limb(elbow_joint, elbow, FOREARM_LEN, FOREARM_THICK, self.skin_color)

            hip_joint = Mat4.from_translation(Vec3(x_sign * HIP_X, HIP_Y, 0.0))
            knee_joint = self._limb(
                hip_joint, hip, THIGH_LEN, THIGH_THICK, self.color
            )
            # すねは膝から後ろへ曲がる（太ももに対して角度を負にする）
            self._limb(knee_joint, -knee, SHIN_LEN, SHIN_THICK, self.color)

    def _limb(
        self,
        joint: Mat4,
        angle: float,
        length: float,
        thickness: float,
        color: int,
    ) -> Mat4:
        """関節 joint から X軸まわりに angle 度（親に対する相対）回した棒を、色 color の箱で描き、末端の行列を返す。

        棒は関節から下向き（-Y 方向）に伸びる。正の角度で前（-Z 側）へ振れる。
        """
        bone = joint * Mat4.from_axis_angle(Vec3.RIGHT, angle)
        self.box(
            bone * Mat4.from_translation(Vec3(0.0, -length / 2.0, 0.0)),
            Vec3(thickness, length, thickness),
            color,
        )
        return bone * Mat4.from_translation(Vec3(0.0, -length, 0.0))


class MarkerView(Node):
    """人間の頭の上に出す▼。human の位置の上で、MARKER_BOB の幅・MARKER_BOB_SEC の周期で上下に揺れる。"""

    def __init__(self, human: Human) -> None:
        """描く対象の人間を受け取る。揺れの時間は起動時からの経過（time.perf_counter）で測る。"""
        super().__init__()
        self.human = human
        self._t0: float = time.perf_counter()

    def on_update(self) -> None:
        """人間の位置の真上へ、揺れの分だけずらした位置に置く（平行移動だけ）。"""
        elapsed = time.perf_counter() - self._t0
        bob = MARKER_BOB * math.sin(2.0 * math.pi * elapsed / MARKER_BOB_SEC)
        pos = self.human.pos
        self.transform = Mat4.from_translation(Vec3(pos.x, MARKER_Y + bob, pos.z))

    def on_draw(self) -> None:
        """上面の正方形（2枚）と、そこから下の頂点へ向かう4枚の三角形で、▼を MARKER_COLOR で描く。陰影なし。"""
        self.shaded(False)
        h = MARKER_HALF
        top = MARKER_DEPTH / 2.0
        c0 = Vec3(-h, top, -h)
        c1 = Vec3(h, top, -h)
        c2 = Vec3(h, top, h)
        c3 = Vec3(-h, top, h)
        tip = Vec3(0.0, -MARKER_DEPTH / 2.0, 0.0)
        self.tri(c0, c1, c2, MARKER_COLOR)
        self.tri(c0, c2, c3, MARKER_COLOR)
        for a, b in ((c0, c1), (c1, c2), (c2, c3), (c3, c0)):
            self.tri(a, b, tip, MARKER_COLOR)


class OfficeRoot(Node):
    """床・壁・机・椅子（has_props の配置ではドア・掲示板・小物も）を描く Node。キャラの描画は AgentView に任せる。"""

    def __init__(self, layout: Layout) -> None:
        """描く配置を受け取る。利用制限の値とドアの角度は App が毎フレーム書き込む。"""
        super().__init__()
        self.layout = layout
        self.five_hour: float = 0.0  # 5時間の利用制限（使った割合 0〜100）
        self.seven_day: float = 0.0  # 週間の利用制限（使った割合 0〜100）
        self.door_angle: float = 0.0  # ドアの開き角（度。0 で閉じ、正で部屋の中へ開く）

    def on_draw(self) -> None:
        """床・壁・机・椅子を描く。"""
        self.box(
            Mat4.from_translation(self.layout.floor_center),
            self.layout.floor_size,
            FLOOR_COLOR,
        )
        for wall_center, wall_size, color in self.layout.walls:
            self.box(Mat4.from_translation(wall_center), wall_size, color)
        for desk_center in self.layout.desks:
            # 天板
            self.box(
                Mat4.from_translation(Vec3(desk_center.x, DESK_TOP_Y, desk_center.z)),
                DESK_TOP_SIZE,
                DESK_COLOR,
            )
            # 左右の側板（間は空けて、座った人の脚が入るようにする）
            for x_sign in (-1.0, 1.0):
                side_center = Vec3(
                    desk_center.x + x_sign * DESK_SIDE_X, DESK_SIDE_Y, desk_center.z
                )
                self.box(
                    Mat4.from_translation(side_center),
                    DESK_SIDE_SIZE,
                    DESK_COLOR,
                )
        # 椅子は全部の席に、椅子の色（CHAIR_COLOR）で置く
        for seat, seat_yaw, _ in self.layout.seats:
            chair = Mat4.from_translation(seat) * Mat4.from_axis_angle(
                Vec3.UP, seat_yaw
            )
            self.box(
                chair * Mat4.from_translation(CHAIR_SEAT_CENTER),
                CHAIR_SEAT_SIZE,
                CHAIR_COLOR,
            )
            self.box(
                chair * Mat4.from_translation(CHAIR_BACK_CENTER),
                CHAIR_BACK_SIZE,
                CHAIR_COLOR,
            )
        if self.layout.has_props:
            self._draw_door()
            self._draw_board()
            self._draw_props()

    def _draw_door(self) -> None:
        """REST ROOM のドアの板と、ドアの上の札（動かない）を描く。"""
        # 蝶番から door_angle 度回した先に、板の中心（板の半分の位置）を置く。正の角度で +X（部屋の中）へ開く
        hinge = Mat4.from_translation(Vec3(DOOR_X, 0.0, DOOR_Z - DOOR_WIDTH / 2.0))
        panel = (
            hinge
            * Mat4.from_axis_angle(Vec3.UP, self.door_angle)
            * Mat4.from_translation(Vec3(0.0, DOOR_HEIGHT / 2.0, DOOR_WIDTH / 2.0))
        )
        self.box(panel, Vec3(DOOR_THICK, DOOR_HEIGHT, DOOR_WIDTH), DOOR_COLOR)
        self.box(
            Mat4.from_translation(Vec3(DOOR_X, DOOR_SIGN_Y, DOOR_Z)),
            DOOR_SIGN_SIZE,
            SIGN_COLOR,
        )

    def _draw_board(self) -> None:
        """奥の壁の白い板と、利用制限の2本の棒（5時間は黄、週間は赤）を描く。"""
        self.box(Mat4.from_translation(BOARD_CENTER), BOARD_SIZE, BOARD_COLOR)
        self._draw_bar_frame(FIVE_HOUR_BAR_Y)
        self._draw_bar(self.five_hour, FIVE_HOUR_BAR_Y, FIVE_HOUR_BAR_COLOR)
        self._draw_bar_frame(WEEK_BAR_Y)
        self._draw_bar(self.seven_day, WEEK_BAR_Y, WEEK_BAR_COLOR)

    def _draw_bar_frame(self, y: float) -> None:
        """100% の長さの枠（細い黒い箱4本）を、棒の外側に描く。0% でも描く。枠は棒を隠さない。"""
        w = BAR_FRAME_W
        half_len = BAR_MAX_LEN / 2.0
        half_h = BAR_HEIGHT / 2.0
        center_x = BAR_LEFT_X + half_len
        # 上下の箱は、左右の箱の角まで覆う横幅にする
        for dy in (-(half_h + w / 2.0), half_h + w / 2.0):
            self.box(
                Mat4.from_translation(Vec3(center_x, y + dy, BAR_Z)),
                Vec3(BAR_MAX_LEN + 2.0 * w, w, BAR_DEPTH),
                BAR_FRAME_COLOR,
            )
        for dx in (-(half_len + w / 2.0), half_len + w / 2.0):
            self.box(
                Mat4.from_translation(Vec3(center_x + dx, y, BAR_Z)),
                Vec3(w, BAR_HEIGHT, BAR_DEPTH),
                BAR_FRAME_COLOR,
            )

    def _draw_bar(self, percent: float, y: float, color: int) -> None:
        """左端 BAR_LEFT_X から、割合 percent（0〜100）に比例した長さの棒を描く。0 以下なら描かない。"""
        length = BAR_MAX_LEN * percent / 100.0
        if length <= 0.0:
            return
        self.box(
            Mat4.from_translation(Vec3(BAR_LEFT_X + length / 2.0, y, BAR_Z)),
            Vec3(length, BAR_HEIGHT, BAR_DEPTH),
            color,
        )

    def _draw_props(self) -> None:
        """書棚（本の段つき）・観葉植物・丸テーブル（脚・台座・コーヒーメーカー）を描く。"""
        for shelf_x in BOOKSHELF_XS:
            self.box(
                Mat4.from_translation(Vec3(shelf_x, BOOKSHELF_Y, BOOKSHELF_Z)),
                BOOKSHELF_SIZE,
                BOOKSHELF_COLOR,
            )
            for book_y, book_color in zip(BOOK_YS, BOOK_COLORS):
                self.box(
                    Mat4.from_translation(Vec3(shelf_x, book_y, BOOK_Z)),
                    BOOK_SIZE,
                    book_color,
                )
        for plant_x, plant_z in PLANT_POSITIONS:
            self.box(
                Mat4.from_translation(Vec3(plant_x, PLANT_POT_Y, plant_z)),
                PLANT_POT_SIZE,
                PLANT_POT_COLOR,
            )
            self.sphere(Vec3(plant_x, PLANT_LEAF_Y, plant_z), PLANT_LEAF_RADIUS, PLANT_LEAF_COLOR)

        # 丸テーブル。elli の大きさは直径で、X軸まわりに -90 度回すと上（+Y）を向く
        table_top = Mat4.from_translation(Vec3(TABLE_X, TABLE_Y, TABLE_Z)) * Mat4.from_euler(
            Vec3(-90.0, 0.0, 0.0)
        )
        self.elli(table_top, TABLE_RADIUS * 2.0, TABLE_RADIUS * 2.0, TABLE_COLOR)
        self.box(
            Mat4.from_translation(Vec3(TABLE_X, TABLE_LEG_Y, TABLE_Z)),
            TABLE_LEG_SIZE,
            TABLE_COLOR,
        )
        base = Mat4.from_translation(Vec3(TABLE_X, TABLE_BASE_Y, TABLE_Z)) * Mat4.from_euler(
            Vec3(-90.0, 0.0, 0.0)
        )
        self.elli(base, TABLE_BASE_DIAMETER, TABLE_BASE_DIAMETER, TABLE_COLOR)

        # コーヒーメーカー（テーブルの上）と、上の小さな赤いランプ
        self.box(
            Mat4.from_translation(Vec3(TABLE_X, TABLE_Y + 16.0, TABLE_Z)),
            COFFEE_BODY_SIZE,
            COFFEE_BODY_COLOR,
        )
        self.box(Mat4.from_translation(COFFEE_LAMP_POS), COFFEE_LAMP_SIZE, COFFEE_LAMP_COLOR)


def _char_cols(ch: str) -> int:
    """1文字の桁数。全角（東アジアの幅が W・F）は2桁、それ以外は1桁。"""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _wrap_text(text: str, cols: int, codes: frozenset[int] = frozenset()) -> list[str]:
    """text を桁数 cols で折り返した行の一覧。空の文字列は [""] を返す。

    codes（UI フォントの文字コードの集合）があるときは、各字を font_safe で描く字に直してから幅を数える。
    返す行の字は元のまま（描くときに font_safe を通す）。
    """
    rows: list[str] = []
    line = ""
    width = 0
    for ch in text:
        w = _char_cols(font_safe(ch, codes))
        if width + w > cols:
            rows.append(line)
            line = ""
            width = 0
        line += ch
        width += w
    rows.append(line)
    return rows


# ---- UI フォントに無い字の置き換え（見え方だけの直し。送る文字・会話記録・覚える文字は変えない） ----

# UI フォント（PixelMplus12）に無い字を、形の似た字に置き換える表。置き換え先もフォントに無ければ '?' にする
GLYPH_SUBSTITUTES: dict[str, str] = {
    "〜": "～", "–": "-", "—": "―", "✔": "v", "▸": ">", "❯": ">", "⎿": "└", "█": "■", "▌": "■",
    "╭": "┌", "╰": "└", "◐": "●", "╮": "┐", "╯": "┘", "⏵": ">", "▲": "^",
}
_FONT_SAFE_SPACES = frozenset(" \t\r\n　")  # 空白・改行・タブ（半角・全角）はそのまま
_font_safe_cache: dict[tuple[frozenset[int], str], str] = {}  # (codes, 字) → 描く字


def _cmap_format4_codes(buf: bytes, off: int) -> set[int]:
    """cmap の形式4（BMP の区間表）から文字コードの集合を作る。"""
    seg_x2 = struct.unpack_from(">H", buf, off + 6)[0]
    seg = seg_x2 // 2
    end_off = off + 14  # endCode の位置（format・length・language・segCountX2・searchRange・entrySelector・rangeShift の後）
    start_off = end_off + seg_x2 + 2  # 間の reservedPad（2バイト）の後が startCode
    ends = struct.unpack_from(f">{seg}H", buf, end_off)
    starts = struct.unpack_from(f">{seg}H", buf, start_off)
    codes: set[int] = set()
    for first, last in zip(starts, ends):
        last = min(last, 0xFFFE)  # 0xFFFF は字ではない
        if first <= last:
            codes.update(range(first, last + 1))
    return codes


def _cmap_format12_codes(buf: bytes, off: int) -> set[int]:
    """cmap の形式12（全 Unicode の区間表）から文字コードの集合を作る。"""
    groups = struct.unpack_from(">I", buf, off + 12)[0]
    codes: set[int] = set()
    for g in range(groups):
        first, last, _glyph = struct.unpack_from(">III", buf, off + 16 + g * 12)
        codes.update(range(first, min(last, 0x10FFFF) + 1))
    return codes


def font_codepoints(path: Path) -> frozenset[int]:
    """TTF の cmap の形式4・12から、フォントに入っている文字コードの集合を返す。読めない・壊れているときは空の集合。"""
    try:
        with path.open("rb") as f:
            head = f.read(12)
            num_tables = struct.unpack_from(">H", head, 4)[0]
            directory = f.read(16 * num_tables)
            cmap: bytes | None = None
            for i in range(num_tables):
                tag, _checksum, offset, length = struct.unpack_from(">4sIII", directory, i * 16)
                if tag == b"cmap":
                    f.seek(offset)
                    cmap = f.read(length)
                    break
        if cmap is None:
            return frozenset()
        codes: set[int] = set()
        seen: set[int] = set()
        num_sub = struct.unpack_from(">H", cmap, 2)[0]
        for k in range(num_sub):
            sub_off = struct.unpack_from(">I", cmap, 4 + k * 8 + 4)[0]
            if sub_off in seen:
                continue
            seen.add(sub_off)
            fmt = struct.unpack_from(">H", cmap, sub_off)[0]
            if fmt == 4:
                codes |= _cmap_format4_codes(cmap, sub_off)
            elif fmt == 12:
                codes |= _cmap_format12_codes(cmap, sub_off)
        return frozenset(codes)
    except (OSError, struct.error, ValueError, IndexError):
        return frozenset()


def _font_safe_char(ch: str, codes: frozenset[int]) -> str:
    """1字を、フォントで描ける字に直す（入っていればそのまま、無ければ置き換え、それも無ければ '?'）。"""
    key = (codes, ch)
    cached = _font_safe_cache.get(key)
    if cached is not None:
        return cached
    if ch in _FONT_SAFE_SPACES or ord(ch) in codes:
        out = ch
    else:
        sub = GLYPH_SUBSTITUTES.get(ch, "")
        out = sub if sub and all(ord(c) in codes for c in sub) else "?"
    _font_safe_cache[key] = out
    return out


def font_safe(text: str, codes: frozenset[int]) -> str:
    """UI フォントで描ける形の文字列にする。codes が空（フォントを読めなかった）ときは text をそのまま返す。"""
    if not codes:
        return text
    return "".join(_font_safe_char(ch, codes) for ch in text)


@dataclass
class TalkPage:
    """会話のダイアログの1ページ。プロンプト1つと、それへの返事（届いた順）。notice は決まった形の知らせか。"""

    prompt: str  # 見せる文（prompt_display を通したもの）
    notice: bool  # 知らせなら True（プロンプトを灰色で出す）
    replies: list[str] = field(default_factory=list)  # 返事の全文（届いた順）


@dataclass
class PermRequest:
    """許可の依頼が1件。received は受け取った時刻、conn は hook とのつながり（答えを返すまで開けておく）。"""

    tool_name: str
    tool_input: object
    received: float
    conn: socket.socket | None
    suggestions: list[dict[str, object]] = field(default_factory=list)  # Claude Code の案（permission_suggestions の辞書だけ）。無ければ空


def _recv_line(conn: socket.socket, timeout_sec: float) -> str:
    """相手から1行（改行まで）読む。全体で timeout_sec 秒まで。時間切れ・切断・長すぎるときは例外。"""
    deadline = time.monotonic() + timeout_sec
    buf = bytearray()
    while b"\n" not in buf:
        remain = deadline - time.monotonic()
        if remain <= 0:
            raise TimeoutError(t("err_request_timeout"))
        conn.settimeout(remain)
        chunk = conn.recv(4096)
        if not chunk:
            raise ConnectionError(t("err_peer_closed"))
        buf += chunk
        if len(buf) > PERM_MAX_LINE:
            raise ValueError(t("err_request_too_long"))
    return bytes(buf).split(b"\n", 1)[0].decode("utf-8")


def _close_quietly(conn: socket.socket | None) -> None:
    """つながりを閉じる。None や閉じられないときは何もしない。"""
    if conn is None:
        return
    try:
        conn.close()
    except OSError:
        pass


class PermServer:
    """hook（pca_perm_hook.py）からの許可の依頼を受ける待ち受け。accept と読み取りは裏のスレッド、依頼は queue に入れてメインのスレッドが取り出す。"""

    # このプロセスでいま待ち受けている PermServer。同じプロセス内の前の待ち受けは、次の start で止めてから bind する
    _active: "PermServer | None" = None

    def __init__(
        self, name: str | None = None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """name は待ち受けの名前（省略時は環境変数 PCA_PERM_SOCKET か既定の名前）。clock は受け取った時刻に使う。"""
        self.name: str = name if name is not None else perm_socket_name()
        if not self.name.startswith("\0"):
            self.name = "\0" + self.name  # 先頭の \0 は抽象名前空間（ファイルを作らない）の印
        self.clock: Callable[[], float] = clock
        # 依頼の (受け取った時刻, 辞書, つながり)。通知（notification）はつながりを閉じて None で入れる
        self.queue: queue.Queue[tuple[float, dict[str, object], socket.socket | None]] = queue.Queue()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop: threading.Event = threading.Event()

    def start(self) -> bool:
        """待ち受けを始める。すでに待ち受け中なら何もせず True。bind に失敗（ほかで使用中）なら、出力して False。"""
        if self._sock is not None:
            return True
        previous = PermServer._active
        if previous is not None and previous is not self and previous.name == self.name and previous._sock is not None:
            previous.stop()  # 同じプロセスの前の待ち受けは止める（残りの依頼は deny）。注意の行は出さない
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(self.name)
            sock.listen(8)
        except OSError:
            sock.close()
            print(t("perm_server_busy"), flush=True)
            return False
        sock.settimeout(PERM_ACCEPT_SEC)
        self._sock = sock
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, args=(sock, self._stop), daemon=True)
        self._thread.start()
        PermServer._active = self
        return True

    def _accept_loop(self, sock: socket.socket, stop: threading.Event) -> None:
        """接続を待ち、つながるたびに読み取りのスレッドを作る。stop が立つか、待ち受けが閉じたら終わる。"""
        while not stop.is_set():
            try:
                conn, _ = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._read_one, args=(conn,), daemon=True).start()

    def _read_one(self, conn: socket.socket) -> None:
        """接続から依頼の1行を読んで queue に入れる。壊れた依頼・種類が不明なものは閉じて捨てる。"""
        try:
            data = json.loads(_recv_line(conn, PERM_READ_SEC))
            if not isinstance(data, dict):
                raise ValueError(t("err_request_not_dict"))
            kind = data.get("type")
            if kind == "notification":
                _close_quietly(conn)
                self.queue.put((self.clock(), data, None))
            elif kind == "permission":
                self.queue.put((self.clock(), data, conn))
            else:
                raise ValueError(t("err_unknown_kind"))
        except Exception:
            _close_quietly(conn)

    def answer(self, conn: socket.socket | None, answer: str) -> bool:
        """答え（{"answer": ...}の1行）を送って閉じる。送れたら True。送れなければ False（例外は出さない）。"""
        if conn is None:
            return False
        try:
            conn.sendall((json.dumps({"answer": answer}, ensure_ascii=False) + "\n").encode("utf-8"))
            sent = True
        except Exception:
            sent = False
        _close_quietly(conn)
        return sent

    def is_closed(self, conn: socket.socket | None) -> bool:
        """相手が閉じたか。読めて、中身が空（閉じた）なら True。調べられないときも True とする。"""
        if conn is None:
            return True
        try:
            readable, _, _ = select.select([conn], [], [], 0)
            if not readable:
                return False
            return conn.recv(1, socket.MSG_PEEK) == b""
        except (OSError, ValueError):
            return True

    def deny_all(self) -> None:
        """queue に残っている依頼に、すべて deny を返す（待ち受けは止めない）。"""
        while True:
            try:
                _, _, conn = self.queue.get_nowait()
            except queue.Empty:
                return
            if conn is not None:
                self.answer(conn, "deny")

    def stop(self) -> None:
        """待ち受けを閉じ、queue に残っている依頼にも deny を返す。読み取りの途中の分は hook 側の時間切れに任せる。"""
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=PERM_ACCEPT_SEC * 4)
        self._thread = None
        sock, self._sock = self._sock, None
        _close_quietly(sock)
        self.deny_all()
        if PermServer._active is self:
            PermServer._active = None


def _perm_suggestions(value: object) -> list[dict[str, object]]:
    """依頼の permission_suggestions から辞書だけを取り出す。list でなければ空の list。"""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _suggestion_rows(s: list[dict[str, object]]) -> list[str]:
    """Claude Code の案を、人の言葉の行の一覧にする（「いつも許可」の確かめと履歴に出す）。"""
    rows: list[str] = []
    for sg in s:
        kind = sg.get("type")
        destination = sg.get("destination")
        if kind == "setMode":
            mode = sg.get("mode")
            if mode == "acceptEdits":
                text = t("suggest_accept_edits")
            else:
                text = t("suggest_set_mode", mode=mode)
            if destination != "session":
                text += t("suggest_destination", destination=destination)
        elif kind == "addRules":
            rules = sg.get("rules")
            names: list[str] = []
            for rule in rules if isinstance(rules, list) else []:
                if not isinstance(rule, dict):
                    continue
                content = rule.get("ruleContent")
                tool = str(rule.get("toolName"))
                names.append(f"{tool}({content})" if isinstance(content, str) and content else tool)
            scope_key = PERM_RULE_SCOPE.get(str(destination))
            where = t(scope_key) if scope_key else str(destination)
            text = t("suggest_add_rules", where=where, names=t("list_sep").join(names))
            behavior = sg.get("behavior")
            if behavior is not None and behavior != "allow":
                text = f"[{behavior}] {text}"
        elif kind == "addDirectories":
            dirs = sg.get("directories")
            shown = t("list_sep").join(str(d) for d in dirs) if isinstance(dirs, list) else str(dirs)
            text = t("suggest_add_dirs", shown=shown)
        else:
            text = f"{kind}: {json.dumps(sg, ensure_ascii=False, separators=(',', ':'))}"
        rows.append(text)
    return rows


def _tool_input_rows(tool_input: object) -> list[tuple[str, str]]:
    """道具の入力を (項目名, 値の文字) の一覧にする。辞書なら項目ごと、それ以外は「入力」1つだけ。"""
    if isinstance(tool_input, dict):
        rows: list[tuple[str, str]] = []
        for key, value in tool_input.items():
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            rows.append((str(key), text))
        return rows
    return [(t("perm_input_label"), json.dumps(tool_input, ensure_ascii=False))]


def _first_line(text: str) -> str:
    """文の1行目を、前後の空白を除いて返す。"""
    return text.split("\n")[0].strip()


def _short_text(text: str) -> str:
    """吹き出しに出す文字：最初の4文字＋"....".4文字以下ならそのまま（"...." は付けない）。文字数は len で数える。"""
    return text if len(text) <= 4 else text[:4] + "...."


def _slash_result_lines(lines: list[str], cmd: str) -> list[str]:
    """画面の行から、送った文（cmd）の後ろの結果だけを取り出す。
    最後の「❯ <送った文>」の行の次から、入力欄の上の罫線（─ だけの行）の手前まで。
    「❯」の行が見つからなければ画面全体。罫線が見つからなければ最後まで。"""
    head = "❯ " + _first_line(cmd)
    # 本物の画面では「❯」のあとが改行させない空白（\xa0）なので、ふつうの空白に直してから比べる（2026-11-21 実物で確認）
    start = next(
        (k for k in range(len(lines) - 1, -1, -1) if lines[k].replace("\xa0", " ").startswith(head)), None
    )
    if start is None:
        return lines
    end = len(lines)
    for k in range(start + 1, len(lines)):
        stripped = lines[k].strip()
        if stripped and set(stripped) == {"─"}:
            end = k
            break
    return lines[start + 1 : end]


# スプラッシュを飛ばすキー（すべてのキーボードのキー。Esc を含む。KEY_NONE は除く）
SPLASH_SKIP_KEYS: tuple[int, ...] = tuple(
    value
    for name, value in vars(pyxel).items()
    if name.startswith("KEY_") and name != "KEY_NONE" and isinstance(value, int)
)


class App:
    """Pyxel の初期化、シーン構築、毎フレームの更新と描画を担当する。"""

    def __init__(
        self,
        fps: int,
        seed: int | None,
        layout: str = "proto",
        agents: int = 3,
        config_path: str | None = None,
        time_scale: float = DEFAULT_TIME_SCALE,
        claude: bool = False,
        workdir: str | None = None,
        session: str = "pyxelcube_agents",
        bridge_factory: Callable[[str, str], Bridge] | None = None,
        splash: bool = False,
    ) -> None:
        """fps を 1〜60 に収めて pyxel.init し、シーンを構築する。pyxel.run は呼ばない。

        claude を True にすると、office で本物の Claude Code とつなぐ準備をする（bridge_factory 省略時は Bridge(workdir, session)）。
        claude が False のときは今までどおり。
        splash を True にすると、起動時に「Powered by Pyxel」とアプリ名のスプラッシュを出す（終わるまで何も操作しない。キーかマウスの左クリックで飛ばす）。
        splash が False のときは出さない（テストは False で作る。main() だけ True を渡す）。

        layout は "proto" か "office"。agents は 1〜その配置の席数に収める。
        config_path は設定ファイル。省略時は pyxelcube_agents.py と同じフォルダの pyxelcube_agents.toml。
        time_scale は行き先・会話のタイマーの早回し倍率（0 以下は 1.0）。
        """
        if layout not in LAYOUTS:
            raise ValueError(t("err_layout", choices=list(LAYOUTS), value=repr(layout)))
        self.fps: int = min(60, max(1, fps))
        scale = _as_finite_float(time_scale)
        self.time_scale: float = scale if scale is not None and scale > 0.0 else DEFAULT_TIME_SCALE
        self.layout_name: str = layout
        self.layout: Layout = LAYOUTS[layout]
        if self.layout.has_props:
            # office は 3D と下の履歴・入力欄を並べた大きい画面。Esc では閉じない
            pyxel.init(
                OFFICE_SCREEN_W,
                OFFICE_SCREEN_H,
                title=f"{APP_NAME} {APP_VERSION}",
                fps=self.fps,
                display_scale=OFFICE_DISPLAY_SCALE,
                quit_key=pyxel.KEY_NONE,
            )
        else:
            pyxel.init(SCREEN_W, SCREEN_H, title=f"{APP_NAME} {APP_VERSION}", fps=self.fps)
        pyxel.mouse(True)  # 窓の中にマウスの矢印を出す（クリックで人間を歩かせる）
        # 起動時のスプラッシュ（pyxel.init のあとに作る。画面の大きさと fps に合わせる）。出さないときは None
        self.splash: Splash | None = (
            Splash(pyxel.width, pyxel.height, self.fps, APP_NAME, APP_VERSION) if splash else None
        )

        # office の操作と画面の状態。モードは起動時 WALK
        self.mode: str = MODE_WALK
        self.input_buf: str = ""  # PROMPT の入力中の文字
        self.ime_composing: bool = False  # 日本語の変換中と推測しているか
        self._ime_wait_text: int = 0  # 英字キーのあと、文字を待っている残りフレーム
        self._pending_enter: int = 0  # Enter のあと、確定の文字を待っている残りフレーム（0 なら送信待ちはない）
        # 日本語入力の状態の札。"?"（分からない）・"あ"（オン）・"A"（オフ）。実機で、Shift＋Ctrl で切り替わる
        self.ime_state: str = "?"
        self.history: list[str] = []  # 履歴（折り返したあとの行）
        self.history_color: list[int] = []  # 履歴の行ごとの文字の色（history と同じ長さ）
        self.history_scroll: int = 0  # 一番上に出ている行の番号
        self.ui_font: pyxel.Font | None = None
        self.ui_codes: frozenset[int] = frozenset()  # UI フォントに入っている文字コード（空なら置き換えをしない）
        if self.layout.has_props:
            self.ui_font = pyxel.Font(str(UI_FONT_PATH), UI_FONT_SIZE)
            self.ui_codes = font_codepoints(UI_FONT_PATH)

        # 利用制限の JSON の場所と読み直しの間隔（設定ファイル。無いときは既定値）
        cfg_path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
        json_path, reload_sec = load_rate_settings(cfg_path)
        self.rate_json_path: Path = Path(json_path).expanduser()
        self._reload_every: int = max(1, round(reload_sec * self.fps))  # 読み直すフレーム数
        self._reload_count: int = 0  # 前回読み直してから数えたフレーム数
        self.five_hour: float = 0.0  # 5時間の利用制限（使った割合 0〜100）
        self.seven_day: float = 0.0  # 週間の利用制限（使った割合 0〜100）
        self.manual_limits: bool = False  # キー 1〜4 で手動に変えたら True（以後は JSON を読まない）

        # ドア（REST ROOM）。door_open が目標（True で開く）、door_angle が今の角度（0〜90）
        self.door_open: bool = False
        self.door_angle: float = 0.0

        # 乱数はここで1つだけ作り、各キャラに渡す
        self.rng = random.Random(seed)
        self.agents: list[Agent] = []
        self.next_index: int = 0  # 次にスペースキーで作業状態にするキャラの番号

        self.measured_fps: float = 0.0
        self._frame_times: deque[float] = deque()

        self.camera: Camera  # _build_scene で作る

        # カメラの注視点・注視点から目への単位ベクトル・距離。ホイールで距離だけ変える
        self.cam_target: Vec3 = self.layout.camera_target
        eye_offset = self.layout.camera_eye - self.layout.camera_target
        self.cam_dist: float = eye_offset.length()
        # 起動時の向きは今の目の位置から求める。カーソルキーで cam_yaw・cam_pitch を変える
        direction = eye_offset.normalize()
        self.cam_yaw: float = math.degrees(math.atan2(direction.x, direction.z)) % 360.0
        self.cam_pitch: float = math.degrees(math.asin(direction.y))
        self.cam_dir: Vec3 = _view_dir(self.cam_yaw, self.cam_pitch)

        # 障害物（机・椅子・壁）。席の番号 i の机と椅子は owner = i。配置の全席ぶん作る
        self.obstacles: list[Obstacle] = _build_obstacles(self.layout)
        # 丸い障害物（中心の x, z, 半径）。丸いものは has_props の配置（丸テーブル）だけ
        self.circles: list[tuple[float, float, float]] = _build_circles(self.layout)
        # 行き先・道探し（office だけ）。道の地図は初期化で1回だけ作る（障害物は動かない）
        self.nav: NavGrid | None = None
        self.spot_manager: SpotManager | None = None
        if self.layout.has_props:
            self.nav = NavGrid(
                self.layout.wander_x,
                self.layout.wander_z,
                [ob.rect for ob in self.obstacles],
                self.circles,
            )
            self.spot_manager = SpotManager(OFFICE_SPOTS, self.rng)
        # 道を探す順番待ちの列（人の番号。先頭から順に探す）。同じ人は二重に並ばない
        self._nav_queue: deque[int] = deque()

        # 人間（office だけ。_build_scene で作る）。agents には入れない（番号のずれを防ぐ）
        self.human: Human | None = None
        self.talk_partner: int | None = None  # 会話している相手の番号（会話していなければ None）
        # カメラの切り替え。(target, yaw, pitch, dist)。from は切り替え中だけ入る
        self._cam_from: tuple[Vec3, float, float, float] | None = None
        self._cam_to: tuple[Vec3, float, float, float] | None = None
        self._cam_blend: float = 0.0  # 切り替えの進み（0〜1。1 で終わり）
        self._saved_view: tuple[float, float, float] | None = None  # 会話の前の (yaw, pitch, dist)
        self._follow_replan: float = 0.0  # 会話相手が歩くとき、人間が道を探し直すまでの残り時間（秒）
        self._talk_seat_moved: bool = False  # 会話相手が座ったあと、人間を机の正面へ動かし終えたか

        count = int(_clamp(agents, 1, len(self.layout.seats)))
        self.scene: OfficeRoot = self._build_scene(count)
        # 各キャラが進めないで立ち止まっている時間（秒）
        self._stuck_time: list[float] = [0.0] * len(self.agents)
        self._stuck_state: list[str] = [WANDER] * len(self.agents)  # 前のフレームの状態（変わったら計り直す）
        self._stuck_count: list[int] = [0] * len(self.agents)  # 引っかかりが続いた回数（この回数で横へよける）
        self._chat: list[Chatter] = [Chatter() for _ in self.agents]  # 会話中の人の状態（office だけ使う）
        self._speakers: dict[str, int] = {}  # 行き先の名前 → 話し手の番号
        self._speaker_timers: dict[str, float] = {}  # 行き先の名前 → 話し手を交代するまでの残り時間（秒）
        self.stat_replans: int = 0  # 引っかかって道を探し直した回数（計測用）
        self.stat_sidesteps: int = 0  # 引っかかって横へよけた回数（計測用）
        self.stat_give_ups: int = 0  # 行き先へ行けずにあきらめた回数（計測用）

        self._init_claude(claude, workdir, session, bridge_factory)
        if not self.claude:
            self.reload_rate_limits()  # --claude のときは JSON を読まない（/usage の値を使う）
        self._sync_scene_values()

    def _build_scene(self, count: int) -> OfficeRoot:
        """ルートの OfficeRoot、カメラ、床・壁・机、先頭 count 席のキャラを組み立てる。"""
        layout = self.layout
        root = OfficeRoot(layout)
        root.shading = Shading(pyxel.colors)

        camera = Camera()
        camera.clear_color = 0
        self.camera = camera
        root.camera = camera
        self._apply_camera()

        for i, (seat, seat_yaw, color) in enumerate(layout.seats[:count]):
            name = chr(ord("A") + i)
            agent = Agent(
                name,
                seat,
                self.rng,
                seat_yaw=seat_yaw,
                wander_x=layout.wander_x,
                wander_z=layout.wander_z,
                obstacles=tuple(ob.rect for ob in self.obstacles),
                circles=tuple(self.circles),
                nav=self.nav,
                on_path_request=lambda i=i: self._request_path(i),
            )
            if layout.has_props:
                # 起動時のうろつき時間を 0〜OUTING_WANDER_SEC の乱数で始める。全員が同じ瞬間に出かけないようにする
                agent.wander_time = self.rng.uniform(0.0, OUTING_WANDER_SEC)
            self.agents.append(agent)
            root.add_child(AgentView(agent, color))

        if layout.has_props:
            # 人間（ユーザーの分身）。agents には入れず、描画（人型と▼）と操作だけ別に持つ
            human = Human(
                Vec3(HUMAN_START[0], 0.0, HUMAN_START[1]),
                self.rng,
                wander_x=layout.wander_x,
                wander_z=layout.wander_z,
                obstacles=tuple(ob.rect for ob in self.obstacles),
                circles=tuple(self.circles),
                nav=self.nav,
            )
            self.human = human
            root.add_child(AgentView(human, HUMAN_BODY_COLOR, skin_color=HUMAN_SKIN_COLOR))
            root.add_child(MarkerView(human))
            # 起動時のカメラの注視点は人間の位置。人間が止まっている間はカメラも動かない
            self.cam_target = Vec3(HUMAN_START[0], 0.0, HUMAN_START[1])
            self._apply_camera()

        return root

    def _apply_camera(self) -> None:
        """カメラの位置・向きと遠方クリップ距離を、今の注視点・yaw・pitch・距離に合わせて設定する。"""
        self.cam_dir = _view_dir(self.cam_yaw, self.cam_pitch)
        eye = self.cam_target + self.cam_dir * self.cam_dist
        self.camera.transform = Mat4.look_at(eye, self.cam_target)
        # どの距離でも部屋全体が描かれるように、遠方クリップは距離に余裕を足した値にする
        self.camera.far = self.cam_dist + FAR_MARGIN

    def update(self) -> None:
        """キーとマウスを処理し、全員の行動とシーンを1フレーム進める。office では WALK と PROMPT のモードで操作が変わる。"""
        # スプラッシュの間は、進めるだけ。キーかマウスの左クリックがあれば飛ばす（飛ばしたフレームも何もしない）
        if self.splash is not None and not self.splash.finished:
            self.splash.update()
            if self._splash_skip_pressed():
                self.splash.skip()
            return
        # このフレームの最初に、ダイアログが開いていたかを覚える。開いていたフレームは、ほかの入力を一切処理しない
        dialog_open = self._dialog
        # このフレームの最初に、メニューが開いていたかも覚える。開いていたフレームは、入力欄のキー（Esc を含む）を処理しない
        menu_open = self._menu is not None
        if self.claude and self._menu is None:
            self._update_claude_keys()  # F1 と、ダイアログの 1〜3（選ぶメニューの間は止める）
        # コマンドの窓（SLASH）の間は、キーを tmux へ送り・画面を読み・閉じるだけ。WALK・入力欄・Y/N/T などは止める
        slash = self._slash_open and self.claude
        if slash:
            self._update_slash()
        if self._menu is not None:
            self._update_menu()  # 選ぶメニューの間は、キーで選ぶ・決める・閉じる（ほかのキー操作は止める）
        # モードの切り替えと、PROMPT の文字入力（office だけ。ダイアログが開いていたフレームは止める）
        if self.layout.has_props and not dialog_open and not slash and not menu_open and self._menu is None:
            self._update_mode_keys()
        # WALK のときだけ3Dの操作を受け付ける。自動で WALK に切り替えた直後の守り時間の間は、キー操作を受け付けない（マウスは止めない）
        walking = not dialog_open and not self._prompting() and not self._perm_guard_active()
        if walking:
            # --claude のときは、スペースキーで作業を始めない（製品版）
            if pyxel.btnp(pyxel.KEY_SPACE) and not self.claude:
                self._start_next_work()
            self._update_rate_keys()
            if pyxel.btnp(pyxel.KEY_D):
                self.door_open = not self.door_open
                self._door_auto = False  # 自分で開けたドアは、出入りの後に自動で閉めない
            if pyxel.btnp(pyxel.KEY_Q):
                self.end_talk()  # 会話していなければ何もしない
            if self.claude:
                self._update_talk_dialog_keys()  # PageUp・PageDown（ダイアログの中身）
                self._update_talk_pages()  # ↑↓（メインとのやりとりのページ。会話中はカメラが固定なので、↑↓は視点に渡らない）
        if self.claude:
            self._update_talk_dialog()  # ダイアログのつまみの押しを確かめる（会話が終わったら戻す）
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if self._menu is not None:
                self._menu_click(pyxel.mouse_x, pyxel.mouse_y)  # 選ぶメニューの中の行・外のクリック
            elif slash:
                self._slash_click(pyxel.mouse_x, pyxel.mouse_y)  # 窓の中の溝・つまみ。結果だけの窓は窓の外で閉じる
            elif dialog_open:
                self._claude_click(pyxel.mouse_x, pyxel.mouse_y)  # ダイアログの選び方だけ受け付ける
            else:
                self._on_left_click(pyxel.mouse_x, pyxel.mouse_y)

        # ホイール：コマンドの窓の上ならその中を動かす。会話のダイアログの上ならダイアログを動かす（ズームしない）。
        # 履歴の枠の上なら履歴をスクロール、3D の範囲の上なら今どおりズーム（会話中は動かさない）
        wheel = pyxel.mouse_wheel
        if slash and wheel != 0:
            self._slash_wheel(wheel)
        elif wheel != 0 and not dialog_open and self._menu is None:
            talk_partner = self._talk_dialog_partner()
            if talk_partner is not None and self._in_rect(
                pyxel.mouse_x, pyxel.mouse_y, DLG_X, DLG_Y, DLG_W, DLG_H
            ):
                self._scroll_talk(talk_partner, -DLG_WHEEL_ROWS * wheel)
            elif self.layout.has_props and self._in_rect(
                pyxel.mouse_x, pyxel.mouse_y, HISTORY_X, HISTORY_Y, HISTORY_W, HISTORY_H
            ):
                self.history_scroll = _clamp(
                    self.history_scroll - wheel, 0, self._max_scroll()
                )
            elif self._wheel_zooms(pyxel.mouse_x, pyxel.mouse_y) and self.talk_partner is None:
                self.cam_dist *= ZOOM_STEP**wheel
                self.cam_dist = _clamp(self.cam_dist, self.layout.zoom_min, self.layout.zoom_max)
                self._apply_camera()

        dt = 1.0 / self.fps
        timer_dt = dt * self.time_scale  # 行き先・会話のタイマーだけ早回しする（歩く速さは変えない）
        self._update_door(dt)
        self._update_rate_limits()
        if walking and self.talk_partner is None:
            self._update_view(dt)  # 会話中はカーソルキーで視点を動かさない
        if self.spot_manager is not None:
            self._update_wanderers(timer_dt)
        self._serve_nav_queue()  # 道を探す順番が来た人に道を探す（1フレームに NAV_MAX_PER_FRAME 人まで）
        # 押し出し前後の移動距離を測るため、行動の前の位置を覚えておく
        if self.claude:
            self._update_claude(dt)  # 会話記録のイベント・終業の待ち・吹き出し・帰る時間・ドア
        prev_xz = [(a.pos.x, a.pos.z) for a in self.agents]
        for i, agent in enumerate(self.agents):
            if not agent.visible:
                continue  # 見えていない人は動かさない（--claude のとき）
            if self._is_held(i):
                agent.intended_move = 0.0  # 会話の相手は止めたまま（引っかかり判定に歩きの量を残さない）
                continue
            agent.update(dt)
        if self.human is not None:
            self.human.update(dt)
        self._update_partner(dt)
        if self.claude:
            self._finish_leaving(dt)  # 部屋を出る道を歩き終えた人（や、長すぎる人）を置き場所へ
        self._resolve_collisions()
        self._check_stuck(prev_xz, dt)
        if self.spot_manager is not None:
            self._update_spot_groups(timer_dt)
        if self.human is not None:
            self._update_camera(dt)
        self._sync_scene_values()
        self.scene.update()

        self._record_frame()

    def _prompting(self) -> bool:
        """今が PROMPT モードか（office だけ。proto は常に False）。"""
        return self.layout.has_props and self.mode == MODE_PROMPT

    def _perm_guard_active(self) -> bool:
        """自動で WALK に切り替えたあと、キー操作を受け付けない時間の中か（既定値 0.0 のときは False）。マウスは止めない。"""
        until = self._perm_key_guard_until
        return until > 0.0 and self._perm_clock() < until

    def _ctrl_held(self) -> bool:
        """Ctrl（左右どちらでも）を押しているか。"""
        return pyxel.btn(pyxel.KEY_LCTRL) or pyxel.btn(pyxel.KEY_RCTRL)

    def _prompt_exit_pressed(self) -> bool:
        """PROMPT から WALK に戻るキー（Ctrl+E）が今のフレームで押されたか。"""
        return self._ctrl_held() and pyxel.btnp(pyxel.KEY_E)

    def _update_mode_keys(self) -> None:
        """office のモード切り替えと、PROMPT の文字入力を1フレーム分処理する。

        WALK で P キーを押すと PROMPT になり、そのフレームの入力文字は足さない（p が入らないように）。
        PROMPT で Ctrl+E を押すと WALK に戻る。PROMPT で Esc を押すと、履歴に中断の行を出す（モードは変えない）。
        PROMPT で Ctrl+J を押すと改行（送信はしない）。
        日本語入力の変換中は、英字・Enter・Backspace・Esc の扱いを推測で変える（IME_* の定数の説明を参照）。
        日本語入力の状態（ime_state）は、英字の届き方と Shift＋Ctrl の切り替えから推測する。
        """
        switched = False
        if self.mode == MODE_WALK and pyxel.btnp(PROMPT_ENTER_KEY) and not self._perm_guard_active():  # 守り時間の間は P を受け付けない
            self.mode = MODE_PROMPT
            switched = True
        elif self.mode == MODE_PROMPT and self._prompt_exit_pressed():
            self.mode = MODE_WALK
            self._reset_ime()
            return  # そのフレームの入力文字（e など）は足さない
        if self.mode != MODE_PROMPT:
            return  # WALK の間は pyxel.input_text を使わない

        # 文字が来たか。P で入ったフレームと、Ctrl を押している間は足さない（来なかったものとして扱う）
        ctrl = self._ctrl_held()
        letter_pressed = any(pyxel.btnp(k) for k in IME_PRINTABLE_KEYS)
        printable = letter_pressed and (not switched) and (not ctrl)
        text = "" if (switched or ctrl) else pyxel.input_text

        # Shift＋Ctrl で日本語入力のオン・オフを切り替える。どちらかが押された瞬間で、もう一方が押されていて、英字は押されていないとき
        # （実機：この環境では Shift＋Ctrl が切り替え。「あ」と「A」を入れ替え、「?」のままなら「?」）
        shift_held = pyxel.btn(pyxel.KEY_LSHIFT) or pyxel.btn(pyxel.KEY_RSHIFT)
        shift_hit = pyxel.btnp(pyxel.KEY_LSHIFT) or pyxel.btnp(pyxel.KEY_RSHIFT)
        ctrl_hit = pyxel.btnp(pyxel.KEY_LCTRL) or pyxel.btnp(pyxel.KEY_RCTRL)
        if not letter_pressed and ((shift_hit and ctrl) or (ctrl_hit and shift_held)):
            if self.ime_state == "あ":
                self.ime_state = "A"
            elif self.ime_state == "A":
                self.ime_state = "あ"

        if text:
            # 文字が届いた。英字キーを押したフレームに届いたなら日本語入力はオフ。確定の文字なら変換は終わり
            if printable:
                self.ime_state = "A"
            # 確定の Enter の直後なら、送信を取り消して入力欄に足す（確定の文字）
            self._pending_enter = 0
            self.input_buf += text
            self.ime_composing = False
            self._ime_wait_text = 0
        elif printable:
            # 英字を押したが、日本語入力オフなら同じフレームに文字が届くはず。来なければ待つ
            self._ime_wait_text = IME_GRACE_FRAMES + 1
        elif self._ime_wait_text > 0:
            self._ime_wait_text -= 1
            if self._ime_wait_text == 0 and not self.ime_composing:
                self.ime_composing = True  # 英字を押したのに文字が来ない → 変換中とみなす
                self.ime_state = "あ"

        # Ctrl+J：改行。変換中は何もしない（送信はしない）
        if ctrl and pyxel.btnp(pyxel.KEY_J) and not self.ime_composing:
            self.input_buf += "\n"

        # Enter：変換中なら日本語入力に任せる。そうでなければ少し待ってから送る（確定の文字が来たら取り消す）
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_KP_ENTER):
            if not self.ime_composing:
                self._pending_enter = IME_ENTER_WAIT + 1
        if self._pending_enter > 0 and not text:
            self._pending_enter -= 1
            if self._pending_enter == 0:
                self._send_input()

        # Backspace：変換中なら使わない（改行も1文字として消す）
        if pyxel.btnp(pyxel.KEY_BACKSPACE, hold=15, repeat=3) and not self.ime_composing:
            self.input_buf = self.input_buf[:-1]

        # Esc：変換中（または変換中かもしれないと待っている間）は変換の取り消しとみなす（中断の行は出さない）。
        # そうでなければ中断を送る
        if self.mode == MODE_PROMPT and pyxel.btnp(pyxel.KEY_ESCAPE):
            if self.ime_composing or self._ime_wait_text > 0:
                self.ime_composing = False
                self._ime_wait_text = 0
                self.ime_state = "あ"
            elif self._perm_block_send():
                pass  # 許可の答えを待っている間は、Esc（中断）も送らない
            elif self._usage_busy:
                pass  # 利用制限を読んでいる間は、Esc を送らない（/usage の画面が閉じてしまうため）
            else:
                # 本番では Claude Code に Esc（中断）を送る。試作では履歴に出すだけ。モードは変えない
                if self.claude and self.started and self.bridge is not None and self.mode == MODE_PROMPT:
                    self.bridge.send_escape()  # 本物の Claude Code の作業を中断する（PROMPT で、変換中でないとき）
                self._add_history(t("hist_esc_interrupt"))

    def _send_input(self) -> None:
        """入力中の文字を履歴に送る（試作。Claude Code には送らない）。1行目は "> "、2行目以降は "  " を付け、桁数で折り返す。

        改行と空白（半角・全角）だけのときは送らない。その場合は入力欄を空にする。
        """
        if self.input_buf.strip() == "":
            self.input_buf = ""
            return
        if self._perm_block_send():
            return  # 許可の答えを待っている間は送らない（入力欄の文字は残す）
        text = self.input_buf
        if self.claude and _is_blocked_command(text):
            # /exit・/quit は Claude Code に送らない（コマンドの窓も開かない）。送った文の行は出さず、案内だけ出す
            self.input_buf = ""
            self._add_history(t("hist_no_exit"))
            return
        self._add_block("> ", text)
        self.input_buf = ""
        if self.claude and self._is_menu_command(text) and self.started and not self._perm_block_send():
            self._open_menu(text.strip()[1:])  # 「/model」「/effort」だけの文は Claude Code に送らず、メニューを開く
            return
        if self.claude:
            # 「/」で始まる文は、送ったあとコマンドの窓に入る（モードは PROMPT のまま）。読んでいる間は取っておく
            self._send_to_claude(text, slash=self._is_slash_command(text))

    def _reset_ime(self) -> None:
        """日本語の変換中の推測と、送信待ちを全部 0／False に戻す。PROMPT から WALK に戻るときに使う。"""
        self.ime_composing = False
        self._ime_wait_text = 0
        self._pending_enter = 0

    # ---- --claude：本物の Claude Code とつなぐ（office だけ。--claude のときだけ動く） ----

    def _init_claude(
        self,
        claude: bool,
        workdir: str | None,
        session: str,
        bridge_factory: Callable[[str, str], Bridge] | None,
    ) -> None:
        """--claude のときの準備。見えない人を部屋の外に置き、つなぐ部品（Bridge）を作る。--claude なしでは既定値だけ入れる。"""
        self.claude: bool = claude and self.layout.has_props
        self.session: str = session
        self.workdir: str = workdir if workdir is not None else str(DEFAULT_PCA_WORKDIR)
        self.bridge: Bridge | None = None
        self.started: bool = False  # 始業しているか
        self.ending: bool = False  # 終業で引き継ぎメモを待っているか
        self._handoff_left: float = 0.0  # 終業の待ちの残り時間（秒）
        self._last_sent: str | None = None  # 直前に自分で送った文字（届いた Prompt と比べる）
        self._sub_map: dict[str, int] = {}  # サブエージェントの番号 → 席の番号
        self._leave_timers: dict[int, float] = {}  # 帰るまでの残り時間（秒）
        self._idle_main: float = 0.0  # メインが作業を止めている時間（秒）
        self._bubble: str = ""  # 吹き出しの文
        self._bubble_left: float = 0.0  # 吹き出しを出す残り時間（秒）
        self._dialog: bool = False  # 「前のセッションが残っています」を出しているか
        self._door_auto: bool = False  # 出入りのためにドアを開けたか（D キーで開けたら False）
        self._door_idle: float = 0.0  # 出入りが止まってからの時間（秒）
        self._last_line: dict[int, str] = {}  # 話しかけたときの様子に出す、最後の行
        self._leave_elapsed: dict[int, float] = {}  # 部屋を出ようとしている時間（秒）
        self._busy_text: dict[int, str] = {}  # 作業中の吹き出しの文（人の番号 → 1行目）
        self._pending_reply: str | None = None  # 作業中に届いた、いちばん新しい返事（作業が終わったら6秒出す）
        self._human_text: str | None = None  # 人間の吹き出しの文（送ったプロンプト）
        self._session_check_left: float = SESSION_CHECK_SEC  # 次にセッションを確かめるまでの時間（秒）
        self._handoff_seen: bool = False  # 引き継ぎメモの Prompt（自分で送った分）を、記録で見たか
        # 許可の依頼（hook から届く）。待ち受けは始業のとき始める。--claude なしでも既定値を入れておく
        self._perm_clock: Callable[[], float] = time.monotonic
        self._perm_server: PermServer | None = None
        self._perm_pending: list[PermRequest] = []  # 答えを待っている許可の依頼（先頭から答える）
        self._perm_key_guard_until: float = 0.0  # 自動でワープしたあと Y・N・T を受け付けない時刻（_perm_clock の値）
        self._perm_tmux: bool = False  # tmux で答える分がある（次の Tool・Reply・TurnEnd で戻す）
        self._perm_always_confirm: bool = False  # 「いつも許可」の確かめの途中か（A を1回押したあと、もう1回 A で答える）
        self._perm_always_req: PermRequest | None = None  # 確かめの途中の依頼（先頭がこの物のあいだだけ確かめを続ける）
        self._perm_lock: bool = False  # 送信を止めているか（依頼がある、または tmux で答える分がある）
        self._perm_wait_noted: bool = False  # 送信の止めの行を出したか（止めが外れたら戻す）
        self._last_reply: str | None = None  # 最新の Reply の全文（会話のダイアログに出す）
        self._last_prompt: str | None = None  # 最新のプロンプトの全文（Reply が無いとき出す）
        self._pages: list[TalkPage] = []  # メインとのやりとりのページ（プロンプトごとに1ページ。古いものから TALK_PAGE_MAX まで）
        self._page_index: int | None = None  # 見ているページの番号（None は最新を見ている）
        self._dlg_scroll: int = 0  # 会話のダイアログのスクロール（先頭の行の番号）
        self._dlg_drag: bool = False  # 会話のダイアログのつまみを押したまま動かしているか
        # コマンドの窓（SLASH）。「/」で始まる文を送ったあと、tmux の画面を映す（モードは PROMPT のまま）
        self._slash_open: bool = False
        self._slash_cmd: str = ""  # 送った文（前後の空白を除いたもの）
        self._slash_seen_panel: bool = False  # パネル（「Esc to」の案内）を見たか
        self._slash_started: float = 0.0  # 窓に入った時刻（_perm_clock の値）
        self._slash_lines: list[str] = []  # 画面の行（末尾の空白は消してある）
        self._slash_scroll: int = 0  # 一番上に出ている行（折り返し後）の番号
        self._slash_user_scrolled: bool = False  # ユーザーが動かしたか（一番下まで戻したらまた下に付く）
        self._slash_static: bool = False  # 結果だけの窓か（画面を読むのをやめた）
        self._slash_gone_since: float | None = None  # パネルの案内が見えなくなった時刻
        self._slash_next_read: float = 0.0  # 次に画面を読む時刻（_perm_clock の値）
        self._slash_drag: bool = False  # スクロールバーのつまみを押したまま動かしているか
        # 今のモデルと effort（画面の文字と /model・/effort の結果から覚える。分からなければ "?"）
        self._cur_model: str = "?"
        self._cur_effort: str = "?"
        self._state_left: float = 0.0  # 画面から今のモデルを読む残りの時間（秒）。0 なら読まない
        self._state_next: float = 0.0  # 次に画面を読むまでの時間（秒）
        # 選ぶメニュー（"model" か "effort"。None なら閉じている）と、選んでいる行の番号
        self._menu: str | None = None
        self._menu_sel: int = 0
        # 利用制限を /usage の画面から読む（--claude のとき）
        self._usage_busy: bool = False  # 読んでいる最中か
        self._usage_phase: str = ""  # "read"（値を探す）・"close"（閉じるのを待つ）・""（読んでいない）
        self._usage_elapsed: float = 0.0  # 読み始めてからの時間（秒）
        self._usage_poll_left: float = 0.0  # 次に画面を読むまでの時間（秒）
        self._usage_close_elapsed: float = 0.0  # 閉じるのを待っている時間（秒）
        self._usage_closes: int = 0  # 閉じるために Escape を送った回数
        self._usage_panel_seen: bool = False  # 最後に読んだ画面に「Esc to」があったか
        self._usage_note_shown: bool = False  # 今の読み取りで「読んでいます」の行を出したか
        self._usage_start_armed: bool = False  # 始業してモデルの読み取りが終わったら、1回だけ読む
        self._usage_after_turn_left: float = 0.0  # 返事の終わりから読むまでの残り時間（秒）。0 なら予定なし
        self._usage_pending: list[tuple[str, bool]] = []  # 読んでいる間に送ろうとした文（文, コマンドの窓を開くか）
        self._usage_reset_5h: str | None = None  # 5時間の「Resets」の行（表示には使わない）
        self._usage_reset_week: str | None = None  # 週間の「Resets」の行（表示には使わない）
        if not self.claude:
            return
        Path(self.workdir).mkdir(parents=True, exist_ok=True)
        make = bridge_factory if bridge_factory is not None else (
            lambda w, s: Bridge(w, s, claude_cmd=claude_command(HOOK_PATH, get_lang()))
        )
        self.bridge = make(self.workdir, self.session)
        self._perm_server = PermServer(clock=self._perm_clock)
        for agent in self.agents:
            agent.park()  # 始めは全員が見えず、部屋の外にいる（人間だけがいる）
        atexit.register(self._atexit_shutdown)

    def _active_indices(self) -> list[int]:
        """見えている人の番号。--claude のとき見えていない人は、動かさず・描かず・道や予約にも入れない。"""
        return [i for i, agent in enumerate(self.agents) if agent.visible]

    def _bridge_error(self) -> str:
        """つなぎの部品の最後の失敗の理由（無ければ空）。"""
        if self.bridge is None:
            return ""
        error = getattr(self.bridge, "last_error", "")
        if not error:
            error = getattr(getattr(self.bridge, "tmux", None), "last_error", "")
        return error or ""

    def _add_block(self, first: str, text: str, rest: str = "  ", color: int = TEXT_COLOR) -> None:
        """text を改行で分け、1行目に first、2行目以降に rest を付けて、桁数で折り返して履歴に足す（色は color）。"""
        rows: list[str] = []
        for index, line in enumerate(text.split("\n")):
            prefix = first if index == 0 else rest
            rows.extend(_wrap_text(prefix + line, UI_COLS, self.ui_codes))
        self._append_history_rows(rows, color)

    def _send_to_claude(self, text: str, slash: bool = False) -> bool:
        """入力の文字を Claude Code に送る。送れたら True。始業していなければ、その旨を履歴に出して False。メインが見えていなければ入ってくる。
        利用制限を読んでいる間は送らずに取っておき（False）、読み終わったあと順に送る。slash が True なら、送ったあとコマンドの窓に入る。
        """
        if not self.started or self.bridge is None:
            self._add_history(t("hist_not_started"))
            return False
        if self._perm_block_send():
            return False  # 許可の答えを待っている間は送らない
        if self._usage_busy:
            if not self._usage_note_shown:
                self._add_history(t("hist_usage_reading"))
                self._usage_note_shown = True
            self._usage_pending.append((text, slash))
            return False  # 読み終わったあと送る（送るときに、会話の記録と履歴の扱いが決まる）
        main = self.agents[MAIN_INDEX]
        if not main.visible:
            self._enter(MAIN_INDEX)
        self._idle_main = 0.0
        self._last_sent = text
        self._human_text = text
        sent = self.bridge.send_prompt(text)
        if sent and slash:
            self._open_slash(text)  # 「/」で始まる文は、送ったあとコマンドの窓に入る（モードは PROMPT のまま）
        return sent

    def _toggle_session(self) -> None:
        """始業・終業（ボタンと F1）。始業していなければ始業（前のセッションがあればダイアログ）、していれば終業。"""
        if self.ending or not self.claude or self.bridge is None:
            return
        if not self.started:
            if self.bridge.session_exists():
                self._dialog = True
                return
            self._start_session("new")
        else:
            self._begin_handoff()

    def _choose_dialog(self, mode: str) -> None:
        """ダイアログの選び方：resume・restart。空なら何もしない（やめる）。"""
        self._dialog = False
        if mode:
            self._start_session(mode)

    def _start_session(self, mode: str) -> None:
        """Bridge.begin で始業する。成功ならメイン（番号 0）を席へ、失敗なら履歴に理由を出す。"""
        if self.bridge is None:
            return
        if self.bridge.begin(mode):
            self.started = True
            self._start_perm()
            main = self.agents[MAIN_INDEX]
            main.role = "main"
            main.label = "main"
            self._session_check_left = SESSION_CHECK_SEC
            self._state_left = STATE_READ_SEC  # 今のモデルを画面から読み始める
            self._state_next = 0.0
            self._usage_start_armed = True  # モデルの読み取りが終わったら、利用制限を1回読む
            self._idle_main = 0.0
            self._enter(MAIN_INDEX)
            if mode == "resume":
                self._add_history(t("hist_start_resumed"))
            else:
                self._add_history(t("hist_start_new"))
        else:
            self._add_history(t("hist_start_failed", error=self._bridge_error()))

    def _begin_handoff(self, sleep: Callable[[float], None] = time.sleep) -> None:
        """終業の前に、引き継ぎメモを書いてもらう。TurnEnd が来るか、待ち時間を過ぎたら閉じる。"""
        self._close_slash()  # コマンドの窓は、何も送らずに閉じる
        self._close_menu()  # 選ぶメニューも、何も送らずに閉じる
        if self.bridge is None:
            return
        self._usage_abort(send_escape=True)  # 読んでいたら Escape を1回送って読みをやめる（引き継ぎを送る前）
        self._usage_drop_pending()
        self._add_history(t("hist_ending"))
        self._release_perm(sleep)  # 残った許可の依頼は deny。tmux の許可画面は Esc で取り消す（待ちの止めも外す）
        if not self.bridge.session_exists():
            self._finish_ending()  # セッションが無ければ、頼まずにそのまま終える
            return
        self._handoff_seen = False
        if not self.bridge.send_prompt(t(HANDOFF_PROMPT)):
            self._finish_ending()  # 送れなければ、待たずに終える
            return
        self._last_sent = t(HANDOFF_PROMPT)
        self._human_text = t(HANDOFF_PROMPT)
        self.ending = True
        self._handoff_left = HANDOFF_WAIT_SEC

    def _finish_ending(self) -> None:
        """終業を終える：見えている全員を部屋から出し、見張りと tmux のセッションを閉じる。"""
        for i in self._active_indices():
            self._leave(i)
        if self.bridge is not None:
            self.bridge.end(kill_session=True)
        self._stop_perm()
        self.started = False
        self.ending = False
        self._forget_state()  # 今のモデルと effort を "?" に戻す（メニューも閉じる）
        self._sub_map.clear()
        self._leave_timers.clear()
        self._last_line.clear()
        self._busy_text.clear()
        self._pending_reply = None
        self._human_text = None
        self._add_history(t("hist_ended"))

    def _session_gone(self) -> None:
        """Claude Code のセッションが無くなった（/exit など）。見えている全員を部屋から出し、見張りを止める。終業中なら終業も終える（tmux は閉じない）。"""
        was_ending = self.ending
        self._usage_abort(send_escape=True)  # 読んでいたら Escape を1回送って読みをやめる
        self._usage_drop_pending()
        self._close_slash()  # コマンドの窓は、何も送らずに閉じる
        self._forget_state()  # 今のモデルと effort を "?" に戻す（メニューも閉じる）
        self._add_history(t("hist_claude_exited"))
        for i in self._active_indices():
            self._leave(i)
        if self.bridge is not None:
            self.bridge.end(kill_session=False)
        self._stop_perm()  # セッションが無いので、許可の依頼は deny にして待ち受けも止める
        self.started = False
        self.ending = False
        self._sub_map.clear()
        self._leave_timers.clear()
        self._last_line.clear()
        self._busy_text.clear()
        self._pending_reply = None
        self._human_text = None
        if was_ending:
            self._add_history(t("hist_ended"))

    def _shutdown_claude(self, sleep: Callable[[float], None] = time.sleep) -> None:
        """窓を閉じるときの後始末。始業していて終業していなければ、引き継ぎメモを待ってから tmux を閉じる（最大 HANDOFF_WAIT_SEC 秒）。

        許可の依頼は、ここで deny にして待ち受けを止める（止めないと、待つ間に依頼が答えられず hook が時間切れまで待つため）。
        """
        self._close_slash()  # 窓の×。コマンドの窓は、何も送らずに閉じる
        self._close_menu()  # 窓の×。選ぶメニューも、何も送らずに閉じる
        if self.claude:
            self._usage_abort(send_escape=True)  # 読んでいたら Escape を1回送って読みをやめる
            self._usage_drop_pending()
        if self.claude and self.bridge is not None and self.started:
            self._release_perm(sleep)  # 残った依頼は deny。tmux の許可画面は Esc で取り消す
        self._stop_perm()
        if not self.claude or self.bridge is None or not self.started:
            return
        if not self.bridge.session_exists():
            self.bridge.end(kill_session=False)  # セッションが無ければ、待たずに閉じる
            self.started = False
            self.ending = False
            return
        if not self.ending:
            self._handoff_seen = False
            if not self.bridge.send_prompt(t(HANDOFF_PROMPT)):
                self.bridge.end(kill_session=False)  # 送れなければ、待たずに閉じる
                self.started = False
                self.ending = False
                return
            self._last_sent = t(HANDOFF_PROMPT)
        print(t("log_handoff_wait", sec=int(HANDOFF_WAIT_SEC)), flush=True)
        waited = 0.0
        done = False
        while waited < HANDOFF_WAIT_SEC and not done:
            for event in self.bridge.poll():
                if isinstance(event, Prompt) and event.text == t(HANDOFF_PROMPT):
                    self._handoff_seen = True  # 引き継ぎメモの依頼が記録に出た
                elif isinstance(event, TurnEnd) and self._handoff_seen:
                    done = True  # 依頼のあとの返事の終わり
            if done:
                break
            sleep(0.2)
            waited += 0.2
        if done:
            print(t("log_handoff_received"), flush=True)
        else:
            print(t("log_handoff_timeout"), flush=True)
        self.bridge.end(kill_session=True)
        self.started = False
        self.ending = False

    def _atexit_shutdown(self) -> None:
        """プロセスの終わりに呼ぶ後始末（atexit に登録する）。"""
        self._shutdown_claude()

    def _begin_work(self, i: int) -> None:
        """人 i を作業状態にする。行き先へ向かう途中・行き先・戻り中なら、予約を外してタイマーを0にしてから作業に入る。"""
        if self.spot_manager is not None and self.agents[i].state in (GOING, AT_SPOT, RETURNING):
            self.spot_manager.release(i)  # 行き先の予約を外す（外さないと次の予約が二重予約で止まる）
            self.agents[i].reset_outing_timers()
        self.agents[i].start_work()

    def _enter(self, i: int) -> None:
        """人 i を部屋に入れる：ドアを開け、ドアの内側に置いて、席へ向かわせる（見えるようにする）。"""
        agent = self.agents[i]
        self.door_open = True
        self._door_auto = True
        self._door_idle = 0.0
        agent.pos = Vec3(ENTER_INSIDE_X, 0.0, DOOR_Z)
        agent.visible = True
        self._begin_work(i)

    def _leave(self, i: int) -> None:
        """人 i を部屋から出す：ドアを開け、ドアの内側まで歩かせる（着いたら _finish_leaving で置き場所へ）。会話の相手なら会話を終える。"""
        agent = self.agents[i]
        if not agent.visible:
            return
        if self.talk_partner == i:
            self.end_talk()
        self.door_open = True
        self._door_auto = True
        self._door_idle = 0.0
        if self.spot_manager is not None:
            self.spot_manager.release(i)
        self._chat[i] = Chatter()
        if i in self._nav_queue:
            self._nav_queue.remove(i)
        self._leave_timers.pop(i, None)
        goal = Vec3(ENTER_INSIDE_X, 0.0, DOOR_Z)
        if not agent.begin_leaving(goal):
            self._park_agent(i)  # 道が無ければ、歩かずにそのまま置き場所へ

    def _finish_leaving(self, dt: float = 0.0) -> None:
        """部屋を出る人を、見えない置き場所へ戻す。着いた人（leaving_done）と、LEAVE_MAX_SEC 続いた人が対象。"""
        for i in self._active_indices():
            agent = self.agents[i]
            if agent.state != LEAVING:
                self._leave_elapsed.pop(i, None)
                continue
            elapsed = self._leave_elapsed.get(i, 0.0) + dt
            self._leave_elapsed[i] = elapsed
            if agent.leaving_done or elapsed >= LEAVE_MAX_SEC:
                self._leave_elapsed.pop(i, None)
                self._park_agent(i)

    def _park_agent(self, i: int) -> None:
        """人 i を見えない置き場所へ戻し、この人への対応（サブエージェント・帰る時間・最後の行）を消す。"""
        self.agents[i].park()
        for agent_id, slot in list(self._sub_map.items()):
            if slot == i:
                del self._sub_map[agent_id]
        self._leave_timers.pop(i, None)
        self._last_line.pop(i, None)
        self._busy_text.pop(i, None)

    def _update_door_auto(self, dt: float) -> None:
        """出入りが止まってから DOOR_IDLE_CLOSE_SEC 秒たったら、出入りのために開けたドアを閉める。"""
        moving = any(
            a.visible and ((a.state == WORKING and not a.is_seated) or a.state == LEAVING)
            for a in self.agents
        )
        if moving:
            self._door_idle = 0.0
            return
        if not self._door_auto:
            return
        self._door_idle += dt
        if self._door_idle >= DOOR_IDLE_CLOSE_SEC:
            self.door_open = False
            self._door_auto = False

    # ---- 利用制限の読み取り（--claude のとき。/usage の画面から使った割合を読む） ----

    def _usage_can_read(self) -> bool:
        """今、/usage を送って読んでよいか（始業していて終業中でなく、読んでいず、許可の依頼も無く、コマンドの窓もメニューも開いておらず、メインが作業していない）。"""
        if not (self.claude and self.started and not self.ending and self.bridge is not None):
            return False
        if self._usage_busy or self._perm_pending or self._perm_tmux or self._slash_open or self._menu is not None:
            return False
        if self.agents[MAIN_INDEX].busy:
            return False
        return not self._tmux_shows_permission()

    def _usage_try_start(self) -> None:
        """読めるなら /usage を送って読み始める。読めなければ何もしない（その予定は、そこで終わる）。"""
        if not self._usage_can_read():
            return
        self._usage_busy = True
        self._usage_phase = "read"
        self._usage_elapsed = 0.0
        self._usage_poll_left = USAGE_POLL_SEC
        self._usage_close_elapsed = 0.0
        self._usage_closes = 0
        self._usage_panel_seen = False
        self._usage_note_shown = False
        if not self.bridge.send_prompt(USAGE_COMMAND):
            self._usage_finish()
            print(t("log_usage_send_failed"), flush=True)

    def _usage_panel_open(self) -> bool:
        """/usage の画面が出ていて、Escape で閉じる必要があるか。読んでいる間は True。閉じるのを待つ間は、最後に見た画面に案内が残っているときだけ。"""
        if self._usage_phase == "read":
            return True
        return self._usage_phase == "close" and self._usage_panel_seen

    def _usage_finish(self) -> None:
        """読み取りを終える（値は前のままか、読んだ値）。取っておいた文は残す。"""
        self._usage_busy = False
        self._usage_phase = ""
        self._usage_panel_seen = False

    def _usage_abort(self, send_escape: bool) -> None:
        """読んでいる最中なら読みをやめる。send_escape が True で画面が出ていそうなら、Escape を1回送る。取っておいた文は残す。"""
        if not self._usage_busy:
            return
        if send_escape and self._usage_panel_open() and self.bridge is not None:
            self.bridge.send_escape()
        self._usage_finish()

    def _usage_drop_pending(self) -> None:
        """取っておいた文を捨てる（終業・×・セッション消失のとき）。1つでもあれば、その旨を履歴に出す。"""
        if self._usage_pending:
            self._usage_pending.clear()
            self._add_history(t("hist_unsent_prompts"))

    def _usage_flush(self) -> None:
        """取っておいた文を、読み終わったあと1フレームに1つずつ送る。許可の答えを待つ間・コマンドの窓の間・読んでいる間は送らない。"""
        if self._usage_busy or not self._usage_pending or not self.started or self._slash_open:
            return
        self._sync_perm_lock()
        if self._perm_lock or self._tmux_shows_permission():
            return
        text, slash = self._usage_pending.pop(0)
        self._send_to_claude(text, slash=slash)

    def _update_usage(self, dt: float) -> None:
        """利用制限の読み取りの1フレーム：予定（始業・返事の終わりから1秒）を確かめ、許可の依頼で読みをやめ、読んでいれば進め、取っておいた文を送る。"""
        if self._usage_start_armed and self._state_left <= 0.0:
            self._usage_start_armed = False
            self._usage_try_start()
        if self._usage_after_turn_left > 0.0:
            self._usage_after_turn_left -= dt
            if self._usage_after_turn_left <= 0.0:
                self._usage_after_turn_left = 0.0
                self._usage_try_start()
        if self._usage_busy and (self._perm_pending or self._perm_tmux):
            self._usage_abort(send_escape=True)  # 許可の依頼が来た：Escape を1回送って読みをやめる（取っておいた文は残す）
        if self._usage_busy:
            self._usage_step(dt)
        self._usage_flush()

    def _usage_step(self, dt: float) -> None:
        """読み取りを1フレーム進める。値を探す（read）→ 値が取れたら Escape を送って閉じるのを待つ（close）。"""
        self._usage_elapsed += dt
        self._usage_poll_left -= dt
        if self._usage_phase == "read":
            if self._usage_poll_left <= 0.0:
                self._usage_poll_left = USAGE_POLL_SEC
                text = self._slash_capture()
                lines = [] if text is None else [line.rstrip() for line in text.splitlines()]
                # 英語の画面が前提（上の USAGE_PCT_RE の説明を参照）
                self._usage_panel_seen = any("Esc to" in line for line in lines)
                five, week, reset_5h, reset_week = _parse_usage(lines)
                if five is not None and week is not None:
                    self.five_hour = _clamp(five, 0.0, 100.0)
                    self.seven_day = _clamp(week, 0.0, 100.0)
                    self._usage_reset_5h = reset_5h
                    self._usage_reset_week = reset_week
                    self._sync_scene_values()  # 掲示板（描画が読む値）へ渡す
                    if self.bridge is not None:
                        self.bridge.send_escape()  # 画面を閉じる
                    self._usage_phase = "close"
                    self._usage_close_elapsed = 0.0
                    return
            if self._usage_elapsed >= USAGE_TIMEOUT_SEC:
                if self._usage_panel_seen and self.bridge is not None:
                    self.bridge.send_escape()  # 画面が残っていれば閉じる
                print(t("log_usage_timeout", sec=f"{USAGE_TIMEOUT_SEC:g}"), flush=True)
                self._usage_finish()
            return
        # close：「Esc to」の案内が消えたら終わり。USAGE_CLOSE_SEC 残れば Escape をもう一度送り、それでも残ればあきらめる
        self._usage_close_elapsed += dt
        if self._usage_poll_left <= 0.0:
            self._usage_poll_left = USAGE_POLL_SEC
            text = self._slash_capture()
            if text is not None:
                # 英語の画面が前提（上の USAGE_PCT_RE の説明を参照）
                self._usage_panel_seen = any("Esc to" in line for line in text.splitlines())
                if not self._usage_panel_seen:
                    self._usage_finish()
                    return
        if self._usage_close_elapsed >= USAGE_CLOSE_SEC:
            if self._usage_closes == 0:
                self._usage_closes = 1
                self._usage_close_elapsed = 0.0
                if self.bridge is not None:
                    self.bridge.send_escape()
            else:
                print(t("log_usage_not_closed"), flush=True)
                self._usage_finish()

    # ---- 許可の依頼（hook から届く。--claude のときだけ動く） ----

    def _start_perm(self) -> None:
        """始業のとき待ち受けを始める。使えなければ履歴に目立つ1行を出す（許可は tmux に出る）。"""
        if self._perm_server is None:
            return
        if not self._perm_server.start():
            self._add_history(t("hist_perm_unavailable"))

    def _stop_perm(self) -> None:
        """待ち受けを止める。残った依頼はすべて deny（tmux には回さない）。"""
        if self._perm_server is None:
            return
        self._deny_perm_all()
        self._perm_server.stop()
        self._perm_tmux = False
        self._sync_perm_lock()

    def _deny_perm_all(self) -> None:
        """今の依頼（待ちの列と queue の残り）に、すべて deny を返す。_perm_tmux は変えない。"""
        if self._perm_server is None:
            return
        for req in self._perm_pending:
            self._perm_server.answer(req.conn, "deny")
        self._perm_pending.clear()
        self._perm_server.deny_all()
        self._sync_perm_lock()

    def _release_perm(self, sleep: Callable[[float], None]) -> None:
        """終わるときの後始末：依頼は deny。tmux で答える分があれば Esc を1回送って1秒待つ（許可画面を取り消す）。最後に送信の止めを外す。"""
        self._deny_perm_all()
        if self._perm_tmux and self.bridge is not None:
            self.bridge.send_escape()
            sleep(1.0)
        self._perm_tmux = False
        self._sync_perm_lock()

    def _sync_perm_lock(self) -> None:
        """送信を止めるかを決める（依頼が1件でもある、または tmux で答える分がある）。止めが外れたら、待ちの行の印も戻す。"""
        self._perm_lock = bool(self._perm_pending) or self._perm_tmux
        if not self._perm_lock:
            self._perm_wait_noted = False

    def _clear_perm_tmux(self) -> None:
        """Tool・Reply・TurnEnd の届いたとき、tmux で答える分の印を戻す（依頼が残っていれば戻さない）。"""
        if not self._perm_pending:
            self._perm_tmux = False
        self._sync_perm_lock()

    def _tmux_shows_permission(self) -> bool:
        """tmux の画面に許可の画面が出ているか（送る直前の2つ目の守り）。--claude 以外・偽の Bridge（メソッドが無い）は False。"""
        if not self.claude or not self.started or self.bridge is None:
            return False
        check = getattr(self.bridge, "permission_screen_open", None)
        if check is None:
            return False
        try:
            return bool(check())
        except Exception:
            return False

    def _perm_block_send(self) -> bool:
        """送信を止めているか。止めているなら、待ちの行を同じ文を続けて出さないように1度だけ出し、True を返す。

        止めていなくても、tmux の画面に許可の画面が出ていれば止める（_perm_tmux を立てる）。
        """
        self._sync_perm_lock()
        if not self._perm_lock and self._tmux_shows_permission():
            self._perm_tmux = True
            self._sync_perm_lock()
        if not self._perm_lock:
            return False
        if not self._perm_wait_noted:
            self._add_history(t(PERM_WAIT_NOTE))
            self._perm_wait_noted = True
        return True

    def _perm_cwd_ok(self, cwd: object) -> bool:
        """依頼の cwd が作業フォルダの中か。無い・壊れているときは False（tmux に回す）。"""
        if not isinstance(cwd, str) or not cwd:
            return False
        try:
            return Path(cwd).resolve().is_relative_to(Path(self.workdir).resolve())
        except (OSError, ValueError, RuntimeError):
            return False

    def _perm_summary(self, req: PermRequest) -> str:
        """履歴に出す依頼の要約（道具名と入力の要約）。"""
        return f"{req.tool_name} {_tool_summary(req.tool_input)}".strip()

    def _update_perm_requests(self) -> None:
        """毎フレーム：queue から依頼を取り出し、時間切れ・取り下げ（相手が閉じた）を確かめる。"""
        server = self._perm_server
        if server is None:
            return
        was_empty = not self._perm_pending  # このフレームの最初に依頼が無かったか（新しく来たかの判定）
        while True:
            try:
                received, data, conn = server.queue.get_nowait()
            except queue.Empty:
                break
            if conn is None:  # 通知。許可の画面が出た（permission_prompt）なら tmux で答える扱いにする
                if data.get("notification_type") == "permission_prompt":
                    self._perm_tmux = True
                continue
            if not self._perm_cwd_ok(data.get("cwd")):
                server.answer(conn, "tmux")  # 作業フォルダの外の依頼は、ツールでは扱わない
                self._perm_tmux = True
                continue
            name = data.get("tool_name")
            self._perm_pending.append(
                PermRequest(
                    tool_name=name if isinstance(name, str) else "?",
                    tool_input=data.get("tool_input"),
                    received=received,
                    conn=conn,
                    suggestions=_perm_suggestions(data.get("permission_suggestions")),
                )
            )
            self._dlg_scroll = 0
        now = self._perm_clock()
        kept: list[PermRequest] = []
        for req in self._perm_pending:
            if now - req.received >= PERM_WAIT_SEC:
                server.answer(req.conn, "tmux")  # hook の時間切れより前に外す（hook は何も出さない）
                self._perm_tmux = True
                self._add_history(t("hist_perm_timeout", summary=self._perm_summary(req)))
            else:
                kept.append(req)
        self._perm_pending = kept
        still: list[PermRequest] = []
        for req in self._perm_pending:
            if server.is_closed(req.conn):
                self._perm_tmux = True
                self._add_history(t("hist_perm_withdrawn", summary=self._perm_summary(req)))
            else:
                still.append(req)
        self._perm_pending = still
        if was_empty and self._perm_pending:
            self._close_slash()  # 許可の依頼が来たら、コマンドの窓は何も送らずに閉じる
        # 新しく依頼が来たら（時間切れ・取り下げで外れた分は数えない）、人間がメインと会話していなければメインのところへ行く
        if was_empty and self._perm_pending and self.human is not None and self.talk_partner != MAIN_INDEX:
            if self.agents[MAIN_INDEX].visible:
                if self.talk_partner is not None:
                    self.end_talk()
                self.start_talk(MAIN_INDEX)
                if self.talk_partner == MAIN_INDEX:  # 立つ場所が見つかって会話が始まったときだけ
                    self._perm_key_guard_until = self._perm_clock() + PERM_KEY_GUARD_SEC
                    self._add_history(t("hist_perm_went_to_main"))
                else:
                    self._add_history(t("hist_perm_click_main"))
        # 新しく依頼が来て入力欄で打っていたら、WALK に切り替える（入力中の文字は消さない）。
        # ワープの守り時間より後に決めるので、ここで入れた PERM_KEY_GUARD_PROMPT_SEC が残る
        if was_empty and self._perm_pending and self.mode == MODE_PROMPT:
            self.mode = MODE_WALK
            self._reset_ime()
            self._perm_key_guard_until = self._perm_clock() + PERM_KEY_GUARD_PROMPT_SEC
            self._add_history(t("hist_perm_to_walk"))
        self._sync_perm_lock()

    def _perm_always_done(self) -> bool:
        """「いつも許可」の確かめを続けてよいか。先頭の依頼が確かめの依頼のままで、WALK でメインと話していて、ダイアログが無いとき True。"""
        return (
            bool(self._perm_pending)
            and self._perm_pending[0] is self._perm_always_req
            and self.mode == MODE_WALK
            and self.talk_partner == MAIN_INDEX
            and not self._dialog
        )

    def _update_perm_keys(self) -> None:
        """Y・N・T で、先頭の許可の依頼に答える。A は「いつも許可」（案がある依頼だけ。確かめの1回を経てから答える）。WALK で、メインと会話しているときだけ効く。"""
        if self._perm_always_confirm and not self._perm_always_done():
            self._perm_always_confirm = False  # 依頼が変わった・会話が終わった・ダイアログが出た：確かめをやめる
            self._perm_always_req = None
        server = self._perm_server
        if server is None or not self._perm_pending or self._dialog or self._perm_clock() < self._perm_key_guard_until:
            return
        if self.mode != MODE_WALK or self.talk_partner != MAIN_INDEX:
            return
        if self._perm_always_confirm:
            if pyxel.btnp(pyxel.KEY_A):
                self._answer_always(server)
            elif any(pyxel.btnp(button) for button in PERM_CANCEL_BUTTONS):
                self._perm_always_confirm = False  # A 以外のキー・クリックは確かめをやめるだけ（そのキーでは答えない）
                self._perm_always_req = None
            return
        if pyxel.btnp(pyxel.KEY_A):
            if self._perm_pending[0].suggestions:
                self._perm_always_confirm = True
                self._perm_always_req = self._perm_pending[0]
                self._dlg_scroll = 0
            return
        if pyxel.btnp(pyxel.KEY_Y):
            choice = "allow"
        elif pyxel.btnp(pyxel.KEY_N):
            choice = "deny"
        elif pyxel.btnp(pyxel.KEY_T):
            choice = "tmux"
        else:
            return
        req = self._perm_pending.pop(0)
        self._dlg_scroll = 0
        summary = self._perm_summary(req)
        if choice == "tmux":
            server.answer(req.conn, "tmux")
            self._perm_tmux = True
            self._add_history(t("hist_answer_in_tmux", summary=summary))
        elif server.answer(req.conn, choice):
            self._add_history(t("hist_allowed", summary=summary) if choice == "allow" else t("hist_denied", summary=summary))
        else:
            self._perm_tmux = True
            self._add_history(t("hist_answer_not_delivered", summary=summary))
        self._sync_perm_lock()

    def _answer_always(self, server: PermServer) -> None:
        """「いつも許可」の2回目の A：先頭の依頼に always を返す。履歴に要約と案の行（灰色）を出す。届かなければ tmux に回す。"""
        req = self._perm_pending.pop(0)
        self._perm_always_confirm = False
        self._perm_always_req = None
        self._dlg_scroll = 0
        summary = self._perm_summary(req)
        if server.answer(req.conn, "always"):
            self._add_history(t("hist_always_allowed", summary=summary))
            for row in _suggestion_rows(req.suggestions):
                self._append_history_rows(_wrap_text("  " + row, UI_COLS, self.ui_codes), PERM_SUGGEST_COLOR)
        else:
            self._perm_tmux = True
            self._add_history(t("hist_answer_not_delivered", summary=summary))
        self._sync_perm_lock()

    # ---- コマンドの窓（SLASH。--claude のとき、「/」で始まる文を送ったあとに出す） ----

    def _is_slash_command(self, text: str) -> bool:
        """送る文が、コマンドの窓を出すものか（前後の空白を除いて / で始まり、/exit・/quit ではない）。"""
        cmd = text.strip()
        return cmd.startswith("/") and cmd not in SLASH_EXIT_CMDS

    def _open_slash(self, text: str) -> None:
        """コマンドの窓に入る。送った文を覚え、すぐ画面を読む状態にする。モードは PROMPT のまま。"""
        now = self._perm_clock()
        self._slash_open = True
        self._slash_cmd = text.strip()
        self._slash_seen_panel = False
        self._slash_started = now
        self._slash_lines = []
        self._slash_scroll = 0
        self._slash_user_scrolled = False
        self._slash_static = False
        self._slash_gone_since = None
        self._slash_next_read = now
        self._slash_drag = False

    def _close_slash(self) -> None:
        """コマンドの窓を閉じる。何も送らない。モードは PROMPT のまま（入力欄は送ったときに空になっている）。"""
        self._slash_open = False
        self._slash_lines = []
        self._slash_static = False
        self._slash_seen_panel = False
        self._slash_gone_since = None
        self._slash_drag = False

    def _update_slash(self) -> None:
        """コマンドの窓の1フレーム。パネルのときはキーを tmux へ送り、画面を読んで閉じるかを決める。結果だけの窓は Esc・Enter で閉じる。"""
        now = self._perm_clock()
        if self._slash_static:
            if pyxel.btnp(pyxel.KEY_ESCAPE) or pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_KP_ENTER):
                self._close_slash()
                return
        else:
            if self._send_slash_keys():
                self._slash_next_read = now  # 送ったら、返事を早く映すため待たずに読む
            if now >= self._slash_next_read:
                self._read_slash(now)
        self._update_slash_drag()

    def _send_slash_keys(self) -> bool:
        """今のフレームに押されたキーと入力の文字を、tmux へ送る。何か送ったら True。"""
        if self.bridge is None:
            return False
        sent = False
        for key, name, repeat in SLASH_KEYS:
            pressed = pyxel.btnp(key, hold=15, repeat=3) if repeat else pyxel.btnp(key)
            if pressed:
                self.bridge.send_keys(name)
                sent = True
        # 英数字と記号だけを送る（空白はキーの Space で送るので除く。日本語は送らない）
        typed = "".join(ch for ch in pyxel.input_text if "!" <= ch <= "~")
        if typed:
            self.bridge.send_literal(typed)
            sent = True
        return sent

    def _slash_capture(self) -> str | None:
        """tmux の画面の文字。Bridge に tmux が無い・読めないときは None。"""
        tmux = getattr(self.bridge, "tmux", None) if self.bridge is not None else None
        capture = getattr(tmux, "capture", None)
        if capture is None:
            return None
        return capture()

    def _read_slash(self, now: float) -> None:
        """画面を1回読む。「Esc to」の案内を見たらパネルが出ているとみなし、案内が SLASH_CLOSE_SEC 消えたら閉じる。
        一度も見ないまま SLASH_STATIC_SEC たったら、結果だけの窓に切り替えて以後は読まない。"""
        self._slash_next_read = now + SLASH_POLL_SEC
        text = self._slash_capture()
        if text is None:
            # 画面を読めない。パネルを見たあとなら、案内が消えたのと同じ扱いで読めない状態が続いたら閉じる
            if self._slash_seen_panel:
                if self._slash_gone_since is None:
                    self._slash_gone_since = now
                elif now - self._slash_gone_since >= SLASH_CLOSE_SEC:
                    self._close_slash()
            elif now - self._slash_started >= SLASH_STATIC_SEC:
                self._slash_static = True  # パネルを一度も見ないまま時間がたった：1行だけの結果の窓にする
                self._set_slash_lines([t("slash_read_failed")])
            return
        lines = [line.rstrip() for line in text.splitlines()]
        # 英語の画面が前提（上の USAGE_PCT_RE の説明を参照）
        if any("Esc to" in line for line in lines):
            self._slash_seen_panel = True
            self._slash_gone_since = None
        elif self._slash_seen_panel:
            if self._slash_gone_since is None:
                self._slash_gone_since = now
            elif now - self._slash_gone_since >= SLASH_CLOSE_SEC:
                self._close_slash()  # パネルを見たあと案内が消えた：窓を閉じる
                return
        if not self._slash_seen_panel and now - self._slash_started >= SLASH_STATIC_SEC:
            self._slash_static = True  # パネルを見ないまま時間がたった：結果だけの窓にする
            lines = _slash_result_lines(lines, self._slash_cmd)
        self._set_slash_lines(lines)

    def _set_slash_lines(self, lines: list[str]) -> None:
        """画面の行を入れ替える。ユーザーが動かしていなければ一番下へ、動かしていれば位置を保つ（範囲内に収める）。"""
        self._slash_lines = lines
        if not self._slash_user_scrolled:
            self._slash_scroll = self._slash_max_scroll()
        else:
            self._slash_scroll = int(_clamp(self._slash_scroll, 0, self._slash_max_scroll()))

    def _slash_rows(self) -> list[str]:
        """画面の行を、窓の中の桁数で折り返した表示用の行。"""
        rows: list[str] = []
        for line in self._slash_lines:
            rows.extend(_wrap_text(line, SLASH_COLS, self.ui_codes))
        return rows

    def _slash_max_scroll(self) -> int:
        """窓の中身の先頭の行の番号の上限（最後の行まで見える位置）。"""
        return max(0, len(self._slash_rows()) - SLASH_BODY_ROWS)

    def _set_slash_scroll(self, value: int) -> None:
        """窓の中身の先頭の行を value にする（範囲内に収める）。一番下まで戻したら、また下に付いていく。"""
        max_scroll = self._slash_max_scroll()
        self._slash_scroll = int(_clamp(value, 0, max_scroll))
        self._slash_user_scrolled = self._slash_scroll < max_scroll

    def _scroll_slash(self, delta: int) -> None:
        """窓の中身を delta 行動かす。"""
        self._set_slash_scroll(self._slash_scroll + delta)

    def _slash_track(self) -> tuple[int, int, int, int]:
        """窓のスクロールバーの溝 (x, y, 幅, 高さ)。右の端の内側、画面の行の範囲。"""
        return (
            SLASH_X + SLASH_W - 2 - SCROLLBAR_W,
            SLASH_Y + UI_PAD + UI_LINE_H,
            SCROLLBAR_W,
            SLASH_BODY_ROWS * UI_LINE_H,
        )

    def _slash_thumb(self, total: int) -> tuple[int, int]:
        """スクロールバーのつまみの (y, 高さ)。total は全部の行数（SLASH_BODY_ROWS より多いときだけ使う）。"""
        _, ty, _, th = self._slash_track()
        thumb_h = max(6, int(th * SLASH_BODY_ROWS / total))
        max_scroll = total - SLASH_BODY_ROWS
        thumb_y = ty + int((th - thumb_h) * self._slash_scroll / max_scroll)
        return (thumb_y, thumb_h)

    def _slash_click(self, sx: int, sy: int) -> None:
        """窓の上のクリック。溝を押したら1画面ぶん動かし、つまみを押したら動かし始める。
        窓の外のクリックは、結果だけの窓のときだけ閉じる（パネルのときは何もしない）。"""
        if not self._in_rect(sx, sy, SLASH_X, SLASH_Y, SLASH_W, SLASH_H):
            if self._slash_static:
                self._close_slash()
            return
        total = len(self._slash_rows())
        tx, ty, tw, th = self._slash_track()
        if total <= SLASH_BODY_ROWS or not self._in_rect(sx, sy, tx, ty, tw, th):
            return
        thumb_y, thumb_h = self._slash_thumb(total)
        if thumb_y <= sy < thumb_y + thumb_h:
            self._slash_drag = True
        elif sy < thumb_y:
            self._scroll_slash(-SLASH_BODY_ROWS)
        else:
            self._scroll_slash(SLASH_BODY_ROWS)

    def _update_slash_drag(self) -> None:
        """つまみを押したまま動かしているとき、つまみの位置から窓の中身の先頭の行を決める。"""
        if not self._slash_drag:
            return
        if not pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
            self._slash_drag = False
            return
        total = len(self._slash_rows())
        if total <= SLASH_BODY_ROWS:
            return
        _, ty, _, th = self._slash_track()
        thumb_h = self._slash_thumb(total)[1]
        span = th - thumb_h
        frac = _clamp((pyxel.mouse_y - ty - thumb_h / 2.0) / span, 0.0, 1.0) if span > 0 else 0.0
        self._set_slash_scroll(round(frac * (total - SLASH_BODY_ROWS)))

    def _slash_wheel(self, wheel: int) -> None:
        """ホイールを窓の上で回したら、窓の中身を動かす（3D はズームしない）。"""
        if self._in_rect(pyxel.mouse_x, pyxel.mouse_y, SLASH_X, SLASH_Y, SLASH_W, SLASH_H):
            self._scroll_slash(-DLG_WHEEL_ROWS * wheel)

    def _draw_slash(self) -> None:
        """コマンドの窓を描く。背景は少し透かし、枠、1行目に「コマンド：」の文、画面の行、スクロールバー、一番下に案内。"""
        font = self.ui_font
        pyxel.dither(SLASH_DITHER)  # 背景の黒だけ半透明にする
        pyxel.rect(SLASH_X, SLASH_Y, SLASH_W, SLASH_H, 0)
        pyxel.dither(1.0)  # 戻す（枠・文字・スクロールバーは通常の濃さ）
        pyxel.rectb(SLASH_X, SLASH_Y, SLASH_W, SLASH_H, TEXT_COLOR)
        if font is None:
            return
        head = _wrap_text(t("slash_command_label") + _first_line(self._slash_cmd), SLASH_COLS, self.ui_codes)[0]
        pyxel.text(SLASH_X + UI_PAD, SLASH_Y + UI_PAD, self._ui(head), 10, font)
        rows = self._slash_rows()
        self._slash_scroll = int(_clamp(self._slash_scroll, 0, self._slash_max_scroll()))
        for row_no, row in enumerate(rows[self._slash_scroll : self._slash_scroll + SLASH_BODY_ROWS]):
            pyxel.text(
                SLASH_X + UI_PAD, SLASH_Y + UI_PAD + (row_no + 1) * UI_LINE_H, self._ui(row), TEXT_COLOR, font
            )
        if len(rows) > SLASH_BODY_ROWS:
            tx, ty, tw, th = self._slash_track()
            pyxel.rect(tx, ty, tw, th, 1)  # 溝
            thumb_y, thumb_h = self._slash_thumb(len(rows))
            pyxel.rect(tx, thumb_y, tw, thumb_h, TEXT_COLOR)
        guide = t(SLASH_GUIDE_STATIC) if self._slash_static else t(SLASH_GUIDE_PANEL)
        pyxel.text(
            SLASH_X + UI_PAD, SLASH_Y + UI_PAD + (SLASH_BODY_ROWS + 1) * UI_LINE_H, self._ui(guide), 10, font
        )

    # ---- 今のモデル・effort と、選ぶメニュー（--claude のとき。/model と /effort を入力欄で打ったときに使う） ----

    def _note_state(self, text: str) -> None:
        """会話記録の /model・/effort の結果から、今のモデルと effort を覚える（ほかから打たれた分も含む）。"""
        model = SET_MODEL_RE.search(text)
        if model is not None:
            self._cur_model = model.group(1)
        effort = SET_EFFORT_RE.search(text)
        if effort is not None:
            self._cur_effort = effort.group(1)

    def _read_state_screen(self) -> bool:
        """tmux の画面から今のモデルと effort を読む。見つかったら True。画面が読めない・見つからないなら False。"""
        text = self._slash_capture()  # tmux の画面を読む共通の口（コマンドの窓と同じ）
        if text is None:
            return False
        for line in text.split("\n"):
            found = STATE_RE.search(line)
            if found is not None:
                self._cur_model = f"{found.group(1)} {found.group(2)}"
                self._cur_effort = found.group(3) or STATE_DEFAULT_EFFORT
                return True
        return False

    def _update_state_read(self, dt: float) -> None:
        """始業したあとの読み取り。STATE_READ_EVERY_SEC ごとに画面を読み、見つかったか STATE_READ_SEC たったら止める。"""
        if self._state_left <= 0.0 or not self.started:
            return
        self._state_left -= dt
        self._state_next -= dt
        if self._state_next > 0.0:
            return
        self._state_next = STATE_READ_EVERY_SEC
        if self._read_state_screen():
            self._state_left = 0.0

    def _forget_state(self) -> None:
        """終業・セッション消失のあと、今のモデルと effort を "?" に戻し、読み取りとメニューも止める。"""
        self._cur_model = "?"
        self._cur_effort = "?"
        self._state_left = 0.0
        self._usage_start_armed = False
        self._usage_after_turn_left = 0.0
        self._close_menu()
        self._pages.clear()  # 会話のダイアログのやりとりも空にし、最新を見る状態に戻す
        self._page_index = None
        self._last_reply = None
        self._last_prompt = None

    def _is_menu_command(self, text: str) -> bool:
        """送る文が、選ぶメニューを開く文か（前後の空白を除いて、ちょうど /model か /effort）。"""
        return text.strip() in ("/model", "/effort")

    def _menu_choices(self, kind: str) -> tuple[tuple[str, str], ...]:
        """メニューの選択肢。kind は "model" か "effort"。"""
        return MENU_MODEL_CHOICES if kind == "model" else MENU_EFFORT_CHOICES

    def _menu_is_current(self, kind: str, choice: tuple[str, str]) -> bool:
        """選択肢が今の値か。モデルは表示名と今のモデルを、effort は引数と今の effort を比べる。"""
        name, arg = choice
        if kind == "model":
            return self._cur_model == name
        return self._cur_effort == arg

    def _menu_height(self, count: int) -> int:
        """メニューの高さ。1行目は題、最後の行は案内。"""
        return UI_PAD * 2 + (count + 2) * UI_LINE_H

    def _open_menu(self, kind: str) -> None:
        """選ぶメニューを開く。選んでいる行は今の値の行（分からなければ先頭）。モードは PROMPT のまま。"""
        self._menu = kind
        choices = self._menu_choices(kind)
        self._menu_sel = next(
            (i for i, choice in enumerate(choices) if self._menu_is_current(kind, choice)), 0
        )

    def _close_menu(self) -> None:
        """選ぶメニューを閉じる。何も送らない。"""
        self._menu = None

    def _decide_menu(self) -> None:
        """選んでいる値を、/model か /effort の引数として送り、メニューを閉じる。送りかたは通常の送信と同じ（許可の待ち・始業前の扱い）。"""
        kind = self._menu
        if kind is None:
            return
        _name, arg = self._menu_choices(kind)[self._menu_sel]
        self._close_menu()
        self._send_to_claude(f"/{kind} {arg}")

    def _update_menu(self) -> None:
        """メニューの1フレーム：許可の依頼が来たら何も送らず閉じる。↑↓で選ぶ、Enter で決める、Esc で閉じる。"""
        if self._perm_pending or self._perm_lock:
            self._close_menu()
            return
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._close_menu()
            return
        if self._menu is None:
            return
        count = len(self._menu_choices(self._menu))
        if pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=3):
            self._menu_sel = max(0, self._menu_sel - 1)
        if pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=3):
            self._menu_sel = min(count - 1, self._menu_sel + 1)
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_KP_ENTER):
            self._decide_menu()

    def _menu_click(self, sx: int, sy: int) -> None:
        """メニューのクリック。外なら何も送らず閉じる。選んでいない行ならその行を選び、選んでいる行をもう一度押したら決める。"""
        if self._menu is None:
            return
        choices = self._menu_choices(self._menu)
        if not self._in_rect(sx, sy, SLASH_X, SLASH_Y, SLASH_W, self._menu_height(len(choices))):
            self._close_menu()
            return
        row = (sy - (SLASH_Y + UI_PAD)) // UI_LINE_H - 1  # 1行目は題。選ぶ行は2行目から
        if not 0 <= row < len(choices):
            return
        if row == self._menu_sel:
            self._decide_menu()
        else:
            self._menu_sel = row

    def _draw_menu(self) -> None:
        """選ぶメニューを描く。コマンドの窓と同じ位置・背景の透かし。今の値の行の頭に * を付け、選んでいる行は反転する。"""
        kind = self._menu
        if kind is None:
            return
        font = self.ui_font
        choices = self._menu_choices(kind)
        height = self._menu_height(len(choices))
        pyxel.dither(SLASH_DITHER)  # 背景の黒だけ半透明にする
        pyxel.rect(SLASH_X, SLASH_Y, SLASH_W, height, 0)
        pyxel.dither(1.0)  # 戻す（枠・文字は通常の濃さ）
        pyxel.rectb(SLASH_X, SLASH_Y, SLASH_W, height, TEXT_COLOR)
        if font is None:
            return
        title = t("menu_title_model") if kind == "model" else t("menu_title_effort")
        pyxel.text(SLASH_X + UI_PAD, SLASH_Y + UI_PAD, self._ui(title), 10, font)
        label_x = SLASH_X + UI_PAD + UI_CHAR_W * 2
        for row_no, choice in enumerate(choices):
            name, arg = choice
            mark = "*" if self._menu_is_current(kind, choice) else " "
            label = self._ui(f"{mark} {name}" if kind == "effort" else f"{mark} {name}  [{arg}]")
            y = SLASH_Y + UI_PAD + (row_no + 1) * UI_LINE_H
            if row_no == self._menu_sel:
                pyxel.text(SLASH_X + UI_PAD, y, ">", 10, font)
                pyxel.rect(label_x - 2, y, font.text_width(label) + 4, UI_LINE_H, 7)  # 選んでいる行は白い帯に黒い字
                pyxel.text(label_x, y, label, 0, font)
            else:
                pyxel.text(label_x, y, label, TEXT_COLOR, font)
        guide_y = SLASH_Y + UI_PAD + (len(choices) + 1) * UI_LINE_H
        pyxel.text(SLASH_X + UI_PAD, guide_y, self._ui(t(MENU_GUIDE)), 10, font)

    # ---- 会話のダイアログ（3D の範囲に出す。--claude のとき、メインかサブエージェントと話しているとき） ----

    def _talk_dialog_partner(self) -> int | None:
        """ダイアログを出す相手の番号。--claude で、会話の相手がメインかサブエージェントのときだけ。それ以外は None。"""
        if not self.claude or self.talk_partner is None:
            return None
        partner = self.talk_partner
        if partner == MAIN_INDEX or self.agents[partner].role == "sub":
            return partner
        return None

    def _talk_dialog_lines(self, partner: int) -> list[tuple[str, int]]:
        """ダイアログの中身を、桁数で折り返した（字, 色）の一覧にする（最後の固定の行は含まない）。
        メインとの会話（依頼が無いとき）は今のページ、それ以外は今までどおり文字の一覧に色を付ける。"""
        if partner == MAIN_INDEX and not self._perm_pending:
            return self._talk_page_lines()
        return [(row, TEXT_COLOR) for row in self._talk_dialog_texts(partner)]

    def _current_page_index(self) -> int:
        """今見ているページの番号。None（最新）のときは最後のページ。ページが無いときは 0。"""
        if not self._pages:
            return 0
        if self._page_index is None:
            return len(self._pages) - 1
        return int(_clamp(self._page_index, 0, len(self._pages) - 1))

    def _talk_page_lines(self) -> list[tuple[str, int]]:
        """メインとの会話のダイアログの中身（今のページ）。1行目は題、次はプロンプト・空行・返事（折り返し済み）。"""
        codes = self.ui_codes
        if not self._pages:
            title = t("main_name")
        else:
            title = t("dialog_main_page", page=self._current_page_index() + 1, total=len(self._pages))
        rows: list[tuple[str, int]] = [(row, TEXT_COLOR) for row in _wrap_text(title, DLG_COLS, codes)]
        if not self._pages:
            rows.extend((row, TEXT_COLOR) for row in _wrap_text(t("talk_none_yet"), DLG_COLS, codes))
            return rows
        page = self._pages[self._current_page_index()]
        prompt_color = NOTICE_COLOR if page.notice else TALK_PROMPT_COLOR
        if page.prompt:
            for line in ("> " + page.prompt).split("\n"):
                rows.extend((row, prompt_color) for row in _wrap_text(line, DLG_COLS, codes))
            rows.append(("", TEXT_COLOR))  # プロンプトと返事のあいだの空行
        if page.replies:
            for line in "\n\n".join(page.replies).split("\n"):
                rows.extend((row, TEXT_COLOR) for row in _wrap_text(line, DLG_COLS, codes))
        else:
            rows.extend((row, NOTICE_COLOR) for row in _wrap_text(t("talk_waiting_reply"), DLG_COLS, codes))
        return rows

    def _page_guide_on(self, partner: int) -> bool:
        """ダイアログの一番下に「↑↓:前後のやりとり」を出すか（メインと話していて、依頼が無く、ページが2つ以上あるとき）。"""
        return partner == MAIN_INDEX and not self._perm_pending and len(self._pages) >= 2

    def _add_talk_page(self, page: TalkPage) -> None:
        """ページを1つ足す。TALK_PAGE_MAX を超えたら古いものから捨て、見ているページの番号もずらす（0 未満になれば 0）。"""
        self._pages.append(page)
        drop = len(self._pages) - TALK_PAGE_MAX
        if drop > 0:
            del self._pages[:drop]
            if self._page_index is not None:
                self._page_index = max(0, self._page_index - drop)

    def _talk_dialog_texts(self, partner: int) -> list[str]:
        """依頼・サブエージェントの会話のダイアログの文字の行（桁数で折り返し済み）。メインの通常の会話は _talk_page_lines を使う。"""
        agent = self.agents[partner]
        name = t("main_name") if partner == MAIN_INDEX else (agent.label or agent.name)
        codes = self.ui_codes
        rows: list[str] = _wrap_text(name, DLG_COLS, codes)
        if partner == MAIN_INDEX and self._perm_pending:
            req = self._perm_pending[0]
            if self._perm_always_confirm and self._perm_always_done():
                rows.extend(_wrap_text(t(PERM_ALWAYS_QUESTION), DLG_COLS, codes))
                for row in _suggestion_rows(req.suggestions):
                    rows.extend(_wrap_text(row, DLG_COLS, codes))
                return rows
            rows.extend(_wrap_text(t("perm_asking", count=len(self._perm_pending)), DLG_COLS, codes))
            rows.extend(_wrap_text(t("perm_tool", name=req.tool_name), DLG_COLS, codes))
            for key, value in _tool_input_rows(req.tool_input):
                for line in f"{key}: {value}".split("\n"):
                    rows.extend(_wrap_text(line, DLG_COLS, codes))
            return rows
        if partner == MAIN_INDEX:
            text = self._last_reply or self._last_prompt or t("talk_none_yet")
        else:
            text = self._last_line.get(partner, "")
        for line in text.split("\n"):
            rows.extend(_wrap_text(line, DLG_COLS, codes))
        return rows

    def _dlg_visible_rows(self, partner: int) -> int:
        """ダイアログで中身を出せる行数。許可の依頼があるときは、最後の行を Y・N・T の案内に使う。"""
        if partner == MAIN_INDEX and self._perm_pending:
            return DLG_BODY_ROWS - 1
        if self._page_guide_on(partner):
            return DLG_BODY_ROWS - 1  # 一番下は「↑↓:前後のやりとり」の案内
        return DLG_BODY_ROWS

    def _dlg_track(self) -> tuple[int, int, int, int]:
        """ダイアログのスクロールバーの溝 (x, y, 幅, 高さ)。右の端の内側。"""
        return (DLG_X + DLG_W - 2 - SCROLLBAR_W, DLG_Y + 2, SCROLLBAR_W, DLG_H - 4)

    def _dlg_thumb(self, total: int, visible: int) -> tuple[int, int]:
        """スクロールバーのつまみの (y, 高さ)。total は全部の行数、visible は見えている行数（total > visible のとき）。"""
        _, ty, _, th = self._dlg_track()
        thumb_h = max(6, int(th * visible / total))
        max_scroll = total - visible
        thumb_y = ty + int((th - thumb_h) * self._dlg_scroll / max_scroll)
        return (thumb_y, thumb_h)

    def _scroll_talk(self, partner: int, delta: int) -> None:
        """ダイアログの中身を delta 行動かす（0 から最後の行までに収める）。"""
        total = len(self._talk_dialog_lines(partner))
        max_scroll = max(0, total - self._dlg_visible_rows(partner))
        self._dlg_scroll = int(_clamp(self._dlg_scroll + delta, 0, max_scroll))

    def _click_talk_dialog(self, partner: int, sx: int, sy: int) -> None:
        """ダイアログの上のクリック：つまみを押したら動かし始める。溝を押したら1画面ぶん動かす。"""
        total = len(self._talk_dialog_lines(partner))
        visible = self._dlg_visible_rows(partner)
        tx, ty, tw, th = self._dlg_track()
        if total <= visible or not self._in_rect(sx, sy, tx, ty, tw, th):
            return
        thumb_y, thumb_h = self._dlg_thumb(total, visible)
        if thumb_y <= sy < thumb_y + thumb_h:
            self._dlg_drag = True
        elif sy < thumb_y:
            self._scroll_talk(partner, -visible)
        else:
            self._scroll_talk(partner, visible)

    def _drag_talk_dialog(self, partner: int, sy: int) -> None:
        """つまみを押したまま動かしたとき、つまみの位置から中身の先頭の行を決める。"""
        total = len(self._talk_dialog_lines(partner))
        visible = self._dlg_visible_rows(partner)
        if total <= visible:
            return
        _, ty, _, th = self._dlg_track()
        thumb_h = self._dlg_thumb(total, visible)[1]
        span = th - thumb_h
        frac = _clamp((sy - ty - thumb_h / 2.0) / span, 0.0, 1.0) if span > 0 else 0.0
        self._dlg_scroll = int(round(frac * (total - visible)))

    def _update_talk_dialog(self) -> None:
        """毎フレーム：ダイアログが出ていないときは、スクロールとつまみの押しを戻す。つまみを押したままなら動かす。"""
        partner = self._talk_dialog_partner()
        if partner is None:
            self._dlg_scroll = 0
            self._dlg_drag = False
            return
        if self._dlg_drag:
            if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
                self._drag_talk_dialog(partner, pyxel.mouse_y)
            else:
                self._dlg_drag = False

    def _update_talk_dialog_keys(self) -> None:
        """PageUp・PageDown で、ダイアログの中身を1画面ぶん動かす（WALK のとき）。"""
        partner = self._talk_dialog_partner()
        if partner is None:
            return
        visible = self._dlg_visible_rows(partner)
        if pyxel.btnp(pyxel.KEY_PAGEUP):
            self._scroll_talk(partner, -visible)
        if pyxel.btnp(pyxel.KEY_PAGEDOWN):
            self._scroll_talk(partner, visible)

    def _update_talk_pages(self) -> None:
        """↑↓ で、メインとのやりとりのページをめくる。メインと会話中・依頼が無い・メニューとコマンドの窓が閉じているとき（WALK の中で呼ぶ）。
        ↑ は前のページ、↓ は次のページ。最後のページで ↓ なら最新（None）に戻す。ページを変えたらスクロールを 0 に戻す。"""
        if self.talk_partner != MAIN_INDEX or self._perm_pending or self._menu is not None or self._slash_open:
            return
        if not self._pages:
            return
        if pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=3):
            current = self._current_page_index()
            if current > 0:
                self._page_index = current - 1
                self._dlg_scroll = 0
        elif pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=3) and self._page_index is not None:
            if self._page_index >= len(self._pages) - 1:
                self._page_index = None  # 最後のページから ↓ で、最新に付いていく
            else:
                self._page_index += 1
            self._dlg_scroll = 0

    def _draw_talk_dialog(self, partner: int) -> None:
        """会話のダイアログを、3D の範囲に黒い箱で重ねて描く（中身・許可の案内・スクロールバー）。"""
        font = self.ui_font
        if font is None:
            return
        pyxel.dither(0.5)  # 背景の黒だけ半透明にする
        pyxel.rect(DLG_X, DLG_Y, DLG_W, DLG_H, 0)
        pyxel.dither(1.0)  # 戻す（枠・文字・スクロールバーは通常の濃さ）
        pyxel.rectb(DLG_X, DLG_Y, DLG_W, DLG_H, TEXT_COLOR)
        lines = self._talk_dialog_lines(partner)
        visible = self._dlg_visible_rows(partner)
        self._dlg_scroll = int(_clamp(self._dlg_scroll, 0, max(0, len(lines) - visible)))
        for row_no, (row, row_color) in enumerate(lines[self._dlg_scroll : self._dlg_scroll + visible]):
            color = PERM_ALWAYS_COLOR if self._perm_always_confirm and row == t(PERM_ALWAYS_QUESTION) else row_color
            pyxel.text(DLG_X + UI_PAD, DLG_Y + UI_PAD + row_no * UI_LINE_H, self._ui(row), color, font)
        if partner == MAIN_INDEX and self._perm_pending:
            req = self._perm_pending[0]
            if self._perm_always_confirm and self._perm_always_done():
                guide = t(PERM_ALWAYS_CONFIRM_TEXT)
            elif req.suggestions:
                guide = t(PERM_KEYS_ALWAYS_TEXT)
            else:
                guide = t(PERM_KEYS_TEXT)
            pyxel.text(DLG_X + UI_PAD, DLG_Y + DLG_H - UI_PAD - UI_LINE_H, self._ui(guide), PERM_ALWAYS_COLOR, font)
        elif self._page_guide_on(partner):
            pyxel.text(DLG_X + UI_PAD, DLG_Y + DLG_H - UI_PAD - UI_LINE_H, self._ui(t(TALK_PAGE_GUIDE)), NOTICE_COLOR, font)
        if len(lines) > visible:
            tx, ty, tw, th = self._dlg_track()
            pyxel.rect(tx, ty, tw, th, 1)  # 溝
            thumb_y, thumb_h = self._dlg_thumb(len(lines), visible)
            pyxel.rect(tx, thumb_y, tw, thumb_h, TEXT_COLOR)

    def _update_claude_keys(self) -> None:
        """F1（始業・終業）と、ダイアログの 1〜3 を処理する。"""
        if self._dialog:
            for key, mode in ((pyxel.KEY_1, "resume"), (pyxel.KEY_2, "restart"), (pyxel.KEY_3, "")):
                if pyxel.btnp(key):
                    self._choose_dialog(mode)
                    return
            return
        if pyxel.btnp(pyxel.KEY_F1):
            self._toggle_session()

    def _update_claude(self, dt: float) -> None:
        """--claude の毎フレームの処理：セッションの確かめ、会話記録のイベント、終業の待ち、吹き出し、帰る時間、10分の休み、ドア。"""
        if self.bridge is None:
            return
        if self.started:
            self._session_check_left -= dt
            if self._session_check_left <= 0.0:
                self._session_check_left = SESSION_CHECK_SEC
                if not self.bridge.session_exists():
                    self._session_gone()
        if self.started:
            for event in self.bridge.poll():
                self._on_event(event)
        self._update_state_read(dt)  # 始業したあと、画面から今のモデルと effort を読む
        self._update_perm_requests()  # 許可の依頼の受け取り・時間切れ・取り下げ
        self._update_perm_keys()  # Y・N・T（WALK でメインと会話しているとき）
        self._update_usage(dt)  # 利用制限を /usage で読む（読めるときだけ。取っておいた文も送る）
        if self.ending and self.started:
            self._handoff_left -= dt
            if self._handoff_left <= 0.0:
                self._finish_ending()
        if self._bubble_left > 0.0:
            self._bubble_left -= dt
            if self._bubble_left <= 0.0:
                self._bubble = ""
        for i in list(self._leave_timers):
            self._leave_timers[i] -= dt
            if self._leave_timers[i] <= 0.0:
                del self._leave_timers[i]
                self._leave(i)
        main = self.agents[MAIN_INDEX]
        if self.started and main.visible and not main.busy:
            self._idle_main += dt
            if self._idle_main >= IDLE_LEAVE_SEC:
                self._idle_main = 0.0
                self._leave(MAIN_INDEX)  # tmux は動かしたまま、メインだけ帰る
        self._update_door_auto(dt)

    def _on_event(self, event: object) -> None:
        """会話記録のイベント1つを、画面の動きと履歴に反映する。"""
        main = self.agents[MAIN_INDEX]
        if isinstance(event, Prompt):
            self._idle_main = 0.0
            if not main.visible:
                self._enter(MAIN_INDEX)
            main.busy = True
            self._note_state(event.text)  # /model・/effort の結果から、今のモデルと effort を覚える
            shown, notice = prompt_display(event.text)  # タグを外した見せる文（決まった形の知らせなら notice が True）
            self._busy_text[MAIN_INDEX] = _first_line(shown)  # 作業中の吹き出し（返事が来るまでは依頼の文）
            if not notice or shown.startswith("/"):
                self._human_text = shown  # 人間の吹き出し（送ったプロンプト。知らせ・コマンドの出力は人間の言葉ではないので出さない）
            if not main.is_seated and main.state != WORKING:
                self._begin_work(MAIN_INDEX)
            if self.ending and event.text == t(HANDOFF_PROMPT):
                self._handoff_seen = True  # 引き継ぎメモの依頼が記録に出た（これ以降の TurnEnd で終業）
            self._last_prompt = shown  # 会話のダイアログに出す全文
            self._add_talk_page(TalkPage(prompt=shown, notice=notice))  # 会話のダイアログの新しいページ
            if self._page_index is None:
                self._dlg_scroll = 0  # 最新を見ているときは、新しいページを先頭から見せる（前のページを読んでいるときは変えない）
            if event.text == self._last_sent:
                self._last_sent = None  # 自分で送った分は、もう履歴にある
            else:
                # ほかから打たれた分。決まった形の知らせは灰色で出す
                self._add_block("> ", shown, color=NOTICE_COLOR if notice else TEXT_COLOR)
        elif isinstance(event, Tool):
            self._idle_main = 0.0
            self._clear_perm_tmux()  # tmux で答えた許可の後の動きが届いたら、送信の止めを外す（依頼が残っていれば残す）
            if not main.visible:
                self._enter(MAIN_INDEX)
            main.busy = True
            who = t("subagent_name") if event.name == "Agent" else event.name
            self._add_history(f"  [{who}] {event.summary}")
            self._last_line[MAIN_INDEX] = f"{who}: {event.summary}"
        elif isinstance(event, Reply):
            self._idle_main = 0.0
            self._clear_perm_tmux()
            self._last_reply = event.text  # 会話のダイアログに出す全文
            if self._pages:
                self._pages[-1].replies.append(event.text)  # 最後のページの返事に足す
            else:
                self._add_talk_page(TalkPage(prompt="", notice=False, replies=[event.text]))  # プロンプトが無いときは空の文のページ
            if self._page_index is None:
                self._dlg_scroll = 0
            if main.busy:
                # 作業中は、作業中の吹き出しに出す。6秒の吹き出しは作業が終わってから出す
                self._busy_text[MAIN_INDEX] = _first_line(event.text)
                self._pending_reply = event.text
            else:
                self._bubble = event.text
                self._bubble_left = BUBBLE_SEC
            # 返事は会話のダイアログで読むので、履歴には出さない
        elif isinstance(event, TurnEnd):
            main.busy = False
            self._idle_main = 0.0
            self._clear_perm_tmux()
            self._busy_text.pop(MAIN_INDEX, None)  # 作業中の吹き出しは消す
            self._usage_after_turn_left = USAGE_AFTER_TURN_SEC  # 返事のあと少ししてから利用制限を読む
            self._human_text = None
            if self._pending_reply is not None:
                self._bubble = self._pending_reply  # 作業が終わったあとの最後の返事を6秒出す
                self._bubble_left = BUBBLE_SEC
                self._pending_reply = None
            if self.ending and self._handoff_seen:
                self._finish_ending()  # 引き継ぎメモの返事が終わった
        elif isinstance(event, SubagentStart):
            if event.agent_id in self._sub_map:
                return
            label = event.agent_type or "sub"
            reuse = self._find_reusable_sub()
            if reuse is not None:
                # 仕事を終えて帰るのを待っている人がいれば、その人を使う（帰るのをやめて席へ戻る）
                slot = reuse
                self._leave_timers.pop(slot, None)
                sub = self.agents[slot]
                sub.role = "sub"
                sub.label = label
                sub.busy = True
                self._busy_text[slot] = _first_line(event.description) or label
                self._sub_map[event.agent_id] = slot
                self._last_line[slot] = event.description
                self._begin_work(slot)  # 席へ戻って作業に入る（会話の相手でも会話は続く）
                self._add_history(t("hist_called", label=label, desc=event.description))
                return
            slot = next(
                (
                    i
                    for i in range(SUB_SLOT_FIRST, min(SUB_SLOT_END, len(self.agents)))
                    if not self.agents[i].visible
                ),
                None,
            )
            if slot is None:
                return  # 空いている席が無ければ何もしない（作業は止めない）
            sub = self.agents[slot]
            sub.role = "sub"
            sub.label = label
            sub.busy = True
            self._busy_text[slot] = _first_line(event.description) or label  # 作業中の吹き出し（説明。空なら名前）
            self._sub_map[event.agent_id] = slot
            self._last_line[slot] = event.description
            self._enter(slot)
            self._add_history(t("hist_called", label=label, desc=event.description))
        elif isinstance(event, SubagentEnd):
            slot = self._sub_map.pop(event.agent_id, None)
            if slot is None:
                return
            self.agents[slot].busy = False
            self._busy_text.pop(slot, None)
            self._leave_timers[slot] = SUB_LEAVE_SEC

    def _find_reusable_sub(self) -> int | None:
        """再利用できるサブの席の番号を返す（無ければ None）。見えていて、作業が終わって帰るのを待っている人（_leave_timers に入っている）で、部屋を出る途中でない人。"""
        for i in range(SUB_SLOT_FIRST, min(SUB_SLOT_END, len(self.agents))):
            agent = self.agents[i]
            if not agent.visible or agent.role != "sub" or agent.busy:
                continue
            if i in self._sub_map.values() or i not in self._leave_timers:
                continue
            if agent.state == LEAVING:
                continue
            return i
        return None

    def _button_rect(self, label: str) -> tuple[int, int, int, int]:
        """始業・終業のボタンの長方形 (x, y, 幅, 高さ)。左上、人数表示の下。"""
        font = self.ui_font
        width = (font.text_width(self._ui(label)) if font is not None else len(label) * pyxel.FONT_WIDTH) + 8
        return (4, BUTTON_Y, width, UI_LINE_H)

    def _claude_click(self, sx: int, sy: int) -> bool:
        """--claude のときのクリック（ボタンとダイアログ）。処理したら True。ダイアログを出している間は、ほかのクリックを受けない。"""
        if not self.claude:
            return False
        if self._dialog:
            for k, (mode, _key) in enumerate(CLAUDE_DIALOG_OPTIONS):
                if self._in_rect(sx, sy, 68, 94 + k * 16, 504, 14):
                    self._choose_dialog(mode)
                    return True
            return True
        label = t("button_clock_out") if self.started else t("button_clock_in")
        if self._in_rect(sx, sy, *self._button_rect(label)):
            self._toggle_session()
            return True
        return False

    def _head_point(self, agent: Agent) -> tuple[float, float] | None:
        """人の頭の画面上の位置。3D の範囲の外・カメラの後ろなら None。"""
        point = self.world_to_screen(
            Vec3(agent.pos.x, HEAD_CENTER.y + agent.pose.body_y, agent.pos.z),
            0,
            0,
            OFFICE_SCREEN_W,
            VIEW3D_H,
        )
        if point is None:
            return None
        if not (0 <= point[0] < OFFICE_SCREEN_W and 0 <= point[1] < VIEW3D_H):
            return None
        return point

    def _draw_bubble(self, point: tuple[float, float], shown: str) -> None:
        """白い吹き出し（黒い文字）を、点 point の真上に出す。口元の三角は点を指す。画面の上に入らないときは出さない。"""
        font = self.ui_font
        if font is None or not shown:
            return
        shown = self._ui(shown)
        w = font.text_width(shown) + 6
        h = UI_LINE_H + 2
        x = int(_clamp(point[0] - w / 2.0, 0, OFFICE_SCREEN_W - w))
        y = int(point[1] - h - 8)
        if y < 0:
            return
        pyxel.rect(x, y, w, h, TEXT_COLOR)
        pyxel.text(x + 3, y + 1, shown, 0, font)
        tip_x, tip_y = int(point[0]), y + h
        pyxel.tri(tip_x - 3, tip_y, tip_x + 3, tip_y, tip_x, tip_y + 5, TEXT_COLOR)

    def _draw_claude(self) -> None:
        """--claude のときの2Dの表示：始業・終業のボタン、ダイアログ、吹き出し、名前の札、話しかけた様子。"""
        font = self.ui_font
        if font is None:
            return
        label = t("button_clock_out") if self.started else t("button_clock_in")
        bx, by, bw, bh = self._button_rect(label)
        pyxel.rect(bx, by, bw, bh, 0)
        pyxel.text(bx + 4, by + 1, self._ui(label), TEXT_COLOR, font)

        if self._dialog:
            pyxel.rect(60, 70, 520, 110, 0)
            pyxel.rectb(60, 70, 520, 110, TEXT_COLOR)
            pyxel.text(68, 78, self._ui(t("dialog_title")), TEXT_COLOR, font)
            for k, (_mode, key) in enumerate(CLAUDE_DIALOG_OPTIONS):
                pyxel.text(68, 96 + k * 16, self._ui(t(key)), TEXT_COLOR, font)

        main = self.agents[MAIN_INDEX]
        bubble_shown = False
        # 許可の依頼があるあいだ、メインの頭の上に「！」を出し、メインの吹き出しは出さない
        perm_waiting = bool(self._perm_pending) and main.visible
        if self._bubble and self._bubble_left > 0.0 and main.visible and not perm_waiting:
            text = self._bubble.replace("\n", " ")
            shown = self._ui(text[:BUBBLE_CHARS] + ("…" if len(text) > BUBBLE_CHARS else ""))
            head = self._head_point(main)
            if head is not None:
                bubble_shown = True
                w = font.text_width(shown) + 6
                h = UI_LINE_H + 2
                x = int(_clamp(head[0] - w / 2.0, 0, OFFICE_SCREEN_W - w))
                y = int(head[1] - h - 8)
                if y >= 0:
                    pyxel.rect(x, y, w, h, TEXT_COLOR)
                    pyxel.text(x + 3, y + 1, shown, 0, font)
                    tip_x, tip_y = int(head[0]), y + h
                    pyxel.tri(tip_x - 3, tip_y, tip_x + 3, tip_y, tip_x, tip_y + 5, TEXT_COLOR)

        # 作業中の吹き出し（見えている人。作業が終わるまで出したまま）
        busy_shown: set[int] = set()
        for i, text in self._busy_text.items():
            agent = self.agents[i]
            if not agent.visible or not text or (perm_waiting and i == MAIN_INDEX):
                continue
            head = self._head_point(agent)
            if head is None:
                continue
            self._draw_bubble(head, _short_text(text))
            busy_shown.add(i)
        if perm_waiting and font is not None and not self._slash_open:  # コマンドの窓の間は「！」を描かない
            head = self._head_point(main)
            if head is not None:
                mark = self._ui("！")
                pyxel.text(
                    int(head[0]) - font.text_width(mark) // 2, int(head[1]) - 24, mark, 10, font
                )
        # 人間の吹き出し（メインが作業中のとき。▼のさらに上に出す）
        if self._human_text and main.busy and self.human is not None:
            point = self.world_to_screen(
                Vec3(self.human.pos.x, MARKER_Y + MARKER_BOB + MARKER_DEPTH / 2.0 + 2.0, self.human.pos.z),
                0,
                0,
                OFFICE_SCREEN_W,
                VIEW3D_H,
            )
            shown = _short_text(_first_line(self._human_text))
            if point is not None and shown:
                self._draw_bubble(point, shown)

        # 名前の札（見えている人。吹き出しが出ている人は除く。人間は出さない）
        for i in self._active_indices():
            agent = self.agents[i]
            if not agent.label or i in busy_shown or (bubble_shown and i == MAIN_INDEX):
                continue
            head = self._head_point(agent)
            if head is None:
                continue
            color = 10 if agent.role == "main" else TEXT_COLOR
            text_w = len(agent.label) * pyxel.FONT_WIDTH
            pyxel.text(int(head[0]) - text_w // 2, int(head[1]) - 10, agent.label, color)

        # 会話のダイアログは最後に重ねる（メインかサブエージェントと話しているとき）
        dialog_partner = self._talk_dialog_partner()
        if self._slash_open:
            self._draw_slash()  # コマンドの窓の間は、会話のダイアログを描かない
        elif dialog_partner is not None:
            self._draw_talk_dialog(dialog_partner)
        if self._menu is not None:
            self._draw_menu()  # 選ぶメニューは一番上に重ねる

    def _update_door(self, dt: float) -> None:
        """ドアの角度を目標（開く 90 度・閉じる 0 度）へ DOOR_SPEED で近づける。目標を行き過ぎない。"""
        target = DOOR_OPEN_ANGLE if self.door_open else 0.0
        step = DOOR_SPEED * dt
        if self.door_angle < target:
            self.door_angle = min(target, self.door_angle + step)
        else:
            self.door_angle = max(target, self.door_angle - step)

    def _update_rate_keys(self) -> None:
        """数字キー 1〜4 で利用制限の値を RATE_KEY_STEP ずつ変える。押したら以後は JSON を読まない。

        1 は 5時間を減らし、2 は増やす。3 は週間を減らし、4 は増やす。
        """
        if self.claude:
            return  # --claude のときは /usage の値を使う（手動では変えない）
        if pyxel.btnp(pyxel.KEY_1):
            self.manual_limits = True
            self.five_hour = _clamp(self.five_hour - RATE_KEY_STEP, 0.0, 100.0)
        if pyxel.btnp(pyxel.KEY_2):
            self.manual_limits = True
            self.five_hour = _clamp(self.five_hour + RATE_KEY_STEP, 0.0, 100.0)
        if pyxel.btnp(pyxel.KEY_3):
            self.manual_limits = True
            self.seven_day = _clamp(self.seven_day - RATE_KEY_STEP, 0.0, 100.0)
        if pyxel.btnp(pyxel.KEY_4):
            self.manual_limits = True
            self.seven_day = _clamp(self.seven_day + RATE_KEY_STEP, 0.0, 100.0)

    def _update_rate_limits(self) -> None:
        """手動で変えていなければ、_reload_every フレームごとに JSON を読み直す。"""
        if self.manual_limits or self.claude:
            return  # --claude のときは JSON を読まない（/usage の値を使う）
        self._reload_count += 1
        if self._reload_count >= self._reload_every:
            self._reload_count = 0
            self.reload_rate_limits()

    def reload_rate_limits(self) -> None:
        """JSON を読み、five_hour と seven_day に used_percentage を 0〜100 に収めて入れる。

        ファイルが無い・壊れている・項目が無い・数でないときは、その値を 0.0 にする。例外は出さない。
        """
        data: object = None
        try:
            with self.rate_json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = None
        self.five_hour = _read_used_percentage(data, "five_hour")
        self.seven_day = _read_used_percentage(data, "seven_day")

    def _sync_scene_values(self) -> None:
        """利用制限の値とドアの角度を OfficeRoot に書き込む（描画が読む）。"""
        self.scene.five_hour = self.five_hour
        self.scene.seven_day = self.seven_day
        self.scene.door_angle = self.door_angle

    def _update_view(self, dt: float) -> None:
        """カーソルキーで視点を回す。押している間ずっと効くよう pyxel.btn を使う。

        → で yaw を増やす（目が +X 側へ回る）、← で減らす。
        ↑ で pitch を増やす（真上に近づく）、↓ で減らす。変わったら視点を更新する。
        """
        turn = int(pyxel.btn(pyxel.KEY_RIGHT)) - int(pyxel.btn(pyxel.KEY_LEFT))
        tilt = int(pyxel.btn(pyxel.KEY_UP)) - int(pyxel.btn(pyxel.KEY_DOWN))
        if turn == 0 and tilt == 0:
            return
        self.cam_yaw = (self.cam_yaw + turn * CAM_YAW_SPEED * dt) % 360.0
        self.cam_pitch = _clamp(
            self.cam_pitch + tilt * CAM_PITCH_SPEED * dt, CAM_PITCH_MIN, CAM_PITCH_MAX
        )
        self._apply_camera()

    def _resolve_collisions(self) -> None:
        """障害物・キャラどうし（人間を含む）・床の範囲の順に押し出し、結果を各 pos に書き戻す。

        この3つを1組として COLLISION_ITERATIONS 回繰り返す。床に収めた後の重なりも次の回で直す。
        WORKING のキャラは自分の席の机と椅子を無視する（座るため）。着席中と行き先の立つ場所にいるキャラは動かさない。
        """
        # 見えている人だけを押し出す（--claude のとき見えていない人は入れない）。人間は最後に1人として並べる
        active = self._active_indices()
        bodies: list[Agent] = [self.agents[i] for i in active]
        owners: list[int] = list(active)  # 障害物の持ち主（席の番号。人間は -1）
        fixed: list[bool] = [self.agents[i].is_fixed for i in active]
        if self.human is not None:
            bodies.append(self.human)
            owners.append(-1)
            fixed.append(True)  # 人間はいつも押されない。ぶつかったエージェントのほうが押し出される
        leaving = [b.state == LEAVING for b in bodies]  # 部屋を出る人は、ほかの人と押し合わない
        xs = [b.pos.x for b in bodies]
        zs = [b.pos.z for b in bodies]
        x_min, x_max = self.layout.wander_x
        z_min, z_max = self.layout.wander_z

        for _ in range(COLLISION_ITERATIONS):
            # 1. 障害物から押し出す
            for i, body in enumerate(bodies):
                for ob in self.obstacles:
                    if body.state == WORKING and ob.owner == owners[i]:
                        continue
                    xs[i], zs[i] = push_out_of_rect(
                        xs[i], zs[i], AGENT_RADIUS, ob.rect
                    )
                # 丸い障害物からも押し出す。作業中のキャラも無視しない
                for cx, cz, cr in self.circles:
                    xs[i], zs[i] = push_out_of_circle(xs[i], zs[i], AGENT_RADIUS, cx, cz, cr)

            # 2. キャラどうしを引き離す（全ペア。人間も1人として入る）
            for i in range(len(bodies)):
                for j in range(i + 1, len(bodies)):
                    if leaving[i] or leaving[j]:
                        continue  # 部屋を出る人が絡むペアは押し合わない（障害物との判定は上のとおり）
                    xs[i], zs[i], xs[j], zs[j] = separate(
                        xs[i],
                        zs[i],
                        xs[j],
                        zs[j],
                        AGENT_RADIUS,
                        fixed[i],
                        fixed[j],
                    )

            # 3. 床の範囲（Layout の wander_x・wander_z）に収める
            for i in range(len(bodies)):
                xs[i] = _clamp(xs[i], x_min, x_max)
                zs[i] = _clamp(zs[i], z_min, z_max)

        # 4. 押し出した位置を pos に書き戻す（y は 0）。Agent と人間の両方
        for body, x, z in zip(bodies, xs, zs):
            body.pos = Vec3(x, 0.0, z)

    def _check_stuck(self, prev_xz: list[tuple[float, float]], dt: float) -> None:
        """歩いているのに予定の STUCK_RATIO 未満しか進めないフレームが STUCK_SEC 続いたら、目標か道を選び直させる。

        予定どおり進めたフレームがあれば、計っていた時間は0に戻す。
        office では行き先へ向かう人・席へ戻る人・作業で席へ向かう人も数え、状態が変わったら計り直す。
        道を探す順番待ちの人は歩いていないので、待っている時間は数えない。
        """
        for i, agent in enumerate(self.agents):
            if not agent.visible:
                continue  # 見えていない人は引っかかりを数えない（--claude のとき）
            if self.layout.has_props and agent.state != self._stuck_state[i]:
                self._stuck_state[i] = agent.state
                self._stuck_time[i] = 0.0
                self._stuck_count[i] = 0
            if agent.path_wait:
                self._stuck_time[i] = 0.0  # 順番待ちの時間は引っかかりに数えない
                continue
            if agent.sidestepping:
                self._stuck_time[i] = 0.0  # 横へよけている最中は引っかかりに数えない
                continue
            if not self._stuck_counted(agent) or agent.intended_move <= 0.0:
                continue  # 歩いていないフレームは数えない
            prev_x, prev_z = prev_xz[i]
            moved = math.hypot(agent.pos.x - prev_x, agent.pos.z - prev_z)
            if moved < STUCK_RATIO * agent.intended_move:
                self._stuck_time[i] += dt
                if self._stuck_time[i] >= STUCK_SEC:
                    self._repath(i)
                    self._stuck_time[i] = 0.0
            else:
                self._stuck_time[i] = 0.0

    def _stuck_counted(self, agent: Agent) -> bool:
        """引っかかりを数える状態か。WANDER は今までどおり。office では行き先へ向かう・席へ戻る・作業で席へ向かう人も数える。"""
        if agent.state == WANDER:
            return True
        return self.layout.has_props and agent.state in (GOING, RETURNING, WORKING)

    def _repath(self, i: int) -> None:
        """引っかかった人 i の目標か道を選び直す。WANDER は目標を選び直す。行き先へ行けなければあきらめて WANDER に戻す。

        同じ状態で SIDESTEP_AFTER 回続けて引っかかったら、近くの人から離れる向きへ横によける（道は探さない）。
        よける向きが無いときは、近くの人をよけて道を探し直す。
        """
        agent = self.agents[i]
        if agent.state == WANDER:
            agent.repick_target()
            return
        self.stat_replans += 1
        self._stuck_count[i] += 1
        if self._stuck_count[i] >= SIDESTEP_AFTER:
            direction = self._sidestep_direction(i)
            if direction is not None:
                agent.begin_sidestep(*direction)
                self._stuck_count[i] = 0
                self.stat_sidesteps += 1
                return
        agent.avoid_near = True  # 次の道探しでは、近くの人もよける
        if not agent.request_replan():
            self._path_failed(i)

    def _sidestep_direction(self, i: int) -> tuple[float, float] | None:
        """引っかかった人 i が横へよける向き（単位ベクトル）。よけなくてよいときや向きが無いときは None。

        いちばん近くて NAV_NEAR_DIST 以内の人 j から離れる向きを基準に、その左右で通れるほうを選ぶ。
        両方通れなければ、j から離れる向きそのものを使う。
        よけるのは、i が j より番号が後ろか、j が席や立つ場所で動かない人のとき（動く人どうしが同時によけないため）。
        """
        nav = self.nav
        if nav is None:
            return None
        agent = self.agents[i]
        nearest: int | None = None
        nearest_dist = 0.0
        for j, other in enumerate(self.agents):
            if j == i or not other.visible:
                continue
            dist = math.hypot(other.pos.x - agent.pos.x, other.pos.z - agent.pos.z)
            if dist <= NAV_NEAR_DIST and (nearest is None or dist < nearest_dist):
                nearest = j
                nearest_dist = dist
        if nearest is None or nearest_dist == 0.0:
            return None  # 近くに人がいない、または重なっていて向きが決まらない
        other = self.agents[nearest]
        if not (i > nearest or other.is_fixed):
            return None
        # j から i へ離れる向きの単位ベクトル
        ax = (agent.pos.x - other.pos.x) / nearest_dist
        az = (agent.pos.z - other.pos.z) / nearest_dist
        # 左右（離れる向きに垂直）のうち、SIDESTEP_PROBE 先が通れるほう
        for ux, uz in ((-az, ax), (az, -ax)):
            if nav._point_free(agent.pos.x + ux * SIDESTEP_PROBE, agent.pos.z + uz * SIDESTEP_PROBE):
                return (ux, uz)
        return (ax, az)

    def _people_for(self, i: int) -> list[tuple[float, float]]:
        """人 i が道を探すときに避けるほかの人の中心（x, z）の列。

        席に着いている人と、行き先の立つ場所にいる人は必ず入れる。
        avoid_near が True のときは、NAV_NEAR_DIST 以内の人も入れる（同じ人は1回だけ入る）。
        人間は、会話中なら必ず入れる。そうでなくても avoid_near のときは NAV_NEAR_DIST 以内なら入れる。
        最後に avoid_near を False に戻す。
        """
        agent = self.agents[i]
        people: list[tuple[float, float]] = []
        for j, other in enumerate(self.agents):
            if j == i or not other.visible:
                continue
            near = math.hypot(other.pos.x - agent.pos.x, other.pos.z - agent.pos.z) <= NAV_NEAR_DIST
            if other.is_fixed or (agent.avoid_near and near):
                people.append((other.pos.x, other.pos.z))
        human = self.human
        if human is not None:
            near = math.hypot(human.pos.x - agent.pos.x, human.pos.z - agent.pos.z) <= NAV_NEAR_DIST
            if self.talk_partner is not None or (agent.avoid_near and near):
                people.append((human.pos.x, human.pos.z))
        agent.avoid_near = False
        return people

    def _request_path(self, i: int) -> None:
        """道が要る人 i を列の後ろに並べる。すでに並んでいる人は二重に並べず、列の位置も変えない（その人の目標は新しいものになる）。"""
        if i not in self._nav_queue:
            self._nav_queue.append(i)

    def _serve_nav_queue(self) -> None:
        """列の先頭から順に道を探す。1フレームに探すのは NAV_MAX_PER_FRAME 人まで。見つからなければ後始末をする。"""
        served = 0
        while self._nav_queue and served < NAV_MAX_PER_FRAME:
            i = self._nav_queue.popleft()
            if not self.agents[i].path_wait:
                continue  # 道がもう要らなくなった古い番号は捨てる
            served += 1
            if not self.agents[i].serve_path(self._people_for(i)):
                self._path_failed(i)

    def _path_failed(self, i: int) -> None:
        """道が見つからなかった人 i の後始末。行き先へ行く人（GOING）は予約を外し、あきらめた数を1つ増やす。"""
        agent = self.agents[i]
        was_going = agent.state == GOING
        if agent.path_failed():
            if was_going and self.spot_manager is not None:
                self.spot_manager.release(i)
            self.stat_give_ups += 1

    def _start_next_work(self) -> None:
        """次の番号の人を作業状態にする。行き先にいた人は予約を外し、タイマーを0にする（office だけ）。

        道を探す順番を待っていた古い依頼は、作業の依頼に置き換わる（列の位置はそのまま）。道が要らなければ列から外す。
        """
        index = self.next_index
        agent = self.agents[index]
        self._chat[index] = Chatter()
        if self.claude and not agent.visible:
            self._enter(index)  # 見えていない人は、ドアから入って席へ
        else:
            self._begin_work(index)
        if not agent.path_wait and index in self._nav_queue:
            self._nav_queue.remove(index)
        self.next_index = (self.next_index + 1) % len(self.agents)

    def _update_wanderers(self, timer_dt: float) -> None:
        """うろついている人の休みとうろつき時間を数え、時間が来たら行き先を予約して GOING にする（office だけ）。

        休みの間はうろつき時間を数えず、休みを減らす。行き先が取れなければ、うろつき時間を0に戻して続ける。
        """
        manager = self.spot_manager
        if manager is None:
            return
        for i, agent in enumerate(self.agents):
            if agent.state != WANDER or self._is_held(i) or not agent.visible:
                continue  # 会話の相手は数えない（時間が進まない）
            if agent.cooldown > 0.0:
                agent.cooldown = max(0.0, agent.cooldown - timer_dt)
                continue
            agent.wander_time += timer_dt
            if agent.wander_time < OUTING_WANDER_SEC:
                continue
            agent.wander_time = 0.0
            manager.release(i)  # 古い予約が残っていても二重予約で止まらないように
            picked = manager.reserve(i)
            if picked is None:
                continue  # 空いている行き先が無い。うろつきを続けて、また後で選ぶ
            spot, slot = picked
            if not agent.begin_going(spot, slot):
                manager.release(i)
                self.stat_give_ups += 1

    def _update_spot_groups(self, timer_dt: float) -> None:
        """行き先にいる人を Spot ごとに数え、1人か会話かで姿勢と向きを決め、時間が来たら席へ戻す（office だけ）。"""
        groups: dict[str, tuple[Spot, list[int]]] = {}
        for i, agent in enumerate(self.agents):
            # 会話の相手は数えない（1人の時間・会話の時間が進まない。行き先の予約はそのまま）
            if agent.state == AT_SPOT and agent.spot is not None and not self._is_held(i):
                groups.setdefault(agent.spot.name, (agent.spot, []))[1].append(i)
        # 人がいなくなった行き先の話し手は消す
        for name in list(self._speakers):
            if name not in groups:
                del self._speakers[name]
                self._speaker_timers.pop(name, None)

        leaving: list[int] = []
        for name, (spot, members) in groups.items():
            if len(members) == 1:
                i = members[0]
                agent = self.agents[i]
                agent.alone_time += timer_dt  # 会話していない間だけ数える
                self._speakers.pop(name, None)
                self._speaker_timers.pop(name, None)
                self._chat[i] = Chatter()
                agent.pose = spot_pose(spot.kind)
                agent.yaw = facing_yaw(
                    agent.pos.x, agent.pos.z, spot.center[0], spot.center[1], default=agent.yaw
                )
                if agent.alone_time >= ALONE_SEC:
                    leaving.append(i)
                continue
            for i in members:
                agent = self.agents[i]
                agent.alone_time = 0.0
                agent.talk_time += timer_dt
            self._update_talk(name, members, timer_dt)
            leaving.extend(i for i in members if self.agents[i].talk_time >= TALK_SEC)
        for i in leaving:
            self._leave_spot(i)

    def _update_talk(self, name: str, members: list[int], t: float) -> None:
        """会話中の行き先の話し手を決め、話し手の身ぶりと、聞き手の姿勢と向きを決める。"""
        speaker = self._speakers.get(name)
        timer = self._speaker_timers.get(name, 0.0) - t
        if speaker is None or speaker not in members:
            speaker = self.rng.choice(members)
            timer = self.rng.uniform(SPEAKER_MIN_SEC, SPEAKER_MAX_SEC)
        elif timer <= 0.0:
            speaker = self.rng.choice([m for m in members if m != speaker])
            timer = self.rng.uniform(SPEAKER_MIN_SEC, SPEAKER_MAX_SEC)
        self._speakers[name] = speaker
        self._speaker_timers[name] = timer

        speaker_agent = self.agents[speaker]
        desk = self.layout.desks[0]
        for i in members:
            agent = self.agents[i]
            chat = self._chat[i]
            if i == speaker:
                others = [m for m in members if m != i]
                chat.gesture_timer -= t
                if (
                    chat.gesture == ""
                    or chat.gesture_timer <= 0.0
                    or chat.gesture_listener not in others
                ):
                    chat.gesture = self.rng.choice(GESTURE_KINDS)
                    chat.gesture_listener = self.rng.choice(others)
                    chat.gesture_timer = self.rng.uniform(GESTURE_MIN_SEC, GESTURE_MAX_SEC)
                agent.pose = gesture_pose(chat.gesture)
                if chat.gesture == GESTURE_POINT_DESK:
                    target_x, target_z = desk.x, desk.z  # メインの机を指す
                else:
                    listener = self.agents[chat.gesture_listener]
                    target_x, target_z = listener.pos.x, listener.pos.z
                agent.yaw = facing_yaw(agent.pos.x, agent.pos.z, target_x, target_z, default=agent.yaw)
            else:
                chat.gesture = ""
                chat.listen_timer -= t
                if chat.listen_timer <= 0.0:
                    chat.listen_drink = self.rng.random() < 0.5
                    chat.listen_timer = self.rng.uniform(LISTEN_MIN_SEC, LISTEN_MAX_SEC)
                agent.pose = drink_pose() if chat.listen_drink else stand_pose()
                agent.yaw = facing_yaw(
                    agent.pos.x,
                    agent.pos.z,
                    speaker_agent.pos.x,
                    speaker_agent.pos.z,
                    default=agent.yaw,
                )

    def _leave_spot(self, i: int) -> None:
        """行き先の予約を外し、席へ戻る道を探す。道が無ければあきらめて WANDER に戻る。"""
        if self.spot_manager is not None:
            self.spot_manager.release(i)
        self._chat[i] = Chatter()
        if not self.agents[i].begin_returning():
            self.stat_give_ups += 1

    def _is_held(self, i: int) -> bool:
        """人 i が会話の相手で、作業中ではないか（止めて動かさない人か）。作業中の相手は通常どおり動く。"""
        return i == self.talk_partner and self.agents[i].state != WORKING

    def _stationary_people(self) -> list[tuple[float, float]]:
        """座っている人と行き先の立つ場所にいる人の中心 (x, z) の列。人間の道探しで避ける人。"""
        return [(a.pos.x, a.pos.z) for a in self.agents if a.is_seated or a.state == AT_SPOT]

    def _overlaps_any_obstacle(self, x: float, z: float, margin: float = AGENT_RADIUS) -> bool:
        """点 (x, z) が、いずれかの障害物（長方形・丸）を margin だけ広げた範囲に入っていれば True。既定は AGENT_RADIUS。"""
        for ob in self.obstacles:
            r = ob.rect
            if (
                r.xmin - margin < x < r.xmax + margin
                and r.zmin - margin < z < r.zmax + margin
            ):
                return True
        for cx, cz, cr in self.circles:
            if math.hypot(x - cx, z - cz) < cr + margin:
                return True
        return False

    def _spot_free(self, x: float, z: float, partner: int | None = None) -> bool:
        """人間が立つ点 (x, z) が空いているか。うろつきの範囲の内側で、障害物（余白つき）に入らず、人から離れている。

        相手 partner 以外の人からは 2*AGENT_RADIUS + TALK_CLEAR 以上、相手からは 2*AGENT_RADIUS 以上離れていること。
        障害物は AGENT_RADIUS + TALK_CLEAR/2 だけ広げた範囲で見る。
        """
        x_min, x_max = self.layout.wander_x
        z_min, z_max = self.layout.wander_z
        if not (x_min <= x <= x_max and z_min <= z <= z_max):
            return False
        if self._overlaps_any_obstacle(x, z, AGENT_RADIUS + TALK_CLEAR / 2.0):
            return False
        for j, other in enumerate(self.agents):
            if not other.visible:
                continue
            need = 2.0 * AGENT_RADIUS if j == partner else 2.0 * AGENT_RADIUS + TALK_CLEAR
            if math.hypot(other.pos.x - x, other.pos.z - z) < need:
                return False
        return True

    def _talk_spot(self, i: int, with_desk: bool = True) -> tuple[float, float] | None:
        """相手 i と話すために人間が立つ位置 (x, z)。空いている最初の候補を返し、無ければ None。

        相手が作業中（座っている・席へ向かっている）で with_desk のときは、まず机の正面（席の反対側）を候補にする。
        そのあと、相手のまわり TALK_SIDE_DIST の TALK_DIRECTIONS 方向を、相手の正面に近い順に候補にする。
        """
        partner = self.agents[i]
        candidates: list[tuple[float, float]] = []
        if with_desk and partner.state == WORKING:
            desk = self.layout.desks[i]  # 席 i の机
            dx = desk.x - partner.seat.x
            dz = desk.z - partner.seat.z
            length = math.hypot(dx, dz)
            if length > 0.0:
                candidates.append(
                    (desk.x + dx / length * TALK_FRONT_GAP, desk.z + dz / length * TALK_FRONT_GAP)
                )
        # 相手の正面（yaw 0 で -Z）に近い方向から順に試す
        front_x = -math.sin(math.radians(partner.yaw))
        front_z = -math.cos(math.radians(partner.yaw))
        dirs: list[tuple[float, float, float]] = []  # (正面との内積, 方向の x, 方向の z)
        for k in range(TALK_DIRECTIONS):
            angle = 2.0 * math.pi * k / TALK_DIRECTIONS
            ux = math.sin(angle)
            uz = math.cos(angle)
            dirs.append((ux * front_x + uz * front_z, ux, uz))
        dirs.sort(key=lambda d: -d[0])
        for _, ux, uz in dirs:
            candidates.append(
                (partner.pos.x + ux * TALK_SIDE_DIST, partner.pos.z + uz * TALK_SIDE_DIST)
            )
        for x, z in candidates:
            if self._spot_free(x, z, partner=i):
                return (x, z)
        return None

    def handle_click(self, sx: int, sy: int) -> None:
        """画面の点 (sx, sy) をクリックしたときの処理（office だけ）。人を押せば会話を始め、床を押せばそこへ歩く。

        先に人を当て、当たらなければ床に当てる。会話中に別の人を押すと、今の会話を終えてから始める。
        """
        if not self.layout.has_props or self.human is None:
            return
        if sy >= VIEW3D_H:
            return  # 3D の範囲の外（履歴・入力欄）は3Dの処理をしない
        self.mode = MODE_WALK  # 3D をクリックしたら WALK に戻す（そのクリックは歩く・話しかける）
        self._reset_ime()
        eye, direction = self.screen_ray(sx, sy, 0, 0, OFFICE_SCREEN_W, VIEW3D_H)
        picked = self.pick_agent(eye, direction)
        if picked is not None:
            if picked == self.talk_partner:
                return  # 同じ人なら何もしない
            if self.talk_partner is not None:
                self.end_talk()
            self.start_talk(picked)
            return
        point = self.floor_hit(eye, direction)
        if point is None:
            return
        if self.talk_partner is not None:
            self.end_talk()
        x_min, x_max = self.layout.wander_x
        z_min, z_max = self.layout.wander_z
        x = _clamp(point[0], x_min, x_max)
        z = _clamp(point[1], z_min, z_max)
        self.human.walk_to(x, z, self._stationary_people())

    def screen_ray(
        self, sx: float, sy: float, vx: int, vy: int, vw: int, vh: int
    ) -> tuple[Vec3, Vec3]:
        """画面の点 (sx, sy) を通る3D の線（目の位置, 向きの単位ベクトル）を返す。

        描く範囲の左上が (vx, vy)、幅 vw・高さ vh。_apply_camera と同じ目の位置・向きを使い、fov は縦方向（度）。
        """
        eye = self.cam_target + self.cam_dir * self.cam_dist
        f = (self.cam_target - eye).normalize()
        r = f.cross(Vec3.UP).normalize()
        u = r.cross(f)
        k = math.tan(math.radians(self.camera.fov) / 2.0)
        aspect = vw / vh
        nx = 2.0 * (sx + 0.5 - vx) / vw - 1.0
        ny = 1.0 - 2.0 * (sy + 0.5 - vy) / vh
        direction = (f + r * (nx * k * aspect) + u * (ny * k)).normalize()
        return (eye, direction)

    def floor_hit(self, eye: Vec3, direction: Vec3) -> tuple[float, float] | None:
        """線と床（y=0）の交わる (x, z)。線が上を向いていれば None。"""
        if direction.y >= 0.0:
            return None
        t = -eye.y / direction.y
        return (eye.x + direction.x * t, eye.z + direction.z * t)

    def pick_agent(self, eye: Vec3, direction: Vec3) -> int | None:
        """線が当たるエージェントのうち、いちばん手前の人の番号。どれにも当たらなければ None。

        各人は中心 (x, PICK_CENTER_Y + body_y, z)・半径 PICK_RADIUS の球として調べる。direction は単位ベクトル。
        """
        best: int | None = None
        best_t = math.inf
        for i, agent in enumerate(self.agents):
            if not agent.visible:
                continue  # 見えていない人は選べない
            center = Vec3(agent.pos.x, PICK_CENTER_Y + agent.pose.body_y, agent.pos.z)
            oc = eye - center
            b = oc.dot(direction)
            c = oc.dot(oc) - PICK_RADIUS * PICK_RADIUS
            disc = b * b - c
            if disc < 0.0:
                continue
            root = math.sqrt(disc)
            t = -b - root  # 手前の交わり
            if t <= 0.0:
                t = -b + root  # 目が球の中にあるときは奥の交わり
            if t > 0.0 and t < best_t:
                best = i
                best_t = t
        return best

    def start_talk(self, i: int) -> None:
        """人 i と会話を始める（office だけ）。立つ位置が無ければ何もしない。会話のカメラへ切り替えを始める。"""
        if self.human is None:
            return
        self.human.stop()  # 歩いている途中なら止まる（立つ位置が無くても止まる）
        spot = self._talk_spot(i)
        if spot is None:
            return
        x, z = spot
        partner = self.agents[i]
        if self._saved_view is None:
            # 会話の前の視点を覚える。戻しの切り替え中（_saved_view が残っている）なら入れ直さない
            self._saved_view = (self.cam_yaw, self.cam_pitch, self.cam_dist)
        self.human.warp(x, z, facing_yaw(x, z, partner.pos.x, partner.pos.z, default=0.0))
        self.talk_partner = i
        partner.hold = True
        self._follow_replan = 0.0
        self._talk_seat_moved = partner.is_seated  # すでに座っていれば、座ってからの歩き直しは不要
        self._begin_blend(self._talk_view())

    def end_talk(self) -> None:
        """会話を終える（会話していなければ何もしない）。相手は動き出し、カメラは会話の前の視点へ戻す。"""
        if self.talk_partner is None:
            return
        self.agents[self.talk_partner].hold = False
        self.talk_partner = None
        self._follow_replan = 0.0
        if self.human is not None:
            self.human.stop()  # 会話中に相手について歩き直していた道を残さない（この後の walk_to は道を新しく作る）
            if self._saved_view is not None:
                yaw, pitch, dist = self._saved_view
                self._begin_blend((Vec3(self.human.pos.x, 0.0, self.human.pos.z), yaw, pitch, dist))

    def _talk_view(self) -> tuple[Vec3, float, float, float]:
        """会話のカメラの目標 (target, yaw, pitch, dist)。2人の真ん中を見る。2人を結ぶ線に直角な左右のうち、部屋の中に入るほうから見る。

        会話相手がいないとき（呼び出しの誤りに備えて）は、今のカメラの視点をそのまま返す。
        """
        if self.human is None or self.talk_partner is None:
            return (self.cam_target, self.cam_yaw, self.cam_pitch, self.cam_dist)
        human = self.human
        partner = self.agents[self.talk_partner]
        mx = (human.pos.x + partner.pos.x) / 2.0
        mz = (human.pos.z + partner.pos.z) / 2.0
        target = Vec3(mx, TALK_CAM_TARGET_Y, mz)
        lx = human.pos.x - partner.pos.x
        lz = human.pos.z - partner.pos.z
        gap = math.hypot(lx, lz)
        if gap > 0.0:
            ux = lx / gap
            uz = lz / gap
        else:
            ux, uz = 1.0, 0.0
        pitch = TALK_CAM_PITCH
        dist = max(TALK_CAM_MIN_DIST, gap * TALK_CAM_DIST_RATIO)
        horiz = dist * math.cos(math.radians(pitch))
        # 直角な2つの向き P1 と P2。目の位置は (mx, mz) + P * horiz
        dirs = ((-uz, ux), (uz, -ux))
        eyes = [(mx + px * horiz, mz + pz * horiz) for px, pz in dirs]
        inside = [
            self.layout.wander_x[0] <= ex <= self.layout.wander_x[1]
            and self.layout.wander_z[0] <= ez <= self.layout.wander_z[1]
            for ex, ez in eyes
        ]
        if inside[0] and not inside[1]:
            chosen = 0
        elif inside[1] and not inside[0]:
            chosen = 1
        elif inside[0] and inside[1] and abs(eyes[0][1] - eyes[1][1]) < 1.0:
            chosen = 0 if eyes[0][0] <= eyes[1][0] else 1
        else:
            # 両方入る（z の差が大きい）か、両方入らないときは、目の z が大きいほう（部屋の手前）
            chosen = 0 if eyes[0][1] >= eyes[1][1] else 1
        px, pz = dirs[chosen]
        yaw = math.degrees(math.atan2(px, pz)) % 360.0
        return self._nudge_talk_view((target, yaw, pitch, dist))

    def _nudge_talk_view(
        self, view: tuple[Vec3, float, float, float]
    ) -> tuple[Vec3, float, float, float]:
        """会話の視点で2人の頭の画面上の横の差が TALK_MIN_SCREEN_GAP 以上になるよう、yaw を TALK_YAW_OFFSETS の順にずらす。

        どれもだめなら、差がいちばん大きかった視点を使う（最初の視点を含む）。
        """
        target, yaw, pitch, dist = view
        best = view
        best_gap = self._head_screen_gap(view)
        if best_gap >= TALK_MIN_SCREEN_GAP:
            return view
        for offset in TALK_YAW_OFFSETS:
            candidate = (target, (yaw + offset) % 360.0, pitch, dist)
            gap = self._head_screen_gap(candidate)
            if gap >= TALK_MIN_SCREEN_GAP:
                return candidate
            if gap > best_gap:
                best = candidate
                best_gap = gap
        return best

    def _head_screen_gap(self, view: tuple[Vec3, float, float, float]) -> float:
        """視点 view から見た、2人の頭の画面上の横の差（画面の点）。どちらかが後ろなら 0。会話相手がいなければ 0。"""
        if self.human is None or self.talk_partner is None:
            return 0.0
        partner = self.agents[self.talk_partner]
        head_y = HEAD_CENTER.y
        human_xy = self.world_to_screen(
            Vec3(self.human.pos.x, head_y + self.human.pose.body_y, self.human.pos.z),
            0, 0, OFFICE_SCREEN_W, VIEW3D_H, view,
        )
        partner_xy = self.world_to_screen(
            Vec3(partner.pos.x, head_y + partner.pose.body_y, partner.pos.z),
            0, 0, OFFICE_SCREEN_W, VIEW3D_H, view,
        )
        if human_xy is None or partner_xy is None:
            return 0.0
        return abs(human_xy[0] - partner_xy[0])

    def world_to_screen(
        self,
        p: Vec3,
        vx: int,
        vy: int,
        vw: int,
        vh: int,
        view: tuple[Vec3, float, float, float] | None = None,
    ) -> tuple[float, float] | None:
        """3D の点 p の画面上の位置（screen_ray の逆）。カメラの後ろなら None。

        描く範囲は左上 (vx, vy)、幅 vw・高さ vh。view は (target, yaw, pitch, dist)。省略すると今のカメラを使う。
        目・向き・fov は screen_ray と同じ決まりに従う。
        """
        if view is None:
            target, yaw, pitch, dist = self.cam_target, self.cam_yaw, self.cam_pitch, self.cam_dist
        else:
            target, yaw, pitch, dist = view
        eye = target + _view_dir(yaw, pitch) * dist
        f = (target - eye).normalize()
        r = f.cross(Vec3.UP).normalize()
        u = r.cross(f)
        v = p - eye
        depth = v.dot(f)
        if depth <= 0.0:
            return None
        k = math.tan(math.radians(self.camera.fov) / 2.0)
        aspect = vw / vh
        nx = v.dot(r) / (depth * k * aspect)
        ny = v.dot(u) / (depth * k)
        return (vx + (nx + 1.0) * vw / 2.0 - 0.5, vy + (1.0 - ny) * vh / 2.0 - 0.5)

    def _begin_blend(self, to: tuple[Vec3, float, float, float]) -> None:
        """今のカメラ（target, yaw, pitch, dist）から to へ、CAM_BLEND_SEC かけて切り替えを始める。"""
        self._cam_from = (self.cam_target, self.cam_yaw, self.cam_pitch, self.cam_dist)
        self._cam_to = to
        self._cam_blend = 0.0

    def _update_partner(self, dt: float) -> None:
        """会話の相手の姿勢と向き、人間の向きと歩き直しを決める（office の会話中だけ）。

        相手が作業中でないとき：その場で立ち、人間を向く。
        相手が座っているとき：体は席の向きのまま、頭だけ人間を向く（HEAD_YAW_LIMIT まで）。座ったら机の正面へ1回だけ歩く。
        相手が席へ歩いているとき：FOLLOW_REPLAN_SEC ごとに、相手のまわりの立つ位置へ歩き直す。
        人間は止まっているとき、相手を向く。
        """
        i = self.talk_partner
        human = self.human
        if i is None or human is None:
            return
        partner = self.agents[i]
        if partner.state != WORKING:
            partner.pose = stand_pose()
            partner.yaw = facing_yaw(
                partner.pos.x, partner.pos.z, human.pos.x, human.pos.z, default=partner.yaw
            )
        elif partner.is_seated:
            if not self._talk_seat_moved:
                self._talk_seat_moved = True
                spot = self._talk_spot(i)
                if spot is not None:
                    human.walk_to(spot[0], spot[1], self._stationary_people())
            turn = (
                facing_yaw(partner.pos.x, partner.pos.z, human.pos.x, human.pos.z, default=partner.yaw)
                - partner.yaw
            )
            turn = (turn + 180.0) % 360.0 - 180.0  # -180〜180 に直す
            partner.pose.head_yaw = _clamp(turn, -HEAD_YAW_LIMIT, HEAD_YAW_LIMIT)
        else:
            self._follow_replan -= dt
            if self._follow_replan <= 0.0:
                self._follow_replan = FOLLOW_REPLAN_SEC
                spot = self._talk_spot(i, with_desk=False)
                if spot is not None:
                    human.walk_to(spot[0], spot[1], self._stationary_people())
        if not human.walking:
            human.yaw = facing_yaw(
                human.pos.x, human.pos.z, partner.pos.x, partner.pos.z, default=human.yaw
            )

    def _update_camera(self, dt: float) -> None:
        """人間がいる配置のカメラを毎フレーム決める（office だけ）。

        切り替え中は from から to へ smoothstep でなめらかにつなぐ。会話中は2人を映す視点、ふだんは人間を追う。
        会話中は目標を毎フレーム計算し直す。切り替えが終わって会話の前の視点に戻ったら、_saved_view を消す。
        """
        human = self.human
        if human is None:
            return
        talking = self.talk_partner is not None
        if self._cam_from is not None:
            if talking:
                self._cam_to = self._talk_view()
            self._cam_blend = min(1.0, self._cam_blend + dt / CAM_BLEND_SEC)
            b = self._cam_blend
            s = b * b * (3.0 - 2.0 * b)
            f_target, f_yaw, f_pitch, f_dist = self._cam_from
            t_target, t_yaw, t_pitch, t_dist = self._cam_to
            self.cam_target = f_target + (t_target - f_target) * s
            d_yaw = (t_yaw - f_yaw + 180.0) % 360.0 - 180.0  # 近いほうの回り方
            self.cam_yaw = (f_yaw + d_yaw * s) % 360.0
            self.cam_pitch = f_pitch + (t_pitch - f_pitch) * s
            self.cam_dist = f_dist + (t_dist - f_dist) * s
            if self._cam_blend >= 1.0:
                self._cam_from = None
                if not talking:
                    self._saved_view = None
        elif talking:
            target, yaw, pitch, dist = self._talk_view()
            self.cam_target = target
            self.cam_yaw = yaw
            self.cam_pitch = pitch
            self.cam_dist = dist
        else:
            goal = Vec3(human.pos.x, 0.0, human.pos.z)
            k = 1.0 - math.exp(-FOLLOW_RATE * dt)
            self.cam_target = self.cam_target + (goal - self.cam_target) * k
        self._apply_camera()

    def _record_frame(self) -> None:
        """直近約1秒のフレーム時刻から実測 FPS を求める。"""
        now = time.perf_counter()
        self._frame_times.append(now)
        while now - self._frame_times[0] > 1.0:
            self._frame_times.popleft()

        if len(self._frame_times) >= 2:
            span = self._frame_times[-1] - self._frame_times[0]
            if span > 0.0:
                self.measured_fps = (len(self._frame_times) - 1) / span

    def _view_rect(self) -> tuple[int, int, int, int]:
        """3D を描く範囲 (x, y, 幅, 高さ)。office は (0, 0, 640, 296)、proto は画面全体。"""
        if self.layout.has_props:
            return (0, 0, OFFICE_SCREEN_W, VIEW3D_H)
        return (0, 0, pyxel.width, pyxel.height)

    def _in_rect(self, sx: float, sy: float, x: int, y: int, w: int, h: int) -> bool:
        """画面の点 (sx, sy) が長方形 (x, y, w, h) の中か。"""
        return x <= sx < x + w and y <= sy < y + h

    def _wheel_zooms(self, sx: float, sy: float) -> bool:
        """ホイールで3Dを寄せ引きする位置か。proto は画面全体、office は 3D の範囲の上だけ。"""
        if not self.layout.has_props:
            return True
        return sy < VIEW3D_H

    def _max_scroll(self) -> int:
        """履歴の一番上の行の番号の上限（最後の HISTORY_ROWS 行が見えるところ）。"""
        return max(0, len(self.history) - HISTORY_ROWS)

    def _scroll_track(self) -> tuple[int, int, int, int]:
        """履歴のスクロールバーの溝 (x, y, 幅, 高さ)。枠の右端の内側に置く。"""
        return (
            HISTORY_X + HISTORY_W - 2 - SCROLLBAR_W,
            HISTORY_Y + 2,
            SCROLLBAR_W,
            HISTORY_H - 4,
        )

    def _on_left_click(self, sx: int, sy: int) -> None:
        """左クリックの処理。office は入力欄なら PROMPT、履歴の枠ならスクロールバー、3D の範囲なら歩く・話しかける。"""
        if not self.layout.has_props:
            self.handle_click(sx, sy)
            return
        if self._claude_click(sx, sy):
            return  # 始業・終業のボタン、ダイアログ（--claude のとき）
        talk_partner = self._talk_dialog_partner()
        if talk_partner is not None and self._in_rect(sx, sy, DLG_X, DLG_Y, DLG_W, DLG_H):
            self._click_talk_dialog(talk_partner, sx, sy)
            return  # 会話のダイアログの上のクリックは、床のクリック（歩く・会話を終える）にしない
        if self._in_rect(sx, sy, HISTORY_X, INPUT_Y, HISTORY_W, INPUT_H):
            self.mode = MODE_PROMPT  # モードは変えるが、履歴は変えない
            return
        if self._in_rect(sx, sy, HISTORY_X, HISTORY_Y, HISTORY_W, HISTORY_H):
            tx, ty, tw, th = self._scroll_track()
            total = len(self.history)
            if total > HISTORY_ROWS and self._in_rect(sx, sy, tx, ty, tw, th):
                # 溝をクリックした位置へ飛ぶ
                frac = _clamp((sy - ty) / th, 0.0, 1.0)
                self.history_scroll = min(self._max_scroll(), int(frac * (total - HISTORY_ROWS)))
            return
        self.handle_click(sx, sy)

    def _add_history(self, text: str) -> None:
        """履歴の末尾に text を桁数で折り返して足す。"""
        self._append_history_rows(_wrap_text(text, UI_COLS, self.ui_codes))

    def _append_history_rows(self, rows: list[str], color: int = TEXT_COLOR) -> None:
        """履歴の末尾に行を足す（行ごとの色は color）。上限を超えたら古い行から捨て、一番下まで見せる。"""
        self.history.extend(rows)
        self.history_color.extend([color] * len(rows))
        excess = len(self.history) - HISTORY_MAX
        if excess > 0:
            del self.history[:excess]
            del self.history_color[:excess]
        self.history_scroll = self._max_scroll()

    def _ui(self, text: str) -> str:
        """UI フォントで描く前に通す。フォントに無い字を形の似た字にする（記録の文字は変えない）。"""
        return font_safe(text, self.ui_codes)

    def _draw_ui(self) -> None:
        """office の下の履歴・スクロールバー・入力欄を描く（文字は UI フォント）。"""
        font = self.ui_font
        pyxel.rect(0, VIEW3D_H, OFFICE_SCREEN_W, OFFICE_SCREEN_H - VIEW3D_H, 0)
        # 履歴の枠と行
        pyxel.rectb(HISTORY_X, HISTORY_Y, HISTORY_W, HISTORY_H, 5)
        visible = slice(self.history_scroll, self.history_scroll + HISTORY_ROWS)
        for row_no, (row, row_color) in enumerate(
            zip(self.history[visible], self.history_color[visible])
        ):
            pyxel.text(
                HISTORY_X + UI_PAD, HISTORY_Y + UI_PAD + row_no * UI_LINE_H, self._ui(row), row_color, font
            )
        total = len(self.history)
        if total > HISTORY_ROWS:
            tx, ty, tw, th = self._scroll_track()
            pyxel.rect(tx, ty, tw, th, 1)  # 溝
            thumb_h = max(6, int(th * HISTORY_ROWS / total))  # つまみの長さは見えている割合
            thumb_y = ty + int((th - thumb_h) * self.history_scroll / (total - HISTORY_ROWS))
            pyxel.rect(tx, thumb_y, tw, thumb_h, TEXT_COLOR)
        # 入力欄の枠と文字（PROMPT のときは黄色の枠と点滅するカーソル）
        prompting = self._prompting()
        pyxel.rectb(HISTORY_X, INPUT_Y, HISTORY_W, INPUT_H, 10 if prompting else 5)
        # 日本語入力の札：入力欄の枠の左上の内側。文字は札の幅のぶん右から書く
        if font is not None:
            badge_w = font.text_width("あ") + 4
            badge_bg = {"あ": 8, "A": 3}.get(self.ime_state, 5)
            pyxel.rect(HISTORY_X + 4, INPUT_Y + 4, badge_w, UI_LINE_H, badge_bg)
            pyxel.text(HISTORY_X + 6, INPUT_Y + 5, self._ui(self.ime_state), TEXT_COLOR, font)
        # 入力欄の文字は描くときだけ置き換える（input_buf は変えない。カーソルは置き換えたあとの行の末尾）
        shown = self.input_buf
        if prompting and (pyxel.frame_count // 15) % 2 == 0:
            shown += "_"
        for row_no, row in enumerate(self._input_rows(shown)):
            pyxel.text(
                self._input_text_x(), INPUT_Y + UI_PAD + row_no * UI_LINE_H, self._ui(row), TEXT_COLOR, font
            )
        if self.claude:
            # いちばん下の行は、今のモデルと effort（灰色）
            status = self._ui(t("status_model", model=self._cur_model, effort=self._cur_effort))
            pyxel.text(
                self._input_text_x(), INPUT_Y + UI_PAD + INPUT_TEXT_ROWS_CLAUDE * UI_LINE_H, status, 13, font
            )
        if self.ime_composing and font is not None:
            # 変換中の札は、入力欄の枠の上の線の右端に重ねる（札の下半分が枠の線にかかる）
            label = self._ui(t("ime_converting"))
            box_w = font.text_width(label) + 4
            box_x, box_y = self._composing_label_pos(box_w)
            pyxel.rect(box_x, box_y, box_w, UI_LINE_H, 8)
            pyxel.text(box_x + 2, box_y + 1, label, TEXT_COLOR, font)

    def _composing_label_pos(self, box_w: int) -> tuple[int, int]:
        """「変換中」の札の左上 (x, y)。右端は x=620（スクロールバーの溝より左）、上端は履歴の枠の下の線（y=438）より下。

        入力欄の上の線（INPUT_Y）に重なる。入力欄の文字は、この札の左側までで折り返す（_input_cols）。
        """
        box_x = COMPOSING_LABEL_RIGHT - box_w
        box_y = HISTORY_Y + HISTORY_H + 1
        return (box_x, box_y)

    def _input_text_x(self) -> int:
        """入力欄の文字を書き始める x。日本語入力の札の幅のぶん右から。"""
        font = self.ui_font
        badge_w = (font.text_width("あ") if font is not None else UI_CHAR_W * 2) + 4
        return HISTORY_X + 4 + badge_w + 4

    def _input_cols(self) -> int:
        """入力欄の1行の桁数。日本語入力の札のぶん、また「変換中」の札の左側までの分だけ、文字の領域が狭くなる。"""
        font = self.ui_font
        label_w = (font.text_width(t("ime_converting")) if font is not None else UI_CHAR_W * 6) + 4
        right = COMPOSING_LABEL_RIGHT - label_w - 4  # 札の左端より手前まで
        return (right - self._input_text_x()) // UI_CHAR_W

    def _input_text_rows(self) -> int:
        """入力の文字を見せる行数。--claude のときはいちばん下の行を状態の行にするので、1行少ない。"""
        return INPUT_TEXT_ROWS_CLAUDE if self.claude else INPUT_ROWS

    def _input_rows(self, text: str) -> list[str]:
        """入力中の文字を改行で行を分け、それぞれを桁数で折り返した、最後の入力の行数ぶん（_input_text_rows）。"""
        rows: list[str] = []
        for line in text.split("\n"):
            rows.extend(_wrap_text(line, self._input_cols(), self.ui_codes))
        return rows[-self._input_text_rows() :]

    def _splash_skip_pressed(self) -> bool:
        """このフレームに、スプラッシュを飛ばすキーかマウスの左クリックが押されたか。"""
        return pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) or any(pyxel.btnp(key) for key in SPLASH_SKIP_KEYS)

    def draw(self) -> None:
        """3D を描いたあと、2D の文字を重ねる。office は下に履歴と入力欄も描く。"""
        if self.splash is not None and not self.splash.finished:
            self.splash.draw()
            return
        vx, vy, vw, vh = self._view_rect()
        self.scene.draw(vx, vy, vw, vh)

        # デバッグ用の左上の表示（FPS・人数・TALK）は、試作の配置（proto）だけ出す。office（製品版）では出さない
        if not self.layout.has_props:
            pyxel.text(4, 4, f"FPS {self.measured_fps:.1f} / {self.fps}", TEXT_COLOR)
            # 人数が多いと画面からはみ出すので、6人を超えたら人数だけ出す
            if len(self.agents) <= 6:
                for i, agent in enumerate(self.agents):
                    pyxel.text(4, 14 + i * 8, f"{agent.name}:{agent.state}", TEXT_COLOR)
                count_lines = len(self.agents)
            else:
                pyxel.text(4, 14, f"AGENTS {len(self.agents)}", TEXT_COLOR)
                count_lines = 1
            if self.talk_partner is not None:
                # 会話中は人数表示の下に、相手の名前を出す
                partner = self.agents[self.talk_partner]
                pyxel.text(4, 14 + count_lines * 8, f"TALK:{partner.name}", TEXT_COLOR)
        if self.layout.has_props:
            # 上の真ん中に、MODE 表示と操作の案内を1つの黒い四角の中に出す（横の真ん中）
            prompting = self._prompting()
            if self._menu is not None:
                mode_part = "MODE: MENU"  # 選ぶメニューの間
                hint_part = "  (ESC:CLOSE)"
            elif self._slash_open:
                mode_part = "MODE: SLASH"  # コマンドの窓の間は、モードの札を SLASH にする（モードの中身は PROMPT のまま）
                hint_part = "  (ESC:CLOSE)"
            else:
                mode_part = f"MODE: {self.mode}"
                hint_part = (
                    "  (CTRL+E:WALK ESC:CANCEL ENTER:SEND)" if prompting else "  (P:PROMPT)"
                )
            total_w = (len(mode_part) + len(hint_part)) * pyxel.FONT_WIDTH
            label_x = (OFFICE_SCREEN_W - total_w) // 2
            # 文字の後ろに黒い四角を先に塗る（上下左右 2 点ずつの余白）
            pyxel.rect(label_x - 2, 2, total_w + 4, pyxel.FONT_HEIGHT + 4, 0)
            pyxel.text(label_x, 4, mode_part, 10 if prompting else TEXT_COLOR)
            pyxel.text(
                label_x + len(mode_part) * pyxel.FONT_WIDTH, 4, hint_part, 6
            )
            if self.claude:
                self._draw_claude()
            self._draw_ui()
        else:
            pyxel.text(4, pyxel.height - 10, "SPACE:WORK WHEEL:ZOOM ARROWS:VIEW", TEXT_COLOR)

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数を解釈する。先に --lang だけを読んで言語を決め、--help の文もその言語で出す。"""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang", choices=LANGS, default=None)
    pre_args, _ = pre.parse_known_args(argv)
    set_lang(pre_args.lang or detect_lang())
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument("--lang", choices=LANGS, default=get_lang(), help=t("arg_lang"))
    parser.add_argument("--fps", type=int, default=30, help=t("arg_fps"))
    parser.add_argument("--seed", type=int, default=None, help=t("arg_seed"))
    parser.add_argument(
        "--layout",
        choices=("proto", "office"),
        default="office",
        help=t("arg_layout"),
    )
    parser.add_argument(
        "--agents", type=int, default=18, help=t("arg_agents")
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help=t("arg_config"),
    )
    parser.add_argument(
        "--time-scale",
        type=float,
        default=DEFAULT_TIME_SCALE,
        help=t("arg_speed"),
    )
    parser.add_argument(
        "--claude",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=t("arg_claude"),
    )
    parser.add_argument(
        "--workdir",
        type=str,
        default=None,
        help=t("arg_workdir"),
    )
    parser.add_argument(
        "--session",
        type=str,
        default="pyxelcube_agents",
        help=t("arg_session"),
    )
    args = parser.parse_args(argv)
    if args.claude is None:
        # 付けていなければ、office ではつなぐ（proto ではつながない）
        args.claude = args.layout == "office"
    elif args.claude and args.layout != "office":
        parser.error(t("err_claude_needs_office"))
    return args


def main() -> None:
    """引数を解釈してアプリを作り、Pyxel のループを開始する。"""
    args = parse_args()
    app = App(
        args.fps,
        args.seed,
        args.layout,
        args.agents,
        config_path=args.config,
        time_scale=args.time_scale,
        claude=args.claude,
        workdir=str(Path(args.workdir).expanduser()) if args.workdir is not None else None,
        session=args.session,
        splash=True,
    )
    pyxel.run(app.update, app.draw)


if __name__ == "__main__":
    main()
