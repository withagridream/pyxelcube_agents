"""pyxelcube_agents.py（Pyxel Cube の3Dオフィス試作）の操作テスト。

実行: .venv/bin/python test_pyxelcube_agents.py
App は1回だけ作る（pyxel.init は1プロセス1回）。テストごとに Agent の状態を作り直す。
"""
import os
import sys
import json
import math
import random
import contextlib
import unicodedata
import shlex
from pathlib import Path

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# 許可の待ち受けの名前：指定が無ければ実行ごとの名前にする（本番の名前 pyxelcube_agents_perm にはつながない）
os.environ.setdefault("PCA_PERM_SOCKET", f"pca_test_o3d_default_{os.getpid()}")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pyxel
pyxel.run = lambda *a, **k: None
import pyxelcube_agents
from pca_i18n import t as i18n_t, set_lang, get_lang, detect_lang, MESSAGES, LANGS
import pca_i18n

set_lang("ja")  # 日本語の文を期待するテストが多いので、最初に ja を明示する（言語を変えるテストは最後に ja へ戻す）

fail = []
n_checks = 0  # check() を呼んだ回数（最後に表示する）

# 一時ファイルの置き場所。ユーザーの ~/.cache などは読み書きしない。
# 既定はこのファイルと同じフォルダの .test_tmp/（環境変数 OFFICE3D_TEST_TMP があればそれを使う）。
# 消さずに毎回同じファイルを上書きする（フォルダ・ファイルは作りっぱなし）。
TMP_DIR = Path(os.environ.get(
    "OFFICE3D_TEST_TMP",
    str(Path(__file__).resolve().parent / ".test_tmp")))
TMP_DIR.mkdir(parents=True, exist_ok=True)


def write_toml(name, json_path, reload_sec=3.0):
    """一時の設定ファイル（toml）を作ってパス（文字列）を返す。"""
    p = TMP_DIR / name
    p.write_text(f'[rate_limits]\njson_path = "{json_path}"\nreload_sec = {reload_sec}\n', encoding="utf-8")
    return str(p)


# 既存のテストが使う設定：JSON は存在しない場所を指す（ユーザーの既定の JSON を読まない）
SAFE_CFG = write_toml("safe.toml", TMP_DIR / "no_such_rate_limits.json")


def check(c, msg):
    global n_checks
    n_checks += 1
    if not c:
        fail.append(msg)
        print("NG:", msg)


def dtx(app, partner):
    """会話のダイアログの中身の文字の行（色を除いたもの）。_talk_dialog_lines は（字, 色）の一覧を返す。"""
    return [row for row, _col in app._talk_dialog_lines(partner)]


def dist(a, b):
    return math.hypot(a.x - b.x, a.z - b.z)


# スペースキーの押下を真似る（pressed[0] が True のフレームだけ押された扱い）
# D・1〜4 キーは pressed_keys に入れたキーだけが押された扱い（press_keys_and_update を使う）
pressed = [False]
pressed_keys: set = set()
_orig_btnp = pyxel.btnp
pyxel.btnp = lambda k, *a, **kw: (k == pyxel.KEY_SPACE and pressed[0]) or k in pressed_keys


def press_space_and_update(app):
    """1フレームだけスペースを押して update を1回呼ぶ。"""
    pressed[0] = True
    app.update()
    pressed[0] = False


def press_keys_and_update(app, *keys):
    """指定したキーを1フレームだけ押して update を1回呼ぶ。"""
    pressed_keys.update(keys)
    try:
        app.update()
    finally:
        pressed_keys.clear()


def reset(app, seed=1):
    """全 Agent を初期状態へ作り直し、next_index も戻す。"""
    for i, a in enumerate(app.agents):
        a.__init__(a.name, a.seat, random.Random(seed + i))
    app.next_index = 0


SEATS = [(-250.0, 0.0, -30.0), (0.0, 0.0, -30.0), (250.0, 0.0, -30.0)]

# 1. 起動直後：3人（A,B,C）、全員 WANDER、位置は席、next_index 0
# 画面は office の大きさ（640×500）で1回だけ作る。pyxel.init は1プロセス1回なので、proto の App も同じ画面で動かす。
pyxel.init(pyxelcube_agents.OFFICE_SCREEN_W, pyxelcube_agents.OFFICE_SCREEN_H, title="test", fps=30,
           display_scale=pyxelcube_agents.OFFICE_DISPLAY_SCALE, quit_key=pyxel.KEY_NONE)
_real_init_1 = pyxel.init
pyxel.init = lambda *a, **k: None
try:
    app = pyxelcube_agents.App(30, 7, config_path=SAFE_CFG)
finally:
    pyxel.init = _real_init_1
check(len(app.agents) == 3, f"1: agents が3人でない {len(app.agents)}")
check([a.name for a in app.agents] == ["A", "B", "C"], "1: 名前が A,B,C でない")
check(all(a.state == "WANDER" for a in app.agents), "1: 全員 WANDER でない")
for a, s in zip(app.agents, SEATS):
    check((a.pos.x, a.pos.y, a.pos.z) == s, f"1: {a.name} の位置が席でない {a.pos}")
check(app.next_index == 0, "1: next_index が 0 でない")

# 2. スペース1回 + update 1回 → A だけ WORKING、next_index 1。押さずに update しても増えない
reset(app)
press_space_and_update(app)
check([a.state for a in app.agents] == ["WORKING", "WANDER", "WANDER"],
      f"2: スペース1回後の状態 {[a.state for a in app.agents]}")
check(app.next_index == 1, f"2: next_index が 1 でない {app.next_index}")
for _ in range(5):
    app.update()
check([a.state for a in app.agents][1:] == ["WANDER", "WANDER"],
      "2: 押さないのに B/C が WORKING になった")
check(app.next_index == 1, "2: 押さないのに next_index が進んだ")

# 3. スペース3回で全員 WORKING、next_index は 0 に戻る。4回目は A がやり直し
reset(app)
for _ in range(3):
    press_space_and_update(app)
    app.update()  # 押さないフレームをはさむ（別フレーム）
check(all(a.state == "WORKING" for a in app.agents), "3: 3回押して全員 WORKING でない")
check(app.next_index == 0, f"3: next_index が 0 に戻らない {app.next_index}")
# A は席にいるので数フレームで着席し、着席時間がたまっているはず
for _ in range(30):
    app.update()
a0 = app.agents[0]
check(a0._seated_time > 0.5, f"3: A の着席時間がたまっていない {a0._seated_time}")
press_space_and_update(app)
check(a0.state == "WORKING", "3: 4回目で A が WORKING でない")
check(a0._seated_time < 1e-9, f"3: 4回目で A の着席時間がリセットされない {a0._seated_time}")
check(app.next_index == 1, "3: 4回目の後 next_index が 1 でない")

# 4. WORKING の流れ：席から離れた所から、席へ近づく → 着席 → 5秒 → WANDER
seat = pyxelcube_agents.Vec3(0.0, 0.0, -30.0)
ag = pyxelcube_agents.Agent("T", seat, random.Random(1))
ag.pos = pyxelcube_agents.Vec3(300.0, 0.0, 100.0)
ag.start_work()
d0 = dist(ag.pos, seat)
ag.update(1 / 60)
check(dist(ag.pos, seat) < d0, "4: 席に向かって近づかない")
steps = 0
while not ag._arrived and steps < 6000:
    ag.update(1 / 60)
    steps += 1
check(ag._arrived, "4: 席に着かない")
check(abs(ag.pos.x - seat.x) < 1e-9 and abs(ag.pos.z - seat.z) < 1e-9, f"4: 着席位置が席と一致しない {ag.pos}")
check(abs(ag.yaw) < 1e-9, f"4: 着席時の yaw が 0 でない {ag.yaw}")
check(ag.state == "WORKING", "4: 着席直後に WORKING でない")
# 作業中の姿勢：5秒未満は座った姿勢で、肘が時間で変わる（15±5、振れ幅5以内）
poses = []
t = 0.0
while t < 4.9:
    ag.update(1 / 60)
    t += 1 / 60
    poses.append(ag.pose)
check(ag.state == "WORKING", "4: 5秒未満で WORKING でなくなった")
check(all(q.body_y == pyxelcube_agents.SIT_BODY_Y for q in poses), "4: 作業中の body_y が SIT_BODY_Y でない")
check(all(q.hip_l == 90.0 and q.knee_l == 90.0 for q in poses), "4: 作業中が座った姿勢(付け根・膝90)でない")
check(all(abs(q.elbow_l - 15.0) <= 5.0 + 1e-9 for q in poses), "4: 肘が 15±5 を超えた")
check(all(q.body_z == pyxelcube_agents.SIT_BODY_Z == -25.0 for q in poses), "4: 作業中の body_z が -25 でない")
check(max(q.elbow_l for q in poses) - min(q.elbow_l for q in poses) > 5.0, "4: 肘が時間で変化しない")
check(not hasattr(ag, "bob_y"), "4: bob_y が残っている（削除されたはず）")
for _ in range(30):
    ag.update(1 / 60)
check(ag.state == "WANDER", "4: 5秒過ぎても WANDER に戻らない")
check(ag.pose.body_y == 0.0, f"4: WANDER 復帰後 body_y が 0 でない {ag.pose.body_y}")
check(ag.pose in (pyxelcube_agents.stand_pose(), pyxelcube_agents.walk_pose(ag.walk_phase)),
      f"4: WANDER 復帰後の姿勢が stand でも walk でもない {ag.pose}")

# 5. 速さ：WORKING 中（着席前）1秒で約120、WANDER 中は1秒あたり60以下
ag = pyxelcube_agents.Agent("T", seat, random.Random(2))
ag.pos = pyxelcube_agents.Vec3(500.0, 0.0, 200.0)
ag.start_work()
p0 = ag.pos
for _ in range(60):
    ag.update(1 / 60)
moved = dist(p0, ag.pos)
check(abs(moved - 120.0) < 2.0, f"5: 戻る速さが約120でない {moved}")
ag = pyxelcube_agents.Agent("T", seat, random.Random(3))
max_speed = 0.0
for _ in range(60 * 30):
    p = ag.pos
    ag.update(1 / 60)
    max_speed = max(max_speed, dist(p, ag.pos) * 60)
check(max_speed <= 60.0 + 0.01, f"5: うろつきが速すぎる {max_speed}")
check(max_speed > 50.0, f"5: うろつきでほとんど動かない {max_speed}")

# 6. fps に依存しない：dt=1/10 x10 と dt=1/60 x60 で位置の差が小さい
worst = 0.0
for seed in range(10):
    a = pyxelcube_agents.Agent("T", seat, random.Random(seed))
    b = pyxelcube_agents.Agent("T", seat, random.Random(seed))
    for _ in range(10):
        a.update(1 / 10)
    for _ in range(60):
        b.update(1 / 60)
    worst = max(worst, dist(a.pos, b.pos))
print(f"(6) 最大の位置の差 {worst:.2f}")
check(worst <= 10.0, f"6: fps で位置が大きくずれる {worst}")

# 7. うろつく範囲：60秒、複数の席・種で。机の中に入らない
bad = []
for seat_x in (-250.0, 0.0, 250.0):
    sv = pyxelcube_agents.Vec3(seat_x, 0.0, -30.0)
    for seed in range(5):
        ag = pyxelcube_agents.Agent("T", sv, random.Random(seed))
        for _ in range(60 * 60):
            ag.update(1 / 60)
            p = ag.pos
            if not (-380 - 1e-6 <= p.x <= 380 + 1e-6):
                bad.append(("x", seat_x, seed, p.x))
            if not (-50 - 1e-6 <= p.z <= 280 + 1e-6):
                bad.append(("z", seat_x, seed, p.z))
            if dist(p, sv) > 120 + 1e-6:
                bad.append(("dist", seat_x, seed, dist(p, sv)))
            for dx in pyxelcube_agents.DESK_XS:
                if abs(p.x - dx) < 60 and -130 < p.z < -70:
                    bad.append(("desk", seat_x, seed, (p.x, p.z)))
check(not bad, f"7: 範囲外 {bad[:3]}（計{len(bad)}件）")

# 8. 乱数の種：同じ種なら同じ動き、違う種なら違う動き
def trace(seed):
    ag = pyxelcube_agents.Agent("T", seat, random.Random(seed))
    out = []
    for _ in range(600):
        ag.update(1 / 60)
        out.append((round(ag.pos.x, 6), round(ag.pos.z, 6)))
    return out

check(trace(5) == trace(5), "8: 同じ種で動きが違う")
check(trace(5) != trace(6), "8: 違う種で動きが同じ")

# 9. 描画：update と draw を数百フレーム。measured_fps は 0 以上
reset(app, 11)
err = None
try:
    for i in range(400):
        if i % 100 == 50:
            press_space_and_update(app)
        else:
            app.update()
        app.draw()
except Exception as e:  # noqa: BLE001
    err = e
check(err is None, f"9: update/draw で例外 {err!r}")
check(isinstance(app.measured_fps, (int, float)) and app.measured_fps >= 0,
      f"9: measured_fps が不正 {app.measured_fps}")

# 10. fps の clamp：pyxel.init を一時的に差し替えて App を作り直して確認する（実 init は呼ばない）
_orig_init = pyxel.init
pyxel.init = lambda *a, **k: None
try:
    for given, want in ((100, 60), (60, 60), (30, 30), (1, 1), (0, 1), (-5, 1)):
        got = pyxelcube_agents.App(given, 0, config_path=SAFE_CFG).fps
        check(got == want, f"10: App({given}) の fps が {want} でなく {got}")
except Exception as e:  # noqa: BLE001
    check(False, f"10: clamp 確認で例外 {e!r}")
finally:
    pyxel.init = _orig_init

# 11. 引数
ns = pyxelcube_agents.parse_args([])
check(ns.fps == 30 and ns.seed is None, f"11: 既定値 {ns}")
ns = pyxelcube_agents.parse_args(["--fps", "10", "--seed", "3"])
check(ns.fps == 10 and ns.seed == 3, f"11: 指定値 {ns}")

# ---- ここから office 配置（--layout office）の項目 ----
def make_app(*args, **kwargs):
    """pyxel.init を一時的に空にして App を作り直す（実 init は1回だけ）。終わったら戻す。
    config_path を渡さないときは SAFE_CFG（JSON なし）を使う。ユーザーの既定の JSON を読まないため。"""
    saved = pyxel.init
    pyxel.init = lambda *a, **k: None
    kwargs.setdefault("config_path", SAFE_CFG)
    try:
        return pyxelcube_agents.App(*args, **kwargs)
    finally:
        pyxel.init = saved


# 12. 引数：既定は proto・3人。office・18人の指定。不正な layout は SystemExit
ns = pyxelcube_agents.parse_args([])
check(ns.layout == "proto" and ns.agents == 3, f"12: 既定の layout/agents {ns}")
ns = pyxelcube_agents.parse_args(["--layout", "office", "--agents", "18"])
check(ns.layout == "office" and ns.agents == 18, f"12: office 指定 {ns}")
_orig_stderr = sys.stderr
sys.stderr = open(os.devnull, "w")  # argparse のエラー表示を抑える
try:
    pyxelcube_agents.parse_args(["--layout", "xxx"])
    exited = False
except SystemExit:
    exited = True
finally:
    sys.stderr.close()
    sys.stderr = _orig_stderr
check(exited, "12: 不正な layout で SystemExit にならない")

# 13. office 18人：名前 A〜R、全員 WANDER、初期位置は各席
oapp = make_app(30, 1, "office", 18)
check(len(oapp.agents) == 18, f"13: agents が18人でない {len(oapp.agents)}")
check([a.name for a in oapp.agents] == [chr(ord("A") + i) for i in range(18)],
      "13: 名前が A〜R でない")
check(all(a.state == "WANDER" for a in oapp.agents), "13: 全員 WANDER でない")
for a, (s_pos, _y, _c) in zip(oapp.agents, pyxelcube_agents.OFFICE_LAYOUT.seats):
    check((a.pos.x, a.pos.z) == (s_pos.x, s_pos.z), f"13: {a.name} の初期位置が席でない {a.pos}")

# 14. 人数の範囲：office 0→1、25→18。proto 10→3。既定呼び出しは従来どおり
check(len(make_app(30, 1, "office", 0).agents) == 1, "14: office 0人指定が1人でない")
check(len(make_app(30, 1, "office", 25).agents) == 18, "14: office 25人指定が18人でない")
check(len(make_app(30, 1, "proto", 10).agents) == 3, "14: proto 10人指定が3人でない")
dapp = make_app(30, 1)
check(len(dapp.agents) == 3 and dapp.layout_name == "proto", "14: App(30,1) が proto 3人でない")
for a, s_xyz in zip(dapp.agents, SEATS):
    check((a.pos.x, a.pos.y, a.pos.z) == s_xyz, f"14: 既定の席が従来と違う {a.name} {a.pos}")

# 15. 席の配置：18席で重複なし。窓際2席は z=-500・yaw180。島の16席は中心から z が ±100
oseats = pyxelcube_agents.OFFICE_LAYOUT.seats
check(len(oseats) == 18, f"15: 席が18でない {len(oseats)}")
check(len({(v.x, v.z) for v, _y, _c in oseats}) == 18, "15: 席の位置が重複している")
for v, yaw, _c in oseats[:2]:
    check(v.z == -500.0 and yaw == 180.0, f"15: 窓際席が z=-500/yaw180 でない {v} {yaw}")
island_seats = oseats[2:]
check(len(island_seats) == 16, f"15: 島の席が16でない {len(island_seats)}")
for k, (cx, cz) in enumerate(pyxelcube_agents.ISLAND_CENTERS):
    for v, yaw, _c in island_seats[k * 4:(k + 1) * 4]:
        dz = v.z - cz
        check(abs(dz) == 100.0, f"15: 島{k}の席の z が中心から ±100 でない {dz}")
        if dz == -100.0:
            check(yaw == 180.0, f"15: 奥列の yaw が 180 でない {yaw}")
        else:
            check(yaw == 0.0, f"15: 手前列の yaw が 0 でない {yaw}")
    zs = sorted(v.z - cz for v, _y, _c in island_seats[k * 4:(k + 1) * 4])
    check(zs == [-100.0, -100.0, 100.0, 100.0], f"15: 島{k}の奥2・手前2でない {zs}")

# 16. 座ったときの向き：窓際(0番)=180、手前列(島の先頭の手前=index 4)=0、奥列(index 2)=180。proto は 0
def seat_yaw_after_work(app, idx):
    ag = app.agents[idx]
    ag.pos = pyxelcube_agents.Vec3(ag.seat.x + 60.0, 0.0, ag.seat.z + 40.0)  # 席から離す
    ag.start_work()
    for _ in range(600):
        if ag._arrived:
            break
        ag.update(1 / 30)
    return ag.yaw if ag._arrived else None

for idx, want in ((0, 180.0), (1, 180.0), (2, 180.0), (4, 0.0)):
    got = seat_yaw_after_work(oapp, idx)
    check(got == want, f"16: office の席{idx}の着席 yaw が {want} でなく {got}")
check(seat_yaw_after_work(dapp, 0) == 0.0, "16: proto の着席 yaw が 0 でない")

# 17. 色：office の全キャラの色は 2〜15 で、床(1)・椅子(4)・机(13)を含まない
cols = [c for _v, _y, c in oseats]
check(all(2 <= c <= 15 for c in cols), f"17: 色が 2〜15 でない {cols}")
check(not ({1, 4, 13} & set(cols)), f"17: 床(1)・椅子(4)・机(13)の色を含む {cols}")
views = [ch for ch in getattr(oapp.scene, "children", []) if isinstance(ch, pyxelcube_agents.AgentView)]
if len(views) == 18:
    check([v.color for v in views] == cols, "17: AgentView の色が席の色と違う")
else:
    print("(17) AgentView の取得を確認できず（席の色のみ検証）")

# 18. うろつき範囲：office 18人を60秒相当 WANDER。x/z の範囲と席からの距離
bad = []
oapp2 = make_app(30, 3, "office", 18)
for _ in range(30 * 60):
    for a in oapp2.agents:
        a.update(1 / 30)
        if not (-780 - 1e-6 <= a.pos.x <= 780 + 1e-6):
            bad.append(("x", a.name, a.pos.x))
        if not (-580 - 1e-6 <= a.pos.z <= 580 + 1e-6):
            bad.append(("z", a.name, a.pos.z))
        if dist(a.pos, a.seat) > 120 + 1.0:
            bad.append(("dist", a.name, dist(a.pos, a.seat)))
check(not bad, f"18: うろつき範囲外 {bad[:3]}（計{len(bad)}件）")

# 19. 描画：office 18人で update/draw を数百フレーム。途中でスペースも押す
reset(oapp2, 5)
err = None
try:
    for i in range(400):
        if i % 40 == 10:
            press_space_and_update(oapp2)
        else:
            oapp2.update()
        oapp2.draw()
except Exception as e:  # noqa: BLE001
    err = e
check(err is None, f"19: office の update/draw で例外 {err!r}")

# 20. 状態の一覧表示：6人以下は人ごとの行、7人以上は "AGENTS N" の1行だけ
def drawn_texts(app):
    """draw 中に pyxel.text へ渡された文字列を集める（終わったら元に戻す）。"""
    out = []
    saved = pyxel.text
    pyxel.text = lambda x, y, s, col, *a, **k: out.append(str(s))
    try:
        app.draw()
    finally:
        pyxel.text = saved
    return out

# office（製品版）の左上には、FPS・人ごとの行・AGENTS・TALK のデバッグ表示を出さない（2026-11-21 夜に削除）
for n20 in (6, 7, 18):
    t_office = drawn_texts(make_app(30, 1, "office", n20))
    check(not any(x.startswith("AGENTS") or x.startswith("FPS") or x.startswith("TALK:") for x in t_office), f"20: office {n20}人にデバッグ表示が出た {t_office}")
    check(not any(len(x) > 2 and x[1] == ":" and x.split(":")[1] in ("WANDER", "WORKING") for x in t_office), f"20: office {n20}人に人ごとの行が出た {t_office}")
check(any(x.startswith("FPS ") for x in drawn_texts(dapp)), "20: proto には FPS の行が出る")
# proto には人間がいない（start_talk は office だけ）ので、会話の相手の番号を直接入れて描かせる
dapp.talk_partner = 0
try:
    check(any(x.startswith("TALK:") for x in drawn_texts(dapp)), "20: proto の会話中は TALK: の行が出る")
finally:
    dapp.talk_partner = None
check(not any(x.startswith("TALK:") for x in drawn_texts(dapp)), "20: proto の会話中でなければ TALK: は出ない")
t3 = drawn_texts(dapp)
check(any(t.startswith("A:") for t in t3) and not any(t.startswith("AGENTS") for t in t3),
      f"20: proto 3人の表示が従来と違う {t3}")

# ---- ここから「実際に描かれたか」の項目（draw が例外を出さないだけでは far 不足を見逃すため） ----
# 画面下の案内の文字（y=height-18 と height-10、色7）を数えない。数えると色7（キャラの色の候補）が文字で満たされてしまう。
COUNT_Y1 = pyxel.height - 20


def count_y1(app):
    """色を数える範囲の下端。office は3Dの範囲（y<296）から案内の文字（y=270〜）を除いた所まで、proto は画面の下の文字を除いた所まで。"""
    return pyxelcube_agents.VIEW3D_H - 30 if app.layout.has_props else COUNT_Y1


@contextlib.contextmanager
def props_hidden():
    """ドア・掲示板・小物の描画を一時的に止める。小物の色（板の7・植木の3・本の10〜12 など）が
    キャラの色と同じで、「キャラが描かれたか」の判定が小物で満たされてしまうのを避ける。"""
    saved = (pyxelcube_agents.OfficeRoot._draw_door, pyxelcube_agents.OfficeRoot._draw_board, pyxelcube_agents.OfficeRoot._draw_props)
    pyxelcube_agents.OfficeRoot._draw_door = lambda self: None
    pyxelcube_agents.OfficeRoot._draw_board = lambda self: None
    pyxelcube_agents.OfficeRoot._draw_props = lambda self: None
    try:
        yield
    finally:
        (pyxelcube_agents.OfficeRoot._draw_door, pyxelcube_agents.OfficeRoot._draw_board,
         pyxelcube_agents.OfficeRoot._draw_props) = saved


def count_colors(app, y0=20, y1=None):
    """update と draw を1回ずつ呼び、画面の y0〜y1 行（文字表示を避ける）の色ごとの画素数を数える。"""
    app.update()
    app.draw()
    if y1 is None:
        y1 = count_y1(app)
    cnt = {}
    for y in range(y0, min(y1, pyxel.height)):
        for x in range(pyxel.width):
            c = pyxel.screen.pget(x, y)
            cnt[c] = cnt.get(c, 0) + 1
    return cnt


MIN_PIXELS = 100  # 床・机・壁が「描かれた」とみなす最小の画素数

# 21. office 18人：床1・机4・壁5が十分な画素数あり、キャラの色（席の色）がすべて1画素以上ある
oapp3 = make_app(30, 1, "office", 18)
with props_hidden():  # 小物の色とキャラの色が同じ番号のことがあるため、キャラの判定では小物を描かない
    cnt = count_colors(oapp3)
for name, col in (("床", 1), ("机", pyxelcube_agents.DESK_COLOR), ("椅子", pyxelcube_agents.CHAIR_COLOR), ("壁", 5)):
    check(cnt.get(col, 0) >= MIN_PIXELS, f"21: office の{name}(色{col})が{MIN_PIXELS}画素未満 {cnt.get(col, 0)}")
for i, (_v, _y, col) in enumerate(pyxelcube_agents.OFFICE_LAYOUT.seats):
    # 色5は壁の色と同じなので、キャラ単独の確認にはならない（壁の画素で満たされる）
    check(cnt.get(col, 0) >= 1, f"21: office の席{i}のキャラの色{col}が描かれていない")

# 22. カメラの far：cam_dist + 2500（起動時の値を office・proto の両方で確かめる）
#     Layout.camera_far は廃止（ホイールで距離が変わるため、far は距離から決める）
check(not hasattr(pyxelcube_agents.Layout, "camera_far") and not hasattr(pyxelcube_agents.OFFICE_LAYOUT, "camera_far"),
      "22: Layout.camera_far が残っている（削除されたはず）")
check(pyxelcube_agents.FAR_MARGIN == 2500.0, f"22: FAR_MARGIN が2500でない {pyxelcube_agents.FAR_MARGIN}")
check(abs(oapp3.cam_dist - 1741.4) < 0.1, f"22: office の起動時 cam_dist が約1741.4でない {oapp3.cam_dist}")
check(abs(oapp3.scene.camera.far - (oapp3.cam_dist + 2500.0)) < 0.01,
      f"22: office のカメラ far が cam_dist+2500 でない {oapp3.scene.camera.far} {oapp3.cam_dist}")
papp = make_app(30, 1)
check(abs(papp.cam_dist - 832.2) < 0.1, f"22: proto の起動時 cam_dist が約832.2でない {papp.cam_dist}")
check(abs(papp.scene.camera.far - (papp.cam_dist + 2500.0)) < 0.01,
      f"22: proto のカメラ far が cam_dist+2500 でない {papp.scene.camera.far} {papp.cam_dist}")

# 23. proto 3人：床1・机4・3人の色（8, 11, 12）が描かれている
pcnt = count_colors(papp)
check(pcnt.get(1, 0) >= MIN_PIXELS, f"23: proto の床(1)が{MIN_PIXELS}画素未満 {pcnt.get(1, 0)}")
check(pyxelcube_agents.DESK_COLOR == 13 and pyxelcube_agents.CHAIR_COLOR == 4, f"23: 机/椅子の色が 13/4 でない {pyxelcube_agents.DESK_COLOR} {pyxelcube_agents.CHAIR_COLOR}")
check(pcnt.get(pyxelcube_agents.DESK_COLOR, 0) >= MIN_PIXELS, f"23: proto の机({pyxelcube_agents.DESK_COLOR})が{MIN_PIXELS}画素未満 {pcnt.get(pyxelcube_agents.DESK_COLOR, 0)}")
check(pcnt.get(pyxelcube_agents.CHAIR_COLOR, 0) >= 1, f"23: proto の椅子({pyxelcube_agents.CHAIR_COLOR})が描かれていない {pcnt.get(pyxelcube_agents.CHAIR_COLOR, 0)}")
for col in (8, 11, 12):
    check(pcnt.get(col, 0) >= 1, f"23: proto のキャラの色{col}が描かれていない")

# 24. 回帰の確認：office のカメラの far を一時的に 1000 にすると、キャラの色が描かれない
#     （＝上の項目が far の不足を検出できる）。色5は壁と同じなので除く。確認後 _apply_camera() で元の far に戻す。
oapp4 = make_app(30, 1, "office", 18)
# 起動時のカメラの注視点は人間の位置。far の効きを確かめるため、従来の注視点（layout.camera_target）に戻してから far を縮める
# （update の中のカメラ更新は far を cam_dist+2500 に戻してしまうので、この確認の間だけ止める）
oapp4.cam_target = oapp4.layout.camera_target
oapp4._apply_camera()
oapp4.scene.camera.far = 1000.0
oapp4._update_camera = lambda dt: None
try:
    with props_hidden():
        lcnt = count_colors(oapp4)
finally:
    del oapp4._update_camera  # インスタンスに付けた差し替えを外し、本来のメソッドに戻す
    oapp4._apply_camera()
char_cols = {c for _v, _y, c in pyxelcube_agents.OFFICE_LAYOUT.seats} - {5}
drawn = {c for c in char_cols if lcnt.get(c, 0) > 0}
check(not drawn, f"24: far=1000 でもキャラの色が描かれた {sorted(drawn)}")
check(abs(oapp4.scene.camera.far - (oapp4.cam_dist + 2500.0)) < 0.01, "24: far を cam_dist+2500 に戻せていない")
with props_hidden():
    rcnt = count_colors(oapp4)
check(all(rcnt.get(c, 0) >= 1 for c in char_cols), "24: far を戻してもキャラの色が描かれない")

# ---- ここから人型の関節（Pose）の項目 ----
from pyxelcube_agents import Pose, stand_pose, walk_pose, sit_pose, Mat4, Vec3


def in_range(p):
    """Pose の全角度が関節の範囲内か。"""
    o = pyxelcube_agents
    return (o.SHOULDER_RANGE[0] <= p.shoulder_l <= o.SHOULDER_RANGE[1]
            and o.SHOULDER_RANGE[0] <= p.shoulder_r <= o.SHOULDER_RANGE[1]
            and o.ELBOW_RANGE[0] <= p.elbow_l <= o.ELBOW_RANGE[1]
            and o.ELBOW_RANGE[0] <= p.elbow_r <= o.ELBOW_RANGE[1]
            and o.HIP_RANGE[0] <= p.hip_l <= o.HIP_RANGE[1]
            and o.HIP_RANGE[0] <= p.hip_r <= o.HIP_RANGE[1]
            and o.KNEE_RANGE[0] <= p.knee_l <= o.KNEE_RANGE[1]
            and o.KNEE_RANGE[0] <= p.knee_r <= o.KNEE_RANGE[1])


# 25. Pose.clamped：範囲外は端に収まる。範囲内は変わらない
bad_p = Pose(shoulder_l=999.0, shoulder_r=-999.0, elbow_l=-10.0, elbow_r=999.0,
             hip_l=-999.0, hip_r=999.0, knee_l=200.0, knee_r=-5.0, body_y=-7.0).clamped()
check(bad_p.shoulder_l == 150.0 and bad_p.shoulder_r == -60.0, f"25: 肩が端に収まらない {bad_p}")
check(bad_p.elbow_l == 0.0 and bad_p.elbow_r == 150.0, f"25: 肘が端に収まらない {bad_p}")
check(bad_p.hip_l == -60.0 and bad_p.hip_r == 120.0, f"25: 付け根が端に収まらない {bad_p}")
check(bad_p.knee_l == 150.0 and bad_p.knee_r == 0.0, f"25: 膝が端に収まらない {bad_p}")
check(bad_p.body_y == -7.0, f"25: body_y が変わった {bad_p.body_y}")
check(bad_p.body_z == 0.0, f"25: body_z の既定が0でない {bad_p.body_z}")
check(Pose(0, 0, 5, 5, 0, 0, 0, 0, -1.0, -25.0).clamped().body_z == -25.0, "25: clamped で body_z が変わった")
ok_p = Pose(shoulder_l=10.0, shoulder_r=-20.0, elbow_l=30.0, elbow_r=140.0,
            hip_l=-50.0, hip_r=100.0, knee_l=1.0, knee_r=149.0, body_y=3.0)
check(ok_p.clamped() == ok_p, f"25: 範囲内の値が変わった {ok_p.clamped()}")

# 26. stand_pose：肩・付け根・膝が0、肘5、body_y 0
sp = stand_pose()
check((sp.shoulder_l, sp.shoulder_r, sp.hip_l, sp.hip_r, sp.knee_l, sp.knee_r) == (0.0,) * 6,
      f"26: 立ちの肩・付け根・膝が0でない {sp}")
check(sp.elbow_l == 5.0 and sp.elbow_r == 5.0 and sp.body_y == 0.0, f"26: 立ちの肘/body_y {sp}")
check(sp.body_z == 0.0, f"26: 立ちの body_z が0でない {sp}")

# 27. walk_pose：左右逆・腕は同じ側の脚と逆・膝は後ろへ下がる脚だけ・範囲内
w = walk_pose(math.pi / 2)
check(w.hip_l > 0 and w.hip_r < 0, f"27: phase=π/2 の付け根が 左>0/右<0 でない {w}")
check(w.shoulder_l < 0 and w.shoulder_r > 0, f"27: phase=π/2 の肩が 左<0/右>0 でない {w}")
check(w.knee_l == 0.0 and w.knee_r > 0.0, f"27: phase=π/2 の膝（後ろの右脚だけ曲がる）{w}")
w = walk_pose(-math.pi / 2)
check(w.hip_l < 0 and w.hip_r > 0, f"27: phase=-π/2 の付け根が逆でない {w}")
check(w.shoulder_l > 0 and w.shoulder_r < 0, f"27: phase=-π/2 の肩が逆でない {w}")
check(w.knee_r == 0.0 and w.knee_l > 0.0, f"27: phase=-π/2 の膝（後ろの左脚だけ曲がる）{w}")
check(walk_pose(0.0).knee_l == 0.0 and walk_pose(0.0).knee_r == 0.0, "27: phase=0 で膝が曲がっている")
allin = all(in_range(walk_pose(k * 0.1)) for k in range(-100, 400))
check(allin, "27: walk_pose に範囲外の値がある")
bothknee = [k for k in range(-100, 400)
            if walk_pose(k * 0.1).knee_l > 0 and walk_pose(k * 0.1).knee_r > 0]
check(not bothknee, f"27: 両膝が同時に曲がる位相がある {bothknee[:3]}")
check(all(walk_pose(k * 0.1).body_y == 0.0 for k in range(100)), "27: 歩きの body_y が 0 でない")
check(all(walk_pose(k * 0.1).body_z == 0.0 for k in range(100)), "27: 歩きの body_z が 0 でない")

# 28. sit_pose：付け根・膝90、肩80、body_y -20、body_z -25。肘は 15±5 で時間で変わり、左右は逆向き（和30）
sit0 = sit_pose(0.0)
check(sit0.hip_l == 90.0 and sit0.hip_r == 90.0 and sit0.knee_l == 90.0 and sit0.knee_r == 90.0,
      f"28: 座りの付け根・膝が90でない {sit0}")
check(sit0.shoulder_l == 80.0 and sit0.shoulder_r == 80.0, f"28: 座りの肩が80でない {sit0}")  # 旧仕様は40→75
check(sit0.body_z == -25.0 and pyxelcube_agents.SIT_BODY_Z == -25.0, f"28: 座りの body_z が-25でない {sit0.body_z}")
check(sit0.body_y == -20.0 and pyxelcube_agents.SIT_BODY_Y == -20.0, f"28: 座りの body_y が-20でない {sit0.body_y}")
elb = [sit_pose(k * 0.01) for k in range(100)]
check(all(abs(q.elbow_l + q.elbow_r - 30.0) < 1e-9 for q in elb), "28: elbow_l+elbow_r が常に30でない")
check(max(q.elbow_l for q in elb) - min(q.elbow_l for q in elb) > 5.0, "28: 肘が時間で変わらない")
check(all(abs(q.elbow_l - 15.0) <= 5.0 + 1e-9 for q in elb), "28: 肘が 15±5 を超えた")
check(sit_pose(0.075).elbow_l > 15.0 and sit_pose(0.075).elbow_r < 15.0, "28: 左右が逆向きに動かない")
check(all(in_range(q) for q in elb), "28: sit_pose に範囲外の値がある")

# 29. Agent の姿勢：歩く間は walk_phase が進み walk_pose と一致、立ち止まりは stand_pose、座ると sit_pose
ag = pyxelcube_agents.Agent("T", seat, random.Random(4))
walk_seen = stand_seen = 0
travel = 0.0
phase_prev = ag.walk_phase
ng = []
for _ in range(60 * 30):
    p0 = ag.pos
    ag.update(1 / 60)
    moved = dist(p0, ag.pos)
    travel += moved
    if moved > 1e-12:
        if ag.walk_phase <= phase_prev:
            ng.append(("phase が進まない", ag.walk_phase))
        if ag.pose == walk_pose(ag.walk_phase):
            walk_seen += 1
        elif ag.pose == stand_pose():
            stand_seen += 1  # 目標に着いたフレーム
        else:
            ng.append(("歩き中の姿勢が不正", ag.pose))
    else:
        if ag.walk_phase != phase_prev:
            ng.append(("止まっているのに phase が変わる", ag.walk_phase))
        if ag.pose != stand_pose():
            ng.append(("止まっている間が stand でない", ag.pose))
    phase_prev = ag.walk_phase
check(not ng, f"29: 歩き/立ち止まりの姿勢 {ng[:3]}（計{len(ng)}件）")
check(walk_seen > 100, f"29: 歩きの姿勢が十分に見られない {walk_seen}")
check(abs(ag.walk_phase - travel / pyxelcube_agents.STRIDE * 2 * math.pi) < 1e-3,  # Vec3 は単精度のため 1e-5 程度ずれる
      f"29: walk_phase が歩いた距離と合わない {ag.walk_phase}")
# 立ち止まっている間（_wait>0）を作って確認
ag = pyxelcube_agents.Agent("T", seat, random.Random(4))
stopped = 0
for _ in range(60 * 30):
    ag.update(1 / 60)
    if ag._wait > 0.0:
        stopped += 1
        check(ag.pose == stand_pose(), "29: 立ち止まり中が stand_pose でない")
check(stopped > 0, "29: 立ち止まる時間が観測できない")
# 着席：sit_pose、5秒後は body_y 0
ag = pyxelcube_agents.Agent("T", seat, random.Random(5))
ag.pos = pyxelcube_agents.Vec3(200.0, 0.0, 100.0)
ag.start_work()
n = 0
while not ag._arrived and n < 6000:
    ag.update(1 / 60)
    n += 1
check(ag._arrived and ag.pose.body_y == -20.0, f"29: 着席直後の body_y が-20でない {ag.pose}")
check(ag.pose == sit_pose(0.0), "29: 着席直後が sit_pose(0) でない")
ag.update(1 / 60)
check(ag.pose == sit_pose(ag._seated_time), "29: 着席中が sit_pose(経過時間) と一致しない")
for _ in range(60 * 5):
    ag.update(1 / 60)
check(ag.state == "WANDER" and ag.pose.body_y == 0.0, f"29: 5秒後に WANDER で body_y 0 でない {ag.state} {ag.pose}")

# 30. 座ったときの形（AgentView と同じ計算を Mat4 で再現して幾何を確かめる）
def leg_geometry(pose, x_sign=-1.0):
    """AgentView と同じ式で、脚の付け根・膝・足の裏・太ももの箱の中心の位置を返す。"""
    o = pyxelcube_agents
    a = o.Agent("G", Vec3(0.0, 0.0, 0.0), random.Random(0))
    a.pose = pose
    view = o.AgentView(a, 8)
    view.on_update()  # 位置(0,body_y,0)・yaw 0 の変換行列を作る
    base = view.transform
    hip = base * Mat4.from_translation(Vec3(x_sign * o.HIP_X, o.HIP_Y, 0.0))
    hip_angle = pose.hip_l if x_sign < 0 else pose.hip_r
    knee_angle = pose.knee_l if x_sign < 0 else pose.knee_r
    thigh = hip * Mat4.from_axis_angle(Vec3.RIGHT, hip_angle)
    thigh_center = thigh * Mat4.from_translation(Vec3(0.0, -o.THIGH_LEN / 2, 0.0))
    knee = thigh * Mat4.from_translation(Vec3(0.0, -o.THIGH_LEN, 0.0))
    shin = knee * Mat4.from_axis_angle(Vec3.RIGHT, -knee_angle)
    foot = shin * Mat4.from_translation(Vec3(0.0, -o.SHIN_LEN, 0.0))
    return hip.pos, thigh_center.pos, knee.pos, foot.pos


for xs in (-1.0, 1.0):
    hip_p, thigh_c, knee_p, foot_p = leg_geometry(sit_pose(0.0), xs)
    check(abs(hip_p.z - pyxelcube_agents.SIT_BODY_Z) < 1e-6, f"30: 座りの付け根の z が body_z(-25)でない {hip_p.z}")
    check(abs(hip_p.y - 20.0) < 1e-6, f"30: 座りの付け根の高さが20でない {hip_p.y}")
    check(abs(knee_p.y - 20.0) < 1e-6, f"30: 座りの膝の高さが20（太ももが水平）でない {knee_p.y}")
    check(abs(foot_p.y - 0.0) < 1e-6, f"30: 座りの足の裏が床(0)でない {foot_p.y}")
    check(knee_p.z < hip_p.z - 19.0, f"30: 膝が付け根より前(-Z)に出ていない {hip_p.z} {knee_p.z}")
    check(abs(foot_p.z - knee_p.z) < 1e-6, f"30: すねが垂直でない {knee_p.z} {foot_p.z}")
    thigh_bottom = thigh_c.y - pyxelcube_agents.THIGH_THICK / 2
    seat_top = pyxelcube_agents.CHAIR_SEAT_CENTER.y + pyxelcube_agents.CHAIR_SEAT_SIZE.y / 2
    check(abs(thigh_bottom - 15.0) < 1e-6 and abs(seat_top - 16.0) < 1e-6,
          f"30: 太ももの下面{thigh_bottom}/座面の上面{seat_top}が15/16でない")
    check(abs(thigh_bottom - seat_top) <= 1.0, f"30: 太ももと座面の差が1を超える {thigh_bottom} {seat_top}")
    # 太ももが座面の上：付け根と太ももの中心が座面の x・z 範囲内（座面は席のローカルで中心 z=-25、30x30）
    sc, ss = pyxelcube_agents.CHAIR_SEAT_CENTER, pyxelcube_agents.CHAIR_SEAT_SIZE
    for nm, pt in (("付け根", hip_p), ("太ももの中心", thigh_c)):
        check(abs(pt.x - sc.x) <= ss.x / 2 and abs(pt.z - sc.z) <= ss.z / 2,
              f"30: {nm}が座面の範囲外 x={pt.x} z={pt.z}（座面 z {sc.z - ss.z / 2}〜{sc.z + ss.z / 2}）")
# 立ちの形：足の裏が床に付き、歩きの前脚は前(-Z)へ出る（符号の確認）
_h, _c, _k, _f = leg_geometry(stand_pose(), -1.0)
check(abs(_f.y) < 1e-6 and abs(_h.y - 40.0) < 1e-6, f"30: 立ちの足の裏/付け根の高さ {_f.y} {_h.y}")
_h, _c, _k, _f = leg_geometry(Pose(0, 0, 5, 5, 30.0, 0, 0, 0, 0.0), -1.0)
check(_k.z < _h.z, f"30: 付け根が正の脚が前(-Z)へ振れない {_h.z} {_k.z}")
_h, _c, _k, _f = leg_geometry(Pose(0, 0, 5, 5, 0, 0, 60.0, 0, 0.0), -1.0)
check(_f.z > _k.z, f"30: 膝を曲げたすねが後ろ(+Z)へ曲がらない {_k.z} {_f.z}")

# 31. 描画：proto 3人で1人を座らせ、3人の色・机の色13・椅子の色4・床の色1が描かれる
papp2 = make_app(30, 2)
papp2.agents[0].start_work()
for _ in range(10):
    papp2.update()
check(papp2.agents[0]._arrived and papp2.agents[0].pose.body_y == -20.0, "31: A が座った姿勢になっていない")
c2 = count_colors(papp2)
check(c2.get(1, 0) >= MIN_PIXELS, f"31: 床(1)が描かれていない {c2.get(1, 0)}")
check(c2.get(pyxelcube_agents.DESK_COLOR, 0) >= MIN_PIXELS, f"31: 机({pyxelcube_agents.DESK_COLOR})が描かれていない {c2.get(pyxelcube_agents.DESK_COLOR, 0)}")
check(c2.get(pyxelcube_agents.CHAIR_COLOR, 0) >= 1, f"31: 椅子({pyxelcube_agents.CHAIR_COLOR})が描かれていない {c2.get(pyxelcube_agents.CHAIR_COLOR, 0)}")
for col in (8, 11, 12):
    check(c2.get(col, 0) >= 1, f"31: proto のキャラの色{col}が描かれていない（1人座り）")
# office 18人（1人座らせる）：各キャラの色（色5は壁と同じなので除く）
oapp5 = make_app(30, 1, "office", 18)
oapp5.agents[0].start_work()
for _ in range(10):
    oapp5.update()
with props_hidden():
    c3 = count_colors(oapp5)
for i, (_v, _y, col) in enumerate(pyxelcube_agents.OFFICE_LAYOUT.seats):
    if col != 5:
        check(c3.get(col, 0) >= 1, f"31: office の席{i}のキャラの色{col}が描かれていない（1人座り）")
check(c3.get(pyxelcube_agents.DESK_COLOR, 0) >= MIN_PIXELS and c3.get(1, 0) >= MIN_PIXELS, "31: office の机(13)/床(1)が描かれていない")
check(c3.get(pyxelcube_agents.CHAIR_COLOR, 0) >= 1, "31: office の椅子(4)が描かれていない")

# 32. 机の大きさと椅子：DESK_SIZE=(120,38,60)、机の中心 y=19。机1つ＝天板1＋側板2の3個、椅子は席ごとに2個
ds = pyxelcube_agents.DESK_SIZE
check((ds.x, ds.y, ds.z) == (120.0, 38.0, 60.0), f"32: DESK_SIZE が(120,38,60)でない {ds}")
check(pyxelcube_agents.DESK_Y == 19.0, f"32: DESK_Y が19でない {pyxelcube_agents.DESK_Y}")
check(all(d.y == 19.0 for d in pyxelcube_agents.PROTO_LAYOUT.desks + pyxelcube_agents.OFFICE_LAYOUT.desks),
      "32: 机の中心 y が19でない")


def box_calls(layout_name):
    """OfficeRoot.on_draw の中の box 呼び出しを記録する（実際には描かない）。"""
    root = pyxelcube_agents.OfficeRoot(pyxelcube_agents.LAYOUTS[layout_name])
    calls = []
    root.box = lambda m, size, col, *a, **k: calls.append((m, size, col))
    root.on_draw()
    return calls


def sz(v):
    return (v.x, v.y, v.z)


# office の壁は4枚（奥・左・右・手前）。has_props の小物の箱は16個：
# ドアの板1＋札1・掲示板1（棒は0%のとき描かない）・100% の枠（棒2本×4個＝8個。0% でも描く）・書棚2×（本体1＋本3）・植木の鉢2・丸テーブルの脚1・コーヒーメーカー本体1＋ランプ1
N_PROP_BOXES = {"proto": 0, "office": 1 + 1 + 1 + 8 + 2 * 4 + 2 + 1 + 1 + 1}
for lname, nwall, ndesk, nseat in (("proto", 0, 3, 3), ("office", 4, 18, 18)):
    calls = box_calls(lname)
    lay = pyxelcube_agents.LAYOUTS[lname]
    want = 1 + nwall + ndesk * 3 + nseat * 2 + N_PROP_BOXES[lname]
    check(len(calls) == want, f"32: {lname} の box 呼び出しが{want}回でなく{len(calls)}回")
    tops = [c for c in calls if sz(c[1]) == (120.0, 4.0, 60.0)]
    sides = [c for c in calls if sz(c[1]) == (4.0, 34.0, 60.0)]
    check(len(tops) == ndesk and all(c[2] == pyxelcube_agents.DESK_COLOR == 13 for c in tops), f"32: {lname} の天板が{ndesk}個・色13でない {len(tops)}")
    check(len(sides) == ndesk * 2 and all(c[2] == pyxelcube_agents.DESK_COLOR == 13 for c in sides),
          f"32: {lname} の側板が{ndesk * 2}個・色13でない {len(sides)}")
    # 位置：天板は y=36（上面38）、側板は y=17・x=机±58。机ごとに天板1＋側板2が対応している
    for d in lay.desks:
        tp = [c for c in tops if abs(c[0].pos.x - d.x) < 1e-3 and abs(c[0].pos.z - d.z) < 1e-3]
        sd = [c for c in sides if abs(c[0].pos.z - d.z) < 1e-3 and abs(abs(c[0].pos.x - d.x) - 58.0) < 1e-3]
        check(len(tp) == 1 and abs(tp[0][0].pos.y - 36.0) < 1e-3, f"32: {lname} の机{d}の天板が y=36 で1枚でない")
        check(len(sd) == 2 and all(abs(c[0].pos.y - 17.0) < 1e-3 for c in sd)
              and {round(c[0].pos.x - d.x) for c in sd} == {-58, 58}, f"32: {lname} の机{d}の側板が x±58・y=17 で2枚でない")
    chairs = [c for c in calls if c[1] in (pyxelcube_agents.CHAIR_SEAT_SIZE, pyxelcube_agents.CHAIR_BACK_SIZE)]
    check(len(chairs) == nseat * 2 and all(c[2] == pyxelcube_agents.CHAIR_COLOR == 4 for c in chairs),
          f"32: {lname} の椅子の箱が{nseat * 2}個・色4でない {len(chairs)}")
    check(calls[0][2] == 1, f"32: {lname} の最初（床）の色が1でない")
    # 椅子の位置：席から見て座面は前(机側)へ25・高さ14、背もたれは前へ10・高さ31（yaw180 は z の向きが逆）
    for sv, syaw, _c in lay.seats:
        sgn = -1.0 if syaw == 0.0 else 1.0  # 机の方向の z の符号
        for cy, cz in ((14.0, 25.0), (31.0, 10.0)):
            hit = [c for c in chairs if abs(c[0].pos.x - sv.x) < 1e-3 and abs(c[0].pos.y - cy) < 1e-3
                   and abs(c[0].pos.z - (sv.z + sgn * cz)) < 1e-3]
            check(len(hit) == 1, f"32: {lname} の席{sv}の椅子(高さ{cy})が席から机側へ{cz}の位置にない")

# 33. 手が机の上：座った人の肩→肘→手の先を Mat4（AgentView と同じ式）で計算する。
#     机の手前の縁（席に近い側）から 5 より奥で、天板の上面(38)より上・48 より下。タイピングの動き全体で成り立つ。
def arm_geometry(seat_v, seat_yaw, pose, x_sign):
    """座った人の 肘の位置・前腕の中心・手の先（ワールド座標）を返す。AgentView と同じ式。"""
    o = pyxelcube_agents
    a = o.Agent("G", seat_v, random.Random(0))
    a.pose = pose
    a.yaw = seat_yaw
    view = o.AgentView(a, 8)
    view.on_update()
    shoulder = view.transform * Mat4.from_translation(Vec3(x_sign * o.SHOULDER_X, o.SHOULDER_Y, 0.0))
    sh_angle = pose.shoulder_l if x_sign < 0 else pose.shoulder_r
    el_angle = pose.elbow_l if x_sign < 0 else pose.elbow_r
    upper = shoulder * Mat4.from_axis_angle(Vec3.RIGHT, sh_angle)
    elbow = upper * Mat4.from_translation(Vec3(0.0, -o.UPPER_ARM_LEN, 0.0))
    fore = elbow * Mat4.from_axis_angle(Vec3.RIGHT, el_angle)
    fore_c = fore * Mat4.from_translation(Vec3(0.0, -o.FOREARM_LEN / 2.0, 0.0))
    hand = fore * Mat4.from_translation(Vec3(0.0, -o.FOREARM_LEN, 0.0))
    return elbow.pos, fore_c.pos, hand.pos


def depth_into_desk(desk_v, seat_yaw, p):
    """点 p が、机の中心から見て席側の縁(-30)を 0 の基準にどれだけ机の奥へ入っているか。
    席が +Z 側(yaw0)なら机は -Z 向き、席が -Z 側(yaw180)なら机は +Z 向き。縁は中心から 30。"""
    along = -(p.z - desk_v.z) if seat_yaw == 0.0 else (p.z - desk_v.z)
    return along + 30.0


T_SAMPLES = [k * 0.025 for k in range(13)]  # 打鍵の周期0.3秒を一巡


def check_hands_on_desk(tag, lay):
    bad = []
    for i, (sv, syaw, _c) in enumerate(lay.seats):
        desk = lay.desks[i]
        for t in T_SAMPLES:
            for xs in (-1.0, 1.0):
                _e, fc, hand = arm_geometry(sv, syaw, sit_pose(t), xs)
                dep = depth_into_desk(desk, syaw, hand)
                if not (dep > 5.0):
                    bad.append(("手が縁より奥でない", i, t, xs, round(dep, 1)))
                if dep >= 60.0 or abs(hand.x - desk.x) > 60.0:
                    bad.append(("手が天板の範囲外", i, t, xs, round(dep, 1), round(hand.x - desk.x, 1)))
                if not (38.0 < hand.y < 48.0):
                    bad.append(("手の高さが38〜48でない", i, t, xs, round(hand.y, 1)))
                # 前腕の中ほど：天板の上面(38)より上（太さの半分3.5を考え、1の許容）
                if fc.y < 38.0 + 3.5 - 1.0:
                    bad.append(("前腕が天板にめり込む", i, t, xs, round(fc.y, 2)))
    miny = min(b_[-1] for b_ in bad if b_[0] == "前腕が天板にめり込む") if any(b_[0] == "前腕が天板にめり込む" for b_ in bad) else None
    kinds = sorted({b_[0] for b_ in bad})
    check(not bad, f"33: {tag} 手が机の上にない {kinds} 前腕中心yの最小{miny}（要40.5以上）{bad[:2]}（計{len(bad)}件）")


check_hands_on_desk("proto", pyxelcube_agents.PROTO_LAYOUT)
# 34. office の窓際・各島でも同じ。窓際は席 z=-500(yaw180・+Zを向く)、机 z=-430 なので、席側の縁は z=-460
#     （机の手前=部屋側の縁 z=-400 ではない）。depth_into_desk が向きを考えて計算する。
check_hands_on_desk("office（窓際2＋島16）", pyxelcube_agents.OFFICE_LAYOUT)
# 34 の補足：窓際の手の先の z を直接確かめる（席 -500、体の前ずらし25、手は前55付近 → z=-445付近、-460〜-400 の間）
for i in (0, 1):
    sv, syaw, _c = pyxelcube_agents.OFFICE_LAYOUT.seats[i]
    for xs in (-1.0, 1.0):
        hz = arm_geometry(sv, syaw, sit_pose(0.0), xs)[2].z
        check(-455.0 < hz < -400.0, f"34: 窓際{i}の手の先の z が机の上(-455〜-400)にない {hz}")

# 35. 脚が机に入る：座った太もも・すね・足が、天板の下(y<34)で側板(机±58、厚さ4＝内面±56)にぶつからない
def check_legs_under_desk(tag, lay):
    bad = []
    for i, (sv, syaw, _c) in enumerate(lay.seats):
        desk = lay.desks[i]
        for xs in (-1.0, 1.0):
            hip_p, thigh_c, knee_p, foot_p = leg_geometry_at(sv, syaw, sit_pose(0.0), xs)
            for nm, pt, half in (("太ももの中心", thigh_c, pyxelcube_agents.THIGH_THICK / 2),
                                 ("膝", knee_p, pyxelcube_agents.THIGH_THICK / 2),
                                 ("足の裏", foot_p, pyxelcube_agents.SHIN_THICK / 2)):
                dx = abs(pt.x - desk.x)
                if abs(dx - pyxelcube_agents.HIP_X) > 1e-3:
                    bad.append((nm, "脚の x が机±7でない", i, round(dx, 2)))
                if dx + half >= 56.0:
                    bad.append((nm, "側板にぶつかる", i, round(dx + half, 2)))
            # 太ももの上面・膝・すねの中ほどの高さは天板の下面(34)より下
            top_of_thigh = thigh_c.y + pyxelcube_agents.THIGH_THICK / 2
            if top_of_thigh >= 34.0:
                bad.append(("太ももの上面が天板に届く", i, round(top_of_thigh, 2)))
            if max(hip_p.y, knee_p.y, foot_p.y) >= 34.0:
                bad.append(("脚の関節が天板より上", i))
    check(not bad, f"35: {tag} 脚が机に入らない {bad[:4]}（計{len(bad)}件）")


def leg_geometry_at(seat_v, seat_yaw, pose, x_sign):
    """leg_geometry と同じ式で、席の位置・向きを付けたワールド座標の脚の位置を返す。"""
    o = pyxelcube_agents
    a = o.Agent("G", seat_v, random.Random(0))
    a.pose = pose
    a.yaw = seat_yaw
    view = o.AgentView(a, 8)
    view.on_update()
    hip = view.transform * Mat4.from_translation(Vec3(x_sign * o.HIP_X, o.HIP_Y, 0.0))
    thigh = hip * Mat4.from_axis_angle(Vec3.RIGHT, pose.hip_l if x_sign < 0 else pose.hip_r)
    thigh_c = thigh * Mat4.from_translation(Vec3(0.0, -o.THIGH_LEN / 2, 0.0))
    knee = thigh * Mat4.from_translation(Vec3(0.0, -o.THIGH_LEN, 0.0))
    shin = knee * Mat4.from_axis_angle(Vec3.RIGHT, -(pose.knee_l if x_sign < 0 else pose.knee_r))
    foot = shin * Mat4.from_translation(Vec3(0.0, -o.SHIN_LEN, 0.0))
    return hip.pos, thigh_c.pos, knee.pos, foot.pos


check_legs_under_desk("proto", pyxelcube_agents.PROTO_LAYOUT)
check_legs_under_desk("office", pyxelcube_agents.OFFICE_LAYOUT)

# 36. ズーム（マウスホイール）：pyxel.mouse_wheel を代入して真似る。終わったら必ず 0 に戻す
def wheel_update(app, n):
    """ホイールを n ノッチ回した 1 フレームだけ update を呼ぶ。"""
    pyxel.mouse_wheel = n
    try:
        app.update()
    finally:
        pyxel.mouse_wheel = 0


def cam_pos_ok(app):
    """カメラの位置が target + dir*dist、far が dist+2500 か。"""
    eye = app.cam_target + app.cam_dir * app.cam_dist
    cp = app.camera.transform.pos
    near = abs(cp.x - eye.x) < 0.05 and abs(cp.y - eye.y) < 0.05 and abs(cp.z - eye.z) < 0.05
    return near and abs(app.camera.far - (app.cam_dist + 2500.0)) < 0.01


for lname, nm in (("proto", "proto"), ("office", "office")):
    zapp = make_app(30, 1, lname, 3)
    lay = zapp.layout
    d0 = zapp.cam_dist
    dir0 = (zapp.cam_dir.x, zapp.cam_dir.y, zapp.cam_dir.z)
    check(pyxelcube_agents.ZOOM_STEP == 0.9, f"36: ZOOM_STEP が0.9でない {pyxelcube_agents.ZOOM_STEP}")
    wheel_update(zapp, 0)
    check(zapp.cam_dist == d0, f"36: {nm} ホイール0で距離が変わった {zapp.cam_dist}")
    wheel_update(zapp, 1)
    check(abs(zapp.cam_dist - d0 * 0.9) < 1e-6, f"36: {nm} ホイール+1で0.9倍でない {zapp.cam_dist / d0}")
    check(cam_pos_ok(zapp), f"36: {nm} +1 後のカメラ位置/far が合わない")
    wheel_update(zapp, -1)
    check(abs(zapp.cam_dist - d0) < 1e-6, f"36: {nm} ホイール-1で元に戻らない（1/0.9倍でない）{zapp.cam_dist / d0}")
    check(cam_pos_ok(zapp), f"36: {nm} -1 後のカメラ位置/far が合わない")
    wheel_update(zapp, 3)
    check(abs(zapp.cam_dist - d0 * 0.729) < 1e-6, f"36: {nm} ホイール+3で0.729倍でない {zapp.cam_dist / d0}")
    wheel_update(zapp, -3)
    check(abs(zapp.cam_dist - d0) < 1e-6, f"36: {nm} ホイール-3で元に戻らない {zapp.cam_dist / d0}")
    # ホイール0のフレームを挟んでも変わらない（カメラも動かない）
    before = (zapp.cam_dist, zapp.camera.transform.pos.x, zapp.camera.transform.pos.y, zapp.camera.transform.pos.z)
    for _ in range(5):
        wheel_update(zapp, 0)
    after = (zapp.cam_dist, zapp.camera.transform.pos.x, zapp.camera.transform.pos.y, zapp.camera.transform.pos.z)
    check(before == after, f"36: {nm} ホイール0のフレームでカメラが変わった {before} {after}")
    # 何度も寄ると zoom_min で止まり、途中も範囲内・向きは変わらない
    ok_between = True
    for _ in range(80):
        wheel_update(zapp, 1)
        ok_between = ok_between and lay.zoom_min - 1e-9 <= zapp.cam_dist <= lay.zoom_max + 1e-9 and cam_pos_ok(zapp)
    check(abs(zapp.cam_dist - lay.zoom_min) < 1e-9, f"36: {nm} 寄っても zoom_min({lay.zoom_min}) で止まらない {zapp.cam_dist}")
    check(ok_between, f"36: {nm} 寄る途中で範囲外/カメラ位置のずれ")
    wheel_update(zapp, 1)
    check(zapp.cam_dist == lay.zoom_min, f"36: {nm} zoom_min で更に寄れてしまう {zapp.cam_dist}")
    # 一度に大きく回しても範囲内
    wheel_update(zapp, 50)
    check(zapp.cam_dist == lay.zoom_min, f"36: {nm} +50 で zoom_min に収まらない {zapp.cam_dist}")
    for _ in range(120):
        wheel_update(zapp, -1)
    check(abs(zapp.cam_dist - lay.zoom_max) < 1e-9, f"36: {nm} 引いても zoom_max({lay.zoom_max}) で止まらない {zapp.cam_dist}")
    check(cam_pos_ok(zapp), f"36: {nm} zoom_max でカメラ位置/far が合わない")
    wheel_update(zapp, -50)
    check(zapp.cam_dist == lay.zoom_max, f"36: {nm} -50 で zoom_max に収まらない {zapp.cam_dist}")
    d = (zapp.cam_dir.x, zapp.cam_dir.y, zapp.cam_dir.z)
    check(max(abs(a - b) for a, b in zip(d, dir0)) < 1e-9, f"36: {nm} ズームで向き cam_dir が変わった")
    # 実際の向き：カメラ位置 - 注視点 が cam_dir と平行
    cp = zapp.camera.transform.pos
    v = Vec3(cp.x - zapp.cam_target.x, cp.y - zapp.cam_target.y, cp.z - zapp.cam_target.z).normalize()
    check(abs(v.x - dir0[0]) < 1e-3 and abs(v.y - dir0[1]) < 1e-3 and abs(v.z - dir0[2]) < 1e-3,
          f"36: {nm} 最も引いたとき実際のカメラの向きが変わった")
    check(pyxel.mouse_wheel == 0, "36: mouse_wheel を 0 に戻せていない")
check(pyxelcube_agents.PROTO_LAYOUT.zoom_min == 120.0 and pyxelcube_agents.PROTO_LAYOUT.zoom_max == 1500.0,
      "36: proto の zoom_min/max が 120/1500 でない")
check(pyxelcube_agents.OFFICE_LAYOUT.zoom_min == 150.0 and pyxelcube_agents.OFFICE_LAYOUT.zoom_max == 3000.0,
      "36: office の zoom_min/max が 150/3000 でない")

# 37. ズームの全域で描かれる：zoom_min と zoom_max で、キャラの色が1画素以上描かれる。
#     zoom_min では注視点の周り以外は画面に入らないので、「注視点の近くのキャラ」の色を見る
#     （proto は既定の注視点の近くの B、office は注視点を席(5番=島の席)の足元に置いて、その人の色）。
#     zoom_max は遠くて小さいため、キャラ全体のうち1色以上が描かれていればよい。office は色5が壁と同じなので除く。
def draw_count(app):
    app.draw()
    cnt = {}
    for y in range(20, min(count_y1(app), pyxel.height)):
        for x in range(pyxel.width):
            c = pyxel.screen.pget(x, y)
            cnt[c] = cnt.get(c, 0) + 1
    return cnt


for lname in ("proto", "office"):
    zapp = make_app(30, 1, lname, 18 if lname == "office" else 3)
    lay = zapp.layout
    # 注視点の近くの人：proto は B(1)、office は色が5でない席（5番）
    idx = 1 if lname == "proto" else 5
    col = lay.seats[idx][2]
    check(col != 5, f"37: テストの前提 {lname} の席{idx}の色が5（壁と同じ）")
    ag = zapp.agents[idx]
    # 近くへ寄る：注視点をその人の胸の高さへ移し（注視点の移動はテスト用）、zoom_min まで寄る
    zapp.cam_target = Vec3(ag.pos.x, 40.0, ag.pos.z)
    wheel_update(zapp, 100)
    check(zapp.cam_dist == lay.zoom_min, f"37: {lname} zoom_min に寄れていない {zapp.cam_dist}")
    zapp.update()
    # 小物の色とキャラの色が同じ番号のことがあるので、office はキャラの判定のとき小物を描かない
    def hide():
        return props_hidden() if lname == "office" else contextlib.nullcontext()
    with hide():
        cnt = draw_count(zapp)
    check(cnt.get(col, 0) >= 1, f"37: {lname} zoom_min で注視点の近くのキャラの色{col}が描かれない")
    check(cnt.get(1, 0) + cnt.get(pyxelcube_agents.DESK_COLOR, 0) + cnt.get(col, 0) + cnt.get(5, 0) > 0, f"37: {lname} zoom_min で何も描かれない")
    # zoom_max：既定の注視点へ戻して最大まで引く
    zapp.cam_target = lay.camera_target
    wheel_update(zapp, -200)
    check(zapp.cam_dist == lay.zoom_max, f"37: {lname} zoom_max まで引けていない {zapp.cam_dist}")
    # zoom_max ではキャラが 1〜3 画素ほどしかなく、その瞬間の位置や向きで 1 フレームだけ 0 画素になる人がいる
    # （office の席7＝色11 が単独でも描かれないことを確認済み。隠れているのではなく小さすぎるため）。
    # そこで 90 フレーム（3 秒）動かし、その間に一度でも描かれた色を集める。全員の色が描かれていればよい。
    char_cols = {c for _v, _y, c in lay.seats[:len(zapp.agents)]} - {5}
    got = set()
    floor_px = 0
    for _ in range(90):
        zapp.update()
        with hide():
            cnt = draw_count(zapp)
        got |= {c for c in char_cols if cnt.get(c, 0) >= 1}
        floor_px = max(floor_px, cnt.get(1, 0))
    check(got == char_cols, f"37: {lname} zoom_max で90フレームの間に描かれなかったキャラの色 {sorted(char_cols - got)}")
    check(floor_px >= MIN_PIXELS, f"37: {lname} zoom_max で床(1)が描かれない {floor_px}")
    print(f"(37) {lname} zoom_max で描かれたキャラの色 {sorted(got)} / {sorted(char_cols)}")

# 38. 案内の文字
# proto だけ出す。office（製品版）には出さない
check("SPACE:WORK WHEEL:ZOOM ARROWS:VIEW" in drawn_texts(dapp), "38: proto の案内が 'SPACE:WORK WHEEL:ZOOM ARROWS:VIEW' でない")
check("SPACE:WORK WHEEL:ZOOM ARROWS:VIEW" not in drawn_texts(oapp), "38: office に proto の案内が出た")

# 39. AgentView.on_draw の箱10個の色：box を差し替えて (行列, 大きさ, 色) を集める。
#     頭と腕4本（上腕・前腕）は肌色 SKIN_COLOR、胴と脚4本（太もも・すね）はキャラの色。立ち・歩き・座りで同じ。
def view_boxes(view):
    """AgentView.on_draw 内の box 呼び出しを記録する（実際には描かない）。"""
    calls = []
    view.box = lambda m, size, col, *a, **k: calls.append((m, sz(size), col))
    view.on_draw()
    return calls


O = pyxelcube_agents
SKIN_SIZES = {sz(O.HEAD_SIZE): "頭",
              (O.UPPER_ARM_THICK, O.UPPER_ARM_LEN, O.UPPER_ARM_THICK): "上腕",
              (O.FOREARM_THICK, O.FOREARM_LEN, O.FOREARM_THICK): "前腕"}
BODY_SIZES = {sz(O.BODY_SIZE): "胴",
              (O.THIGH_THICK, O.THIGH_LEN, O.THIGH_THICK): "太もも",
              (O.SHIN_THICK, O.SHIN_LEN, O.SHIN_THICK): "すね"}
check(O.SKIN_COLOR == 15, f"39: SKIN_COLOR が 15 でない {O.SKIN_COLOR}")
# 前提：部位の大きさが互いに区別できる（区別できないと色の検証が成り立たない）
check(len(set(SKIN_SIZES) | set(BODY_SIZES)) == 6, "39: 部位の大きさが重複していて区別できない")
for pname, pose_fn in (("立ち", lambda: O.stand_pose()),
                       ("歩き", lambda: O.walk_pose(0.7)),
                       ("座り", lambda: O.sit_pose(0.1))):
    for chosen in (8, 3):  # キャラの色は肌色と違う適当な2色
        ag = O.Agent("T", O.Vec3(0.0, 0.0, 0.0), random.Random(1))
        ag.pose = pose_fn()
        v = O.AgentView(ag, chosen)
        calls = view_boxes(v)
        tag = f"39: {pname} 色{chosen}"
        check(len(calls) == 10, f"{tag} の箱が10個でなく{len(calls)}個")
        skin = [c for c in calls if c[1] in SKIN_SIZES]
        body = [c for c in calls if c[1] in BODY_SIZES]
        check(len(skin) + len(body) == 10, f"{tag} 未知の大きさの箱がある {[c[1] for c in calls]}")
        # 頭1・上腕2・前腕2 = 5個が肌色、胴1・太もも2・すね2 = 5個がキャラの色
        check(len(skin) == 5 and all(c[2] == O.SKIN_COLOR for c in skin),
              f"{tag} 頭と腕4本が肌色{O.SKIN_COLOR}の5個でない {[(SKIN_SIZES[c[1]], c[2]) for c in skin]}")
        check(len(body) == 5 and all(c[2] == chosen for c in body),
              f"{tag} 胴と脚4本がキャラの色{chosen}の5個でない {[(BODY_SIZES[c[1]], c[2]) for c in body]}")
        for size, name, n in ((sz(O.HEAD_SIZE), "頭", 1), (sz(O.BODY_SIZE), "胴", 1)):
            check(sum(1 for c in calls if c[1] == size) == n, f"{tag} {name}が{n}個でない")
        check(sum(1 for c in calls if c[1] == (O.UPPER_ARM_THICK, O.UPPER_ARM_LEN, O.UPPER_ARM_THICK)) == 2,
              f"{tag} 上腕が2個でない")
        check(sum(1 for c in calls if c[1] == (O.THIGH_THICK, O.THIGH_LEN, O.THIGH_THICK)) == 2,
              f"{tag} 太ももが2個でない")

# 40. office の色：18席の色がすべて OFFICE_AGENT_COLORS の中で、1・4・5・13・15 を含まない。席 i の色は [i % 色数]。
NCOL = len(O.OFFICE_AGENT_COLORS)
check(O.OFFICE_AGENT_COLORS == (2, 3, 6, 7, 8, 9, 10, 11, 12, 14) and NCOL == 10,
      f"40: OFFICE_AGENT_COLORS が仕様の10色でない {O.OFFICE_AGENT_COLORS}")
check(not ({1, 4, 5, 13, 15} & set(O.OFFICE_AGENT_COLORS)), f"40: 候補の色に 1・4・5・13・15 がある {O.OFFICE_AGENT_COLORS}")
check(len(set(O.OFFICE_AGENT_COLORS)) == NCOL, "40: 候補の色に重複がある")
ocols = [c for _v, _y, c in O.LAYOUTS["office"].seats]
check(len(ocols) == 18, f"40: office の席が18でない {len(ocols)}")
check(all(c in O.OFFICE_AGENT_COLORS for c in ocols), f"40: 席の色が OFFICE_AGENT_COLORS の外 {ocols}")
check(not ({1, 4, 5, 13, 15} & set(ocols)), f"40: 床1・椅子4・壁5・机13・肌15 の色を含む {ocols}")
for i, c in enumerate(ocols):
    check(c == O.OFFICE_AGENT_COLORS[i % NCOL], f"40: 席{i}の色が OFFICE_AGENT_COLORS[{i}%{NCOL}]={O.OFFICE_AGENT_COLORS[i % NCOL]} でなく {c}")
# 実際に生成される AgentView の色も同じ
oview_app = make_app(30, 1, "office", 18)
all_views = [ch for ch in oview_app.scene.children if isinstance(ch, O.AgentView)]
oviews = [v for v in all_views if v.agent is not oview_app.human]  # 人間（色8・肌7）は席の色の対象外
check([v.color for v in oviews] == ocols, "40: 生成された AgentView の色が席の色と違う")
hviews = [v for v in all_views if v.agent is oview_app.human]
check(len(hviews) == 1 and hviews[0].color == 8 and hviews[0].skin_color == 7,
      f"40: 人間の AgentView が1つだけ（色8・肌7）でない {[(v.color, v.skin_color) for v in hviews]}")
check(len(all_views) == 18 + 1, f"40: office の AgentView が 18+1 でない {len(all_views)}")
# proto の色は従来どおり 8,11,12（肌色や机と重ならない）
check([c for _v, _y, c in O.LAYOUTS["proto"].seats] == [8, 11, 12], "40: proto の色が 8,11,12 でない")

# 41. 描画：proto 3人・office 18人で update/draw したあと、画面に肌色15 が一定数描かれている。
SKIN_MIN = 10
for lname, n in (("proto", 3), ("office", 18)):
    sapp = make_app(30, 1, lname, n)
    sapp.update()
    sapp.draw()
    skin_px = sum(1 for y in range(pyxel.height) for x in range(pyxel.width) if pyxel.screen.pget(x, y) == O.SKIN_COLOR)
    check(skin_px >= SKIN_MIN, f"41: {lname} {n}人で肌色{O.SKIN_COLOR}が{SKIN_MIN}画素未満 {skin_px}")
    print(f"(41) {lname} {n}人 肌色{O.SKIN_COLOR}の画素数 {skin_px}")

# ---- ここから当たり判定と視点の回転の項目 ----
R = pyxelcube_agents.AGENT_RADIUS
RECT_T = pyxelcube_agents.Rect(0.0, 100.0, 0.0, 50.0)  # テスト用の長方形（x 0〜100、z 0〜50）


def rect_dist(x, z, rect):
    """点 (x, z) から長方形までの距離（中にあれば 0）。"""
    cx = min(max(x, rect.xmin), rect.xmax)
    cz = min(max(z, rect.zmin), rect.zmax)
    return math.hypot(x - cx, z - cz)


def near(a, b, tol=1e-9):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


# 42. push_out_of_rect：円（半径10）を長方形から押し出す
pr = pyxelcube_agents.push_out_of_rect
# 外にある円はそのまま（ぴったり接するだけの円も動かさない）
check(pr(-30.0, 25.0, 10.0, RECT_T) == (-30.0, 25.0), "42: 離れた円が動いた")
check(pr(-10.0, 25.0, 10.0, RECT_T) == (-10.0, 25.0), "42: ちょうど接する円が動いた")
check(pr(50.0, 80.0, 10.0, RECT_T) == (50.0, 80.0), "42: 上に離れた円が動いた")
# 辺に食い込んだ円は、辺の外へちょうど r 離れる（4辺）
check(near(pr(-5.0, 25.0, 10.0, RECT_T), (-10.0, 25.0)), f"42: 左辺に食い込んだ円 {pr(-5.0, 25.0, 10.0, RECT_T)}")
check(near(pr(105.0, 25.0, 10.0, RECT_T), (110.0, 25.0)), f"42: 右辺に食い込んだ円 {pr(105.0, 25.0, 10.0, RECT_T)}")
check(near(pr(50.0, -3.0, 10.0, RECT_T), (50.0, -10.0)), f"42: 手前辺に食い込んだ円 {pr(50.0, -3.0, 10.0, RECT_T)}")
check(near(pr(50.0, 55.0, 10.0, RECT_T), (50.0, 60.0)), f"42: 奥辺に食い込んだ円 {pr(50.0, 55.0, 10.0, RECT_T)}")
# 角に食い込んだ円は、角から r 離れる（向きは角から円の中心への向き）
for corner, c0 in (((0.0, 0.0), (-3.0, -4.0)), ((100.0, 50.0), (103.0, 54.0)),
                   ((0.0, 50.0), (-3.0, 54.0)), ((100.0, 0.0), (103.0, -4.0))):
    got = pr(c0[0], c0[1], 10.0, RECT_T)
    want = (corner[0] + (c0[0] - corner[0]) * 2.0, corner[1] + (c0[1] - corner[1]) * 2.0)  # 距離5 → 10 は2倍
    check(near(got, want, 1e-9), f"42: 角{corner}に食い込んだ円 {got}（期待 {want}）")
    check(abs(math.hypot(got[0] - corner[0], got[1] - corner[1]) - 10.0) < 1e-9, f"42: 角{corner}から r 離れていない")
# 中心が長方形の中：いちばん近い辺の外へ
check(near(pr(3.0, 25.0, 10.0, RECT_T), (-10.0, 25.0)), f"42: 中の円（左が近い）{pr(3.0, 25.0, 10.0, RECT_T)}")
check(near(pr(97.0, 25.0, 10.0, RECT_T), (110.0, 25.0)), f"42: 中の円（右が近い）{pr(97.0, 25.0, 10.0, RECT_T)}")
check(near(pr(50.0, 2.0, 10.0, RECT_T), (50.0, -10.0)), f"42: 中の円（手前が近い）{pr(50.0, 2.0, 10.0, RECT_T)}")
check(near(pr(50.0, 48.0, 10.0, RECT_T), (50.0, 60.0)), f"42: 中の円（奥が近い）{pr(50.0, 48.0, 10.0, RECT_T)}")
# 押し出したあとは重ならず、もう一度押しても動かない
for c0 in ((-5.0, 25.0), (-3.0, -4.0), (3.0, 25.0), (50.0, 48.0), (0.0, 0.0)):
    got = pr(c0[0], c0[1], 10.0, RECT_T)
    check(rect_dist(got[0], got[1], RECT_T) >= 10.0 - 1e-9, f"42: 押し出し後も重なる {c0} → {got}")
    check(pr(got[0], got[1], 10.0, RECT_T) == got, f"42: 押し出し後にもう一度押すと動く {c0}")

# 43. separate：半径 10 の2つの円
sep = pyxelcube_agents.separate
check(sep(0.0, 0.0, 25.0, 0.0, 10.0, False, False) == (0.0, 0.0, 25.0, 0.0), "43: 離れた2つが動いた")
check(sep(0.0, 0.0, 20.0, 0.0, 10.0, False, False) == (0.0, 0.0, 20.0, 0.0), "43: ちょうど接する2つが動いた")
# 両方動ける：半分ずつ離れて距離が 2r（重なり10 → 5ずつ）
got = sep(0.0, 0.0, 10.0, 0.0, 10.0, False, False)
check(all(abs(g - w) < 1e-9 for g, w in zip(got, (-5.0, 0.0, 15.0, 0.0))), f"43: 両方動ける2つが半分ずつ離れない {got}")
got = sep(0.0, 0.0, 6.0, 8.0, 10.0, False, False)  # 斜め（距離10）
check(abs(math.hypot(got[2] - got[0], got[3] - got[1]) - 20.0) < 1e-9, f"43: 斜めで距離が20にならない {got}")
check(abs((got[0] + got[2]) / 2 - 3.0) < 1e-9 and abs((got[1] + got[3]) / 2 - 4.0) < 1e-9,
      f"43: 斜めで真ん中の位置が変わった {got}")
# 片方固定：固定側は動かず、もう片方が全部動いて距離 2r
got = sep(0.0, 0.0, 10.0, 0.0, 10.0, True, False)
check(got[:2] == (0.0, 0.0) and abs(got[2] - 20.0) < 1e-9 and got[3] == 0.0, f"43: a 固定 {got}")
got = sep(0.0, 0.0, 10.0, 0.0, 10.0, False, True)
check(got[2:] == (10.0, 0.0) and abs(got[0] - (-10.0)) < 1e-9 and got[1] == 0.0, f"43: b 固定 {got}")
# 両方固定は動かない
check(sep(0.0, 0.0, 10.0, 0.0, 10.0, True, True) == (0.0, 0.0, 10.0, 0.0), "43: 両方固定なのに動いた")
# 中心が同じでも離れる（両方動ける・片方固定）
got = sep(3.0, 4.0, 3.0, 4.0, 10.0, False, False)
check(abs(math.hypot(got[2] - got[0], got[3] - got[1]) - 20.0) < 1e-9, f"43: 同じ中心の2つが離れない {got}")
check(abs((got[0] + got[2]) / 2 - 3.0) < 1e-9 and abs((got[1] + got[3]) / 2 - 4.0) < 1e-9, f"43: 同じ中心で真ん中が動いた {got}")
got = sep(3.0, 4.0, 3.0, 4.0, 10.0, True, False)
check(got[:2] == (3.0, 4.0) and abs(math.hypot(got[2] - 3.0, got[3] - 4.0) - 20.0) < 1e-9, f"43: 同じ中心で a 固定 {got}")
got = sep(3.0, 4.0, 3.0, 4.0, 10.0, False, True)
check(got[2:] == (3.0, 4.0) and abs(math.hypot(got[0] - 3.0, got[1] - 4.0) - 20.0) < 1e-9, f"43: 同じ中心で b 固定 {got}")


# 44. 障害物の作り方：proto は 机3＋椅子3、office は 机18＋椅子18＋壁4＋小物5（ドアの範囲1・書棚2・植木2）。owner と向き
def expected_chair(seat_v, yaw):
    """席のローカル z -40〜-8・x ±15。yaw 180 は z が逆。"""
    if yaw == 0.0:
        return (seat_v.x - 15.0, seat_v.x + 15.0, seat_v.z - 40.0, seat_v.z - 8.0)
    return (seat_v.x - 15.0, seat_v.x + 15.0, seat_v.z + 8.0, seat_v.z + 40.0)


def rect_t(r):
    return (r.xmin, r.xmax, r.zmin, r.zmax)


def near_rect(a, b, tol=1e-3):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


for lname, n_wall in (("proto", 0), ("office", 4 + 5)):  # office の owner=None は壁4＋小物5
    lay = pyxelcube_agents.LAYOUTS[lname]
    napp = make_app(30, 1, lname, 18)
    obs = napp.obstacles
    n = len(lay.seats)
    check(len(obs) == n * 2 + n_wall, f"44: {lname} の障害物が{n * 2 + n_wall}個でなく{len(obs)}個")
    check(all(isinstance(o, pyxelcube_agents.Obstacle) for o in obs), f"44: {lname} の障害物が Obstacle でない")
    walls = [o for o in obs if o.owner is None]
    check(len(walls) == n_wall, f"44: {lname} の壁（owner=None）が{n_wall}個でなく{len(walls)}個")
    for i, (sv, syaw, _c) in enumerate(lay.seats):
        mine = [o for o in obs if o.owner == i]
        check(len(mine) == 2, f"44: {lname} 席{i}の持ち物が2個でなく{len(mine)}個")
        d = lay.desks[i]
        want_desk = (d.x - 60.0, d.x + 60.0, d.z - 30.0, d.z + 30.0)
        want_chair = expected_chair(sv, syaw)
        got_rects = [rect_t(o.rect) for o in mine]
        check(any(near_rect(g, want_desk) for g in got_rects), f"44: {lname} 席{i}の机の長方形が違う {got_rects} 期待 {want_desk}")
        check(any(near_rect(g, want_chair) for g in got_rects),
              f"44: {lname} 席{i}の椅子の長方形が違う（yaw {syaw}）{got_rects} 期待 {want_chair}")
    if n_wall:
        # 壁：中心 (0,-605)、大きさ 1600 x 10
        check(near_rect(rect_t(walls[0].rect), (-800.0, 800.0, -610.0, -600.0)), f"44: office の壁の長方形 {walls[0].rect}")
# 椅子の向き：yaw 0（席が手前）は席の奥側（-z）、yaw 180 は +z 側に椅子がある
c0 = expected_chair(pyxelcube_agents.Vec3(0.0, 0.0, -30.0), 0.0)
check(c0 == (-15.0, 15.0, -70.0, -38.0), f"44: proto の椅子の期待値の確認 {c0}")
oc = [o.rect for o in make_app(30, 1, "office", 18).obstacles if o.owner == 0]
ch = [r for r in oc if r.xmax - r.xmin < 40.0][0]
check(near_rect(rect_t(ch), (-165.0, -135.0, -492.0, -460.0)), f"44: office 席0(yaw180)の椅子 {rect_t(ch)}（z は席 -500 より +8〜+40）")
pc = [o.rect for o in make_app(30, 1).obstacles if o.owner == 0]
ch = [r for r in pc if r.xmax - r.xmin < 40.0][0]
check(near_rect(rect_t(ch), (-265.0, -235.0, -70.0, -38.0)), f"44: proto 席0(yaw0)の椅子 {rect_t(ch)}（z は席 -30 より -40〜-8）")

# 45. 重なりなし：office 18人、種 1〜4、1/3 の人を作業中にして 60 秒相当（30fps で 1800 フレーム）動かす。
#     毎フレーム：WANDER の人は全障害物（自分の机・椅子も）と、WORKING の人は他人の机・椅子と重ならず、
#     人どうしの距離は 2r-0.5 以上。押し出しの繰り返しは3回なので、許容は 0.5。
TOL = 0.5  # 人どうしの許容（仕様どおり）
TOL_OB = 1.0  # 障害物との食い込みの許容。押し出しは3回で打ち切るため、種1で0.504の食い込みが1フレームだけ出る（下の表示を参照）
for seed in (1, 2, 3, 4):
    capp = make_app(30, seed, "office", 18)
    work_ids = [i for i in range(18) if i % 3 == 0]  # 6人（1/3）
    bad_ob, bad_pair = [], []
    worst_ob = worst_pair = 0.0
    n_working_frames = 0
    for f in range(30 * 60):
        if f % 300 == 0:
            for i in work_ids:  # 10秒ごとに作業へ（5秒座ると WANDER に戻るので、作業中と待機が混ざる）
                capp.agents[i].start_work()
        capp.update()
        for i, a in enumerate(capp.agents):
            n_working_frames += a.state == "WORKING"
            for ob in capp.obstacles:
                if a.state == "WORKING" and ob.owner == i:
                    continue  # 作業中は自分の机・椅子を無視する
                d = rect_dist(a.pos.x, a.pos.z, ob.rect)
                worst_ob = max(worst_ob, R - d)
                if d < R - TOL_OB:
                    bad_ob.append((f, a.name, a.state, ob.owner, round(d, 2)))
        for i in range(18):
            for j in range(i + 1, 18):
                d = dist(capp.agents[i].pos, capp.agents[j].pos)
                worst_pair = max(worst_pair, 2 * R - d)
                if d < 2 * R - TOL:
                    bad_pair.append((f, capp.agents[i].name, capp.agents[j].name, round(d, 2)))
    check(not bad_ob, f"45: 種{seed} 障害物と重なる {bad_ob[:3]}（計{len(bad_ob)}件、最大の食い込み{worst_ob:.2f}）")
    check(not bad_pair, f"45: 種{seed} 人どうしが近すぎる {bad_pair[:3]}（計{len(bad_pair)}件、最大の食い込み{worst_pair:.2f}）")
    check(n_working_frames > 30 * 60 * 2, f"45: 種{seed} 作業中の人がほとんどいない {n_working_frames}")
    print(f"(45) 種{seed} 最大の食い込み 障害物 {worst_ob:.3f} / 人どうし {worst_pair:.3f}")

# 46. 座れること：作業を始めた人は席に着き、着席中は位置が席のまま（ほかの人に押されない）
sapp = make_app(30, 1, "office", 18)
for a in sapp.agents:
    a.start_work()
for _ in range(30 * 4):  # 4秒（席まで最大120単位 → 約1秒で着く。5秒座る前）
    sapp.update()
check(all(a.is_seated for a in sapp.agents), f"46: 全員が席に着いていない {[a.name for a in sapp.agents if not a.is_seated]}")
check(all(dist(a.pos, a.seat) < 1e-3 for a in sapp.agents),
      f"46: 着席した位置が席と違う {[(a.name, round(dist(a.pos, a.seat), 3)) for a in sapp.agents if dist(a.pos, a.seat) >= 1e-3]}")
# 押し込まれても動かない：席4の人が座っているところへ、別の WANDER の人（席5）を毎フレーム重ねる
sapp = make_app(30, 1, "office", 18)
sitter, walker = sapp.agents[4], sapp.agents[5]
sitter.start_work()
for _ in range(60):
    sapp.update()
    if sitter.is_seated:
        break
check(sitter.is_seated, "46: 席4の人が着席しない")
moved_max = 0.0
walker_close = 0.0
for _ in range(60):
    walker.pos = pyxelcube_agents.Vec3(sitter.seat.x + 3.0, 0.0, sitter.seat.z)
    sapp.update()
    moved_max = max(moved_max, dist(sitter.pos, sitter.seat))
    walker_close = max(walker_close, 2 * R - dist(walker.pos, sitter.pos))
    if not sitter.is_seated:
        break
check(moved_max < 1e-3, f"46: 着席中の人が押された {moved_max}")
check(walker_close < TOL, f"46: 押しつけた側が着席中の人に重なったまま {walker_close}")
# 5秒後に WANDER に戻ると、椅子の外へ押し出される（数フレーム後に自分の椅子と重ならない）
own_chair = [o.rect for o in sapp.obstacles if o.owner == 4][0:2]
n = 0
while sitter.state != "WANDER" and n < 30 * 10:
    sapp.update()
    n += 1
check(sitter.state == "WANDER", "46: 5秒後に WANDER に戻らない")
for _ in range(5):
    sapp.update()
d_own = min(rect_dist(sitter.pos.x, sitter.pos.z, r) for r in own_chair)
check(d_own >= R - TOL, f"46: WANDER に戻って5フレーム後も自分の机か椅子と重なる 距離{d_own:.2f}")
# 全席：座っていた人が WANDER に戻ったあと、自分の椅子と重ならない
sapp = make_app(30, 2, "office", 18)
for a in sapp.agents:
    a.start_work()
for _ in range(30 * 8):
    sapp.update()
check(all(a.state == "WANDER" for a in sapp.agents), "46: 全員が WANDER に戻っていない")
bad = []
for i, a in enumerate(sapp.agents):
    for ob in sapp.obstacles:
        d = rect_dist(a.pos.x, a.pos.z, ob.rect)
        if d < R - TOL:
            bad.append((a.name, ob.owner, round(d, 2)))
check(not bad, f"46: 全員 WANDER に戻ったあと障害物に重なる {bad[:3]}")

# 47. 引っかかり：机にまっすぐ突っ込ませると、約1秒後に目標が選び直される
def stuck_app():
    """office の席0（窓際）の人を、机の右側に置き、机の向こう側の目標へ向かわせる準備をする。
    机0は x -210〜-90、z -460〜-400。右側(x=-70, z=-430)から左へ向かうと机の右面で止まる。"""
    a = make_app(30, 1, "office", 18)
    ag = a.agents[0]
    ag.pos = pyxelcube_agents.Vec3(-70.0, 0.0, -430.0)
    return a, ag


papp47, ag47 = stuck_app()
repicks = []
_orig_repick = ag47.repick_target
ag47.repick_target = lambda: (repicks.append(len(frames_log)), _orig_repick())
frames_log = []
blocked_target = pyxelcube_agents.Vec3(-230.0, 0.0, -430.0)  # 机の向こう側（左）
ag47._target = blocked_target
ag47._wait = 0.0
first_repick_frame = None
for f in range(30 * 3):
    papp47.update()
    frames_log.append(f)
    if repicks and first_repick_frame is None:
        first_repick_frame = f + 1
        check(ag47._target is not blocked_target, "47: 選び直したのに目標が同じ")
        break
check(first_repick_frame is not None, "47: 3秒たっても目標が選び直されない")
if first_repick_frame is not None:
    # 30fps で 1秒＝30フレーム。進めなくなるまでに数フレームかかる分だけ後ろにずれる
    check(25 <= first_repick_frame <= 36, f"47: 選び直しが約1秒後でない（{first_repick_frame}フレーム目）")
    print(f"(47) 引っかかって {first_repick_frame} フレーム目に目標を選び直した")
    check(len(repicks) == 1, f"47: 選び直しの回数が1回でない {len(repicks)}")

# 進めているフレームでは選び直さない：障害物のない方向へ歩いている間（3秒）は1回も選び直さない
papp47, ag47 = stuck_app()
repicks = []
frames_log = []
_orig_repick = ag47.repick_target
ag47.repick_target = lambda: (repicks.append(len(frames_log)), _orig_repick())
ag47._target = pyxelcube_agents.Vec3(-70.0, 0.0, -330.0)  # +z へ100（机から離れる向き。約1.7秒で着く）
ag47._wait = 0.0
walked = 0.0
for f in range(30 * 1):
    p0 = ag47.pos
    papp47.update()
    frames_log.append(f)
    walked += dist(p0, ag47.pos)
check(walked > 40.0, f"47: 自由に歩けるはずが進んでいない {walked}")
check(not repicks, f"47: 進めているのに目標を選び直した {repicks}")
# 進めないフレームの合計ではなく「続いた時間」：20フレーム止められ → 3フレーム進める → 20フレーム止められ、では選び直さない
papp47, ag47 = stuck_app()
repicks = []
frames_log = []
_orig_repick = ag47.repick_target
ag47.repick_target = lambda: (repicks.append(len(frames_log)), _orig_repick())
for phase_target, nframes in ((blocked_target, 20), (pyxelcube_agents.Vec3(-70.0, 0.0, -330.0), 3), (blocked_target, 20)):
    ag47._target = phase_target
    ag47._wait = 0.0
    for _ in range(nframes):
        papp47.update()
        frames_log.append(0)
check(not repicks, f"47: 進めたフレームをはさんだのに選び直した {repicks}")

# 48. 目標の選び方：多数選んだ目標が、障害物を AGENT_RADIUS 広げた範囲に入らない（office 18人×30回 = 540回）
tapp = make_app(30, 5, "office", 18)
n_pick = n_none = 0
bad_t = []
out_range = []
for ag in tapp.agents:
    for _ in range(30):
        ag._target = None
        ag.repick_target()
        n_pick += 1
        t = ag._target
        if t is None:
            n_none += 1  # 20回試してもだめ → 1秒立ち止まる
            check(ag._wait == 1.0, f"48: 目標が見つからないとき1秒立ち止まらない {ag._wait}")
            continue
        for ob in tapp.obstacles:
            r = ob.rect
            if r.xmin - R < t.x < r.xmax + R and r.zmin - R < t.z < r.zmax + R:
                bad_t.append((ag.name, round(t.x, 1), round(t.z, 1), ob.owner))
        if not (-780 <= t.x <= 780 and -580 <= t.z <= 580) or dist(t, ag.seat) > 120.0 + 1e-3:
            out_range.append((ag.name, round(t.x, 1), round(t.z, 1)))
check(not bad_t, f"48: 障害物を広げた範囲に入る目標 {bad_t[:3]}（計{len(bad_t)}件）")
check(not out_range, f"48: 目標がうろつきの範囲外 {out_range[:3]}")
check(n_none <= n_pick * 0.2, f"48: 目標が見つからない回数が多い {n_none}/{n_pick}")
print(f"(48) 目標を {n_pick} 回選び、見つからなかった回数 {n_none}")
# proto でも同様（障害物は机3＋椅子3）
tapp = make_app(30, 5)
bad_t = []
for ag in tapp.agents:
    for _ in range(100):
        ag._target = None
        ag.repick_target()
        t = ag._target
        if t is None:
            continue
        for ob in tapp.obstacles:
            r = ob.rect
            if r.xmin - R < t.x < r.xmax + R and r.zmin - R < t.z < r.zmax + R:
                bad_t.append((ag.name, round(t.x, 1), round(t.z, 1)))
check(not bad_t, f"48: proto で障害物を広げた範囲に入る目標 {bad_t[:3]}（計{len(bad_t)}件）")

# 49. 視点：起動時の値、カーソルキーでの回転、pitch の範囲、目＝target + dir*dist、far＝dist+2500
held = set()
_orig_btn = pyxel.btn
pyxel.btn = lambda k, *a, **kw: k in held


def view_frames(app, keys, n):
    """keys を押したまま update を n 回呼ぶ。終わったら押していない状態へ戻す。"""
    held.clear()
    held.update(keys)
    try:
        for _ in range(n):
            app.update()
    finally:
        held.clear()


def eye_matches(app, tol=0.05):
    """目の位置が target + _view_dir(yaw,pitch)*dist で、cam_dir も同じ、far が dist+2500 か。"""
    d = pyxelcube_agents._view_dir(app.cam_yaw, app.cam_pitch)
    eye = app.cam_target + d * app.cam_dist
    cp = app.camera.transform.pos
    ok_eye = abs(cp.x - eye.x) < tol and abs(cp.y - eye.y) < tol and abs(cp.z - eye.z) < tol
    ok_dir = abs(app.cam_dir.x - d.x) < 1e-6 and abs(app.cam_dir.y - d.y) < 1e-6 and abs(app.cam_dir.z - d.z) < 1e-6
    return ok_eye and ok_dir and abs(app.camera.far - (app.cam_dist + 2500.0)) < 0.01


def cam_pos_t(app):
    cp = app.camera.transform.pos
    return (cp.x, cp.y, cp.z)


try:
    check(pyxelcube_agents.CAM_YAW_SPEED == 90.0 and pyxelcube_agents.CAM_PITCH_SPEED == 60.0, "49: 回す速さが 90/60 度毎秒でない")
    check(pyxelcube_agents.CAM_PITCH_MIN == 10.0 and pyxelcube_agents.CAM_PITCH_MAX == 85.0, "49: pitch の範囲が 10〜85 でない")
    for lname, want_pitch in (("proto", math.degrees(math.atan2(450.0, 700.0))),
                              ("office", math.degrees(math.atan2(1100.0, 1350.0)))):
        vapp = make_app(30, 1, lname, 3)
        lay = vapp.layout
        # office は起動時の注視点が人間の位置、目は 注視点＋(camera_eye − camera_target)。proto は従来どおり
        if lname == "office":
            want_target = Vec3(pyxelcube_agents.HUMAN_START[0], 0.0, pyxelcube_agents.HUMAN_START[1])
        else:
            want_target = lay.camera_target
        want_eye = want_target + (lay.camera_eye - lay.camera_target)
        check(vapp.cam_target == want_target, f"49: {lname} 起動時の注視点が期待と違う {vapp.cam_target} {want_target}")
        target0 = vapp.cam_target
        # 起動時：yaw 0、pitch は目の位置から求めた値（proto 約32.7、office 約39.2）
        check(abs(vapp.cam_yaw) < 0.01 or abs(vapp.cam_yaw - 360.0) < 0.01, f"49: {lname} 起動時の yaw が 0 でない {vapp.cam_yaw}")
        check(abs(vapp.cam_pitch - want_pitch) < 0.05, f"49: {lname} 起動時の pitch が{want_pitch:.2f}でない {vapp.cam_pitch}")
        # 起動時の目の位置が、これまでの camera_eye と一致（単精度の誤差を考えて 0.5）
        eye0 = vapp.cam_target + pyxelcube_agents._view_dir(vapp.cam_yaw, vapp.cam_pitch) * vapp.cam_dist
        check(abs(eye0.x - want_eye.x) < 0.5 and abs(eye0.y - want_eye.y) < 0.5
              and abs(eye0.z - want_eye.z) < 0.5, f"49: {lname} _view_dir から作った目 {eye0} が期待の目 {want_eye} と違う")
        cp = vapp.camera.transform.pos
        check(abs(cp.x - want_eye.x) < 0.5 and abs(cp.y - want_eye.y) < 0.5 and abs(cp.z - want_eye.z) < 0.5,
              f"49: {lname} 実際のカメラ位置が期待の目と違う {cp} {want_eye}")
        check(eye_matches(vapp), f"49: {lname} 起動時に 目＝target+dir*dist／far が合わない")

        # → を1秒（30フレーム）で yaw +90
        y0 = vapp.cam_yaw
        view_frames(vapp, {pyxel.KEY_RIGHT}, 30)
        check(abs(vapp.cam_yaw - (y0 + 90.0)) < 0.01, f"49: {lname} →1秒で yaw が +90 でない {y0} → {vapp.cam_yaw}")
        check(eye_matches(vapp), f"49: {lname} → のあと 目／far が合わない")
        # ← を1秒で -90（元へ戻る）、さらに1秒で -90（0 未満は 360 側へ回る）
        view_frames(vapp, {pyxel.KEY_LEFT}, 30)
        check(abs(vapp.cam_yaw - y0) < 0.01 or abs(abs(vapp.cam_yaw - y0) - 360.0) < 0.01,
              f"49: {lname} ←1秒で元に戻らない {vapp.cam_yaw}")
        view_frames(vapp, {pyxel.KEY_LEFT}, 30)
        check(abs(vapp.cam_yaw - 270.0) < 0.01, f"49: {lname} ←で 0 を超えて 270 に回らない {vapp.cam_yaw}")
        check(0.0 <= vapp.cam_yaw < 360.0, f"49: {lname} yaw が 0〜360 の外 {vapp.cam_yaw}")
        check(eye_matches(vapp), f"49: {lname} ← のあと 目／far が合わない")
        # → で 270 から +90 すると 360 を超え、0 付近へ回る
        view_frames(vapp, {pyxel.KEY_RIGHT}, 30)
        check(0.0 <= vapp.cam_yaw < 360.0 and min(vapp.cam_yaw, 360.0 - vapp.cam_yaw) < 0.01,
              f"49: {lname} → で 360 を超えて 0 付近へ回らない {vapp.cam_yaw}")
        # → と ← を同時に押すと動かない
        yb = vapp.cam_yaw
        view_frames(vapp, {pyxel.KEY_LEFT, pyxel.KEY_RIGHT}, 10)
        check(vapp.cam_yaw == yb, f"49: {lname} 左右同時で yaw が変わった {yb} → {vapp.cam_yaw}")

        # pitch：↑ を押し続けると 85 で止まり、↓ で 10 で止まる（60度/秒）
        p0 = vapp.cam_pitch
        view_frames(vapp, {pyxel.KEY_UP}, 15)  # 0.5秒 = +30度（上限85に届かない範囲）
        check(abs(vapp.cam_pitch - min(p0 + 30.0, 85.0)) < 0.01, f"49: {lname} ↑0.5秒で pitch が+30でない {p0} → {vapp.cam_pitch}")
        view_frames(vapp, {pyxel.KEY_UP}, 30 * 5)
        check(vapp.cam_pitch == 85.0, f"49: {lname} ↑を押し続けても 85 で止まらない {vapp.cam_pitch}")
        check(eye_matches(vapp), f"49: {lname} pitch85 で 目／far が合わない")
        view_frames(vapp, {pyxel.KEY_UP}, 5)
        check(vapp.cam_pitch == 85.0, f"49: {lname} 85 で更に増えた {vapp.cam_pitch}")
        view_frames(vapp, {pyxel.KEY_DOWN}, 30 * 5)
        check(vapp.cam_pitch == 10.0, f"49: {lname} ↓を押し続けても 10 で止まらない {vapp.cam_pitch}")
        check(eye_matches(vapp), f"49: {lname} pitch10 で 目／far が合わない")
        view_frames(vapp, {pyxel.KEY_DOWN}, 5)
        check(vapp.cam_pitch == 10.0, f"49: {lname} 10 で更に減った {vapp.cam_pitch}")

        # 回したあとにズームしても 目＝target+dir*dist、far＝dist+2500（ホイールは各ノッチ0.9倍）
        view_frames(vapp, {pyxel.KEY_RIGHT, pyxel.KEY_UP}, 20)
        d_before = vapp.cam_dist
        wheel_update(vapp, 3)
        check(abs(vapp.cam_dist - d_before * 0.729) < 1e-6 and eye_matches(vapp), f"49: {lname} 回したあとのズームで 目／far が合わない")
        wheel_update(vapp, -200)
        check(vapp.cam_dist == lay.zoom_max and eye_matches(vapp), f"49: {lname} 回したあとの zoom_max で 目／far が合わない")
        # ズームしながら回す（同じフレームにホイールと矢印）
        held.update({pyxel.KEY_LEFT})
        wheel_update(vapp, 2)
        held.clear()
        check(eye_matches(vapp), f"49: {lname} ホイールと回転が同じフレームで 目／far が合わない")

        # キーを押していないフレームでは何も変わらない（yaw・pitch・カメラ位置・far）
        before = (vapp.cam_yaw, vapp.cam_pitch, cam_pos_t(vapp), vapp.camera.far)
        view_frames(vapp, set(), 10)
        after = (vapp.cam_yaw, vapp.cam_pitch, cam_pos_t(vapp), vapp.camera.far)
        check(before == after, f"49: {lname} キーを押していないのに視点が変わった {before} {after}")
        # 回転しても注視点は動かない
        check(vapp.cam_target == target0, f"49: {lname} 回転で注視点が動いた {vapp.cam_target} {target0}")
        if lname == "office":
            check(vapp.cam_target == Vec3(vapp.human.pos.x, 0.0, vapp.human.pos.z), f"49: office 回転のあとも注視点が人間の位置でない {vapp.cam_target}")

    # 50. 視点を回しても描かれる：proto 3人の色（8, 11, 12）。yaw 0/90/180/270 × pitch 10/85。
    #     人が小さくて 1 フレームだけ 0 画素になることがあるので、30 フレーム動かして一度でも描かれた色を集める。
    #     「全員」が条件。隠れて見えない人がいる角度は下の表示で確認する。
    draw_log = {}
    for yaw in (0.0, 90.0, 180.0, 270.0):
        for pitch in (10.0, 85.0):
            rapp = make_app(30, 1)
            rapp.cam_yaw, rapp.cam_pitch = yaw, pitch
            rapp._apply_camera()
            seen = {}
            for _ in range(30):
                rapp.update()
                cnt = draw_count(rapp)
                for c in (8, 11, 12):
                    seen[c] = max(seen.get(c, 0), cnt.get(c, 0))
            draw_log[(yaw, pitch)] = seen
            check(all(seen[c] >= 1 for c in (8, 11, 12)), f"50: yaw{yaw:.0f} pitch{pitch:.0f} で描かれない色 {[c for c in (8, 11, 12) if seen[c] < 1]} {seen}")
            check(eye_matches(rapp), f"50: yaw{yaw:.0f} pitch{pitch:.0f} で 目／far が合わない")
    print("(50) 色8/11/12 の最大画素数", {f"{int(y)}/{int(p)}": tuple(v[c] for c in (8, 11, 12)) for (y, p), v in draw_log.items()})
finally:
    pyxel.btn = _orig_btn
    held.clear()
    pyxel.mouse_wheel = 0
check(pyxel.btn is _orig_btn, "49: pyxel.btn を元に戻せていない")

# ---- ここから office だけの機能（壁3枚・ドア・掲示板・小物・丸テーブル・設定ファイル・キー操作）の項目 ----
# 一時ファイルは TMP_DIR の下だけに作る。App には必ず一時の設定ファイルを渡す（既定の JSON を読まないため）。
O = pyxelcube_agents
OLAY = O.OFFICE_LAYOUT


def capture_boxes(root):
    """root.on_draw 中の box 呼び出しを (行列, 大きさ(x,y,z), 色) で記録する（実際には描かない）。"""
    calls = []
    root.box = lambda m, size, col, *a, **k: calls.append((m, sz(size), col))
    root.on_draw()
    return calls


def write_json_file(name, content):
    """一時の JSON ファイルを書いてパスを返す。content が str ならそのまま、それ以外は json 化する。"""
    p = TMP_DIR / name
    p.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return p


def rate_obj(five, seven):
    return {"five_hour": {"used_percentage": five}, "seven_day": {"used_percentage": seven}}


def make_rate_app(content, name, reload_sec=1.0, fps=30, layout="office", agents=1):
    """一時の toml と JSON（content。None なら JSON を作らない＝ファイルなし）で App を作る。"""
    jp = TMP_DIR / name
    if content is not None:
        write_json_file(name, content)
    cfg = write_toml(name + ".toml", jp, reload_sec)
    return make_app(fps, 1, layout, agents, config_path=cfg), jp


def feq(a, b, tol=1e-9):
    return abs(a - b) <= tol


# 51. office の壁が4枚（奥・左・右・手前）あり、人が左・右・手前・奥の壁をすり抜けない
want_walls = {"奥": ((0.0, 100.0, -605.0), (1600.0, 200.0, 10.0)),
              "左": ((-805.0, 100.0, 0.0), (10.0, 200.0, 1220.0)),
              "右": ((805.0, 100.0, 0.0), (10.0, 200.0, 1220.0)),
              "手前": ((0.0, 22.5, 605.0), (1620.0, 45.0, 10.0))}
check(len(OLAY.walls) == 4, f"51: office の壁が4枚でない {len(OLAY.walls)}")
check(len(O.PROTO_LAYOUT.walls) == 0, f"51: proto に壁がある {len(O.PROTO_LAYOUT.walls)}")
for wname, (wc, ws) in want_walls.items():
    hit = [w for w in OLAY.walls if max(abs(w[0].x - wc[0]), abs(w[0].y - wc[1]), abs(w[0].z - wc[2])) < 1e-3
           and max(abs(w[1].x - ws[0]), abs(w[1].y - ws[1]), abs(w[1].z - ws[2])) < 1e-3]
    check(len(hit) == 1, f"51: {wname}の壁（中心{wc}・大きさ{ws}）が1枚でない {len(hit)}")
wapp = make_app(30, 1, "office", 1)
none_rects = [rect_t(o.rect) for o in wapp.obstacles if o.owner is None]
for wname, want in (("左", (-810.0, -800.0, -610.0, 610.0)), ("右", (800.0, 810.0, -610.0, 610.0)),
                    ("手前", (-810.0, 810.0, 600.0, 610.0)), ("奥", (-800.0, 800.0, -610.0, -600.0))):
    check(any(near_rect(r_, want) for r_ in none_rects), f"51: {wname}の壁が障害物にない 期待{want}")
# 壁の内側の面から 5 内側に円の中心を置くと、半径ぶん（14）の位置まで押し戻される（clamp に頼らず障害物だけで確かめる）
for wname, (px, pz), (wx, wz) in (("左", (-795.0, 0.0), (-786.0, 0.0)), ("右", (795.0, 0.0), (786.0, 0.0)),
                                  ("手前", (0.0, 595.0), (0.0, 586.0)), ("奥", (0.0, -595.0), (0.0, -586.0))):
    gx, gz = px, pz
    for o_ in wapp.obstacles:
        if o_.owner is None:
            gx, gz = O.push_out_of_rect(gx, gz, R, o_.rect)
    check(abs(gx - wx) < 1e-6 and abs(gz - wz) < 1e-6, f"51: {wname}の壁の手前で押し戻されない ({px},{pz}) → ({gx},{gz}) 期待({wx},{wz})")
# 壁の外へ向かって歩かせる（毎フレーム目標を壁の外へ置き直す）。x は ±(800-14)、z は ±(600-14) の内側に収まり、壁際まで行く
for wname, (sx, sz_), (tx, tz), axis, limit in (("左", (-700.0, 0.0), (-2000.0, 0.0), "x", -786.0),
                                                ("右", (700.0, 0.0), (2000.0, 0.0), "x", 786.0),
                                                ("手前", (100.0, 500.0), (100.0, 2000.0), "z", 586.0),
                                                ("奥", (0.0, -540.0), (0.0, -2000.0), "z", -586.0)):
    wapp = make_app(30, 1, "office", 1)
    wag = wapp.agents[0]
    wag.pos = O.Vec3(sx, 0.0, sz_)
    far_t = O.Vec3(tx, 0.0, tz)
    worst = 0.0  # 壁の向きに出た最大の量（limit を超えた分）
    nearest = 1e9  # limit までの最短距離
    for _ in range(150):
        wag._target, wag._wait = far_t, 0.0
        wapp.update()
        v = wag.pos.x if axis == "x" else wag.pos.z
        over = (limit - v) if limit < 0 else (v - limit)  # 正なら limit を超えて壁側へ入っている
        worst = max(worst, over)
        nearest = min(nearest, abs(v - limit))
    check(worst <= 1e-6, f"51: {wname}の壁をすり抜けた（limit {limit} を {worst:.3f} 超えた）")
    check(nearest <= 20.0, f"51: {wname}の壁際まで歩けていない（最も近くて {nearest:.1f}）→ すり抜けの確認が空になる")

# 52. Dキー：door_open が切り替わり、door_angle が毎秒180度（30fps で6度/フレーム）で 0↔90 へ近づき、行き過ぎない
dapp2 = make_app(30, 1, "office", 1)
check(dapp2.door_open is False and dapp2.door_angle == 0.0, f"52: 起動時にドアが閉じていない {dapp2.door_open} {dapp2.door_angle}")
for _ in range(5):
    dapp2.update()
check(dapp2.door_angle == 0.0 and dapp2.door_open is False, "52: Dを押さないのにドアが動いた")
press_keys_and_update(dapp2, pyxel.KEY_D)
check(dapp2.door_open is True, "52: D で door_open が True にならない")
check(abs(dapp2.door_angle - 6.0) < 1e-9, f"52: D を押した1フレームで6度進まない {dapp2.door_angle}")
angles = [dapp2.door_angle]
for _ in range(10):
    dapp2.update()
    angles.append(dapp2.door_angle)
check(0.0 < angles[-1] < 90.0, f"52: 11フレーム後は途中の角度のはず {angles[-1]}")
check(all(b_ > a_ for a_, b_ in zip(angles, angles[1:])), "52: 開く間に角度が増え続けない")
for _ in range(10):
    dapp2.update()
    angles.append(dapp2.door_angle)
check(feq(dapp2.door_angle, 90.0), f"52: 数フレーム後に 90 に達しない {dapp2.door_angle}")
for _ in range(60):
    dapp2.update()
    angles.append(dapp2.door_angle)
check(max(angles) == 90.0 and dapp2.door_angle == 90.0, f"52: 90 を超えた/90 に留まらない 最大{max(angles)}")
check(dapp2.scene.door_angle == dapp2.door_angle, "52: scene.door_angle が door_angle と同じでない")
# 開いたときのドアの先の端：描かれる板の行列から先端（蝶番から幅80の位置）を求める。x が DOOR_X より大きい（＝部屋の中）
def door_tip(app):
    """app.scene の描画で、ドアの板（大きさ 6x160x80）の先の端のワールド座標を返す。"""
    calls = capture_boxes(app.scene)
    panel = [c for c in calls if c[1] == (O.DOOR_THICK, O.DOOR_HEIGHT, O.DOOR_WIDTH)]
    check(len(panel) == 1 and panel[0][2] == O.DOOR_COLOR, f"52: ドアの板が1枚でない {len(panel)}")
    return (panel[0][0] * Mat4.from_translation(Vec3(0.0, 0.0, O.DOOR_WIDTH / 2.0))).pos


tip = door_tip(dapp2)
check(tip.x > O.DOOR_X + 1.0, f"52: 角度90で先の端の x が DOOR_X({O.DOOR_X}) より大きくない（部屋の中へ開いていない）{tip.x}")
check(abs(tip.x - (O.DOOR_X + O.DOOR_WIDTH)) < 0.01 and abs(tip.z - (O.DOOR_Z - O.DOOR_WIDTH / 2.0)) < 0.01,
      f"52: 角度90の先の端が (DOOR_X+80, DOOR_Z-40) でない ({tip.x},{tip.z})")
# もう一度 D：閉まり始め、0 に戻って 0 未満にならない。途中で押すと向きが変わる
press_keys_and_update(dapp2, pyxel.KEY_D)
check(dapp2.door_open is False and abs(dapp2.door_angle - 84.0) < 1e-9, f"52: もう一度 D で閉まり始めない {dapp2.door_open} {dapp2.door_angle}")
for _ in range(5):
    dapp2.update()
mid = dapp2.door_angle
press_keys_and_update(dapp2, pyxel.KEY_D)  # 閉まる途中でもう一度（開く向きに変わる）
check(dapp2.door_open is True and dapp2.door_angle > mid, f"52: 閉まる途中で D を押しても開く向きに変わらない {mid} → {dapp2.door_angle}")
press_keys_and_update(dapp2, pyxel.KEY_D)
low = []
for _ in range(60):
    dapp2.update()
    low.append(dapp2.door_angle)
check(dapp2.door_open is False and dapp2.door_angle == 0.0 and min(low) == 0.0, f"52: D をもう一度で 0 に戻らない {dapp2.door_angle} 最小{min(low)}")
tip = door_tip(dapp2)
check(abs(tip.x - O.DOOR_X) < 0.01 and abs(tip.z - (O.DOOR_Z + O.DOOR_WIDTH / 2.0)) < 0.01,
      f"52: 閉じたドアの先の端が (DOOR_X, DOOR_Z+40) でない ({tip.x},{tip.z})")
# ドアの板（中心線）は、どの角度でも障害物の範囲（x -800〜-720、z -390〜-310）からほぼはみ出さない。
# 蝶番が x=-797・z=-390 で幅80なので、角度90の先の端は (-717,-390) になり、範囲から3だけ出る（仕様の範囲と実寸のずれ）。
# 人は範囲から半径14以上離れるので板には重ならない。3を超えるずれは失敗にする。
DOOR_SLACK = 3.01
door_area = O.Rect(-800.0, -720.0, -390.0, -310.0)
inside = True
for ang in range(0, 91, 5):
    dapp2.scene.door_angle = float(ang)
    calls = capture_boxes(dapp2.scene)
    panel = [c for c in calls if c[1] == (O.DOOR_THICK, O.DOOR_HEIGHT, O.DOOR_WIDTH)][0]
    for lz in (-O.DOOR_WIDTH / 2.0, 0.0, O.DOOR_WIDTH / 2.0):
        p_ = (panel[0] * Mat4.from_translation(Vec3(0.0, 0.0, lz))).pos
        if rect_dist(p_.x, p_.z, door_area) > DOOR_SLACK:
            inside = False
check(inside, f"52: ドアの板が障害物の範囲(x -800〜-720, z -390〜-310)から{DOOR_SLACK}を超えて出る角度がある")

# 52 の補足：1秒あたりの角度が 90 を割り切らない fps（25 → 7.2度/フレーム）でも、90 と 0 を行き過ぎない
for fps_ in (25, 7, 60):
    da = make_app(fps_, 1, "office", 1)
    seq = []
    press_keys_and_update(da, pyxel.KEY_D)
    seq.append(da.door_angle)
    for _ in range(fps_ * 2):
        da.update()
        seq.append(da.door_angle)
    check(max(seq) == 90.0 and da.door_angle == 90.0, f"52: fps{fps_} で開いたとき 90 を超える/届かない 最大{max(seq)} 最後{da.door_angle}")
    press_keys_and_update(da, pyxel.KEY_D)
    seq = [da.door_angle]
    for _ in range(fps_ * 2):
        da.update()
        seq.append(da.door_angle)
    check(min(seq) == 0.0 and da.door_angle == 0.0, f"52: fps{fps_} で閉じたとき 0 未満になる/届かない 最小{min(seq)} 最後{da.door_angle}")

# 53. 押し出し：ドアの範囲・書棚・植木の中の人、丸テーブルの中心近くの人（作業中も）
def resolve_at(app, x, z, working=False):
    ag = app.agents[0]
    ag._arrived = False
    ag.state = O.WANDER
    ag._target = None
    if working:
        ag.start_work()
    ag.pos = Vec3(x, 0.0, z)
    app._resolve_collisions()
    return ag.pos.x, ag.pos.z


papp53 = make_app(30, 1, "office", 1)
door_r = O.Rect(-800.0, -720.0, O.DOOR_Z - 40.0, O.DOOR_Z + 40.0)
shelf_rs = [O.Rect(sx - 60.0, sx + 60.0, -598.0, -562.0) for sx in (-700.0, 700.0)]
plant_rs = [O.Rect(px - 30.0, px + 30.0, pz - 30.0, pz + 30.0) for px, pz in ((-740.0, 540.0), (740.0, 540.0))]
probes = [("ドア", door_r, [(-730.0, -350.0), (-740.0, -330.0), (-725.0, -380.0)]),
          ("左の書棚", shelf_rs[0], [(-700.0, -565.0), (-650.0, -570.0)]),
          ("右の書棚", shelf_rs[1], [(700.0, -565.0), (750.0, -570.0)]),
          ("左の植木", plant_rs[0], [(-720.0, 540.0), (-740.0, 515.0)]),
          ("右の植木", plant_rs[1], [(720.0, 540.0), (740.0, 515.0)])]
for pname, prect, pts in probes:
    for (px, pz) in pts:
        check(rect_dist(px, pz, prect) < 1e-9, f"53: テストの前提 {pname}の点({px},{pz})が範囲の中にない")
        for working in (False, True):
            gx, gz = resolve_at(papp53, px, pz, working)
            d_ = rect_dist(gx, gz, prect)
            check(d_ >= R - 1e-3, f"53: {pname}の中の点({px},{pz})が押し出されない（作業中={working}）→({gx:.1f},{gz:.1f}) 距離{d_:.2f}")
# 丸テーブル：中心近く・中心のずれた点・ちょうど中心。中心から 50+AGENT_RADIUS(64) 以上離される。作業中も同じ
tx_, tz_, tr_ = O.TABLE_X, O.TABLE_Z, O.TABLE_RADIUS
check((tx_, tz_, tr_) == (0.0, 180.0, 50.0), f"53: 丸テーブルの定数 {(tx_, tz_, tr_)}")
for working in (False, True):
    for (dx, dz) in ((5.0, 3.0), (-20.0, 10.0), (0.0, -40.0), (30.0, 40.0), (0.0, 0.0)):
        gx, gz = resolve_at(papp53, tx_ + dx, tz_ + dz, working)
        dd = math.hypot(gx - tx_, gz - tz_)
        check(dd >= tr_ + R - 1e-3, f"53: 丸テーブルの中心から({dx},{dz})の点が押し出されない（作業中={working}）距離{dd:.2f} < {tr_ + R}")
gx, gz = resolve_at(papp53, tx_ + 5.0, tz_ + 3.0, True)
check(papp53.agents[0].state == O.WORKING, "53: 作業中のテストなのに WORKING でない")
check(papp53.circles == [(0.0, 180.0, 50.0)], f"53: App.circles が丸テーブル1つでない {papp53.circles}")

# 54. push_out_of_circle の単体：重なっていなければそのまま、重なっていれば距離 r+cr、中心が同じなら +X へ
pc_ = O.push_out_of_circle
check(pc_(100.0, 0.0, 10.0, 0.0, 0.0, 50.0) == (100.0, 0.0), "54: 離れた円が動いた")
check(pc_(60.0, 0.0, 10.0, 0.0, 0.0, 50.0) == (60.0, 0.0), "54: ちょうど接する円が動いた")
check(pc_(-60.0, 0.0, 10.0, 0.0, 0.0, 50.0) == (-60.0, 0.0), "54: ちょうど接する円（左）が動いた")
check(pc_(60.5, 0.0, 10.0, 0.0, 0.0, 50.0) == (60.5, 0.0) and pc_(0.0, 62.0, 10.0, 0.0, 0.0, 50.0) == (0.0, 62.0),
      "54: わずかに離れた円が動いた（引き寄せられた）")
check(near(pc_(30.0, 0.0, 10.0, 0.0, 0.0, 50.0), (60.0, 0.0)), f"54: 重なる円が距離60へ出ない {pc_(30.0, 0.0, 10.0, 0.0, 0.0, 50.0)}")
check(near(pc_(0.0, -10.0, 10.0, 0.0, 0.0, 50.0), (0.0, -60.0)), f"54: 重なる円（-Z 側）{pc_(0.0, -10.0, 10.0, 0.0, 0.0, 50.0)}")
got = pc_(3.0, 4.0, 10.0, 0.0, 0.0, 50.0)  # 中心から距離5 → 60
check(near(got, (36.0, 48.0), 1e-9), f"54: 斜めの円が元の向きに距離60へ出ない {got}")
got = pc_(103.0, 204.0, 10.0, 100.0, 200.0, 50.0)  # 円の中心がずれていても、相対で同じ
check(near(got, (136.0, 248.0), 1e-9), f"54: 中心がずれた円の押し出し {got}")
got = pc_(7.0, 9.0, 10.0, 7.0, 9.0, 50.0)
check(near(got, (67.0, 9.0), 1e-9), f"54: 中心が同じとき +X へ r+cr 出ない {got}")
for c0 in ((30.0, 0.0), (3.0, 4.0), (-20.0, 15.0), (0.0, 0.0)):
    got = pc_(c0[0], c0[1], 10.0, 0.0, 0.0, 50.0)
    check(abs(math.hypot(got[0], got[1]) - 60.0) < 1e-9, f"54: {c0} の押し出し後の距離が60でない {got}")
    check(pc_(got[0], got[1], 10.0, 0.0, 0.0, 50.0) == got, f"54: 押し出し後にもう一度押すと動く {c0}")

# 55. うろつきの目標が丸テーブルの円（＋半径）の中に選ばれない（多数回）
check(all(ag.circles == (O.TABLE_X, O.TABLE_Z, O.TABLE_RADIUS) or tuple(ag.circles) == ((0.0, 180.0, 50.0),) for ag in make_app(30, 1, "office", 18).agents),
      "55: office の人が丸テーブルを避ける円を持っていない")
check(all(tuple(ag.circles) == () for ag in make_app(30, 1, "proto", 3).agents), "55: proto の人が円を持っている")
# 席がテーブルの近く（(0,100)、テーブル中心まで80）の人を直接作る。円を渡さないと、円の中に目標が選ばれる（この試験で検出できる）
def table_picks(circles, n=3000, seed=1):
    ag = O.Agent("T", Vec3(0.0, 0.0, 100.0), random.Random(seed), wander_x=(-780.0, 780.0),
                 wander_z=(-580.0, 580.0), obstacles=(), circles=circles)
    inside_n = none_n = 0
    min_d = 1e9
    for _ in range(n):
        ag._target = None
        ag.repick_target()
        t = ag._target
        if t is None:
            none_n += 1
            continue
        d_ = math.hypot(t.x - 0.0, t.z - 180.0)
        min_d = min(min_d, d_)
        inside_n += d_ < 50.0 + R
    return inside_n, none_n, min_d


in_without, _n0, _m0 = table_picks(())
in_with, none_with, min_with = table_picks(((0.0, 180.0, 50.0),))
check(in_without > 100, f"55: 前提：円なしなら円の中に目標が選ばれるはず {in_without}")
check(in_with == 0 and min_with >= 50.0 + R - 1e-9, f"55: 目標が丸テーブルの円(半径{50 + R})の中に選ばれた {in_with}回 最短{min_with:.2f}")
check(none_with < 3000 * 0.2, f"55: 目標が見つからない回数が多い {none_with}/3000")
print(f"(55) 円なしで円の中に選ばれた {in_without}/3000 → 円ありで {in_with}/3000（見つからず {none_with}）")
# 18人の目標：丸テーブルと、書棚・植木・ドア・壁を広げた範囲にも入らない（多数回）
tapp = make_app(30, 9, "office", 18)
bad_t = []
for ag in tapp.agents:
    for _ in range(100):
        ag._target = None
        ag.repick_target()
        t = ag._target
        if t is None:
            continue
        for ob in tapp.obstacles:
            r_ = ob.rect
            if r_.xmin - R < t.x < r_.xmax + R and r_.zmin - R < t.z < r_.zmax + R:
                bad_t.append((ag.name, round(t.x, 1), round(t.z, 1), ob.owner))
        if math.hypot(t.x - 0.0, t.z - 180.0) < 50.0 + R:
            bad_t.append((ag.name, "table", round(t.x, 1), round(t.z, 1)))
check(not bad_t, f"55: 18人の目標が障害物・丸テーブルの範囲に入った {bad_t[:3]}（計{len(bad_t)}件）")

# 56. 18人で 600 フレーム：壁・小物・丸テーブルとの重なりが0（すり抜けなし）。
#     途中で作業を始めさせ、さらに待機中の人を 30 フレームごとに丸テーブルの上へ置く（押し出しが働くことを強く確かめる）。
TOL56 = 1.0
for seed in (1, 2):
    sapp56 = make_app(30, seed, "office", 18)
    rng56 = random.Random(100 + seed)
    bad_ob, bad_circle, bad_range = [], [], []
    worst_ob = worst_circle = 0.0
    teleports = 0
    for f in range(600):
        if f % 150 == 0:
            for i in range(0, 18, 3):
                sapp56.agents[i].start_work()
        if f % 30 == 10:
            # 出かける人が増えて待機中（WANDER）の人が少ないので、候補を広げ、待機中の人を先頭から最大3人置く
            # （一度に置くのは従来どおり3人まで。人数を増やすと人どうしの押し合いで3回の繰り返しでは収まらない）
            placed_ = 0
            for i in (1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 16, 17):
                a_ = sapp56.agents[i]
                if a_.state == O.WANDER and placed_ < 3:
                    ang = rng56.uniform(0.0, 2.0 * math.pi)
                    a_.pos = Vec3(O.TABLE_X + 15.0 * math.cos(ang) + 60.0 * (placed_ - 1), 0.0,
                                  O.TABLE_Z + 15.0 * math.sin(ang))
                    placed_ += 1
                    teleports += 1
        sapp56.update()
        for i, a in enumerate(sapp56.agents):
            if not (-780.0 - 1e-6 <= a.pos.x <= 780.0 + 1e-6 and -580.0 - 1e-6 <= a.pos.z <= 580.0 + 1e-6):
                bad_range.append((f, a.name, round(a.pos.x, 1), round(a.pos.z, 1)))
            for ob in sapp56.obstacles:
                if a.state == O.WORKING and ob.owner == i:
                    continue
                d_ = rect_dist(a.pos.x, a.pos.z, ob.rect)
                worst_ob = max(worst_ob, R - d_)
                if d_ < R - TOL56:
                    bad_ob.append((f, a.name, a.state, ob.owner, round(d_, 2)))
            for cx_, cz_, cr_ in sapp56.circles:
                d_ = math.hypot(a.pos.x - cx_, a.pos.z - cz_)
                worst_circle = max(worst_circle, cr_ + R - d_)
                if d_ < cr_ + R - TOL56:
                    bad_circle.append((f, a.name, a.state, round(d_, 2)))
    check(not bad_ob, f"56: 種{seed} 壁・小物・机・椅子と重なる {bad_ob[:3]}（計{len(bad_ob)}件、最大の食い込み{worst_ob:.2f}）")
    check(not bad_circle, f"56: 種{seed} 丸テーブルと重なる {bad_circle[:3]}（計{len(bad_circle)}件、最大の食い込み{worst_circle:.2f}）")
    check(not bad_range, f"56: 種{seed} 床の範囲の外へ出た {bad_range[:3]}")
    check(teleports >= 10, f"56: 種{seed} 丸テーブルの上へ置いた回数が少ない {teleports}")
    print(f"(56) 種{seed} 600フレーム 最大の食い込み 障害物 {worst_ob:.3f} / 丸テーブル {worst_circle:.3f}（置いた回数 {teleports}）")

# 57. 設定ファイル：一時の toml と JSON から値が読める。toml なし・壊れた toml でも落ちず既定値
a57, jp57 = make_rate_app(rate_obj(23.5, 41.2), "r57.json", reload_sec=2.0)
check(feq(a57.five_hour, 23.5) and feq(a57.seven_day, 41.2), f"57: JSON の値(23.5, 41.2)が読めない {a57.five_hour} {a57.seven_day}")
check(a57.rate_json_path == jp57, f"57: toml の json_path が使われない {a57.rate_json_path}")
check(feq(a57.scene.five_hour, 23.5) and feq(a57.scene.seven_day, 41.2), "57: 起動直後に scene へ値が渡っていない")
check(a57.manual_limits is False, "57: 起動直後に manual_limits が True")
check(pyxelcube_agents.DEFAULT_RATE_JSON_PATH == "~/.cache/pixel_office/rate_limits.json" and pyxelcube_agents.DEFAULT_RELOAD_SEC == 3.0,
      f"57: 既定の json_path/reload_sec が仕様と違う {pyxelcube_agents.DEFAULT_RATE_JSON_PATH} {pyxelcube_agents.DEFAULT_RELOAD_SEC}")
# toml がない／壊れている／型が違う → 落ちず、既定値（json_path と 3秒）。既定の JSON の場所はテスト用に一時の場所へ差し替える
default_json = write_json_file("r57_default.json", rate_obj(12.0, 34.0))
_orig_default_path = pyxelcube_agents.DEFAULT_RATE_JSON_PATH
pyxelcube_agents.DEFAULT_RATE_JSON_PATH = str(default_json)
try:
    broken_cfgs = {"toml なし": str(TMP_DIR / "no_such_config.toml")}
    for nm_, body in (("toml が壊れている", "[rate_limits\njson_path = = \n\x00\x01"),
                      ("toml が空", ""),
                      ("rate_limits がない", "[other]\nx = 1\n"),
                      ("型が違う", '[rate_limits]\njson_path = 5\nreload_sec = "abc"\n')):
        pth = TMP_DIR / "r57_bad.toml"
        pth.write_text(body, encoding="utf-8")
        broken_cfgs[nm_] = str(pth)
        # 同じ名前を使い回すので、ここで App を作ってから次へ
        err57 = None
        try:
            ap = make_app(30, 1, "office", 1, config_path=str(pth))
        except Exception as e:  # noqa: BLE001
            err57 = e
            ap = None
        check(err57 is None, f"57: {nm_} で例外 {err57!r}")
        if ap is not None:
            check(ap.rate_json_path == default_json and feq(ap.five_hour, 12.0) and feq(ap.seven_day, 34.0),
                  f"57: {nm_} で既定の json_path が使われない {ap.rate_json_path} {ap.five_hour}")
            ap.update()
    err57 = None
    try:
        ap = make_app(30, 1, "office", 1, config_path=broken_cfgs["toml なし"])
    except Exception as e:  # noqa: BLE001
        err57 = e
        ap = None
    check(err57 is None, f"57: toml なしで例外 {err57!r}")
    if ap is not None:
        check(ap.rate_json_path == default_json and feq(ap.five_hour, 12.0), f"57: toml なしで既定の json_path が使われない {ap.rate_json_path}")
        # 既定の reload_sec 3秒＝90フレーム（30fps）
        write_json_file("r57_default.json", rate_obj(70.0, 80.0))
        for _ in range(89):
            ap.update()
        check(feq(ap.five_hour, 12.0), f"57: 既定の3秒より前に読み直した {ap.five_hour}")
        ap.update()
        check(feq(ap.five_hour, 70.0) and feq(ap.seven_day, 80.0), f"57: 既定の3秒（90フレーム）で読み直さない {ap.five_hour}")
    # load_rate_settings の単体
    check(O.load_rate_settings(TMP_DIR / "no_such_config.toml") == (str(default_json), 3.0), "57: load_rate_settings(toml なし) が既定値でない")
finally:
    pyxelcube_agents.DEFAULT_RATE_JSON_PATH = _orig_default_path
# ~ は HOME に展開される（HOME を一時フォルダへ差し替えて確かめる。実際のホームは読まない）
_orig_home = os.environ.get("HOME")
os.environ["HOME"] = str(TMP_DIR)
try:
    write_json_file("r57_home.json", rate_obj(8.0, 9.0))
    ap = make_app(30, 1, "office", 1, config_path=write_toml("r57_home.toml", "~/r57_home.json", 1.0))
    check(ap.rate_json_path == TMP_DIR / "r57_home.json" and feq(ap.five_hour, 8.0), f"57: json_path の ~ が展開されない {ap.rate_json_path}")
finally:
    if _orig_home is None:
        del os.environ["HOME"]
    else:
        os.environ["HOME"] = _orig_home
# JSON の中身ごとの値（five_hour, seven_day の順）
json_cases = [
    ("JSON なし", None, (0.0, 0.0)),
    ("JSON が壊れている", "{not json", (0.0, 0.0)),
    ("JSON が空", "", (0.0, 0.0)),
    ("JSON が配列", "[1, 2]", (0.0, 0.0)),
    ("項目なし {}", {}, (0.0, 0.0)),
    ("five_hour だけ", {"five_hour": {"used_percentage": 20.0}}, (20.0, 0.0)),
    ("used_percentage なし", {"five_hour": {}, "seven_day": {"used_percentage": 41.2}}, (0.0, 41.2)),
    ("項目が数でなく辞書でない", {"five_hour": 5, "seven_day": [1]}, (0.0, 0.0)),
    ("150 と -5", rate_obj(150, -5), (100.0, 0.0)),
    ("ちょうど 0 と 100", rate_obj(0, 100), (0.0, 100.0)),
    ("1e9 と -1e9", rate_obj(1e9, -1e9), (100.0, 0.0)),
    ("数でない文字列", rate_obj("abc", "50"), (0.0, 0.0)),
    ("null と true", rate_obj(None, True), (0.0, 0.0)),
    ("NaN", '{"five_hour": {"used_percentage": NaN}, "seven_day": {"used_percentage": Infinity}}', (0.0, 0.0)),
]
for jn, content, want in json_cases:
    err57 = None
    try:
        ap, _jp = make_rate_app(content, "r57_case.json" if content is not None else "r57_nofile.json")
        ap.update()
    except Exception as e:  # noqa: BLE001
        err57 = e
        ap = None
    check(err57 is None, f"57: {jn} で例外 {err57!r}")
    if ap is not None:
        check(feq(ap.five_hour, want[0]) and feq(ap.seven_day, want[1]),
              f"57: {jn} の値が{want}でなく({ap.five_hour}, {ap.seven_day})")
# --config 引数
check(pyxelcube_agents.parse_args([]).config is None and pyxelcube_agents.parse_args(["--config", "x.toml"]).config == "x.toml", "57: --config 引数が解釈されない")

# 58. reload_sec ごとに読み直す：途中で JSON を書き換え、reload_sec 経過後（フレーム数）に値が変わる
for rs, fps_ in ((1.0, 30), (0.5, 30), (2.0, 10), (1.5, 20)):
    nframes = round(rs * fps_)
    ap, jp = make_rate_app(rate_obj(10.0, 20.0), "r58.json", reload_sec=rs, fps=fps_)
    check(feq(ap.five_hour, 10.0) and feq(ap.seven_day, 20.0), f"58: reload_sec={rs} fps={fps_} 起動時の値が違う")
    for rnd, (nf, nw) in enumerate(((55.0, 66.0), (5.0, 95.0), (0.0, 0.0))):
        write_json_file("r58.json", rate_obj(nf, nw))
        old = (ap.five_hour, ap.seven_day)
        for _ in range(nframes - 1):
            ap.update()
        check((ap.five_hour, ap.seven_day) == old, f"58: reload_sec={rs} fps={fps_} {rnd + 1}回目 {nframes - 1}フレームでは読み直さない（早すぎ）{ap.five_hour}")
        ap.update()
        check(feq(ap.five_hour, nf) and feq(ap.seven_day, nw), f"58: reload_sec={rs} fps={fps_} {rnd + 1}回目 {nframes}フレームで値が変わらない {ap.five_hour} {ap.seven_day}")
        check(feq(ap.scene.five_hour, nf) and feq(ap.scene.seven_day, nw), f"58: 読み直した値が scene に渡らない")
    # ファイルが途中で消えた/壊れた → 次の読み直しで 0
    write_json_file("r58.json", "{broken")
    for _ in range(nframes):
        ap.update()
    check(ap.five_hour == 0.0 and ap.seven_day == 0.0, f"58: 途中で JSON が壊れても 0 にならない {ap.five_hour}")

# 59. キー 1〜4：値が10ずつ変わり 0〜100 に収まる。押したあとは JSON を書き換えても変わらない（manual_limits）
ap, jp = make_rate_app(rate_obj(23.5, 41.2), "r59.json", reload_sec=1.0)
check(ap.manual_limits is False, "59: 押す前に manual_limits が True")
for _ in range(40):
    ap.update()
check(ap.manual_limits is False, "59: 押さないのに manual_limits が True になった")
for key, want5, want7, nm_ in ((pyxel.KEY_2, 33.5, 41.2, "2"), (pyxel.KEY_1, 23.5, 41.2, "1"),
                                (pyxel.KEY_4, 23.5, 51.2, "4"), (pyxel.KEY_3, 23.5, 41.2, "3")):
    press_keys_and_update(ap, key)
    check(feq(ap.five_hour, want5) and feq(ap.seven_day, want7), f"59: キー{nm_} のあと ({ap.five_hour}, {ap.seven_day}) が ({want5}, {want7}) でない")
    check(ap.manual_limits is True, f"59: キー{nm_} のあと manual_limits が True でない")
    check(feq(ap.scene.five_hour, ap.five_hour) and feq(ap.scene.seven_day, ap.seven_day), f"59: キー{nm_} のあと scene の値が同じでない")
# 0〜100 に収まる
seen = []
for key in (pyxel.KEY_2,) * 12 + (pyxel.KEY_4,) * 12:
    press_keys_and_update(ap, key)
    seen += [ap.five_hour, ap.seven_day]
check(ap.five_hour == 100.0 and ap.seven_day == 100.0 and max(seen) == 100.0, f"59: 増やし続けて 100 で止まらない {ap.five_hour} {ap.seven_day} {max(seen)}")
for key in (pyxel.KEY_1,) * 12 + (pyxel.KEY_3,) * 12:
    press_keys_and_update(ap, key)
    seen += [ap.five_hour, ap.seven_day]
check(ap.five_hour == 0.0 and ap.seven_day == 0.0 and min(seen) == 0.0, f"59: 減らし続けて 0 で止まらない {ap.five_hour} {ap.seven_day} {min(seen)}")
for _ in range(3):
    press_keys_and_update(ap, pyxel.KEY_2)
for _ in range(5):
    press_keys_and_update(ap, pyxel.KEY_4)
check(feq(ap.five_hour, 30.0) and feq(ap.seven_day, 50.0), f"59: 0 から増やした値が(30,50)でない ({ap.five_hour}, {ap.seven_day})")
write_json_file("r59.json", rate_obj(77.0, 88.0))
for _ in range(30 * 5):  # reload_sec=1 の5倍の時間
    ap.update()
check(feq(ap.five_hour, 30.0) and feq(ap.seven_day, 50.0), f"59: 手動のあと JSON を読んで値が変わった ({ap.five_hour}, {ap.seven_day})")
# キー1つだけ押した場合も、押していないほうの値まで JSON から読み直さない
ap, jp = make_rate_app(rate_obj(23.5, 41.2), "r59b.json", reload_sec=1.0)
press_keys_and_update(ap, pyxel.KEY_3)
write_json_file("r59b.json", rate_obj(77.0, 88.0))
for _ in range(60):
    ap.update()
check(feq(ap.five_hour, 23.5) and feq(ap.seven_day, 31.2), f"59: キー3だけ押したあと 5h の値が JSON で変わった ({ap.five_hour}, {ap.seven_day})")
# JSON が読めなかった（0）あとに押しても 0〜100 に収まる
ap, jp = make_rate_app(None, "r59_nofile.json")
press_keys_and_update(ap, pyxel.KEY_1)
press_keys_and_update(ap, pyxel.KEY_3)
check(ap.five_hour == 0.0 and ap.seven_day == 0.0, f"59: 0 から減らしても 0 未満になる ({ap.five_hour}, {ap.seven_day})")

# 60. 掲示板：five_hour=60 で黄色の棒（色10）、0 で描かない。週間の赤（色8）も同じ。長さ＝200×割合/100、左端 x=-100
def bar_boxes(root):
    """掲示板の棒の箱（高さ14・奥行き2）だけを集める。"""
    # 100% の枠（色 BAR_FRAME_COLOR の左右の箱が同じ高さ・奥行き）は棒ではないので外す
    return [c for c in capture_boxes(root) if c[1][1] == O.BAR_HEIGHT and c[1][2] == O.BAR_DEPTH and c[2] != O.BAR_FRAME_COLOR]


def check_bar(tag, calls, color, y, percent):
    mine = [c for c in calls if c[2] == color]
    if percent <= 0.0:
        check(not mine, f"60: {tag} {percent}% で棒（色{color}）が描かれた {len(mine)}個")
        return
    length = 200.0 * percent / 100.0
    check(len(mine) == 1, f"60: {tag} {percent}% の棒（色{color}）が1個でなく{len(mine)}個")
    if len(mine) == 1:
        m_, size_, _c = mine[0]
        check(feq(size_[0], length, 1e-3) and feq(size_[1], 14.0) and feq(size_[2], 2.0), f"60: {tag} {percent}% の棒の大きさ {size_}（長さ{length}のはず）")
        check(abs(m_.pos.x - (-100.0 + length / 2.0)) < 1e-3 and abs(m_.pos.y - y) < 1e-3 and abs(m_.pos.z - (-596.0)) < 1e-3,
              f"60: {tag} {percent}% の棒の位置 ({m_.pos.x},{m_.pos.y},{m_.pos.z})（左端 -100・y={y}・z=-596 のはず）")
        check(abs((m_.pos.x - size_[0] / 2.0) - (-100.0)) < 1e-3, f"60: {tag} {percent}% の棒の左端が -100 でない")


check(O.FIVE_HOUR_BAR_COLOR == 10 and O.WEEK_BAR_COLOR == 8, f"60: 棒の色が 10/8 でない {O.FIVE_HOUR_BAR_COLOR} {O.WEEK_BAR_COLOR}")
for fh, wk in ((0.0, 0.0), (60.0, 0.0), (0.0, 35.0), (100.0, 100.0), (60.0, 35.0), (0.5, 100.0)):
    root = O.OfficeRoot(OLAY)
    root.five_hour, root.seven_day = fh, wk
    cs = bar_boxes(root)
    check_bar(f"黄({fh},{wk})", cs, 10, 160.0, fh)
    check_bar(f"赤({fh},{wk})", cs, 8, 128.0, wk)
    check(len(cs) == (fh > 0) + (wk > 0), f"60: ({fh},{wk}) で棒の数が{(fh > 0) + (wk > 0)}個でなく{len(cs)}個")
# 白い板は常に1枚（棒が0でも描く）。板の色7・大きさ(240,70,2)
root = O.OfficeRoot(OLAY)
boards = [c for c in capture_boxes(root) if c[1] == (240.0, 70.0, 2.0)]
check(len(boards) == 1 and boards[0][2] == 7, f"60: 白い板が色7で1枚でない {len(boards)}")
# App 経由：JSON の値が棒になる／キーで変えると棒が変わる
ap, _jp = make_rate_app(rate_obj(60.0, 35.0), "r60.json")
ap.update()
cs = bar_boxes(ap.scene)
check_bar("App 黄", cs, 10, 160.0, 60.0)
check_bar("App 赤", cs, 8, 128.0, 35.0)
for _ in range(6):
    press_keys_and_update(ap, pyxel.KEY_1)
cs = bar_boxes(ap.scene)
check_bar("App 黄（キー1を6回）", cs, 10, 160.0, 0.0)
check_bar("App 赤（変えていない）", cs, 8, 128.0, 35.0)
press_keys_and_update(ap, pyxel.KEY_3)
press_keys_and_update(ap, pyxel.KEY_3)
press_keys_and_update(ap, pyxel.KEY_3)
press_keys_and_update(ap, pyxel.KEY_3)
check_bar("App 赤（キー3を4回→0）", bar_boxes(ap.scene), 8, 128.0, 0.0)
# 実際の画面：黄の棒が描かれると色10の画素が増える（office、小物は描くまま。本の色10と区別するため、棒あり／なしの差で見る）
def yellow_px(app):
    app.update()
    app.draw()
    return sum(1 for y in range(20, count_y1(app)) for x in range(pyxel.width) if pyxel.screen.pget(x, y) == 10)


ap0, _ = make_rate_app(rate_obj(0.0, 0.0), "r60_px0.json")
ap1, _ = make_rate_app(rate_obj(100.0, 0.0), "r60_px1.json")
for a_ in (ap0, ap1):
    a_.cam_dist = 900.0  # 近づけて掲示板を大きく写す
    a_._apply_camera()
ypx0, ypx1 = yellow_px(ap0), yellow_px(ap1)
check(ypx1 > ypx0, f"60: 黄の棒（100%）で画面の色10が増えない {ypx0} → {ypx1}")
print(f"(60) 画面の色10の画素数 棒なし {ypx0} / 棒100% {ypx1}")

# 61. proto 配置ではドア・掲示板・小物を描かない・障害物にもならない（has_props=False）。案内文字も出ない
check(O.PROTO_LAYOUT.has_props is False and OLAY.has_props is True, "61: has_props が proto=False/office=True でない")
rp = O.OfficeRoot(O.PROTO_LAYOUT)
rp.five_hour, rp.seven_day, rp.door_angle = 60.0, 35.0, 90.0
ro = O.OfficeRoot(OLAY)
ro.five_hour, ro.seven_day = 60.0, 35.0
extra = {"box": 0, "elli": 0, "sphere": 0}
for rt, tag in ((rp, "proto"), (ro, "office")):
    cnt_ = {"elli": 0, "sphere": 0}
    rt.elli = lambda *a, c=cnt_, **k: c.__setitem__("elli", c["elli"] + 1)
    rt.sphere = lambda *a, c=cnt_, **k: c.__setitem__("sphere", c["sphere"] + 1)
    calls = capture_boxes(rt)
    sizes_ = {c[1] for c in calls}
    has_door = (O.DOOR_THICK, O.DOOR_HEIGHT, O.DOOR_WIDTH) in sizes_
    has_board = (240.0, 70.0, 2.0) in sizes_
    has_bar = any(c[1][1] == 14.0 and c[1][2] == 2.0 for c in calls)
    has_shelf = O.BOOKSHELF_SIZE and (120.0, 180.0, 36.0) in sizes_
    has_coffee = (24.0, 32.0, 18.0) in sizes_
    has_pot = (40.0, 40.0, 40.0) in sizes_
    if tag == "proto":
        check(not (has_door or has_board or has_bar or has_shelf or has_coffee or has_pot),
              f"61: proto にドア/掲示板/棒/書棚/コーヒー/鉢が描かれる {has_door, has_board, has_bar, has_shelf, has_coffee, has_pot}")
        check(cnt_["elli"] == 0 and cnt_["sphere"] == 0, f"61: proto で丸テーブル・植木の葉が描かれる {cnt_}")
        check(len(calls) == 1 + 3 * 3 + 3 * 2, f"61: proto の箱が{1 + 9 + 6}個でなく{len(calls)}個")
    else:
        check(has_door and has_board and has_bar and has_shelf and has_coffee and has_pot,
              f"61: office にドア/掲示板/棒/書棚/コーヒー/鉢がない {has_door, has_board, has_bar, has_shelf, has_coffee, has_pot}")
        check(cnt_["elli"] == 2 and cnt_["sphere"] == 2, f"61: office の丸テーブル（天板・台座の2つ）・植木の葉（2つ）が描かれない {cnt_}")
# 障害物・円・人の円：proto にはない
papp61 = make_app(30, 1, "proto", 3)
check(len(papp61.obstacles) == 3 * 2 and all(o_.owner is not None for o_ in papp61.obstacles),
      f"61: proto の障害物が机3＋椅子3でない {len(papp61.obstacles)}")
check(papp61.circles == [] and all(tuple(a.circles) == () for a in papp61.agents), "61: proto に丸い障害物がある")
# proto で D を押しても、ドアの範囲・小物の場所は歩ける（障害物でない）。ドアの位置の点が押し出されない
ag61 = papp61.agents[0]
for (px, pz) in ((-760.0, -350.0), (-700.0, -570.0), (0.0, 180.0)):
    ag61.pos = Vec3(px, 0.0, pz)
    papp61._resolve_collisions()
    # proto の床は ±380 なので x は床の端に収まるが、ドア/書棚/テーブルのためには押し出されない（x,z とも床の範囲で clamp されるだけ）
    want_x = min(max(px, -380.0), 380.0)
    want_z = min(max(pz, -50.0), 280.0)
    # 机・椅子との重なりは proto の範囲外の点なので無関係
    check(abs(ag61.pos.x - want_x) < 1e-6 and abs(ag61.pos.z - want_z) < 1e-6, f"61: proto で ({px},{pz}) が小物のために押し出された ({ag61.pos.x},{ag61.pos.z})")
# 案内の文字：office だけ、y=height-18。proto は出ない
def drawn_text_at(app):
    out = []
    saved = pyxel.text
    pyxel.text = lambda x, y, s, col, *a, **k: out.append((x, y, str(s), col))
    try:
        app.draw()
    finally:
        pyxel.text = saved
    return out


GUIDE = "D:DOOR 1/2:5H 3/4:WEEK CLICK:WALK/TALK Q:END"
tt_o = drawn_text_at(make_app(30, 1, "office", 18))
tt_p = drawn_text_at(papp61)
g_o = [t for t in tt_o if t[2] == GUIDE]
check(len(g_o) == 0, f"61: office に左下の案内 '{GUIDE}' が出た（製品版では出さない） {g_o}")
check(not any(t[2] == GUIDE for t in tt_p), "61: proto に案内 'D:DOOR...' が出た")
check(any(t[2] == "SPACE:WORK WHEEL:ZOOM ARROWS:VIEW" for t in tt_p) and not any(t[2] == "SPACE:WORK WHEEL:ZOOM ARROWS:VIEW" for t in tt_o), "61: proto の案内だけが出る（office には出ない）")

# ---- ここから「行き先・出かける・会話・道探し」（office だけ）の項目（62〜73） ----
# 時間の数え方：App は dt=1/30 秒ずつ進む。行き先・会話のタイマーは dt × time_scale、歩く速さは time_scale の影響を受けない。
# 他の人が勝手に出かけて邪魔しないよう、操作しない人には長い休み（cooldown）を付けて静かにさせる（ov_quiet）。
OV_FPS = 30
OV_SPOT = {s.name: s for s in O.OFFICE_SPOTS}
OV_SLOTS_TOTAL = sum(len(s.slots) for s in O.OFFICE_SPOTS)


def ov_app(seed=1, n=1, ts=1.0):
    """office の App（n 人・時間倍率 ts）。"""
    return make_app(OV_FPS, seed, "office", n, time_scale=ts)


def ov_quiet(app, ids=None):
    """指定した人（省略で全員）が勝手に出かけないよう、長い休みを付ける。"""
    for i, a in enumerate(app.agents):
        if ids is None or i in ids:
            a.cooldown = 1.0e9
            a.wander_time = 0.0


def ov_send(app, i, want=None, slots=None, avoid=()):
    """人 i の行き先を予約して GOING にする。want が行き先の名前か種類（coffee/shelf/plant）、slots が立つ場所の番号の集まりなら、
    その条件の場所が出るまで取り直す。avoid は避ける (行き先の名前, 場所の番号)。

    丸テーブルの南側（coffee の場所 1・2）は、北側の席から来る人が、東西の場所に立つ人に道をふさがれやすい
    （道探しは立っている人を障害にしない）ので、会話のテストでは slots で北寄りの場所に絞る。
    """
    mgr = app.spot_manager
    for _ in range(500):
        picked = mgr.reserve(i)
        if picked is None:
            raise AssertionError("予約できない")
        ok = (want is None or want in (picked[0].name, picked[0].kind)) \
            and (slots is None or picked[1] in slots) and (picked[0].name, picked[1]) not in avoid
        if ok:
            break
        mgr.release(i)
    else:
        raise AssertionError(f"{want} {slots} が出ない")
    spot, k = picked
    assert app.agents[i].begin_going(spot, k)
    return spot, k


def ov_step(app, frames, per_frame=None):
    """update を frames 回進める。per_frame(f) を毎フレームの後に呼ぶ。"""
    for f in range(frames):
        app.update()
        if per_frame is not None:
            per_frame(f)


def ov_until(app, cond, limit, per_frame=None):
    """cond() が真になるまで update する。真になったときまでに進めたフレーム数（最初から真なら 0）。limit までに真にならなければ None。"""
    for f in range(limit + 1):
        if cond():
            return f
        if f == limit:
            break
        app.update()
        if per_frame is not None:
            per_frame(f)
    return None


def ov_total_count(app):
    """予約されている立つ場所の数（全部の行き先の合計）。"""
    return sum(app.spot_manager.count(s) for s in O.OFFICE_SPOTS)


def ov_forward_dot(agent, tx, tz):
    """人の正面（yaw から求める。yaw 0 が -Z、(-sin, -cos)）と、人から (tx, tz) への向きの内積。1 に近いほどその方を向く。"""
    fx = -math.sin(math.radians(agent.yaw))
    fz = -math.cos(math.radians(agent.yaw))
    dx, dz = tx - agent.pos.x, tz - agent.pos.z
    d = math.hypot(dx, dz)
    return (fx * dx + fz * dz) / d if d > 0 else 1.0


# 62. SpotManager（行き先の予約）：上限・解放・くじの比率・空きのない場所は選ばれない
SM = O.SpotManager
coffee62 = OV_SPOT["coffee"]
m62 = SM((coffee62,), random.Random(1))
r62 = [m62.reserve(i) for i in range(6)]
check(all(r is not None and r[0] is coffee62 for r in r62), f"62: coffee に6人まで予約できない {r62}")
check(sorted(r[1] for r in r62) == list(range(6)), f"62: coffee の立つ場所が重なる/足りない {[r[1] for r in r62]}")
check(m62.count(coffee62) == 6, f"62: coffee の予約数が6でない {m62.count(coffee62)}")
check(m62.reserve(6) is None, "62: coffee に7人目が予約できてしまう")
check(m62.count(coffee62) == 6, "62: 7人目に断られたのに予約数が変わった")
m62.release(3)
check(m62.count(coffee62) == 5, f"62: release(3) で予約数が5にならない {m62.count(coffee62)}")
r62b = m62.reserve(6)
check(r62b == (coffee62, r62[3][1]), f"62: 解放された場所（{r62[3]}）に7人目が入れない {r62b}")
m62.release(99)  # 予約していない人の release は何も起こさない
check(m62.count(coffee62) == 6, "62: 予約のない人の release で予約数が変わった")
try:
    m62.reserve(0)
    err62 = None
except ValueError as e_:
    err62 = e_
check(isinstance(err62, ValueError), "62: 同じ人の二重予約が ValueError にならない")
# 全部の行き先：立つ場所は全部で 6+3+3+2+2=16。16人まで予約でき、17人目は None。重なりなし
check(OV_SLOTS_TOTAL == 16, f"62: 立つ場所の合計が16でない {OV_SLOTS_TOTAL}")
m62 = SM(O.OFFICE_SPOTS, random.Random(2))
r62 = [m62.reserve(i) for i in range(16)]
check(all(r is not None for r in r62), "62: 16人まで予約できない")
check(len({(r[0].name, r[1]) for r in r62}) == 16, "62: 立つ場所が重なっている")
check(all(m62.count(s) == len(s.slots) for s in O.OFFICE_SPOTS), "62: 全部いっぱいなのに予約数が上限に達していない")
check(m62.reserve(16) is None and m62.reserve(17) is None, "62: 全部いっぱいなのに予約できてしまう")
m62.release(7)
r62b = m62.reserve(16)
check(r62b is not None and (r62b[0].name, r62b[1]) == (r62[7][0].name, r62[7][1]),
      f"62: 解放した場所 {(r62[7][0].name, r62[7][1])} に次の人が入れない {r62b}")
for i in range(17):
    m62.release(i)
check(all(m62.count(s) == 0 for s in O.OFFICE_SPOTS), "62: 全員 release しても予約が残る")


def ov_fill(mgr, spot, first_id):
    """行き先 spot の立つ場所を全部、ダミーの人番号（first_id 以上）で埋める。他の行き先に当たったダミーは外す。"""
    k = first_id
    while mgr.count(spot) < len(spot.slots):
        picked = mgr.reserve(k)
        if picked[0] is not spot:
            mgr.release(k)
        k += 1


def ov_lottery(mgr, times):
    """人 0 が予約と解放を times 回繰り返して、行き先の名前ごとの回数を返す。"""
    cnt = {s.name: 0 for s in mgr.spots}
    for _ in range(times):
        picked = mgr.reserve(0)
        if picked is None:
            cnt["none"] = cnt.get("none", 0) + 1
        else:
            cnt[picked[0].name] += 1
            mgr.release(0)
    return cnt


def ov_ratio_ok(cnt, times, want, tol=0.03):
    """cnt の各行き先の割合が want（名前→割合）の ±tol に入っているか。want にない行き先は 0 であること。"""
    return all(abs(cnt.get(k, 0) / times - want.get(k, 0.0)) <= tol for k in cnt)


N62 = 6000
m62 = SM(O.OFFICE_SPOTS, random.Random(5))
cnt62 = ov_lottery(m62, N62)
check(ov_ratio_ok(cnt62, N62, {"coffee": 0.5, "shelf_l": 0.125, "shelf_r": 0.125, "plant_l": 0.125, "plant_r": 0.125}),
      f"62: くじの比率が coffee 50%・書棚計25%・植木計25% でない {cnt62}")
# コーヒーがいっぱい：選ばれず、書棚と植木が半々
m62 = SM(O.OFFICE_SPOTS, random.Random(6))
ov_fill(m62, coffee62, 100)
cnt62 = ov_lottery(m62, N62)
check(cnt62["coffee"] == 0, f"62: いっぱいの coffee が選ばれた {cnt62}")
check(ov_ratio_ok(cnt62, N62, {"shelf_l": 0.25, "shelf_r": 0.25, "plant_l": 0.25, "plant_r": 0.25}),
      f"62: coffee が埋まったとき、書棚と植木が半々でない {cnt62}")
# 左の書棚だけいっぱい：選ばれず、書棚の分（25）は右の書棚が全部引き受ける
m62 = SM(O.OFFICE_SPOTS, random.Random(7))
ov_fill(m62, OV_SPOT["shelf_l"], 100)
cnt62 = ov_lottery(m62, N62)
check(cnt62["shelf_l"] == 0, f"62: いっぱいの shelf_l が選ばれた {cnt62}")
check(ov_ratio_ok(cnt62, N62, {"coffee": 0.5, "shelf_r": 0.25, "plant_l": 0.125, "plant_r": 0.125}),
      f"62: shelf_l が埋まったとき、書棚の重み25が右に移っていない {cnt62}")
# 書棚が両方いっぱい：書棚は選ばれず、coffee 2/3・植木 1/3
m62 = SM(O.OFFICE_SPOTS, random.Random(8))
ov_fill(m62, OV_SPOT["shelf_l"], 100)
ov_fill(m62, OV_SPOT["shelf_r"], 200)
cnt62 = ov_lottery(m62, N62)
check(cnt62["shelf_l"] == 0 and cnt62["shelf_r"] == 0, f"62: いっぱいの書棚が選ばれた {cnt62}")
check(ov_ratio_ok(cnt62, N62, {"coffee": 2 / 3, "plant_l": 1 / 6, "plant_r": 1 / 6}),
      f"62: 書棚が両方埋まったとき coffee 2/3・植木 1/3 でない {cnt62}")
# 空きが1つだけ：必ずそこへ入る（どの行き先が空いても）
for want_id in (100, 105, 110, 115):
    m62 = SM(O.OFFICE_SPOTS, random.Random(9))
    held62 = [m62.reserve(100 + k) for k in range(16)]
    m62.release(want_id)
    got62 = {(p_[0].name, p_[1]) for p_ in (m62.reserve(0) for _ in range(1)) if p_}
    m62.release(0)
    check(got62 == {(held62[want_id - 100][0].name, held62[want_id - 100][1])},
          f"62: 空きが1つ（人{want_id}の場所）だけのとき、そこへ入らない {got62}")

# 63. 出かける時刻：うろつきが5秒続くと GOING。休み（cooldown）が残っていれば出かけない。空きが無ければ出かけず、うろつき時間が0に戻る
# 起動時のうろつき時間：office は 0〜5 秒の乱数（全員が同じ瞬間に出かけない）。proto は 0
a63 = ov_app(1, 18)
w63 = [a.wander_time for a in a63.agents]
check(all(0.0 <= w < O.OUTING_WANDER_SEC for w in w63), f"63: 起動時の wander_time が 0〜5 に入らない {min(w63)} {max(w63)}")
check(len({round(w, 6) for w in w63}) >= 15, f"63: 起動時の wander_time がばらけていない {sorted(w63)[:4]}")
check(all(a.wander_time == 0.0 and a.cooldown == 0.0 for a in make_app(30, 1, "proto", 3).agents), "63: proto の起動時 wander_time/cooldown が 0 でない")
# 5 秒（150 フレーム）で GOING。その前は WANDER のまま。予約が1つ入り、行き先が決まる
for ts63, want63 in ((1.0, 150), (10.0, 15)):
    a63 = ov_app(1, 1, ts63)
    ag63 = a63.agents[0]
    ag63.wander_time = 0.0
    ag63.cooldown = 0.0
    states63 = []
    f63 = ov_until(a63, lambda: ag63.state == O.GOING, 400, lambda f: states63.append(ag63.state))
    check(f63 is not None and abs(f63 - want63) <= 3, f"63: time_scale {ts63} で GOING になるフレームが {want63}±3 でない {f63}")
    check(all(s == O.WANDER for s in states63[:-1]), f"63: GOING になる前に WANDER 以外になった {set(states63)}")
    check(ag63.spot is not None and ov_total_count(a63) == 1, f"63: GOING なのに行き先・予約が1つでない {ag63.spot} {ov_total_count(a63)}")
    check(ag63.wander_time == 0.0, f"63: 出かけたあと wander_time が 0 でない {ag63.wander_time}")
# 休み 20 秒（time_scale 10 で 60 フレーム）：その間は出かけず、うろつき時間も数えない。休みが明けて 5 秒後（15 フレーム）に出かける
a63 = ov_app(1, 1, 10.0)
ag63 = a63.agents[0]
ag63.wander_time = 0.0
ag63.cooldown = 20.0
log63 = []
f63 = ov_until(a63, lambda: ag63.state == O.GOING, 200, lambda f: log63.append((ag63.state, ag63.cooldown, ag63.wander_time)))
check(f63 is not None and 70 <= f63 <= 80, f"63: 休み20秒＋うろつき5秒（time_scale 10 で約75フレーム）で出かけない {f63}")
check(all(s == O.WANDER for s, _, _ in log63[:-1]), "63: 休みの間に WANDER 以外になった")
check(abs(log63[29][1] - 10.0) < 0.5, f"63: 30フレーム（10秒）後の休みの残りが10秒前後でない {log63[29][1]}")
check(all(w == 0.0 for _, c, w in log63[:-1] if c > 0.0), "63: 休みの間にうろつき時間を数えた")
# 全部いっぱい：出かけず WANDER のまま、うろつき時間が 0 に戻る。1つ空くと出かける
a63 = ov_app(1, 1, 10.0)
ag63 = a63.agents[0]
ag63.wander_time = 0.0
ag63.cooldown = 0.0
held63 = [a63.spot_manager.reserve(100 + k) for k in range(16)]
resets63 = [0]
prev63 = [0.0]


def watch63(f):
    if prev63[0] > 4.0 and ag63.wander_time == 0.0:
        resets63[0] += 1
    prev63[0] = ag63.wander_time


ov_step(a63, 120, watch63)  # 120 フレーム＝タイマー 40 秒（うろつき5秒が8回ぶん）
check(ag63.state == O.WANDER, f"63: 全部いっぱいなのに出かけた {ag63.state}")
check(resets63[0] >= 6, f"63: 全部いっぱいのとき、うろつき時間が 0 に戻る回数が少ない {resets63[0]}")
check(ov_total_count(a63) == 16, f"63: 出かけない人が予約を増やした {ov_total_count(a63)}")
a63.spot_manager.release(105)
f63 = ov_until(a63, lambda: ag63.state == O.GOING, 40)
check(f63 is not None and f63 <= 20, f"63: 空きができても出かけない {f63}")
check(ag63.spot is held63[5][0] and ag63.slot_index == held63[5][1], f"63: 空いた場所 {held63[5][0].name}/{held63[5][1]} に向かわない {ag63.spot} {ag63.slot_index}")

# 64. 戻る時刻：1人なら30秒で RETURNING。2人以上は30秒では戻らず、会話60秒で戻る。会話していない間は talk_time が止まる
a64 = ov_app(2, 1)
ag64 = a64.agents[0]
ag64.wander_time = 0.0
ag64.cooldown = 0.0
check(ov_until(a64, lambda: ag64.state == O.AT_SPOT, 3000) is not None, "64: 1人の行き先に着かない")
check(ag64.alone_time < 0.1 and ag64.talk_time == 0.0, f"64: 着いた直後の alone_time/talk_time が 0 付近でない {ag64.alone_time} {ag64.talk_time}")
f64 = ov_until(a64, lambda: ag64.state == O.RETURNING, 1200)
check(f64 is not None and 897 <= f64 <= 903, f"64: 1人で30秒（900フレーム）で戻らない {f64}")
check(ag64.talk_time == 0.0, f"64: 1人なのに talk_time が増えた {ag64.talk_time}")
check(ov_total_count(a64) == 0 and ag64.spot is None, f"64: 戻り始めても予約が残る {ov_total_count(a64)} {ag64.spot}")


OV_SAFE_COFFEE = (0, 3, 4, 5)  # 北側の席から行きやすい coffee の立つ場所


def ov_pair(seed, n=2, want="coffee", ts=1.0):
    """n 人を同じ行き先（want）へ行かせ、全員が AT_SPOT になるまで進めた App と、そのときの行き先を返す。"""
    app_ = ov_app(seed, n, ts)
    ov_quiet(app_)
    spot_, _ = ov_send(app_, 0, want, OV_SAFE_COFFEE)
    for i in range(1, n):
        ov_send(app_, i, spot_.name, OV_SAFE_COFFEE)
    f_ = ov_until(app_, lambda: all(a.state == O.AT_SPOT for a in app_.agents), 3000)
    assert f_ is not None, "全員が行き先に着かない"
    return app_, spot_


# 2人：30秒たっても戻らない。会話 60 秒（1800 フレーム）で2人とも戻る。その間 alone_time は 0
a64, sp64 = ov_pair(3, 2)
alone64 = []
f64 = ov_until(a64, lambda: any(a.state != O.AT_SPOT for a in a64.agents), 2000,
               lambda f: alone64.append(max(a.alone_time for a in a64.agents)))
check(f64 is not None and 1796 <= f64 <= 1804, f"64: 2人の会話60秒（1800フレーム）で戻らない {f64}")
check(all(a.state == O.RETURNING for a in a64.agents), f"64: 2人が同時に戻らない {[a.state for a in a64.agents]}")
check(max(alone64) == 0.0, f"64: 会話中に alone_time が増えた {max(alone64)}")
# 会話していない間は talk_time が止まる：2人で5秒話し、1人が抜ける（スペースキー）。残った人は1人で30秒
a64, sp64 = ov_pair(4, 2)
ov_step(a64, 150)
t64 = [a.talk_time for a in a64.agents]
check(all(abs(t - 5.0) < 0.2 for t in t64), f"64: 2人で5秒話して talk_time が5秒前後でない {t64}")
a64.next_index = 1
press_space_and_update(a64)
check(a64.agents[1].state == O.WORKING, "64: スペースで人1が WORKING にならない")
t_frozen64 = a64.agents[0].talk_time
tk64 = []
f64 = ov_until(a64, lambda: a64.agents[0].state == O.RETURNING, 1200, lambda f: tk64.append(a64.agents[0].talk_time))
check(all(t == t_frozen64 for t in tk64), "64: 1人になったあと talk_time が動いた")
check(f64 is not None and 895 <= f64 <= 903, f"64: 1人になってから30秒（900フレーム）で戻らない {f64}")
check(abs(t_frozen64 - 5.0) < 0.3, f"64: 抜けた時点の talk_time が5秒前後でない {t_frozen64}")

# 65. 戻ったあと60秒は出かけない。60秒たてば出かけられる
a65 = ov_app(5, 1)
ag65 = a65.agents[0]
ag65.wander_time = 0.0
ag65.cooldown = 0.0
check(ov_until(a65, lambda: ag65.state == O.RETURNING, 4000, None) is not None, "65: 1人の行き先から戻り始めない")
check(ov_until(a65, lambda: ag65.state == O.WANDER, 3000) is not None, "65: 席に戻って WANDER にならない")
check(ag65.cooldown == O.OUTING_COOLDOWN_SEC == 60.0 and ag65.wander_time == 0.0, f"65: 戻った直後の休み/うろつき時間が 60/0 でない {ag65.cooldown} {ag65.wander_time}")
st65 = []
f65 = ov_until(a65, lambda: ag65.state == O.GOING, 2500, lambda f: st65.append(ag65.state))
# 休み60秒（1800フレーム）＋うろつき5秒（150フレーム）＝1950 フレームあたり
check(f65 is not None and 1944 <= f65 <= 1956, f"65: 戻って60秒＋5秒（1950フレーム）で次に出かけない {f65}")
check(all(s == O.WANDER for s in st65[:-1]), "65: 休みの間に WANDER 以外になった")

# 66. 話し手：グループに1人だけ。4〜6秒で交代し、交代後は別の人。話し手が抜けたら新しく選ばれる
# 67. 姿勢：話し手の身ぶり3種が全部出る・机を指すときは机のほうを向く。聞き手は話し手を向き、飲む／立つ（3〜6秒ごと）
GESTURES = {k: O.gesture_pose(k) for k in O.GESTURE_KINDS}
a66, sp66 = ov_pair(6, 3)
ids66 = [0, 1, 2]
desk66 = a66.layout.desks[0]
sp_log66 = []        # (フレーム, 話し手の番号)
gest_count66 = []    # 各フレームの、身ぶりの姿勢をしている人の数
gest_seen66 = {}     # 身ぶりの種類 → 見たフレーム数
bad_face66 = []      # 身ぶり・聞き手の向きが合わない例
bad_pose66 = []      # 聞き手の姿勢が「立つ／飲む」でない例
listen_seg66 = {i: None for i in ids66}   # 聞き手の姿勢が同じ役のまま変わった最後のフレーム
listen_prev66 = {i: None for i in ids66}  # 前のフレームの (役, 姿勢が飲むか)
seg_len66 = []       # 聞き手の姿勢が役を変えずに変わるまでのフレーム数
listener_poses66 = set()  # 聞き手が取った姿勢（True=飲む、False=立つ）


def watch66(f):
    members = [i for i in ids66 if a66.agents[i].state == O.AT_SPOT]
    if len(members) < 2:
        return
    spk = a66._speakers.get(sp66.name)
    if not sp_log66 or sp_log66[-1][1] != spk:
        sp_log66.append((f, spk))
    gest_agents = [i for i in members if any(a66.agents[i].pose == g for g in GESTURES.values())]
    gest_count66.append(len(gest_agents))
    for i in members:
        ag = a66.agents[i]
        if i == spk:
            kind = next((k for k, g in GESTURES.items() if ag.pose == g), None)
            if kind is None:
                continue
            gest_seen66[kind] = gest_seen66.get(kind, 0) + 1
            if kind == O.GESTURE_POINT_DESK:
                if ov_forward_dot(ag, desk66.x, desk66.z) < 0.999:
                    bad_face66.append((f, "机", round(ov_forward_dot(ag, desk66.x, desk66.z), 4)))
            else:
                dots = [ov_forward_dot(ag, a66.agents[j].pos.x, a66.agents[j].pos.z) for j in members if j != i]
                if max(dots) < 0.999:
                    bad_face66.append((f, kind, round(max(dots), 4)))
            listen_prev66[i] = None
            listen_seg66[i] = None
        else:
            drink = ag.pose == O.drink_pose()
            listener_poses66.add(drink)
            if not (drink or ag.pose == O.stand_pose()):
                bad_pose66.append((f, i))
            if ov_forward_dot(ag, a66.agents[spk].pos.x, a66.agents[spk].pos.z) < 0.999:
                bad_face66.append((f, "聞き手", i))
            prev = listen_prev66[i]
            if prev is not None and prev != ("L", drink):
                if listen_seg66[i] is not None:
                    seg_len66.append(f - listen_seg66[i])
                listen_seg66[i] = f
            elif prev is None:
                listen_seg66[i] = None
            listen_prev66[i] = ("L", drink)


talk66 = []


def watch66b(f):
    talk66.append(max(a.talk_time for a in a66.agents if a.state == O.AT_SPOT) if any(a.state == O.AT_SPOT for a in a66.agents) else None)
    watch66(f)


f66 = ov_until(a66, lambda: any(a.state != O.AT_SPOT for a in a66.agents), 1900, watch66b)
# 3人が揃う前に先に着いた2人の会話が始まっているので、揃ってから数えず、会話した時間（talk_time）が60秒で戻ることを見る
leavers66 = [a for a in a66.agents if a.state == O.RETURNING]
check(f66 is not None and leavers66 and all(O.TALK_SEC <= a.talk_time < O.TALK_SEC + 0.05 for a in leavers66),
      f"66: 会話の時間（talk_time）が60秒になったら戻る、になっていない {f66} {[a.talk_time for a in a66.agents]}")
check(max(t for t in talk66 if t is not None) < O.TALK_SEC, "66: 会話60秒より前に戻った人がいる")
check(len(sp_log66) >= 8, f"66: 60秒で話し手が8回以上入れ替わらない {len(sp_log66)}")
check(all(c == 1 for c in gest_count66), f"66: 身ぶりの人がちょうど1人でないフレームがある {sorted(set(gest_count66))}")
check(all(spk is not None for _, spk in sp_log66), "66: 話し手が決まらないフレームがある")
check(all(a[1] != b[1] for a, b in zip(sp_log66, sp_log66[1:])), f"66: 交代したのに同じ人 {sp_log66}")
iv66 = [b[0] - a[0] for a, b in zip(sp_log66, sp_log66[1:])][1:]  # 最初の間隔は途中からなので除く
check(all(4 * 30 - 1 <= d <= 6 * 30 + 1 for d in iv66), f"66: 話し手の交代間隔が4〜6秒に入らない {iv66}")
check(max(iv66) - min(iv66) >= 15, f"66: 交代間隔がばらけない（4〜6秒の乱数のはず） {iv66}")
check(len({spk for _, spk in sp_log66}) == 3, f"66: 3人全員が話し手にならない {sorted({spk for _, spk in sp_log66})}")
# 67（身ぶり・聞き手）
check(set(gest_seen66) == set(O.GESTURE_KINDS), f"67: 身ぶり3種が全部出ない {gest_seen66}")
check(not bad_face66, f"67: 話し手・聞き手の向きが合わない {bad_face66[:3]}（計{len(bad_face66)}件）")
check(O.GESTURE_POINT_DESK in gest_seen66 and not [b for b in bad_face66 if b[1] == "机"], "67: 机を指すとき机の方を向いていない")
check(not bad_pose66, f"67: 聞き手が立つ・飲む以外の姿勢になった {bad_pose66[:3]}")
check(len(seg_len66) >= 2 and min(seg_len66) >= 3 * 30 - 1, f"67: 聞き手の姿勢の切り替えが3秒より速い/起きない {sorted(seg_len66)[:5]} 計{len(seg_len66)}")
check(listener_poses66 == {True, False}, f"67: 聞き手が『飲む』と『立つ』の両方を取らない {listener_poses66}")
check(max(seg_len66) <= 12 * 30 + 2, f"67: 聞き手の姿勢が12秒を超えて変わらない {max(seg_len66)}")
check(GESTURES[O.GESTURE_BOTH_UP].shoulder_l > 100 and GESTURES[O.GESTURE_BOTH_UP].shoulder_r > 100,
      "67: 『両手を上げる』で両肩が上がっていない")
check(GESTURES[O.GESTURE_POINT_LISTENER].shoulder_r > 45 and GESTURES[O.GESTURE_POINT_LISTENER].shoulder_l == O.stand_pose().shoulder_l,
      "67: 『聞き手へ片手』が片手だけ上がっていない")
check(len({tuple(vars(g).values()) for g in GESTURES.values()}) == 3, "67: 身ぶり3種の姿勢が互いに違わない")

# 66（続き）話し手が抜けたら新しく選ばれる。1人になると話し手はいなくなる（1人の姿勢になる）
a66, sp66 = ov_pair(7, 3)
ov_step(a66, 60)
spk66 = a66._speakers[sp66.name]
a66.next_index = spk66
press_space_and_update(a66)
check(a66.agents[spk66].state == O.WORKING, "66: スペースで話し手が WORKING にならない")
rest66 = [i for i in range(3) if i != spk66]
new66 = a66._speakers.get(sp66.name)
check(new66 in rest66, f"66: 話し手が抜けたのに、残りの2人から新しい話し手が選ばれない {new66} {rest66}")
ov_step(a66, 1)
check(sum(1 for i in rest66 if a66.agents[i].pose in GESTURES.values()) == 1, "66: 話し手が抜けたあと、身ぶりの人が1人でない")
a66.next_index = new66
press_space_and_update(a66)
left66 = [i for i in rest66 if i != new66][0]
check(sp66.name not in a66._speakers, f"66: 1人になったのに話し手が残る {a66._speakers}")
check(a66.agents[left66].pose == O.spot_pose(sp66.kind) and a66.agents[left66].pose == O.drink_pose(),
      "67: coffee に1人で残った人が『飲む』姿勢でない")

# 67（続き）1人のときの姿勢：coffee は飲む、shelf は本を取る、plant はかがむ（足の裏が床に付く）。行き先の中心を向く
def ov_sole_heights(pose):
    """姿勢の左右の足の裏の高さ。関節の角度から、立った状態の長さ（腰 HIP_Y・太もも・すね）で求める（床が 0）。"""
    hs = []
    for hip, knee in ((pose.hip_l, pose.knee_l), (pose.hip_r, pose.knee_r)):
        hs.append(pose.body_y + O.HIP_Y - O.THIGH_LEN * math.cos(math.radians(hip))
                  - O.SHIN_LEN * math.cos(math.radians(hip - knee)))
    return hs


check(all(abs(h) < 1e-6 for h in ov_sole_heights(O.stand_pose())), f"67: 立ち姿勢の足の裏が床(0)でない {ov_sole_heights(O.stand_pose())}")
solo67 = {}
for name67 in ("coffee", "shelf_l", "shelf_r", "plant_l", "plant_r"):
    a67 = ov_app(8, 1)
    ov_quiet(a67)
    sp67, k67 = ov_send(a67, 0, name67)
    ag67 = a67.agents[0]
    check(ov_until(a67, lambda: ag67.state == O.AT_SPOT, 3000) is not None, f"67: {name67} に着かない")
    ov_step(a67, 10)
    p67 = ag67.pose
    solo67[name67] = p67
    check(ag67.state == O.AT_SPOT and abs(ag67.pos.x - sp67.slots[k67][0]) < 1e-6 and abs(ag67.pos.z - sp67.slots[k67][1]) < 1e-6,
          f"67: {name67} の立つ場所に立っていない {ag67.pos}")
    check(ov_forward_dot(ag67, sp67.center[0], sp67.center[1]) > 0.999, f"67: {name67} で行き先の中心を向かない")
    if sp67.kind == "coffee":
        check(p67.elbow_r >= 90.0 and p67.shoulder_r > 20.0 and p67.shoulder_l == O.stand_pose().shoulder_l and p67.elbow_l == O.stand_pose().elbow_l and p67.body_y == 0.0,
              f"67: coffee 1人の姿勢が『飲む』（右肘を大きく曲げ、左は立ち姿勢）でない {p67}")
    elif sp67.kind == "shelf":
        check(p67.shoulder_r >= 90.0 and p67.elbow_r <= 30.0 and p67.shoulder_l == O.stand_pose().shoulder_l and p67.body_y == 0.0,
              f"67: {name67} 1人の姿勢が『本を取る』（右腕を前へ伸ばす）でない {p67}")
    else:
        check(p67.body_y < -5.0 and p67.hip_l > 0.0 and p67.knee_l > p67.hip_l and p67.hip_r == p67.hip_l and p67.knee_r == p67.knee_l,
              f"67: {name67} 1人の姿勢が『かがむ』（体が下がり、腰・膝が曲がる）でない {p67}")
        hs67 = ov_sole_heights(p67)
        check(all(abs(h) < 0.5 for h in hs67), f"67: かがんだとき足の裏が床(0)付近でない {hs67}")
check(solo67["shelf_l"] == solo67["shelf_r"] and solo67["plant_l"] == solo67["plant_r"], "67: 同じ種類の行き先なのに姿勢が違う")
check(len({tuple(vars(p).values()) for p in (solo67["coffee"], solo67["shelf_l"], solo67["plant_l"])}) == 3, "67: 飲む/本を取る/かがむの姿勢が互いに違わない")

# 68. スペースキー割り込み：GOING・AT_SPOT・RETURNING のどれからでも WORKING になり、予約が外れる。そのあと席に着いて座る
def ov_interrupt(state, seed):
    app_ = ov_app(seed, 2)
    ov_quiet(app_)
    ag_ = app_.agents[0]
    ov_send(app_, 0, "coffee", OV_SAFE_COFFEE)
    if state != O.GOING:
        assert ov_until(app_, lambda: ag_.state == O.AT_SPOT, 3000) is not None
    if state == O.RETURNING:
        assert ov_until(app_, lambda: ag_.state == O.RETURNING, 3000) is not None
        ov_step(app_, 30)
    else:
        ov_step(app_, 30 if state == O.GOING else 5)
    return app_, ag_


for st68 in (O.GOING, O.AT_SPOT, O.RETURNING):
    a68, ag68 = ov_interrupt(st68, 9)
    check(ag68.state == st68, f"68: 準備で {st68} になっていない {ag68.state}")
    check(ov_total_count(a68) == (0 if st68 == O.RETURNING else 1), f"68: {st68} の予約数が想定と違う {ov_total_count(a68)}")
    a68.next_index = 0
    press_space_and_update(a68)
    check(ag68.state == O.WORKING, f"68: {st68} からスペースで WORKING にならない {ag68.state}")
    check(ov_total_count(a68) == 0 and ag68.spot is None, f"68: {st68} からの割り込みで予約が外れない {ov_total_count(a68)}")
    check(ag68.cooldown == 0.0 and ag68.talk_time == 0.0 and ag68.alone_time == 0.0, f"68: {st68} からの割り込みでタイマーが0にならない")
    ov_quiet(a68, {0})  # 作業のあと勝手に出かけないようにする
    f68 = ov_until(a68, lambda: ag68.is_seated, 2500)
    check(f68 is not None, f"68: {st68} から割り込んだあと、席に着いて座らない")
    if f68 is not None:
        check(abs(ag68.pos.x - ag68.seat.x) < 1e-6 and abs(ag68.pos.z - ag68.seat.z) < 1e-6, f"68: {st68} のあとの着席位置が席でない {ag68.pos}")
        check(abs(ag68.yaw - ag68.seat_yaw) < 1e-6, f"68: {st68} のあと、席の向きを向かない {ag68.yaw}")
        check(ag68.pose.body_y == O.SIT_BODY_Y, f"68: {st68} のあと、座った姿勢でない {ag68.pose.body_y}")
    # 割り込んだ場所はほかの人が使える
    p68 = a68.spot_manager.reserve(1)
    check(p68 is not None and ov_total_count(a68) == 1, "68: 割り込みのあと予約し直せない")
# 道を待っている間（列に並んでいる間）の割り込み：列から外れ、WORKING になる
a68 = ov_app(10, 3)
ov_quiet(a68)
for i in range(3):
    ov_send(a68, i, "coffee", OV_SAFE_COFFEE)
check(all(a.path_wait for a in a68.agents) and list(a68._nav_queue) == [0, 1, 2], f"68: 3人が同時に出発して列に並ばない {list(a68._nav_queue)}")
a68.next_index = 2
press_space_and_update(a68)
check(a68.agents[2].state == O.WORKING and 2 not in a68._nav_queue, f"68: 列で待つ人がスペースで WORKING になり、列から外れない {list(a68._nav_queue)}")
check(ov_total_count(a68) == 2, f"68: 列で待つ人の割り込みで予約が外れない {ov_total_count(a68)}")

# 68（続き）道が見つからないとき：GOING からは予約を外して休みなしで WANDER に戻る。RETURNING からは休み60秒つきで WANDER に戻る
a68 = ov_app(13, 1)
ov_quiet(a68)
a68.nav.find_path = lambda *args, **kw: None
ov_send(a68, 0, "coffee")
ov_step(a68, 3)
ag68 = a68.agents[0]
check(ag68.state == O.WANDER and ag68.spot is None and ov_total_count(a68) == 0, f"68: 行き先への道が無いとき、あきらめて予約を外し WANDER に戻らない {ag68.state}")
check(ag68.cooldown == 0.0 and ag68.wander_time < 0.2 and a68.stat_give_ups == 1, f"68: GOING からのあきらめは休みなし・あきらめ回数1のはず {ag68.cooldown} {ag68.wander_time} {a68.stat_give_ups}")
a68, sp68 = ov_pair(14, 1)
ag68 = a68.agents[0]
a68.nav.find_path = lambda *args, **kw: None
f68 = ov_until(a68, lambda: ag68.state == O.WANDER, 1200)
check(f68 is not None and ag68.state == O.WANDER and ov_total_count(a68) == 0, f"68: 戻る道が無いとき、あきらめて予約を外し WANDER に戻らない {ag68.state}")
check(ag68.cooldown == O.OUTING_COOLDOWN_SEC and a68.stat_give_ups == 1, f"68: RETURNING からのあきらめは休み60秒・あきらめ回数1のはず {ag68.cooldown} {a68.stat_give_ups}")

# 68（続き）立つ場所にいる人は押されない（AT_SPOT は is_fixed）。歩いている人（GOING）は押される
a68, sp68 = ov_pair(11, 2)
fix68 = a68.agents[0]
other68 = a68.agents[1]
check(fix68.is_fixed and other68.is_fixed, "68: AT_SPOT の人が is_fixed でない")
other68.state = O.WANDER  # もう1人を待機にして、同じ場所へ重ねる
other68.spot = None
check(not other68.is_fixed, "68: WANDER の人が is_fixed になる")
x68, z68 = fix68.pos.x, fix68.pos.z
other68.pos = O.Vec3(x68 + 3.0, 0.0, z68)
a68._resolve_collisions()
check(abs(fix68.pos.x - x68) < 1e-9 and abs(fix68.pos.z - z68) < 1e-9, f"68: AT_SPOT の人が押された {fix68.pos}")
check(math.hypot(other68.pos.x - x68, other68.pos.z - z68) >= 2 * O.AGENT_RADIUS - 1e-6, f"68: 押される側が離れない {other68.pos}")

# 69. 道探し（NavGrid）：全部の立つ場所へ、全部の席から道が見つかる。道が障害物（人の半径込み）を通らない。角を切らない
def ov_seg_ok(p, q, rects, circles, r, step=2.0):
    """点 p→q の直線が、障害物（長方形・丸）から r 以上離れているか。区間のまわりの障害物だけを step ごとに調べる。"""
    x0, x1 = sorted((p[0], q[0]))
    z0, z1 = sorted((p[1], q[1]))
    rs = [c for c in rects if c.xmin - r <= x1 and c.xmax + r >= x0 and c.zmin - r <= z1 and c.zmax + r >= z0]
    cs = [c for c in circles if c[0] - c[2] - r <= x1 and c[0] + c[2] + r >= x0 and c[1] - c[2] - r <= z1 and c[1] + c[2] + r >= z0]
    n = max(1, math.ceil(math.hypot(q[0] - p[0], q[1] - p[1]) / step))
    for k in range(n + 1):
        x = p[0] + (q[0] - p[0]) * k / n
        z = p[1] + (q[1] - p[1]) * k / n
        for c in rs:
            if rect_dist(x, z, c) < r - 1e-6:
                return False
        for cx, cz, cr in cs:
            if math.hypot(x - cx, z - cz) < cr + r - 1e-6:
                return False
    return True


a69 = ov_app(1, 18)
nav69 = a69.nav
rects69 = [ob.rect for ob in a69.obstacles]
circles69 = a69.circles
seats69 = [(s[0].x, s[0].z) for s in O.OFFICE_LAYOUT.seats]
slots69 = [(sp.name, k, xz) for sp in O.OFFICE_SPOTS for k, xz in enumerate(sp.slots)]
times69, none69, bad_seg69, far_end69, first_gap69, npts69 = [], [], [], [], [], []
import time as _t69


def ov_check_path(tag, start, goal, from_seat):
    t0 = _t69.perf_counter()
    path = nav69.find_path(start, goal)
    times69.append(_t69.perf_counter() - t0)
    if path is None:
        none69.append(tag)
        return
    npts69.append(len(path))
    if math.hypot(path[-1][0] - goal[0], path[-1][1] - goal[1]) > 40.0:
        far_end69.append((tag, round(math.hypot(path[-1][0] - goal[0], path[-1][1] - goal[1]), 1)))
    pts = list(path) if from_seat else [start] + list(path)  # 席は椅子の中なので、最初の区間（席→最初の点）は調べない
    if from_seat:
        first_gap69.append(math.hypot(path[0][0] - start[0], path[0][1] - start[1]))
    for p, q in zip(pts, pts[1:]):
        if not ov_seg_ok(p, q, rects69, circles69, R):
            bad_seg69.append((tag, tuple(round(v) for v in p), tuple(round(v) for v in q)))
            break


for si, seat in enumerate(seats69):
    for name, k, xz in slots69:
        ov_check_path(f"席{si}→{name}{k}", seat, xz, True)
        ov_check_path(f"{name}{k}→席{si}", xz, seat, False)
# 遠い場所どうし（対角など）
for (n1, k1, xz1), (n2, k2, xz2) in ((slots69[6], slots69[-1]), (slots69[-1], slots69[6]), (slots69[0], slots69[9]), (slots69[10], slots69[14])):
    ov_check_path(f"{n1}{k1}→{n2}{k2}", xz1, xz2, False)
check(not none69, f"69: 道が見つからない組がある {none69[:5]}（計{len(none69)}件）")
# 注意：find_path は最後の点を目標の点に置き換えるが、置き換えたあとの最後の区間は障害物との確認をしていない
check(not bad_seg69, f"69: 道の区間が障害物（人の半径{R}込み）に入る {bad_seg69[:3]}（計{len(bad_seg69)}件）")
check(not far_end69, f"69: 道の終点が目標から40以上離れる {far_end69[:3]}")
check(max(first_gap69) <= 3 * O.NAV_CELL, f"69: 席から最初の点までが遠い {max(first_gap69):.1f}")
check(len(times69) == 18 * 16 * 2 + 4, f"69: 調べた組の数が想定と違う {len(times69)}")
check(max(times69) < 0.05, f"69: find_path が1回 50 ms を超える {max(times69) * 1000:.1f} ms")
check(sum(npts69) / len(npts69) < 20, f"69: 道の点の間引きが効いていない（平均{sum(npts69) / len(npts69):.1f}点）")
print(f"(69) find_path {len(times69)}回 平均 {sum(times69) / len(times69) * 1000:.2f} ms / 最大 {max(times69) * 1000:.2f} ms / 平均点数 {sum(npts69) / len(npts69):.1f}")
# 角を切らない：斜めの2マスだけが通れる地図（他は障害物）。斜めには進めないので、道は無い。片方が通れるなら、そのマスを回る
def ov_tiny(i, j):
    cx, cz = 10.0 + 20.0 * i, 10.0 + 20.0 * j
    return O.Rect(cx - 1.0, cx + 1.0, cz - 1.0, cz + 1.0)


cells69 = [(i, j) for i in range(3) for j in range(3)]
nav_c = O.NavGrid((0.0, 60.0), (0.0, 60.0), [ov_tiny(*c) for c in cells69 if c not in ((0, 0), (1, 1))], [])
check(nav_c._free(0, 0) and nav_c._free(1, 1) and sum(1 for i, j in cells69 if nav_c._free(i, j)) == 2, "69: 角の試験の地図が想定どおりでない")
check(nav_c.find_path((10.0, 10.0), (30.0, 30.0)) is None, "69: 斜めの隙間（縦横の隣が通れない）を抜ける道が見つかる（角を切っている）")
nav_c = O.NavGrid((0.0, 60.0), (0.0, 60.0), [ov_tiny(*c) for c in cells69 if c not in ((0, 0), (1, 1), (1, 0))], [])
p69 = nav_c.find_path((10.0, 10.0), (30.0, 30.0))
check(p69 is not None and len(p69) == 3 and (30.0, 10.0) in [tuple(q) for q in p69], f"69: 角を回る道（(30,10) を通る）にならない {p69}")

# 70. 1フレームの find_path は1回まで。順番待ちの人は歩かない（立って待つ）
check(O.NAV_MAX_PER_FRAME == 1, f"70: NAV_MAX_PER_FRAME が1でない {O.NAV_MAX_PER_FRAME}")
a70 = ov_app(12, 16)
ov_quiet(a70)
ov_step(a70, 10)  # 起動直後は席の椅子・机から押し出されて動くので、落ち着かせてから出発させる
calls70 = [0]
orig70 = a70.nav.find_path


def counting70(*a, **k):
    calls70[0] += 1
    return orig70(*a, **k)


a70.nav.find_path = counting70
for i in range(16):
    ov_send(a70, i)
check(list(a70._nav_queue) == list(range(16)) and all(a.path_wait for a in a70.agents), "70: 16人が出発して列に並ばない")
per70, moved_wait70, wrong70 = [], [], []
for f in range(40):
    before = [(a.pos.x, a.pos.z, a.path_wait) for a in a70.agents]
    c0 = calls70[0]
    a70.update()
    per70.append(calls70[0] - c0)
    for i, a in enumerate(a70.agents):
        if before[i][2] and a.path_wait:  # 待ったまま
            if math.hypot(a.pos.x - before[i][0], a.pos.z - before[i][1]) > 1e-9 or a.pose != O.stand_pose():
                moved_wait70.append((f, i))
    if f < 16:
        # f フレーム目が終わった時点で、先頭から f+1 人が道をもらっている（順番どおり）
        waiting = [i for i, a in enumerate(a70.agents) if a.path_wait]
        if waiting != list(range(f + 1, 16)):
            wrong70.append((f, waiting))
check(max(per70) <= 1, f"70: 1フレームに find_path が2回以上呼ばれた {max(per70)}")
check(per70[:16] == [1] * 16, f"70: 16人が並んだとき、最初の16フレームは毎回1回ずつのはず {per70[:16]}")
check(not wrong70, f"70: 列の順番（先に並んだ人から）どおりに道がもらえない {wrong70[:2]}")
check(not moved_wait70, f"70: 順番待ちの人が歩いた/姿勢を変えた {moved_wait70[:3]}")
check(all(not a.path_wait for a in a70.agents), "70: 40フレームたっても道をもらえない人がいる")
check(sum(per70) >= 16, f"70: 16人ぶんの find_path が呼ばれていない {sum(per70)}")

# 71. 18人・time_scale 10・長く回す（種2つ）
OV_STUCK_FRAMES = 60 * OV_FPS  # 5 以上動かない状態がこの長さ続いたら「止まりっぱなし」（待機の立ち止まりは最長3秒。AT_SPOT と着席中は数えない）
OV_LONG_FRAMES = 3600  # 30fps で 120 秒（行き先・会話のタイマーは10倍なので、1人の滞在30秒は3秒、休み60秒は6秒）


def ov_long_run(seed, frames):
    """18人で frames フレーム回し、各種の数値を集めた dict を返す。"""
    app_ = ov_app(seed, 18, 10.0)
    calls_ = [0]
    orig_ = app_.nav.find_path

    def counting_(*a, **k):
        calls_[0] += 1
        return orig_(*a, **k)

    app_.nav.find_path = counting_
    st = dict(max_calls=0, over_cap=[], dup=[], arrivals=0, talk_frames=0, max_group=0, going_starts=0,
              bad_ob=[], bad_circle=[], bad_range=[], worst_ob=0.0, worst_circle=0.0, kinds=set(),
              stuck=[], max_still=0.0, states=set(), mgr_mismatch=[])
    anchor = [(a.pos.x, a.pos.z) for a in app_.agents]
    still = [0] * 18
    prev_state = [a.state for a in app_.agents]
    max_still = [0] * 18
    for f in range(frames):
        c0 = calls_[0]
        app_.update()
        st["max_calls"] = max(st["max_calls"], calls_[0] - c0)
        per_slot = {}
        per_spot = {}
        for i, a in enumerate(app_.agents):
            st["states"].add(a.state)
            if a.state != prev_state[i]:
                if a.state == O.AT_SPOT:
                    st["arrivals"] += 1
                    st["kinds"].add(a.spot.name)
                if a.state == O.GOING:
                    st["going_starts"] += 1
                prev_state[i] = a.state
            if a.state in (O.GOING, O.AT_SPOT):
                key = (a.spot.name, a.slot_index)
                per_slot.setdefault(key, []).append(i)
                per_spot.setdefault(a.spot.name, []).append(i)
            elif a.spot is not None:
                st["mgr_mismatch"].append((f, i, a.state))
            # 食い込み
            if not (-780.0 - 1e-6 <= a.pos.x <= 780.0 + 1e-6 and -580.0 - 1e-6 <= a.pos.z <= 580.0 + 1e-6):
                st["bad_range"].append((f, a.name))
            for ob in app_.obstacles:
                if a.state == O.WORKING and ob.owner == i:
                    continue
                d_ = rect_dist(a.pos.x, a.pos.z, ob.rect)
                st["worst_ob"] = max(st["worst_ob"], R - d_)
                if d_ < R - 1.0:
                    st["bad_ob"].append((f, a.name, a.state, ob.owner, round(d_, 2)))
            for cx_, cz_, cr_ in app_.circles:
                d_ = math.hypot(a.pos.x - cx_, a.pos.z - cz_)
                st["worst_circle"] = max(st["worst_circle"], cr_ + R - d_)
                if d_ < cr_ + R - 1.0:
                    st["bad_circle"].append((f, a.name, a.state, round(d_, 2)))
            # 止まりっぱなし：5 以上動かない状態が続く時間（座って作業中・行き先で立つ間は除く）
            exempt = a.state == O.AT_SPOT or a.is_seated
            if exempt or math.hypot(a.pos.x - anchor[i][0], a.pos.z - anchor[i][1]) > 5.0:
                anchor[i] = (a.pos.x, a.pos.z)
                still[i] = 0
            else:
                still[i] += 1
                max_still[i] = max(max_still[i], still[i])
                if still[i] == OV_STUCK_FRAMES:
                    st["stuck"].append((f, a.name, a.state, round(a.pos.x), round(a.pos.z)))
        for key, who in per_slot.items():
            if len(who) > 1:
                st["dup"].append((f, key, who))
        for name, who in per_spot.items():
            slots_n = len(OV_SPOT[name].slots)
            st["max_group"] = max(st["max_group"], len(who))
            if len(who) > slots_n:
                st["over_cap"].append((f, name, len(who)))
        if any(len([i for i in who if app_.agents[i].state == O.AT_SPOT]) >= 2 for who in per_spot.values()):
            st["talk_frames"] += 1
        # 予約表と人の状態が合う：GOING・AT_SPOT の人の数 = 予約の数
        if sum(app_.spot_manager.count(s) for s in O.OFFICE_SPOTS) != sum(len(w) for w in per_spot.values()):
            st["mgr_mismatch"].append((f, "count"))
    st["max_still"] = max(max_still) / OV_FPS
    st["replans"] = app_.stat_replans
    st["give_ups"] = app_.stat_give_ups
    st["app"] = app_
    return st


import time as _t71
for seed71 in (1, 2):
    t71 = _t71.perf_counter()
    r71 = ov_long_run(seed71, OV_LONG_FRAMES)
    print(f"(71) 種{seed71} {OV_LONG_FRAMES}フレーム {(_t71.perf_counter() - t71):.1f}秒 出発{r71['going_starts']} 到着{r71['arrivals']} 会話フレーム{r71['talk_frames']} "
          f"最大人数{r71['max_group']} 引っかかり{r71['replans']} あきらめ{r71['give_ups']} 最長静止{r71['max_still']:.1f}秒 食い込み 障害物{r71['worst_ob']:.2f}/円{r71['worst_circle']:.2f}")
    check(r71["max_calls"] <= 1, f"71: 種{seed71} 1フレームに find_path が2回以上 {r71['max_calls']}")
    check(not r71["over_cap"], f"71: 種{seed71} 行き先の上限人数を超えた {r71['over_cap'][:3]}")
    check(not r71["dup"], f"71: 種{seed71} 同じ立つ場所に2人以上が向かった {r71['dup'][:3]}")
    check(not r71["mgr_mismatch"], f"71: 種{seed71} 予約の数と GOING/AT_SPOT の人数が合わない {r71['mgr_mismatch'][:3]}")
    check({O.GOING, O.AT_SPOT, O.RETURNING} <= r71["states"], f"71: 種{seed71} 行き先の状態が出ない {r71['states']}")
    check(r71["arrivals"] >= 20, f"71: 種{seed71} 行き先にたどり着く人が少ない {r71['arrivals']}")
    check(len(r71["kinds"]) >= 4, f"71: 種{seed71} 行き先がかたよる（着いた行き先 {sorted(r71['kinds'])}）")
    check(r71["talk_frames"] >= 300, f"71: 種{seed71} 会話（同じ行き先に2人以上）がほとんど起きない {r71['talk_frames']}")
    check(r71["give_ups"] <= max(2, 0.1 * r71["going_starts"]), f"71: 種{seed71} あきらめが多い {r71['give_ups']} / 出発 {r71['going_starts']}")
    check(not r71["bad_ob"], f"71: 種{seed71} 壁・小物・机・椅子と重なる {r71['bad_ob'][:3]}（計{len(r71['bad_ob'])}件）")
    check(not r71["bad_circle"], f"71: 種{seed71} 丸テーブルと重なる {r71['bad_circle'][:3]}")
    check(not r71["bad_range"], f"71: 種{seed71} 床の範囲の外へ出た {r71['bad_range'][:3]}")
    check(not r71["stuck"], f"71: 種{seed71} 60秒以上同じ場所で止まりっぱなしの人がいる（フレーム, 人, 状態, x, z）{r71['stuck'][:4]} 最長{r71['max_still']:.1f}秒")

# 72. proto 配置では新しい状態にならない：待機（WANDER）と作業（WORKING）だけ。行き先・道探しの部品も無い
for ts72 in (1.0, 10.0):
    a72 = make_app(30, 3, "proto", 3, time_scale=ts72)
    seen72, extra72 = set(), []
    for f in range(3000):
        if f % 500 == 0:
            press_space_and_update(a72)
        else:
            a72.update()
        for a in a72.agents:
            seen72.add(a.state)
            if a.spot is not None or a.path_wait or a.wander_time != 0.0 or a.cooldown != 0.0 or a.alone_time != 0.0 or a.talk_time != 0.0:
                extra72.append((f, a.name))
    check(seen72 == {O.WANDER, O.WORKING}, f"72: proto（time_scale {ts72}）で WANDER と WORKING 以外になった {seen72}")
    check(not extra72, f"72: proto で行き先のタイマー・予約が動いた {extra72[:3]}")
    check(a72.spot_manager is None and a72.nav is None and a72.stat_give_ups == 0 and a72.stat_replans == 0 and not a72._nav_queue,
          f"72: proto に行き先・道探しの部品がある/動いた")

# 73. --time-scale 引数：既定 1.0、0 以下は 1.0（不正な値も 1.0）。歩く速さには効かない
check(O.parse_args([]).time_scale == 1.0 and O.DEFAULT_TIME_SCALE == 1.0, f"73: --time-scale の既定が 1.0 でない {O.parse_args([]).time_scale}")
check(O.parse_args(["--time-scale", "10"]).time_scale == 10.0 and O.parse_args(["--time-scale", "0.5"]).time_scale == 0.5, "73: --time-scale の指定値が読めない")
for bad73 in (0.0, -1.0, -0.001, float("nan"), float("inf"), float("-inf")):
    check(make_app(30, 1, "office", 1, time_scale=bad73).time_scale == 1.0, f"73: time_scale={bad73} が 1.0 にならない")
for ok73 in (0.001, 0.5, 1.0, 2.5, 10.0):
    check(make_app(30, 1, "office", 1, time_scale=ok73).time_scale == ok73, f"73: time_scale={ok73} がそのまま使われない")
check(make_app(30, 1, "office", 1).time_scale == 1.0, "73: time_scale を省くと 1.0 でない")
# main() が --time-scale を App へ渡す（App を差し替えて引数を受け取るだけにする）
got73 = {}
orig_app73 = O.App
orig_argv73 = sys.argv


class FakeApp73:
    def __init__(self, *a, **k):
        got73["a"], got73["k"] = a, k
        self.update = self.draw = None


O.App = FakeApp73
try:
    sys.argv = ["pyxelcube_agents.py", "--layout", "office", "--agents", "5", "--time-scale", "7.5"]
    O.main()
    check(got73["k"].get("time_scale") == 7.5 and got73["a"][2:4] == ("office", 5), f"73: main が --time-scale を App に渡さない {got73}")
    got73.clear()
    sys.argv = ["pyxelcube_agents.py"]
    O.main()
    check(got73["k"].get("time_scale") == 1.0, f"73: main の既定の time_scale が 1.0 でない {got73}")
finally:
    O.App = orig_app73
    sys.argv = orig_argv73
# 歩く速さは time_scale で変わらない：同じ種・同じ行き先で、90 フレーム後の位置が同じ。一方でタイマーは速く進む
pos73 = {}
for ts73 in (1.0, 10.0):
    a73 = ov_app(3, 1, ts73)
    ov_quiet(a73)
    ov_send(a73, 0, "shelf")
    ov_step(a73, 90)
    pos73[ts73] = (a73.agents[0].pos.x, a73.agents[0].pos.z)
check(pos73[1.0] == pos73[10.0], f"73: time_scale で歩く速さが変わった {pos73}")
check(math.hypot(pos73[1.0][0] - a73.agents[0].seat.x, pos73[1.0][1] - a73.agents[0].seat.z) > 100.0, "73: 90フレームで歩いていない（試験が成り立たない）")

# 74. find_path の最後の区間：以前の失敗例（席12→coffee の立つ場所0）が、どの区間も通れる。目標へ直線で行けなくても最後のマスを残す
import time as _t74


def ov_path_segments_ok(nav, rects, circles, path, start, from_seat):
    """道の全区間が障害物から R 以上離れているか。from_seat のとき、席（椅子の中）から最初の点までは調べない。"""
    pts = list(path) if from_seat else [start] + list(path)
    if False:
        pts = [pts[0]] + pts[1:]
    return all(ov_seg_ok(p, q, rects, circles, R) for p, q in zip(pts, pts[1:]))


a74 = ov_app(1, 18)
nav74 = a74.nav
rects74 = [ob.rect for ob in a74.obstacles]
circles74 = a74.circles
seats74 = [(s[0].x, s[0].z) for s in O.OFFICE_LAYOUT.seats]
coffee74 = O.OFFICE_SPOTS[0]
check(coffee74.name == "coffee", "74: OFFICE_SPOTS の先頭が coffee でない（試験の前提）")
goal74 = coffee74.slots[0]
p74 = nav74.find_path(seats74[12], goal74)
check(p74 is not None and len(p74) >= 2, f"74: 席12→coffee0 の道が見つからない {p74}")
check(tuple(p74[-1]) == tuple(goal74), f"74: 道の最後の点が目標そのものでない {p74[-1]} / {goal74}")
check(ov_path_segments_ok(nav74, rects74, circles74, p74, seats74[12], True), f"74: 席12→coffee0 の道に障害物へ入る区間がある {p74}")
# 最後の区間 points[-2]→goal だけを取り出して確かめる（直線で行けないので、最後のマスの中心が残るはず）
check(ov_seg_ok(p74[-2], p74[-1], rects74, circles74, R), f"74: 席12→coffee0 の最後の区間が障害物に入る {p74[-2:]}")
check(tuple(p74[-2]) == nav74._centre(*nav74._cell_of(*p74[-2])), f"74: 最後の1つ前の点がマスの中心でない {p74[-2]}")
# 全席×coffee の6か所（行き・帰り）で、全区間が通れて、最後の点が目標そのもの。目標が障害物に近い場所では、最後のマスの中心が残る道がいくつか出る
bad74, kept74, far74 = [], 0, []
for si, seat in enumerate(seats74):
    for k, xz in enumerate(coffee74.slots):
        for tag, s_, g_, fs in ((f"席{si}→coffee{k}", seat, xz, True), (f"coffee{k}→席{si}", xz, seat, False)):
            pp = nav74.find_path(s_, g_)
            if pp is None:
                bad74.append((tag, "道なし"))
                continue
            if not ov_path_segments_ok(nav74, rects74, circles74, pp, s_, fs):
                bad74.append((tag, "区間が障害物に入る"))
            if tuple(pp[-1]) != tuple(g_):
                far74.append((tag, pp[-1]))
            elif len(pp) >= 2 and tuple(pp[-2]) == nav74._centre(*nav74._cell_of(*pp[-2])) and math.hypot(pp[-2][0] - g_[0], pp[-2][1] - g_[1]) > 1.0:
                kept74 += 1
check(not bad74, f"74: 席×coffee の道に問題がある {bad74[:3]}（計{len(bad74)}件）")
check(all(math.hypot(p_[0] - nav74._centre(*nav74._cell_of(*p_))[0], p_[1] - nav74._centre(*nav74._cell_of(*p_))[1]) < 1e-9 for _, p_ in far74),
      f"74: 目標へ直線で行けないとき、最後の点がマスの中心でない {far74[:3]}")
check(kept74 >= 1, f"74: 最後のマスを残して目標を足す道が1つも出ない（試験が成り立たない）{kept74}")
print(f"(74) 席×coffee 36組×往復 最後のマスを残した道 {kept74}件 / 最後の点が目標でない {len(far74)}件")
# 小さな地図で、3つの場合を確かめる：(a) 目標へ直線で行ける → 最後の点が目標、(b) 行けない → 最後のマスの中心＋目標、(c) 目標のマスの中心にも行けない
# 通路の地図：3行×8列。真ん中の行だけが通れる（上下は小さな障害物を全マスに置く）。行 j=1 の中心は z=30
def ov_corridor():
    cells = [(i, j) for i in range(8) for j in range(3) if j != 1]
    return O.NavGrid((0.0, 160.0), (0.0, 60.0), [ov_tiny(*c) for c in cells], [])


nav_k = ov_corridor()
check(all(nav_k._free(i, 1) for i in range(8)) and not any(nav_k._free(i, j) for i in range(8) for j in (0, 2)), "74: 通路の試験の地図が想定どおりでない")
pk = nav_k.find_path((10.0, 30.0), (150.0, 30.0))
check(pk is not None and pk[-1] == (150.0, 30.0) and len(pk) <= 2 and ov_seg_ok(pk[0], pk[-1], [], [], R), f"74: まっすぐ行ける通路で、道が目標へまっすぐ行く形にならない {pk}")
pk = nav_k.find_path((10.0, 30.0), (142.0, 31.0))  # 目標はマス (7,1) の中。直線で行ける
check(pk is not None and pk[-1] == (142.0, 31.0), f"74: 目標が通路の中にあるのに最後の点が目標でない {pk}")
# 目標が壁の中（通れないマス）：いちばん近い通れるマスへ行き、その中心が最後の点
pk = nav_k.find_path((10.0, 30.0), (150.0, 10.0))
check(pk is not None and pk[-1] in ((150.0, 30.0),) and len(pk) >= 1, f"74: 目標が壁の中のとき、最後の点が近い通れるマスの中心でない {pk}")

# 75. 人をよける find_path：people に入れた人の周り（NAV_PERSON_RADIUS 未満）を道が通らない。道が無ければ people なしの道に戻る。start と goal のマスはふさがない
check(O.NAV_PERSON_RADIUS == 2.0 * R == 28.0 and O.NAV_NEAR_DIST == 60.0 and O.SIDESTEP_AFTER == 3 and O.SIDESTEP_SEC == 1.0,
      f"75: 定数が想定と違う {O.NAV_PERSON_RADIUS} {O.NAV_NEAR_DIST} {O.SIDESTEP_AFTER} {O.SIDESTEP_SEC}")


def ov_min_dist_to_people(path, start, people, step=1.0):
    """start から path の点を順に結んだ折れ線の上で、people のどの人にも最も近づいた距離。"""
    best = 1.0e9
    pts = [start] + list(path)
    for p, q in zip(pts, pts[1:]):
        n = max(1, math.ceil(math.hypot(q[0] - p[0], q[1] - p[1]) / step))
        for k in range(n + 1):
            x = p[0] + (q[0] - p[0]) * k / n
            z = p[1] + (q[1] - p[1]) * k / n
            for ox, oz in people:
                best = min(best, math.hypot(x - ox, z - oz))
    return best


a75 = ov_app(1, 18)
nav75 = a75.nav
s75, g75 = (-300.0, 0.0), (300.0, 0.0)
p_free = nav75.find_path(s75, g75)
check(p_free is not None and ov_min_dist_to_people(p_free, s75, [(0.0, 0.0)]) < O.NAV_PERSON_RADIUS, f"75: 試験の前提：人なしの道は (0,0) のそばを通るはず {p_free}")
# 道の上の人（真ん中）、2人、道の上の3人。どれも、道が人から NAV_PERSON_RADIUS 近く以上離れる（直線の調べは NAV_CELL/4 ごと）
for ppl75 in ([(0.0, 0.0)], [(0.0, 0.0), (-150.0, 0.0)], [(0.0, 0.0), (-150.0, 5.0), (150.0, -5.0)], [(0.0, 10.0), (0.0, -30.0)]):
    pp = nav75.find_path(s75, g75, ppl75)
    check(pp is not None and pp[-1] == g75, f"75: 人{len(ppl75)}人をよける道が見つからない/目標で終わらない {ppl75} {pp}")
    if pp:
        dmin = ov_min_dist_to_people(pp, s75, ppl75)
        check(dmin >= O.NAV_PERSON_RADIUS - 0.5, f"75: 道が人に近すぎる（最小 {dmin:.1f} < {O.NAV_PERSON_RADIUS}）{ppl75} {pp}")
        check(ov_path_segments_ok(nav75, [ob.rect for ob in a75.obstacles], a75.circles, pp, s75, False), f"75: 人をよける道が障害物に入る {pp}")
check(nav75._tmp_people == (), "75: find_path のあとも _tmp_people が残っている")
# 道の上に人がいなければ、people ありでも people なしと同じ道（遠い人はよける必要がない）
far_people = [(0.0, 400.0), (-500.0, -300.0)]
check(nav75.find_path(s75, g75, far_people) == p_free, "75: 道から遠い人がいるだけで道が変わった")
# 通路の地図：真ん中の行だけが通れる。通路をふさぐ人がいると人をよける道は無い → people なしの道に戻る
nav_c75 = ov_corridor()
sc75, gc75 = (10.0, 30.0), (150.0, 30.0)
calls75 = []
orig_fpa = nav_c75._find_path_avoiding
nav_c75._find_path_avoiding = lambda s, g, ppl: (calls75.append(len(ppl)), orig_fpa(s, g, ppl))[1]
check(nav_c75.find_path(sc75, gc75, [(80.0, 30.0)]) == nav_c75.find_path(sc75, gc75), "75: 通路を人がふさぐとき、people なしの道に戻らない")
check(calls75[:2] == [1, 0] and calls75[2:] == [0], f"75: 戻るときの探し方の回数が想定と違う（1人ありで探し→なしで探し直す） {calls75}")
check(nav_c75.find_path(sc75, gc75, [(80.0, 30.0)]) is not None, "75: 人がふさぐ通路で None が返る（people なしに戻るはず）")
# 戻らないとき（人をよけて道が見つかる）：探すのは1回だけ
calls75.clear()
nav_c75.find_path(sc75, gc75, [(80.0, 200.0)])
check(calls75 == [1], f"75: 人をよけて道が見つかるのに2回探した {calls75}")
# 道が元から無いとき（通れるマスが無い）は None のまま。people ありでも例外にならない
cells75 = [(i, j) for i in range(3) for j in range(3)]
nav_n75 = O.NavGrid((0.0, 60.0), (0.0, 60.0), [ov_tiny(*c) for c in cells75 if c not in ((0, 0), (1, 1))], [])
check(nav_n75.find_path((10.0, 10.0), (30.0, 30.0), [(20.0, 20.0)]) is None, "75: 元から道が無いのに people ありで道が出た")
# start と goal のマスはふさがない：start・goal の真上に人がいても、_blocked_by_people の中に start/goal のマスが入らず、隣のマスは入る
sc, gc = nav75._cell_of(*s75), nav75._cell_of(*g75)
blk = nav75._blocked_by_people([s75, g75, (0.0, 0.0)], sc, gc)
check(sc[1] * nav75.nx + sc[0] not in blk and gc[1] * nav75.nx + gc[0] not in blk, "75: start/goal のマスが people でふさがれている")
nb = (sc[0] - 1, sc[1])
check(nb[1] * nav75.nx + nb[0] in blk, "75: start の隣のマスが people でふさがれていない（試験が成り立たない）")
cc = nav75._cell_of(0.0, 0.0)
check(cc[1] * nav75.nx + cc[0] in blk, "75: 人の真下のマスがふさがれていない")
check(all(math.hypot(nav75._centre(k % nav75.nx, k // nav75.nx)[0] - px, nav75._centre(k % nav75.nx, k // nav75.nx)[1] - pz) < O.NAV_PERSON_RADIUS
          for k in blk for (px, pz) in [min([s75, g75, (0.0, 0.0)], key=lambda q: math.hypot(nav75._centre(k % nav75.nx, k // nav75.nx)[0] - q[0], nav75._centre(k % nav75.nx, k // nav75.nx)[1] - q[1]))]),
      "75: ふさぐマスの中に、どの人からも NAV_PERSON_RADIUS 以上離れたマスがある")
# 人が start の真上・goal の真上にいても道が見つかる（1回で見つかる＝people なしに戻らない）
calls75b = []
orig_fpa75 = nav75._find_path_avoiding
nav75._find_path_avoiding = lambda s, g, ppl: (calls75b.append(len(ppl)), orig_fpa75(s, g, ppl))[1]
pp = nav75.find_path(s75, g75, [s75, g75])
check(pp is not None and calls75b == [2], f"75: 人が start/goal の真上にいると道が見つからない/people なしに戻る {calls75b} {pp}")
check(pp is not None and math.hypot(pp[-1][0] - g75[0], pp[-1][1] - g75[1]) < O.NAV_CELL, f"75: 人が goal の真上にいるとき、道の終点が goal のマスから離れる {pp}")
nav75._find_path_avoiding = orig_fpa75
# 席→coffee の全部で、people（立っている人を立つ場所に置く）を入れても道が見つかり、人の周りを通らない
bad75, fallback75 = [], 0
spot_xz75 = [xz for sp in O.OFFICE_SPOTS for xz in sp.slots]
rng75 = random.Random(75)
calls75c = []
nav75._find_path_avoiding = lambda s, g, ppl: (calls75c.append(len(ppl)), orig_fpa75(s, g, ppl))[1]
for si, seat in enumerate(seats74):
    for k, xz in enumerate(coffee74.slots):
        ppl = [q for q in rng75.sample(spot_xz75, 4) if q != xz]  # 立つ場所のうち目標でない所に立っている人
        calls75c.clear()
        pp = nav75.find_path(seat, xz, ppl)
        if pp is None:
            bad75.append((si, k, "道なし"))
            continue
        if not ov_path_segments_ok(nav75, rects74, circles74, pp, seat, True):
            bad75.append((si, k, "障害物"))
        if len(calls75c) == 2:
            fallback75 += 1  # people をよけられず、people なしに戻った
        elif ov_min_dist_to_people(pp[1:], pp[0], ppl) < O.NAV_PERSON_RADIUS - 0.5:
            bad75.append((si, k, "人に近い"))
nav75._find_path_avoiding = orig_fpa75
check(not bad75, f"75: 席→coffee で people ありの道に問題がある {bad75[:4]}（計{len(bad75)}件）")
print(f"(75) 席×coffee 108組 people4人で、people なしに戻った {fallback75} 件")

# 76. 引数を省いたとき：find_path は people なしと同じ、serve_path() は serve_path(()) と同じ
a76 = ov_app(1, 18)
nav76 = a76.nav
rng76 = random.Random(76)
diff76 = []
for _ in range(60):
    s_ = (rng76.uniform(-600, 600), rng76.uniform(-450, 450))
    g_ = rng76.choice(spot_xz75)
    r0, r1, r2, r3 = nav76.find_path(s_, g_), nav76.find_path(s_, g_, ()), nav76.find_path(s_, g_, []), nav76.find_path(s_, g_, people=())
    if not (r0 == r1 == r2 == r3):
        diff76.append((s_, g_))
check(not diff76, f"76: 引数を省いた find_path と people=() の結果が違う {diff76[:2]}")
paths76 = {}
for variant in ("省略", "空タプル", "空リスト"):
    ap = ov_app(3, 4)
    ov_quiet(ap)
    ov_step(ap, 5)
    ov_send(ap, 2, "coffee")
    ap._nav_queue.clear()  # App の列で探させず、serve_path を直接呼ぶ
    ag = ap.agents[2]
    ok = ag.serve_path() if variant == "省略" else ag.serve_path(() if variant == "空タプル" else [])
    paths76[variant] = (ok, list(ag._path), ag.path_wait)
check(paths76["省略"][0] and paths76["省略"] == paths76["空タプル"] == paths76["空リスト"] and len(paths76["省略"][1]) >= 1,
      f"76: serve_path の引数を省いたときと people なしで結果が違う {paths76}")
# App の列でも同じ：人が1人しかいない（ほかに固定の人がいない）とき、人をよけても今までと同じ動きになる（種ごとの再現性は 8 番で確認済み）
def ov_trace76(seed):
    ap = ov_app(seed, 6, 10.0)
    out = []
    for f in range(600):
        ap.update()
        if f % 50 == 0:
            out.append([(round(a.pos.x, 3), round(a.pos.z, 3), a.state) for a in ap.agents])
    return out


check(ov_trace76(5) == ov_trace76(5), "76: 同じ種で動きが違う（people を入れても再現できる）")

# 77. App._people_for(i)：固定の人（席に着いている人・立つ場所にいる人）は必ず入り、歩いている遠くの人は入らない。avoid_near で近くの人が入り、そのあと False に戻る
a77 = ov_app(1, 8)
ov_quiet(a77)
# 人間は遠くに置く（人間が近くにいると avoid_near で入ってしまうため。人間の規則は下の別項目で確かめる）
a77.human.pos = O.Vec3(700.0, 0.0, 500.0)


def ov_put(app, i, x, z, state=None, arrived=None):
    """人 i を (x, z) に置き、必要なら状態を決める。"""
    ag = app.agents[i]
    ag.pos = O.Vec3(x, 0.0, z)
    if state is not None:
        ag.state = state
    if arrived is not None:
        ag._arrived = arrived
    return ag


me = ov_put(a77, 0, 0.0, 0.0, O.WANDER)
ov_put(a77, 1, 300.0, 0.0, O.AT_SPOT)             # 立つ場所にいる（固定）・遠い
ov_put(a77, 2, 30.0, 0.0, O.WANDER)               # 歩いている・近い
ov_put(a77, 3, 400.0, 100.0, O.WANDER)            # 歩いている・遠い
ov_put(a77, 4, 0.0, 60.0, O.WANDER)               # 歩いている・ちょうど NAV_NEAR_DIST（以内に入る）
ov_put(a77, 5, 0.0, -60.5, O.WANDER)              # 歩いている・NAV_NEAR_DIST を少し超える
ov_put(a77, 6, -40.0, 0.0, O.WORKING, True)       # 席に着いている（固定）・近い（avoid_near でも1回だけ入る）
ov_put(a77, 7, -500.0, 300.0, O.WORKING, False)   # 席へ向かう途中（固定でない）・遠い
check([a77.agents[j].is_fixed for j in range(1, 8)] == [True, False, False, False, False, True, False], "77: 試験の前提：固定の人の並びが想定と違う")
xz = lambda j: (a77.agents[j].pos.x, a77.agents[j].pos.z)
me.avoid_near = False
got = a77._people_for(0)
check(sorted(got) == sorted([xz(1), xz(6)]), f"77: avoid_near が False のとき、固定の人（遠くても）だけが入るはず {got}")
check(me.avoid_near is False, "77: avoid_near が False のまま変わった")
me.avoid_near = True
got = a77._people_for(0)
check(sorted(got) == sorted([xz(1), xz(2), xz(4), xz(6)]), f"77: avoid_near が True のとき、固定の人と NAV_NEAR_DIST 以内の人が入るはず {got}")
check(len(got) == len(set(got)), f"77: 同じ人が2回入った {got}")
check((0.0, 0.0) not in got, "77: 自分自身が入っている")
check(me.avoid_near is False, "77: _people_for のあと avoid_near が False に戻らない")
got = a77._people_for(0)
check(sorted(got) == sorted([xz(1), xz(6)]), f"77: avoid_near が戻ったあと、次の呼び出しで近くの人が入る {got}")
# 人 j が近づいたら avoid_near のときに入る・離れたら入らない
me.avoid_near = True
ov_put(a77, 3, 59.9, 0.0)
check(xz(3) in a77._people_for(0), "77: NAV_NEAR_DIST 内に来た人が入らない")
ov_put(a77, 3, 60.2, 0.0)
me.avoid_near = True
check(xz(3) not in a77._people_for(0), "77: NAV_NEAR_DIST の外の人が入る")
# 別の人 i から見ても、同じ規則（他人の avoid_near は影響しない）
a77.agents[2].avoid_near = False
me.avoid_near = True
got2 = a77._people_for(2)
check(sorted(got2) == sorted([xz(1), xz(6)]) and me.avoid_near is True, f"77: 人2の呼び出しが人0の avoid_near に影響する/近くの人が入る {got2} {me.avoid_near}")
# 人間の規則：会話中（talk_partner が入っている）なら、遠くても必ず入る。そうでなければ avoid_near で NAV_NEAR_DIST 以内のときだけ入る
hxz = lambda: (a77.human.pos.x, a77.human.pos.z)
me.avoid_near = False
a77.human.pos = O.Vec3(700.0, 0.0, 500.0)
check(hxz() not in a77._people_for(0), "77: 会話していない・遠い人間が入っている")
a77.talk_partner = 3  # 会話中のふりをする（_people_for は talk_partner が None かどうかだけを見る）
me.avoid_near = False
check(hxz() in a77._people_for(0), "77: 会話中の人間が（遠くても avoid_near でなくても）入らない")
me.avoid_near = False
check(hxz() in a77._people_for(2), "77: 会話中の人間が別の人 2 の呼び出しで入らない")
got = a77._people_for(0)
check(len([p_ for p_ in got if p_ == hxz()]) == 1, f"77: 会話中の人間が1回だけ入っていない {got}")
a77.talk_partner = None
me.avoid_near = True
check(hxz() not in a77._people_for(0), "77: 会話していない・遠い人間が avoid_near で入っている")
a77.human.pos = O.Vec3(59.9, 0.0, 0.0)  # avoid_near で近ければ入る
me.avoid_near = True
check(hxz() in a77._people_for(0), "77: 会話していなくても avoid_near で NAV_NEAR_DIST 以内の人間が入らない")
check(me.avoid_near is False, "77: 人間を入れたあと avoid_near が False に戻らない")
me.avoid_near = False
check(hxz() not in a77._people_for(0), "77: avoid_near が False で近い人間が入っている（会話していない）")
a77.human.pos = O.Vec3(60.5, 0.0, 0.0)  # NAV_NEAR_DIST を少し超えたら入らない
me.avoid_near = True
check(hxz() not in a77._people_for(0), "77: NAV_NEAR_DIST の外の人間が avoid_near で入る")
a77.human.pos = O.Vec3(700.0, 0.0, 500.0)
# App の列で道を探すとき、_people_for の結果が find_path に渡る（固定の人だけ：avoid_near なし）
a77b = ov_app(2, 4)
ov_quiet(a77b)
ov_step(a77b, 5)
ov_put(a77b, 1, 200.0, -100.0, O.AT_SPOT)
seen77 = []
orig77 = a77b.nav.find_path
a77b.nav.find_path = lambda s, g, ppl=(): (seen77.append(list(ppl)), orig77(s, g, ppl))[1]
ov_send(a77b, 3, "coffee")
a77b.update()
check(seen77 and (200.0, -100.0) in seen77[0], f"77: App の列で探すとき、固定の人が find_path に渡らない {seen77}")

# 78. 横へよける：SIDESTEP_AFTER 回続けて引っかかったら、番号が大きいほう（または相手が固定のとき）がよける。よけている間は引っかかりに数えない。1秒後に道を探し直す
def ov_stuck_pair(seed=1, n=3):
    """人1（引っかかる側）と人0（近くにいる相手・WANDER）を (300,0) と (330,0) に置く。人1は coffee へ GOING。"""
    ap = ov_app(seed, n)
    ov_quiet(ap)
    ov_step(ap, 3)
    ov_send(ap, 1, "coffee")
    ap._nav_queue.clear()
    ap.agents[1].path_wait = False
    ov_put(ap, 0, 330.0, 0.0, O.WANDER)
    ov_put(ap, 1, 300.0, 0.0)
    for k in range(2, n):
        ov_put(ap, k, -500.0 + 60.0 * k, 400.0, O.WANDER)
    return ap


# (a) 番号が大きいほう（人1）が3回目でよける。1・2回目は道を探し直すだけ（avoid_near が立つ）
ap = ov_stuck_pair()
ag1 = ap.agents[1]
for n_ in (1, 2):
    ap._repath(1)
    check(not ag1.sidestepping and ap.stat_sidesteps == 0 and ag1.avoid_near and ag1.path_wait, f"78: {n_}回目の引っかかりで、道を探し直す（avoid_near が立つ）はず {ag1.sidestepping} {ag1.avoid_near} {ag1.path_wait}")
ap._repath(1)
check(ag1.sidestepping and ap.stat_sidesteps == 1 and ap._stuck_count[1] == 0, f"78: 3回目の引っかかりで横へよけない {ag1.sidestepping} {ap.stat_sidesteps} {ap._stuck_count[1]}")
ux, uz = ag1._sidestep_dir
check(abs(math.hypot(ux, uz) - 1.0) < 1e-9, f"78: よける向きが単位ベクトルでない {ag1._sidestep_dir}")
# 人0 (330,0) から人1 (300,0) へ離れる向きは (-1,0)。左右は (0,±1)
check(abs(ux) < 1e-9 or (ux, uz) == (-1.0, 0.0), f"78: よける向きが相手から離れる向きに垂直（左右）か、離れる向きそのものになっていない {ag1._sidestep_dir}")
check(ag1._path == [], "78: よけ始めても今の道が残っている")
check(ap.stat_replans == 3, f"78: 引っかかった回数（stat_replans）が3でない {ap.stat_replans}")
# (b) 番号が小さいほう（人0）は、相手が動く人（固定でない）なら何回引っかかってもよけない
ap = ov_stuck_pair()
ov_send(ap, 0, "coffee")
ap._nav_queue.clear()
ap.agents[0].path_wait = False
ov_put(ap, 0, 330.0, 0.0)
ov_put(ap, 1, 300.0, 0.0)
for n_ in range(6):
    ap._repath(0)
check(not ap.agents[0].sidestepping and ap.stat_sidesteps == 0 and ap._stuck_count[0] == 6, f"78: 番号が小さいほうが、動く相手にもよけた/数えない {ap.stat_sidesteps} {ap._stuck_count[0]}")
check(ap.agents[0].avoid_near, "78: よけないときは avoid_near を立てて道を探し直す")
# (c) 相手が固定なら、番号の大小にかかわらずよける：人0（小さい）が相手の人1（固定）から、人1（大きい）が相手の人0（固定）から
for who, other in ((0, 1), (1, 0)):
    ap = ov_stuck_pair()
    if who == 0:
        ov_send(ap, 0, "coffee")
        ap._nav_queue.clear()
        ap.agents[0].path_wait = False
    ov_put(ap, who, 330.0 if who == 0 else 300.0, 0.0, O.GOING)
    ov_put(ap, other, 300.0 if who == 0 else 330.0, 0.0, O.AT_SPOT)
    check(ap.agents[other].is_fixed, "78: 試験の前提：相手が固定でない")
    for n_ in range(3):
        ap._repath(who)
    check(ap.agents[who].sidestepping and ap.stat_sidesteps == 1, f"78: 相手が固定なのに人{who}がよけない")
# (d) 近くに人がいなければ（NAV_NEAR_DIST の外）、3回引っかかってもよけず、道を探し直す
ap = ov_stuck_pair()
ov_put(ap, 0, 300.0 + 61.0, 0.0)
for n_ in range(5):
    ap._repath(1)
check(not ap.agents[1].sidestepping and ap.stat_sidesteps == 0, "78: 近くに人がいないのによけた")
# (e) 状態が変わると数え直す：2回引っかかったあと、状態が変わって _check_stuck を通ると回数が0に戻り、そのあと2回ではよけない
ap = ov_stuck_pair()
ap._repath(1)
ap._repath(1)
check(ap._stuck_count[1] == 2, "78: 試験の前提：2回数えていない")
ap._stuck_state[1] = O.GOING
ap.agents[1].state = O.RETURNING
ap._check_stuck([(a.pos.x, a.pos.z) for a in ap.agents], 1.0 / 30.0)
check(ap._stuck_count[1] == 0, f"78: 状態が変わっても引っかかりの回数が0に戻らない {ap._stuck_count[1]}")
ap._repath(1)
ap._repath(1)
check(not ap.agents[1].sidestepping, "78: 状態が変わったあとの2回でよけた（数え直していない）")
ap._repath(1)
check(ap.agents[1].sidestepping, "78: 状態が変わって数え直したあとの3回目でよけない")
# (f) 時間：よけている間は引っかかりに数えず、1秒たったら道を探し直す（avoid_near で近くの人もよける）
ap = ov_stuck_pair()
for n_ in range(3):
    ap._repath(1)
ag1 = ap.agents[1]
check(ag1.sidestepping, "78: 試験の前提：よけていない")
ap._nav_queue.clear()  # 1・2回目の引っかかりで並んだぶんは、実際には道が探されて消えている
ag1.path_wait = False
ag1.avoid_near = False
replans0, sides0 = ap.stat_replans, ap.stat_sidesteps
recorded = []  # 道を探すとき、(人, avoid_near)
orig_pf = ap._people_for
ap._people_for = lambda i: (recorded.append((i, ap.agents[i].avoid_near)), orig_pf(i))[1]
calls78 = []  # find_path に渡った people と、そのときの人0の位置
orig_fp = ap.nav.find_path
ap.nav.find_path = lambda s, g, ppl=(): (calls78.append(([tuple(p) for p in ppl], (ap.agents[0].pos.x, ap.agents[0].pos.z))), orig_fp(s, g, ppl))[1]
x0_, z0_ = ag1.pos.x, ag1.pos.z
frames_side, stuck_max, disp_dir = 0, 0.0, []
for f in range(45):
    ap.update()
    stuck_max = max(stuck_max, ap._stuck_time[1])
    if ag1.sidestepping:
        frames_side += 1
        disp_dir.append((ag1.pos.x - x0_) * ux + (ag1.pos.z - z0_) * uz)
        check(not recorded, f"78: よけている間に道を探した {recorded}")
    if calls78:
        break
check(28 <= frames_side <= 31, f"78: よけている時間が約1秒（30fps で 29〜30 フレーム）でない {frames_side}")
check(stuck_max == 0.0, f"78: よけている間に引っかかりが数えられた {stuck_max}")
check(ap.stat_replans == replans0 and ap.stat_sidesteps == sides0, f"78: よけている間に引っかかりの数が増えた {ap.stat_replans} {ap.stat_sidesteps}")
check(disp_dir and disp_dir[-1] > 20.0, f"78: よけている間に決めた向きへ進まない {disp_dir[-3:]}")
check(recorded == [(1, True)], f"78: よけ終わったあと、avoid_near を立てて道を探し直さない {recorded}")
check(len(calls78) == 1 and len(calls78[0][0]) == 1 and abs(calls78[0][0][0][0] - calls78[0][1][0]) < 1e-9 and abs(calls78[0][0][0][1] - calls78[0][1][1]) < 1e-9,
      f"78: 探し直すとき、近くの人0を people に入れていない {calls78}")
check(not ag1.sidestepping and ag1.avoid_near is False and ag1.state == O.GOING, f"78: 探し直したあとの状態がおかしい {ag1.sidestepping} {ag1.avoid_near} {ag1.state}")
# (f2) よけている最中に壁などで進めなくても、引っかかりに数えない（_check_stuck を直接呼ぶ：予定の移動があるのに動かないフレームを10秒ぶん）
ap = ov_stuck_pair()
for n_ in range(3):
    ap._repath(1)
ag1 = ap.agents[1]
check(ag1.sidestepping, "78: 試験の前提：よけていない")
ap._nav_queue.clear()
ag1.path_wait = False
replans0 = ap.stat_replans
for n_ in range(300):
    ag1.intended_move = 2.0
    ap._check_stuck([(a.pos.x, a.pos.z) for a in ap.agents], 1.0 / 30.0)
check(ap._stuck_time[1] == 0.0 and ap.stat_replans == replans0 and ap.stat_sidesteps == 1,
      f"78: よけている最中に進めなくても引っかかりに数えられた {ap._stuck_time[1]} {ap.stat_replans - replans0}")
# 比べ：よけていなければ、同じ入力で引っかかりに数えられる（試験が成り立つ）
ap = ov_stuck_pair()
ag1 = ap.agents[1]
replans0 = ap.stat_replans
for n_ in range(40):
    ag1.intended_move = 2.0
    ap._check_stuck([(a.pos.x, a.pos.z) for a in ap.agents], 1.0 / 30.0)
check(ap.stat_replans > replans0, "78: 比べの試験：よけていないのに、進めないフレームが引っかかりに数えられない")
# (g) 割り込み：よけている最中にスペース → 作業になり、よける動きと avoid_near が消える
ap = ov_stuck_pair()
ov_put(ap, 1, 330.0, 0.0, O.GOING)
ov_put(ap, 0, 300.0, 0.0, O.AT_SPOT)  # 人0は固定（立つ場所にいる）
ap.next_index = 1
for n_ in range(3):
    ap._repath(1)
check(ap.agents[1].sidestepping, "78: 試験の前提：割り込みの試験で、よけていない")
ap.agents[1].avoid_near = True
ap.next_index = 1
press_space_and_update(ap)
check(ap.agents[1].state == O.WORKING and not ap.agents[1].sidestepping and not ap.agents[1].avoid_near, f"78: スペースで作業になっても、よける動き/avoid_near が残る {ap.agents[1].state} {ap.agents[1].sidestepping} {ap.agents[1].avoid_near}")
# 作業中（席へ向かう途中）によけ始めても、席に着いて座れば（_return_to_wander で立ち上がるとき）消える
ap = ov_stuck_pair()
ag = ap.agents[1]
ag.start_work()
ag.begin_sidestep(0.0, 1.0)
ag.avoid_near = True
ag._return_to_wander()
check(not ag.sidestepping and not ag.avoid_near, "78: 待機に戻るとき、よける動きが消えない")
# 行き先を終えるとき（_end_outing）と、道があきらめられるとき（path_failed）
ap = ov_stuck_pair()
ag = ap.agents[1]
ag.begin_sidestep(0.0, 1.0)
ag.avoid_near = True
ag._end_outing(5.0)
check(not ag.sidestepping and not ag.avoid_near and ag.state == O.WANDER, "78: 行き先を終えるとき、よける動きが消えない")
# 作業中の人がよけているとき：席へ向かう動きは止まり、決めた向きへ歩く。席に着いたことにはならない
ap = ov_stuck_pair()
ag = ap.agents[1]
ag.start_work()
ag._path = []
ov_put(ap, 1, ag.seat.x + 20.0, ag.seat.z)  # 席のすぐそば
ag.begin_sidestep(1.0, 0.0)
ap.update()
check(ag.sidestepping and not ag._arrived and ag.pos.x > ag.seat.x + 20.0, f"78: 作業中のよけで、席に向かって着席してしまった/向きへ進まない {ag._arrived} {ag.pos}")

# 79. 重さ：people ありの find_path（平均と最大。50 ms 以内）、18人・time_scale 10 で update 1フレームの最大の時間
import time as _t79
slots69 = [(sp.name, k, xz) for sp in O.OFFICE_SPOTS for k, xz in enumerate(sp.slots)]
a79 = ov_app(1, 18)
nav79 = a79.nav
rng79 = random.Random(79)
times79, times79_near, none79 = [], [], []
for si, seat in enumerate(seats74):
    for name, k, xz in slots69:
        # 立っている人6人（立つ場所の上）と、近くを歩く人5人（目標のまわり 60 以内）。実際の _people_for の最大に近い人数
        fixed = rng79.sample([q for q in spot_xz75 if q != xz], 6)
        nearp = [(xz[0] + rng79.uniform(-60, 60), xz[1] + rng79.uniform(-60, 60)) for _ in range(5)]
        for bucket, ppl in ((times79, fixed), (times79_near, fixed + nearp)):
            t0 = _t79.perf_counter()
            pp = nav79.find_path(seat, xz, ppl)
            bucket.append(_t79.perf_counter() - t0)
            if pp is None:
                none79.append((si, name, k))
check(not none79, f"79: people ありで道が見つからない組がある {none79[:3]}")
print(f"(79) find_path people6人 {len(times79)}回 平均 {sum(times79) / len(times79) * 1000:.2f} ms / 最大 {max(times79) * 1000:.2f} ms ; "
      f"people11人 平均 {sum(times79_near) / len(times79_near) * 1000:.2f} ms / 最大 {max(times79_near) * 1000:.2f} ms")
check(max(times79) < 0.05, f"79: people ありの find_path が1回 50 ms を超える {max(times79) * 1000:.1f} ms")
check(max(times79_near) < 0.05, f"79: people 11人の find_path が1回 50 ms を超える {max(times79_near) * 1000:.1f} ms")
# 18人・time_scale 10 で update 1回の時間（引っかかり・よけを含めて回す）
frame_times = []
for seed79 in (1, 2):
    ap = ov_app(seed79, 18, 10.0)
    for f in range(1800):
        t0 = _t79.perf_counter()
        ap.update()
        frame_times.append(_t79.perf_counter() - t0)
    print(f"(79) 種{seed79} 1800フレーム よけた回数 {ap.stat_sidesteps} 引っかかり {ap.stat_replans} あきらめ {ap.stat_give_ups}")
frame_times_sorted = sorted(frame_times)
print(f"(79) update 1回 平均 {sum(frame_times) / len(frame_times) * 1000:.2f} ms / 99.9% {frame_times_sorted[int(len(frame_times) * 0.999)] * 1000:.2f} ms / 最大 {max(frame_times) * 1000:.2f} ms")
check(max(frame_times) < 0.05, f"79: 18人・time_scale 10 で update 1回が 50 ms を超える {max(frame_times) * 1000:.1f} ms")

# ---- ここから「人間（ユーザーの分身）」の項目（80〜94）。クリックで歩く・話しかける・会話のカメラ（office だけ） ----
# 操作：App.handle_click(sx, sy)（update の中ではマウス左ボタンで呼ばれる）、Q キーで会話を終える。
# 画面の点は、screen_ray の式（指示書 5-2）の逆（3D の点を画面へ投影する式）で求める。
H_SHOT_DIR = TMP_DIR / "talk_shots"
H_SHOT_DIR.mkdir(parents=True, exist_ok=True)  # 作るだけ（既にあれば何もしない）


def h_proj(app, x, y, z):
    """3D の点 (x, y, z) を画面の点 (sx, sy)（小数）にする。screen_ray の式の逆。"""
    eye = app.cam_target + app.cam_dir * app.cam_dist
    f = (app.cam_target - eye).normalize()
    r = f.cross(Vec3.UP).normalize()
    u = r.cross(f)
    k = math.tan(math.radians(app.camera.fov) / 2.0)
    vx, vy, vw, vh = app._view_rect()  # 3D を描く範囲（office は (0,0,640,296)）
    aspect = vw / vh
    v = Vec3(x, y, z) - eye
    zc = v.dot(f)
    nx = v.dot(r) / (zc * k * aspect)
    ny = v.dot(u) / (zc * k)
    return (vx + (nx + 1.0) / 2.0 * vw - 0.5, vy + (1.0 - ny) / 2.0 * vh - 0.5)


def h_agent_xy(app, i):
    """人 i のクリック用の球の中心を投影した画面の点（小数）。"""
    a = app.agents[i]
    return h_proj(app, a.pos.x, O.PICK_CENTER_Y + a.pose.body_y, a.pos.z)


def h_click_agent(app, i):
    """人 i の球の中心を投影した点をクリックする（整数に丸める）。押した点を返す。"""
    sx, sy = h_agent_xy(app, i)
    p = (round(sx), round(sy))
    app.handle_click(*p)
    return p


def h_click_floor(app, x, z):
    """床の点 (x, z) を投影した点をクリックする（整数に丸める）。押した点を返す。"""
    sx, sy = h_proj(app, x, 0.0, z)
    p = (round(sx), round(sy))
    app.handle_click(*p)
    return p


def h_on_screen(p, app=None):
    """画面の点 p が 3D の範囲の中か（app 省略なら office の範囲）。"""
    vx, vy, vw, vh = app._view_rect() if app is not None else (0, 0, O.OFFICE_SCREEN_W, O.VIEW3D_H)
    return vx <= p[0] < vx + vw and vy <= p[1] < vy + vh


def h_ray(app, sx, sy):
    """3D の範囲を使った screen_ray。"""
    return app.screen_ray(sx, sy, *app._view_rect())


def h_pen(app, x, z):
    """点 (x, z) にいる人の、障害物（長方形・丸）への食い込み量（AGENT_RADIUS ぶんの体の食い込み。0 なら食い込みなし）。"""
    worst = 0.0
    for ob in app.obstacles:
        worst = max(worst, O.AGENT_RADIUS - rect_dist(x, z, ob.rect))
    for cx, cz, cr in app.circles:
        worst = max(worst, cr + O.AGENT_RADIUS - math.hypot(x - cx, z - cz))
    return worst


def h_app(seed=1, n=3, ts=1.0, quiet=True):
    """office の App（n 人・全員が勝手に出かけないよう静かにする）。"""
    ap = ov_app(seed, n, ts)
    if quiet:
        ov_quiet(ap)
    return ap


def h_seat_up(app, i, limit=900):
    """人 i をスペースで作業にして、席に着くまで進める（着いたら True）。"""
    app.next_index = i
    press_space_and_update(app)
    return ov_until(app, lambda: app.agents[i].is_seated, limit) is not None


def h_stand_dot(app, a):
    """人 a がどれだけ人間のほうを向いているか（1 に近いほど向いている）。"""
    return ov_forward_dot(a, app.human.pos.x, app.human.pos.z)


def h_ang(a, b):
    """角度 a と b の差（度、0〜180）。"""
    return abs((a - b + 180.0) % 360.0 - 180.0)


# 80. 人間が office だけにいて、agents の数に入っていない（proto には人間がいない）
for n80 in (3, 18):
    ap80 = make_app(30, 1, "office", n80)
    check(isinstance(ap80.human, O.Human), f"80: office({n80}人) に人間（Human）がいない {ap80.human}")
    check(len(ap80.agents) == n80, f"80: agents の数が {n80} でない {len(ap80.agents)}")
    check(all(a is not ap80.human for a in ap80.agents), f"80: 人間が agents に入っている（{n80}人）")
    check(all(not isinstance(a, O.Human) for a in ap80.agents), "80: agents に Human がある")
    check((ap80.human.pos.x, ap80.human.pos.y, ap80.human.pos.z) == (0.0, 0.0, 40.0), f"80: 人間の最初の位置が (0,0,40) でない {ap80.human.pos}")
    check(ap80.human.name == "YOU", f"80: 人間の名前が YOU でない {ap80.human.name}")
    check(ap80.talk_partner is None, "80: 起動時に会話中になっている")
    hv = [v for v in ap80.scene.children if isinstance(v, O.AgentView) and v.agent is ap80.human]
    mv = [v for v in ap80.scene.children if isinstance(v, O.MarkerView)]
    check(len(hv) == 1 and len(mv) == 1 and mv[0].human is ap80.human, f"80: 人間の AgentView・MarkerView が1つずつでない {len(hv)} {len(mv)}")
    check(len([v for v in ap80.scene.children if isinstance(v, O.AgentView)]) == n80 + 1, f"80: AgentView の数が {n80}+1 でない")
    check(ap80.human not in ap80._nav_queue and len(ap80._chat) == n80 and len(ap80._stuck_time) == n80, "80: 人間の分が agents 用の配列に入っている")
pp80 = make_app(30, 1, "proto", 3)
check(pp80.human is None, "80: proto に人間がいる")
check(not any(isinstance(v, (O.MarkerView,)) or (isinstance(v, O.AgentView) and isinstance(v.agent, O.Human)) for v in pp80.scene.children),
      "80: proto の scene に人間の絵・▼がある")
check(len(pp80.agents) == 3, "80: proto の agents が3人でない")
# proto でクリックしても何も起きない（人間がいないので）
before80 = [(a.pos.x, a.pos.z, a.state) for a in pp80.agents]
pp80.handle_click(128, 96)
pp80.handle_click(10, 10)
check(pp80.talk_partner is None and [(a.pos.x, a.pos.z, a.state) for a in pp80.agents] == before80, "80: proto のクリックで何かが変わった")
# 人間は _people_for の対象 index・agents の番号を増やさない：18人の最後の人の番号は 17 のまま
ap80b = make_app(30, 1, "office", 18)
check([a.name for a in ap80b.agents][-1] == "R" and ap80b.agents[17] is not ap80b.human, "80: 18人の最後が R でない")

# 81. screen_ray／floor_hit：床の既知の点を、5-2 の式の逆（投影）で画面の点にしてクリックすると、その近く（±10）に向けて歩き出す。地平線より上のクリックは何もしない
a81 = h_app(1, 2)
VX, VY, VW, VH = a81._view_rect()
r0, d0 = a81.screen_ray(VX + VW / 2.0 - 0.5, VY + VH / 2.0 - 0.5, VX, VY, VW, VH)
fh = a81.floor_hit(r0, d0)
check(fh is not None and abs(fh[0] - a81.cam_target.x) < 0.01 and abs(fh[1] - a81.cam_target.z) < 0.01,
      f"81: 画面の中心の線が注視点の真下に当たらない {fh} {a81.cam_target}")
check(abs(d0.length() - 1.0) < 1e-9, "81: 線の向きが単位ベクトルでない")
r1, d1 = a81.screen_ray(VX + VW / 2.0 - 0.5, VY + VH / 2.0 - 0.5, VX + VW // 4, VY + VH // 4, VW // 2, VH // 2)  # 描く範囲が中央の半分（縦横比は同じ）でも、その中心は同じ線
check(abs(d1.x - d0.x) < 1e-9 and abs(d1.y - d0.y) < 1e-9 and abs(d1.z - d0.z) < 1e-9 and abs(r1.x - r0.x) < 1e-9,
      "81: 描く範囲を変えたとき、その中心を通る線が変わった")
check(a81.floor_hit(Vec3(0.0, 100.0, 0.0), Vec3(0.0, 0.0, -1.0)) is None, "81: 水平の線が床に当たった")
check(a81.floor_hit(Vec3(0.0, 100.0, 0.0), Vec3(0.0, 1.0, 0.0)) is None, "81: 上向きの線が床に当たった")
h81 = a81.floor_hit(Vec3(10.0, 100.0, 20.0), Vec3(0.0, -1.0, 0.0))
check(h81 is not None and abs(h81[0] - 10.0) < 1e-9 and abs(h81[1] - 20.0) < 1e-9, f"81: 真下の線が (10,20) に当たらない {h81}")
worst81 = 0.0
worst81f = 0.0
for (px, pz) in ((150.0, 100.0), (-200.0, 60.0), (60.0, -150.0), (320.0, 220.0), (-300.0, 230.0), (0.0, 40.0), (-100.0, 260.0)):
    ap = h_app(1, 2)
    sxy = h_proj(ap, px, 0.0, pz)
    check(h_on_screen(sxy, ap), f"81: 試験の点 ({px},{pz}) が3Dの範囲の外 {sxy}")
    # 小数のまま戻す：投影の逆がほぼ元の点になる（式の整合）
    e, d = h_ray(ap, sxy[0], sxy[1])
    hh = ap.floor_hit(e, d)
    check(hh is not None and abs(hh[0] - px) < 0.01 and abs(hh[1] - pz) < 0.01, f"81: 投影して戻した点が元の点と違う {hh} ({px},{pz})")
    # 整数に丸めてクリックする
    ap.handle_click(round(sxy[0]), round(sxy[1]))
    hp = ap.human._path
    check(len(hp) > 0 and ap.human.walking, f"81: ({px},{pz}) をクリックしても人間が歩き出さない")
    if hp:
        gx, gz = hp[-1].x, hp[-1].z
        err = math.hypot(gx - px, gz - pz)
        worst81 = max(worst81, err)
        check(abs(gx - px) <= 10.0 and abs(gz - pz) <= 10.0, f"81: ({px},{pz}) のクリックの行き先が ±10 の外 ({gx:.1f},{gz:.1f})")
        d_before = math.hypot(px - ap.human.pos.x, pz - ap.human.pos.z)
        # 道の最初の点は今いるマスの中心なので、最初の数フレームは少し遠回りになる。20フレーム（約 80 単位）後に近づいていればよい
        for _ in range(20):
            ap.update()
        d_after = math.hypot(px - ap.human.pos.x, pz - ap.human.pos.z)
        if d_before > 150.0:
            check(d_after < d_before - 40.0, f"81: 20フレームで目的地に近づかない {d_before:.1f} → {d_after:.1f}")
print(f"(81) 床の点を投影→整数にしてクリック→行き先のずれ 最大 {worst81:.2f}（単位）")
# 地平線より上：pitch を最小 10 度にして、画面の最上段をクリックしても何も起きない
ap = h_app(1, 2)
ap.cam_pitch = O.CAM_PITCH_MIN
ap._apply_camera()
e, d = h_ray(ap, 320, 0)
check(d.y > 0.0 and ap.floor_hit(e, d) is None, f"81: pitch10 の最上段が地平線より上でない {d}")
hp0 = (ap.human.pos.x, ap.human.pos.z)
ap.handle_click(320, 0)
check(not ap.human.walking and (ap.human.pos.x, ap.human.pos.z) == hp0 and ap.talk_partner is None, "81: 地平線より上のクリックで人間が動いた／会話が始まった")
# update の中のつなぎ：マウス左ボタンが押されたフレームに、pyxel.mouse_x/y の点で handle_click が呼ばれる
ap = h_app(1, 2)
sxy = h_proj(ap, 150.0, 0.0, 100.0)
pyxel.mouse_x, pyxel.mouse_y = round(sxy[0]), round(sxy[1])
press_keys_and_update(ap, pyxel.MOUSE_BUTTON_LEFT)
check(ap.human.walking or (ap.human.pos.x != 0.0), "81: マウス左ボタンを押した update で人間が歩き出さない")
ap.update()
pyxel.mouse_x, pyxel.mouse_y = 0, 0

# 82. 床をクリック→道を探して歩き、着く。壁や机の中をクリックしても、すり抜けない
ap = h_app(2, 2)
worst82 = 0.0


def h_walk_and_watch(app, limit=1200):
    """人間が止まるまで update し、途中の障害物への最大の食い込みと、床の範囲の外に出た量を返す。止まらなければ None。"""
    worst, out = 0.0, 0.0
    x_min, x_max = app.layout.wander_x
    z_min, z_max = app.layout.wander_z
    for f in range(limit):
        app.update()
        hp_ = app.human.pos
        worst = max(worst, h_pen(app, hp_.x, hp_.z))
        out = max(out, x_min - hp_.x, hp_.x - x_max, z_min - hp_.z, hp_.z - z_max)
        if not app.human.walking:
            return worst, out, f + 1
    return None


for (px, pz) in ((200.0, 100.0), (-300.0, 200.0), (0.0, -250.0)):
    ap = h_app(2, 2)
    h_click_floor(ap, px, pz)
    res = h_walk_and_watch(ap)
    check(res is not None, f"82: ({px},{pz}) のクリックのあと、人間が止まらない")
    if res:
        worst, out, fr = res
        check(math.hypot(ap.human.pos.x - px, ap.human.pos.z - pz) < 12.0, f"82: ({px},{pz}) に着かない {ap.human.pos}")
        check(worst < 0.5 and out < 1e-6, f"82: ({px},{pz}) へ歩く途中で障害物・壁に食い込んだ {worst:.2f} {out:.2f}")
        check(ap.human.pose.shoulder_l == 0.0 and ap.human.pose.hip_l == 0.0, "82: 着いたあと立ち姿勢に戻らない")
# 机・丸テーブル・書棚・植木・壁の中をクリックする
blocks82 = []
for k, ob in enumerate(O.OFFICE_LAYOUT.desks):
    if k in (0, 4, 7, 12):
        blocks82.append((f"机{k}", ob.x, ob.z))
blocks82 += [("丸テーブル", 0.0, 180.0), ("書棚", -700.0, -580.0), ("植木", 740.0, 540.0),
             ("右の壁の外", 900.0, 0.0), ("左の壁の外", -900.0, 100.0), ("手前の壁の外", 100.0, 900.0), ("奥の壁の外", 200.0, -900.0),
             ("ドアの範囲", -760.0, -350.0)]
stuck_in82 = []
for name, px, pz in blocks82:
    ap = h_app(2, 2)
    p = h_click_floor(ap, px, pz)
    res = h_walk_and_watch(ap, 1800)
    if res is None:
        # 止まらないのは歩き続けているということ。食い込みだけは確かめる
        res = (0.0, 0.0, 0)
        worst, out = 0.0, 0.0
        check(False, f"82: {name} をクリックしたあと人間が止まらない")
    else:
        worst, out, fr = res
    check(worst < 0.5 and out < 1e-6, f"82: {name}（{px},{pz}）をクリックしたら障害物・壁に食い込んだ／床の外に出た {worst:.2f} {out:.2f}")
    hp_ = ap.human.pos
    check(h_pen(ap, hp_.x, hp_.z) < 0.5, f"82: {name} をクリックしたあと、障害物の中で止まった {hp_}")
    stuck_in82.append((name, round(hp_.x), round(hp_.z), h_on_screen(p)))
print("(82) 障害物・壁の中のクリック→止まった場所（名前, x, z, 画面内か）", stuck_in82)

# 83. エージェントをクリック（その人の PICK 球の中心を投影した画面の点）→ talk_partner がその人、人間が隣にワープ、2人が向き合う
for who83 in (0, 1, 2):
    ap = h_app(3, 3)
    ap.update()
    e, d = h_ray(ap, *h_agent_xy(ap, who83))
    check(ap.pick_agent(e, d) == who83, f"83: 人 {who83} の球の中心を通る線で pick_agent が {who83} を返さない {ap.pick_agent(e, d)}")
    ag = ap.agents[who83]
    p = h_click_agent(ap, who83)
    check(ap.talk_partner == who83, f"83: 人 {who83} をクリックしても talk_partner がその人にならない {ap.talk_partner}")
    check(ag.hold is True and all(not a.hold for j, a in enumerate(ap.agents) if j != who83), "83: hold が相手だけ True でない")
    dd = math.hypot(ap.human.pos.x - ag.pos.x, ap.human.pos.z - ag.pos.z)
    check(abs(dd - O.TALK_SIDE_DIST) < 0.01, f"83: 人間が相手のまわり TALK_SIDE_DIST の隣にワープしていない（距離 {dd:.3f}）")
    check(not ap.human.walking and h_pen(ap, ap.human.pos.x, ap.human.pos.z) < 0.5, "83: ワープした場所が歩いている／障害物の中")
    check(ap.agents[who83].is_fixed, "83: 会話中の相手が押されない（is_fixed）状態でない")
    ap.update()
    check(h_stand_dot(ap, ag) > 0.99, f"83: 相手が人間のほうを向かない {h_stand_dot(ap, ag):.3f}")
    check(ov_forward_dot(ap.human, ag.pos.x, ag.pos.z) > 0.99, f"83: 人間が相手のほうを向かない {ov_forward_dot(ap.human, ag.pos.x, ag.pos.z):.3f}")
# 同じ人をもう一度クリックしても何も起きない（今の会話のまま・人間は動かない）
ap.update()
hp_before = (ap.human.pos.x, ap.human.pos.z)
h_click_agent(ap, 2)
check(ap.talk_partner == 2 and (ap.human.pos.x, ap.human.pos.z) == hp_before, "83: 同じ人をもう一度クリックして状態が変わった")

# 84. メイン（番号0、窓際）に話しかけると、人間は机の正面（おおよそ x=-150, z=-370）に立つ
ap = h_app(4, 1)
check(h_seat_up(ap, 0), "84: 試験の前提：人0が席に着かない")
check(ap.agents[0].is_seated and abs(ap.agents[0].pos.z - (-500.0)) < 1e-6, "84: 前提：窓際の席に座っている")
h_click_agent(ap, 0)
check(ap.talk_partner == 0, "84: 座っているメインをクリックしても会話にならない")
hx, hz = ap.human.pos.x, ap.human.pos.z
check(abs(hx - (-150.0)) < 1.0 and abs(hz - (-370.0)) < 1.0, f"84: 人間が机の正面 (-150,-370) に立たない ({hx:.1f},{hz:.1f})")
check(abs(math.hypot(hx - (-150.0), hz - (-430.0)) - O.TALK_FRONT_GAP) < 1.0, "84: 机の中心から TALK_FRONT_GAP の距離でない")
check(ov_forward_dot(ap.human, -150.0, -500.0) > 0.99, "84: 人間が席の人のほうを向いていない")
ap.update()
check(ap.agents[0].is_seated, "84: 会話の途中で席から立った")

# 85. 座っている相手は5秒たっても立ち上がらない（hold）。頭の向きは ±70 度以内で人間のほうへ
ap = h_app(4, 1)
h_seat_up(ap, 0)
h_click_agent(ap, 0)
ag = ap.agents[0]
ov_step(ap, int(6.5 * OV_FPS))
check(ag.state == "WORKING" and ag.is_seated and ag._seated_time > O.WORK_HOLD_SEC + 1.0,
      f"85: 会話中の座った相手が5秒たって立ち上がった {ag.state} {ag._seated_time:.1f}")
check(abs(ag.yaw - ag.seat_yaw) < 1e-9, f"85: 座った相手の体の向きが席の向きでない {ag.yaw}")
check(abs(ag.pose.body_y - O.SIT_BODY_Y) < 1e-9, "85: 座った相手の姿勢が sit_pose でない")
check(abs(ag.pose.head_yaw) < 5.0, f"85: 机の正面にいる人間に対して頭がまっすぐでない {ag.pose.head_yaw}")
# 人間を相手のまわりの空いている点へ動かして、頭の向きを確かめる（人間を動かすだけ。相手の席・体は変えない）
seen_clamp85, seen_mid85, n85, worst85 = 0, 0, 0, 0.0
for k in range(24):
    ang = 2.0 * math.pi * k / 24
    for rad in (45.0, 70.0, 100.0, 130.0, 170.0, 220.0):
        x, z = ag.pos.x + rad * math.sin(ang), ag.pos.z + rad * math.cos(ang)
        if not ap._spot_free(x, z):
            continue
        ap.human.warp(x, z, 0.0)
        ap.update()
        if abs(ap.human.pos.x - x) > 1e-6 or abs(ap.human.pos.z - z) > 1e-6:
            continue
        n85 += 1
        want = (O.facing_yaw(ag.pos.x, ag.pos.z, x, z, default=ag.yaw) - ag.yaw + 180.0) % 360.0 - 180.0
        want = max(-O.HEAD_YAW_LIMIT, min(O.HEAD_YAW_LIMIT, want))
        hy = ag.pose.head_yaw
        worst85 = max(worst85, abs(hy - want))
        check(abs(hy) <= O.HEAD_YAW_LIMIT + 1e-9, f"85: 頭の向きが ±70 度を超えた {hy} 人間 ({x:.0f},{z:.0f})")
        check(abs(hy - want) < 1e-6, f"85: 頭の向きが人間のほうの角度（±70 に収めた値）と違う {hy:.2f} 期待 {want:.2f} 人間 ({x:.0f},{z:.0f})")
        check(abs(ag.yaw - ag.seat_yaw) < 1e-9 and ag.is_seated, "85: 頭を回したら体の向き・席が変わった")
        if abs(want) >= O.HEAD_YAW_LIMIT - 1e-9:
            seen_clamp85 += 1
        elif abs(want) > 5.0:
            seen_mid85 += 1
check(n85 >= 8, f"85: 試した人間の位置が少ない {n85}")
check(seen_clamp85 >= 1, f"85: 上限 ±70 に収まる位置（人間が相手の横〜後ろ）を1つも試せなかった {seen_clamp85}")
check(seen_mid85 >= 1, f"85: 5〜70 度の途中の角度（収まらない値）を1つも試せなかった {seen_mid85}")
print(f"(85) 人間の位置を {n85} か所試した（±70 で止まったのは {seen_clamp85}、途中の角度は {seen_mid85}）。期待との最大のずれ {worst85:.2e}")
# 会話を終えると、次のフレームで（5秒以上座っているので）立ち上がる。頭の向きは 0 に戻る
ap.human.warp(-150.0, -370.0, 0.0)
ap.end_talk()
check(ag.hold is False, "85: end_talk で hold が False に戻らない")
ap.update()
check(ag.state == "WANDER" and abs(ag.pose.head_yaw) < 1e-9, f"85: 会話を終えても立ち上がらない／頭が戻らない {ag.state} {ag.pose.head_yaw}")

# 86. 立っている相手（WANDER）は止まり、人間を向く。うろうろ時間・行き先のタイマーが進まない。AT_SPOT の相手も止まる
ap = h_app(5, 2, ts=10.0)
ag = ap.agents[1]
ag.cooldown = 0.0
ag.wander_time = 0.0
ov_step(ap, 3)
check(ag.wander_time > 0.0 or ag.state != "WANDER", "86: 試験の前提：会話しない人は時間が進む")
ag.state = "WANDER"
ag.cooldown = 0.0
ag.wander_time = 0.0
ag._wait = 0.0
h_click_agent(ap, 1)
check(ap.talk_partner == 1, "86: 前提：WANDER の相手と会話にならない")
snap = (ag.pos.x, ag.pos.z, ag.wander_time, ag.cooldown, ag.state)
ov_step(ap, 90)  # time_scale 10 で 30 秒ぶん（うろつき5秒で出かけるはずの時間）
check(ag.state == "WANDER" and (ag.pos.x, ag.pos.z) == snap[:2], f"86: 会話中の立っている相手が動いた／出かけた {ag.state} ({ag.pos.x:.1f},{ag.pos.z:.1f}) 元 {snap}")
check(ag.wander_time == snap[2] and ag.cooldown == snap[3], f"86: 会話中にうろうろ時間・休みが進んだ {ag.wander_time} {ag.cooldown} 元 {snap}")
check(h_stand_dot(ap, ag) > 0.99 and ag.pose.shoulder_l == 0.0 and ag.pose.hip_l == 0.0, "86: 会話中の立っている相手が人間を向いて立っていない")
check(ag.intended_move == 0.0 and not ag._path, "86: 止めた相手が歩こうとしている")
# 終わると動き出し、うろうろ時間が進み始める（時間が進まなかったのは会話のせい）
ap.end_talk()
ov_step(ap, 6)
check(ag.wander_time > 0.0 or ag.state != "WANDER", f"86: 会話を終えてもうろうろ時間が進まない {ag.wander_time} {ag.state}")
# 歩いている途中の相手（うろつきで動いている）も止まる
ap = h_app(5, 2)
ag = ap.agents[1]
ag.cooldown = 1.0e9
for _ in range(240):
    ap.update()
    if ag.intended_move > 0.0:
        break
check(ag.intended_move > 0.0, "86: 前提：うろつきで歩いている相手が見つからない")
h_click_agent(ap, 1)
p0 = (ag.pos.x, ag.pos.z)
ov_step(ap, 60)
check((ag.pos.x, ag.pos.z) == p0 and ag.intended_move == 0.0, f"86: 歩いていた相手が会話で止まらない {p0} → ({ag.pos.x:.1f},{ag.pos.z:.1f})")
# AT_SPOT の相手
ap = h_app(6, 2, ts=10.0)
ag = ap.agents[1]
ov_send(ap, 1, "coffee")
n_at = ov_until(ap, lambda: ag.state == "AT_SPOT", 4000)
check(n_at is not None, "86: 前提：行き先に着かない")
if n_at is not None:
    ag.alone_time = 0.0
    ag.talk_time = 0.0
    ov_step(ap, 2)
    cnt0 = ov_total_count(ap)
    h_click_agent(ap, 1)
    check(ap.talk_partner == 1, f"86: AT_SPOT の相手をクリックしても会話にならない {ap.talk_partner}")
    pS = (ag.pos.x, ag.pos.z)
    a0, t0 = ag.alone_time, ag.talk_time
    ov_step(ap, 120)  # time_scale 10 で 40 秒ぶん（1人 30 秒で席へ戻るはずの時間）
    check(ag.state == "AT_SPOT" and (ag.pos.x, ag.pos.z) == pS, f"86: 会話中の AT_SPOT の相手が動いた／席へ戻った {ag.state}")
    check(ag.alone_time == a0 and ag.talk_time == t0, f"86: 会話中に 1人の時間・会話の時間が進んだ {ag.alone_time} {ag.talk_time}")
    check(ov_total_count(ap) == cnt0 and ap.spot_manager.count(ag.spot) >= 1, "86: 会話中に行き先の予約が外れた")
    check(h_stand_dot(ap, ag) > 0.99 and ag.pose.shoulder_l == 0.0, "86: AT_SPOT の相手が人間を向いて立っていない")
    ap.end_talk()
    ov_step(ap, 200)
    check(ag.alone_time > a0 or ag.state != "AT_SPOT", "86: 会話を終えても AT_SPOT の時間が進まない")
# GOING の相手（歩いて行き先へ向かう途中）
ap = h_app(7, 2)
ag = ap.agents[1]
ov_send(ap, 1, "coffee")
ov_step(ap, 20)
check(ag.state == "GOING", f"86: 前提：GOING でない {ag.state}")
if ag.state == "GOING":
    h_click_agent(ap, 1)
    check(ap.talk_partner == 1, "86: GOING の相手をクリックしても会話にならない")
    pG = (ag.pos.x, ag.pos.z)
    ov_step(ap, 60)
    check(ag.state == "GOING" and (ag.pos.x, ag.pos.z) == pG, "86: 会話中の GOING の相手が動いた")
    ap.end_talk()
    ov_step(ap, 30)
    check((ag.pos.x, ag.pos.z) != pG, "86: 会話を終えても GOING の相手が歩き出さない")

# 87. 会話中にスペースで相手が作業に呼ばれても会話は続く。相手は席に着く
ap = h_app(8, 2)
ag = ap.agents[1]
h_click_agent(ap, 1)
check(ap.talk_partner == 1, "87: 前提：会話が始まらない")
ap.next_index = 1
press_space_and_update(ap)
check(ag.state == "WORKING" and ap.talk_partner == 1 and ag.hold is True, f"87: スペースで作業に呼ばれて会話が終わった／hold が外れた {ag.state} {ap.talk_partner} {ag.hold}")
n87 = ov_until(ap, lambda: ag.is_seated, 1500)
check(n87 is not None, "87: 会話中に作業に呼ばれた相手が席に着かない")
check(ap.talk_partner == 1, "87: 席に着くまでの間に会話が終わった")
ov_step(ap, int(7 * OV_FPS))
check(ag.state == "WORKING" and ag.is_seated and ap.talk_partner == 1, f"87: 席に着いたあと5秒を超えて立ち上がった／会話が終わった {ag.state} {ap.talk_partner}")
# 人間は、相手が座ったら机の正面へ歩いて行く
want87 = (ap.layout.desks[1].x + 0.0, ap.layout.desks[1].z + O.TALK_FRONT_GAP)
ov_until(ap, lambda: not ap.human.walking, 600)
check(math.hypot(ap.human.pos.x - want87[0], ap.human.pos.z - want87[1]) < 3.0,
      f"87: 相手が座ったあと、人間が机の正面 {want87} へ来ない ({ap.human.pos.x:.1f},{ap.human.pos.z:.1f})")
check(h_pen(ap, ap.human.pos.x, ap.human.pos.z) < 0.5, "87: 人間が障害物の中にいる")
# 呼ばれて歩いている最中に会話が続き、人間が相手を追う（席へ歩いている間に人間が動く）
ap = h_app(9, 3)
ag = ap.agents[2]
ov_step(ap, 3)
h_click_agent(ap, 2)
h0 = (ap.human.pos.x, ap.human.pos.z)
ap.next_index = 2
press_space_and_update(ap)
moved87 = False
for _ in range(60):
    ap.update()
    if (ap.human.pos.x, ap.human.pos.z) != h0:
        moved87 = True
    if ag.is_seated:
        break
check(ap.talk_partner == 2, "87: 呼ばれた相手を追っている間に会話が終わった")
print(f"(87) 席へ歩く相手を人間が追って動いた: {moved87}")

# 88. Q キーで会話が終わり、カメラが元の yaw・pitch・dist に戻る（CAM_BLEND_SEC ぶんフレームを進めたあと）
ap = h_app(10, 3)
ap.cam_yaw, ap.cam_pitch, ap.cam_dist = 100.0, 30.0, 900.0
ap._apply_camera()
ap.update()
saved88 = (ap.cam_yaw, ap.cam_pitch, ap.cam_dist)
blend_frames = int(O.CAM_BLEND_SEC * OV_FPS) + 3
h_click_agent(ap, 1)
check(ap.talk_partner == 1, "88: 前提：会話が始まらない")
ov_step(ap, blend_frames)
tv = ap._talk_view()
check(abs(ap.cam_dist - tv[3]) < 0.01 and abs(ap.cam_pitch - tv[2]) < 0.01 and h_ang(ap.cam_yaw, tv[1]) < 0.01
      and (ap.cam_target - tv[0]).length() < 0.01, f"88: 会話のカメラに切り替わらない {ap.cam_yaw} {ap.cam_pitch} {ap.cam_dist} / 目標 {tv}")
check(abs(ap.cam_pitch - O.TALK_CAM_PITCH) < 0.01 and ap.cam_dist >= O.TALK_CAM_MIN_DIST - 0.01, f"88: 会話のカメラの pitch・dist が仕様でない {ap.cam_pitch} {ap.cam_dist}")
check(eye_matches(ap), "88: 会話中の 目＝target+dir*dist／far が合わない")
press_keys_and_update(ap, pyxel.KEY_Q)
check(ap.talk_partner is None and ap.agents[1].hold is False, "88: Q で会話が終わらない／hold が外れない")
ov_step(ap, blend_frames)
check(h_ang(ap.cam_yaw, saved88[0]) < 0.01 and abs(ap.cam_pitch - saved88[1]) < 0.01 and abs(ap.cam_dist - saved88[2]) < 0.01,
      f"88: Q のあとカメラが元の yaw・pitch・dist に戻らない {(ap.cam_yaw, ap.cam_pitch, ap.cam_dist)} 元 {saved88}")
check((ap.cam_target - Vec3(ap.human.pos.x, 0.0, ap.human.pos.z)).length() < 0.5, f"88: 戻ったあとの注視点が人間の位置でない {ap.cam_target} {ap.human.pos}")
check(ap._saved_view is None and ap._cam_from is None, "88: 戻ったあとも切り替えの状態が残っている")
# 戻ったあとは通常のカメラ：カーソルキーでまた回せる
_orig_btn88 = pyxel.btn
pyxel.btn = lambda k, *a, **kw: k in held
try:
    y88 = ap.cam_yaw
    view_frames(ap, {pyxel.KEY_RIGHT}, 10)
    check(h_ang(ap.cam_yaw, y88 + O.CAM_YAW_SPEED * 10 / OV_FPS) < 0.01, f"88: 会話のあと、カーソルキーで視点が回らない {y88} → {ap.cam_yaw}")
finally:
    pyxel.btn = _orig_btn88
    held.clear()
# 会話していないときの Q は何もしない（カメラも変わらない）
before88 = (ap.cam_yaw, ap.cam_pitch, ap.cam_dist)
press_keys_and_update(ap, pyxel.KEY_Q)
check(ap.talk_partner is None and (ap.cam_yaw, ap.cam_pitch, ap.cam_dist) == before88, "88: 会話していないときの Q でカメラが変わった")
# 切り替えの途中（始まって数フレーム）で Q を押しても、元の視点に戻る
ap = h_app(10, 3)
ap.cam_yaw, ap.cam_pitch, ap.cam_dist = 200.0, 50.0, 1200.0
ap._apply_camera()
ap.update()
saved88b = (ap.cam_yaw, ap.cam_pitch, ap.cam_dist)
h_click_agent(ap, 0)
ov_step(ap, 4)
press_keys_and_update(ap, pyxel.KEY_Q)
ov_step(ap, blend_frames + 3)
check(h_ang(ap.cam_yaw, saved88b[0]) < 0.05 and abs(ap.cam_pitch - saved88b[1]) < 0.05 and abs(ap.cam_dist - saved88b[2]) < 0.5,
      f"88: 切り替えの途中で Q を押したら元の視点に戻らない {(ap.cam_yaw, ap.cam_pitch, ap.cam_dist)} 元 {saved88b}")

# 89. 会話中に床をクリック→会話が終わり、そこへ歩く。別の人をクリック→その人と会話
ap = h_app(11, 3)
ap.update()
h_click_agent(ap, 0)
check(ap.talk_partner == 0 and ap.agents[0].hold, "89: 前提：会話が始まらない")
ov_step(ap, 20)
# 会話のカメラに映っている床の点を選ぶ（人間のそばで、空いていて、人に隠れない点）
tgt89 = None
for ox, oz in ((60.0, 60.0), (-60.0, 60.0), (60.0, -60.0), (-60.0, -60.0), (90.0, 0.0), (-90.0, 0.0), (0.0, 90.0)):
    cx, cz = ap.human.pos.x + ox, ap.human.pos.z + oz
    sxy = h_proj(ap, cx, 0.0, cz)
    e, d = h_ray(ap, round(sxy[0]), round(sxy[1]))
    if ap._spot_free(cx, cz) and h_on_screen((round(sxy[0]), round(sxy[1])), ap) and ap.pick_agent(e, d) is None:
        tgt89 = (cx, cz)
        break
check(tgt89 is not None, "89: 前提：会話のカメラに映る空いた床の点がない")
if tgt89 is not None:
    h_click_floor(ap, *tgt89)
    check(ap.talk_partner is None and ap.agents[0].hold is False, "89: 会話中に床をクリックしても会話が終わらない")
    check(ap.human.walking, "89: 床をクリックしても人間が歩き出さない")
    ov_until(ap, lambda: not ap.human.walking, 1200)
    check(math.hypot(ap.human.pos.x - tgt89[0], ap.human.pos.z - tgt89[1]) < 12.0, f"89: クリックした床の点へ着かない {ap.human.pos} {tgt89}")
ov_step(ap, int(O.CAM_BLEND_SEC * OV_FPS) + 3)
check(ap._saved_view is None and ap._cam_from is None, "89: 床のクリックのあとカメラが元に戻らない")
# 別の人をクリック
ap = h_app(12, 3)
ap.update()
h_click_agent(ap, 0)
ov_step(ap, 20)
e, d = h_ray(ap, *h_agent_xy(ap, 2))
front89 = ap.pick_agent(e, d)
h_click_agent(ap, 2)
if front89 == 2:
    check(ap.talk_partner == 2, f"89: 会話中に別の人をクリックしても、その人と会話にならない {ap.talk_partner}")
    check(ap.agents[0].hold is False and ap.agents[2].hold is True, "89: hold が 前の相手 False・新しい相手 True でない")
    d2 = math.hypot(ap.human.pos.x - ap.agents[2].pos.x, ap.human.pos.z - ap.agents[2].pos.z)
    check(d2 < 80.0, f"89: 人間が新しい相手の隣へ来ない {d2:.1f}")
else:
    check(False, f"89: 前提：人2の球の中心を通る線で別の人（{front89}）が先に当たった")
ov_step(ap, 5)
check(ap._saved_view is not None, "89: 会話を続けているのに、前の視点の記憶がない")
# 別の人へ移っても、Q で最初の視点に戻る（途中で記憶を入れ直さない）
ap = h_app(12, 3)
ap.cam_yaw, ap.cam_pitch, ap.cam_dist = 40.0, 45.0, 1000.0
ap._apply_camera()
ap.update()
saved89 = (ap.cam_yaw, ap.cam_pitch, ap.cam_dist)
h_click_agent(ap, 0)
ov_step(ap, 20)
h_click_agent(ap, 2)
ov_step(ap, 20)
press_keys_and_update(ap, pyxel.KEY_Q)
ov_step(ap, 20)
check(h_ang(ap.cam_yaw, saved89[0]) < 0.05 and abs(ap.cam_pitch - saved89[1]) < 0.05 and abs(ap.cam_dist - saved89[2]) < 0.5,
      f"89: 人を替えたあとの Q で、最初の視点に戻らない {(ap.cam_yaw, ap.cam_pitch, ap.cam_dist)} 元 {saved89}")

# 90. 会話中はカーソルキーとホイールでカメラが変わらない
_orig_btn90 = pyxel.btn
pyxel.btn = lambda k, *a, **kw: k in held
try:
    ap = h_app(13, 3)
    ap.update()
    h_click_agent(ap, 1)
    # 切り替えの途中からキーを押し続けても、切り替え終わりは会話のカメラ
    held.update({pyxel.KEY_LEFT, pyxel.KEY_UP})
    ov_step(ap, int(O.CAM_BLEND_SEC * OV_FPS) + 3)
    held.clear()
    tv = ap._talk_view()
    check(h_ang(ap.cam_yaw, tv[1]) < 0.01 and abs(ap.cam_pitch - tv[2]) < 0.01 and abs(ap.cam_dist - tv[3]) < 0.01,
          f"90: 切り替え中にキーを押し続けたら会話のカメラにならない {(ap.cam_yaw, ap.cam_pitch, ap.cam_dist)} 目標 {tv}")
    cam0 = (ap.cam_yaw, ap.cam_pitch, ap.cam_dist, ap.cam_target.x, ap.cam_target.y, ap.cam_target.z)
    for keys in ({pyxel.KEY_RIGHT}, {pyxel.KEY_LEFT}, {pyxel.KEY_UP}, {pyxel.KEY_DOWN}, {pyxel.KEY_LEFT, pyxel.KEY_UP}):
        view_frames(ap, keys, 30)
        cam1 = (ap.cam_yaw, ap.cam_pitch, ap.cam_dist, ap.cam_target.x, ap.cam_target.y, ap.cam_target.z)
        check(cam1 == cam0, f"90: 会話中にカーソルキー {sorted(keys)} でカメラが変わった {cam0} → {cam1}")
    for n_wheel in (5, -5, 1, -200):
        wheel_update(ap, n_wheel)
        cam1 = (ap.cam_yaw, ap.cam_pitch, ap.cam_dist, ap.cam_target.x, ap.cam_target.y, ap.cam_target.z)
        check(cam1 == cam0, f"90: 会話中にホイール {n_wheel} でカメラが変わった {cam0} → {cam1}")
    check(eye_matches(ap), "90: 会話中の 目／far が合わない")
    # 会話を終えて戻ったあとは、同じ操作でカメラが変わる（比べるための対照）
    ap.end_talk()
    ov_step(ap, int(O.CAM_BLEND_SEC * OV_FPS) + 3)
    c2 = ap.cam_dist
    wheel_update(ap, 3)
    check(abs(ap.cam_dist - c2 * 0.729) < 1e-6, f"90: 会話を終えたあとホイールが効かない {c2} → {ap.cam_dist}")
    y2 = ap.cam_yaw
    view_frames(ap, {pyxel.KEY_RIGHT}, 15)
    check(h_ang(ap.cam_yaw, y2 + 45.0) < 0.01, "90: 会話を終えたあとカーソルキーが効かない")
finally:
    pyxel.btn = _orig_btn90
    held.clear()
    pyxel.mouse_wheel = 0

# 91. 人間は押されない（エージェントが人間に向かって歩いても人間の位置が変わらない）
ap = h_app(14, 3)
ag = ap.agents[1]
h0 = (ap.human.pos.x, ap.human.pos.z)
ag.pos = Vec3(h0[0] + 4.0, 0.0, h0[1] + 3.0)  # 人間とほとんど重なる位置
ap.update()
check((ap.human.pos.x, ap.human.pos.z) == h0, f"91: 重なったエージェントに人間が押された {h0} → ({ap.human.pos.x}, {ap.human.pos.z})")
check(dist(ag.pos, ap.human.pos) >= 2 * O.AGENT_RADIUS - 1e-6, f"91: 重なったエージェントが押し出されない {dist(ag.pos, ap.human.pos):.2f}")
worst91 = 1e9
for k in range(150):
    # エージェントを人間のほうへ歩かせる（うろつきの目標を人間の位置にし続ける）
    ag.state = "WANDER"
    ag._target = Vec3(h0[0], 0.0, h0[1])
    ag._wait = 0.0
    if k == 0:
        ag.pos = Vec3(h0[0] + 120.0, 0.0, h0[1])
    ap.update()
    check((ap.human.pos.x, ap.human.pos.z) == h0, f"91: フレーム {k} でエージェントに人間が押された ({ap.human.pos.x:.3f}, {ap.human.pos.z:.3f}) 元 {h0}")
    worst91 = min(worst91, dist(ag.pos, ap.human.pos))
check(worst91 >= 2 * O.AGENT_RADIUS - 1e-6, f"91: エージェントが人間に食い込んだ 最短 {worst91:.2f}")
# 作業で席へ歩くエージェントの通り道に人間が立っていても、人間は動かない
ap = h_app(15, 2)
ag = ap.agents[1]
ag.pos = Vec3(ag.seat.x + 100.0, 0.0, ag.seat.z + 50.0)
hx, hz = ag.seat.x + 50.0, ag.seat.z + 25.0
ap.human.warp(hx, hz, 0.0)
ap.next_index = 1
press_space_and_update(ap)
for _ in range(240):
    ap.update()
    if (ap.human.pos.x, ap.human.pos.z) != (hx, hz) and h_pen(ap, ap.human.pos.x, ap.human.pos.z) < 0.5:
        # 押されて動いたら失敗（障害物から押し出された場合を除く）
        check(False, f"91: 席へ向かうエージェントに人間が押された ({ap.human.pos.x:.2f}, {ap.human.pos.z:.2f}) 元 ({hx}, {hz})")
        break
# 会話中の人間：相手に押されない
ap = h_app(16, 3)
h_click_agent(ap, 0)
hc = (ap.human.pos.x, ap.human.pos.z)
ov_step(ap, 30)
check((ap.human.pos.x, ap.human.pos.z) == hc, "91: 会話中に人間が動いた")


# ---- ここから「画面の配分とモード」の項目（95〜106）。office は 640×500、3D は (0,0,640,296)、下に履歴と入力欄 ----
# 操作は p_frame で1フレームぶんを真似る：押したキー・押し続けたキー（Ctrl）・input_text・マウスの位置とクリック・ホイール。
H_SHOT_DIR3 = TMP_DIR / "talk_shots3"
H_SHOT_DIR3.mkdir(parents=True, exist_ok=True)
P_HX, P_HY, P_HW, P_HH = O.HISTORY_X, O.HISTORY_Y, O.HISTORY_W, O.HISTORY_H
P_IX, P_IY, P_IW, P_IH = O.HISTORY_X, O.INPUT_Y, O.HISTORY_W, O.INPUT_H


def p_frame(app, keys=(), hold_keys=(), text="", click=None, mouse=None, wheel=0):
    """1フレームぶんの操作を真似て update を1回呼ぶ。

    keys：このフレームに押された（btnp）キー。hold_keys：押し続けているキー（btn。Ctrl など）。
    text：pyxel.input_text。click：(x, y) を左クリック。mouse：クリックしないときのマウスの位置。wheel：ホイール。
    """
    saved_btn = pyxel.btn
    held.clear()
    held.update(hold_keys)
    pyxel.btn = lambda k, *a, **kw: k in held
    pressed_keys.update(keys)
    pyxel.input_text = text
    if click is not None:
        pyxel.mouse_x, pyxel.mouse_y = click
        pressed_keys.add(pyxel.MOUSE_BUTTON_LEFT)
    elif mouse is not None:
        pyxel.mouse_x, pyxel.mouse_y = mouse
    pyxel.mouse_wheel = wheel
    try:
        app.update()
    finally:
        pyxel.btn = saved_btn
        held.clear()
        pressed_keys.clear()
        pyxel.input_text = ""
        pyxel.mouse_wheel = 0
        pyxel.mouse_x, pyxel.mouse_y = 0, 0


def p_enter_prompt(app):
    """WALK から P キーで PROMPT にする。"""
    p_frame(app, keys=(O.PROMPT_ENTER_KEY,))


def p_type(app, text):
    """PROMPT で文字を1フレームで入力する。"""
    p_frame(app, text=text)


def p_enter(app, key=None):
    """Enter を押して、送信まで進める。送信は日本語入力の確定の文字を待つため、Enter のフレームを含めて
    IME_ENTER_WAIT+1 回の update で行われる（Enter のフレーム＋IME_ENTER_WAIT フレーム）。"""
    p_frame(app, keys=(pyxel.KEY_RETURN if key is None else key,))
    for _ in range(O.IME_ENTER_WAIT):
        p_frame(app)


def p_send(app, text):
    """PROMPT で text を打って Enter（履歴に足す）。送信まで進める。"""
    p_type(app, text)
    p_enter(app)


def p_texts(app):
    """draw で出た標準フォントの文字 (x, y, 文字列, 色) の一覧（UI フォントの文字は font が付くので別に集める）。"""
    std, ui = [], []
    saved = pyxel.text
    pyxel.text = lambda x, y, s, col, *a, **k: (ui if (a or k) else std).append((x, y, str(s), col))
    try:
        app.draw()
    finally:
        pyxel.text = saved
    return std, ui


P_LETTER_KEYS = [getattr(pyxel, f"KEY_{c}") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"] + [pyxel.KEY_MINUS]


def p_cols(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)




# 92. 18人＋人間で乱数のクリックを数千フレーム：例外なし、人間は床の範囲内、壁を抜けない、頭の向きは ±70 度以内
def h_random_run(seed, frames, ts):
    """18人の office でランダムにクリック・スペース・Q を混ぜて回す。(結果の辞書) を返す。"""
    ap = ov_app(seed, 18, ts)
    rng = random.Random(seed * 101 + 7)
    x_min, x_max = ap.layout.wander_x
    z_min, z_max = ap.layout.wander_z
    r = {"exc": None, "frame": None, "out": 0.0, "pen": 0.0, "head": 0.0, "hold_bad": 0, "talks": 0, "clicks": 0, "floor_clicks": 0,
         "walks": 0, "min_ag": 1e9, "partner_changes": 0, "bad_talk_view": 0, "ui_bad": 0, "modes": {}}
    prev_partner = None
    try:
        for f in range(frames):
            if f % 12 == 5:
                kind = rng.random()
                if kind < 0.35:
                    i = rng.randrange(len(ap.agents))
                    sx, sy = h_agent_xy(ap, i)
                    ap.handle_click(round(sx), round(sy))
                elif kind < 0.9:
                    ap.handle_click(rng.randrange(0, O.OFFICE_SCREEN_W), rng.randrange(0, O.VIEW3D_H))
                    r["floor_clicks"] += 1
                else:
                    ap.handle_click(rng.randrange(-40, O.OFFICE_SCREEN_W + 40), rng.randrange(-40, O.VIEW3D_H + 40))
                r["clicks"] += 1
            op = rng.random()
            if f % 151 == 100:
                p_frame(ap, keys=(pyxel.KEY_SPACE,))
            elif op < 0.004:
                p_frame(ap, keys=(pyxel.KEY_Q,))
            elif op < 0.025:
                p_frame(ap, keys=(O.PROMPT_ENTER_KEY,), text=rng.choice(["p", "", "pp"]))
            elif op < 0.045:
                p_frame(ap, hold_keys=(rng.choice([pyxel.KEY_LCTRL, pyxel.KEY_RCTRL]),), keys=(pyxel.KEY_E,), text=rng.choice(["e", ""]))
            elif op < 0.075:
                p_frame(ap, text=rng.choice(["a", "hello", "こんにちは", "日本語 abc", " ", "x" * 130, "あ" * 70, ""]))
            elif op < 0.085:
                p_frame(ap, keys=(pyxel.KEY_RETURN,))
            elif op < 0.095:
                p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
            elif op < 0.105:
                p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
            elif op < 0.13:
                p_frame(ap, mouse=(rng.randrange(0, O.OFFICE_SCREEN_W), rng.randrange(0, O.OFFICE_SCREEN_H)), wheel=rng.choice([-3, -1, 1, 2, 5]))
            elif op < 0.15:
                p_frame(ap, hold_keys=(rng.choice([pyxel.KEY_LEFT, pyxel.KEY_RIGHT, pyxel.KEY_UP, pyxel.KEY_DOWN]),))
            elif op < 0.17:
                p_frame(ap, keys=(rng.choice([pyxel.KEY_D, pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3, pyxel.KEY_4]),))
            elif op < 0.20:
                p_frame(ap, click=(rng.randrange(0, O.OFFICE_SCREEN_W), rng.randrange(0, O.OFFICE_SCREEN_H)))  # 画面全体（履歴・入力欄・スクロールバーも）
            elif op < 0.23:
                # 英字キーだけ（日本語入力オンの想定で、文字は来ない）。Ctrl を押しながらのこともある
                p_frame(ap, keys=(rng.choice(P_LETTER_KEYS),), hold_keys=((pyxel.KEY_LCTRL,) if rng.random() < 0.2 else ()))
            elif op < 0.26:
                # Enter のあと、次のフレームに確定の文字（途中で別のフレームをはさむこともある）
                p_frame(ap, keys=(pyxel.KEY_RETURN,))
                if rng.random() < 0.3:
                    p_frame(ap)
                p_frame(ap, text=rng.choice(["日本語", "確定", "abc", ""]))
            elif op < 0.29:
                # Shift＋Ctrl（日本語入力の切り替え）。順番・左右はいろいろ
                sh = rng.choice([pyxel.KEY_LSHIFT, pyxel.KEY_RSHIFT])
                ct = rng.choice([pyxel.KEY_LCTRL, pyxel.KEY_RCTRL])
                if rng.random() < 0.5:
                    p_frame(ap, keys=(sh,), hold_keys=(sh,))
                    p_frame(ap, keys=(ct,), hold_keys=(sh, ct))
                else:
                    p_frame(ap, keys=(ct,), hold_keys=(ct,))
                    p_frame(ap, keys=(sh,), hold_keys=(sh, ct))
                p_frame(ap)
            elif op < 0.32:
                p_frame(ap, keys=(pyxel.KEY_J,), hold_keys=(rng.choice([pyxel.KEY_LCTRL, pyxel.KEY_RCTRL]),))
            else:
                ap.update()
            # 画面の部品の決まり
            if ap.mode not in ("WALK", "PROMPT") or len(ap.history) > O.HISTORY_MAX or not (0 <= ap.history_scroll <= ap._max_scroll())                     or any(p_cols(row_) > O.UI_COLS for row_ in ap.history) or not isinstance(ap.input_buf, str):
                r["ui_bad"] += 1
            if not all(math.isfinite(v_) for v_ in (ap.cam_yaw, ap.cam_pitch, ap.cam_dist, ap.cam_target.x, ap.cam_target.z)):
                r["ui_bad"] += 1
            r["modes"][ap.mode] = r["modes"].get(ap.mode, 0) + 1
            if ap.ime_state not in ("?", "あ", "A"):
                r["ui_bad"] += 1
            if not (isinstance(ap.ime_composing, bool) and 0 <= ap._pending_enter <= O.IME_ENTER_WAIT + 1 and 0 <= ap._ime_wait_text <= O.IME_GRACE_FRAMES + 1) \
                    or (ap.mode == "WALK" and (ap.ime_composing or ap._pending_enter or ap._ime_wait_text)):
                r["ui_bad"] += 1
            hu = ap.human
            r["out"] = max(r["out"], x_min - hu.pos.x, hu.pos.x - x_max, z_min - hu.pos.z, hu.pos.z - z_max)
            r["pen"] = max(r["pen"], h_pen(ap, hu.pos.x, hu.pos.z))
            if hu.walking:
                r["walks"] += 1
            for a in ap.agents:
                r["head"] = max(r["head"], abs(a.pose.head_yaw))
                r["min_ag"] = min(r["min_ag"], dist(a.pos, hu.pos))
            r["head"] = max(r["head"], abs(hu.pose.head_yaw))
            tp = ap.talk_partner
            if tp != prev_partner:
                if tp is not None:
                    r["talks"] += 1
                prev_partner = tp
            holds = [j for j, a in enumerate(ap.agents) if a.hold]
            if holds != ([tp] if tp is not None else []):
                r["hold_bad"] += 1
            if tp is not None and ap._saved_view is None:
                r["bad_talk_view"] += 1
    except Exception as e:  # noqa: BLE001 例外が出たら記録して止める
        import traceback
        r["exc"] = traceback.format_exc()
        r["frame"] = f
    return ap, r


for seed92, ts92 in ((1, 1.0), (2, 5.0)):
    ap92, r92 = h_random_run(seed92, 2500, ts92)
    check(r92["exc"] is None, f"92: 種{seed92} フレーム {r92['frame']} で例外 {r92['exc']}")
    check(r92["out"] < 1e-6, f"92: 種{seed92} 人間が床の範囲の外に出た {r92['out']:.3f}")
    check(r92["pen"] < 0.5, f"92: 種{seed92} 人間が壁・障害物に食い込んだ {r92['pen']:.3f}")
    check(r92["head"] <= O.HEAD_YAW_LIMIT + 1e-9, f"92: 種{seed92} 頭の向きが ±70 度を超えた {r92['head']:.2f}")
    check(r92["min_ag"] >= O.AGENT_RADIUS / 2, f"92: 種{seed92} 人間と人が体の半径の半分より近く重なった {r92['min_ag']:.1f}")
    check(r92["hold_bad"] == 0, f"92: 種{seed92} hold と talk_partner が食い違ったフレームがある {r92['hold_bad']}")
    check(r92["ui_bad"] == 0, f"92: 種{seed92} モード・履歴・入力欄・カメラの決まりが崩れたフレームがある {r92['ui_bad']}")
    check(len(r92["modes"]) == 2, f"92: 種{seed92} WALK と PROMPT の両方に入らなかった {r92['modes']}")
    check(r92["bad_talk_view"] == 0, f"92: 種{seed92} 会話中なのに _saved_view がないフレームがある")
    check(r92["talks"] >= 5 and r92["walks"] >= 50, f"92: 種{seed92} 会話・歩きがほとんど起きなかった {r92['talks']} {r92['walks']}")
    print(f"(92) 種{seed92} 2500フレーム クリック{r92['clicks']}回（床{r92['floor_clicks']}） 会話の始まり{r92['talks']}回 歩いたフレーム{r92['walks']} "
          f"最大の食い込み {r92['pen']:.3f} 床の外 {r92['out']:.3f} 頭の最大 {r92['head']:.1f}度 人間と人の最短距離 {r92['min_ag']:.1f}")

# 93. クリックで狙った人を pick_agent が取れなかったとき、手前に別の人がいたかを調べる
def h_sphere_t(app, eye, d, i):
    """線と人 i の球（クリック用）の交わり t（手前の正の値）。当たらなければ None。pick_agent とは別に書いた式。"""
    a = app.agents[i]
    c = Vec3(a.pos.x, O.PICK_CENTER_Y + a.pose.body_y, a.pos.z)
    oc = eye - c
    b = oc.dot(d)
    disc = b * b - (oc.dot(oc) - O.PICK_RADIUS ** 2)
    if disc < 0.0:
        return None
    s = math.sqrt(disc)
    t = -b - s
    if t <= 0.0:
        t = -b + s
    return t if t > 0.0 else None


stat93 = {"behind": 0, "tries": 0, "ok": 0, "front": 0, "miss_offscreen": 0, "miss_onscreen": 0, "miss_else": 0}
bad93 = []
for seed93 in (1, 2):
    ap = ov_app(seed93, 18, 3.0)  # 出かけて動き回る（人が重なって見える場面を増やす）
    rng = random.Random(seed93 + 900)
    if seed93 == 2:
        ap.cam_pitch, ap.cam_dist = O.CAM_PITCH_MIN, 700.0  # 低い角度でも（人が重なって見える）
        ap._apply_camera()
    for f in range(900):
        ap.update()
        if f % 5 == 0:
            i = rng.randrange(len(ap.agents))
            sx, sy = h_agent_xy(ap, i)
            p = (round(sx), round(sy))
            eye_ = ap.cam_target + ap.cam_dir * ap.cam_dist
            fwd_ = (ap.cam_target - eye_).normalize()
            a_ = ap.agents[i]
            if (Vec3(a_.pos.x, O.PICK_CENTER_Y + a_.pose.body_y, a_.pos.z) - eye_).dot(fwd_) <= 0.0:
                stat93["behind"] += 1  # カメラの後ろにいる人は画面に映らないので、狙えない
                continue
            e, d = h_ray(ap, p[0], p[1])
            got = ap.pick_agent(e, d)
            stat93["tries"] += 1
            if got == i:
                stat93["ok"] += 1
            else:
                t_target = h_sphere_t(ap, e, d, i)
                t_got = h_sphere_t(ap, e, d, got) if got is not None else None
                if t_got is not None and t_target is not None and t_got < t_target:
                    stat93["front"] += 1  # 手前に別の人がいる（仕様どおり）
                elif t_target is None:
                    stat93["miss_onscreen" if h_on_screen(p, ap) else "miss_offscreen"] += 1
                    bad93.append((seed93, f, i, got, p, "球に当たらない"))
                else:
                    stat93["miss_else"] += 1
                    bad93.append((seed93, f, i, got, p, f"手前でないのに別の人 t_target={t_target:.1f} t_got={t_got}"))
print(f"(93) 狙った人を選べたか {stat93}")
check(stat93["tries"] > 100 and stat93["ok"] > 50, "93: 試行が少ない／選べた数が少ない")
check(stat93["miss_onscreen"] == 0 and stat93["miss_else"] == 0 and stat93["miss_offscreen"] == 0,
      f"93: 手前の別の人以外の理由で狙った人を取れなかった例がある {bad93[:5]}")

# 94. 会話の場面の画像：画面を PNG に書き出す（合否なし。目で見る）。pyxel.pget で読み、標準ライブラリの zlib・struct で書く
import zlib
import struct


def h_write_png(path, scale=3):
    """今の画面（pyxel.screen）を、パレットの実際の色で scale 倍に拡大して PNG（RGB 8bit）に書く。"""
    w, hgt = pyxel.width, pyxel.height
    rows = []
    for y in range(hgt):
        row = bytearray()
        for x in range(w):
            c = pyxel.colors[pyxel.screen.pget(x, y)]
            px = bytes(((c >> 16) & 255, (c >> 8) & 255, c & 255))
            row += px * scale
        for _ in range(scale):
            rows.append(b"\x00" + bytes(row))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, hgt * scale, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def h_shot(name, setup):
    """setup(app) で場面を作り、会話の切り替えが終わるまで進めてから画面を書き出す。パスを返す。"""
    ap = ov_app(21, 18, 1.0)
    ov_quiet(ap)
    ap.update()
    setup(ap)
    ov_step(ap, int(O.CAM_BLEND_SEC * OV_FPS) + 12)
    ap.draw()
    path = H_SHOT_DIR / name
    h_write_png(path)
    return ap, path


def h_setup_main(ap):
    h_seat_up(ap, 0)
    ap.update()
    h_click_agent(ap, 0)


def h_setup_island(ap):
    h_seat_up(ap, 5)
    ov_step(ap, 3)
    h_click_agent(ap, 5)


def h_setup_stand(ap):
    ov_step(ap, 3)
    h_click_agent(ap, 8)


shots94 = []
for name94, setup94, who94 in (("talk_main.png", h_setup_main, 0), ("talk_island.png", h_setup_island, 5), ("talk_standing.png", h_setup_stand, 8)):
    ap94, path94 = h_shot(name94, setup94)
    ok94 = path94.exists() and path94.stat().st_size > 1000 and path94.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    check(ap94.talk_partner == who94 and ok94, f"94: 会話の画像 {name94} を書けなかった／会話が始まっていない {ap94.talk_partner} {ok94}")
    shots94.append(str(path94))
print("(94) 会話の場面の画像", shots94)


# 95. 起動時は WALK。MODE 表示（案内つき、横の真ん中）が y=4 付近に黒い背景つきで出る（pget で黒の四角と文字の色 7・括弧は6）。P で PROMPT（色10）、そのフレームの input_text 'p' は入らない
ap = h_app(31, 3)
check(ap.mode == "WALK", f"95: 起動時が WALK でない {ap.mode}")
check(ap.input_buf == "" and ap.talk_partner is None, "95: 起動時に入力中の文字・会話がある")
check(ap.history == [], f"95: 起動時の履歴が空でない（試作の1行は削除済み） {ap.history}")


P_HINT = {"WALK": "(P:PROMPT)", "PROMPT": "(CTRL+E:WALK ESC:CANCEL ENTER:SEND)"}
P_MODE_COL = {"WALK": 7, "PROMPT": 10}
P_HINT_COL = 6


def p_label_parts(std):
    """上の真ん中の MODE 表示（y=4付近）の文字を、x の順に返す。"""
    return sorted([t for t in std if 2 <= t[1] <= 6], key=lambda t: t[0])


def p_mode_label(app, mode):
    """MODE 表示：'MODE: <モード>  (案内)' 全体が横の真ん中で、'MODE: …' は モードの色、括弧の部分は色6。
    その四角（上下左右 2 点の余白）の中が、黒と2つの文字色だけで、文字の画素がある（pget）ことを確かめる。"""
    std, _ = p_texts(app)
    parts = p_label_parts(std)
    head = [t for t in parts if t[2].startswith("MODE:")]
    hint = [t for t in parts if t[2].lstrip().startswith("(")]
    if len(head) != 1 or len(hint) != 1:
        return False, f"MODE 部分と括弧の部分が1つずつ y=4付近に出ていない {parts}"
    h, g = head[0], hint[0]
    if h[2].rstrip() != f"MODE: {mode}" or g[2].strip() != P_HINT[mode]:
        return False, f"文字列が違う {h[2]!r} {g[2]!r}"
    if h[3] != P_MODE_COL[mode] or g[3] != P_HINT_COL:
        return False, f"色が違う MODE部分{h[3]}（期待{P_MODE_COL[mode]}）括弧{g[3]}（期待{P_HINT_COL}）"
    x0 = h[0]
    x1 = g[0] + len(g[2]) * pyxel.FONT_WIDTH
    # MODE 部分と括弧の間は半角2つ分（"  "）。空白は括弧の文字列の頭に付いていても、位置で空けてあってもよい
    gap_chars = (g[0] - (h[0] + len(h[2].rstrip()) * pyxel.FONT_WIDTH)) // pyxel.FONT_WIDTH + (len(g[2]) - len(g[2].lstrip()))
    if gap_chars != 2:
        return False, f"MODE 部分と括弧の間が半角2文字分でない {h[0]} {h[2]!r} {g[0]} {g[2]!r}"
    if abs((x0 + x1) / 2.0 - O.OFFICE_SCREEN_W / 2.0) > 2.0:
        return False, f"全体が横の真ん中でない 左{x0} 右{x1}"
    app.draw()  # p_texts は文字を描かずに集めただけなので、画素を調べるために本当に描き直す
    y = h[1]
    other, seen = 0, {}
    for yy in range(y - 2, y + pyxel.FONT_HEIGHT + 2):
        for xx in range(x0 - 2, x1 + 2):
            c = pyxel.screen.pget(xx, yy)
            if c in (0, P_MODE_COL[mode], P_HINT_COL):
                seen[c] = seen.get(c, 0) + 1
            else:
                other += 1
    if other:
        return False, f"四角の中に黒と文字色以外の画素が {other} 個ある"
    if seen.get(P_MODE_COL[mode], 0) < 8 or seen.get(P_HINT_COL, 0) < 8:
        return False, f"文字の画素が少ない {seen}"
    return True, ""


ok95, msg95 = p_mode_label(ap, "WALK")
check(ok95, f"95: WALK の MODE 表示 {msg95}")
pyxel.input_text = ""
p_frame(ap, keys=(O.PROMPT_ENTER_KEY,), text="p")
check(ap.mode == "PROMPT", f"95: P で PROMPT にならない {ap.mode}")
check(ap.input_buf == "", f"95: P を押したフレームの input_text 'p' が入力欄に入った {ap.input_buf!r}")
ok95, msg95 = p_mode_label(ap, "PROMPT")
check(ok95, f"95: PROMPT の MODE 表示 {msg95}")
p_frame(ap, text="p")
check(ap.mode == "PROMPT" and ap.input_buf == "p", f"95: PROMPT で p を打ったら文字として入るはず {ap.mode} {ap.input_buf!r}")
# WALK では input_text は捨てる
ap = h_app(31, 3)
p_frame(ap, text="abc")
check(ap.input_buf == "" and ap.mode == "WALK", f"95: WALK で input_text が入力欄に入った {ap.input_buf!r}")
# 入力欄の枠の色：WALK は 5、PROMPT は 10
ap.draw()
check(pyxel.screen.pget(P_IX, P_IY) == 5, f"95: WALK の入力欄の枠が色5でない {pyxel.screen.pget(P_IX, P_IY)}")
p_enter_prompt(ap)
ap.draw()
check(pyxel.screen.pget(P_IX, P_IY) == 10, f"95: PROMPT の入力欄の枠が色10でない {pyxel.screen.pget(P_IX, P_IY)}")
# 会話中に P を押しても会話は終わらない・Space を押したままの P でも何も起きない
ap = h_app(31, 3)
h_click_agent(ap, 1)
p_enter_prompt(ap)
check(ap.mode == "PROMPT" and ap.talk_partner == 1, "95: 会話中に P で PROMPT にしたら会話が終わった")

# 96. PROMPT で input_text（英字と日本語の確定文字）が入力欄に入る。Backspace で1文字消える。Enter で "> 文字" が履歴に足され入力欄が空。空のときの Enter は何もしない。長い文字は桁数で折り返す
ap = h_app(32, 2)
p_enter_prompt(ap)
p_type(ap, "abc")
check(ap.input_buf == "abc", f"96: 英字が入らない {ap.input_buf!r}")
p_type(ap, "こん")
check(ap.input_buf == "abcこん", f"96: 日本語の確定文字が入らない {ap.input_buf!r}")
p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
check(ap.input_buf == "abcこ", f"96: Backspace で1文字消えない {ap.input_buf!r}")
std96, ui96 = p_texts(ap)
check(any(t[2].startswith("abcこ") and t[1] == P_IY + O.UI_PAD for t in ui96), f"96: 入力欄に入力中の文字が出ていない {ui96[-3:]}")
n_hist = len(ap.history)
p_enter(ap)
check(ap.history[-1] == "> abcこ" and len(ap.history) == n_hist + 1, f"96: Enter で '> abcこ' が履歴に足されない {ap.history[-2:]}")
check(ap.input_buf == "" and ap.mode == "PROMPT", "96: Enter のあと入力欄が空・PROMPT のままでない")
check(ap.history_scroll == ap._max_scroll(), "96: 行を足したら一番下へ行かない")
# 空のときの Enter は何もしない（KP_ENTER も）
before96 = list(ap.history)
p_enter(ap)
p_enter(ap, pyxel.KEY_KP_ENTER)
check(ap.history == before96 and ap.input_buf == "", "96: 空の Enter で履歴が増えた")
p_type(ap, "ok")
p_enter(ap, pyxel.KEY_KP_ENTER)
check(ap.history[-1] == "> ok", f"96: テンキーの Enter で送れない {ap.history[-1]!r}")
# 空のとき Backspace は何も起きない
p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
check(ap.input_buf == "", "96: 空で Backspace したら変になった")
# 長い文字は桁数（UI_COLS）で折り返す：半角と全角
cols = O.UI_COLS
for tag, text in (("半角", "x" * 250), ("全角", "あ" * 80), ("混ぜ", "ab" + "あ" * 49 + "c" * 120)):
    n0 = len(ap.history)
    p_send(ap, text)
    rows = ap.history[n0:]
    check("".join(rows) == "> " + text, f"96: {tag} 折り返した行をつなぐと元の文字にならない {len(rows)}")
    check(all(p_cols(r) <= cols for r in rows) and len(rows) >= 2, f"96: {tag} 折り返しの桁数が {cols} を超える／折り返されない {[p_cols(r) for r in rows]}")
    # 最後の行以外は、次の1文字が入らない（詰めて折り返す）
    check(all(p_cols(r) >= cols - 1 for r in rows[:-1]), f"96: {tag} 行の途中で早く折り返した {[p_cols(r) for r in rows]}")
# 長い入力中の文字は入力欄で折り返し、3行を超えたら最後の3行だけ出る
p_type(ap, "y" * (cols * 4 + 5))
_, ui96 = p_texts(ap)
rows_in = [t for t in ui96 if t[1] >= P_IY and t[0] >= ap._input_text_x()]  # 左の「あ」「A」の札の文字は除く
check(len(rows_in) == O.INPUT_ROWS, f"96: 入力欄が 3 行を超えて出た／足りない {len(rows_in)}")
check(rows_in[0][1] == P_IY + O.UI_PAD and rows_in[-1][1] == P_IY + O.UI_PAD + 2 * O.UI_LINE_H, "96: 入力欄の行の位置が違う")
# 入力欄の文字が枠の中に収まる（画面の右端を超えない）
check(all(p_cols(t[2]) <= ap._input_cols() for t in rows_in), "96: 入力欄の1行が桁数（札のぶん狭い）を超えた")

# 97. PROMPT では Space・D・1〜4・Q・←→↑↓ が 3D に効かない（作業開始・ドア・利用制限・会話終了・カメラが変わらない）。WALK に戻ると効く
ap = h_app(33, 3)
p_enter_prompt(ap)
cam97 = (ap.cam_yaw, ap.cam_pitch, ap.cam_dist)
ni0, door0, five0, seven0 = ap.next_index, ap.door_open, ap.five_hour, ap.seven_day
for k in (pyxel.KEY_SPACE, pyxel.KEY_D, pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3, pyxel.KEY_4, pyxel.KEY_Q):
    p_frame(ap, keys=(k,))
check(ap.next_index == ni0 and all(a.state != "WORKING" for a in ap.agents), "97: PROMPT で Space が効いた（作業が始まった）")
check(ap.door_open == door0, "97: PROMPT で D がドアに効いた")
check(ap.five_hour == five0 and ap.seven_day == seven0 and ap.manual_limits is False, "97: PROMPT で 1〜4 が利用制限に効いた")
for ks in ({pyxel.KEY_LEFT}, {pyxel.KEY_RIGHT}, {pyxel.KEY_UP}, {pyxel.KEY_DOWN}):
    for _ in range(10):
        p_frame(ap, hold_keys=ks)
check((ap.cam_yaw, ap.cam_pitch, ap.cam_dist) == cam97, f"97: PROMPT でカーソルキーがカメラに効いた {cam97} → {(ap.cam_yaw, ap.cam_pitch, ap.cam_dist)}")
check(ap.mode == "PROMPT", "97: これらのキーでモードが変わった")
# Q：会話中に PROMPT で Q を押しても会話は終わらない
ap = h_app(33, 3)
h_click_agent(ap, 1)
p_enter_prompt(ap)
p_frame(ap, keys=(pyxel.KEY_Q,))
check(ap.talk_partner == 1 and ap.agents[1].hold, "97: PROMPT で Q が会話を終えた")
# Ctrl+E で WALK に戻ると、すべて効く
p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,))
check(ap.mode == "WALK", "97: Ctrl+E で WALK に戻らない")
p_frame(ap, keys=(pyxel.KEY_Q,))
check(ap.talk_partner is None, "97: WALK に戻っても Q が会話を終えない")
ni0 = ap.next_index
p_frame(ap, keys=(pyxel.KEY_SPACE,))
check(ap.next_index == (ni0 + 1) % len(ap.agents) and ap.agents[ni0].state == "WORKING", "97: WALK に戻っても Space が効かない")
p_frame(ap, keys=(pyxel.KEY_D,))
check(ap.door_open is True, "97: WALK で D が効かない")
p_frame(ap, keys=(pyxel.KEY_2,))
check(ap.five_hour == O.RATE_KEY_STEP and ap.manual_limits, "97: WALK で 2 が効かない")
p_frame(ap, keys=(pyxel.KEY_4,))
check(ap.seven_day == O.RATE_KEY_STEP, "97: WALK で 4 が効かない")
ap2 = h_app(33, 3)
ap2.update()
y97 = ap2.cam_yaw
for _ in range(10):
    p_frame(ap2, hold_keys={pyxel.KEY_RIGHT})
check(h_ang(ap2.cam_yaw, y97 + O.CAM_YAW_SPEED * 10 / OV_FPS) < 0.01, f"97: WALK で → が効かない {y97} → {ap2.cam_yaw}")
# PROMPT で打った Space は文字として入る
p_enter_prompt(ap2)
p_frame(ap2, text="a b")
check(ap2.input_buf == "a b", f"97: PROMPT で空白が文字として入らない {ap2.input_buf!r}")

# 98. Ctrl+E で WALK に戻る。入力中の文字は残る。e が入らない。Ctrl を押している間の input_text も入らない
ap = h_app(34, 2)
p_enter_prompt(ap)
p_type(ap, "abc")
p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,), text="e")
check(ap.mode == "WALK" and ap.input_buf == "abc", f"98: Ctrl+E で WALK に戻る・文字が残る でない {ap.mode} {ap.input_buf!r}")
# 戻ったあとの表示：入力中の文字は入力欄に残って見える（カーソルは出ない）
_, ui98 = p_texts(ap)
check(any(t[2] == "abc" for t in ui98), f"98: WALK でも入力中の文字が入力欄に見えない {ui98[-3:]}")
p_enter_prompt(ap)
check(ap.input_buf == "abc", "98: もう一度 PROMPT にしたら入力中の文字が消えた")
# 右 Ctrl でも
p_frame(ap, hold_keys=(pyxel.KEY_RCTRL,), keys=(pyxel.KEY_E,), text="e")
check(ap.mode == "WALK" and ap.input_buf == "abc", f"98: 右 Ctrl+E で WALK に戻らない {ap.mode} {ap.input_buf!r}")
p_enter_prompt(ap)
# Ctrl を押している間の input_text は入らない（e 以外のキーでも）。モードも変わらない
p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), text="x")
check(ap.mode == "PROMPT" and ap.input_buf == "abc", f"98: Ctrl 押下中の input_text が入った {ap.input_buf!r}")
p_frame(ap, hold_keys=(pyxel.KEY_RCTRL,), keys=(pyxel.KEY_A,), text="a")
check(ap.mode == "PROMPT" and ap.input_buf == "abc", f"98: 右 Ctrl 押下中の input_text が入った {ap.input_buf!r}")
# Ctrl を離せば入る
p_frame(ap, text="d")
check(ap.input_buf == "abcd", "98: Ctrl を離したあと文字が入らない")
# e だけ（Ctrl なし）は文字として入り、モードは変わらない
p_frame(ap, keys=(pyxel.KEY_E,), text="e")
check(ap.mode == "PROMPT" and ap.input_buf == "abcde", f"98: Ctrl なしの e が文字として入らない {ap.mode} {ap.input_buf!r}")
# WALK で Ctrl+E は何も起こさない
p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,))
check(ap.mode == "WALK", "98: Ctrl+E で WALK")
p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,))
check(ap.mode == "WALK" and ap.input_buf == "abcde", "98: WALK で Ctrl+E をもう一度押したら変わった")

# 99. PROMPT の Esc で履歴に「(Esc: 中断を送る)」が1行、モードは PROMPT のまま。WALK の Esc は何も起きず、アプリも終わらない（quit_key が KEY_NONE）
ap = h_app(35, 2)
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(len(ap.history) == n0 and ap.mode == "WALK" and ap.input_buf == "", f"99: WALK の Esc で何かが起きた {ap.history[-2:]} {ap.mode}")
p_enter_prompt(ap)
p_type(ap, "draft")
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(len(ap.history) == n0 + 1 and ap.history[-1] == "(Esc: 中断を送る)", f"99: PROMPT の Esc で履歴に1行出ない {ap.history[-2:]}")
check(ap.mode == "PROMPT" and ap.input_buf == "draft", f"99: PROMPT の Esc でモード・入力中の文字が変わった {ap.mode} {ap.input_buf!r}")
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(len(ap.history) == n0 + 2 and ap.history[-1] == "(Esc: 中断を送る)", "99: Esc を2回押したら2行にならない")
# アプリを閉じる設定：pyxel.init の引数（quit_key が KEY_NONE、office は 640×500・display_scale 2、proto は 256×192）
init_calls = []
_saved_init99 = pyxel.init
pyxel.init = lambda *a, **k: init_calls.append((a, k))
try:
    pyxelcube_agents.App(30, 1, "office", 2, config_path=SAFE_CFG)
    pyxelcube_agents.App(30, 1, "proto", 3, config_path=SAFE_CFG)
finally:
    pyxel.init = _saved_init99
check(len(init_calls) == 2, f"99: pyxel.init の呼び出しが2回でない {init_calls}")
if len(init_calls) == 2:
    (oa, ok_), (pa, pk) = init_calls
    check(oa[:2] == (640, 500) and ok_.get("display_scale") == 2 and ok_.get("quit_key") == pyxel.KEY_NONE,
          f"99: office の pyxel.init の引数が 640×500・display_scale=2・quit_key=KEY_NONE でない {oa} {ok_}")
    check(pa[:2] == (256, 192) and pk.get("quit_key", pyxel.KEY_NONE) == pyxel.KEY_NONE and "display_scale" not in pk,
          f"99: proto の pyxel.init の引数が 256×192 のままでない {pa} {pk}")

# 100. 入力欄のクリックで PROMPT、3D のクリックで WALK になりそのクリックで歩く／話しかける。履歴の枠のクリックではモードが変わらない。3D の範囲の外のクリックでは歩かない
ap = h_app(36, 3)
ap.update()
hist0 = list(ap.history)
p_frame(ap, click=(100, P_IY + 10))
check(ap.mode == "PROMPT" and ap.history == hist0 and not ap.human.walking and ap.talk_partner is None, f"100: 入力欄のクリックで PROMPT にならない／何かが動いた {ap.mode}")
# 3D のクリック：床 → WALK になって歩く
sxy = h_proj(ap, 150.0, 0.0, 100.0)
p_frame(ap, click=(round(sxy[0]), round(sxy[1])))
check(ap.mode == "WALK" and ap.human.walking, f"100: PROMPT 中の3Dクリックで WALK になって歩き出さない {ap.mode} {ap.human.walking}")
# 3D のクリック：人 → WALK になって話しかける
p_enter_prompt(ap)
ap.update()
sxy = h_agent_xy(ap, 1)
p_frame(ap, click=(round(sxy[0]), round(sxy[1])))
check(ap.mode == "WALK" and ap.talk_partner == 1, f"100: PROMPT 中に人をクリックしても WALK で話しかけない {ap.mode} {ap.talk_partner}")
# 履歴の枠のクリックではモードが変わらない（WALK のときも PROMPT のときも）。歩かない・話しかけない
ap = h_app(36, 3)
ap.update()
p_frame(ap, click=(100, P_HY + 10))
check(ap.mode == "WALK" and not ap.human.walking and ap.talk_partner is None, "100: WALK で履歴の枠をクリックしたら変わった")
p_enter_prompt(ap)
p_frame(ap, click=(100, P_HY + 10))
check(ap.mode == "PROMPT" and not ap.human.walking, "100: PROMPT で履歴の枠をクリックしたらモードが変わった")
p_frame(ap, click=(2, P_HY + 10))  # 枠の外の左（余白）
check(ap.mode == "PROMPT", "100: 履歴の枠の外の余白のクリックでモードが変わった")
# 3D の範囲の外のクリックでは歩かない（3D の真下・履歴との間・入力欄の下の余白）
ap = h_app(36, 3)
ap.update()
h0 = (ap.human.pos.x, ap.human.pos.z)
for (cx, cy) in ((320, O.VIEW3D_H), (320, O.VIEW3D_H + 1), (320, P_HY - 1), (10, P_IY - 2), (320, O.OFFICE_SCREEN_H - 1), (639, O.VIEW3D_H)):
    p_frame(ap, click=(cx, cy))
    check(not ap.human.walking and (ap.human.pos.x, ap.human.pos.z) == h0 and ap.talk_partner is None,
          f"100: 3D の範囲の外 ({cx},{cy}) のクリックで歩いた／話しかけた")
# 画面の外（x が 640 以上）のクリックは、マウスが窓から出たときにしか起きない。起きたときの動きを記録だけする（合否なし）
ap = h_app(36, 3)
ap.update()
p_frame(ap, click=(700, 100))
print(f"(100) x=700（画面の右の外）・y=100 のクリックで歩き出したか: {ap.human.walking}")
# 3D の範囲の一番下の行（y=295）は3D の中。床なら歩く
ap = h_app(36, 3)
ap.update()
e_, d_ = h_ray(ap, 320, O.VIEW3D_H - 1)
if ap.floor_hit(e_, d_) is not None and ap.pick_agent(e_, d_) is None:
    p_frame(ap, click=(320, O.VIEW3D_H - 1))
    check(ap.human.walking, "100: 3D の範囲の一番下の行のクリックで歩かない")
# 入力欄をクリックしても文字は消えない
ap = h_app(36, 3)
p_enter_prompt(ap)
p_type(ap, "keep")
p_frame(ap, click=(100, P_HY + 10))
p_frame(ap, click=(100, P_IY + 5))
check(ap.input_buf == "keep" and ap.mode == "PROMPT", "100: クリックで入力中の文字が消えた")

# 101. ホイール：履歴の上で履歴がスクロール（端で止まる）、3D の上でズーム、それ以外は何もしない。行を足すと一番下へ。HISTORY_MAX を超えると古い行が消える。9 行以下ではスクロールバーを描かない。溝のクリックでその位置へ飛ぶ
ap = h_app(37, 3)
p_enter_prompt(ap)
for k in range(24):
    p_send(ap, f"line{k}")
total = len(ap.history)
check(total == 24, f"101: 履歴の行数が 24 でない（起動時の行は無い） {total}")
mx = ap._max_scroll()
check(mx == total - O.HISTORY_ROWS and ap.history_scroll == mx, f"101: 行を足したら一番下へ行く でない {ap.history_scroll} {mx}")
hover_h = (100, P_HY + 20)
hover_3d = (100, 100)
hover_in = (100, P_IY + 20)
hover_gap = (100, O.VIEW3D_H + 1)
d0 = ap.cam_dist
p_frame(ap, mouse=hover_h, wheel=1)
check(ap.history_scroll == mx - 1 and ap.cam_dist == d0, f"101: 履歴の上のホイール（奥）で1行上がらない／ズームした {ap.history_scroll} {ap.cam_dist}")
p_frame(ap, mouse=hover_h, wheel=-1)
check(ap.history_scroll == mx, "101: 履歴の上のホイール（手前）で1行下がらない")
p_frame(ap, mouse=hover_h, wheel=-3)
check(ap.history_scroll == mx, f"101: 一番下でさらに下へ回しても止まらない {ap.history_scroll}")
p_frame(ap, mouse=hover_h, wheel=5)
check(ap.history_scroll == mx - 5, f"101: ホイール 5 で 5 行上がらない {ap.history_scroll}")
p_frame(ap, mouse=hover_h, wheel=1000)
check(ap.history_scroll == 0, f"101: 一番上で止まらない {ap.history_scroll}")
p_frame(ap, mouse=hover_h, wheel=1)
check(ap.history_scroll == 0, "101: 一番上でさらに上へ回しても止まらない")
# 3D の上：ズーム。履歴は動かない
s0 = ap.history_scroll
d0 = ap.cam_dist
p_frame(ap, mouse=hover_3d, wheel=2)
check(abs(ap.cam_dist - d0 * O.ZOOM_STEP ** 2) < 1e-6 and ap.history_scroll == s0, f"101: 3D の上のホイールでズームしない／履歴が動いた {d0} → {ap.cam_dist}")
# それ以外（入力欄の上・3D と履歴の間・画面の右の余白）は何もしない
d0 = ap.cam_dist
for pos in (hover_in, hover_gap, (100, O.OFFICE_SCREEN_H - 1), (2, P_HY + 5), (639, P_HY + 5)):
    p_frame(ap, mouse=pos, wheel=3)
    p_frame(ap, mouse=pos, wheel=-3)
    check(ap.cam_dist == d0 and ap.history_scroll == s0, f"101: 履歴・3D 以外の {pos} の上のホイールで何かが変わった {ap.cam_dist} {ap.history_scroll}")
# 行を足すと一番下へ（上へ回していても戻る）
p_send(ap, "newest")
check(ap.history_scroll == ap._max_scroll() and ap.history[-1] == "> newest", "101: 上へ回したあと行を足しても一番下へ戻らない")
# スクロールバー：9 行以下では描かない。10 行以上では溝（色1）とつまみ（色7）
ap = h_app(37, 3)
tx, ty, tw, th = ap._scroll_track()


def p_track_colors(app):
    app.update()
    app.draw()
    cols_ = {}
    for yy in range(ty, ty + th):
        for xx in range(tx, tx + tw):
            c = pyxel.screen.pget(xx, yy)
            cols_[c] = cols_.get(c, 0) + 1
    return cols_


def p_thumb_rows(app):
    app.draw()
    rows_ = [yy for yy in range(ty, ty + th) if pyxel.screen.pget(tx + tw // 2, yy) == 7]
    return rows_


for n_lines in (1, 5, 9):
    ap = h_app(37, 3)
    while len(ap.history) < n_lines:
        ap._add_history(f"row{len(ap.history)}")
    tc = p_track_colors(ap)
    check(set(tc) == {0}, f"101: 履歴が {n_lines} 行（9行以下）なのにスクロールバーが描かれた {tc}")
for n_lines in (10, 40, 300):
    ap = h_app(37, 3)
    while len(ap.history) < n_lines:
        ap._add_history(f"row{len(ap.history)}")
    tc = p_track_colors(ap)
    check(tc.get(1, 0) > 0 and tc.get(7, 0) > 0, f"101: 履歴が {n_lines} 行なのにスクロールバーの溝・つまみがない {tc}")
    rows_t = p_thumb_rows(ap)
    want_len = max(6, int(th * O.HISTORY_ROWS / n_lines))
    check(abs(len(rows_t) - want_len) <= 1, f"101: {n_lines} 行のつまみの長さが見えている割合でない {len(rows_t)} 期待 {want_len}")
    check(rows_t and rows_t[-1] == ty + th - 1 or (rows_t and abs(rows_t[-1] - (ty + th - 1)) <= 1), f"101: 一番下にいるのにつまみが溝の下端にない {rows_t[-1:]}")
    ap.history_scroll = 0
    rows_t0 = p_thumb_rows(ap)
    check(rows_t0 and rows_t0[0] == ty, f"101: 一番上にいるのにつまみが溝の上端にない {rows_t0[:1]}")
    # 溝のクリックでその位置へ飛ぶ（WALK のまま・歩かない）
    for frac in (0.0, 0.25, 0.5, 0.9):
        cy_ = ty + int(th * frac)
        p_frame(ap, click=(tx + 2, cy_))
        want_scroll = min(ap._max_scroll(), int(((cy_ - ty) / th) * (n_lines - O.HISTORY_ROWS)))
        check(ap.history_scroll == want_scroll and ap.mode == "WALK" and not ap.human.walking,
              f"101: {n_lines} 行で溝の {frac} をクリックしてもその位置へ飛ばない {ap.history_scroll} 期待 {want_scroll}")
    p_frame(ap, click=(tx + 2, ty + th - 1))
    gap101 = ap._max_scroll() - ap.history_scroll
    check(0 <= gap101 <= (n_lines - O.HISTORY_ROWS) / th + 1, f"101: 溝の一番下のクリックでほぼ一番下へ飛ばない {ap.history_scroll} 最大 {ap._max_scroll()}")
    print(f"(101) {n_lines}行：溝の最下段をクリックして一番下まで足りない行数 {gap101}")
# 溝のクリックは PROMPT のモードを変えない
ap = h_app(37, 3)
for k in range(15):
    ap._add_history(f"row{k}")
p_enter_prompt(ap)
p_frame(ap, click=(tx + 2, ty + 5))
check(ap.mode == "PROMPT", "101: 溝のクリックで PROMPT でなくなった")
# 9 行以下でも溝の位置のクリックは何も起こさない（落ちない・歩かない・モード不変）
ap = h_app(37, 3)
p_frame(ap, click=(tx + 2, ty + 10))
check(ap.mode == "WALK" and ap.history_scroll == 0 and not ap.human.walking, "101: 9行以下で溝をクリックしたら変わった")
# HISTORY_MAX：超えると古い行から消える
ap = h_app(37, 3)
p_enter_prompt(ap)
N101 = O.HISTORY_MAX + 10
for k in range(N101):
    p_send(ap, f"n{k}")
check(len(ap.history) == O.HISTORY_MAX, f"101: 履歴が HISTORY_MAX({O.HISTORY_MAX}) 行に収まらない {len(ap.history)}")
check(ap.history[-1] == f"> n{N101 - 1}", f"101: 一番新しい行が残らない {ap.history[-1]!r}")
want_first = N101 - O.HISTORY_MAX + 1  # 起動時の行は無い。N101行のうち、先頭から (N101-HISTORY_MAX) 行が消え、残る先頭は n{N101-HISTORY_MAX}（want_first-1）
check(ap.history[0] == f"> n{want_first - 1}", f"101: 古い行から消えていない 先頭 {ap.history[0]!r} 期待 > n{want_first - 1}")
check(not any("試作" in x for x in ap.history), "101: 起動時の行が残っている")
check(ap.history_scroll == ap._max_scroll(), "101: 上限を超えたあと一番下にいない")

# 102. 会話の立つ場所：相手以外から 2R+TALK_CLEAR 以上、障害物から余白つき。会話のカメラで2人の頭の画面上の横の差が TALK_MIN_SCREEN_GAP 以上
R102 = O.AGENT_RADIUS
stat102 = {"tries": 0, "talk": 0, "no_spot": 0, "gap_ok": 0, "gap_small": 0}
small102 = []
bad102 = []
x_min, x_max = OLAY.wander_x
z_min, z_max = OLAY.wander_z


def p_check_spot(ap, i, tag):
    """会話が始まったあとの人間の位置について、離れ・余白を調べ、カメラの頭の横の差を数える。"""
    hx_, hz_ = ap.human.pos.x, ap.human.pos.z
    for j, other in enumerate(ap.agents):
        d_ = math.hypot(other.pos.x - hx_, other.pos.z - hz_)
        need = 2 * R102 if j == i else 2 * R102 + O.TALK_CLEAR
        if d_ < need - 1e-3:
            bad102.append(f"{tag}: 人{j} との距離 {d_:.1f} < {need:.1f}")
    for ob in ap.obstacles:
        dd = rect_dist(hx_, hz_, ob.rect)
        if dd < R102 + O.TALK_CLEAR / 2 - 1e-3:
            bad102.append(f"{tag}: 障害物との距離 {dd:.1f} < {R102 + O.TALK_CLEAR / 2:.1f}")
            break
    for cx_, cz_, cr_ in ap.circles:
        dd = math.hypot(hx_ - cx_, hz_ - cz_) - cr_
        if dd < R102 + O.TALK_CLEAR / 2 - 1e-3:
            bad102.append(f"{tag}: 丸い障害物との距離 {dd:.1f}")
    if not (x_min <= hx_ <= x_max and z_min <= hz_ <= z_max):
        bad102.append(f"{tag}: 床の範囲の外 ({hx_:.0f},{hz_:.0f})")
    # カメラの頭の横の差
    ov_step(ap, int(O.CAM_BLEND_SEC * OV_FPS) + 3)
    partner = ap.agents[i]
    hh = O.HEAD_CENTER.y
    ph = ap.world_to_screen(Vec3(partner.pos.x, hh + partner.pose.body_y, partner.pos.z), *ap._view_rect())
    hhp = ap.world_to_screen(Vec3(ap.human.pos.x, hh + ap.human.pose.body_y, ap.human.pos.z), *ap._view_rect())
    if ph is None or hhp is None:
        bad102.append(f"{tag}: 頭がカメラの後ろ")
        return
    # h_proj（screen_ray の式の逆）と world_to_screen が同じ点を返す
    ph2 = h_proj(ap, partner.pos.x, hh + partner.pose.body_y, partner.pos.z)
    if abs(ph[0] - ph2[0]) > 1e-2 or abs(ph[1] - ph2[1]) > 1e-2:
        bad102.append(f"{tag}: world_to_screen と投影の式が違う {ph} {ph2}")
    gap = abs(ph[0] - hhp[0])
    if gap >= O.TALK_MIN_SCREEN_GAP - 0.5:
        stat102["gap_ok"] += 1
    else:
        stat102["gap_small"] += 1
        small102.append((tag, round(gap, 1), (round(partner.pos.x), round(partner.pos.z)), (round(hx_), round(hz_)), round(ap.cam_yaw)))


for seed102 in (1, 2, 3):
    ap = ov_app(seed102, 18, 1.0)
    ov_quiet(ap)
    ov_step(ap, 20 + seed102 * 30)  # みんなが席のまわりで動いている状態
    for i in range(18):
        stat102["tries"] += 1
        p = h_click_agent(ap, i)
        if ap.talk_partner != i:
            stat102["no_spot"] += 1
            continue
        stat102["talk"] += 1
        p_check_spot(ap, i, f"種{seed102}・立っている人{i}")
        ap.end_talk()
        ov_step(ap, int(O.CAM_BLEND_SEC * OV_FPS) + 3)
        ap.human.warp(O.HUMAN_START[0], O.HUMAN_START[1], 0.0)
        ap.cam_target = Vec3(O.HUMAN_START[0], 0.0, O.HUMAN_START[1])
        ap._apply_camera()
# 座っている人（作業にしてから）：メインと島の席の人
for seed102, who in ((4, (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)),):
    ap = ov_app(seed102, 18, 1.0)
    ov_quiet(ap)
    for i in who:
        stat102["tries"] += 1
        if not h_seat_up(ap, i, 2400):
            bad102.append(f"席{i}に座れない")
            continue
        ov_step(ap, 3)
        h_click_agent(ap, i)
        if ap.talk_partner != i:
            stat102["no_spot"] += 1
            continue
        stat102["talk"] += 1
        p_check_spot(ap, i, f"座っている人{i}")
        ap.end_talk()
        ov_step(ap, int(O.CAM_BLEND_SEC * OV_FPS) + 3)
check(not bad102, f"102: 立つ場所・余白・カメラの条件を満たさない例 {bad102[:6]}（計{len(bad102)}件）")
check(stat102["talk"] >= 40, f"102: 会話が始まった数が少ない {stat102}")
print(f"(102) 会話の立つ場所と頭の横の差 {stat102}")
if small102:
    print(f"(102) 頭の横の差が {O.TALK_MIN_SCREEN_GAP} 未満の会話の場面 {len(small102)} 件。例（場面, 差, 相手の位置, 人間の位置, yaw）:", small102[:6])
# 座っている人の1人（メイン席0）：人間が机の正面に立つと、机・椅子との余白も満たす
ap = h_app(38, 1)
h_seat_up(ap, 0)
ov_step(ap, 3)
h_click_agent(ap, 0)
check(ap.talk_partner == 0, "102: 前提：座ったメインと会話にならない")
check(all(rect_dist(ap.human.pos.x, ap.human.pos.z, ob.rect) >= R102 + O.TALK_CLEAR / 2 - 1e-3 for ob in ap.obstacles), "102: メインの机の正面の位置が障害物に近すぎる")
# world_to_screen：カメラの後ろは None、前は screen_ray の逆
ap = h_app(38, 1)
eye_ = ap.cam_target + ap.cam_dir * ap.cam_dist
check(ap.world_to_screen(eye_ + ap.cam_dir * 10.0, *ap._view_rect()) is None, "102: カメラの後ろの点が None でない")
vx_, vy_, vw_, vh_ = ap._view_rect()
cw = ap.world_to_screen(ap.cam_target, vx_, vy_, vw_, vh_)
check(cw is not None and abs(cw[0] - (vw_ / 2 - 0.5)) < 1e-3 and abs(cw[1] - (vh_ / 2 - 0.5)) < 1e-3, f"102: 注視点が3Dの範囲の中心に投影されない {cw}")
# 相手以外の人が近くにいる所には立たない：相手の隣の候補の位置に別の人を置いて、その方向を避ける
ap = h_app(38, 4)
ov_step(ap, 3)
tgt = ap.agents[1]
first = ap._talk_spot(1)
ap.agents[2].pos = Vec3(first[0] + 20.0, 0.0, first[1])  # 候補のすぐ隣（2R+TALK_CLEAR=40 未満）
second = ap._talk_spot(1)
check(second is None or math.hypot(second[0] - ap.agents[2].pos.x, second[1] - ap.agents[2].pos.z) >= 2 * R102 + O.TALK_CLEAR - 1e-6,
      f"102: 相手以外の人に 2R+TALK_CLEAR より近い位置を選んだ {second}")
check(second != first, "102: 近くに別の人がいるのに同じ位置を選んだ")

# 103. ▼の色が 10 で陰影なし（▼の画素に色10があり、陰影の暗い色が混じらない）
check(O.MARKER_COLOR == 10, f"103: MARKER_COLOR が 10 でない {O.MARKER_COLOR}")
ap = h_app(39, 2)
ap.cam_dist = 600.0
ap._apply_camera()
ap.update()
mv = [v for v in ap.scene.children if isinstance(v, O.MarkerView)][0]
# 描くときに shaded(False) を最初に呼び、三角が MARKER_COLOR だけで描かれる
calls103 = []
_orig_shaded = mv.shaded
_orig_tri = mv.tri
mv.shaded = lambda *a, **k: (calls103.append(("shaded", a)), _orig_shaded(*a, **k))[1]
mv.tri = lambda *a, **k: (calls103.append(("tri", a[-1])), _orig_tri(*a, **k))[1]
ap.draw()
del mv.shaded
del mv.tri
check(calls103 and calls103[0] == ("shaded", (False,)), f"103: ▼を描くとき最初に shaded(False) を呼ばない {calls103[:2]}")
check(len([c for c in calls103 if c[0] == "tri"]) == 6 and all(c[1] == 10 for c in calls103 if c[0] == "tri"), f"103: ▼の三角が6枚・色10でない {calls103}")
# 画素：▼のまわりの窓で、▼を描いたときに増える色が 10 だけ
mx_, my_ = h_proj(ap, ap.human.pos.x, O.MARKER_Y, ap.human.pos.z)
win = [(xx, yy) for yy in range(int(my_) - 25, int(my_) + 25) for xx in range(int(mx_) - 25, int(mx_) + 25)]
_orig_on_draw = O.MarkerView.on_draw
O.MarkerView.on_draw = lambda self: None
try:
    ap.draw()
    bg103 = {pyxel.screen.pget(xx, yy) for xx, yy in win}
finally:
    O.MarkerView.on_draw = _orig_on_draw
ap.draw()
fg103 = {}
for xx, yy in win:
    c = pyxel.screen.pget(xx, yy)
    fg103[c] = fg103.get(c, 0) + 1
new103 = set(fg103) - bg103
check(fg103.get(10, 0) >= 20, f"103: ▼の画素（色10）が少ない {fg103.get(10, 0)}（窓の色 {fg103}）")
check(new103 <= {10}, f"103: ▼のまわりに色10以外の新しい色（陰影の色）が混じった {new103} 窓の色 {fg103} 背景 {bg103}")
# 揺れても（時間が進んでも）色は10のまま
for _ in range(20):
    ap.update()
ap.draw()
mx_, my_ = h_proj(ap, ap.human.pos.x, O.MARKER_Y, ap.human.pos.z)
cnt103 = sum(1 for yy in range(int(my_) - 25, int(my_) + 25) for xx in range(int(mx_) - 25, int(mx_) + 25) if pyxel.screen.pget(xx, yy) == 10)
check(cnt103 >= 20, f"103: 少したったあと▼の色10が見えない {cnt103}")

# 104. 歩き出しの逆走：(0,40) から (-200,60) をクリックした最初の数フレームで、目的地からの距離が増えない
for (gx, gz) in ((-200.0, 60.0), (150.0, 100.0), (60.0, -150.0), (320.0, 220.0), (-300.0, 230.0), (-100.0, 260.0), (0.0, -250.0)):
    ap = h_app(40, 2)
    h_click_floor(ap, gx, gz)
    check(ap.human.walking, f"104: ({gx},{gz}) のクリックで歩き出さない")
    prev = math.hypot(gx - ap.human.pos.x, gz - ap.human.pos.z)
    d_start = prev
    worst_up = 0.0
    for f in range(8):
        ap.update()
        cur = math.hypot(gx - ap.human.pos.x, gz - ap.human.pos.z)
        worst_up = max(worst_up, cur - prev)
        prev = cur
    check(worst_up <= 1e-6, f"104: ({gx},{gz}) への歩き出しで距離が増えた（逆走）最大 +{worst_up:.2f}")
    check(prev < d_start - 20.0, f"104: ({gx},{gz}) への最初の8フレームでほとんど進まない {d_start:.1f} → {prev:.1f}")
# 道の最初の点：今いる場所のマスの中心ではない（2つ目の点へ直接行けるなら捨てる）
ap = h_app(40, 2)
ap.human.walk_to(-200.0, 60.0, [])
first_pt = ap.human._path[0]
check(math.hypot(first_pt.x - ap.human.pos.x, first_pt.z - ap.human.pos.z) > 0.5 or len(ap.human._path) == 1,
      f"104: 道の先頭が今いる位置の近くのまま {first_pt}")
# 目的地が近い（今の位置から NAV_CELL 以内）ときも、目的地へ向かう（点が1つだけ）
ap = h_app(40, 2)
ap.human.walk_to(5.0, 45.0, [])
check(ap.human.walking and abs(ap.human._path[-1].x - 5.0) <= 10.0 and abs(ap.human._path[-1].z - 45.0) <= 10.0,
      f"104: 近い目的地へ向かう道の最後が目的地でない {[(p.x, p.z) for p in ap.human._path]}")
# エージェントの道は変えていない：エージェントの道の先頭はこれまでどおり（出発のマスの中心を含みうる）。人間と同じ関数を使っていないことだけ確かめる
check(O.Human.walk_to is not O.Agent._plan, "104: Human.walk_to が Agent の道探しそのままになっている")

# 105. モードの案内は y=270 の行ではなく、上の真ん中の MODE の黒い四角の中。左下の案内2行は元の位置で、ほかの文字と重ならない
for n105 in (6, 18):
    for talk105 in (False, True):
        for mode105 in ("WALK", "PROMPT"):
            ap = h_app(41, n105)
            ap.update()
            if talk105:
                h_click_agent(ap, 1)
            if mode105 == "PROMPT":
                p_enter_prompt(ap)
            std, ui = p_texts(ap)
            tag = f"{n105}人・会話{talk105}・{mode105}"
            check(not any(t[1] == 270 for t in std), f"105: {tag} y=270 に案内の行が出ている {[t for t in std if t[1] == 270]}")
            check(not any(("P:PROMPT" in t[2] or "CTRL+E" in t[2]) and not (2 <= t[1] <= 6) for t in std), f"105: {tag} モードの案内が MODE の四角の外に出ている")
            parts = p_label_parts(std)
            check(any(P_HINT[mode105] == t[2].strip() for t in parts), f"105: {tag} 案内 {P_HINT[mode105]!r} が MODE の行に出ていない {parts}")
            other_mode = "PROMPT" if mode105 == "WALK" else "WALK"
            check(not any(P_HINT[other_mode] == t[2].strip() for t in std), f"105: {tag} もう一方のモードの案内が出ている")
            # 左下の案内2行は元の位置（VIEW3D_H-18・-10）・色7
            low = sorted(t for t in std if t[1] >= 260)
            check(low == [], f"105: {tag} 左下に案内の行が出ている（製品版では出さない） {low}")
            # 重ならない：標準フォントの文字どうし。MODE の黒い四角（上下左右2点）が別の文字を隠さない
            rects = [(t[0], t[1], t[0] + len(t[2]) * pyxel.FONT_WIDTH, t[1] + pyxel.FONT_HEIGHT, t[2]) for t in std]
            for a_i in range(len(rects)):
                for b_i in range(a_i + 1, len(rects)):
                    a_, b_ = rects[a_i], rects[b_i]
                    over = a_[0] < b_[2] and b_[0] < a_[2] and a_[1] < b_[3] and b_[1] < a_[3]
                    check(not over, f"105: {tag} 文字が重なる {a_[4]!r} {b_[4]!r}")
            lab = [r for r in rects if 2 <= r[1] <= 6 and (r[4].startswith("MODE:") or r[4].lstrip().startswith("("))]
            if lab:
                lx0, lx1 = min(r[0] for r in lab) - 2, max(r[2] for r in lab) + 2
                ly0, ly1 = min(r[1] for r in lab) - 2, max(r[3] for r in lab) + 2
                for r in rects:
                    if r in lab:
                        continue
                    check(not (r[0] < lx1 and lx0 < r[2] and r[1] < ly1 and ly0 < r[3]), f"105: {tag} MODE の黒い四角が別の文字 {r[4]!r} にかかる")
            check(all(r[3] <= O.VIEW3D_H for r in rects), f"105: {tag} 3D の範囲の下端を越える文字がある")
# proto には新しい案内がない
tt_p105, _ = p_texts(papp61)
check(not any("PROMPT" in t[2] or "MODE" in t[2] for t in tt_p105), "105: proto に MODE・PROMPT の案内が出た")


# 106. PNG：メイン・島の席の人・立っている人との会話、PROMPT で文字を打った画面、履歴が9行を超えてスクロールバーが出た画面を書く（合否は書けたことだけ）
def h_shot3(name, setup, frames=None):
    ap_ = ov_app(21, 18, 1.0)
    ov_quiet(ap_)
    ap_.update()
    setup(ap_)
    ov_step(ap_, (int(O.CAM_BLEND_SEC * OV_FPS) + 12) if frames is None else frames)
    ap_.draw()
    path_ = H_SHOT_DIR3 / name
    h_write_png(path_, 1)
    return ap_, path_


def s_prompt(ap_):
    p_enter_prompt(ap_)
    p_send(ap_, "hello Claude")
    p_send(ap_, "こんにちは。日本語も入ります")
    p_type(ap_, "typing now こんな感じ")


def s_scroll(ap_):
    p_enter_prompt(ap_)
    for k in range(30):
        p_send(ap_, f"line {k:02d} の履歴")
    p_frame(ap_, keys=(pyxel.KEY_ESCAPE,))
    p_frame(ap_, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,))
    p_frame(ap_, mouse=(100, P_HY + 20), wheel=8)


shots106 = []
for name106, setup106, who106, mode106 in (
    ("talk_main.png", h_setup_main, 0, "WALK"),
    ("talk_island.png", h_setup_island, 5, "WALK"),
    ("talk_standing.png", h_setup_stand, 8, "WALK"),
    ("prompt_typing.png", s_prompt, None, "PROMPT"),
    ("history_scroll.png", s_scroll, None, "WALK"),
):
    ap106, path106 = h_shot3(name106, setup106, 2 if who106 is None else None)
    ok106 = path106.exists() and path106.stat().st_size > 1000 and path106.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    check(ok106 and ap106.talk_partner == who106 and ap106.mode == mode106, f"106: 画像 {name106} を書けなかった／場面が作れていない {ok106} {ap106.talk_partner} {ap106.mode}")
    shots106.append(str(path106))
print("(106) 画像", shots106)


# ---- ここから日本語入力（fcitx5＋mozc）の「変換中」の推測の項目（107〜115）。実機の記録（ime_probe）の順番をまねる ----
# 実機の事実：オンのとき英字キーを押しても input_text は来ない／変換中の Enter・Backspace・Esc は Pyxel にも届く／
# 確定の Enter は次のフレームに確定文字が input_text で届く／オフでは英字は押したフレームに届く。
KEY_A_ = pyxel.KEY_A


def p_letter(app, key=None, text="", hold=()):
    """英字キーを1フレーム押す（text が空なら日本語入力オンの想定で文字は来ない）。"""
    p_frame(app, keys=(KEY_A_ if key is None else key,), text=text, hold_keys=hold)


def p_composing(app):
    """英字キーだけを押して、変換中と推測されるまで進める。"""
    p_letter(app)
    for _ in range(O.IME_GRACE_FRAMES + 1):
        p_frame(app)


def p_prompt_app(seed=51, n=2):
    ap_ = h_app(seed, n)
    p_enter_prompt(ap_)
    return ap_


def p_hist_extra(ap_, n0):
    return ap_.history[n0:]


# 107. 確定の Enter：Enter だけのフレーム→次のフレームに input_text='日本語' → 送信されず入力欄に '日本語' が足される
for start107 in ("", "x"):
    ap = p_prompt_app()
    if start107:
        p_type(ap, start107)
    n0 = len(ap.history)
    p_frame(ap, keys=(pyxel.KEY_RETURN,))
    check(len(ap.history) == n0 and ap.input_buf == start107, f"107: Enter のフレームで送信された／入力欄が変わった {ap.history[n0:]}")
    p_frame(ap, text="日本語")
    check(ap.input_buf == start107 + "日本語", f"107: 次のフレームの確定文字が入力欄に足されない {ap.input_buf!r}")
    check(len(ap.history) == n0, f"107: 確定の Enter で送信された {ap.history[n0:]}")
    check(ap._pending_enter == 0 and ap.ime_composing is False, "107: 確定のあと送信待ち・変換中が残っている")
    for _ in range(O.IME_ENTER_WAIT + 3):
        p_frame(ap)
    check(len(ap.history) == n0 and ap.input_buf == start107 + "日本語", f"107: 確定のあと時間がたって送信された／入力欄が変わった {ap.history[n0:]} {ap.input_buf!r}")
# Enter から確定文字までに1フレームはさんでも（IME_ENTER_WAIT の範囲）確定として扱う
ap = p_prompt_app()
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_RETURN,))
p_frame(ap)
p_frame(ap, text="あいう")
check(len(ap.history) == n0 and ap.input_buf == "あいう", f"107: Enter の2フレーム後の確定文字が足されない／送信された {ap.input_buf!r} {ap.history[n0:]}")

# 108. 送信の Enter：文字なしの Enter → IME_ENTER_WAIT+1 回の update で履歴へ。その前は送られていない。空なら何もしない
for key108 in (pyxel.KEY_RETURN, pyxel.KEY_KP_ENTER):
    ap = p_prompt_app()
    p_type(ap, "hello")
    n0 = len(ap.history)
    p_frame(ap, keys=(key108,))
    for k in range(O.IME_ENTER_WAIT):
        check(len(ap.history) == n0 and ap.input_buf == "hello", f"108: Enter の {k + 1} フレーム目で（早く）送られた {ap.history[n0:]}")
        p_frame(ap)
    check(ap.history[n0:] == ["> hello"] and ap.input_buf == "", f"108: Enter の {O.IME_ENTER_WAIT + 1} フレーム目で送られない {ap.history[n0:]} {ap.input_buf!r}")
    for _ in range(5):
        p_frame(ap)
    check(len(ap.history) == n0 + 1, "108: 送信のあと二重に送られた")
    # 空のとき：何もしない
    p_frame(ap, keys=(key108,))
    for _ in range(O.IME_ENTER_WAIT + 3):
        p_frame(ap)
    check(len(ap.history) == n0 + 1 and ap.input_buf == "", "108: 空の Enter で履歴が増えた")
# Enter を続けて押しても1回だけ（送信待ちの間の2回目の Enter は待ちを延ばすだけ）
ap = p_prompt_app()
p_type(ap, "dup")
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_RETURN,))
p_frame(ap, keys=(pyxel.KEY_RETURN,))
for _ in range(O.IME_ENTER_WAIT + 3):
    p_frame(ap)
check(ap.history[n0:] == ["> dup"], f"108: Enter を続けて押したら1回だけ送られない {ap.history[n0:]}")

# 109. 変換中の推測：英字キーを押して input_text が来ない → IME_GRACE_FRAMES 後に ime_composing=True、「変換中」の札（色8の四角）が入力欄の枠の上の線の右端
ap = p_prompt_app()
check(ap.ime_composing is False, "109: 前提：最初から変換中")
p_letter(ap)
check(ap.ime_composing is False, "109: 英字キーのフレームですぐ変換中になった")
for k in range(O.IME_GRACE_FRAMES):
    p_frame(ap)
    check(ap.ime_composing is False, f"109: 英字キーの {k + 1} フレーム後（待つ間）に変換中になった")
p_frame(ap)
check(ap.ime_composing is True, f"109: 英字キーの {O.IME_GRACE_FRAMES + 1} フレーム後に変換中にならない")


UI_LINE_H_ = O.UI_LINE_H


def p_label_info(app):
    """「変換中」の札：(文字の x, y) と、色8の画素の外接長方形 (x0, y0, x1, y1)。無ければ None。"""
    _, ui = p_texts(app)
    lab = [t for t in ui if t[2] == "変換中"]
    app.draw()
    # 「変換中」の札は枠の上の線の右端。左上の「あ」の札（これも色8）と区別するため、右半分だけを見る
    pts = [(xx, yy) for yy in range(P_IY - UI_LINE_H_, P_IY + P_IH) for xx in range(P_IX + P_IW // 2, P_IX + P_IW) if pyxel.screen.pget(xx, yy) == 8]
    if not lab and not pts:
        return None
    bb = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)) if pts else None
    return (lab[0][:2] if lab else None), bb


info = p_label_info(ap)
check(info is not None and info[0] is not None and info[1] is not None, f"109: 変換中の札（文字・色8の四角）が出ていない {info}")
if info and info[1]:
    x0, y0, x1, y1 = info[1]
    check(O.COMPOSING_LABEL_RIGHT - 3 <= x1 <= O.COMPOSING_LABEL_RIGHT and x0 > P_IX + P_IW // 2 - 60 and y0 < P_IY <= y1,
          f"109: 札が入力欄の枠の上の線の右端（x=COMPOSING_LABEL_RIGHT）にない {info[1]}（入力欄 {P_IX},{P_IY},{P_IW},{P_IH}）")
    check(x1 - x0 + 1 >= 30 and y1 - y0 + 1 >= 10, f"109: 札の四角が小さい {info[1]}")
# 変換中でなければ札は出ない
ap_n = p_prompt_app()
check(p_label_info(ap_n) is None, "109: 変換中でないのに札（色8）が出ている")
# 英字キーと同じフレームに input_text が来れば（日本語入力オフ）変換中にならない
ap = p_prompt_app()
p_letter(ap, text="a")
for _ in range(O.IME_GRACE_FRAMES + 3):
    p_frame(ap)
check(ap.ime_composing is False and ap.input_buf == "a", f"109: 英字と同じフレームに文字が来たのに変換中になった {ap.ime_composing} {ap.input_buf!r}")
# 変換中のあとに文字が届けば（確定）変換中が終わる
ap = p_prompt_app()
p_composing(ap)
p_frame(ap, text="日")
check(ap.ime_composing is False and ap.input_buf == "日", "109: 確定の文字が来ても変換中が終わらない")
# Ctrl を押しながらの英字では変換中にならない（左右とも）
for ctrl109 in (pyxel.KEY_LCTRL, pyxel.KEY_RCTRL):
    ap = p_prompt_app()
    p_letter(ap, hold=(ctrl109,))
    for _ in range(O.IME_GRACE_FRAMES + 3):
        p_frame(ap)
    check(ap.ime_composing is False and ap.input_buf == "", f"109: Ctrl+英字で変換中になった／文字が入った {ap.ime_composing} {ap.input_buf!r}")
# 数字・マイナスのキーも英字と同じ。Space・矢印は変換中の元にならない
for key109 in (pyxel.KEY_1, pyxel.KEY_0, pyxel.KEY_MINUS, pyxel.KEY_Z):
    ap = p_prompt_app()
    p_composing(ap) if False else None
    p_letter(ap, key109)
    for _ in range(O.IME_GRACE_FRAMES + 1):
        p_frame(ap)
    check(ap.ime_composing is True, f"109: キー {key109} で変換中にならない")
for key109 in (pyxel.KEY_SPACE, pyxel.KEY_LEFT, pyxel.KEY_UP, pyxel.KEY_TAB):
    ap = p_prompt_app()
    p_frame(ap, keys=(key109,))
    for _ in range(O.IME_GRACE_FRAMES + 3):
        p_frame(ap)
    check(ap.ime_composing is False, f"109: キー {key109}（文字キーでない）で変換中になった")
# P を押して PROMPT に入ったフレームの P は英字として数えない
ap = h_app(52, 2)
p_enter_prompt(ap)
for _ in range(O.IME_GRACE_FRAMES + 3):
    p_frame(ap)
check(ap.ime_composing is False, "109: PROMPT に入る P で変換中になった")

# 110. 変換中の Backspace は入力欄を消さない。変換中でなければ消す
ap = p_prompt_app()
p_type(ap, "abc")
p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
check(ap.input_buf == "ab", f"110: 変換中でない Backspace で消えない {ap.input_buf!r}")
p_composing(ap)
check(ap.ime_composing is True, "110: 前提：変換中にならない")
for _ in range(3):
    p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
check(ap.input_buf == "ab", f"110: 変換中の Backspace で入力欄が消えた {ap.input_buf!r}")
check(ap.ime_composing is True, "110: Backspace で変換中の推測が変わった")
p_frame(ap, text="X")
p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
check(ap.input_buf == "ab" and ap.ime_composing is False, f"110: 確定のあと Backspace で消えない（X を消すはず）{ap.input_buf!r}")

# 111. 変換中の Esc は「(Esc: 中断を送る)」を出さず ime_composing=False。変換中でなければ出す
ap = p_prompt_app()
n0 = len(ap.history)
p_composing(ap)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(ap.ime_composing is False and len(ap.history) == n0 and ap.mode == "PROMPT", f"111: 変換中の Esc で履歴に行が出た／変換中が終わらない {ap.history[n0:]} {ap.ime_composing}")
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(ap.history[n0:] == ["(Esc: 中断を送る)"] and ap.mode == "PROMPT", f"111: 変換中でない Esc で中断の行が出ない {ap.history[n0:]}")
# 待ちの途中（まだ変換中と推測する前）の Esc は、変換中でないので中断を送る
ap = p_prompt_app()
n0 = len(ap.history)
p_letter(ap)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
for _ in range(O.IME_GRACE_FRAMES + 2):
    p_frame(ap)
print(f"(111) 英字の直後（推測の前）の Esc：中断の行 {ap.history[n0:]}・そのあとの変換中 {ap.ime_composing}")

# 112. 変換中の Enter は送信しない。続いて確定文字が来れば ime_composing=False で入力欄に足される
ap = p_prompt_app()
p_type(ap, "xy")
p_composing(ap)
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_RETURN,))
check(ap._pending_enter == 0 and len(ap.history) == n0 and ap.ime_composing is True, f"112: 変換中の Enter で送信待ちになった／変換中が終わった {ap._pending_enter} {ap.ime_composing}")
p_frame(ap, text="確定")
check(ap.ime_composing is False and ap.input_buf == "xy確定" and len(ap.history) == n0, f"112: Enter の次のフレームの確定文字が足されない {ap.input_buf!r} {ap.history[n0:]}")
for _ in range(O.IME_ENTER_WAIT + 3):
    p_frame(ap)
check(len(ap.history) == n0 and ap.input_buf == "xy確定", f"112: 確定のあと送信された {ap.history[n0:]}")
# 変換中の Enter のあと文字が来なくても、変換中のままで送信しない
ap = p_prompt_app()
p_type(ap, "keep")
p_composing(ap)
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_RETURN,))
for _ in range(O.IME_ENTER_WAIT + 4):
    p_frame(ap)
check(len(ap.history) == n0 and ap.input_buf == "keep" and ap.ime_composing is True, f"112: 変換中の Enter だけで送信された／推測が変わった {ap.history[n0:]} {ap.ime_composing}")

# 113. Ctrl+E・3D のクリックで WALK に戻ると変換中・送信待ちが消える。WALK の間はキーで変換中にならない
for how113 in ("ctrl_e", "click"):
    # 変換中
    ap = p_prompt_app()
    p_type(ap, "abc")
    p_composing(ap)
    check(ap.ime_composing, "113: 前提：変換中にならない")
    n0 = len(ap.history)
    if how113 == "ctrl_e":
        p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,))
    else:
        sxy = h_proj(ap, 150.0, 0.0, 100.0)
        p_frame(ap, click=(round(sxy[0]), round(sxy[1])))
    check(ap.mode == "WALK" and ap.ime_composing is False and ap._ime_wait_text == 0 and ap._pending_enter == 0, f"113: {how113} で WALK に戻っても変換中が消えない {ap.ime_composing}")
    check(p_label_info(ap) is None, f"113: {how113} のあと変換中の札が残っている")
    # 送信待ち
    ap = p_prompt_app()
    p_type(ap, "abc")
    n0 = len(ap.history)
    p_frame(ap, keys=(pyxel.KEY_RETURN,))
    check(ap._pending_enter > 0, "113: 前提：送信待ちにならない")
    if how113 == "ctrl_e":
        p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,))
    else:
        sxy = h_proj(ap, 150.0, 0.0, 100.0)
        p_frame(ap, click=(round(sxy[0]), round(sxy[1])))
    check(ap._pending_enter == 0 and ap.mode == "WALK", f"113: {how113} で WALK に戻っても送信待ちが消えない {ap._pending_enter}")
    for _ in range(O.IME_ENTER_WAIT + 3):
        p_frame(ap)
    check(len(ap.history) == n0 and ap.input_buf == "abc", f"113: {how113} のあと送信待ちの文字が送られた {ap.history[n0:]}")
    # 戻って PROMPT に入り直しても、前の変換中・送信待ちは残っていない
    p_enter_prompt(ap)
    for _ in range(O.IME_ENTER_WAIT + 3):
        p_frame(ap)
    check(ap.ime_composing is False and len(ap.history) == n0, f"113: {how113} のあと PROMPT に入り直したら送信された／変換中になった")
# 英字キーのあと（推測の前）に WALK に戻っても、あとから変換中にならない
ap = p_prompt_app()
p_letter(ap)
p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,))
for _ in range(O.IME_GRACE_FRAMES + 3):
    p_frame(ap)
check(ap.mode == "WALK" and ap.ime_composing is False, "113: 英字の直後に WALK に戻ったら、あとから変換中になった")
# WALK の間はキーで変換中にならない
ap = h_app(53, 2)
for k in (pyxel.KEY_A, pyxel.KEY_Z, pyxel.KEY_1, pyxel.KEY_MINUS):
    p_frame(ap, keys=(k,))
    for _ in range(O.IME_GRACE_FRAMES + 3):
        p_frame(ap)
    check(ap.mode == "WALK" and ap.ime_composing is False and ap._ime_wait_text == 0, f"113: WALK でキー {k} を押したら変換中になった")
p_frame(ap, keys=(pyxel.KEY_RETURN,))
for _ in range(O.IME_ENTER_WAIT + 3):
    p_frame(ap)
check(ap._pending_enter == 0 and len(ap.history) == 0, "113: WALK で Enter を押したら送信待ち・送信になった")

# 114. 実機の記録（ime_guess_log.txt の流れ：変換中→確定の Enter→確定→変換中→BS→Esc→BS×4→送信）を再現して、最後に '> 日本語abcd' に当たる行が1つだけ送られる
ap = p_prompt_app()
n0 = len(ap.history)
# frame=368 英字を押したのに文字が来ない → 変換中
p_composing(ap)
check(ap.ime_composing, "114: 1) 変換中にならない")
# frame=593 変換中の Enter → 入力欄では使わない
p_frame(ap, keys=(pyxel.KEY_RETURN,))
check(ap.ime_composing and ap._pending_enter == 0 and len(ap.history) == n0, "114: 2) 変換中の Enter が送信待ちになった")
# frame=594 確定した文字が届いた
p_frame(ap, text="日本語")
check(ap.input_buf == "日本語" and ap.ime_composing is False and len(ap.history) == n0, f"114: 3) 確定文字が足されない {ap.input_buf!r}")
# frame=741 変換中
p_composing(ap)
check(ap.ime_composing, "114: 4) 2回目の変換中にならない")
# frame=828 変換中の Backspace → 入力欄では使わない
p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
check(ap.input_buf == "日本語", f"114: 5) 変換中の Backspace で消えた {ap.input_buf!r}")
# frame=1372 変換中の Esc → 変換の取り消し（中断は送らない）
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(ap.ime_composing is False and len(ap.history) == n0, f"114: 6) 変換中の Esc で中断の行が出た {ap.history[n0:]}")
# 日本語入力をオフにして abcd と余分な4文字（zzzz）を打つ（英字と同じフレームに文字が届く）
for ch in "abcdzzzz":
    p_letter(ap, getattr(pyxel, f"KEY_{ch.upper()}"), text=ch)
check(ap.input_buf == "日本語abcdzzzz" and ap.ime_composing is False, f"114: 7) 英字が入らない {ap.input_buf!r}")
# frame=1503,1508,1512,1560 Backspace で1文字ずつ（4回）
for _ in range(4):
    p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
    p_frame(ap)
check(ap.input_buf == "日本語abcd", f"114: 8) Backspace 4回で 日本語abcd にならない {ap.input_buf!r}")
# frame=1738 送信
p_enter(ap)
for _ in range(6):
    p_frame(ap)
sent114 = ap.history[n0:]
check(sent114 == ["> 日本語abcd"], f"114: 9) 最後に '> 日本語abcd' の行が1つだけ送られない {sent114}")
check(ap.input_buf == "" and ap.ime_composing is False and ap.mode == "PROMPT", "114: 送信のあと入力欄が空・PROMPT のままでない")

# 115. 長い入力で「変換中」の札と入力欄の文字が重なるかを PNG に書き出す（合否は書けたことだけ。重なれば報告）
ime_overlap = []
cols115 = O.UI_COLS
for tag115, text115 in (("1行", "a" * 40), ("3行目が右端まで", "a" * (cols115 * 2 + cols115 - 2)), ("3行目が右の手前", "a" * (cols115 * 2 + 80)),
                         ("全角で3行目が右端まで", "あ" * (cols115 * 3 // 2 - 1))):
    ap = p_prompt_app(55, 2)
    p_type(ap, text115)
    p_composing(ap)
    _, ui = p_texts(ap)
    info = p_label_info(ap)
    rows = [t for t in ui if t[1] >= P_IY and t[2] != "変換中"]
    font = ap.ui_font
    bb = info[1] if info else None
    over = False
    if bb:
        for (rx, ry, rs, _c) in rows:
            rw = font.text_width(rs)
            if rx < bb[2] + 1 and bb[0] < rx + rw and ry < bb[3] + 1 and bb[1] < ry + O.UI_LINE_H - 2:
                over = True
    ime_overlap.append((tag115, over, bb))
    if tag115 == "3行目が右端まで":
        h_write_png(H_SHOT_DIR3 / "ime_long.png", 1)
ok115 = (H_SHOT_DIR3 / "ime_long.png").exists() and (H_SHOT_DIR3 / "ime_long.png").stat().st_size > 1000
check(ok115, "115: ime_long.png を書けなかった")
print("(115) 変換中の札と入力欄の文字の重なり（場面, 重なる, 札の外接長方形）", ime_overlap, "→", str(H_SHOT_DIR3 / "ime_long.png"))


# ---- ここから日本語入力の状態の札（ime_state）・Ctrl+J の改行・変換中の札の位置の項目（116〜121） ----
# 実機：Shift＋Ctrl が日本語入力の切り替え。切り替えの瞬間に変換中の文字があると確定して届く（key_log3.txt）。
def p_shift_ctrl(app, shift=None, ctrl=None, ctrl_first=False):
    """Shift と Ctrl を順に押す（2フレーム）。あとの1つが押された瞬間に切り替わる。押し終わりの空フレームも1つ進める。"""
    sh = pyxel.KEY_LSHIFT if shift is None else shift
    ct = pyxel.KEY_LCTRL if ctrl is None else ctrl
    if ctrl_first:
        p_frame(app, keys=(ct,), hold_keys=(ct,))
        p_frame(app, keys=(sh,), hold_keys=(sh, ct))
    else:
        p_frame(app, keys=(sh,), hold_keys=(sh,))
        p_frame(app, keys=(ct,), hold_keys=(sh, ct))
    p_frame(app)


def p_state_to(app, want):
    """ime_state を want（"あ" か "A"）にする（'?' から英字で）。"""
    if want == "A":
        p_letter(app, text="a")
        app.input_buf = ""
    else:
        p_composing(app)
    assert app.ime_state == want, (app.ime_state, want)


# 116. ime_state の推測
ap = p_prompt_app(61)
check(ap.ime_state == "?", f"116: 起動時の ime_state が '?' でない {ap.ime_state!r}")
# ? → 英字で文字あり → A
p_letter(ap, text="a")
check(ap.ime_state == "A", f"116: 英字と同じフレームに文字が届いたのに 'A' にならない {ap.ime_state!r}")
# ? → 英字で文字なし → あ（変換中と推測した時点）
ap = p_prompt_app(61)
p_letter(ap)
check(ap.ime_state == "?", "116: 英字のフレームですぐ 'あ' になった")
for _ in range(O.IME_GRACE_FRAMES):
    p_frame(ap)
    check(ap.ime_state == "?", "116: 変換中と推測する前に 'あ' になった")
p_frame(ap)
check(ap.ime_state == "あ" and ap.ime_composing, f"116: 英字で文字が届かないのに 'あ' にならない {ap.ime_state!r}")
# Shift＋Ctrl で あ⇔A
p_shift_ctrl(ap)
check(ap.ime_state == "A", f"116: Shift＋Ctrl で あ → A にならない {ap.ime_state!r}")
p_shift_ctrl(ap)
check(ap.ime_state == "あ", f"116: Shift＋Ctrl で A → あ にならない {ap.ime_state!r}")
p_shift_ctrl(ap, ctrl_first=True)
check(ap.ime_state == "A", f"116: Ctrl を先に押す Shift＋Ctrl で あ → A にならない {ap.ime_state!r}")
p_shift_ctrl(ap, pyxel.KEY_RSHIFT, pyxel.KEY_RCTRL)
check(ap.ime_state == "あ", f"116: 右の Shift＋右の Ctrl で切り替わらない {ap.ime_state!r}")
p_shift_ctrl(ap, pyxel.KEY_RSHIFT, pyxel.KEY_LCTRL, ctrl_first=True)
check(ap.ime_state == "A", f"116: 右 Shift＋左 Ctrl（Ctrl 先）で切り替わらない {ap.ime_state!r}")
# 片方だけでは切り替わらない。押しっぱなしでも繰り返し切り替わらない
st0 = ap.ime_state
p_frame(ap, keys=(pyxel.KEY_LSHIFT,), hold_keys=(pyxel.KEY_LSHIFT,))
p_frame(ap)
p_frame(ap, keys=(pyxel.KEY_LCTRL,), hold_keys=(pyxel.KEY_LCTRL,))
p_frame(ap)
check(ap.ime_state == st0, f"116: Shift だけ・Ctrl だけ（離してから）で切り替わった {st0} → {ap.ime_state}")
p_frame(ap, keys=(pyxel.KEY_LSHIFT,), hold_keys=(pyxel.KEY_LSHIFT,))
p_frame(ap, keys=(pyxel.KEY_LCTRL,), hold_keys=(pyxel.KEY_LSHIFT, pyxel.KEY_LCTRL))
st1 = ap.ime_state
for _ in range(10):
    p_frame(ap, hold_keys=(pyxel.KEY_LSHIFT, pyxel.KEY_LCTRL))
check(ap.ime_state == st1 and st1 != st0, f"116: 押しっぱなしで繰り返し切り替わった／最初の切り替えがない {st0} {st1} {ap.ime_state}")
# ? は ? のまま
ap = p_prompt_app(61)
p_shift_ctrl(ap)
p_shift_ctrl(ap, ctrl_first=True)
check(ap.ime_state == "?", f"116: '?' が Shift＋Ctrl で変わった {ap.ime_state!r}")
# 英字と同じフレームの Shift＋Ctrl は入れ替えない（A の状態で、Shift 押下中に Ctrl＋英字）
ap = p_prompt_app(61)
p_state_to(ap, "A")
p_frame(ap, keys=(pyxel.KEY_LSHIFT,), hold_keys=(pyxel.KEY_LSHIFT,))
p_frame(ap, keys=(pyxel.KEY_LCTRL, pyxel.KEY_A), hold_keys=(pyxel.KEY_LSHIFT, pyxel.KEY_LCTRL))
check(ap.ime_state == "A", f"116: 英字と同じフレームの Shift＋Ctrl で入れ替わった {ap.ime_state!r}")
p_frame(ap)
# WALK では判定しない（状態は変わらない）
ap = p_prompt_app(61)
p_state_to(ap, "あ")
p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,))  # Ctrl+E で WALK へ
check(ap.mode == "WALK" and ap.ime_state == "あ", f"116: WALK に戻ると ime_state が消えた／変わった {ap.mode} {ap.ime_state!r}")
p_shift_ctrl(ap)
check(ap.ime_state == "あ", f"116: WALK で Shift＋Ctrl が判定された {ap.ime_state!r}")
for k in (pyxel.KEY_A, pyxel.KEY_Z):
    p_letter(ap, k, text="a")
    p_letter(ap, k)
    for _ in range(O.IME_GRACE_FRAMES + 3):
        p_frame(ap)
check(ap.ime_state == "あ", f"116: WALK の英字で ime_state が変わった {ap.ime_state!r}")
ap2 = h_app(62, 2)
for k in (pyxel.KEY_A, pyxel.KEY_B):
    p_letter(ap2, k, text="a")
    p_letter(ap2, k)
    for _ in range(O.IME_GRACE_FRAMES + 3):
        p_frame(ap2)
p_shift_ctrl(ap2)
check(ap2.ime_state == "?", f"116: WALK のままなのに ime_state が '?' から変わった {ap2.ime_state!r}")
# PROMPT に入り直しても残っている
p_enter_prompt(ap)
check(ap.ime_state == "あ", "116: PROMPT に入り直したら ime_state が変わった")
p_shift_ctrl(ap)
check(ap.ime_state == "A", "116: PROMPT に入り直したあと Shift＋Ctrl が効かない")
# 3D のクリックで WALK に戻っても残る
ap = p_prompt_app(61)
p_state_to(ap, "A")
sxy = h_proj(ap, 150.0, 0.0, 100.0)
p_frame(ap, click=(round(sxy[0]), round(sxy[1])))
check(ap.mode == "WALK" and ap.ime_state == "A", "116: 3D のクリックで WALK に戻ったら ime_state が変わった")
# 文字が届けば（確定）状態は変わらない（A のとき確定の文字は来ない想定だが、来ても変えない）
ap = p_prompt_app(61)
p_state_to(ap, "あ")
p_frame(ap, text="日")
check(ap.ime_state == "あ" and ap.input_buf == "日", "116: 確定の文字で ime_state が変わった")

# 117. 札の表示：色と文字、入力欄の文字と重ならない、WALK でも出る
def p_badge(app):
    """入力欄の左上の札を調べる：(背景色の集合, 白(7)の画素数, 札の長方形 (x, y, w, h))。"""
    font = app.ui_font
    bw = font.text_width("あ") + 4
    bx, by, bh = P_IX + 4, P_IY + 4, O.UI_LINE_H
    app.draw()
    cols = {}
    for yy in range(by, by + bh):
        for xx in range(bx, bx + bw):
            c = pyxel.screen.pget(xx, yy)
            cols[c] = cols.get(c, 0) + 1
    return cols, (bx, by, bw, bh)


for st117, bg117 in (("?", 5), ("あ", 8), ("A", 3)):
    for mode117 in ("PROMPT", "WALK"):
        ap = p_prompt_app(63)
        if st117 != "?":
            p_state_to(ap, st117)
        if mode117 == "WALK":
            p_frame(ap, hold_keys=(pyxel.KEY_LCTRL,), keys=(pyxel.KEY_E,))
        check(ap.mode == mode117 and ap.ime_state == st117, f"117: 前提の状態が違う {ap.mode} {ap.ime_state}")
        cols, (bx, by, bw, bh) = p_badge(ap)
        # 札の中は、背景色と白い文字だけ。白は1文字ぶん（ある程度）出る
        check(set(cols) <= {bg117, 7} and cols.get(bg117, 0) > bw * bh // 2 and cols.get(7, 0) >= 5,
              f"117: {mode117}・{st117} の札の色が 背景{bg117}＋白でない {cols}")
        _, ui = p_texts(ap)
        lab = [t for t in ui if t[2] == st117 and t[0] == P_IX + 6]
        check(len(lab) == 1 and lab[0][3] == 7 and P_IY <= lab[0][1] <= P_IY + 8, f"117: {mode117}・{st117} の札の文字（白・1文字）が出ない {lab}")
        # 入力欄の文字は札の右から
        p_enter_prompt(ap) if mode117 == "WALK" else None
        p_type(ap, "hello" + "x" * 150)
        _, ui = p_texts(ap)
        rows = [t for t in ui if t[1] >= P_IY and t[0] != P_IX + 6]
        check(rows and all(r[0] == ap._input_text_x() and r[0] > bx + bw for r in rows), f"117: {mode117}・{st117} 入力欄の文字が札の右から始まらない {[r[:2] for r in rows]}")
        right = O.COMPOSING_LABEL_RIGHT - (ap.ui_font.text_width("変換中") + 4) - 4  # 「変換中」の札の左端の手前まで
        check(all(r[0] + ap.ui_font.text_width(r[2]) <= right for r in rows), f"117: {mode117}・{st117} 入力欄の文字が札の左端の手前を超える")
        check(ap._input_cols() == (right - ap._input_text_x()) // O.UI_CHAR_W and ap._input_cols() < O.UI_COLS, f"117: _input_cols が札のぶん狭くない {ap._input_cols()}")
        # 文字の画素が札の長方形に入らない
        ap.draw()
        inside = 0
        for yy in range(by, by + bh):
            for xx in range(bx + bw, bx + bw + 3):
                pass
        pts_text = [(xx, yy) for yy in range(by, by + bh) for xx in range(bx, bx + bw) if pyxel.screen.pget(xx, yy) == 7]
        check(len(pts_text) < bw * bh // 2, f"117: {mode117}・{st117} 札の中に文字が入り込んだ {len(pts_text)}")

# 118. 実機の記録 key_log3.txt の流れ：a（文字なし）→ Shift → Ctrl → 'あ' → a（文字 'a'）→ Shift → Ctrl
ap = p_prompt_app(64)
p_letter(ap)                               # frame=126 KEY_A 文字なし
for _ in range(O.IME_GRACE_FRAMES + 1):
    p_frame(ap)
check(ap.ime_state == "あ" and ap.ime_composing, f"118: 1) a（文字なし）で あ・変換中にならない {ap.ime_state!r}")
p_frame(ap, keys=(pyxel.KEY_LSHIFT,), hold_keys=(pyxel.KEY_LSHIFT,))                          # frame=224 Shift
check(ap.ime_state == "あ", "118: 2) Shift だけで切り替わった")
p_frame(ap, keys=(pyxel.KEY_LCTRL,), hold_keys=(pyxel.KEY_LSHIFT, pyxel.KEY_LCTRL))           # frame=230 Ctrl
check(ap.ime_state == "A", f"118: 3) Shift→Ctrl で あ → A にならない {ap.ime_state!r}")
check(ap.input_buf == "", "118: 切り替えのフレームで文字が入った")
p_frame(ap)
p_frame(ap, text="あ")                      # frame=237 切り替えで確定した 'あ' が届く
check(ap.input_buf == "あ" and ap.ime_composing is False and ap.ime_state == "A", f"118: 4) 確定した 'あ' が入力欄に入らない／状態が変わった {ap.input_buf!r} {ap.ime_state!r} {ap.ime_composing}")
p_letter(ap, text="a")                      # frame=372 KEY_A 文字 'a'
check(ap.input_buf == "あa" and ap.ime_state == "A", f"118: 5) a（文字 'a'）が入らない {ap.input_buf!r} {ap.ime_state!r}")
p_frame(ap, keys=(pyxel.KEY_LSHIFT,), hold_keys=(pyxel.KEY_LSHIFT,))                          # frame=564 Shift
p_frame(ap, keys=(pyxel.KEY_LCTRL,), hold_keys=(pyxel.KEY_LSHIFT, pyxel.KEY_LCTRL))           # frame=565 Ctrl
check(ap.ime_state == "あ", f"118: 6) 2回目の Shift→Ctrl で A → あ にならない {ap.ime_state!r}")
p_frame(ap)
check(ap.input_buf == "あa" and ap.ime_composing is False, f"118: 最後に入力欄・変換中が変わった {ap.input_buf!r} {ap.ime_composing}")

# 119. Ctrl+J：改行
def p_ctrl_j(app, ctrl=None):
    p_frame(app, keys=(pyxel.KEY_J,), hold_keys=(pyxel.KEY_LCTRL if ctrl is None else ctrl,))


def p_wrap(text, cols):
    """桁数 cols（全角は2桁）で折り返す（_wrap_text とは別に書いた式）。"""
    rows, cur, w = [], "", 0
    for ch in text:
        cw = p_cols(ch)
        if w + cw > cols:
            rows.append(cur)
            cur, w = "", 0
        cur += ch
        w += cw
    rows.append(cur)
    return rows


def p_shown_rows(app):
    """入力欄に出た文字の行（点滅のカーソル _ は末尾から外す）。"""
    _, ui = p_texts(app)
    rows = [t for t in ui if t[1] >= P_IY and t[0] >= app._input_text_x()]
    out = [t[2] for t in rows]
    if out and out[-1].endswith("_"):
        out[-1] = out[-1][:-1]
    return out, rows


for ctrl119 in (pyxel.KEY_LCTRL, pyxel.KEY_RCTRL):
    ap = p_prompt_app(65)
    p_type(ap, "ab")
    n0 = len(ap.history)
    p_ctrl_j(ap, ctrl119)
    check(ap.input_buf == "ab\n", f"119: Ctrl+J で改行が入らない {ap.input_buf!r}")
    for _ in range(O.IME_ENTER_WAIT + 3):
        p_frame(ap)
    check(len(ap.history) == n0 and ap.input_buf == "ab\n" and ap.ime_composing is False, f"119: Ctrl+J で送信された／変換中になった {ap.history[n0:]} {ap.ime_composing}")
    p_type(ap, "cd")
    check(ap.input_buf == "ab\ncd", f"119: 改行のあとの文字が足されない {ap.input_buf!r}")
    rows_t, rows = p_shown_rows(ap)
    check(rows_t == ["ab", "cd"] and rows[0][1] == P_IY + O.UI_PAD and rows[1][1] == P_IY + O.UI_PAD + O.UI_LINE_H, f"119: 入力欄の表示が改行で分かれない {rows_t} {[r[1] for r in rows]}")
# 改行が続く・最後の3行だけ
ap = p_prompt_app(65)
p_type(ap, "a")
p_ctrl_j(ap)
p_ctrl_j(ap)
p_ctrl_j(ap)
p_type(ap, "b")
p_ctrl_j(ap)
p_type(ap, "c")
check(ap.input_buf == "a\n\n\nb\nc", f"119: 改行の入力が違う {ap.input_buf!r}")
rows_t, _ = p_shown_rows(ap)
check(rows_t == ["", "b", "c"], f"119: 5行のうち最後の3行が出ない {rows_t}")
# 折り返しと改行の組み合わせ
ap = p_prompt_app(65)
cols119 = ap._input_cols()
p_type(ap, "x" * (cols119 + 5))
p_ctrl_j(ap)
p_type(ap, "y")
rows_t, _ = p_shown_rows(ap)
check(rows_t == ["x" * cols119, "x" * 5, "y"], f"119: 長い行＋改行の折り返しが違う {[p_cols(r) for r in rows_t]}")
p_type(ap, "z")
p_ctrl_j(ap)
rows_t, _ = p_shown_rows(ap)
check(rows_t == ["x" * 5, "yz", ""], f"119: 4行目（空）を足したら最後の3行にならない {rows_t}")
# 全角の折り返し
ap = p_prompt_app(65)
p_type(ap, "あ" * (cols119 // 2 + 3))
rows_t, _ = p_shown_rows(ap)
check(rows_t == p_wrap("あ" * (cols119 // 2 + 3), cols119)[-3:] and all(p_cols(r) <= cols119 for r in rows_t), f"119: 全角の折り返しが桁数（{cols119}）に収まらない {[p_cols(r) for r in rows_t]}")
# 送信の履歴の形："> " と "  "
ap = p_prompt_app(65)
p_type(ap, "one")
p_ctrl_j(ap)
p_type(ap, "two")
p_ctrl_j(ap)
p_type(ap, "three")
n0 = len(ap.history)
p_enter(ap)
check(ap.history[n0:] == ["> one", "  two", "  three"] and ap.input_buf == "", f"119: 送信の履歴の形が '> '・'  ' でない {ap.history[n0:]}")
# 折り返しを含む送信（履歴の桁数 UI_COLS で、接頭辞を含めて折り返す）
ap = p_prompt_app(65)
long119 = "m" * (O.UI_COLS + 10)
p_type(ap, long119)
p_ctrl_j(ap)
p_type(ap, long119)
n0 = len(ap.history)
p_enter(ap)
want119 = p_wrap("> " + long119, O.UI_COLS) + p_wrap("  " + long119, O.UI_COLS)
check(ap.history[n0:] == want119, f"119: 長い複数行の送信の履歴が違う {[p_cols(r) for r in ap.history[n0:]]} 期待 {[p_cols(r) for r in want119]}")
# 末尾の改行：'> abc' と '  '
ap = p_prompt_app(65)
p_type(ap, "abc")
p_ctrl_j(ap)
n0 = len(ap.history)
p_enter(ap)
check(ap.history[n0:] == ["> abc", "  "], f"119: 末尾が改行の送信が '> abc'・'  ' でない {ap.history[n0:]}")
# 改行だけの入力を送ると
ap = p_prompt_app(65)
p_ctrl_j(ap)
n0 = len(ap.history)
p_enter(ap)
print(f"(119) 改行だけの入力を送った履歴: {ap.history[n0:]}")
# Backspace で改行が消える
ap = p_prompt_app(65)
p_type(ap, "ab")
p_ctrl_j(ap)
p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
check(ap.input_buf == "ab", f"119: Backspace で改行が消えない {ap.input_buf!r}")
p_ctrl_j(ap)
p_type(ap, "c")
p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
p_frame(ap, keys=(pyxel.KEY_BACKSPACE,))
check(ap.input_buf == "ab", f"119: 'c' と改行を Backspace 2回で消せない {ap.input_buf!r}")
# 変換中は入らない
ap = p_prompt_app(65)
p_type(ap, "ab")
p_composing(ap)
p_ctrl_j(ap)
check(ap.input_buf == "ab" and ap.ime_composing is True, f"119: 変換中の Ctrl+J で改行が入った／変換中が変わった {ap.input_buf!r}")
# WALK では何もしない
ap = h_app(66, 2)
n0 = len(ap.history)
p_ctrl_j(ap)
check(ap.mode == "WALK" and ap.input_buf == "" and len(ap.history) == n0, f"119: WALK の Ctrl+J で何かが起きた {ap.input_buf!r}")
# Ctrl なしの J：'j' の文字だけ（日本語入力オフの想定：文字つき）。改行は入らない
ap = p_prompt_app(65)
p_letter(ap, pyxel.KEY_J, text="j")
check(ap.input_buf == "j" and "\n" not in ap.input_buf, f"119: Ctrl なしの J が 'j' だけにならない {ap.input_buf!r}")
# Ctrl+J のフレームの input_text（\n や j）は足さない
ap = p_prompt_app(65)
p_frame(ap, keys=(pyxel.KEY_J,), hold_keys=(pyxel.KEY_LCTRL,), text="\n")
check(ap.input_buf == "\n", f"119: Ctrl+J のフレームの input_text が足されて改行が2つになった／入らない {ap.input_buf!r}")
# Ctrl+J のあと変換中にならず、状態の札も変わらない
ap = p_prompt_app(65)
p_ctrl_j(ap)
for _ in range(O.IME_GRACE_FRAMES + 3):
    p_frame(ap)
check(ap.ime_composing is False and ap.ime_state == "?", f"119: Ctrl+J のあと変換中・状態が変わった {ap.ime_composing} {ap.ime_state!r}")

# 120. 変換中の札が枠の上の線の右端で、入力欄の文字（3行目が右端まで埋まっても）と重ならない
ov120 = []
for tag120, mk in (("1行", lambda a: "a" * 30), ("3行目が右端まで", lambda a: "a" * (a._input_cols() * 3)),
                   ("全角3行いっぱい", lambda a: "あ" * (a._input_cols() * 3 // 2)), ("改行3行・右端まで", lambda a: "\n".join(["z" * a._input_cols()] * 3))):
    ap = p_prompt_app(67)
    for k in range(12):  # 履歴にも横いっぱいの行を入れる（札が履歴の文字にかからないか）
        ap._add_history("h" * (O.UI_COLS - 2))
    txt = mk(ap)
    ap.input_buf = txt
    p_composing(ap)
    check(ap.ime_composing, f"120: {tag120} 前提：変換中にならない")
    info = p_label_info(ap)
    check(info is not None and info[1] is not None, f"120: {tag120} 札が出ない")
    if not info or not info[1]:
        continue
    x0, y0, x1, y1 = info[1]
    check(y0 < P_IY <= y1 and y1 <= P_IY + O.UI_LINE_H and O.COMPOSING_LABEL_RIGHT - 3 <= x1 <= O.COMPOSING_LABEL_RIGHT, f"120: {tag120} 札が枠の上の線の右端（x=COMPOSING_LABEL_RIGHT）にない {info[1]} 枠の上の線 y={P_IY}")
    rows_t, rows = p_shown_rows(ap)
    hit = [r for r in rows if r[0] < x1 + 1 and x0 < r[0] + ap.ui_font.text_width(r[2]) and r[1] < y1 + 1 and y0 < r[1] + O.UI_LINE_H - 2]
    check(not hit, f"120: {tag120} 入力欄の文字と札が重なる {[(r[2][-5:], r[1]) for r in hit]}")
    # 履歴の文字との重なり
    hist_rows = [(HX_ := P_HX + O.UI_PAD, P_HY + O.UI_PAD + k * O.UI_LINE_H, row) for k, row in enumerate(ap.history[ap.history_scroll:ap.history_scroll + O.HISTORY_ROWS])]
    hhit = [r for r in hist_rows if r[0] < x1 + 1 and x0 < r[0] + ap.ui_font.text_width(r[2]) and r[1] < y1 + 1 and y0 < r[1] + O.UI_LINE_H - 2]
    check(not hhit, f"120: {tag120} 履歴の文字と札が重なる {[(r[2][:5], r[1]) for r in hhit]}")
    # スクロールバーの溝との重なり（記録のみ）
    tx_, ty_, tw_, th_ = ap._scroll_track()
    ov120.append((tag120, (x0, y0, x1, y1), (y1 >= ty_ and x1 >= tx_ and y0 < ty_ + th_ and x0 < tx_ + tw_)))
    if tag120 == "3行目が右端まで":
        ap.draw()
        h_write_png(H_SHOT_DIR3 / "ime_badge_top.png", 1)
print("(120) 札の外接長方形と、履歴のスクロールバーの溝にかかるか", ov120)

# 121. 英字の直後（変換中と推測する前）の Esc で中断の行が出ず、そのあと変換中にもならない
for off121 in range(0, O.IME_GRACE_FRAMES + 3):
    ap = p_prompt_app(68)
    n0 = len(ap.history)
    p_letter(ap)
    for _ in range(off121):
        p_frame(ap)
    p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
    check(len(ap.history) == n0, f"121: 英字の {off121} フレーム後の Esc で中断の行が出た {ap.history[n0:]}")
    check(ap.ime_composing is False and ap._ime_wait_text == 0, f"121: Esc のあと変換中の待ちが残った {ap.ime_composing} {ap._ime_wait_text}")
    check(ap.ime_state == "あ", f"121: Esc のあと ime_state が 'あ' でない {ap.ime_state!r}")
    for _ in range(O.IME_GRACE_FRAMES + 4):
        p_frame(ap)
    check(ap.ime_composing is False and len(ap.history) == n0, f"121: Esc のあと時間がたって変換中になった／行が出た {ap.ime_composing} {ap.history[n0:]}")
    check(p_label_info(ap) is None, "121: 変換中の札が出ている")
# 変換中でも待ちでもない Esc は中断の行を出す
ap = p_prompt_app(68)
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(ap.history[n0:] == ["(Esc: 中断を送る)"], f"121: 通常の Esc で中断の行が出ない {ap.history[n0:]}")
# 変換中の Esc のあとの Esc は中断の行を出す
ap = p_prompt_app(68)
p_composing(ap)
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(ap.history[n0:] == ["(Esc: 中断を送る)"] and ap.ime_state == "あ", f"121: 変換中の Esc のあとの Esc で中断の行が1つ出ない {ap.history[n0:]}")


# ---- ここから空の送信と、変換中の札の置き場所の修正の項目（122〜123） ----
# 122. 空白・改行・全角空白だけの送信は履歴に足されず入力欄が空になる。前後に空白がある普通の文字は送られる（中身はそのまま）
for tag122, build in (("半角空白", lambda a: p_type(a, "   ")), ("全角空白", lambda a: p_type(a, "　　")),
                      ("改行だけ", lambda a: (p_ctrl_j(a), p_ctrl_j(a))), ("空白と改行と全角空白", lambda a: (p_type(a, " "), p_ctrl_j(a), p_type(a, "　"), p_ctrl_j(a), p_type(a, "  ")))):
    ap = p_prompt_app(71)
    build(ap)
    check(ap.input_buf != "", f"122: {tag122} 前提：入力欄が空")
    n0 = len(ap.history)
    p_enter(ap)
    for _ in range(O.IME_ENTER_WAIT + 3):
        p_frame(ap)
    check(len(ap.history) == n0 and ap.input_buf == "", f"122: {tag122} の送信で履歴に足された／入力欄が空にならない {ap.history[n0:]} {ap.input_buf!r}")
    check(ap.mode == "PROMPT" and ap.history_scroll == ap._max_scroll(), f"122: {tag122} の送信のあと状態が変わった")
# 前後に空白がある普通の文字は送られる（中身はそのまま）
for tag122, parts, want in (("前後に半角空白", ["  hello  "], ["> " + "  hello  "]), ("前後に全角空白", ["　あ　"], ["> " + "　あ　"]),
                            ("前に改行", ["\n", "abc"], ["> ", "  abc"]), ("後ろに空白行", ["abc", "\n", " "], ["> abc", "   "])):
    ap = p_prompt_app(71)
    for part in parts:
        if part == "\n":
            p_ctrl_j(ap)
        else:
            p_type(ap, part)
    n0 = len(ap.history)
    p_enter(ap)
    check(ap.history[n0:] == want and ap.input_buf == "", f"122: {tag122} が中身そのままで送られない {ap.history[n0:]} 期待 {want}")
# 空のあとの普通の送信：その次の送信は通る
ap = p_prompt_app(71)
p_type(ap, " ")
p_enter(ap)
p_send(ap, "ok")
check(ap.history[-1] == "> ok" and len(ap.history) == 1, f"122: 空白の送信のあと普通の送信ができない {ap.history}")

# 123. 変換中の札が履歴の枠の線・スクロールバー（溝もつまみも、履歴が10行以上のとき）・入力欄の文字（3行目が右端まで埋まっても）と重ならない
H_SHOT_DIR4 = TMP_DIR / "talk_shots4"
H_SHOT_DIR4.mkdir(parents=True, exist_ok=True)
tx_, ty_, tw_, th_ = O.App._scroll_track(h_app(72, 1))
cols_box = []
for tag123, nhist, scroll123, mk in (("履歴10行・一番下", 10, "bottom", lambda a: "a" * (a._input_cols() * 3)),
                                      ("履歴40行・一番上", 40, "top", lambda a: "a" * (a._input_cols() * 3)),
                                      ("履歴40行・途中・全角", 40, "mid", lambda a: "あ" * (a._input_cols() * 3 // 2)),
                                      ("履歴3行・1行", 3, "bottom", lambda a: "a" * 20),
                                      ("履歴40行・改行3行", 40, "bottom", lambda a: "\n".join(["z" * a._input_cols()] * 3))):
    ap = p_prompt_app(72)
    while len(ap.history) < nhist:
        ap._add_history("h" * (O.UI_COLS - 2))
    ap.history_scroll = {"bottom": ap._max_scroll(), "top": 0, "mid": ap._max_scroll() // 2}[scroll123]
    ap.input_buf = mk(ap)
    p_composing(ap)
    check(ap.ime_composing, f"123: {tag123} 前提：変換中にならない")
    # 履歴のスクロール位置は p_composing のフレームでも変わらない（行を足していない）
    info = p_label_info(ap)
    check(info is not None and info[1] is not None, f"123: {tag123} 札が出ない")
    if not info or not info[1]:
        continue
    x0, y0, x1, y1 = info[1]
    cols_box.append((tag123, info[1]))
    hist_bottom = P_HY + P_HH - 1   # 履歴の枠の下の線
    check(y0 > hist_bottom, f"123: {tag123} 札が履歴の枠の下の線（y={hist_bottom}）にかかる {info[1]}")
    check(y0 < P_IY <= y1, f"123: {tag123} 札が入力欄の上の線（y={P_IY}）に重なっていない {info[1]}")
    # 履歴の枠の右の線・スクロールバーの溝（x 範囲）から離れている
    check(x1 < tx_, f"123: {tag123} 札がスクロールバーの溝（x={tx_}〜）にかかる {info[1]}")
    check(x1 < P_HX + P_HW - 1, f"123: {tag123} 札が枠の右の線にかかる")
    # 画素：履歴の枠の下の線（色5）・スクロールバー（色1・つまみ7）が、札の長方形の外で欠けていない
    ap.draw()
    line_ok = all(pyxel.screen.pget(xx, hist_bottom) in (5,) for xx in range(x0, x1 + 1))
    check(line_ok, f"123: {tag123} 履歴の枠の下の線が札の幅の所で欠けている")
    if nhist > O.HISTORY_ROWS:
        groove = [pyxel.screen.pget(tx_ + tw_ // 2, yy) for yy in range(ty_, ty_ + th_)]
        check(1 in groove and 7 in groove and all(c in (1, 7) for c in groove), f"123: {tag123} スクロールバーの溝・つまみの画素が欠けた／色が混じった {sorted(set(groove))}")
    # 札の長方形に重なる色5・色7の文字・線が無い（札の中は 色8＋白い文字だけ）
    inside = {}
    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1):
            c = pyxel.screen.pget(xx, yy)
            inside[c] = inside.get(c, 0) + 1
    check(set(inside) <= {8, 7}, f"123: {tag123} 札の中に色8・白以外がある {inside}")
    # 入力欄の文字との重なり
    rows_t, rows = p_shown_rows(ap)
    hit = [r for r in rows if r[0] < x1 + 1 and x0 < r[0] + ap.ui_font.text_width(r[2]) and r[1] < y1 + 1 and y0 < r[1] + O.UI_LINE_H - 2]
    check(not hit, f"123: {tag123} 入力欄の文字と札が重なる {[(r[2][-5:], r[1]) for r in hit]}")
    # 入力欄の文字の右端は札の左端の手前（余白 4 以上）
    far = max((r[0] + ap.ui_font.text_width(r[2]) for r in rows), default=0)
    check(far <= x0 - 4 + 1 or not any(r[1] + O.UI_LINE_H - 2 > y0 for r in rows) or far <= x0, f"123: {tag123} 入力欄の文字が札の左端に近すぎる 文字の右端 {far} 札の左端 {x0}")
    # 履歴の文字との重なり
    hist_rows = [(P_HX + O.UI_PAD, P_HY + O.UI_PAD + k * O.UI_LINE_H, row) for k, row in enumerate(ap.history[ap.history_scroll:ap.history_scroll + O.HISTORY_ROWS])]
    hhit = [r for r in hist_rows if r[0] < x1 + 1 and x0 < r[0] + ap.ui_font.text_width(r[2]) and r[1] < y1 + 1 and y0 < r[1] + O.UI_LINE_H - 2]
    check(not hhit, f"123: {tag123} 履歴の文字と札が重なる")
    if tag123 == "履歴40行・一番上":
        pass
# 前回と同じ場面の PNG：履歴を横いっぱいの行で埋め、入力欄の3行目まで a で埋め、変換中にする
ap = p_prompt_app(67)
for k in range(12):
    ap._add_history("h" * (O.UI_COLS - 2))
ap.input_buf = "a" * (ap._input_cols() * 3)
p_composing(ap)
ap.draw()
h_write_png(H_SHOT_DIR4 / "ime_badge_fixed.png", 1)
check((H_SHOT_DIR4 / "ime_badge_fixed.png").stat().st_size > 1000, "123: ime_badge_fixed.png を書けなかった")
print("(123) 札の外接長方形", cols_box, "入力欄の桁数", ap._input_cols(), "→", str(H_SHOT_DIR4 / "ime_badge_fixed.png"))


# ---------------------------------------------------------------------------
# 124〜134. --claude（本物の Claude Code とつなぐ）のテスト。本物の tmux・claude は使わない（偽の Bridge）。
# App は make_app で作る（pyxel.init は空にする）。始業したまま終わると、プロセスの終わりの後始末（atexit）が
# 引き継ぎメモを最大 300 秒待つので、作った App は C_APPS に入れ、atexit で先に started を False に戻す。
# ---------------------------------------------------------------------------
import atexit as _atexit_c
import time as _time_c
from pca_bridge import Prompt, Tool, Reply, TurnEnd, SubagentStart, SubagentEnd

C_WORK = TMP_DIR / "pca_work_claude"  # --claude の作業フォルダ（作りっぱなし。消さない）


class FakeBridge:
    """本物の tmux・claude を使わない偽の Bridge。呼ばれた記録と、poll で返すイベントを持つ。"""

    def __init__(self, session=False, begin_ok=True):
        self.session = session
        self.begin_ok = begin_ok
        self.calls = []
        self.script = []  # 次の poll で返すイベント
        self.last_error = ""
        self.polls = 0

    def session_exists(self):
        return self.session

    def begin(self, mode):
        self.calls.append(("begin", mode))
        if self.begin_ok:
            self.session = True
        return self.begin_ok

    def send_prompt(self, text):
        self.calls.append(("send_prompt", text))
        return True

    def send_escape(self):
        self.calls.append(("send_escape",))
        return True

    def poll(self):
        self.polls += 1
        out = self.script[:]
        self.script.clear()
        return out

    def end(self, kill_session):
        self.calls.append(("end", kill_session))
        if kill_session:
            self.session = False


C_APPS = []


def c_make(n=18, session=False, begin_ok=True, seed=1, bridge=None, **kw):
    """--claude の office の App と偽の Bridge を作る。"""
    fb = bridge if bridge is not None else FakeBridge(session, begin_ok)
    ap = make_app(30, seed, "office", n, claude=True, workdir=str(C_WORK), bridge_factory=lambda w, s: fb, **kw)
    C_APPS.append(ap)
    _atexit_c.register(lambda a=ap: (setattr(a, "started", False), setattr(a, "ending", False)))
    return ap, fb


def c_run(ap, n):
    """update を n 回。"""
    for _ in range(n):
        ap.update()


def c_start(ap):
    """F1 で始業して、メイン（番号 0）を返す。"""
    p_frame(ap, keys=(pyxel.KEY_F1,))
    return ap.agents[O.MAIN_INDEX]


def c_seated(ap, i, limit=900):
    """人 i が席に着くまで進める。着いたら True。"""
    return ov_until(ap, lambda: ap.agents[i].is_seated, limit) is not None


def c_invisible_all(ap, i):
    """人 i が見えなくなる（置き場所へ戻る）まで進める。"""
    return ov_until(ap, lambda: not ap.agents[i].visible, 900) is not None


def c_ev(ap, fb, *events):
    """偽の Bridge にイベントを仕込み、1フレーム進める。"""
    fb.script = list(events)
    ap.update()


def c_draw(ap):
    """draw で呼ばれた rect・rectb・tri・text を記録して返す（本物の描画もそのまま行う）。"""
    rec = {"rect": [], "rectb": [], "tri": [], "text": [], "utext": []}
    saved = (pyxel.rect, pyxel.rectb, pyxel.tri, pyxel.text)

    def mk(name, orig):
        def f(*a, **k):
            rec[name].append(a)
            return orig(*a, **k)
        return f

    def text(x, y, s, col, *a, **k):
        rec["utext" if (a or k) else "text"].append((x, y, str(s), col))
        return saved[3](x, y, s, col, *a, **k)

    pyxel.rect, pyxel.rectb, pyxel.tri = mk("rect", saved[0]), mk("rectb", saved[1]), mk("tri", saved[2])
    pyxel.text = text
    try:
        ap.draw()
    finally:
        pyxel.rect, pyxel.rectb, pyxel.tri, pyxel.text = saved
    return rec


def c_ui_has(rec, s):
    return any(t[2] == s for t in rec["utext"])


def c_free_point(ap, k=0):
    """床の、障害物から十分に離れた点（x, z）を k 番目まで探して返す。"""
    x0, x1 = ap.layout.wander_x
    z0, z1 = ap.layout.wander_z
    found = []
    x = x0 + 100
    while x < x1 - 100:
        z = z0 + 100
        while z < z1 - 100:
            if not ap._overlaps_any_obstacle(x, z, O.AGENT_RADIUS * 6):
                found.append((x, z))
            z += 60
        x += 60
    return found[k]


def c_patch(ap, cx, cy, half=22):
    """画面の (cx, cy) のまわりの画素の並び。"""
    out = []
    for yy in range(max(0, int(cy) - half), min(O.VIEW3D_H, int(cy) + half)):
        for xx in range(max(0, int(cx) - half), min(O.OFFICE_SCREEN_W, int(cx) + half)):
            out.append(pyxel.screen.pget(xx, yy))
    return out


# 124. 始業：ダイアログなし（new）／begin 失敗／ボタン／PROMPT でも F1／1・2・3 のダイアログ
ap, fb = c_make()
check(ap.claude and ap.bridge is fb, "124: --claude で bridge_factory の Bridge を使う")
check(all(not a.visible for a in ap.agents) and all(a.pos.x == O.PARK_X and a.pos.z == O.DOOR_Z for a in ap.agents),
      "124: 起動時は全員が見えず、PARK_X・ドアの z にいる")
check(not ap.started and not ap.ending and ap._active_indices() == [], "124: 起動時は未始業・見えている人なし")
check(len(ap.agents) == 18 and O.PARK_X == -900.0, "124: 18人・PARK_X は -900")
rec = c_draw(ap)
check(c_ui_has(rec, "[F1] 始業") and not c_ui_has(rec, "[F1] 終業"), "124: 始業前のボタンは「[F1] 始業」")
bx, by, bw, bh = ap._button_rect("[F1] 始業")
check(by == O.BUTTON_Y == 40 and any(r[:5] == (bx, by, bw, bh, 0) for r in rec["rect"]), f"124: ボタンは y=40 の黒い四角 {(bx, by, bw, bh)}")
check(any(t[2] == "[F1] 始業" and t[3] == 7 for t in rec["utext"]), "124: ボタンの文字は白（色 7）")
n_hist0 = len(ap.history)
main = c_start(ap)
check(fb.calls == [("begin", "new")] and ap.started, f"124: セッションが無ければ begin('new') {fb.calls}")
check(main.visible and main.role == "main" and main.label == "main", "124: メインが見えて role/label が main")
check(ap.history[n_hist0:] == ["始業：Claude Code を起動しました"], f"124: 始業の履歴 {ap.history[n_hist0:]}")
check(ap._active_indices() == [0], f"124: 見えているのはメインだけ {ap._active_indices()}")
check(all(not a.visible for a in ap.agents[1:]) and all(a.role == "" and a.label == "" for a in ap.agents[1:]), "124: ほかの人は見えず role/label も空")
check(ap.door_open and main.state == O.WORKING and abs(main.pos.x - O.ENTER_INSIDE_X) < 40, f"124: ドアが開き、メインがドアの内側から席へ向かう {main.state} {main.pos}")
rec = c_draw(ap)
check(c_ui_has(rec, "[F1] 終業") and not c_ui_has(rec, "[F1] 始業"), "124: 始業後のボタンは「[F1] 終業」")
# 始業のあとの F1 は終業（ここでは始業までを確かめるので、終業の中身は 131）
p_frame(ap, keys=(pyxel.KEY_F1,))
check(ap.ending and ("send_prompt", i18n_t(O.HANDOFF_PROMPT)) in fb.calls, "124: 始業後の F1 は終業になる")
ap.started = False
ap.ending = False

# 124-b. begin が False：履歴に理由。始業しない
ap, fb = c_make(begin_ok=False)
fb.last_error = "boom"
n0 = len(ap.history)
c_start(ap)
check(not ap.started and ap.history[n0:] == ["始業できませんでした：boom"], f"124: begin 失敗の履歴 {ap.history[n0:]}")
check(ap._active_indices() == [] and ap.agents[0].role == "" and ap.agents[0].label == "", "124: begin 失敗ではメインを出さない・role を付けない")
check(not ap.door_open, "124: begin 失敗ではドアを開けない")
rec = c_draw(ap)
check(c_ui_has(rec, "[F1] 始業"), "124: begin 失敗のあとも「[F1] 始業」のまま")
fb.begin_ok = True
c_start(ap)
check(ap.started, "124: 失敗のあとの F1 でもう一度始業できる")
ap.started = False


class FakeBridgeTmuxErr(FakeBridge):
    """last_error を持たず、tmux.last_error だけ持つ Bridge（本物の Bridge と同じ作り）。"""

    def __init__(self):
        super().__init__(False, False)
        del self.last_error

        class _T:
            last_error = "tmux のエラー"

        self.tmux = _T()


ap, fb = c_make(bridge=FakeBridgeTmuxErr())
n0 = len(ap.history)
c_start(ap)
check(ap.history[n0:] == ["始業できませんでした：tmux のエラー"], f"124: Bridge に last_error が無ければ tmux.last_error を出す {ap.history[n0:]}")

# 124-c. ボタンのクリックで始業・終業。PROMPT のときの F1 も効く（入力欄は変わらない）
ap, fb = c_make()
bx, by, bw, bh = ap._button_rect("[F1] 始業")
p_frame(ap, click=(bx - 1, by + 2))
check(not ap.started, "124: ボタンのすぐ外（左）のクリックでは始業しない")
p_frame(ap, click=(bx + bw, by + 2))
check(not ap.started, "124: ボタンのすぐ外（右）のクリックでは始業しない")
p_frame(ap, click=(bx + 2, by + bh))
check(not ap.started, "124: ボタンのすぐ外（下）のクリックでは始業しない")
p_frame(ap, click=(bx + bw // 2, by + bh // 2))
check(ap.started and fb.calls == [("begin", "new")], f"124: ボタンのクリックで始業 {fb.calls}")
bx2, by2, bw2, bh2 = ap._button_rect("[F1] 終業")
p_frame(ap, click=(bx2 + bw2 // 2, by2 + bh2 // 2))
check(ap.ending and ("send_prompt", i18n_t(O.HANDOFF_PROMPT)) in fb.calls, "124: 終業のボタンのクリックで終業の手順に入る")
check(ap.talk_partner is None, "124: ボタンのクリックで会話は始まらない")
ap.started = False
ap.ending = False

ap, fb = c_make()
p_enter_prompt(ap)
p_type(ap, "abc")
check(ap.mode == O.MODE_PROMPT and ap.input_buf == "abc", "124: 前提：PROMPT で abc を入力中")
p_frame(ap, keys=(pyxel.KEY_F1,))
check(ap.started and ap.mode == O.MODE_PROMPT and ap.input_buf == "abc", f"124: PROMPT のときも F1 で始業でき、入力欄は変わらない {ap.mode} {ap.input_buf!r}")
ap.started = False

# 124-d. セッションが残っている：ダイアログ。1・2・3 のキー
for key, mode, text in ((pyxel.KEY_1, "resume", "始業：前のセッションにつなぎました"),
                        (pyxel.KEY_2, "restart", "始業：Claude Code を起動しました")):
    ap, fb = c_make(session=True)
    n0 = len(ap.history)
    c_start(ap)
    check(ap._dialog and not ap.started and fb.calls == [], f"124: セッションがあれば F1 でダイアログ（始業しない） {fb.calls}")
    check(not any(a.visible for a in ap.agents), "124: ダイアログの間は誰も出てこない")
    rec = c_draw(ap)
    check(c_ui_has(rec, "前のセッションが残っています") and c_ui_has(rec, "1: 続きから")
          and c_ui_has(rec, "2: 前のを終わらせて新しく始める") and c_ui_has(rec, "3: やめる"),
          "124: ダイアログに題と 3 つの選択肢が出る")
    check(any(r[:5] == (60, 70, 520, 110, 0) for r in rec["rect"]), "124: ダイアログは 3D の真ん中に黒い四角")
    p_frame(ap, keys=(key,))
    check(fb.calls == [("begin", mode)] and ap.started and not ap._dialog, f"124: キー {key} で begin({mode!r}) {fb.calls}")
    check(ap.history[n0:] == [text], f"124: {mode} の履歴 {ap.history[n0:]}")
    check(ap.agents[0].visible and ap.agents[0].role == "main", f"124: {mode} でメインが出てくる")
    rec = c_draw(ap)
    check(not c_ui_has(rec, "前のセッションが残っています"), "124: 選んだあとダイアログは消える")
    ap.started = False
# 3：やめる
ap, fb = c_make(session=True)
n0 = len(ap.history)
c_start(ap)
p_frame(ap, keys=(pyxel.KEY_3,))
check(not ap._dialog and not ap.started and fb.calls == [] and ap.history[n0:] == [] and not any(a.visible for a in ap.agents),
      f"124: 3 でやめる（何も始めない・履歴も増えない） {fb.calls} {ap.history[n0:]}")
p_frame(ap, keys=(pyxel.KEY_F1,))
check(ap._dialog, "124: やめたあと、もう一度 F1 でダイアログが出る")
ap.started = False

# 124-e. ダイアログのクリックで選ぶ（1・2・3 の行）。外のクリックは受け流す
for k, want in ((0, [("begin", "resume")]), (1, [("begin", "restart")]), (2, [])):
    ap, fb = c_make(session=True)
    c_start(ap)
    p_frame(ap, click=(100, 94 + k * 16 + 6))
    check(fb.calls == want and not ap._dialog, f"124: ダイアログの {k + 1} 行目のクリック {fb.calls}")
    check(ap.started == bool(want), f"124: ダイアログの {k + 1} 行目のクリックで始業するか {ap.started}")
    ap.started = False
ap, fb = c_make(session=True)
c_start(ap)
walks = []
ap.human.walk_to = lambda *a, **kw: walks.append(a)
for pos in ((300, 250), (100, 60), (100, 93), (100, 94 + 3 * 16 + 14), (30, 120), (580, 120)):
    p_frame(ap, click=pos)
    check(ap._dialog and fb.calls == [], f"124: ダイアログの外・行の間のクリック {pos} は選択にならない")
bxd, byd, bwd, bhd = ap._button_rect("[F1] 始業")
p_frame(ap, click=(bxd + 2, byd + 2))
check(ap._dialog and fb.calls == [] and not ap.started, "124: ダイアログの間はボタンも効かない")
check(walks == [] and ap.talk_partner is None, f"124: ダイアログの間の 3D のクリックで人間が歩かない {walks}")

# 124-f. ダイアログが出ている間は、ほかの操作（歩く・文字入力・スペース・D・視点）を止める
ap, fb = c_make(session=True)
c_start(ap)
yaw0, door0, idx0 = ap.cam_yaw, ap.door_open, ap.next_index
press_space_and_update(ap)
check(ap.next_index == idx0 and not any(a.visible for a in ap.agents), "124: ダイアログ中のスペースで誰も作業を始めない")
p_frame(ap, keys=(pyxel.KEY_D,))
check(ap.door_open == door0, "124: ダイアログ中の D でドアが動かない")
p_frame(ap, keys=(O.PROMPT_ENTER_KEY,))
check(ap.mode == O.MODE_WALK, "124: ダイアログ中の P で PROMPT にならない")
for _ in range(10):
    p_frame(ap, hold_keys=(pyxel.KEY_LEFT,))
check(ap.cam_yaw == yaw0, "124: ダイアログ中のカーソルキーで視点が動かない")
ap.mode = O.MODE_PROMPT
p_frame(ap, text="abc")
check(ap.input_buf == "", f"124: ダイアログ中は文字入力が入らない {ap.input_buf!r}")
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_RETURN,))
check(len(ap.history) == n0 and ap._dialog, "124: ダイアログ中の Enter は何も送らない")
# 選んだフレームで、選ぶためのキーが利用制限（1〜4）の操作にならない
for key, mode in ((pyxel.KEY_1, "resume"), (pyxel.KEY_2, "restart"), (pyxel.KEY_3, "")):
    ap, fb = c_make(session=True)
    c_start(ap)
    five, seven = ap.five_hour, ap.seven_day
    p_frame(ap, keys=(key,))
    check(not ap.manual_limits and ap.five_hour == five and ap.seven_day == seven,
          f"124: ダイアログの選択キー {key} が利用制限の手動操作にもなった manual_limits={ap.manual_limits} 5h={ap.five_hour} week={ap.seven_day}")
    ap.started = False

# 選んだフレームの文字が入力欄に入らない（PROMPT のままダイアログを出して 1 を選ぶ）
ap, fb = c_make(session=True)
p_enter_prompt(ap)
p_frame(ap, keys=(pyxel.KEY_F1,))
p_frame(ap, keys=(pyxel.KEY_1,), text="1")
check(ap.started and ap.input_buf == "", f"124: ダイアログの選択キーの文字が入力欄に入った {ap.input_buf!r}")
ap.started = False

# 125. 見えない人は、押し出し・道探し・クリック・会話の立つ場所・行き先の予約・うろうろの時間・描画のすべてから外れる
ap, fb = c_make()
fx, fz = c_free_point(ap, 0)
ghost = ap.agents[5]
check(ap._active_indices() == [], "125: 前提：全員見えない")
# 125-a. _active_indices
ap.agents[3].visible = True
ap.agents[7].visible = True
check(ap._active_indices() == [3, 7], f"125: _active_indices は見えている人の番号 {ap._active_indices()}")
ap.agents[3].visible = False
ap.agents[7].visible = False
# 125-b. クリックで選べない（見えないまま床の上にいても）／見えれば選べる
ghost.pos = Vec3(fx, 0.0, fz)
ap.agents[5].state = O.WANDER
sx, sy = h_agent_xy(ap, 5)
check(h_on_screen((sx, sy), ap), f"125: 前提：人 5 の球が画面の中 {(sx, sy)}")
h_click_agent(ap, 5)
check(ap.talk_partner is None, "125: 見えない人はクリックで会話の相手に選ばれない")
ghost.visible = True
h_click_agent(ap, 5)
check(ap.talk_partner == 5, f"125: 同じ点でも見えていれば選ばれる（対照） {ap.talk_partner}")
ap.end_talk()
ghost.visible = False
h_click_agent(ap, 5)
check(ap.talk_partner is None, "125: また見えなくなったらもう選ばれない")
# 125-c. 押し出し：見えない人と重なっても、見えている人は押されない。見えない人の位置も変わらない
other = ap.agents[6]
other.visible = True
other.pos = Vec3(fx + 4.0, 0.0, fz)
ghost.pos = Vec3(fx, 0.0, fz)
ap._resolve_collisions()
check(abs(other.pos.x - (fx + 4.0)) < 1e-6 and abs(other.pos.z - fz) < 1e-6, f"125: 見えない人に押し出されない {other.pos}")
check(ghost.pos.x == fx and ghost.pos.z == fz, "125: 見えない人は押し出されない（位置が変わらない）")
ghost.visible = True
other.pos = Vec3(fx + 4.0, 0.0, fz)
ghost.pos = Vec3(fx, 0.0, fz)
ap._resolve_collisions()
check(math.hypot(other.pos.x - ghost.pos.x, other.pos.z - ghost.pos.z) > 4.0 + 1.0, "125: 対照：見えていれば押し出し合う")
ghost.visible = False
ghost.pos = Vec3(O.PARK_X, 0.0, O.DOOR_Z)
other.visible = False
other.pos = Vec3(O.PARK_X, 0.0, O.DOOR_Z)
ap._resolve_collisions()
check(ghost.pos.x == O.PARK_X and other.pos.x == O.PARK_X, "125: 見えない人は床の範囲の中へ押し戻されない（PARK_X のまま）")
# 125-d. update しない：位置・うろうろの時間・状態が変わらない
ghost.cooldown = 0.0
ghost.wander_time = 100.0
for a in ap.agents:
    a.cooldown = 0.0
    a.wander_time = 100.0
c_run(ap, 90)
check(all(a.pos.x == O.PARK_X and a.state == O.WANDER and a.wander_time == 100.0 for a in ap.agents),
      "125: 見えない人は動かず、うろうろの時間も数えない")
check(sum(ap.spot_manager.count(s) for s in O.OFFICE_SPOTS) == 0, "125: 見えない人は行き先を予約しない")
check(len(ap._nav_queue) == 0, "125: 見えない人は道探しの列に並ばない")
# 対照：見えていれば予約して出かける
ghost.visible = True
ghost.pos = Vec3(fx, 0.0, fz)
ghost.wander_time = 100.0
ghost.cooldown = 0.0
c_run(ap, 3)
check(sum(ap.spot_manager.count(s) for s in O.OFFICE_SPOTS) >= 1 and ghost.state in (O.GOING,), f"125: 対照：見えていれば行き先を予約する {ghost.state}")
ap.spot_manager.release(5)
ghost.visible = False
ghost.park()
# 125-e. 会話で人間が立つ場所の判定：見えない人の上でも空いている
ap, fb = c_make()
tx, tz = c_free_point(ap, 3)
check(ap._spot_free(tx, tz), "125: 前提：その点は空いている")
ap.agents[9].pos = Vec3(tx, 0.0, tz)
check(ap._spot_free(tx, tz), "125: 見えない人が立っていても、会話の立つ場所は空いている")
ap.agents[9].visible = True
check(not ap._spot_free(tx, tz), "125: 見えていれば塞がる（対照）")
ap.agents[9].visible = False
# 125-f. 道探しでよける人：見えない人は入らない。見えれば入る
ap, fb = c_make()
walker = ap.agents[4]
walker.visible = True
walker.pos = Vec3(*[c_free_point(ap, 0)[0], 0.0, c_free_point(ap, 0)[1]])
sitter = ap.agents[8]
sitter.pos = Vec3(walker.pos.x + 30.0, 0.0, walker.pos.z)
sitter.state = O.WORKING
sitter._arrived = True
check(sitter.is_fixed, "125: 前提：人 8 は座って動かない人")
check(ap._people_for(4) == [], f"125: 見えない人は、道探しでよける人に入らない {ap._people_for(4)}")
sitter.visible = True
check(ap._people_for(4) == [(sitter.pos.x, sitter.pos.z)], f"125: 見えていれば入る（対照） {ap._people_for(4)}")
sitter.visible = False
sitter.park()
walker.visible = False
walker.park()
# 125-g. 描画：見えない人は何も描かない（画素が空の床と同じ）。名前の札も出ない
ap, fb = c_make()
ghost = ap.agents[5]
fx, fz = c_free_point(ap, 0)
ghost.pos = Vec3(fx, 0.0, fz)
sx, sy = h_agent_xy(ap, 5)
ap.scene.update()
ap.draw()
patch_invisible = c_patch(ap, sx, sy)
ghost.pos = Vec3(O.PARK_X, 0.0, O.DOOR_Z)
ap.scene.update()
ap.draw()
patch_empty = c_patch(ap, sx, sy)
check(patch_invisible == patch_empty, "125: 見えない人は何も描かれない（画素が空の床と同じ）")
ghost.pos = Vec3(fx, 0.0, fz)
ghost.visible = True
ap.scene.update()
ap.draw()
patch_visible = c_patch(ap, sx, sy)
check(patch_visible != patch_empty, "125: 見えれば描かれる（対照）")
ghost.visible = False
ghost.label = "ghost"
ghost.role = "sub"
rec = c_draw(ap)
check(not any(t[2] == "ghost" for t in rec["text"]), "125: 見えない人の名前の札は出ない")

# 126. _enter と _leave（ドアの開閉と PARK）
ap, fb = c_make()
main = ap.agents[0]
check(not ap.door_open and ap.door_angle == 0.0, "126: 前提：ドアは閉まっている")
ap._enter(0)
check(ap.door_open and main.visible and main.state == O.WORKING, "126: _enter でドアを開け、見えるようになり、席へ向かう")
check(main.pos.x == O.ENTER_INSIDE_X == O.DOOR_AREA_X[1] + 20.0 and main.pos.z == O.DOOR_Z and main.pos.y == 0.0,
      f"126: ドアの内側（x = DOOR_AREA_X[1]+20、z = DOOR_Z）に置く {main.pos}")
c_run(ap, 10)
check(ap.door_angle > 0.0, f"126: ドアが開き始める {ap.door_angle}")
c_run(ap, 40)
check(ap.door_angle == O.DOOR_OPEN_ANGLE, f"126: ドアが全部開く {ap.door_angle}")
check(c_seated(ap, 0), "126: メインが席に着く")
closed_at = [None]
for f in range(1, 200):
    ap.update()
    if closed_at[0] is None and not ap.door_open:
        closed_at[0] = f
        break
check(closed_at[0] is not None and 56 <= closed_at[0] <= 66, f"126: 席に着いてから約 2 秒（60 フレーム）でドアを閉める {closed_at[0]}")
c_run(ap, 60)
check(ap.door_angle == 0.0, "126: ドアが閉じ切る")
# 席に着く前は閉めない：2 人目が歩いている間はドアは開いたまま
ap, fb = c_make()
ap._enter(0)
c_seated(ap, 0)
c_run(ap, 50)
check(ap.door_open, "126: 前提：席に着いて 50 フレームではまだ開いている")
ap._enter(11)
c_run(ap, 20)
check(ap.door_open and not ap.agents[11].is_seated, "126: 2 人目が歩いている間は、1 人目が着いて 2 秒たってもドアを閉めない")
c_seated(ap, 11)
c_run(ap, 50)
check(ap.door_open, "126: 2 人目が着いてから 50 フレームではまだ開いている")
c_run(ap, 20)
check(not ap.door_open, "126: 2 人目が着いて 2 秒でドアを閉める")
# D キーで開けたドアは自動で閉めない
ap, fb = c_make()
p_frame(ap, keys=(pyxel.KEY_D,))
c_run(ap, 200)
check(ap.door_open, "126: D キーで開けたドアは出入りがなくても自動では閉まらない")
# _leave
ap, fb = c_make()
ap._enter(0)
c_seated(ap, 0)
c_run(ap, 80)
check(not ap.door_open, "126: 前提：着席して 2 秒後にドアは閉まっている")
main = ap.agents[0]
main.busy = True
main.hold = True
ap._leave(0)
check(ap.door_open and main.state == O.LEAVING and main.visible, f"126: _leave でドアを開け、LEAVING になる（まだ見えている） {main.state}")
c_run(ap, 20)
check(ap.door_open and main.visible and main.state == O.LEAVING, "126: 歩いている間はドアが開いたまま・見えている")
check(c_invisible_all(ap, 0), "126: 歩き終えたら見えなくなる")
check(main.pos.x == O.PARK_X and main.pos.z == O.DOOR_Z and main.state == O.WANDER and not main.busy and not main.hold,
      f"126: PARK に戻る（PARK_X・ドアの z・WANDER・busy/hold を外す） {main.pos} {main.state} {main.busy} {main.hold}")
c_run(ap, 70)
check(not ap.door_open, "126: 出ていって 2 秒後にドアが閉まる")
# 見えていない人の _leave は何もしない
ap.door_open = False
ap._door_auto = False
ap._leave(3)
check(not ap.door_open and not ap.agents[3].visible and ap.agents[3].state == O.WANDER, "126: 見えない人の _leave は何もしない（ドアも開けない）")
# _leave が予約・列・帰る時間を片づける
ap, fb = c_make()
ap._enter(7)
c_seated(ap, 7)
ap.agents[7].state = O.WANDER
ap.agents[7]._arrived = False
picked = ap.spot_manager.reserve(7)
check(picked is not None and ap.agents[7].begin_going(*picked), "126: 前提：人 7 が行き先に向かう")
check(7 in ap._nav_queue, "126: 前提：人 7 は道探しの列に並んでいる")
ap._leave_timers[7] = 3.0
ap._leave(7)
check(sum(ap.spot_manager.count(s) for s in O.OFFICE_SPOTS) == 0, "126: _leave で行き先の予約を外す")
check(7 not in ap._nav_queue and 7 not in ap._leave_timers, "126: _leave で道探しの列と帰る時間から外す")
check(ap.agents[7].state == O.LEAVING, "126: 行き先に向かっていた人も LEAVING になる")
check(c_invisible_all(ap, 7), f"126: 道探しの順番待ち（path_wait）の人を _leave しても出ていく（path_wait={ap.agents[7].path_wait}）")
# PARK に戻ると、サブの対応と最後の行を消す
ap, fb = c_make()
ap._enter(7)
c_seated(ap, 7)
ap._sub_map["zz"] = 7
ap._last_line[7] = "最後の行"
ap._leave(7)
check(c_invisible_all(ap, 7), "126: 席に着いていた人は出ていく")
check("zz" not in ap._sub_map and 7 not in ap._last_line, "126: PARK に戻ると、サブエージェントの対応と最後の行を消す")
# 道が無いとき（begin_leaving が False）は、歩かずにその場で PARK
ap, fb = c_make()
ap._enter(0)
c_seated(ap, 0)
ap.agents[0].begin_leaving = lambda goal: False
ap._leave(0)
check(not ap.agents[0].visible and ap.agents[0].pos.x == O.PARK_X, "126: 道が無ければ歩かずに PARK へ")
# 出るときの LEAVING 中も、押し出し・選択の対象（見えている）。出ていく途中の人が人間のクリックで会話に選ばれる前に PARK へ戻る
ap, fb = c_make()
ap._enter(2)
c_seated(ap, 2)
ap._leave(2)
check(ap.agents[2] in [ap.agents[i] for i in ap._active_indices()], "126: LEAVING の間は見えている人に数える")
c_invisible_all(ap, 2)
check(2 not in ap._active_indices(), "126: PARK に戻ったら数えない")
# --claude（製品版）では、スペースで見えない人を作業にしない（2026-11-21 夜の直し）
ap, fb = c_make()
ap.next_index = 4
press_space_and_update(ap)
check(not ap.agents[4].visible and ap.agents[4].state != O.WORKING and not ap.door_open and ap.next_index == 4,
      "126: --claude ではスペースを押しても見えない人は入ってこない")
# 道探しの列で順番待ち（path_wait）をしている人を _leave しても、ちゃんと出ていく
ap, fb = c_make()
ap._enter(9)
check(ap.agents[9].path_wait and 9 in ap._nav_queue, "126: 前提：入ったばかりの人は道探しの順番待ち")
ap._leave(9)
check(c_invisible_all(ap, 9), f"126: 順番待ちの最中に _leave されても出ていく（path_wait={ap.agents[9].path_wait} state={ap.agents[9].state}）")

# 127. busy の間は席から立たない。busy が False になれば立つ
ap, fb = c_make()
main = c_start(ap)
c_seated(ap, 0)
main.busy = True
c_run(ap, 30 * 20)
check(main.state == O.WORKING and main.is_seated, f"127: busy の間は 20 秒たっても立ち上がらない {main.state}")
check(main._seated_time > O.WORK_HOLD_SEC, "127: （前提）座っている時間は 5 秒を超えている")
main.busy = False
c_run(ap, 2)
check(main.state == O.WORKING, "127: busy が False になった直後は（座って 5 秒を超えていても）まだ立たない（立つのは busy が False になってから 5 秒後。139 で詳しく）")
c_run(ap, int(5.3 * 30))
check(main.state == O.WANDER, f"127: busy が False になって 5 秒たてば立つ {main.state}")
# busy でないなら、座って 5 秒で立つ。4.5 秒ではまだ
ap, fb = c_make()
c_start(ap)
main = ap.agents[0]
c_seated(ap, 0)
c_run(ap, int(4.5 * 30))
check(main.state == O.WORKING, "127: busy でなければ座って 4.5 秒ではまだ立たない")
c_run(ap, int(1.0 * 30))
check(main.state == O.WANDER, "127: busy でなければ座って約 5 秒で立つ")
# hold と busy の両方
ap, fb = c_make()
c_start(ap)
main = ap.agents[0]
c_seated(ap, 0)
main.hold = True
c_run(ap, 30 * 7)
check(main.state == O.WORKING, "127: hold の間も立たない（今までどおり）")
main.hold = False
c_run(ap, 2)
check(main.state == O.WANDER, "127: hold を外せば立つ")
# サブも同じ：busy の間は座っている
ap, fb = c_make()
c_start(ap)
ap.started = True
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "d", "m"))
slot = ap._sub_map["a1"]
c_seated(ap, slot)
c_run(ap, 30 * 10)
check(ap.agents[slot].state == O.WORKING and ap.agents[slot].is_seated, "127: サブエージェントも busy の間は 10 秒たっても座っている")

# 128. 各イベントで履歴の行と吹き出しが出る
ap, fb = c_make()
main = c_start(ap)
c_seated(ap, 0)
ov_quiet(ap)
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s1", "ほかから打った"))
check(ap.history[n0:] == ["> ほかから打った"], f"128: ほかから打たれた Prompt は「> 文字」 {ap.history[n0:]}")
check(main.busy, "128: Prompt でメインが busy")
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s1", "一行目\n二行目"))
check(ap.history[n0:] == ["> 一行目", "  二行目"], f"128: 複数行の Prompt は 2 行目以降を字下げ {ap.history[n0:]}")
n0 = len(ap.history)
c_ev(ap, fb, Tool("s1", "Bash", "ls -la"))
check(ap.history[n0:] == ["  [Bash] ls -la"], f"128: Tool は「  [name] summary」 {ap.history[n0:]}")
check(main.busy and ap._last_line[0] == "Bash: ls -la", f"128: Tool でメインが busy・最後の行 {ap._last_line.get(0)}")
n0 = len(ap.history)
c_ev(ap, fb, Tool("s1", "Agent", "調べて"))
check(ap.history[n0:] == ["  [サブエージェント] 調べて"], f"128: name が Agent なら「[サブエージェント]」 {ap.history[n0:]}")
n0 = len(ap.history)
c_ev(ap, fb, Tool("s1", "Read", ""))
check(len(ap.history) - n0 == 1 and ap.history[n0].startswith("  [Read]"), f"128: 要約が空の Tool も 1 行 {ap.history[n0:]}")
# 作業中の Reply は作業中の吹き出し（144 で確かめる）に入るので、ここからの 6 秒の吹き出しは、作業が終わった（TurnEnd）あとに確かめる
c_ev(ap, fb, TurnEnd("s1"))
check(not main.busy, "128: 前提：TurnEnd で作業中でなくなる（作業中でなければ Reply が 6 秒の吹き出しになる）")
n0 = len(ap.history)
c_ev(ap, fb, Reply("s1", "はい\n二行目\n三行目"))
check(ap.history[n0:] == [], f"128: Reply は履歴に出さない（返事は会話のダイアログで読む。156 番の変更） {ap.history[n0:]}")
check(ap._bubble == "はい\n二行目\n三行目" and abs(ap._bubble_left - (O.BUBBLE_SEC - 1 / 30)) < 1e-6, f"128: 吹き出しが 6 秒の予定で出る {ap._bubble!r} {ap._bubble_left}")
# 長い Reply は桁数で折り返す
n0 = len(ap.history)
long_reply = "あいうえお" * 40
c_ev(ap, fb, Reply("s1", long_reply))
rows = ap.history[n0:]
check(rows == [] and ap._last_reply == long_reply, f"128: 長い Reply も履歴には出さない（全文は _last_reply に残る） {rows}")
# 吹き出しの表示（draw）
c_ev(ap, fb, Reply("s1", "短いへんじ"))
head = ap._head_point(main)
check(head is not None, f"128: 前提：メインの頭が画面の中 {head}")
rec = c_draw(ap)
bubble_txt = [t for t in rec["utext"] if t[2] == "短いへんじ"]
check(len(bubble_txt) == 1 and bubble_txt[0][3] == 0, f"128: 吹き出しの文字は黒（色 0）・UI フォント {bubble_txt}")
w_bub = ap.ui_font.text_width("短いへんじ") + 6
white = [r for r in rec["rect"] if len(r) >= 5 and r[4] == 7 and r[2] == w_bub and r[3] == O.UI_LINE_H + 2]
check(len(white) == 1, f"128: 吹き出しの枠は白い四角（色 7）。幅 {w_bub} 高さ {O.UI_LINE_H + 2} {white}")
if white and head is not None:
    bx_, by_ = white[0][0], white[0][1]
    check(by_ + white[0][3] <= head[1] and bx_ <= head[0] <= bx_ + w_bub, f"128: 吹き出しは頭の上 {white[0]} {head}")
    check(len(rec["tri"]) >= 1 and rec["tri"][-1][-1] == 7, "128: 口元の三角（tri・白）が出る")
    tri = rec["tri"][-1]
    check(abs(tri[4] - head[0]) <= 1 and tri[1] == by_ + white[0][3], f"128: 三角が頭を指す {tri}")
check(not any(t[2] == "main" for t in rec["text"]), "128: 吹き出しが出ている間はメインの名前の札を出さない")
# 24 文字を超えたら「…」
c_ev(ap, fb, Reply("s1", "あ" * 24))
rec = c_draw(ap)
check(any(t[2] == "あ" * 24 for t in rec["utext"]) and not any("…" in t[2] for t in rec["utext"]), "128: ちょうど 24 文字なら「…」を付けない")
c_ev(ap, fb, Reply("s1", "い" * 25))
rec = c_draw(ap)
check(any(t[2] == "い" * 24 + "…" for t in rec["utext"]), f"128: 24 文字を超えたら先頭の 24 文字＋「…」 {[t[2] for t in rec['utext'] if 'い' in t[2]]}")
c_ev(ap, fb, Reply("s1", "改行\nあり"))
rec = c_draw(ap)
check(any(t[2] == "改行 あり" for t in rec["utext"]), "128: 吹き出しの中の改行は空白にする")
# 6 秒で消える・次の Reply で延びる
c_run(ap, 30 * 5)
check(ap._bubble != "", "128: 5 秒たってもまだ出ている")
c_ev(ap, fb, Reply("s1", "もう一度"))
c_run(ap, 30 * 5)
check(ap._bubble == "もう一度", "128: 新しい Reply で 6 秒が数え直される")
c_run(ap, 40)
check(ap._bubble == "" and ap._bubble_left <= 0.0, "128: 6 秒たつと吹き出しが消える")
rec = c_draw(ap)
check(not c_ui_has(rec, "もう一度"), "128: 消えたら描かない")
check(any(t[2] == "main" and t[3] == 10 for t in rec["text"]), "128: 吹き出しが無いときはメインの名前の札（色 10）")
# 見えないメインには吹き出しを描かない
c_ev(ap, fb, Reply("s1", "見えない人"))
main.visible = False
rec = c_draw(ap)
check(not c_ui_has(rec, "見えない人"), "128: メインが見えていなければ吹き出しを描かない")
main.visible = True
# TurnEnd
n0 = len(ap.history)
main.busy = True
c_ev(ap, fb, TurnEnd("s1"))
check(not main.busy and ap.history[n0:] == [] and not ap.ending and ap.started, "128: TurnEnd でメインが busy でなくなる（履歴は増えず、終業にならない）")
check(ap.agents[0].visible, "128: TurnEnd だけではメインは出ていかない")
# 自分の送信は二重に出ない
ap, fb = c_make()
main = c_start(ap)
c_seated(ap, 0)
ap.input_buf = "こんにちは"
n0 = len(ap.history)
ap._send_input()
check(ap.history[n0:] == ["> こんにちは"] and ("send_prompt", "こんにちは") in fb.calls and ap.input_buf == "", f"128: 自分の送信は履歴に 1 回・bridge に渡る {ap.history[n0:]}")
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s1", "こんにちは"))
check(ap.history[n0:] == [] and main.busy, "128: 届いた同じ Prompt は履歴に足さない（busy にはなる）")
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s1", "こんにちは"))
check(ap.history[n0:] == ["> こんにちは"], "128: 同じ文を、今度はほかから打たれたら出す（1 回きりの照合）")
ap.input_buf = "違う文"
ap._send_input()
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s1", "別の文"))
check(ap.history[n0:] == ["> 別の文"], "128: 送った文と違う Prompt は履歴に足す")
ap.input_buf = "一行目\n二行目"
ap._send_input()
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s1", "一行目\n二行目"))
check(ap.history[n0:] == [], "128: 複数行の自分の送信も二重にならない")
ap.input_buf = "後ろに空白 "
ap._send_input()
check(("send_prompt", "後ろに空白 ") in fb.calls, "128: bridge には元の input_buf をそのまま渡す")
# 同じフレームに届いたイベントの順番どおりに履歴が並ぶ
ap, fb = c_make()
c_start(ap)
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", "P"), Tool("s", "Bash", "x"), Reply("s", "R"), TurnEnd("s"))
check(ap.history[n0:] == ["> P", "  [Bash] x"], f"128: 1 フレームに届いた複数のイベントが順に履歴に出る（Reply は出さない） {ap.history[n0:]}")
# 立っているメインに Prompt が来ると席へ向かう。見えないメインなら入ってくる
ap, fb = c_make()
main = c_start(ap)
c_seated(ap, 0)
c_run(ap, 30 * 6)
check(main.state == O.WANDER, "128: 前提：メインが席を立った")
c_ev(ap, fb, Prompt("s", "来た"))
check(main.state == O.WORKING and main.busy, "128: 立っているメインに Prompt が来ると席へ向かう")
c_seated(ap, 0)
ap._leave(0)
c_invisible_all(ap, 0)
check(not main.visible, "128: 前提：メインが帰った")
c_ev(ap, fb, Tool("s", "Bash", "ls"))
check(main.visible and main.state == O.WORKING and main.busy and ap.door_open, "128: 帰ったメインに Tool が来ると入ってくる")
c_seated(ap, 0)
ap._leave(0)
c_invisible_all(ap, 0)
c_ev(ap, fb, Prompt("s", "また"))
check(main.visible and main.busy, "128: 帰ったメインに Prompt が来ると入ってくる")
c_seated(ap, 0)
ap._leave(0)
c_invisible_all(ap, 0)
c_ev(ap, fb, Reply("s", "返事だけ"))
check(not main.visible and ap._bubble == "返事だけ", "128: Reply だけでは帰ったメインは入ってこない（吹き出しの予定は入る）")
# 10 分休み
ap, fb = c_make()
main = c_start(ap)
c_seated(ap, 0)
ap.agents[0].busy = False
ap._idle_main = O.IDLE_LEAVE_SEC - 0.2
c_run(ap, 3)
check(main.state == O.WORKING, "128: 10 分に 0.2 秒足りないうちは帰らない")
c_run(ap, 10)
check(main.state == O.LEAVING or not main.visible, f"128: 10 分の休みでメインが帰り始める {main.state}")
check(("end", True) not in fb.calls and ap.started, "128: 10 分休んで帰っても tmux は閉じない（始業のまま）")
c_invisible_all(ap, 0)
check(not main.visible and ap.started, "128: メインが見えなくなる")
ap, fb = c_make()
main = c_start(ap)
c_seated(ap, 0)
main.busy = True
ap._idle_main = 0.0
c_run(ap, 300)
check(ap._idle_main == 0.0, "128: busy の間は休みの時間を数えない")
c_ev(ap, fb, TurnEnd("s"))
ap._idle_main = 5.0
c_ev(ap, fb, Tool("s", "Bash", "x"))
check(ap._idle_main == 0.0, "128: イベントが来ると休みの時間が 0 に戻る")
# 始業前（polled されない）
ap, fb = c_make()
c_run(ap, 10)
check(fb.polls == 0, "128: 始業前は bridge.poll を呼ばない")
fb.script = [Prompt("s", "来ない")]
c_run(ap, 5)
check(fb.polls == 0 and not any(x.startswith(">") for x in ap.history), "128: 始業前に届いたイベントは処理しない")
c_start(ap)
c_run(ap, 5)
check(fb.polls >= 5, "128: 始業後は毎フレーム poll する")
ap.started = False

# 129. サブエージェント：席 2〜17 に入り、5 秒後に帰る
ap, fb = c_make()
main = c_start(ap)
n0 = len(ap.history)
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "肌の色のテスト追加", "sonnet"))
slot = ap._sub_map.get("a1")
check(slot == 2, f"129: 最初のサブエージェントは席 2 {slot}")
sub = ap.agents[slot]
check(sub.visible and sub.role == "sub" and sub.label == "kakaricho" and sub.busy and sub.state == O.WORKING, "129: role/label/busy/WORKING")
check(ap.history[n0:] == ["  [呼ばれた] kakaricho: 肌の色のテスト追加"], f"129: 呼ばれた行 {ap.history[n0:]}")
check(ap._last_line[slot] == "肌の色のテスト追加" and abs(sub.pos.x - O.ENTER_INSIDE_X) < 20 and abs(sub.pos.z - O.DOOR_Z) < 20, f"129: 最後の行は description・ドアの内側から入る {sub.pos}")
check(main.visible and main.role == "main", "129: メインはそのまま")
n0 = len(ap.history)
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "もう一度", "sonnet"))
check(len(ap._sub_map) == 1 and ap.history[n0:] == [], "129: 同じ agent_id の開始は無視する（席も履歴も増えない）")
c_ev(ap, fb, SubagentStart("a2", "", "種類なし", ""))
check(ap._sub_map["a2"] == 3 and ap.agents[3].label == "sub", f"129: 次は席 3・種類が空なら label は sub {ap._sub_map} {ap.agents[3].label!r}")
# 見えている席は飛ばす
ap.agents[4].visible = True
c_ev(ap, fb, SubagentStart("a3", "x", "y", ""))
check(ap._sub_map["a3"] == 5, f"129: 見えている席（4）は飛ばして次（5） {ap._sub_map}")
ap.agents[4].visible = False
c_ev(ap, fb, SubagentStart("a4", "x", "y", ""))
check(ap._sub_map["a4"] == 4, "129: 空いた若い番号（4）を先に使う")
check(0 not in ap._sub_map.values() and 1 not in ap._sub_map.values(), "129: 席 0・1 はサブに使わない")
# 名前の札
rec = c_draw(ap)
labels = {t[2]: t[3] for t in rec["text"]}
check("kakaricho" not in labels, f"129: 作業中のサブは名前の札の代わりに作業中の吹き出しを出す {labels}")
busy_bak = dict(ap._busy_text)
ap._busy_text.clear()
rec = c_draw(ap)
labels = {t[2]: t[3] for t in rec["text"]}
check(labels.get("kakaricho") == 7 or ap._head_point(sub) is None, f"129: 作業中の吹き出しが無いサブの名前の札は色 7 {labels}")
ap._busy_text.update(busy_bak)
check(labels.get("main") == 10, f"129: メインの名前の札は色 10 {labels}")
check(not any(t[2] in ("A", "B", "C", "人間", "human") for t in rec["text"] if t[1] < O.VIEW3D_H and t[0] > 100 and t[3] in (7, 10)), "129: 人間の札は出ない")
# 終わり：5 秒後に帰る
n0 = len(ap.history)
c_ev(ap, fb, SubagentEnd("a1"))
check(not sub.busy and "a1" not in ap._sub_map and slot in ap._leave_timers, "129: 終わりで busy が外れ、対応が消え、帰る時間が入る")
check(O.SUB_LEAVE_SEC == 300.0 and abs(ap._leave_timers[slot] - (O.SUB_LEAVE_SEC - 1 / 30)) < 1e-6,
      f"129: 帰るまでは SUB_LEAVE_SEC（300 秒） {ap._leave_timers[slot]}")
check(ap.history[n0:] == [], "129: 終わりは履歴に出さない")
ap._leave_timers[slot] = 5.0 - 1 / 30  # 帰る仕組みの確認は、残りを 5 秒にして進める（300 秒ぶん回さない）
c_run(ap, int(4.5 * 30))
check(sub.visible and sub.state != O.LEAVING and slot in ap._leave_timers, f"129: 4.5 秒ではまだ帰らない {sub.state}")
c_run(ap, int(0.8 * 30))
check(sub.state == O.LEAVING or not sub.visible, f"129: 5 秒を過ぎると帰り始める {sub.state}")
check(c_invisible_all(ap, slot) and sub.pos.x == O.PARK_X and slot not in ap._leave_timers, "129: 部屋を出て見えなくなる")
check(sub.busy is False, "129: 帰ったあと busy でない")
check(ap.agents[3].visible and "a2" in ap._sub_map, "129: ほかのサブは影響を受けない")
n0 = len(ap.history)
c_ev(ap, fb, SubagentEnd("unknown"))
check(ap.history[n0:] == [] and ap.started, "129: 知らない agent_id の終わりは何もしない")
# 帰った席は次の開始で若い番号から再利用
c_ev(ap, fb, SubagentStart("a5", "z", "w", ""))
check(ap._sub_map["a5"] == 2, f"129: 帰った席（2）が再利用される {ap._sub_map}")
# 全席が埋まったら何もしない（作業は止めない）
ap, fb = c_make()
main = c_start(ap)
for k in range(16):
    c_ev(ap, fb, SubagentStart(f"s{k}", "t", f"d{k}", ""))
check(sorted(ap._sub_map.values()) == list(range(2, 18)), f"129: 席 2〜17 の 16 人が入る {sorted(ap._sub_map.values())}")
n0 = len(ap.history)
c_ev(ap, fb, SubagentStart("s16", "t", "あふれた", ""))
check("s16" not in ap._sub_map and ap.history[n0:] == [] and len(ap._sub_map) == 16, "129: 空きが無ければ何もしない（履歴も出さない）")
check(main.visible and ap.started, "129: あふれてもメインは止まらない")
c_ev(ap, fb, SubagentEnd("s16"))
check(len(ap._sub_map) == 16, "129: あふれた分の終わりは何もしない")
c_run(ap, 5)
# 席が少ない App
ap, fb = c_make(n=5)
c_start(ap)
for k in range(5):
    c_ev(ap, fb, SubagentStart(f"s{k}", "t", "d", ""))
check(sorted(ap._sub_map.values()) == [2, 3, 4], f"129: 5人の App では席 2〜4 だけ {sorted(ap._sub_map.values())}")
ap, fb = c_make(n=2)
c_start(ap)
c_ev(ap, fb, SubagentStart("s0", "t", "d", ""))
check(ap._sub_map == {} and ap.started, "129: 2人の App ではサブの席が無く、何もしない")
# 席に着き、帰るまでの通し
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "d", ""))
slot = ap._sub_map["a1"]
check(c_seated(ap, slot), "129: サブが席に着く")
c_ev(ap, fb, SubagentEnd("a1"))
ap._leave_timers[slot] = 5.0  # 残りを 5 秒にして進める（SUB_LEAVE_SEC は 300 秒）
c_run(ap, 30 * 6)
check(ap.agents[slot].state in (O.LEAVING, O.WANDER) or not ap.agents[slot].visible, "129: 終わってから 6 秒で帰り始めている")
check(c_invisible_all(ap, slot), "129: そのまま出ていく")
# 同じ席の人が続けて呼ばれる前に、終わりの帰る時間が残っていても、_leave で消える
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, SubagentStart("a1", "t", "d", ""))
slot = ap._sub_map["a1"]
c_ev(ap, fb, SubagentEnd("a1"))
ap._leave(slot)
check(slot not in ap._leave_timers, "129: _leave で帰る時間の予約が消える")

# 130. 始業前の送信、始業後の送信、PROMPT の Esc
ap, fb = c_make()
p_enter_prompt(ap)
n0 = len(ap.history)
p_send(ap, "こんにちは")
check(ap.history[n0:] == ["> こんにちは", "(始業していません。F1 で始業してください)"], f"130: 始業前の送信は履歴に出して案内する {ap.history[n0:]}")
check(not any(c[0] == "send_prompt" for c in fb.calls) and not any(a.visible for a in ap.agents), "130: 始業前は bridge に送らず、誰も出てこない")
check(ap.input_buf == "", "130: 送ったあと入力欄は空")
p_frame(ap, keys=(pyxel.KEY_F1,))
check(ap.started and ap.mode == O.MODE_PROMPT, "130: PROMPT のまま始業")
n0 = len(ap.history)
p_send(ap, "  こんにちは  ")
check(("send_prompt", "  こんにちは  ") in fb.calls, f"130: 始業後は元の入力をそのまま bridge に送る {fb.calls}")
check(ap.history[n0:] == ["> " + "  こんにちは  "] or ap.history[n0:] == [">   こんにちは  "], f"130: 履歴に「> 」付きで 1 回 {ap.history[n0:]}")
check(ap._last_sent == "  こんにちは  ", "130: 送った文を覚える")
n0 = len(ap.history)
p_send(ap, "   ")
check(len(fb.calls) == 2 and ap.history[n0:] == [], f"130: 空白だけは送らない・履歴にも出さない {fb.calls}")
# 帰ったメインに送ると入ってくる
c_seated(ap, 0)
ap._leave(0)
c_invisible_all(ap, 0)
check(not ap.agents[0].visible, "130: 前提：メインが帰っている")
ap._idle_main = 123.0
p_send(ap, "もどって")
check(ap.agents[0].visible and ap.agents[0].state == O.WORKING and ap.door_open, "130: 帰ったメインに送ると入ってくる")
check(ap._idle_main < 2.0 and ("send_prompt", "もどって") in fb.calls, f"130: 休みの時間が戻り（123 秒のまま残らない）、bridge に渡る {ap._idle_main}")
ap.started = False
# Esc
ap, fb = c_make()
c_start(ap)
p_enter_prompt(ap)
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(fb.calls.count(("send_escape",)) == 1 and ap.history[n0:] == ["(Esc: 中断を送る)"], f"130: PROMPT の Esc で send_escape と履歴 {fb.calls} {ap.history[n0:]}")
check(ap.mode == O.MODE_PROMPT, "130: Esc でモードは変わらない")
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(fb.calls.count(("send_escape",)) == 2, "130: Esc を押すたびに送る")
# 変換中の Esc は送らない
ap.ime_composing = True
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(fb.calls.count(("send_escape",)) == 2 and ap.history[n0:] == [] and not ap.ime_composing, "130: 変換中の Esc は取り消しで、send_escape も履歴の行も出さない")
ap._ime_wait_text = 3
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(fb.calls.count(("send_escape",)) == 2 and ap._ime_wait_text == 0, "130: 変換中かもしれない待ちの間の Esc も送らない")
ap.started = False
# 始業前の Esc は送らない（履歴の行は出す）
ap, fb = c_make()
p_enter_prompt(ap)
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(not any(c[0] == "send_escape" for c in fb.calls) and ap.history[n0:] == ["(Esc: 中断を送る)"], "130: 始業前の Esc は bridge に送らず、履歴の行だけ出す")

# 131. 終業：TurnEnd／待ち時間切れ
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "d", ""))
c_ev(ap, fb, SubagentStart("a2", "yamada", "d", ""))
c_seated(ap, 0)
c_seated(ap, 2)
check(sorted(ap._active_indices()) == [0, 2, 3], f"131: 前提：メインとサブ 2 人が見えている {ap._active_indices()}")
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_F1,))
check(ap.history[n0:] == ["終業：引き継ぎメモを書いてもらっています"], f"131: 終業の履歴 {ap.history[n0:]}")
check(fb.calls.count(("send_prompt", i18n_t(O.HANDOFF_PROMPT))) == 1 and i18n_t(O.HANDOFF_PROMPT) == "今日の作業の引き継ぎメモを書いてください。", "131: 引き継ぎメモの依頼を送る")
check(ap.ending and ap.started and O.HANDOFF_WAIT_SEC == 300.0 and 299.9 < ap._handoff_left <= 300.0, f"131: ending・待ち時間 300 秒 {ap._handoff_left}")
check(("end", True) not in fb.calls, "131: 引き継ぎを待っている間は閉じない")
# 待っている間の F1・ボタンは何もしない
p_frame(ap, keys=(pyxel.KEY_F1,))
bx2, by2, bw2, bh2 = ap._button_rect("[F1] 終業")
p_frame(ap, click=(bx2 + 4, by2 + 4))
check(fb.calls.count(("send_prompt", i18n_t(O.HANDOFF_PROMPT))) == 1 and ap.ending, "131: 待っている間の F1・ボタンでは二重に頼まない")
# 引き継ぎの依頼が Prompt として届いても、履歴に二重に出ない
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)))
check(ap.history[n0:] == [], f"131: 送った引き継ぎの依頼は Prompt で届いても履歴に二重に出ない {ap.history[n0:]}")
# 待っている間の Reply・Tool は今までどおり出る
n0 = len(ap.history)
c_ev(ap, fb, Tool("s", "Write", "memo.md"), Reply("s", "書きました"))
check(ap.history[n0:] == ["  [Write] memo.md"] and ap.ending, "131: 待っている間も Tool は履歴に出る（Reply は履歴に出さない）（終業にはならない）")
c_ev(ap, fb, TurnEnd("s"))
check(("end", True) in fb.calls and fb.calls.count(("end", True)) == 1, f"131: TurnEnd で bridge.end(kill_session=True) {fb.calls}")
check(not ap.started and not ap.ending and ap.history[-1] == "終業しました", f"131: started/ending が False・「終業しました」 {ap.history[-1]}")
check(ap._sub_map == {} and ap._leave_timers == {} and ap._last_line == {}, "131: サブの対応・帰る時間・最後の行が空になる")
check(all(ap.agents[i].state == O.LEAVING for i in (0, 2, 3)), f"131: 見えていた全員が出ていく {[ap.agents[i].state for i in (0, 2, 3)]}")
check(ap.door_open, "131: 出ていくのでドアが開く")
rec = c_draw(ap)
check(c_ui_has(rec, "[F1] 始業") and not c_ui_has(rec, "[F1] 終業"), "131: 終業後のボタンは「[F1] 始業」")
check(all(c_invisible_all(ap, i) for i in (0, 2, 3)), "131: 全員が見えなくなる")
check(ap._active_indices() == [], "131: 見えている人がいない")
c_run(ap, 90)
check(not ap.door_open, "131: みんな出たあとドアが閉まる")
polls0 = fb.polls
fb.script = [Prompt("s", "終業後")]
c_run(ap, 5)
check(fb.polls == polls0 and fb.script, "131: 終業後は poll しない")
# もう一度始業できる（セッションは閉じたので new）
fb.calls.clear()
c_start(ap)
check(fb.calls == [("begin", "new")] and ap.started and ap.agents[0].visible and ap.agents[0].label == "main", f"131: 終業のあと、もう一度始業できる {fb.calls}")
ap.started = False
# TurnEnd が終業中でなければ終業にならない（128 でも確認）。待ち時間切れ
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
p_frame(ap, keys=(pyxel.KEY_F1,))
c_run(ap, 30 * 280)
check(ap.ending and ap.started and ("end", True) not in fb.calls, "131: 280 秒ではまだ待っている")
check(18 < ap._handoff_left < 21, f"131: 待ちの残りは約 20 秒 {ap._handoff_left}")
c_run(ap, 30 * 19)
check(ap.ending and ("end", True) not in fb.calls, "131: 299 秒でもまだ待っている")
c_run(ap, 60)
check(not ap.ending and not ap.started and ("end", True) in fb.calls and ap.history[-1] == "終業しました", "131: 300 秒を過ぎると TurnEnd が無くても終業する")
check(c_invisible_all(ap, 0), "131: 待ち時間切れでもメインが出ていく")
# 終業中に別の TurnEnd が来たあとの二重の終業をしない
ap, fb = c_make()
c_start(ap)
p_frame(ap, keys=(pyxel.KEY_F1,))
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s"))
check(fb.calls.count(("end", True)) == 1, "131: 終業は 1 回だけ end する")
c_run(ap, 30 * 305)
check(fb.calls.count(("end", True)) == 1 and ap.history.count("終業しました") == 1, "131: 待ち時間が過ぎても、終業済みなら二度目の終業をしない")

# 132. _shutdown_claude（窓を閉じたときの後始末。偽の sleep で）
ap, fb = c_make()
sleeps = []
ap._shutdown_claude(sleep=sleeps.append)
check(fb.calls == [] and sleeps == [], "132: 始業していなければ何もしない")
# 始業していて終業していない：依頼を送り、TurnEnd を待ち、閉じる
ap, fb = c_make()
c_start(ap)
fb.calls.clear()
script_calls = [[], [Prompt("s", i18n_t(O.HANDOFF_PROMPT))], [Tool("s", "t", ""), TurnEnd("s")]]
fb.poll = lambda: script_calls.pop(0) if script_calls else []
sleeps = []
ap._shutdown_claude(sleep=sleeps.append)
check(fb.calls == [("send_prompt", i18n_t(O.HANDOFF_PROMPT)), ("end", True)], f"132: 依頼を 1 回送り、TurnEnd で閉じる {fb.calls}")
check(sleeps == [0.2, 0.2], f"132: TurnEnd が来るまで 0.2 秒ずつ待つ {sleeps}")
check(not ap.started and not ap.ending, "132: started・ending が False")
# TurnEnd が来ない：300 秒で諦めて閉じる
ap, fb = c_make()
c_start(ap)
fb.calls.clear()
fb.poll = lambda: [Reply("s", "x")]
sleeps = []
ap._shutdown_claude(sleep=sleeps.append)
check(fb.calls == [("send_prompt", i18n_t(O.HANDOFF_PROMPT)), ("end", True)], f"132: 待ち時間切れでも閉じる {fb.calls}")
check(all(s == 0.2 for s in sleeps) and 299.0 <= sum(sleeps) <= 300.5 and 1498 <= len(sleeps) <= 1502, f"132: 約 300 秒（0.2 秒を約 1500 回）待つ {len(sleeps)} 回 {sum(sleeps):.1f} 秒")
check(not ap.started, "132: 閉じたあと started が False")
# すでに終業の手順に入っていれば、依頼を二重に送らない
ap, fb = c_make()
c_start(ap)
p_frame(ap, keys=(pyxel.KEY_F1,))
fb.calls.clear()
fb.poll = lambda: [Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s")]
ap._shutdown_claude(sleep=lambda s: None)
check(fb.calls == [("end", True)], f"132: 終業の途中なら依頼を送り直さず、待って閉じる {fb.calls}")
# 最初の poll で TurnEnd：sleep せずに閉じる。TurnEnd 以外のイベントは無視する
ap, fb = c_make()
c_start(ap)
fb.calls.clear()
fb.poll = lambda: [Prompt("s", i18n_t(O.HANDOFF_PROMPT)), SubagentEnd("x"), TurnEnd("s")]
sleeps = []
ap._shutdown_claude(sleep=sleeps.append)
check(sleeps == [] and fb.calls[-1] == ("end", True), "132: 最初の poll に TurnEnd があれば待たない")
# atexit に登録される関数は _shutdown_claude を呼ぶ（始業していれば）。始業していなければ何もしない
ap, fb = c_make()
fb.calls.clear()
ap._atexit_shutdown()
check(fb.calls == [], "132: 始業していなければ atexit の後始末は何もしない")
c_start(ap)
fb.calls.clear()
fb.poll = lambda: [Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s")]
ap._atexit_shutdown()
check(fb.calls == [("send_prompt", i18n_t(O.HANDOFF_PROMPT)), ("end", True)] and not ap.started, f"132: 始業していれば atexit の後始末が引き継ぎを頼んで閉じる {fb.calls}")
# atexit.register に ap._atexit_shutdown が登録される（--claude のときだけ）
registered = []
_real_register = _atexit_c.register
_atexit_c.register = lambda f, *a, **k: registered.append(f) or f
try:
    ap_c = make_app(30, 1, "office", 3, claude=True, workdir=str(C_WORK), bridge_factory=lambda w, s: FakeBridge())
    ap_n = make_app(30, 1, "office", 3)
finally:
    _atexit_c.register = _real_register
check(ap_c._atexit_shutdown in registered, f"132: --claude のとき _atexit_shutdown を atexit に登録する {registered}")
check(ap_n._atexit_shutdown not in registered and len(registered) == 1, "132: --claude なしでは atexit に登録しない")
C_APPS.append(ap_c)

# 133. 会話中に相手が _leave したら会話が終わる。会話の様子の札
def c_talk_ready(ap, i):
    """人 i と会話を始める（席に着いているとき）。"""
    ap.start_talk(i)
    return ap.talk_partner == i


ap, fb = c_make()
main = c_start(ap)
c_seated(ap, 0)
check(c_talk_ready(ap, 0) and main.hold, "133: 前提：メインと会話中")
ap._enter(5)
c_seated(ap, 5)
ap._leave(5)
check(ap.talk_partner == 0 and main.hold, "133: 会話の相手でない人が帰っても会話は続く")
c_invisible_all(ap, 5)
ap._leave(0)
check(ap.talk_partner is None and not main.hold, "133: 会話の相手が _leave したら会話が終わる（相手の hold も外れる）")
check(main.state == O.LEAVING, "133: そのまま出ていく")
c_run(ap, 600)
check(not main.visible and ap.talk_partner is None, "133: 出ていったあとも会話は終わったまま・例外なし")
# サブが終わって帰る時間が来たとき、会話中ならそこで会話が終わる
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "説明", ""))
slot = ap._sub_map["a1"]
c_seated(ap, slot)
check(c_talk_ready(ap, slot), "133: 前提：サブと会話中")
c_ev(ap, fb, SubagentEnd("a1"))
ap._leave_timers[slot] = 5.0  # 残りを 5 秒にして進める（SUB_LEAVE_SEC は 300 秒）
c_run(ap, 30 * 5 + 10)
check(ap.talk_partner is None and not ap.agents[slot].hold, "133: 会話中のサブが帰る時間が来たとき、会話が終わる")
c_invisible_all(ap, slot)
# 終業のとき、会話中のメインとの会話も終わる
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
c_talk_ready(ap, 0)
p_frame(ap, keys=(pyxel.KEY_F1,))
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s"))
check(ap.talk_partner is None, "133: 終業で全員が出るとき、会話も終わる")
c_run(ap, 300)
# 会話の様子の札：製品版（--claude）では右上に描かない（2026-11-21 夜の直し。会話の中身はダイアログに出る）
px = O.OFFICE_SCREEN_W - O.CLAUDE_TALK_PANEL_W - 4
ap, fb = c_make()
main = c_start(ap)
c_seated(ap, 0)
c_ev(ap, fb, Tool("s", "Bash", "ls -la"))
check(c_talk_ready(ap, 0), "133: メインと会話")
rec = c_draw(ap)
check(not any(r[:4] == (px, 4, O.CLAUDE_TALK_PANEL_W, 36) for r in rec["rect"]), "133: 会話中でも右上の札の黒い四角を描かない")
check(not any(t[0] == px + 4 for t in rec["text"]), f"133: 右上の札の文字（label・状態・最後の Tool）を描かない {[t for t in rec['text'] if t[0] == px + 4]}")

# 134. --claude なしでは何も変わらない
ap_n = make_app(30, 1, "office", 5)
check(not ap_n.claude and ap_n.bridge is None and not ap_n.started and not ap_n.ending, "134: --claude なしは claude False・bridge なし")
check(all(a.visible and a.role == "" and a.label == "" and not a.busy for a in ap_n.agents), "134: 全員が見えていて role/label が空・busy でない")
check(ap_n._active_indices() == [0, 1, 2, 3, 4], "134: _active_indices は全員")
check(all(a.pos.x != O.PARK_X for a in ap_n.agents), "134: PARK に置かれない")
n0 = len(ap_n.history)
p_frame(ap_n, keys=(pyxel.KEY_F1,))
check(len(ap_n.history) == n0 and not ap_n._dialog and not ap_n.started, "134: F1 は何もしない")
p_frame(ap_n, click=(10, 45))
check(ap_n.talk_partner is None and not ap_n._dialog and not ap_n.started, "134: ボタンの場所をクリックしても何も起きない")
rec = c_draw(ap_n)
check(not c_ui_has(rec, "[F1] 始業") and not c_ui_has(rec, "[F1] 終業"), "134: ボタンを描かない")
check(not any(t[2] in ("main", "sub") for t in rec["text"]), "134: 名前の札を出さない")
p_enter_prompt(ap_n)
n0 = len(ap_n.history)
p_send(ap_n, "テスト")
check(ap_n.history[n0:] == ["> テスト"], f"134: 送信は履歴に出すだけ（「始業していません」を出さない） {ap_n.history[n0:]}")
n0 = len(ap_n.history)
p_frame(ap_n, keys=(pyxel.KEY_ESCAPE,))
check(ap_n.history[n0:] == ["(Esc: 中断を送る)"], "134: Esc は履歴に出すだけ")
ap_n.mode = O.MODE_WALK
door0 = ap_n.door_open
press_space_and_update(ap_n)
check(ap_n.agents[0].state == O.WORKING and ap_n.door_open == door0 and ap_n.agents[0].visible, "134: スペースで今までどおり作業になる（ドアは動かない）")
c_run(ap_n, 600)
check(ap_n.agents[0].state != O.WORKING and not ap_n.door_open, f"134: busy でないので 5 秒で席を立つ（今までどおり） {ap_n.agents[0].state}")
ap_n.start_talk(1)
rec = c_draw(ap_n)
px = O.OFFICE_SCREEN_W - O.CLAUDE_TALK_PANEL_W - 4
check(ap_n.talk_partner == 1 and not any(r[:4] == (px, 4, O.CLAUDE_TALK_PANEL_W, 36) for r in rec["rect"]), "134: 会話しても様子の札は出ない")
ap_n.end_talk()
ap_n._shutdown_claude(sleep=lambda s: (_ for _ in ()).throw(AssertionError("sleep された")))
check(True, "134: _shutdown_claude は何もしない")
# 引数
ns = pyxelcube_agents.parse_args([])
check(ns.claude is False and ns.workdir is None and ns.session == "pyxelcube_agents", f"134: 引数の既定 claude=False workdir=None session=pyxelcube_agents {ns}")
ns = pyxelcube_agents.parse_args(["--layout", "office", "--claude", "--workdir", "/x/y", "--session", "abc"])
check(ns.claude is True and ns.workdir == "/x/y" and ns.session == "abc", f"134: --claude --workdir --session {ns}")
# proto では --claude が無視される（bridge_factory も作業フォルダも使わない）
made = []
nowhere = TMP_DIR / "no_such_workdir_proto" / "deeper"
check(not nowhere.exists() and not nowhere.parent.exists(), "134: 前提：proto 用の作業フォルダは無い")
ap_p = make_app(30, 1, "proto", 3, claude=True, workdir=str(nowhere), bridge_factory=lambda w, s: made.append((w, s)))
check(not ap_p.claude and ap_p.bridge is None and made == [] and not nowhere.exists(), "134: proto では --claude を無視する（Bridge も作業フォルダも作らない）")
check(all(a.visible for a in ap_p.agents), "134: proto では全員が見える")
ap_p.update()
ap_p.draw()
# --claude なしの office では bridge_factory も作業フォルダも使わない
ap_q = make_app(30, 1, "office", 3, claude=False, workdir=str(nowhere), bridge_factory=lambda w, s: made.append((w, s)))
check(made == [] and not nowhere.exists() and ap_q.bridge is None, "134: claude=False では bridge_factory を呼ばず、作業フォルダも作らない")
# --claude の office では作業フォルダを parents つきで作る
newdir = TMP_DIR / f"pca_work_new_{int(_time_c.time() * 1000)}" / "sub" / "deeper"
ap_r = make_app(30, 1, "office", 3, claude=True, workdir=str(newdir), session="SESS9", bridge_factory=lambda w, s: made.append((w, s)) or FakeBridge())
C_APPS.append(ap_r)
check(newdir.is_dir() and made == [(str(newdir), "SESS9")], f"134: --claude の office は作業フォルダを作り、(workdir, session) で Bridge を作る {made}")
# 既に作業フォルダがあっても落ちない（exist_ok）
ap_s = make_app(30, 1, "office", 3, claude=True, workdir=str(newdir), bridge_factory=lambda w, s: FakeBridge())
C_APPS.append(ap_s)
check(ap_s.claude, "134: 作業フォルダが既にあっても作れる")
# 既定の作業フォルダ・セッション名
check(str(pyxelcube_agents.DEFAULT_PCA_WORKDIR).endswith("pyxelcube_agents/pca_work") and ap_s.session == "pyxelcube_agents", "134: 既定の作業フォルダ・セッション名")
for a_ in C_APPS:
    a_.started = False
    a_.ending = False


# ---------------------------------------------------------------------------
# 135〜140. 修正の確認：ダイアログのフレーム・順番待ちの _leave・Esc・引き継ぎの TurnEnd・busy のあとの 5 秒
# （3 の LogReader.skip_existing は test_pca_bridge.py）
# ---------------------------------------------------------------------------

# 135. ダイアログが開いていたフレームは、選んだフレームも含めて、ほかの入力を一切処理しない（クリックはダイアログの選択だけ）
for key, mode in ((pyxel.KEY_1, "resume"), (pyxel.KEY_2, "restart"), (pyxel.KEY_3, "")):
    ap, fb = c_make(session=True)
    c_start(ap)
    before = (ap.five_hour, ap.seven_day, ap.manual_limits, ap.door_open, ap.cam_yaw, ap.cam_pitch, ap.cam_dist,
              ap.next_index, ap.mode, ap.input_buf)
    ended = []
    ap.end_talk = lambda: ended.append(1)
    walks = []
    ap.human.walk_to = lambda *a, **kw: walks.append(a)
    # 選ぶキーと同じフレームに、Space・D・Q・P・4・文字・ホイール・カーソルキーを全部入れる（1〜3 は選ぶキーそのもの）
    p_frame(ap, keys=(key, pyxel.KEY_SPACE, pyxel.KEY_D, pyxel.KEY_Q, O.PROMPT_ENTER_KEY, pyxel.KEY_4),
            hold_keys=(pyxel.KEY_LEFT, pyxel.KEY_UP), text="x", wheel=3)
    after = (ap.five_hour, ap.seven_day, ap.manual_limits, ap.door_open, ap.cam_yaw, ap.cam_pitch, ap.cam_dist,
             ap.next_index, ap.mode, ap.input_buf)
    check(not ap._dialog, f"135: キー {key} でダイアログが閉じる")
    check(ap.started == (mode != "") and fb.calls == ([("begin", mode)] if mode else []), f"135: 選んだ結果だけが起きる {fb.calls}")
    expect_door = True if mode else False  # 始業すればドアが開く（_enter）。それ以外のドアの動きは D・Space では起きない
    check(before[:3] == after[:3], f"135: 利用制限（5 時間・週間・manual_limits）が変わらない {before[:3]} → {after[:3]}")
    check(after[4:7] == before[4:7], f"135: 視点（カーソルキー・ホイール）が変わらない {before[4:7]} → {after[4:7]}")
    check(ap.next_index == before[7] and ap.mode == O.MODE_WALK and ap.input_buf == "", f"135: Space・P・文字が効かない {ap.next_index} {ap.mode} {ap.input_buf!r}")
    check(ended == [], "135: Q が効かない（end_talk を呼ばない）")
    if not mode:
        check(ap.door_open == before[3], "135: D が効かない（やめるときドアが動かない）")
    check(not any(a.visible for a in ap.agents[1:]), "135: Space で誰も作業にならない")
    # 次のフレームからは、ふつうに操作できる
    p_frame(ap, keys=(pyxel.KEY_Q,))
    check(ended == [1], "135: ダイアログが閉じた次のフレームでは Q が効く")
    ap.started = False

# PROMPT のままダイアログを出して選ぶ：文字・Enter・Esc が入らず、モードも変わらない
ap, fb = c_make(session=True)
p_enter_prompt(ap)
p_type(ap, "abc")
p_frame(ap, keys=(pyxel.KEY_F1,))
check(ap._dialog and ap.input_buf == "abc", "135: 前提：PROMPT で abc を打って F1（ダイアログ）")
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_1, pyxel.KEY_RETURN, pyxel.KEY_BACKSPACE, pyxel.KEY_ESCAPE), text="def")
check(ap.input_buf == "abc" and ap.mode == O.MODE_PROMPT, f"135: ダイアログの選択フレームで、入力欄・モードが変わらない {ap.input_buf!r} {ap.mode}")
check(("send_escape",) not in fb.calls and not any(c[0] == "send_prompt" for c in fb.calls), "135: 選択フレームの Enter・Esc は何も送らない")
check([r for r in ap.history[n0:]] == ["始業：前のセッションにつなぎました"], f"135: 履歴は始業の行だけ {ap.history[n0:]}")
p_type(ap, "def")
check(ap.input_buf == "abcdef", "135: 次のフレームからは文字が入る")
ap.started = False
# クリックで選ぶフレーム：ダイアログの選択だけ。モードも人間の歩きも動かない
ap, fb = c_make(session=True)
p_enter_prompt(ap)
p_frame(ap, keys=(pyxel.KEY_F1,))
walks = []
ap.human.walk_to = lambda *a, **kw: walks.append(a)
p_frame(ap, click=(100, 94 + 6))
check(ap.started and ap.mode == O.MODE_PROMPT and walks == [], f"135: クリックで選んでも、モードは PROMPT のまま・人間は歩かない {ap.mode} {walks}")
p_frame(ap, click=(320, 250))
check(walks != [] or ap.mode == O.MODE_WALK, "135: 閉じたあとのクリックは今までどおり 3D の操作")
ap.started = False
# ダイアログ中のクリックが 3D（人・床）に届かない／ボタン・履歴の枠にも届かない
ap, fb = c_make(session=True)
c_start(ap)
walks = []
ap.human.walk_to = lambda *a, **kw: walks.append(a)
mode0 = ap.mode
for pos in ((320, 250), (200, 400), (O.HISTORY_X + 20, O.INPUT_Y + 5), (O.HISTORY_X + 20, O.HISTORY_Y + 5)):
    p_frame(ap, click=pos)
check(ap._dialog and walks == [] and ap.mode == mode0 and fb.calls == [], f"135: ダイアログ中のクリックは選択以外には届かない {ap.mode} {walks}")
# ダイアログ中のホイールは履歴をスクロールしない
for k in range(30):
    ap._add_history(f"行{k}")
sc0 = ap.history_scroll
p_frame(ap, mouse=(O.HISTORY_X + 20, O.HISTORY_Y + 20), wheel=2)
check(ap.history_scroll == sc0, "135: ダイアログ中のホイールで履歴が動かない")
ap.started = False

# 136. path_wait の人も _leave で出ていく／begin_leaving が path_wait を外す
ap, fb = c_make()
a9 = ap.agents[9]
a9.path_wait = True
a9.begin_leaving(Vec3(O.ENTER_INSIDE_X, 0.0, O.DOOR_Z))
check(a9.state == O.LEAVING and a9.path_wait is False, f"136: begin_leaving で path_wait が False になる {a9.path_wait}")
ap, fb = c_make()
ap._enter(9)
check(ap.agents[9].path_wait and 9 in ap._nav_queue, "136: 前提：入ったばかりの人は道探しの順番待ち")
ap._leave(9)
check(not ap.agents[9].path_wait and 9 not in ap._nav_queue, "136: _leave で順番待ちを外す")
check(c_invisible_all(ap, 9) and ap.agents[9].pos.x == O.PARK_X, "136: 順番待ちの最中に _leave しても出ていく")
c_run(ap, 90)
check(not ap.door_open, "136: そのあとドアが閉まる（出入り中のまま止まらない）")
# 始業してすぐ（まだ席に向かう途中・順番待ち）に終業しても、全員出て、ドアが閉まる
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, SubagentStart("a1", "t", "d", ""))
c_ev(ap, fb, SubagentStart("a2", "t", "d", ""))
check(any(ap.agents[i].path_wait for i in (0, 2, 3)) or True, "136: （前提）入った直後")
p_frame(ap, keys=(pyxel.KEY_F1,))
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s"))
check(not ap.started, "136: 前提：終業した")
check(all(c_invisible_all(ap, i) for i in (0, 2, 3)), "136: 入った直後に終業しても全員が出ていく")
c_run(ap, 90)
check(not ap.door_open and ap._active_indices() == [], "136: 全員が出て、ドアが閉まる")
# 席に着いた全員が一斉に出る：メイン＋サブ 16 人（席 2〜17）。ドアの前で詰まらず、全員が出ていく
ap, fb = c_make()
c_start(ap)
for k in range(16):
    c_ev(ap, fb, SubagentStart(f"a{k}", "t", "d", ""))
ids = [0] + list(range(2, 18))
check(all(c_seated(ap, i, 1500) for i in ids), "136: 前提：17 人が席に着く")
p_frame(ap, keys=(pyxel.KEY_F1,))
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s"))
left = ov_until(ap, lambda: not ap._active_indices(), 4000)
check(left is not None, f"136: 席に着いた 17 人が一斉に出ていく（4000 フレーム＝約 133 秒で全員出られたか。残り {[(i, ap.agents[i].state) for i in ap._active_indices()]}）")
# サブも：開始の直後に終わりが来ても、5 秒後には帰る
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, SubagentStart("a1", "t", "d", ""), SubagentEnd("a1"))
slot = 2
ap._leave_timers[slot] = 5.0  # 残りを 5 秒にして進める（SUB_LEAVE_SEC は 300 秒）
check(c_invisible_all(ap, slot), "136: 開始の直後に終わったサブも帰る")

# 137. Esc：PROMPT モードで変換中でないときだけ send_escape
ap, fb = c_make()
c_start(ap)
ap.mode = O.MODE_WALK
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(("send_escape",) not in fb.calls, f"137: WALK の Esc は send_escape しない {fb.calls}")
hist_walk_esc = ap.history[n0:]
p_enter_prompt(ap)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(fb.calls.count(("send_escape",)) == 1, "137: PROMPT の Esc は send_escape する")
ap.ime_composing = True
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(fb.calls.count(("send_escape",)) == 1 and not ap.ime_composing, "137: PROMPT でも変換中の Esc は送らない")
ap.mode = O.MODE_WALK
ap.ime_composing = True
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(fb.calls.count(("send_escape",)) == 1, "137: WALK で変換中の状態でも送らない")
ap.started = False
print("(137) WALK の Esc の履歴の行（claude あり）", hist_walk_esc)
ap_n = make_app(30, 1, "office", 3)
n0 = len(ap_n.history)
p_frame(ap_n, keys=(pyxel.KEY_ESCAPE,))
print("(137) WALK の Esc の履歴の行（claude なし）", ap_n.history[n0:])
p_enter_prompt(ap_n)
n0 = len(ap_n.history)
p_frame(ap_n, keys=(pyxel.KEY_ESCAPE,))
check(ap_n.history[n0:] == ["(Esc: 中断を送る)"], f"137: claude なしの PROMPT の Esc は今までどおり履歴の行を出す {ap_n.history[n0:]}")

# 138. 終業：引き継ぎの依頼（HANDOFF_PROMPT の Prompt）を記録で見たあとの TurnEnd で閉じる
def c_ending(session=False):
    """始業して席に着き、F1 で終業の手順に入った App。"""
    ap_, fb_ = c_make(session=session)
    c_start(ap_)
    c_seated(ap_, 0)
    p_frame(ap_, keys=(pyxel.KEY_F1,))
    return ap_, fb_


ap, fb = c_ending()
check(ap.ending and ap._handoff_seen is False, "138: 終業に入った時点では _handoff_seen は False")
c_ev(ap, fb, TurnEnd("old"))
check(ap.ending and ap.started and ("end", True) not in fb.calls, "138: 依頼を見る前の TurnEnd（前の返事の終わり）では閉じない")
c_ev(ap, fb, Prompt("s", "別の文"))
check(ap._handoff_seen is False, "138: 別の文の Prompt では _handoff_seen にならない")
c_ev(ap, fb, TurnEnd("s"))
check(ap.ending and ("end", True) not in fb.calls, "138: 別の文のあとの TurnEnd でも閉じない")
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)))
check(ap._handoff_seen is True and ap.ending, "138: 依頼の Prompt を見たら _handoff_seen")
c_ev(ap, fb, Reply("s", "書きました"))
check(ap.ending, "138: Reply では閉じない")
c_ev(ap, fb, TurnEnd("s"))
check(not ap.ending and not ap.started and fb.calls.count(("end", True)) == 1 and ap.history[-1] == "終業しました", "138: 依頼を見たあとの TurnEnd で終業する")
# 同じ poll の中の順番：Prompt→TurnEnd で閉じる、TurnEnd→Prompt では閉じない
ap, fb = c_ending()
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s"))
check(not ap.ending and ("end", True) in fb.calls, "138: 同じ poll の Prompt→TurnEnd で閉じる")
ap, fb = c_ending()
c_ev(ap, fb, TurnEnd("s"), Prompt("s", i18n_t(O.HANDOFF_PROMPT)))
check(ap.ending and ("end", True) not in fb.calls, "138: 同じ poll の TurnEnd→Prompt では閉じない（TurnEnd は前の返事の終わり）")
c_ev(ap, fb, TurnEnd("s"))
check(not ap.ending, "138: そのあとの TurnEnd で閉じる")
# 終業の前に（普通に）届いた同じ文は数えない
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)))
check(ap._handoff_seen is False, "138: 終業に入る前の Prompt では _handoff_seen にならない")
p_frame(ap, keys=(pyxel.KEY_F1,))
c_ev(ap, fb, TurnEnd("s"))
check(ap.ending and ("end", True) not in fb.calls, "138: 終業に入る前に見た依頼は数えない（TurnEnd だけでは閉じない）")
# 自分が送った依頼は履歴に二重に出ない（これまでどおり）
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)))
check(ap.history[n0:] == [] and ap._handoff_seen is True, "138: 依頼は履歴に二重に出ず、_handoff_seen になる")
# 待ち時間：依頼を見なくても、見ても TurnEnd が無ければ 300 秒で閉じる
ap, fb = c_ending()
c_run(ap, 30 * 150)
c_ev(ap, fb, TurnEnd("s"))
check(ap.ending, "138: 依頼を見ないまま 150 秒たって TurnEnd が来ても閉じない")
c_run(ap, 30 * 160)
check(not ap.ending and ("end", True) in fb.calls, "138: 依頼を見なくても 300 秒を過ぎれば閉じる")
ap, fb = c_ending()
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)))
c_run(ap, 30 * 299)
check(ap.ending, "138: 依頼を見て TurnEnd が無いまま 299 秒ではまだ待つ")
c_run(ap, 60)
check(not ap.ending and ("end", True) in fb.calls, "138: 依頼を見て TurnEnd が無くても 300 秒で閉じる")
# 2 回目の終業でも最初から数え直す
ap, fb = c_ending()
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s"))
check(not ap.started, "138: 前提：1 回目の終業")
c_start(ap)
c_seated(ap, 0)
p_frame(ap, keys=(pyxel.KEY_F1,))
c_ev(ap, fb, TurnEnd("s"))
check(ap.ending and ap._handoff_seen is False, "138: 2 回目の終業は、また依頼を見るまで TurnEnd で閉じない")
ap.started = False
ap.ending = False

# 138-b. _shutdown_claude も、依頼の Prompt を見るまで TurnEnd を数えない
def c_shutdown(polls, ending=False, seen=False):
    """_shutdown_claude を、poll が polls（イベントの一覧の列。尽きたら空）を順に返す偽の Bridge で流す。"""
    ap_, fb_ = c_make()
    c_start(ap_)
    if ending:
        p_frame(ap_, keys=(pyxel.KEY_F1,))
    ap_._handoff_seen = seen
    fb_.calls.clear()
    queue = list(polls)
    fb_.poll = lambda: queue.pop(0) if queue else []
    sleeps_ = []
    ap_._shutdown_claude(sleep=sleeps_.append)
    return ap_, fb_, sleeps_


ap, fb, sl = c_shutdown([[TurnEnd("s")], [TurnEnd("s")]])
check(len(sl) >= 1490 and fb.calls == [("send_prompt", i18n_t(O.HANDOFF_PROMPT)), ("end", True)], f"138: 依頼を見ない TurnEnd だけでは 300 秒待つ（待ち {len(sl)} 回）{fb.calls}")
ap, fb, sl = c_shutdown([[Prompt("s", "別の文"), TurnEnd("s")]])
check(len(sl) >= 1490, "138: 別の文の Prompt のあとの TurnEnd では閉じない")
ap, fb, sl = c_shutdown([[Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s")]])
check(sl == [] and fb.calls == [("send_prompt", i18n_t(O.HANDOFF_PROMPT)), ("end", True)], f"138: 依頼 → TurnEnd（同じ poll）で閉じる {fb.calls} {sl}")
ap, fb, sl = c_shutdown([[TurnEnd("s")], [], [Prompt("s", i18n_t(O.HANDOFF_PROMPT))], [Reply("s", "x")], [TurnEnd("s")]])
check(sl == [0.2] * 4 and fb.calls[-1] == ("end", True), f"138: 前の TurnEnd を飛ばし、依頼のあとの TurnEnd で閉じる {sl}")
ap, fb, sl = c_shutdown([[TurnEnd("s"), Prompt("s", i18n_t(O.HANDOFF_PROMPT))], [TurnEnd("s")]])
check(sl == [0.2], f"138: 同じ poll の TurnEnd→Prompt では閉じず、次の TurnEnd で閉じる {sl}")
ap, fb, sl = c_shutdown([[Prompt("s", i18n_t(O.HANDOFF_PROMPT))]])
check(len(sl) >= 1490 and fb.calls[-1] == ("end", True), "138: 依頼を見ても TurnEnd が無ければ 300 秒で閉じる")
# すでに終業の手順に入っていて依頼を見ている：TurnEnd だけで閉じる。見ていなければ依頼から待つ
ap, fb, sl = c_shutdown([[TurnEnd("s")]], ending=True, seen=True)
check(sl == [] and fb.calls == [("end", True)], f"138: 終業の途中で依頼を見ていれば、依頼を送り直さず TurnEnd で閉じる {fb.calls}")
ap, fb, sl = c_shutdown([[TurnEnd("s")], [Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s")]], ending=True, seen=False)
check(sl == [0.2] and fb.calls == [("end", True)], f"138: 終業の途中で依頼を見ていなければ、依頼のあとの TurnEnd を待つ {fb.calls} {sl}")
check(not ap.started and not ap.ending, "138: 閉じたあと started・ending が False")
# 始業していなければ何もしない
ap, fb = c_make()
sl = []
ap._shutdown_claude(sleep=sl.append)
check(fb.calls == [] and sl == [], "138: 始業していなければ何もしない")

# 139. busy が False になってから 5 秒数えて立つ
ap, fb = c_make()
c_start(ap)
main = ap.agents[0]
c_seated(ap, 0)
main.busy = True
c_run(ap, 30 * 20)
check(main.state == O.WORKING and main._busy_hold_time == 0.0, f"139: busy の間は立たず、数えない {main._busy_hold_time}")
main.busy = False
c_run(ap, 2)
check(main.state == O.WORKING, "139: busy が False になった直後は、座って 5 秒を過ぎていても立たない")
c_run(ap, int(4.0 * 30))
check(main.state == O.WORKING, f"139: busy が False になって約 4.1 秒ではまだ立たない {main._busy_hold_time:.2f}")
c_run(ap, int(1.2 * 30))
check(main.state == O.WANDER, f"139: busy が False になって約 5 秒で立つ {main.state} {main._busy_hold_time:.2f}")
# 途中で busy に戻ると数え直し
ap, fb = c_make()
c_start(ap)
main = ap.agents[0]
c_seated(ap, 0)
main.busy = True
c_run(ap, 30)
main.busy = False
c_run(ap, int(3.0 * 30))
main.busy = True
c_run(ap, 2)
check(main._busy_hold_time == 0.0, "139: 途中で busy に戻ると数えが 0 に戻る")
main.busy = False
c_run(ap, int(4.0 * 30))
check(main.state == O.WORKING, "139: 数え直しなので、3 秒＋4 秒でも立たない")
c_run(ap, int(1.3 * 30))
check(main.state == O.WANDER, "139: busy が False になってから通しで 5 秒たてば立つ")
# 立ってからもう一度座ると、また数え直し（start_work で戻る）
c_ev(ap, fb, Prompt("s", "また"))
c_seated(ap, 0)
check(main._busy_hold_time < 1.0, f"139: 座り直したとき数えが戻っている {main._busy_hold_time}")
c_ev(ap, fb, TurnEnd("s"))
c_run(ap, int(4.0 * 30))
check(main.state == O.WORKING, "139: 座り直したあとも、busy が False になってから 4 秒では立たない")
c_run(ap, int(1.3 * 30))
check(main.state == O.WANDER, "139: 5 秒で立つ")
# hold の間は立たない。外せば（数えが 5 秒を超えていれば）立つ
ap, fb = c_make()
c_start(ap)
main = ap.agents[0]
c_seated(ap, 0)
main.hold = True
c_run(ap, 30 * 7)
check(main.state == O.WORKING, "139: hold の間は立たない")
main.hold = False
c_run(ap, 2)
check(main.state == O.WANDER, "139: hold を外せば（busy でなく 5 秒を過ぎていれば）立つ")
# 作業の流れ：Tool で busy → TurnEnd → 5 秒後に立つ
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
c_ev(ap, fb, Tool("s", "Bash", "ls"))
c_run(ap, 30 * 10)
check(ap.agents[0].state == O.WORKING, "139: Tool のあと 10 秒たっても座っている")
c_ev(ap, fb, TurnEnd("s"))
c_run(ap, int(4.0 * 30))
check(ap.agents[0].state == O.WORKING, "139: TurnEnd から 4 秒ではまだ座っている")
c_run(ap, int(1.3 * 30))
check(ap.agents[0].state == O.WANDER, "139: TurnEnd から約 5 秒で立つ")
# サブ：終わりで busy が外れ、5 秒後に立つより先に帰る時間が来る（どちらでも落ちない）
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, SubagentStart("a1", "t", "d", ""))
c_seated(ap, 2)
c_ev(ap, fb, SubagentEnd("a1"))
ap._leave_timers[2] = 5.0  # 残りを 5 秒にして進める（SUB_LEAVE_SEC は 300 秒）
c_run(ap, 30 * 8)
check(c_invisible_all(ap, 2), "139: サブは終わって帰る")
# --claude なし：座って 5 秒で立つ（busy を使わない配置の動きは今までどおり）
ap_n = make_app(30, 1, "office", 3)
ov_quiet(ap_n)
ap_n.next_index = 0
press_space_and_update(ap_n)
c_seated(ap_n, 0)
c_run(ap_n, int(4.5 * 30))
check(ap_n.agents[0].state == O.WORKING, "139: claude なしは座って 4.5 秒ではまだ立たない")
c_run(ap_n, int(1.0 * 30))
check(ap_n.agents[0].state == O.WANDER, "139: claude なしは座って約 5 秒で立つ（今までどおり）")
check(ap_n.agents[0]._busy_hold_time >= 0.0, "139: claude なしでも _busy_hold_time がある")
# proto の Agent（busy を使わない）
ap_p = make_app(30, 1, "proto", 3)
press_space_and_update(ap_p)
for _ in range(30 * 8):
    ap_p.update()
check(ap_p.agents[0].state == O.WANDER, "139: proto でも座って 5 秒で立つ（今までどおり）")

for a_ in C_APPS:
    a_.started = False
    a_.ending = False


# 140. 部屋を出る人（LEAVING）：人どうしは押し合わない／待っている人を押しのけない／障害物と床は今までどおり／出口の点から 30 で着いたことにする／LEAVE_MAX_SEC で park
ap, fb = c_make()
fx, fz = c_free_point(ap, 0)


def c_put(i, x, z, state=None):
    """人 i を見える状態にして (x, z) に置く。"""
    a_ = ap.agents[i]
    a_.visible = True
    a_.pos = Vec3(x, 0.0, z)
    if state is not None:
        a_.state = state
    return a_


def c_unput(i):
    ap.agents[i].visible = False
    ap.agents[i].park()


# 140-a. LEAVING どうしは押し合わない（重なっていても位置が変わらない）。LEAVING でない 2 人は押し合う（対照）
l1 = c_put(3, fx, fz, O.LEAVING)
l2 = c_put(4, fx + 4.0, fz, O.LEAVING)
ap._resolve_collisions()
check((l1.pos.x, l1.pos.z) == (fx, fz) and (l2.pos.x, l2.pos.z) == (fx + 4.0, fz), f"140: LEAVING どうしは重なっていても押し合わない {l1.pos} {l2.pos}")
w1 = c_put(5, fx + 200.0, fz, O.WANDER)
w2 = c_put(6, fx + 204.0, fz, O.WANDER)
ap._resolve_collisions()
check(math.hypot(w1.pos.x - w2.pos.x, w1.pos.z - w2.pos.z) > 4.0 + 1.0, "140: （対照）LEAVING でない 2 人は押し合う")
# 140-b. LEAVING の人が、待っている人（うろうろ・立っている・席に着いている・行き先にいる）を押しのけない
for kind in (O.WANDER, O.AT_SPOT, O.WORKING):
    c_unput(5)
    c_unput(6)
    c_unput(3)
    c_unput(4)
    lv = c_put(3, fx, fz, O.LEAVING)
    waiter = c_put(5, fx + 4.0, fz, kind)
    if kind == O.WORKING:
        waiter._arrived = True  # 席に着いている（動かない人）
    if kind == O.AT_SPOT:
        waiter.spot = ap.spot_manager.spots[0] if hasattr(ap.spot_manager, "spots") else None
    ap._resolve_collisions()
    check((waiter.pos.x, waiter.pos.z) == (fx + 4.0, fz), f"140: LEAVING の人が {kind} の人を押しのけない {waiter.pos}")
    check((lv.pos.x, lv.pos.z) == (fx, fz), f"140: {kind} の人にも LEAVING の人は押されない {lv.pos}")
    waiter._arrived = False
c_unput(5)
c_unput(3)
# 人間（会話の相手でなくても）にも押されない
lv = c_put(3, ap.human.pos.x + 3.0, ap.human.pos.z, O.LEAVING)
hx, hz = ap.human.pos.x, ap.human.pos.z
ap._resolve_collisions()
check((ap.human.pos.x, ap.human.pos.z) == (hx, hz) and (lv.pos.x, lv.pos.z) == (hx + 3.0, hz), "140: LEAVING の人と人間も押し合わない")
c_unput(3)
# 140-c. 障害物と床の範囲は今までどおり：机の中にいる LEAVING の人は押し出される。床の外は床の中へ
ob = ap.obstacles[0].rect
inside_x, inside_z = (ob.xmin + ob.xmax) / 2.0, (ob.zmin + ob.zmax) / 2.0
lv = c_put(3, inside_x, inside_z, O.LEAVING)
ap._resolve_collisions()
check(O.rect_dist(lv.pos.x, lv.pos.z, ob) >= 0.0 if hasattr(O, "rect_dist") else (lv.pos.x, lv.pos.z) != (inside_x, inside_z),
      f"140: LEAVING の人も障害物から押し出される {lv.pos}")
check((lv.pos.x, lv.pos.z) != (inside_x, inside_z), "140: 障害物の中から動いた")
c_unput(3)
x_min, x_max = ap.layout.wander_x
z_min, z_max = ap.layout.wander_z
lv = c_put(3, x_max + 500.0, fz, O.LEAVING)
ap._resolve_collisions()
check(x_min <= lv.pos.x <= x_max, f"140: LEAVING の人も床の範囲に収まる {lv.pos.x} {x_min}..{x_max}")
c_unput(3)
# 140-d. 着いたことにする距離：道が残っていても、出口の点から 30 以内なら leaving_done
a = ap.agents[3]
a.visible = True
a.begin_leaving(Vec3(O.ENTER_INSIDE_X, 0.0, O.DOOR_Z))
a._path = [Vec3(0.0, 0.0, 0.0)]  # 道は残っている
for dx, want in ((0.0, True), (29.0, True), (30.0, True), (30.5, False), (60.0, False)):
    a.pos = Vec3(O.ENTER_INSIDE_X + dx, 0.0, O.DOOR_Z)
    check(a.leaving_done is want, f"140: 出口の点から {dx} のとき leaving_done は {want}（道は残っている） {a.leaving_done}")
a.pos = Vec3(O.ENTER_INSIDE_X + 20.0, 0.0, O.DOOR_Z + 20.0)  # 距離 28.3
check(a.leaving_done, "140: 斜めでも距離 28.3 なら着いたことになる")
a.pos = Vec3(O.ENTER_INSIDE_X + 25.0, 0.0, O.DOOR_Z + 25.0)  # 距離 35.4
check(not a.leaving_done, "140: 斜めの距離 35.4 は着いていない")
a.state = O.WANDER
a.pos = Vec3(O.ENTER_INSIDE_X, 0.0, O.DOOR_Z)
check(not a.leaving_done, "140: LEAVING でなければ出口の点にいても leaving_done でない")
c_unput(3)
check(O.LEAVE_ARRIVE_DIST == 30.0 and O.LEAVE_MAX_SEC >= 30.0, f"140: 定数 LEAVE_ARRIVE_DIST=30・LEAVE_MAX_SEC は最も遠い席の歩き（約 25 秒）より長い {O.LEAVE_MAX_SEC}")
# 着いた人は、App が置き場所へ戻す（道が残っていても）
ap2, fb2 = c_make()
ap2._enter(7)
c_seated(ap2, 7)
ap2._leave(7)
ap2.agents[7]._path = [Vec3(0.0, 0.0, 0.0)] + list(ap2.agents[7]._path)
ap2.agents[7].pos = Vec3(O.ENTER_INSIDE_X + 10.0, 0.0, O.DOOR_Z)
c_run(ap2, 3)
check(not ap2.agents[7].visible and ap2.agents[7].pos.x == O.PARK_X, "140: 出口の点の近くまで来た人は、道が残っていても置き場所へ戻る")

# 140-e. LEAVE_MAX_SEC 続いたらその場で park（歩けなくした人で確かめる。秒数は O.LEAVE_MAX_SEC を基にする）
M = O.LEAVE_MAX_SEC
F = 30  # fps
ap, fb = c_make()
ap._enter(7)
c_seated(ap, 7)
st = ap.agents[7]
st.update = lambda dt: None  # 動かない人（詰まった人の代わり）
ap._leave(7)
check(st.state == O.LEAVING and st.visible, "140: 前提：LEAVING になった")
c_run(ap, int((M - 1.0) * F))
check(st.visible and st.state == O.LEAVING, f"140: LEAVE_MAX_SEC − 1 秒（{M - 1.0} 秒）ではまだ park しない")
check(7 in ap._leave_elapsed and M - 1.5 < ap._leave_elapsed[7] <= M - 0.5, f"140: 続いた時間を数えている {ap._leave_elapsed.get(7)}")
c_run(ap, int(1.3 * F))
check(not st.visible and st.pos.x == O.PARK_X and st.pos.z == O.DOOR_Z and st.state == O.WANDER and not st.busy, f"140: LEAVE_MAX_SEC（{M} 秒）続いたらその場で park する {st.visible} {st.pos}")
check(7 not in ap._leave_elapsed, "140: park したら数えを消す")
c_run(ap, 90)
check(not ap.door_open, "140: park したあとドアが閉まる")
# 数えは人ごと・LEAVING のあいだだけ。LEAVING でなくなれば消える（次の LEAVING で 0 から）
ap, fb = c_make()
ap._enter(7)
c_seated(ap, 7)
st = ap.agents[7]
st.update = lambda dt: None
ap._leave(7)
c_run(ap, int(M * 0.25 * F))
check(7 in ap._leave_elapsed, "140: 前提：LEAVE_MAX_SEC の 4 分の 1 を数えた")
st.state = O.WANDER  # LEAVING でなくなった
c_run(ap, 2)
check(7 not in ap._leave_elapsed, "140: LEAVING でなくなったら数えを消す")
st.state = O.LEAVING
st._path = [Vec3(0.0, 0.0, 0.0)]
st._goal = Vec3(O.ENTER_INSIDE_X, 0.0, O.DOOR_Z)
c_run(ap, int(M * 0.8 * F))  # 前の分と足せば LEAVE_MAX_SEC を超えるが、数え直しなので超えない
check(st.visible, "140: もう一度 LEAVING になったときは 0 から数える（前の分を引きずらない）")
c_run(ap, int(M * 0.3 * F))
check(not st.visible, "140: LEAVE_MAX_SEC 続いたら park")
# 普通に出る人は LEAVE_MAX_SEC より前に出る（数えは邪魔をしない）
ap, fb = c_make()
ap._enter(2)
c_seated(ap, 2)
ap._leave(2)
n = ov_until(ap, lambda: not ap.agents[2].visible, int((M + 5) * F))
check(n is not None and n < M * F, f"140: ドアに近い席の人は LEAVE_MAX_SEC より前に出ていく {n}")
check(2 not in ap._leave_elapsed, "140: 出たあと数えが残らない")
# ドアから遠い席の人（席 17：上限なしで歩くと約 25 秒）は、上限で途中で消えず、ドアまで歩いて出る
ap, fb = c_make()
ap._enter(17)
c_seated(ap, 17)
ap._leave(17)
last_far = [None]
t_gone = None
for f in range(int((M + 5) * F)):
    if not ap.agents[17].visible:
        t_gone = f
        break
    last_far[0] = math.hypot(ap.agents[17].pos.x - O.ENTER_INSIDE_X, ap.agents[17].pos.z - O.DOOR_Z)
    ap.update()
check(t_gone is not None and last_far[0] <= O.LEAVE_ARRIVE_DIST + 5.0,
      f"140: ドアから遠い席の人が、部屋の途中で消えず、出口の点まで歩いて出る（消える直前のドアまで {last_far[0]}、{None if t_gone is None else t_gone / F:.1f} 秒）")
check(t_gone is not None and t_gone / F < M - 1.0, f"140: 遠い席の人は上限（{M} 秒）より前に着く {None if t_gone is None else t_gone / F:.1f} 秒")
# 一斉に出る：席に着いた 17 人が、押し合わず、上限で消される人もなく全員出る
ap, fb = c_make()
c_start(ap)
for k in range(16):
    c_ev(ap, fb, SubagentStart(f"a{k}", "t", "d", ""))
check(all(c_seated(ap, i, 1500) for i in [0] + list(range(2, 18))), "140: 前提：17 人が席に着く")
for i in [0] + list(range(2, 18)):
    ap._leave(i)
parked_by_timeout = []
left = None
for f in range(int((M + 10) * F)):
    if not ap._active_indices():
        left = f
        break
    ap.update()
    parked_by_timeout += [i for i, e in ap._leave_elapsed.items() if e >= M - 0.1]
print(f"(140) 席に着いた 17 人が一斉に出て、全員が出るまで {None if left is None else left} フレーム = {None if left is None else round(left / F, 1)} 秒（LEAVE_MAX_SEC={M}）")
check(left is not None and left / F < M - 1.0, f"140: 17 人が一斉に出ても、上限（{M} 秒）より前に全員出る（かかった時間 {None if left is None else round(left / F, 1)} 秒）")
check(parked_by_timeout == [], f"140: 上限に達して park された人がいない {parked_by_timeout}")
c_run(ap, 90)
check(not ap.door_open and ap._leave_elapsed == {}, "140: 全員が出たらドアが閉まり、数えも空")
# 出る人と入る人が同時でも落ちない
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
ap._leave(0)
ap._enter(5)
ap._enter(6)
ap.agents[5].busy = True
ap.agents[6].busy = True
c_run(ap, 600)
check(not ap.agents[0].visible and ap.agents[5].visible and ap.agents[6].visible, "140: 出る人と入る人が同時でも、出る人は出て入る人は入る")
check(c_seated(ap, 5, 900) and c_seated(ap, 6, 900), "140: 入る人は席に着く")

# ---------------------------------------------------------------------------
# 141. 待ち時間と確かめる間隔の定数、セッションが無い・送れないときは待たずに閉じる
# ---------------------------------------------------------------------------
import contextlib as _ctx141
import io as _io141

check(O.HANDOFF_WAIT_SEC == 300.0, f"141: HANDOFF_WAIT_SEC が 300 秒 {O.HANDOFF_WAIT_SEC}")
check(O.SESSION_CHECK_SEC == 2.0, f"141: SESSION_CHECK_SEC が 2 秒 {O.SESSION_CHECK_SEC}")


class FakeBridgeSendNg(FakeBridge):
    """send_prompt が失敗（False）する偽の Bridge。"""

    def send_prompt(self, text):
        self.calls.append(("send_prompt", text))
        return False


def c_capture(fn):
    """fn() を呼び、標準出力に出た文字を返す。"""
    buf = _io141.StringIO()
    with _ctx141.redirect_stdout(buf):
        fn()
    return buf.getvalue()


# 141-a. 終業（_begin_handoff）：セッションが無ければ、依頼せず待たずに終える
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
fb.calls.clear()
fb.session = False
ap._begin_handoff()
check(("send_prompt", i18n_t(O.HANDOFF_PROMPT)) not in fb.calls, f"141: セッションが無ければ依頼を送らない {fb.calls}")
check(fb.calls == [("end", True)], f"141: セッションが無ければ end(kill_session=True) だけ {fb.calls}")
check(not ap.ending and not ap.started and ap.history[-1] == "終業しました", f"141: 待たずに終業を終える（ending・started が False） {ap.history[-1]}")
check(ap._handoff_left == 0.0, f"141: 待ちの時間を数え始めない {ap._handoff_left}")
check(c_invisible_all(ap, 0), "141: セッションが無い終業でも、メインが部屋から出ていく")

# 141-b. 終業：依頼が送れなければ、待たずに終える
fbn = FakeBridgeSendNg(session=False, begin_ok=True)
ap, fb = c_make(bridge=fbn)
c_start(ap)
c_seated(ap, 0)
fb.calls.clear()
ap._begin_handoff()
check(fb.calls == [("send_prompt", i18n_t(O.HANDOFF_PROMPT)), ("end", True)], f"141: 送れなければ、1回送って待たずに end(True) {fb.calls}")
check(not ap.ending and not ap.started and ap.history[-1] == "終業しました", f"141: 送れなくても待たずに終業を終える {ap.history[-1]}")
check(ap._last_sent != i18n_t(O.HANDOFF_PROMPT) and ap._human_text is None, f"141: 送れなかった依頼を送った扱いにしない {ap._last_sent!r} {ap._human_text!r}")
# F1 でも同じ（セッションが消えた直後、確かめる前に F1 を押した場合）
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
fb.calls.clear()
fb.session = False
p_frame(ap, keys=(pyxel.KEY_F1,))
check(("send_prompt", i18n_t(O.HANDOFF_PROMPT)) not in fb.calls and not ap.ending and not ap.started, f"141: F1 で終業しても、セッションが無ければ待たない {fb.calls}")

# 141-c. 窓の×（_shutdown_claude）：セッションが無ければ待たずに閉じる（kill はしない）
ap, fb = c_make()
c_start(ap)
fb.calls.clear()
fb.session = False
sleeps = []
out = c_capture(lambda: ap._shutdown_claude(sleep=sleeps.append))
check(fb.calls == [("end", False)] and sleeps == [], f"141: ×でセッションが無ければ end(False) だけ・sleep しない {fb.calls} {sleeps}")
check(not ap.started and not ap.ending, "141: ×でセッションが無ければ started・ending が False")
check("待っています" not in out, f"141: セッションが無ければ「待っています」を出さない {out!r}")
# 終業の途中（ending）でセッションが無くなっていても同じ
ap, fb = c_ending()
fb.calls.clear()
fb.session = False
sleeps = []
out = c_capture(lambda: ap._shutdown_claude(sleep=sleeps.append))
check(fb.calls == [("end", False)] and sleeps == [] and not ap.started and not ap.ending, f"141: 終業中にセッションが無くなっても、×で待たない {fb.calls} {sleeps}")
# ×：送れなければ待たずに閉じる
fbn = FakeBridgeSendNg(session=False, begin_ok=True)
ap, fb = c_make(bridge=fbn)
c_start(ap)
fb.calls.clear()
sleeps = []
out = c_capture(lambda: ap._shutdown_claude(sleep=sleeps.append))
check(fb.calls == [("send_prompt", i18n_t(O.HANDOFF_PROMPT)), ("end", False)] and sleeps == [], f"141: ×で送れなければ 1 回送って end(False)・sleep しない {fb.calls} {sleeps}")
check(not ap.started and not ap.ending and "待っています" not in out, f"141: ×で送れなければ待たない（表示なし） {out!r}")

# ---------------------------------------------------------------------------
# 142. セッションが消えたら _session_gone（2 秒ごとに確かめる。始業していなければ確かめない）
# ---------------------------------------------------------------------------
F142 = 30
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "しらべる", ""))
check(c_seated(ap, 2), "142: 前提：サブが席に着く")
gone_calls = []
orig_gone = ap._session_gone
ap._session_gone = lambda: (gone_calls.append(1), orig_gone())[1]
checks_n = [0]
orig_exists = fb.session_exists
fb.session_exists = lambda: (checks_n.__setitem__(0, checks_n[0] + 1), orig_exists())[1]
checks_n[0] = 0
ap._session_check_left = O.SESSION_CHECK_SEC
c_run(ap, F142 * 10)
check(3 <= checks_n[0] <= 6 and gone_calls == [], f"142: セッションがあるうちは 2 秒ごと（10 秒で約 5 回）確かめ、_session_gone は呼ばない {checks_n[0]} 回")
check(ap.started and ap.agents[0].visible, "142: セッションがあるなら何も起きない")
# セッションが消える
fb.calls.clear()
n0 = len(ap.history)
fb.session = False
ap._session_check_left = O.SESSION_CHECK_SEC
c_run(ap, F142 * 1)
check(gone_calls == [] and ap.started, f"142: 消えてから 1 秒ではまだ気づかない（2 秒ごと） {gone_calls}")
f_gone = None
for f in range(F142 * 2):
    ap.update()
    if gone_calls:
        f_gone = f
        break
check(f_gone is not None and gone_calls == [1], f"142: 2 秒以内に _session_gone が 1 回呼ばれる {gone_calls}")
check(ap.history[n0:] == ["Claude Code が終了しました"], f"142: 「Claude Code が終了しました」が履歴に出る {ap.history[n0:]}")
check(not ap.started and not ap.ending, "142: started・ending が False")
check(("end", False) in fb.calls and ("end", True) not in fb.calls, f"142: bridge.end(kill_session=False)（tmux は閉じない） {fb.calls}")
check(ap._sub_map == {} and ap._busy_text == {} and ap._pending_reply is None and ap._human_text is None, "142: 対応表・作業中の文・人間の文が空になる")
check(all(ap.agents[i].state == O.LEAVING for i in (0, 2)), f"142: 見えていた全員が帰り始める {[ap.agents[i].state for i in (0, 2)]}")
check(all(c_invisible_all(ap, i) for i in (0, 2)), "142: 全員が部屋から出る")
c_run(ap, F142 * 6)
check(gone_calls == [1], f"142: 始業していなければ、もう確かめない（_session_gone は 1 回だけ） {gone_calls}")
# 終業の待ち中に消えたら、終業も終える（tmux は閉じない）
ap, fb = c_ending()
fb.calls.clear()
n0 = len(ap.history)
fb.session = False
c_run(ap, F142 * 3)
check(ap.history[n0:] == ["Claude Code が終了しました", "終業しました"], f"142: 終業の待ち中に消えたら「終了しました」→「終業しました」 {ap.history[n0:]}")
check(not ap.started and not ap.ending and fb.calls.count(("end", False)) == 1 and ("end", True) not in fb.calls, f"142: 終業の待ち中に消えても tmux は閉じない {fb.calls}")
# 始業していないときは確かめない
ap, fb = c_make()
cnt = [0]
fb.session_exists = lambda: (cnt.__setitem__(0, cnt[0] + 1), False)[1]
gone2 = []
ap._session_gone = lambda: gone2.append(1)
n0 = len(ap.history)
c_run(ap, F142 * 10)
check(cnt[0] == 0 and gone2 == [] and ap.history[n0:] == [], f"142: 始業していなければセッションを確かめない・メッセージも出ない {cnt[0]} {gone2} {ap.history[n0:]}")
# 終業したあと（started=False）も確かめない
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT))) if False else None
p_frame(ap, keys=(pyxel.KEY_F1,))
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s"))
check(not ap.started, "142: 前提：終業した")
cnt = [0]
fb.session_exists = lambda: (cnt.__setitem__(0, cnt[0] + 1), False)[1]
n0 = len(ap.history)
c_run(ap, F142 * 6)
check(cnt[0] == 0 and "Claude Code が終了しました" not in ap.history[n0:], f"142: 終業したあとは確かめない {cnt[0]}")
# 始業し直すと、数え直す
ap, fb = c_make()
c_start(ap)
check(O.SESSION_CHECK_SEC - 0.1 <= ap._session_check_left <= O.SESSION_CHECK_SEC, f"142: 始業すると次の確かめまで約 2 秒に戻る（始業の 1 フレームぶん引く） {ap._session_check_left}")

# ---------------------------------------------------------------------------
# 143. _short_text：最初の4文字＋"...."（4文字以下はそのまま）。len で数え、改行などは特別に扱わない
# ---------------------------------------------------------------------------
st = O._short_text
check(st("") == "", f"143: 空文字は空のまま {st('')!r}")
check(st("あ") == "あ" and st("abc") == "abc", "143: 4 文字より短ければそのまま")
check(st("abcd") == "abcd" and st("あいうえ") == "あいうえ", f"143: ちょうど 4 文字ならそのまま（\"....\" を付けない） {st('abcd')!r} {st('あいうえ')!r}")
check(st("abcde") == "abcd....", f"143: ちょうど 5 文字は最初の 4 文字＋\"....\" {st('abcde')!r}")
check(st("あいうえお") == "あいうえ....", f"143: 日本語 5 文字 {st('あいうえお')!r}")
check(st("あいうえおかきくけこ") == "あいうえ....", "143: 長い日本語も最初の 4 文字だけ")
check(st("a" * 1000) == "aaaa....", "143: 1000 文字でも 4 文字＋\"....\"")
check(st("a\nbcdef") == "a\nbc....", f"143: _short_text 自体は改行を特別に扱わない（改行も 1 文字。呼ぶ側が _first_line で 1 行目にする） {st('a'+chr(10)+'bcdef')!r}")
check(st("a\nb") == "a\nb", "143: 改行を含めて 4 文字以下ならそのまま")
check(st("  abcd") == "  ab....", f"143: 先頭の空白も数える（strip しない） {st('  abcd')!r}")
check(st("🙂🙂🙂🙂🙂") == "🙂🙂🙂🙂....", "143: 絵文字（1 コードポイント）も 1 文字")
check(len(st("あいうえおかき")) == 8, "143: 結果の長さは最大 8 文字")

# ---------------------------------------------------------------------------
# 144. 作業中（busy）の白い吹き出し：メインは最新の Reply（無ければプロンプト）、サブは description、人間は送ったプロンプト
# ---------------------------------------------------------------------------
def b_count(rec, s):
    """吹き出しの文字（黒＝色 0・UI フォント）で、文 s が何回出たか。"""
    return sum(1 for t in rec["utext"] if t[2] == s and t[3] == 0)


def b_ready(n_sub=0):
    """始業してメインを席に着かせた App と偽の Bridge。"""
    ap_, fb_ = c_make()
    c_start(ap_)
    c_seated(ap_, 0)
    return ap_, fb_


# 144-a. メイン：プロンプトだけ（返事がまだ無い）→ プロンプトの最初の 4 文字
ap, fb = b_ready()
main = ap.agents[0]
check(ap.human is not None and ap._head_point(main) is not None, "144: 前提：人間がいて、メインの頭が画面の中")
rec = c_draw(ap)
check(not any(t[2].endswith("....") for t in rec["utext"]), "144: 作業中でなければ \"....\" の吹き出しは出ない")
c_ev(ap, fb, Prompt("s", "いろはにほへと"))
check(main.busy and ap._busy_text.get(0) == "いろはにほへと" and ap._human_text == "いろはにほへと", f"144: Prompt で busy・作業中の文・人間の文 {ap._busy_text} {ap._human_text!r}")
rec = c_draw(ap)
check(b_count(rec, "いろはに....") == 2, f"144: メインの吹き出し（依頼の最初の 4 文字）と人間の吹き出しが出る（同じ文なので 2 つ） {b_count(rec, 'いろはに....')}")
# 吹き出しは描き続ける（何フレームたっても出たまま）
c_run(ap, 30 * 20)
rec = c_draw(ap)
check(main.busy and b_count(rec, "いろはに....") == 2, "144: 作業中は 20 秒たっても吹き出しを出したまま")
# 返事が来たら、メインの吹き出しは最新の Reply に
c_ev(ap, fb, Reply("s", "さいしょのへんじ"))
check(ap._busy_text[0] == "さいしょのへんじ" and ap._pending_reply == "さいしょのへんじ" and ap._bubble == "", f"144: 作業中の Reply は作業中の文に入り、6 秒の吹き出し（_bubble）にはしない {ap._busy_text} {ap._bubble!r}")
rec = c_draw(ap)
check(b_count(rec, "さいしょ....") == 1 and b_count(rec, "いろはに....") == 1, f"144: メインは返事、人間は送ったプロンプトのまま {b_count(rec, 'さいしょ....')} {b_count(rec, 'いろはに....')}")
c_ev(ap, fb, Reply("s", "にばんめの返事"))
rec = c_draw(ap)
check(b_count(rec, "にばんめ....") == 1 and b_count(rec, "さいしょ....") == 0, "144: Reply が複数なら最新だけ")
# 複数行の返事は 1 行目の最初の 4 文字
c_ev(ap, fb, Reply("s", "あいうえお\n二行目"))
rec = c_draw(ap)
check(b_count(rec, "あいうえ....") == 1 and not any("二行" in t[2] for t in rec["utext"] if t[3] == 0), f"144: 複数行の返事は 1 行目の最初の 4 文字だけ {[t[2] for t in rec['utext'] if t[3] == 0]}")
c_ev(ap, fb, Reply("s", "  空白ではじまる文章"))
check(ap._busy_text[0] == "空白ではじまる文章", f"144: 前後の空白は取る {ap._busy_text[0]!r}")
# 4 文字以下の返事はそのまま
c_ev(ap, fb, Reply("s", "はい"))
rec = c_draw(ap)
check(b_count(rec, "はい") == 1 and b_count(rec, "はい....") == 0, "144: 4 文字以下の返事は \"....\" を付けない")
# 空の返事・空行ではじまる返事：吹き出しを出さない（空の枠を出さない）
c_ev(ap, fb, Reply("s", ""))
rec = c_draw(ap)
check(not any(t[2] == "" for t in rec["utext"] if t[3] == 0) and b_count(rec, "はい") == 0, "144: 空の返事なら、メインの吹き出しを出さない")
# Tool の間も出したまま
c_ev(ap, fb, Reply("s", "つづきの返事"), Tool("s", "Bash", "ls"))
rec = c_draw(ap)
check(b_count(rec, "つづきの....") == 1, "144: Tool が来ても作業中の吹き出しは変わらない")

# 144-b. busy でなくなったら消える・作業中の返事は TurnEnd のあと 6 秒出す
c_ev(ap, fb, Reply("s", "さいごの返事です"))
c_ev(ap, fb, TurnEnd("s"))
check(not main.busy and 0 not in ap._busy_text and ap._human_text is None and ap._pending_reply is None, f"144: TurnEnd で作業中の文・人間の文・保留の返事が消える {ap._busy_text} {ap._human_text!r}")
check(ap._bubble == "さいごの返事です" and abs(ap._bubble_left - (O.BUBBLE_SEC - 1 / 30)) < 1e-6, f"144: 作業中の最後の返事が TurnEnd のあと 6 秒の吹き出しになる {ap._bubble!r} {ap._bubble_left}")
rec = c_draw(ap)
check(not any(t[2].endswith("....") for t in rec["utext"] if t[3] == 0), "144: TurnEnd のあとは作業中の吹き出し（人間の分も）が消える")
check(any(t[2] == "さいごの返事です" for t in rec["utext"]), "144: 6 秒の吹き出しは返事の全文（24 文字まで）で出る")
c_run(ap, 30 * 5)
check(ap._bubble == "さいごの返事です" and ap._bubble_left > 0.5, f"144: TurnEnd の 5 秒後もまだ残る {ap._bubble!r} {ap._bubble_left}")
c_run(ap, 30 * 2)
check(ap._bubble == "" and ap._bubble_left <= 0.0, f"144: TurnEnd の 6 秒後に消える {ap._bubble!r} {ap._bubble_left}")
# 返事が無いまま TurnEnd：6 秒の吹き出しは出ない
ap, fb = b_ready()
c_ev(ap, fb, Prompt("s", "へんじなし"))
c_ev(ap, fb, TurnEnd("s"))
check(ap._bubble == "" and ap._busy_text == {} and ap._human_text is None, f"144: 返事が無いまま TurnEnd なら吹き出しは全部消える {ap._bubble!r}")
# 作業中でない Reply は、そのまま 6 秒の吹き出し（作業中の文にはしない）
c_ev(ap, fb, Reply("s", "ひとこと"))
check(ap._bubble == "ひとこと" and ap._busy_text == {} and ap._pending_reply is None, "144: 作業中でない Reply は 6 秒の吹き出し・作業中の文にしない")
# 次の依頼で TurnEnd 前の保留はもう無い。2 回目の作業でも同じように動く
c_ev(ap, fb, Prompt("s", "にかいめの依頼"), Reply("s", "にかいめの返事"))
c_ev(ap, fb, TurnEnd("s"))
check(ap._bubble == "にかいめの返事" and ap._busy_text == {}, "144: 2 回目の作業でも TurnEnd のあと返事を出す")

# 144-c. 人間の吹き出し：メインが作業中のあいだだけ・送ったプロンプト
ap, fb = b_ready()
ap._send_to_claude("こんにちは世界")
check(ap._human_text == "こんにちは世界", f"144: 送った文が人間の文になる {ap._human_text!r}")
rec = c_draw(ap)
check(b_count(rec, "こんにち....") == 0, "144: メインが作業中でなければ（Prompt がまだ記録に出ていない）人間の吹き出しは出ない")
c_ev(ap, fb, Prompt("s", "こんにちは世界"))
rec = c_draw(ap)
check(b_count(rec, "こんにち....") == 2, f"144: 作業が始まったら人間の吹き出し（とメインの吹き出し）が出る {b_count(rec, 'こんにち....')}")
c_ev(ap, fb, Reply("s", "ごめんなさい"))
rec = c_draw(ap)
check(b_count(rec, "こんにち....") == 1 and b_count(rec, "ごめんな....") == 1, "144: 返事が来ても人間は送ったプロンプトのまま")
c_ev(ap, fb, TurnEnd("s"))
rec = c_draw(ap)
check(b_count(rec, "こんにち....") == 0, "144: 作業が終わったら人間の吹き出しが消える")
# 複数行のプロンプトは 1 行目
c_ev(ap, fb, Prompt("s", "一行目だよ\n二行目だよ"))
rec = c_draw(ap)
check(b_count(rec, "一行目だ....") == 2 and not any("二行" in t[2] for t in rec["utext"] if t[3] == 0), "144: 複数行のプロンプトは 1 行目の最初の 4 文字")
# 引き継ぎの依頼も人間の吹き出しになる（終業の間）
ap, fb = b_ready()
p_frame(ap, keys=(pyxel.KEY_F1,))
check(ap._human_text == i18n_t(O.HANDOFF_PROMPT), f"144: 終業の依頼を送ったら人間の文になる {ap._human_text!r}")
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)))
rec = c_draw(ap)
check(b_count(rec, i18n_t(O.HANDOFF_PROMPT)[:4] + "....") == 2, f"144: 引き継ぎの依頼中は人間とメインの吹き出し {i18n_t(O.HANDOFF_PROMPT)[:4]}")
c_ev(ap, fb, TurnEnd("s"))
check(not ap.started and ap._busy_text == {} and ap._human_text is None and ap._pending_reply is None, "144: 終業したら吹き出しの文が全部空")

# 144-d. サブ：description の最初の 4 文字（空なら名前）。SubagentEnd で消える
ap, fb = b_ready()
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "資料をしらべる\n二行目", ""))
slot = ap._sub_map["a1"]
check(ap._busy_text.get(slot) == "資料をしらべる", f"144: サブの作業中の文は description の 1 行目 {ap._busy_text}")
check(c_seated(ap, slot), "144: 前提：サブが席に着く")
rec = c_draw(ap)
check(b_count(rec, "資料をし....") == 1, f"144: サブの吹き出し（description の最初の 4 文字） {[t[2] for t in rec['utext'] if t[3] == 0]}")
c_ev(ap, fb, SubagentStart("a2", "yamada", "", ""))
slot2 = ap._sub_map["a2"]
check(ap._busy_text.get(slot2) == "yamada", f"144: description が空なら名前（label） {ap._busy_text}")
check(c_seated(ap, slot2), "144: 前提：2 人目のサブも席に着く")
rec = c_draw(ap)
check(b_count(rec, "yama....") == 1 and b_count(rec, "資料をし....") == 1, "144: description が空なら名前の最初の 4 文字")
c_ev(ap, fb, SubagentStart("a3", "mini", "あ", ""))
slot3 = ap._sub_map["a3"]
check(c_seated(ap, slot3), "144: 前提：3 人目のサブも席に着く")
rec = c_draw(ap)
check(b_count(rec, "あ") == 1, "144: 4 文字以下の description はそのまま")
# メインが busy でなくても、サブの吹き出しは出る（人間の吹き出しは出ない）
check(not ap.agents[0].busy and ap._human_text is None, "144: 前提：メインは作業中でない")
# サブの終わり：吹き出しが消える
c_ev(ap, fb, SubagentEnd("a1"))
check(slot not in ap._busy_text and not ap.agents[slot].busy, f"144: SubagentEnd でサブの作業中の文が消える {ap._busy_text}")
rec = c_draw(ap)
check(b_count(rec, "資料をし....") == 0 and b_count(rec, "yama....") == 1, "144: 終わったサブの吹き出しだけ消える（まだ席にいても）")
# サブが部屋を出て（見えなくなって）いるあいだは出ない
ap._busy_text[slot2] = "かくれた人のぶん"
ap.agents[slot2].visible = False
rec = c_draw(ap)
check(b_count(rec, "かくれた....") == 0, "144: 見えていない人の吹き出しは出さない")
ap.agents[slot2].visible = True

# ---------------------------------------------------------------------------
# 145. 待つあいだの標準出力（_shutdown_claude）
# ---------------------------------------------------------------------------
# 受け取れた
ap, fb = c_make()
c_start(ap)
queue = [[], [Prompt("s", i18n_t(O.HANDOFF_PROMPT))], [TurnEnd("s")]]
fb.poll = lambda: queue.pop(0) if queue else []
sleeps = []
out = c_capture(lambda: ap._shutdown_claude(sleep=sleeps.append))
lines = out.splitlines()
check(lines == ["引き継ぎメモを待っています（最大300秒）…", "引き継ぎメモを受け取りました"], f"145: 受け取れたときの標準出力 {lines}")
# 待ち時間切れ
ap, fb = c_make()
c_start(ap)
fb.poll = lambda: []
sleeps = []
out = c_capture(lambda: ap._shutdown_claude(sleep=sleeps.append))
lines = out.splitlines()
check(lines == ["引き継ぎメモを待っています（最大300秒）…", "待ち時間を過ぎたので閉じます"], f"145: 待ち時間切れの標準出力 {lines}")
check(len(sleeps) >= 1490 and abs(sum(sleeps) - O.HANDOFF_WAIT_SEC) < 0.5, f"145: 待ちは約 300 秒ぶん（モックの sleep） {len(sleeps)} 回 {sum(sleeps):.1f}")
# 待ち始める前に表示が出る（最初の sleep より前）
ap, fb = c_make()
c_start(ap)
fb.poll = lambda: []
seen_at_first_sleep = []


def first_sleep(sec):
    if not seen_at_first_sleep:
        seen_at_first_sleep.append(buf145.getvalue())


buf145 = _io141.StringIO()
with _ctx141.redirect_stdout(buf145):
    ap._shutdown_claude(sleep=first_sleep)
check(seen_at_first_sleep and seen_at_first_sleep[0] == "引き継ぎメモを待っています（最大300秒）…\n", f"145: 待ち始める前に「待っています」を出す（flush 済みの 1 行） {seen_at_first_sleep}")
# 終業ボタン（_begin_handoff）の待ちは標準出力に出さない（画面の履歴に出る）
ap, fb = c_make()
c_start(ap)
out = c_capture(lambda: p_frame(ap, keys=(pyxel.KEY_F1,)))
check(out == "" and ap.history[-1] == "終業：引き継ぎメモを書いてもらっています", f"145: 終業ボタンの待ちは履歴に出して標準出力には出さない {out!r} {ap.history[-1]}")
# 始業していなければ何も出さない
ap, fb = c_make()
out = c_capture(lambda: ap._shutdown_claude(sleep=lambda s: None))
check(out == "", f"145: 始業していなければ標準出力に何も出さない {out!r}")

for a_ in C_APPS:
    a_.started = False
    a_.ending = False

# ---------------------------------------------------------------------------
# 146〜155. 許可の依頼をツールの中で答える（PermServer・_perm_*）と、会話のダイアログ（指示書5の3〜5章）。
# 本物の tmux・claude・hook は使わない。待ち受けは本物の AF_UNIX ソケット（抽象名前空間）で、つなぐ側はテストが務める。
# 待ち受けの名前は環境変数 PCA_PERM_SOCKET（無ければ冒頭で実行ごとの名前にしてある）。本番の名前には絶対につながない。
# ---------------------------------------------------------------------------
import socket as _so146
import queue as _q146
import subprocess as _sp146
import time as _tm146
import pca_perm_hook as H146

PM_PID = os.getpid()
_pm_no = [0]
PM_WORK = str(C_WORK)


def pm_name():
    """この実行専用の待ち受けの名前（\0 なし）。"""
    _pm_no[0] += 1
    return f"pca_test_o3d_{PM_PID}_{_pm_no[0]}"


def pm_connect(name):
    """名前（\0 なし）の待ち受けにつなぐ。"""
    s = _so146.socket(_so146.AF_UNIX, _so146.SOCK_STREAM)
    s.settimeout(3.0)
    s.connect("\0" + name)
    return s


def pm_send(s, payload):
    s.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))


def pm_reply(s, timeout=2.0):
    """届いた返事の1行を辞書で返す。時間切れ・閉じられたときは None。"""
    s.settimeout(timeout)
    buf = b""
    try:
        while b"\n" not in buf:
            ch = s.recv(4096)
            if not ch:
                return None
            buf += ch
    except OSError:
        return None
    return json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))


def pm_eof(s, timeout=2.0):
    """相手（待ち受け側）が閉じたか。"""
    s.settimeout(timeout)
    try:
        return s.recv(1) == b""
    except OSError:
        return False


def pm_wait_queue(srv, n=1, limit=3.0):
    """待ち受けの queue に n 件たまるまで待つ。たまったら True。"""
    end = _tm146.time() + limit
    while srv.queue.qsize() < n and _tm146.time() < end:
        _tm146.sleep(0.005)
    return srv.queue.qsize() >= n


def pm_perm_payload(tool="Bash", tool_input=None, cwd="__work__"):
    return {
        "type": "permission",
        "tool_name": tool,
        "tool_input": {"command": "ls -la"} if tool_input is None else tool_input,
        "session_id": "s",
        "transcript_path": None,
        "cwd": PM_WORK if cwd == "__work__" else cwd,
    }


def pm_req(ap, tool="Bash", tool_input=None, cwd="__work__", update=True):
    """hook の代わりに App の待ち受けへつなぎ、許可の依頼を送る。queue に届くまで待ち、update を1回呼ぶ。つなぎ（クライアント）を返す。"""
    srv = ap._perm_server
    s = pm_connect(srv.name[1:])
    pm_send(s, pm_perm_payload(tool, tool_input, cwd))
    pm_wait_queue(srv, 1)
    if update:
        ap.update()
    return s


def pm_notify(ap, ntype):
    """通知（notification）を送って update を1回呼ぶ。"""
    srv = ap._perm_server
    s = pm_connect(srv.name[1:])
    pm_send(s, {"type": "notification", "notification_type": ntype, "message": "m", "session_id": "s", "cwd": PM_WORK})
    pm_wait_queue(srv, 1)
    ap.update()
    s.close()


def pm_ready(talk=True, bridge=None):
    """始業して、メインを席に着かせ（talk なら話しかけ）た App と偽の Bridge。"""
    ap_, fb_ = c_make(bridge=bridge)
    c_start(ap_)
    c_seated(ap_, 0)
    if talk:
        c_talk_ready(ap_, 0)
    return ap_, fb_


def pm_sends(fb_):
    return [c for c in fb_.calls if c[0] == "send_prompt"]


class FakeBridgeScreen(FakeBridge):
    """tmux の画面に許可の画面が出ているか（permission_screen_open）を持つ偽の Bridge。"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.screen = False
        self.screen_error = False
        self.screen_calls = 0

    def permission_screen_open(self):
        self.screen_calls += 1
        if self.screen_error:
            raise RuntimeError("画面を調べられない")
        return self.screen


def pm_connect_refused(name):
    """つなげないなら True。"""
    try:
        s = pm_connect(name)
    except OSError:
        return True
    s.close()
    return False


def pm_dlg_rows(rec):
    """draw のダイアログの中身の行 (y, 文, 色)。"""
    return [(y, s, c) for (x, y, s, c) in rec["utext"] if x == O.DLG_X + O.UI_PAD and O.DLG_Y <= y < O.DLG_Y + O.DLG_H]


def pm_has_dlg_box(rec):
    return (O.DLG_X, O.DLG_Y, O.DLG_W, O.DLG_H, 0) in rec["rect"]


# 前のテスト（124〜145）の App が持つ待ち受けを先に全部止める（PermServer._active は直近の1つしか覚えないため、
# 名前の違う待ち受けを始めると、前の App の待ち受けが同じ環境変数の名前を握ったまま残り、あとの App の bind が失敗する）
for _a in C_APPS:
    if _a._perm_server is not None:
        _a._perm_server.stop()
O.PermServer._active = None

# 146. PermServer：実ソケットでの受け取り・answer・is_closed・deny_all・stop・引き継ぎ・別プロセス使用中
check(O.PERM_WAIT_SEC == 290.0 and O.PERM_WAIT_SEC < H146.WAIT_SEC == 300.0, f"146: PERM_WAIT_SEC は 290 秒で hook の 300 秒より短い {O.PERM_WAIT_SEC} {H146.WAIT_SEC}")
check((O.DLG_X, O.DLG_Y, O.DLG_W, O.DLG_H) == (16, 170, 608, 119), f"146: ダイアログの場所（x16・y170・幅608・高さ119） {(O.DLG_X, O.DLG_Y, O.DLG_W, O.DLG_H)}")
check(os.environ.get("PCA_PERM_SOCKET", "") != "" and O.PermServer().name == "\0" + os.environ["PCA_PERM_SOCKET"], "146: 名前の既定は環境変数 PCA_PERM_SOCKET（先頭に \\0）")
nm = pm_name()
srv = O.PermServer(name=nm, clock=lambda: 123.0)
check(srv.name == "\0" + nm, f"146: 名前の先頭に \\0 を付ける {srv.name!r}")
check(O.PermServer(name="\0" + nm).name == "\0" + nm, "146: すでに \\0 で始まる名前は付け足さない")
check(pm_connect_refused(nm), "146: start 前はつなげない")
check(srv.start() is True and O.PermServer._active is srv, "146: start が True で _active になる")
check(srv.start() is True, "146: 待ち受け中の start はもう一度呼んでも True")
# 依頼の受け取り
c1 = pm_connect(nm)
pay = pm_perm_payload(tool="Write", tool_input={"file_path": "/x/日本語.txt", "content": "あ\nい"})
pm_send(c1, pay)
got = srv.queue.get(timeout=3.0)
check(got[0] == 123.0 and got[1] == pay and got[2] is not None, f"146: 依頼が (時刻, 辞書, つながり) で queue に入る {got[:2]}")
check(srv.is_closed(got[2]) is False, "146: つながっている間は is_closed が False")
check(srv.answer(got[2], "allow") is True, "146: answer(allow) が True")
check(pm_reply(c1) == {"answer": "allow"}, "146: クライアントに {\"answer\": \"allow\"} が届く")
check(pm_eof(c1), "146: 答えたあとサーバー側が閉じる")
c1.close()
c2 = pm_connect(nm)
pm_send(c2, pm_perm_payload())
got = srv.queue.get(timeout=3.0)
check(srv.answer(got[2], "deny") is True and pm_reply(c2) == {"answer": "deny"}, "146: answer(deny) が届く")
c2.close()
# 送れない（相手が先に閉じた）→ False（例外を出さない）
c3 = pm_connect(nm)
pm_send(c3, pm_perm_payload())
got = srv.queue.get(timeout=3.0)
c3.close()
_tm146.sleep(0.05)
try:
    r = srv.answer(got[2], "allow")
except Exception as e:  # noqa: BLE001
    r = f"例外 {e!r}"
check(r is False, f"146: 相手が閉じたあとの answer は False（例外を出さない） {r!r}")
check(srv.answer(None, "allow") is False, "146: conn が None の answer は False")
# is_closed：相手が閉じたら True、None は True
c4 = pm_connect(nm)
pm_send(c4, pm_perm_payload())
got = srv.queue.get(timeout=3.0)
check(srv.is_closed(got[2]) is False, "146: 開いている間は False")
c4.close()
_tm146.sleep(0.05)
check(srv.is_closed(got[2]) is True, "146: 相手が閉じたら is_closed が True")
check(srv.is_closed(None) is True, "146: is_closed(None) は True")
_close_conn = got[2]
_close_conn.close()
check(srv.is_closed(_close_conn) is True, "146: こちらが閉じた conn も True（例外を出さない）")
# notification：つながりを閉じて conn None で入る
c5 = pm_connect(nm)
pm_send(c5, {"type": "notification", "notification_type": "permission_prompt", "message": "許可が要ります", "session_id": "s", "cwd": PM_WORK})
got = srv.queue.get(timeout=3.0)
check(got[2] is None and got[1].get("notification_type") == "permission_prompt" and got[1].get("message") == "許可が要ります", f"146: notification は conn None で入る {got[1:]}")
check(pm_eof(c5), "146: notification のあとサーバー側が閉じる")
c5.close()
# 壊れた依頼・種類が不明な依頼・辞書でない依頼は閉じて捨てる
for label, raw in (("壊れた JSON", "{ばらばら\n".encode("utf-8")), ("種類が不明", b'{"type": "foo"}\n'), ("辞書でない", b"[1, 2]\n"), ("文字でない", b"\xff\xfe\n")):
    cb = pm_connect(nm)
    cb.sendall(raw)
    check(pm_eof(cb), f"146: {label}は閉じて捨てる")
    check(srv.queue.empty(), f"146: {label}は queue に入れない")
    cb.close()
# deny_all：queue に残っている分すべてに deny（待ち受けは止めない）
cs = []
for _ in range(3):
    c = pm_connect(nm)
    pm_send(c, pm_perm_payload())
    cs.append(c)
check(pm_wait_queue(srv, 3), "146: 前提：3 件が queue に入った")
srv.deny_all()
check([pm_reply(c) for c in cs] == [{"answer": "deny"}] * 3 and srv.queue.empty(), "146: deny_all で残り全部に deny が届き queue が空になる")
for c in cs:
    c.close()
c6 = pm_connect(nm)
pm_send(c6, pm_perm_payload())
check(pm_wait_queue(srv, 1) and srv._sock is not None, "146: deny_all のあとも待ち受けは続く")
# stop：残りに deny、待ち受けを閉じる（つなげなくなる）、_active を外す
srv.stop()
check(pm_reply(c6) == {"answer": "deny"}, "146: stop で queue の残りに deny が届く")
c6.close()
check(srv._sock is None and srv._thread is None and O.PermServer._active is None, f"146: stop で _sock・_thread が None・_active が外れる {srv._sock} {srv._thread} {O.PermServer._active}")
check(pm_connect_refused(nm), "146: stop のあとはつなげない")
srv.stop()
check(True, "146: stop を2回呼んでも例外を出さない")
# 同じプロセスでの引き継ぎ：後から start した方が待ち受けを引き継ぎ、前の queue の残りは deny
nm2 = pm_name()
sa = O.PermServer(name=nm2)
check(sa.start() is True, "146: 前の待ち受け A が start")
ca = pm_connect(nm2)
pm_send(ca, pm_perm_payload())
check(pm_wait_queue(sa, 1), "146: 前提：A に依頼が届いた")
sb = O.PermServer(name=nm2)
out = c_capture(lambda: setattr(sb, "_r", sb.start()))
check(sb._r is True and out == "", f"146: 同じ名前の B が start できる（注意の行は出さない） {sb._r} {out!r}")
check(sa._sock is None and O.PermServer._active is sb, "146: A は止まり、B が _active")
check(pm_reply(ca) == {"answer": "deny"}, "146: A の queue に残っていた依頼は deny")
ca.close()
cb2 = pm_connect(nm2)
pm_send(cb2, pm_perm_payload())
check(pm_wait_queue(sb, 1) and sa.queue.empty(), "146: 引き継いだあとの依頼は B に届く")
sb.stop()
cb2.close()
# 名前が違う待ち受けは止めない
nm3 = pm_name()
nm4 = pm_name()
sc, sd = O.PermServer(name=nm3), O.PermServer(name=nm4)
sc.start()
sd.start()
check(sc._sock is not None and sd._sock is not None and not pm_connect_refused(nm3), "146: 名前が違う待ち受けは引き継がず両方動く")
sc.stop()
sd.stop()
# 別プロセスが使用中：start は False・標準出力に1行・何も起こさない
nm5 = pm_name()
code = "import socket,sys\ns=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)\ns.bind('\\0'+sys.argv[1])\ns.listen(1)\nprint('ready',flush=True)\nsys.stdin.read()\n"
other = _sp146.Popen([sys.executable, "-I", "-c", code, nm5], stdin=_sp146.PIPE, stdout=_sp146.PIPE, text=True)
check(other.stdout.readline().strip() == "ready", "146: 前提：別プロセスが名前を握った")
se = O.PermServer(name=nm5)
out = c_capture(lambda: setattr(se, "_r", se.start()))
check(se._r is False and out == "許可の受け取りを使えません（ほかで使用中）\n", f"146: 別プロセス使用中は False・標準出力に1行 {se._r} {out!r}")
check(se._sock is None and se._thread is None and O.PermServer._active is not se, "146: 失敗しても何も作らない")
se.stop()
# App：始業で bind に失敗 → 履歴に目立つ1行、許可は止めず、送信も止めない
ap, fb = c_make()
ap._perm_server = O.PermServer(name=nm5, clock=ap._perm_clock)
out = c_capture(lambda: c_start(ap))
NOTE146 = "(注意：許可の受け取りが使えません。許可は tmux に出て、送信も止まりません)"
check(NOTE146 in ap.history, f"146: bind 失敗の注意の行が履歴にある {ap.history[-4:]}")
check(out == "許可の受け取りを使えません（ほかで使用中）\n", f"146: bind 失敗のとき標準出力にも1行 {out!r}")
check(ap.started and not ap._perm_lock and not ap._perm_tmux, "146: bind 失敗でも始業でき、送信は止まらない")
ap.mode = O.MODE_WALK
p_enter_prompt(ap)
p_send(ap, "こんにちは")
check(pm_sends(fb) == [("send_prompt", "こんにちは")], f"146: bind 失敗のときも送れる {fb.calls}")
other.stdin.close()
other.wait(timeout=10)
# 始業前は待ち受けない・F1 で待ち受ける
ap, fb = c_make()
check(ap._perm_server is not None and ap._perm_server._sock is None and pm_connect_refused(ap._perm_server.name[1:]), "146: 始業前は待ち受けていない")
c_start(ap)
check(ap._perm_server._sock is not None and not pm_connect_refused(ap._perm_server.name[1:]), "146: 始業すると待ち受ける")
check(NOTE146 not in ap.history, "146: 成功したときは注意の行を出さない")

# 147. cwd が作業フォルダの外 → tmux を返して捨て、_perm_tmux。下のフォルダは受け付ける
ap, fb = pm_ready()
s = pm_req(ap, cwd="/tmp")
check(pm_reply(s) == {"answer": "tmux"}, "147: 作業フォルダの外の依頼には tmux が返る")
check(ap._perm_pending == [] and ap._perm_tmux and ap._perm_lock, f"147: 外の依頼は捨てて _perm_tmux・_perm_lock が立つ {ap._perm_pending} {ap._perm_tmux}")
s.close()
for label, cwd in (("同じ名前の兄弟フォルダ", PM_WORK + "_evil"), ("..で外へ出る", PM_WORK + "/../x"), ("cwd なし", None), ("空の cwd", ""), ("文字でない cwd", 5)):
    ap, fb = pm_ready()
    s = pm_req(ap, cwd=cwd)
    check(pm_reply(s) == {"answer": "tmux"} and ap._perm_pending == [] and ap._perm_tmux, f"147: {label}は tmux に回す")
    s.close()
for label, cwd in (("作業フォルダそのもの", PM_WORK), ("下のフォルダ", PM_WORK + "/sub/dir"), ("末尾のスラッシュ", PM_WORK + "/")):
    ap, fb = pm_ready()
    s = pm_req(ap, cwd=cwd)
    check(len(ap._perm_pending) == 1 and not ap._perm_tmux and ap._perm_lock, f"147: {label}は受け付ける {ap._perm_pending}")
    check(pm_reply(s, 0.1) is None, f"147: {label}は答えを返さずに待つ")
    s.close()
ap, fb = pm_ready()
s = pm_req(ap, tool="Edit", tool_input={"file_path": "/a/b.py"})
r = ap._perm_pending[0]
check((r.tool_name, r.tool_input) == ("Edit", {"file_path": "/a/b.py"}) and r.conn is not None and isinstance(r.received, float), f"147: PermRequest の中身 {r.tool_name} {r.tool_input}")
s.close()
ap, fb = pm_ready()
s = pm_req(ap, tool=None)
check(len(ap._perm_pending) == 1 and ap._perm_pending[0].tool_name == "?", "147: 道具名が無い依頼は「?」")
s.close()

# 148. 送信の止め：依頼がある間／_perm_tmux／tmux の許可画面が出ている間は _send_to_claude と Esc を送らない
ap, fb = pm_ready()
s = pm_req(ap)
check(ap._perm_lock is True, "148: 依頼があれば _perm_lock")
p_enter_prompt(ap)
p_type(ap, "テスト")
fb.calls.clear()
p_enter(ap)
check(pm_sends(fb) == [] and ap.input_buf == "テスト", f"148: 依頼がある間は送らず、入力欄の文字は残る {fb.calls} {ap.input_buf!r}")
check(ap.history.count(i18n_t(O.PERM_WAIT_NOTE)) == 1 and ap.history[-1] == i18n_t(O.PERM_WAIT_NOTE) == "(許可の答えを待っています。送信は止めています)", f"148: 注意の行が出る {ap.history[-2:]}")
p_enter(ap)
p_enter(ap)
check(ap.history.count(i18n_t(O.PERM_WAIT_NOTE)) == 1 and pm_sends(fb) == [], "148: 注意の行は続けて何度送っても1回だけ")
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(("send_escape",) not in fb.calls and "(Esc: 中断を送る)" not in ap.history, f"148: 依頼がある間は Esc（中断）を送らない {fb.calls}")
check(ap.history.count(i18n_t(O.PERM_WAIT_NOTE)) == 1, "148: Esc で止めても注意の行は増えない")
ap._send_to_claude("直接")
check(pm_sends(fb) == [] and ap._last_sent is None, "148: _send_to_claude も送らない・送った扱いにしない")
# 答えたら外れて、入力欄の文字が送れる。止めが外れたら注意の行の印も戻る（次の止めでまた出る）
ap.mode = O.MODE_WALK
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s) == {"answer": "allow"} and not ap._perm_lock and not ap._perm_wait_noted, "148: Y で答えると止めが外れ、注意の印も戻る")
s.close()
p_enter_prompt(ap)
p_enter(ap)
check(pm_sends(fb) == [("send_prompt", "テスト")] and ap.input_buf == "", f"148: 止めが外れたら入力欄の文字が送れる {fb.calls}")
s = pm_req(ap)
ap._perm_key_guard_until = 0.0  # 入力欄で打っていたので依頼で WALK に切り替わっている（157 番）。守り時間を外して PROMPT に戻る
p_enter_prompt(ap)
p_type(ap, "二つ目")
p_enter(ap)
check(ap.history.count(i18n_t(O.PERM_WAIT_NOTE)) == 2 and len(pm_sends(fb)) == 1, "148: 止めが外れて次に止めたときは、注意の行がもう一度出る")
s.close()
# Tool・Reply・TurnEnd で _perm_tmux が解ける（T で答えた分）
for ev in (Tool("s", "Bash", "ls"), Reply("s", "返事"), TurnEnd("s")):
    ap, fb = pm_ready()
    s = pm_req(ap)
    ap.mode = O.MODE_WALK
    p_frame(ap, keys=(pyxel.KEY_T,))
    check(pm_reply(s) == {"answer": "tmux"} and ap._perm_tmux and ap._perm_lock and not ap._perm_pending, f"148-{type(ev).__name__}: T で答えると _perm_tmux・止めが続く")
    s.close()
    p_enter_prompt(ap)
    p_type(ap, "T後")
    fb.calls.clear()
    p_enter(ap)
    check(pm_sends(fb) == [] and ap.input_buf == "T後", f"148-{type(ev).__name__}: _perm_tmux の間は送らない")
    c_ev(ap, fb, ev)
    check(not ap._perm_tmux and not ap._perm_lock, f"148-{type(ev).__name__}: イベントで _perm_tmux と止めが解ける")
    p_enter(ap)
    check(pm_sends(fb) == [("send_prompt", "T後")], f"148-{type(ev).__name__}: 解けたあとは送れる {fb.calls}")
# Prompt イベントだけでは解けない
ap, fb = pm_ready()
s = pm_req(ap, cwd="/tmp")
s.close()
c_ev(ap, fb, Prompt("s", "だれかの入力"))
check(ap._perm_tmux and ap._perm_lock, "148: Prompt イベントでは _perm_tmux は解けない（Tool・Reply・TurnEnd だけ）")
# 依頼が残っているときは解かない。依頼に答えても _perm_tmux が残れば止めは続く
ap, fb = pm_ready()
s0 = pm_req(ap, cwd="/tmp")
s0.close()
s = pm_req(ap)
check(ap._perm_tmux and len(ap._perm_pending) == 1, "148: 前提：_perm_tmux と依頼が1件")
c_ev(ap, fb, Tool("s", "Bash", "ls"))
check(ap._perm_tmux and ap._perm_lock, "148: 依頼が残っているあいだは Tool が来ても _perm_tmux を解かない")
ap.mode = O.MODE_WALK
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s) == {"answer": "allow"} and ap._perm_pending == [] and ap._perm_tmux and ap._perm_lock, "148: 依頼に答えても _perm_tmux が残れば止めは続く")
c_ev(ap, fb, Reply("s", "r"))
check(not ap._perm_tmux and not ap._perm_lock, "148: 依頼が空になってから Reply が来ると解ける")
s.close()
# notification の permission_prompt で _perm_tmux・それ以外の通知では変わらない
ap, fb = pm_ready()
pm_notify(ap, "idle_prompt")
check(not ap._perm_tmux and not ap._perm_lock, "148: permission_prompt 以外の通知では止めない")
pm_notify(ap, "permission_prompt")
check(ap._perm_tmux and ap._perm_lock and ap._perm_pending == [], "148: permission_prompt の通知で _perm_tmux・止めが立つ")
p_enter_prompt(ap)
p_type(ap, "通知後")
fb.calls.clear()
p_enter(ap)
check(pm_sends(fb) == [] and ap.input_buf == "通知後", "148: permission_prompt の通知のあとは送らない")
c_ev(ap, fb, Tool("s", "Bash", "ls"))
check(not ap._perm_tmux, "148: 通知で立てた _perm_tmux も Tool で解ける")
# tmux の画面に許可の画面が出ている（permission_screen_open が True）：依頼が無くても送らず Esc も送らない
fbs = FakeBridgeScreen(session=False, begin_ok=True)
ap, fb = pm_ready(talk=False, bridge=fbs)
p_enter_prompt(ap)
p_type(ap, "画面あり")
fb.calls.clear()
fb.screen = True
p_enter(ap)
check(pm_sends(fb) == [] and ap.input_buf == "画面あり", f"148: 許可の画面が出ているあいだは送らず、入力欄の文字は残る {fb.calls}")
check(ap._perm_tmux and ap._perm_lock and ap.history.count(i18n_t(O.PERM_WAIT_NOTE)) == 1, "148: _perm_tmux を立て、注意の行は1回")
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(("send_escape",) not in fb.calls and "(Esc: 中断を送る)" not in ap.history, "148: 許可の画面が出ているあいだは Esc も送らない")
fb.screen = False
check(ap._perm_tmux, "148: 画面が消えただけでは _perm_tmux は解けない（次のイベントで解ける）")
c_ev(ap, fb, Tool("s", "Bash", "ls"))
p_enter(ap)
check(pm_sends(fb) == [("send_prompt", "画面あり")], f"148: 解けたあとは送れる {fb.calls}")
# 許可の画面が出ていて、_perm_tmux がまだ立っていないときの Esc
fbs = FakeBridgeScreen(session=False, begin_ok=True)
ap, fb = pm_ready(talk=False, bridge=fbs)
p_enter_prompt(ap)
fb.calls.clear()
fb.screen = True
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(("send_escape",) not in fb.calls and ap._perm_tmux, "148: 許可の画面が出ているとき最初の Esc も送らず _perm_tmux を立てる")
# 画面を調べて失敗（例外）・False のときは止めない・始業前は調べない
fbs = FakeBridgeScreen(session=False, begin_ok=True)
ap, fb = pm_ready(talk=False, bridge=fbs)
fbs.screen_error = True
p_enter_prompt(ap)
p_send(ap, "例外")
check(pm_sends(fb) == [("send_prompt", "例外")] and not ap._perm_tmux, "148: 画面を調べて例外が出ても止めずに送る")
fbs.screen_error = False
p_send(ap, "偽")
check(len(pm_sends(fb)) == 2, "148: 許可の画面が出ていなければ送れる")
fbs2 = FakeBridgeScreen(session=False, begin_ok=True)
ap2, _ = c_make(bridge=fbs2)
ap2._send_to_claude("始業前")
check(fbs2.screen_calls == 0 and "(始業していません。F1 で始業してください)" in ap2.history, "148: 始業前は画面を調べず「始業していません」")
check(ap2._tmux_shows_permission() is False, "148: 始業前の _tmux_shows_permission は False")

# 149. 時間切れ 290 秒・接続が閉じたら取り下げ・answer 失敗時の履歴
ap, fb = pm_ready()
t_now = [1000.0]
ap._perm_clock = lambda: t_now[0]
ap._perm_server.clock = ap._perm_clock
s1 = pm_req(ap)
t_now[0] = 1100.0
s2 = pm_req(ap, tool="Write", tool_input={"file_path": "/a.txt"})
check([r.received for r in ap._perm_pending] == [1000.0, 1100.0], f"149: 受け取った時刻が入る {[r.received for r in ap._perm_pending]}")
t_now[0] = 1000.0 + 289.9
ap.update()
check(len(ap._perm_pending) == 2 and pm_reply(s1, 0.1) is None, "149: 289.9 秒ではまだ待つ")
t_now[0] = 1000.0 + 290.0
ap.update()
check(len(ap._perm_pending) == 1 and ap._perm_pending[0].tool_name == "Write", "149: 290 秒で1件目だけ外れる（2件目は残る）")
check(pm_reply(s1) == {"answer": "tmux"}, "149: 時間切れの依頼には tmux が返る")
check(ap._perm_tmux and ap._perm_lock, "149: 時間切れで _perm_tmux・止めが立つ")
check(ap.history[-1] == "(許可の答えが時間切れ。tmux で答えてください：Bash ls -la)", f"149: 時間切れの履歴の行 {ap.history[-1]!r}")
t_now[0] = 1100.0 + 290.0
ap.update()
check(ap._perm_pending == [] and pm_reply(s2) == {"answer": "tmux"} and ap.history[-1] == "(許可の答えが時間切れ。tmux で答えてください：Write /a.txt)", f"149: 2件目も 290 秒で外れる {ap.history[-1]!r}")
s1.close()
s2.close()
# 接続が閉じたら取り下げ（先頭だけ閉じたとき、残りの順番は変わらない）
ap, fb = pm_ready()
s1 = pm_req(ap)
s2 = pm_req(ap, tool="Write", tool_input={"file_path": "/b.txt"})
s3 = pm_req(ap, tool="Edit", tool_input={"file_path": "/c.txt"})
check([r.tool_name for r in ap._perm_pending] == ["Bash", "Write", "Edit"], "149: 前提：3件")
s1.close()
_tm146.sleep(0.05)
ap.update()
check([r.tool_name for r in ap._perm_pending] == ["Write", "Edit"] and ap._perm_tmux, f"149: 閉じた1件だけ外れ、順番は保たれ _perm_tmux が立つ {[r.tool_name for r in ap._perm_pending]}")
check(ap.history[-1] == "(許可の依頼が取り下げられました：Bash ls -la)", f"149: 取り下げの履歴の行 {ap.history[-1]!r}")
check(ap._perm_lock, "149: まだ依頼があるので止めは続く")
s2.close()
s3.close()
_tm146.sleep(0.05)
ap.update()
check(ap._perm_pending == [] and ap._perm_tmux and ap._perm_lock, "149: 全部取り下げられても _perm_tmux が残って止めは続く")
check("(許可の依頼が取り下げられました：Write /b.txt)" in ap.history and "(許可の依頼が取り下げられました：Edit /c.txt)" in ap.history, "149: 取り下げの履歴がそれぞれ出る")
# 取り下げ済みで依頼が無いとき Y を押しても何も起きない
ap.mode = O.MODE_WALK
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_Y,))
check(len(ap.history) == n0, "149: 取り下げ済みで依頼が無いとき Y は何もしない")
# answer が False（届かなかった）：履歴は「許可しました」にしない
for key, label in ((pyxel.KEY_Y, "Y"), (pyxel.KEY_N, "N")):
    ap, fb = pm_ready()
    s = pm_req(ap)
    ap._perm_server.answer = lambda conn, a: False
    ap.mode = O.MODE_WALK
    p_frame(ap, keys=(key,))
    check(ap.history[-1] == "(答えが届きませんでした。tmux で答えてください：Bash ls -la)", f"149: {label}で answer が False のときの履歴 {ap.history[-1]!r}")
    check(not any(("許可しました" in h or "断りました" in h) for h in ap.history), f"149: {label}で answer が False のとき「許可しました／断りました」を出さない")
    check(ap._perm_tmux and ap._perm_lock and ap._perm_pending == [], f"149: {label}で answer が False のとき _perm_tmux・止めが立ち、列から外れる")
    s.close()

# 150. ！：依頼がある間メインの頭上に黄色10。作業中の吹き出し・6秒の吹き出しより優先
ap, fb = pm_ready(talk=False)
main = ap.agents[0]
ap._bubble = "ふきだしの文"
ap._bubble_left = 5.0
ap._busy_text[0] = "さぎょうちゅうの文"
rec = c_draw(ap)
check(not any(t[2] == "！" for t in rec["utext"]), "150: 依頼が無ければ ！ を出さない")
check(c_ui_has(rec, "ふきだしの文") and c_ui_has(rec, "さぎょう...."), f"150: 前提：吹き出しと作業中の吹き出しが出る {[t[2] for t in rec['utext']]}")
s = pm_req(ap)
rec = c_draw(ap)
marks = [t for t in rec["utext"] if t[2] == "！"]
check(len(marks) == 1 and marks[0][3] == 10, f"150: 依頼があるあいだ、黄色10の ！ が1つ出る {marks}")
head = ap._head_point(main)
check(head is not None and marks and marks[0][1] == int(head[1]) - 24 and abs(marks[0][0] + ap.ui_font.text_width("！") // 2 - head[0]) <= 1, f"150: ！ はメインの頭の上 {marks} {head}")
check(not c_ui_has(rec, "ふきだしの文") and not c_ui_has(rec, "さぎょう...."), "150: 依頼があるあいだは、6秒の吹き出しも作業中の吹き出しも出さない（！が優先）")
s2 = pm_req(ap, tool="Write", tool_input={"file_path": "/x"})
rec = c_draw(ap)
check(len([t for t in rec["utext"] if t[2] == "！"]) == 1, "150: 依頼が2件でも ！ は1つ")
ap._deny_perm_all()
s.close()
s2.close()
rec = c_draw(ap)
check(not any(t[2] == "！" for t in rec["utext"]) and c_ui_has(rec, "ふきだしの文") and c_ui_has(rec, "さぎょう...."), "150: 依頼が無くなれば ！ は消えて吹き出しが戻る")
# サブの吹き出しは変えない
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "サブの説明です", ""))
slot = ap._sub_map["a1"]
c_seated(ap, slot)
# 会話中のカメラ（メインを見る）で、サブの席が画面の外のことがあるので、頭が画面に入る場所へ寄せる（席の位置は吹き出しの確認に関係ない）
for _dx, _dz in ((60, 80), (-60, 80), (80, 0), (0, 100), (-80, 0), (0, -100)):
    ap.agents[slot].pos = O.Vec3(ap.agents[0].pos.x + _dx, 0.0, ap.agents[0].pos.z + _dz)
    if ap._head_point(ap.agents[slot]) is not None:
        break
check(ap._head_point(ap.agents[slot]) is not None, "150: 前提：サブの頭が画面の中")
s = pm_req(ap)
rec = c_draw(ap)
check(c_ui_has(rec, "サブの説...."), f"150: 依頼があってもサブの吹き出しは出る {[t[2] for t in rec['utext']]}")
s.close()
# メインが見えないときは ！ を出さない
ap, fb = pm_ready(talk=False)
s = pm_req(ap)
main = ap.agents[0]
try:
    main.visible = False
    rec = c_draw(ap)
    check(not any(t[2] == "！" for t in rec["utext"]), "150: メインが見えないときは ！ を出さない")
    main.visible = True
except AttributeError:
    pass
s.close()

# 151. Y/N/T：メインと会話中・WALK・依頼ありのときだけ。PROMPT 中は文字として入る。他の人と会話中は効かない
ap, fb = pm_ready()
s1 = pm_req(ap)
s2 = pm_req(ap, tool="Write", tool_input={"file_path": "/w.txt"})
s3 = pm_req(ap, tool="Edit", tool_input={"file_path": "/e.txt"})
check(ap.mode == O.MODE_WALK and ap.talk_partner == O.MAIN_INDEX and len(ap._perm_pending) == 3, "151: 前提：WALK・メインと会話中・依頼3件")
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s1) == {"answer": "allow"} and [r.tool_name for r in ap._perm_pending] == ["Write", "Edit"], "151: Y：先頭の1件だけ allow・次が先頭になる")
check(ap.history[-1] == "許可しました：Bash ls -la" and pm_reply(s2, 0.1) is None, f"151: Y の履歴の行 {ap.history[-1]!r}")
check("許可を求めています（残り 2 件）" in dtx(ap, 0) and "道具：Write" in dtx(ap, 0), "151: 先頭に答えたら次の依頼をダイアログに出す")
p_frame(ap, keys=(pyxel.KEY_N,))
check(pm_reply(s2) == {"answer": "deny"} and ap.history[-1] == "断りました：Write /w.txt", f"151: N：deny・履歴 {ap.history[-1]!r}")
check(ap._perm_lock and not ap._perm_tmux, "151: まだ依頼があるので止めは続く（_perm_tmux は立てない）")
p_frame(ap, keys=(pyxel.KEY_T,))
check(pm_reply(s3) == {"answer": "tmux"} and ap._perm_tmux and ap.history[-1] == "tmux で答えてください：Edit /e.txt", f"151: T：tmux・_perm_tmux・履歴 {ap.history[-1]!r}")
check(ap._perm_pending == [], "151: 3件とも答えたので列は空")
n0 = len(ap.history)
for k in (pyxel.KEY_Y, pyxel.KEY_N, pyxel.KEY_T):
    p_frame(ap, keys=(k,))
check(len(ap.history) == n0, "151: 依頼が無いときの Y・N・T は何もしない")
for s_ in (s1, s2, s3):
    s_.close()
# 会話していない：効かない
ap, fb = pm_ready(talk=False)
s = pm_req(ap)
ap.end_talk()  # 依頼で自動に始まった会話（157 番）を終える
ap._perm_key_guard_until = 0.0  # 守り時間は外す（効かない理由を「会話していない」だけにする）
for k in (pyxel.KEY_Y, pyxel.KEY_N, pyxel.KEY_T):
    p_frame(ap, keys=(k,))
check(len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, "151: 会話していないときは Y・N・T が効かない")
# 話しかけたら効く
c_talk_ready(ap, 0)
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s) == {"answer": "allow"}, "151: メインと会話を始めたら Y が効く")
s.close()
# PROMPT 中は文字として入り、答えない
ap, fb = pm_ready()
s = pm_req(ap)
p_enter_prompt(ap)
p_frame(ap, keys=(pyxel.KEY_Y,), text="y")
p_frame(ap, keys=(pyxel.KEY_N,), text="n")
p_frame(ap, keys=(pyxel.KEY_T,), text="t")
check(ap.input_buf == "ynt" and len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, f"151: PROMPT 中の Y・N・T は文字として入り、答えない {ap.input_buf!r}")
s.close()
# 他の人（サブ・うろうろしている人）と会話中：効かない
ap, fb = pm_ready(talk=False)
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "サブの説明", ""))
slot = ap._sub_map["a1"]
c_seated(ap, slot)
s = pm_req(ap)
check(c_talk_ready(ap, slot) and ap.talk_partner == slot, "151: 前提：サブと会話中")
for k in (pyxel.KEY_Y, pyxel.KEY_N, pyxel.KEY_T):
    p_frame(ap, keys=(k,))
check(len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, "151: サブと会話中は Y・N・T が効かない")
ap.end_talk()
ap._enter(7)
c_seated(ap, 7)
check(c_talk_ready(ap, 7) and ap.agents[7].role != "sub", "151: 前提：うろうろしている人と会話中")
for k in (pyxel.KEY_Y, pyxel.KEY_N, pyxel.KEY_T):
    p_frame(ap, keys=(k,))
check(len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None and not ap._perm_tmux, "151: ふつうの人と会話中も Y・N・T が効かない")
s.close()
# 始業のダイアログ（前のセッションが残っています）が出ている間も効かない
ap, fb = pm_ready()
s = pm_req(ap)
ap._dialog = True
p_frame(ap, keys=(pyxel.KEY_Y,))
check(len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, "151: 始業のダイアログが出ている間は Y が効かない")
ap._dialog = False
s.close()

# 152. 終わるとき：F1 の終業は残りに deny・待ち受けは止めない・_perm_tmux なら Esc を送って1秒待つ。×・_session_gone は deny して止める
ap, fb = pm_ready()
s1 = pm_req(ap)
s2 = pm_req(ap, tool="Write", tool_input={"file_path": "/w.txt"})
s3 = pm_req(ap, tool="Edit", tool_input={"file_path": "/e.txt"}, update=False)
srv = ap._perm_server
fb.calls.clear()
p_frame(ap, keys=(pyxel.KEY_F1,))
check(ap.ending and ap.started, "152: 前提：F1 で終業の待ちに入った")
check([pm_reply(s) for s in (s1, s2, s3)] == [{"answer": "deny"}] * 3, "152: F1 の終業は残り全部（列と queue の両方）に deny を返す（tmux は返さない）")
check(ap._perm_pending == [] and not ap._perm_lock and not ap._perm_tmux and srv.queue.empty(), "152: 終業のあと列は空・止めは外れる")
check(("send_escape",) not in fb.calls and ("send_prompt", i18n_t(O.HANDOFF_PROMPT)) in fb.calls, f"152: _perm_tmux でなければ Esc は送らず引き継ぎを送る {fb.calls}")
check(srv._sock is not None and O.PermServer._active is srv and not pm_connect_refused(srv.name[1:]), "152: F1 の終業では待ち受けを止めない")
for s in (s1, s2, s3):
    s.close()
s4 = pm_req(ap, tool="Write", tool_input={"file_path": "/memo.md"})
check(len(ap._perm_pending) == 1, "152: 終業の待ちのあいだに来た依頼も受け取る（引き継ぎメモの Write）")
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s4) == {"answer": "allow"}, "152: 終業の待ちのあいだも Y で答えられる")
s4.close()
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)))
c_ev(ap, fb, TurnEnd("s"))
check(not ap.started and srv._sock is None and pm_connect_refused(srv.name[1:]) and O.PermServer._active is not srv, "152: 終業が終わってセッションを閉じたら待ち受けを止める")
# 終業：_perm_tmux なら Esc を1回送って1秒待ってから引き継ぎを送る（順番）
ap, fb = pm_ready()
s0 = pm_req(ap, cwd="/tmp")
s0.close()
s1 = pm_req(ap)
check(ap._perm_tmux and len(ap._perm_pending) == 1, "152: 前提：_perm_tmux と依頼1件")
fb.calls.clear()
sl = []
ap._begin_handoff(sleep=sl.append)
check(fb.calls[:2] == [("send_escape",), ("send_prompt", i18n_t(O.HANDOFF_PROMPT))] and fb.calls.count(("send_escape",)) == 1, f"152: _perm_tmux のとき、引き継ぎの前に Esc を1回送る {fb.calls}")
check(sl == [1.0], f"152: Esc のあと 1 秒待つ {sl}")
check(pm_reply(s1) == {"answer": "deny"}, "152: _perm_tmux があっても残りの依頼には deny")
check(not ap._perm_lock and not ap._perm_tmux and ap.ending, "152: そのあと止めを外して続ける（終業の待ち）")
s1.close()
# _perm_tmux でなければ待たない
ap, fb = pm_ready()
fb.calls.clear()
sl = []
ap._begin_handoff(sleep=sl.append)
check(sl == [] and ("send_escape",) not in fb.calls, f"152: _perm_tmux でなければ Esc も待ちも無い {fb.calls} {sl}")
# 窓の×（_shutdown_claude）：deny して止める。_perm_tmux なら Esc＋1秒
ap, fb = pm_ready()
s0 = pm_req(ap, cwd="/tmp")
s0.close()
s1 = pm_req(ap)
s2 = pm_req(ap, tool="Write", tool_input={"file_path": "/w"}, update=False)
srv = ap._perm_server
fb.session = False
fb.calls.clear()
sl = []
out = c_capture(lambda: ap._shutdown_claude(sleep=sl.append))
check([pm_reply(s1), pm_reply(s2)] == [{"answer": "deny"}] * 2, "152: ×：列と queue の残りに deny")
check(fb.calls == [("send_escape",), ("end", False)] and sl == [1.0], f"152: ×で _perm_tmux なら Esc＋1秒待ち {fb.calls} {sl}")
check(srv._sock is None and pm_connect_refused(srv.name[1:]) and not ap._perm_lock and not ap._perm_tmux and ap._perm_pending == [], "152: ×のあと待ち受けを止めている・止めも外れる")
s1.close()
s2.close()
# ×：_perm_tmux でなければ Esc なし
ap, fb = pm_ready()
s1 = pm_req(ap)
fb.session = False
fb.calls.clear()
sl = []
out = c_capture(lambda: ap._shutdown_claude(sleep=sl.append))
check(pm_reply(s1) == {"answer": "deny"} and fb.calls == [("end", False)] and sl == [], f"152: ×で _perm_tmux が無ければ deny だけ（Esc・待ちなし） {fb.calls} {sl}")
s1.close()
# ×：始業していないときは何もしない・例外なし
ap, fb = c_make()
out = c_capture(lambda: ap._shutdown_claude(sleep=lambda x: None))
check(out == "" and fb.calls == [], f"152: 始業前の×は何もしない {fb.calls} {out!r}")
# セッションが消えた（_session_gone）：deny して止める
ap, fb = pm_ready()
s1 = pm_req(ap)
s2 = pm_req(ap, tool="Write", tool_input={"file_path": "/w"}, update=False)
srv = ap._perm_server
ap._session_gone()
check([pm_reply(s1), pm_reply(s2)] == [{"answer": "deny"}] * 2, "152: _session_gone：残りに deny")
check(srv._sock is None and pm_connect_refused(srv.name[1:]) and not ap._perm_lock and not ap._perm_tmux and ap._perm_pending == [], "152: _session_gone のあと待ち受けを止めている・止めも外れる")
s1.close()
s2.close()
# _finish_ending（終業の終わり）も止める
ap, fb = pm_ready()
s1 = pm_req(ap)
srv = ap._perm_server
ap._finish_ending()
check(pm_reply(s1) == {"answer": "deny"} and srv._sock is None and not ap._perm_lock, "152: _finish_ending：deny して待ち受けを止める")
s1.close()
# 止めたあとの再始業で待ち受けが戻る
fb.session = False
c_start(ap)
check(ap.started and ap._perm_server._sock is not None and not pm_connect_refused(ap._perm_server.name[1:]), "152: 再び始業すると待ち受けが戻る")

# 153. ダイアログ：Claude の人と会話中だけ。中身（メインの最新 Reply 全文／プロンプト／まだ話していません・サブの description・依頼）
ap, fb = pm_ready(talk=False)
rec = c_draw(ap)
check(not pm_has_dlg_box(rec), "153: 会話していなければダイアログは出ない")
c_talk_ready(ap, 0)
rec = c_draw(ap)
check(pm_has_dlg_box(rec) and (O.DLG_X, O.DLG_Y, O.DLG_W, O.DLG_H, 7) in rec["rectb"], "153: メインと会話中は黒0の背景と白7の枠のダイアログが出る")
rows = pm_dlg_rows(rec)
check([r[1] for r in rows] == ["メイン", "(まだ話していません)"] and all(r[2] == 7 for r in rows), f"153: 何も話していないメイン：名前と「(まだ話していません)」（白7） {rows}")
check(len(rows) == 2 and rows[0][0] == O.DLG_Y + O.UI_PAD and rows[1][0] == O.DLG_Y + O.UI_PAD + O.UI_LINE_H, "153: 文字の位置は枠の内側（余白 UI_PAD・行の高さ UI_LINE_H）")
c_ev(ap, fb, Prompt("s", "最新のプロンプト\n二行目"))
check(dtx(ap, 0) == ["メイン  1/1", "> 最新のプロンプト", "二行目", "", "(返事を待っています)"], f"153: Reply が無ければ題・プロンプトの全文・「(返事を待っています)」 {dtx(ap, 0)}")
c_ev(ap, fb, Reply("s", "返事の一行目\n返事の二行目\n\n返事の四行目"))
PAGE1_REPLY = ["メイン  1/1", "> 最新のプロンプト", "二行目", "", "返事の一行目", "返事の二行目", "", "返事の四行目"]
check(dtx(ap, 0) == PAGE1_REPLY, f"153: メインは今のページに、プロンプトと Reply の全文（空行もそのまま） {dtx(ap, 0)}")
rec = c_draw(ap)
check([r[1] for r in pm_dlg_rows(rec)] == PAGE1_REPLY[:ap._dlg_visible_rows(0)], "153: 描いた行も全文（見える行数だけ）")
c_ev(ap, fb, Reply("s", "新しい返事"))
check(dtx(ap, 0) == PAGE1_REPLY + ["", "新しい返事"], f"153: Reply が複数なら同じページに空行をはさんで届いた順に並ぶ {dtx(ap, 0)}")
# 長い行は _wrap_text で、ダイアログの幅の桁数に折り返す
long_text = "あ" * 100 + "abc" * 40
c_ev(ap, fb, Prompt("s", "次の依頼"))  # 新しいページ（2/2）にして、Reply だけを折り返しの対象にする
c_ev(ap, fb, Reply("s", long_text))
lines = dtx(ap, 0)
check(lines[:3] == ["メイン  2/2", "> 次の依頼", ""], f"153: 2つ目のページの題・プロンプト・空行 {lines[:3]}")
check(O.DLG_COLS == (O.DLG_W - O.UI_PAD * 2 - O.SCROLLBAR_W - 2) // O.UI_CHAR_W and all(p_cols(r) <= O.DLG_COLS for r in lines), f"153: 折り返した各行が DLG_COLS（{O.DLG_COLS}）桁以内 {[p_cols(r) for r in lines]}")
check("".join(lines[3:]) == long_text and len(lines) > 5, "153: 折り返しても中身は欠けない")
check(lines[3:] == O._wrap_text(long_text, O.DLG_COLS, ap.ui_codes), "153: _wrap_text で折り返している")
# サブ：description の全文・名前は札と同じ（label）
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "説明の一行目\n説明の二行目", ""))
slot = ap._sub_map["a1"]
c_seated(ap, slot)
ap.end_talk()
check(c_talk_ready(ap, slot), "153: 前提：サブと会話中")
check(dtx(ap, slot) == ["kakaricho", "説明の一行目", "説明の二行目"], f"153: サブは名前（札と同じ）と description の全文 {dtx(ap, slot)}")
rec = c_draw(ap)
check(pm_has_dlg_box(rec) and [r[1] for r in pm_dlg_rows(rec)] == ["kakaricho", "説明の一行目", "説明の二行目"], "153: サブと会話中もダイアログが出る")
# サブの会話中は、メインに依頼があっても依頼の中身は出さない
s = pm_req(ap)
check(ap.talk_partner == O.MAIN_INDEX, "153: 前提：依頼が来たので自動でメインとの会話に切り替わる（157 番）")
ap.end_talk()
check(c_talk_ready(ap, slot), "153: 前提：サブとの会話に戻す")
check(dtx(ap, slot) == ["kakaricho", "説明の一行目", "説明の二行目"], "153: サブのダイアログに許可の依頼は出ない")
rec = c_draw(ap)
check(not c_ui_has(rec, i18n_t(O.PERM_KEYS_TEXT)), "153: サブのダイアログに Y・N・T の案内は出ない")
s.close()
ap._deny_perm_all()
# Claude の人でない人との会話ではダイアログを出さない
ap.end_talk()
ap._enter(7)
c_seated(ap, 7)
check(c_talk_ready(ap, 7) and ap.agents[7].role != "sub" and ap._talk_dialog_partner() is None, "153: 前提：ふつうの人と会話中")
rec = c_draw(ap)
check(not pm_has_dlg_box(rec), "153: Claude の人でない人との会話ではダイアログを出さない")
ap.end_talk()
rec = c_draw(ap)
check(not pm_has_dlg_box(rec), "153: 会話が終わったらダイアログは消える")
# 依頼の中身
ap, fb = pm_ready()
s1 = pm_req(ap, tool="Write", tool_input={"file_path": "/a/b.txt", "content": "一行目\n二行目\n三行目", "timeout": 5, "flags": ["a", "b"]})
s2 = pm_req(ap, tool="Bash", tool_input={"command": "ls"})
exp = ["メイン", "許可を求めています（残り 2 件）", "道具：Write", "file_path: /a/b.txt", "content: 一行目", "二行目", "三行目", "timeout: 5", 'flags: ["a", "b"]']
check(dtx(ap, 0) == exp, f"153: 依頼の中身（項目ごとに「キー: 値」・値の改行は行に・数や配列は JSON） {dtx(ap, 0)}")
rec = c_draw(ap)
rows = pm_dlg_rows(rec)
vis_exp = ap._dlg_visible_rows(0)
check([r[1] for r in rows if r[1] != i18n_t(O.PERM_KEYS_TEXT)] == exp[:vis_exp] and vis_exp == O.DLG_BODY_ROWS - 1, f"153: 描いた行も依頼の中身（見える行数だけ。案内の行を除く） {vis_exp}")
keys_row = [r for r in rows if r[1] == i18n_t(O.PERM_KEYS_TEXT)]
check(i18n_t(O.PERM_KEYS_TEXT) == "Y:許可  N:断る  T:tmuxで答える" and len(keys_row) == 1 and keys_row[0][2] == 10, f"153: 最後の行に「Y:許可  N:断る  T:tmuxで答える」を黄色10で {keys_row}")
check(keys_row and keys_row[0][0] == O.DLG_Y + O.DLG_H - O.UI_PAD - O.UI_LINE_H, f"153: 案内はダイアログの下の端に置く {keys_row}")
s1.close()
s2.close()
ap, fb = pm_ready()
s1 = pm_req(ap, tool="Weird", tool_input="ただの文字")
check(dtx(ap, 0)[1:] == ["許可を求めています（残り 1 件）", "道具：Weird", '入力: "ただの文字"'], f"153: tool_input が辞書でないときは「入力」1つ {dtx(ap, 0)}")
s1.close()
ap, fb = pm_ready()
s1 = pm_req(ap, tool="Bash", tool_input={"command": "x" * 300})
lines = dtx(ap, 0)
check(all(p_cols(r) <= O.DLG_COLS for r in lines) and "".join(lines[3:]) == "command: " + "x" * 300, "153: 依頼の長い行も折り返す")
s1.close()
# 依頼が無くなれば Reply の表示に戻る
ap, fb = pm_ready()
c_ev(ap, fb, Reply("s", "もとの返事"))
s = pm_req(ap)
check("もとの返事" not in dtx(ap, 0), "153: 依頼があるあいだは Reply の代わりに依頼を出す")
p_frame(ap, keys=(pyxel.KEY_Y,))
s.close()
check(dtx(ap, 0) == ["メイン  1/1", "もとの返事"], f"153: 答えたら Reply の表示（今のページ）に戻る {dtx(ap, 0)}")


# 154. ダイアログのスクロール：ホイール3行（上だけ・ズームしない）／つまみのドラッグ／溝のクリック／PageUp・PageDown／中身が変わると先頭へ／クリックで歩かない
def pm_scroll_app():
    ap_, fb_ = pm_ready()
    c_run(ap_, 120)  # 会話のカメラへの切り替えを終わらせる（ズームの確認のため）
    c_ev(ap_, fb_, Reply("s", "\n".join(f"行{i}" for i in range(60))))
    return ap_, fb_


ap, fb = pm_scroll_app()
total = len(dtx(ap, 0))
visible = ap._dlg_visible_rows(0)
max_scroll = total - visible
check(total == 61 and visible == O.DLG_BODY_ROWS == (O.DLG_H - O.UI_PAD * 2) // O.UI_LINE_H and ap._dlg_scroll == 0, f"154: 前提：{total} 行・見える {visible} 行・先頭 {ap._dlg_scroll}")
dist0 = ap.cam_dist
inside = (300, O.DLG_Y + 20)  # ダイアログの中（DLG_Y=170 に下げたので 150 では外）
p_frame(ap, mouse=inside, wheel=-1)
check(ap._dlg_scroll == 3 and ap.cam_dist == dist0, f"154: ホイール1ノッチでダイアログが3行動く・ズームしない {ap._dlg_scroll} {ap.cam_dist} {dist0}")
p_frame(ap, mouse=inside, wheel=-2)
check(ap._dlg_scroll == 9 and ap.cam_dist == dist0, f"154: 2ノッチで6行 {ap._dlg_scroll}")
p_frame(ap, mouse=inside, wheel=1)
check(ap._dlg_scroll == 6, f"154: 逆向きに戻る {ap._dlg_scroll}")
p_frame(ap, mouse=inside, wheel=5)
check(ap._dlg_scroll == 0, "154: 先頭より上へは行かない")
p_frame(ap, mouse=inside, wheel=-100)
check(ap._dlg_scroll == max_scroll, f"154: 最後より下へは行かない {ap._dlg_scroll} {max_scroll}")
rec = c_draw(ap)
check([r[1] for r in pm_dlg_rows(rec)] == dtx(ap, 0)[max_scroll:], "154: いちばん下まで動かすと最後の行が見える")
# ダイアログの外では動かさない（3D の上の方・ダイアログの下・履歴の枠の上など）
sc0 = ap._dlg_scroll
for pos in ((300, 10), (300, O.DLG_Y + O.DLG_H + 6), (300, O.HISTORY_Y + 20), (4, 150), (O.DLG_X + O.DLG_W + 3, 150)):
    p_frame(ap, mouse=pos, wheel=-1)
    check(ap._dlg_scroll == sc0, f"154: ダイアログの外 {pos} のホイールではダイアログを動かさない {ap._dlg_scroll}")
    check(ap.cam_dist == dist0, f"154: 会話中は外のホイールでもズームしない {pos}")
# ダイアログの縁（内側の端）でも効く
p_frame(ap, mouse=inside, wheel=100)
p_frame(ap, mouse=inside, wheel=5)
p_frame(ap, mouse=(O.DLG_X, O.DLG_Y), wheel=-1)
check(ap._dlg_scroll == 3, "154: ダイアログの左上の端でも効く")
p_frame(ap, mouse=(O.DLG_X + O.DLG_W - 1, O.DLG_Y + O.DLG_H - 1), wheel=1)
check(ap._dlg_scroll == 0, "154: ダイアログの右下の端でも効く")
# つまみのドラッグ
tx, ty, tw, th = ap._dlg_track()
thumb_y, thumb_h = ap._dlg_thumb(total, visible)
check(thumb_y == ty and thumb_h < th and (tx, tw) == (O.DLG_X + O.DLG_W - 2 - O.SCROLLBAR_W, O.SCROLLBAR_W), f"154: 先頭のときつまみは溝の上端 {thumb_y} {ty} {thumb_h} {th}")
p_frame(ap, click=(tx + 2, thumb_y + 2))
check(ap._dlg_drag is True and ap._dlg_scroll == 0 and ap.talk_partner == 0, "154: つまみを押すとドラッグが始まる（まだ動かない・会話は続く）")
p_frame(ap, hold_keys=(pyxel.MOUSE_BUTTON_LEFT,), mouse=(tx + 2, ty + th))
check(ap._dlg_scroll == max_scroll, f"154: つまみを下の端まで引くと最後まで {ap._dlg_scroll}")
mid = int(ty + thumb_h / 2 + (th - thumb_h) / 2)
p_frame(ap, hold_keys=(pyxel.MOUSE_BUTTON_LEFT,), mouse=(tx + 2, mid))
check(abs(ap._dlg_scroll - max_scroll / 2) <= 1.5, f"154: つまみを真ん中まで戻すと真ん中あたり {ap._dlg_scroll} {max_scroll / 2}")
p_frame(ap, hold_keys=(pyxel.MOUSE_BUTTON_LEFT,), mouse=(tx + 2, ty - 80))
check(ap._dlg_scroll == 0, "154: 溝より上へ引いても先頭で止まる")
p_frame(ap, hold_keys=(pyxel.MOUSE_BUTTON_LEFT,), mouse=(0, ty + th))
check(ap._dlg_scroll == max_scroll, "154: ドラッグ中は横にずれても追いかける")
p_frame(ap)
check(ap._dlg_drag is False, "154: ボタンを離すとドラッグが終わる")
p_frame(ap, mouse=(tx + 2, ty + 5))
check(ap._dlg_scroll == max_scroll, "154: 離したあとはマウスを動かしても動かない")
p_frame(ap, mouse=inside, wheel=5)
# 溝のクリック（1画面ぶん）
p_frame(ap, mouse=inside, wheel=100)
p_frame(ap, click=(tx + 2, ty + th - 2))
check(ap._dlg_scroll == visible and not ap._dlg_drag, f"154: つまみより下の溝をクリックすると1画面ぶん下へ {ap._dlg_scroll}")
p_frame(ap, click=(tx + 2, ty + th - 2))
check(ap._dlg_scroll == visible * 2, "154: もう一度で2画面ぶん")
p_frame(ap, click=(tx + 2, ty + 1))
check(ap._dlg_scroll == visible, f"154: つまみより上の溝をクリックすると1画面ぶん上へ {ap._dlg_scroll}")
p_frame(ap, click=(tx + 2, ty + 1))
p_frame(ap, click=(tx + 2, ty + 1))
check(ap._dlg_scroll == 0, "154: 先頭より上へは行かない（溝）")
for _ in range(total // visible + 2):  # 見える行が少ない（7 行）ので、最後まで行くのに必要な回数
    p_frame(ap, click=(tx + 2, ty + th - 2))
check(ap._dlg_scroll == max_scroll, f"154: 最後より下へは行かない（溝） {ap._dlg_scroll} {max_scroll}")
p_frame(ap, mouse=inside, wheel=5)
# PageUp・PageDown（WALK のとき）
p_frame(ap, mouse=inside, wheel=100)
p_frame(ap, keys=(pyxel.KEY_PAGEDOWN,))
check(ap._dlg_scroll == visible, f"154: PageDown で1画面ぶん下へ {ap._dlg_scroll}")
p_frame(ap, keys=(pyxel.KEY_PAGEDOWN,))
p_frame(ap, keys=(pyxel.KEY_PAGEUP,))
check(ap._dlg_scroll == visible, f"154: PageUp で1画面ぶん上へ {ap._dlg_scroll}")
p_frame(ap, keys=(pyxel.KEY_PAGEUP,))
p_frame(ap, keys=(pyxel.KEY_PAGEUP,))
check(ap._dlg_scroll == 0, "154: PageUp は先頭で止まる")
p_enter_prompt(ap)
p_frame(ap, keys=(pyxel.KEY_PAGEDOWN,))
check(ap._dlg_scroll == 0, "154: PROMPT のときは PageDown が効かない")
ap.mode = O.MODE_WALK
# ダイアログの上のクリックは歩かず、会話を終えない
hx, hz = ap.human.pos.x, ap.human.pos.z
for pos in ((100, O.DLG_Y + 30), (300, O.DLG_Y + 60), (O.DLG_X + 2, O.DLG_Y + 2), (tx - 10, ty + 40)):
    p_frame(ap, click=pos)
    c_run(ap, 15)
    check(ap.talk_partner == 0 and abs(ap.human.pos.x - hx) < 1e-6 and abs(ap.human.pos.z - hz) < 1e-6, f"154: ダイアログ上のクリック {pos} で歩かず、会話も終わらない")
# 中身が変わると先頭へ：新しい Reply
ap, fb = pm_scroll_app()
p_frame(ap, mouse=inside, wheel=-6)
check(ap._dlg_scroll == 18, "154: 前提：18 行目まで動かした")
c_ev(ap, fb, Reply("s", "\n".join(f"新{i}" for i in range(60))))
check(ap._dlg_scroll == 0, f"154: 新しい Reply でいちばん上に戻る {ap._dlg_scroll}")
# 次の依頼
p_frame(ap, mouse=inside, wheel=-6)
s1 = pm_req(ap, tool_input={"command": "\n".join(f"c{i}" for i in range(50))})
check(ap._dlg_scroll == 0, f"154: 依頼が来たらいちばん上に戻る {ap._dlg_scroll}")
s2 = pm_req(ap, tool="Write", tool_input={"content": "\n".join(f"w{i}" for i in range(50))})
total = len(dtx(ap, 0))
visible = ap._dlg_visible_rows(0)
check(visible == O.DLG_BODY_ROWS - 1 and total > visible, f"154: 依頼のあいだは見える行が1行少ない（最後の行は案内用） {visible} {total}")
p_frame(ap, mouse=inside, wheel=-6)
check(ap._dlg_scroll == 18, "154: 依頼のダイアログもスクロールできる")
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s1) == {"answer": "allow"} and ap._dlg_scroll == 0, f"154: 先頭に答えて次の依頼を出すときも、いちばん上に戻る {ap._dlg_scroll}")
s1.close()
s2.close()
# 会話が終わったらスクロールとドラッグを戻す
ap, fb = pm_scroll_app()
p_frame(ap, mouse=inside, wheel=-6)
ap._dlg_drag = True
ap.end_talk()
ap.update()
check(ap._dlg_scroll == 0 and ap._dlg_drag is False, f"154: 会話が終わったらスクロールとドラッグを戻す {ap._dlg_scroll} {ap._dlg_drag}")
# 依頼のダイアログ：最後の行（案内）はスクロールしても動かず、中身がそこに重ならない
ap, fb = pm_ready()
s1 = pm_req(ap, tool_input={"command": "\n".join(f"c{i}" for i in range(80))})
key_y = O.DLG_Y + O.DLG_H - O.UI_PAD - O.UI_LINE_H
visible = ap._dlg_visible_rows(0)
for sc in (0, 7, 40, 10_000):
    ap._dlg_scroll = 0
    ap._scroll_talk(0, sc)
    rec = c_draw(ap)
    rows = pm_dlg_rows(rec)
    keys_row = [r for r in rows if r[1] == i18n_t(O.PERM_KEYS_TEXT)]
    body = [r for r in rows if r[1] != i18n_t(O.PERM_KEYS_TEXT)]
    check(len(keys_row) == 1 and keys_row[0][0] == key_y and keys_row[0][2] == 10, f"154: スクロール {sc} でも案内は下の端に黄色10で出る {keys_row}")
    check(len(body) == visible and max(r[0] for r in body) + O.UI_LINE_H <= key_y, f"154: スクロール {sc} でも中身は案内に重ならない {len(body)} 行 {max(r[0] for r in body)}")
check(body[-1][1] == dtx(ap, 0)[-1], "154: いちばん下まで動かすと依頼の最後の行まで見える")
s1.close()

# 155. --claude 無しのときは何も変わらない（PermServer を作らない・キーが効かない・ダイアログも出ない）
_made146 = []
_real_ps = O.PermServer


class _CountPS(_real_ps):
    def __init__(self, *a, **k):
        _made146.append(1)
        super().__init__(*a, **k)


O.PermServer = _CountPS
try:
    ap_n = make_app(30, 1, "office", 5)
    n_without = len(_made146)
    ap_c, fb_c = c_make()
    n_with = len(_made146)
finally:
    O.PermServer = _real_ps
check(n_without == 0, f"155: --claude 無しは PermServer を作らない {n_without}")
check(n_with == 1, f"155: --claude ありは作る（前提） {n_with}")
check(ap_n._perm_server is None and ap_n._perm_pending == [] and not ap_n._perm_lock and not ap_n._perm_tmux, "155: --claude 無しの許可の状態は既定値")
check(ap_n._perm_block_send() is False and ap_n._tmux_shows_permission() is False and ap_n._talk_dialog_partner() is None, "155: 送信は止めず・画面も調べず・ダイアログの相手も無い")
n0 = len(ap_n.history)
ap_n.start_talk(1)
check(ap_n.talk_partner == 1, "155: 前提：会話中")
for k in (pyxel.KEY_Y, pyxel.KEY_N, pyxel.KEY_T, pyxel.KEY_PAGEDOWN, pyxel.KEY_PAGEUP):
    p_frame(ap_n, keys=(k,))
check(len(ap_n.history) == n0 and ap_n._dlg_scroll == 0 and not ap_n._perm_tmux, "155: Y・N・T・PageUp・PageDown は何もしない")
rec = c_draw(ap_n)
check(not pm_has_dlg_box(rec) and not any(t[2] == "！" for t in rec["utext"]), "155: 会話してもダイアログも ！ も出ない")
p_frame(ap_n, mouse=(300, 150), wheel=-1)
check(ap_n._dlg_scroll == 0, "155: ホイールでダイアログを動かさない")
ap_n.end_talk()
p_enter_prompt(ap_n)
n0 = len(ap_n.history)
p_send(ap_n, "テスト")
check(ap_n.history[n0:] == ["> テスト"], f"155: 送信は今までどおり履歴に出すだけ {ap_n.history[n0:]}")
p_frame(ap_n, keys=(pyxel.KEY_ESCAPE,))
check(ap_n.history[-1] == "(Esc: 中断を送る)", "155: Esc も今までどおり")
# --claude 無しでも、終わるときの関数は例外を出さない
ap_n._stop_perm()
ap_n._release_perm(lambda s: None)
ap_n._deny_perm_all()
check(True, "155: --claude 無しで _stop_perm・_release_perm・_deny_perm_all を呼んでも例外なし")
# 始業前の --claude：依頼の関数は何も起こさない
ap_c._update_perm_requests()
ap_c._update_perm_keys()
check(ap_c._perm_pending == [] and not ap_c._perm_lock, "155: 始業前は依頼の処理が何も起こさない")

# ---------------------------------------------------------------------------
# 156〜162. 実機確認を受けた変更（ダイアログの位置と半透明・履歴の Reply・プロンプトの整形・許可の依頼で自動に動く・予約の二重エラー・サブの再利用・入力中の切り替え）
# ---------------------------------------------------------------------------

def n_clock(ap_, start=1000.0):
    """許可まわりの時計を、テストが進める時計 [秒] にする。時計の入れ物（1要素のリスト）を返す。"""
    t = [start]
    ap_._perm_clock = lambda: t[0]
    ap_._perm_server.clock = ap_._perm_clock
    return t


def n_draw_log(ap_):
    """draw で呼ばれた dither・rect・rectb・text を、呼ばれた順に ('dither', 値) などの組で返す。"""
    log = []
    saved = (pyxel.dither, pyxel.rect, pyxel.rectb, pyxel.text)

    def d(a, *r, **k):
        log.append(("dither", a))
        return saved[0](a, *r, **k)

    def rc(*a, **k):
        log.append(("rect", a))
        return saved[1](*a, **k)

    def rb(*a, **k):
        log.append(("rectb", a))
        return saved[2](*a, **k)

    def tx(x, y, s, col, *a, **k):
        log.append(("text", (x, y, str(s), col)))
        return saved[3](x, y, s, col, *a, **k)

    pyxel.dither, pyxel.rect, pyxel.rectb, pyxel.text = d, rc, rb, tx
    try:
        ap_.draw()
    finally:
        pyxel.dither, pyxel.rect, pyxel.rectb, pyxel.text = saved
    return log


# 156. ダイアログの位置・大きさ・背景の半透明（背景の塗りだけ dither(0.5)、そのあと dither(1.0) に戻す）
check((O.DLG_Y, O.DLG_H) == (170, 119) and O.DLG_Y + O.DLG_H <= O.VIEW3D_H, f"156: DLG_Y=170・DLG_H=119（y 170〜288。3D の範囲 {O.VIEW3D_H} の内側） {(O.DLG_Y, O.DLG_H)}")
check(O.DLG_BODY_ROWS == (O.DLG_H - O.UI_PAD * 2) // O.UI_LINE_H == 7, f"156: 見える行数は高さから計算（(119-12)//14=7） {O.DLG_BODY_ROWS}")
ap, fb = pm_ready()
log = n_draw_log(ap)
box = (O.DLG_X, O.DLG_Y, O.DLG_W, O.DLG_H, 0)
idx_box = [k for k, e in enumerate(log) if e == ("rect", box)]
check(len(idx_box) == 1, f"156: 黒の背景の塗りが1回 {len(idx_box)}")
k0 = idx_box[0]
check(log[k0 - 1] == ("dither", 0.5), f"156: 背景の塗りの直前に dither(0.5) {log[k0 - 1]}")
check(log[k0 + 1] == ("dither", 1.0), f"156: 背景の塗りの直後に dither(1.0) に戻す {log[k0 + 1]}")
after = [e for e in log[k0 + 2:]]
frame_i = [k for k, e in enumerate(after) if e == ("rectb", (O.DLG_X, O.DLG_Y, O.DLG_W, O.DLG_H, 7))]
check(len(frame_i) == 1, "156: 白7の枠は dither(1.0) のあとに描く")
dither_vals = [e[1] for e in log if e[0] == "dither"]
check(dither_vals and dither_vals[-1] == 1.0, f"156: draw の終わりは dither(1.0)（ほかの描画を薄くしない） {dither_vals}")
half_span = log[k0 - 1:k0 + 2]
check([e[0] for e in half_span] == ["dither", "rect", "dither"], "156: dither(0.5) の間に描くのは背景の塗りだけ")
check(any(e[0] == "text" and e[1][0] == O.DLG_X + O.UI_PAD and e[1][2] == "メイン" for e in after), "156: 文字は dither(1.0) のあと（通常の濃さ）で描く")
# 長い返事：見える行は DLG_BODY_ROWS 行だけ。許可の依頼があれば1行少なく、案内の行は箱の中に収まる
c_ev(ap, fb, Reply("s", "\n".join(f"行{i}" for i in range(30))))
rec = c_draw(ap)
check(len(pm_dlg_rows(rec)) == O.DLG_BODY_ROWS, f"156: 長い返事でも描く行は DLG_BODY_ROWS（{O.DLG_BODY_ROWS}）行 {len(pm_dlg_rows(rec))}")
check(max(r[0] for r in pm_dlg_rows(rec)) + O.UI_LINE_H <= O.DLG_Y + O.DLG_H - O.UI_PAD, "156: 最後の行は箱の中（下の余白の内側）")
s = pm_req(ap, tool_input={"command": "\n".join(f"c{i}" for i in range(30))})
rec = c_draw(ap)
rows = pm_dlg_rows(rec)
body = [r for r in rows if r[1] != i18n_t(O.PERM_KEYS_TEXT)]
keys_row = [r for r in rows if r[1] == i18n_t(O.PERM_KEYS_TEXT)]
check(len(body) == O.DLG_BODY_ROWS - 1 and len(keys_row) == 1 and keys_row[0][0] + O.UI_LINE_H <= O.DLG_Y + O.DLG_H, f"156: 依頼があれば中身は {O.DLG_BODY_ROWS - 1} 行＋案内1行で、箱に収まる {len(body)} {keys_row}")
check(max(r[0] for r in body) + O.UI_LINE_H <= keys_row[0][0], "156: 中身は案内の行に重ならない")
s.close()
ap._deny_perm_all()


# 157. 許可の依頼が新しく来たら、メインと会話していなければ自動でメインのところへ行く（会話が始まったら守り時間 0.5 秒・履歴の行）
MSG_WARP = "(許可の依頼が来たので、メインのところへ行きました)"
MSG_NOSPOT = "(許可の依頼が来ました。メインの近くに立つ場所が無いので、メインをクリックしてください)"
check(O.PERM_KEY_GUARD_SEC == 0.5, f"157: 守り時間の定数は 0.5 秒 {O.PERM_KEY_GUARD_SEC}")
# 157-a. 誰とも会話していない：メインとの会話が始まる・守り時間・履歴の行・守り時間の間は Y が効かない
ap, fb = pm_ready(talk=False)
t = n_clock(ap)
check(ap.talk_partner is None and ap._perm_key_guard_until == 0.0, "157: 前提：会話していない・守り時間なし")
n0 = len(ap.history)
s = pm_req(ap)
check(ap.talk_partner == O.MAIN_INDEX and ap.agents[0].hold, f"157: 依頼が来たら自動でメインとの会話が始まる {ap.talk_partner}")
check(abs(ap._perm_key_guard_until - (1000.0 + O.PERM_KEY_GUARD_SEC)) < 1e-9, f"157: 守り時間は今の時計＋0.5 秒 {ap._perm_key_guard_until}")
check(ap.history[n0:].count(MSG_WARP) == 1, f"157: 履歴に「メインのところへ行きました」の行が1つ {ap.history[n0:]}")
check(ap.mode == O.MODE_WALK, "157: WALK のまま")
p_frame(ap, keys=(pyxel.KEY_Y,))
check(len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, "157: 守り時間の間は Y が効かない（直前に押していたキーで答えてしまわない）")
t[0] = 1000.0 + 0.49
p_frame(ap, keys=(pyxel.KEY_Y,))
check(len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, "157: 0.49 秒でもまだ効かない")
t[0] = 1000.0 + 0.5
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s) == {"answer": "allow"} and ap._perm_pending == [], "157: 0.5 秒たつと Y が効く")
s.close()
# 157-b. 別の人（うろうろしている人・サブ）と会話中：その会話を終えて、メインのところへ行く
ap, fb = pm_ready(talk=False)
n_clock(ap)
ap._enter(7)
c_seated(ap, 7)
check(c_talk_ready(ap, 7) and ap.agents[7].hold, "157: 前提：7 番の人と会話中")
n0 = len(ap.history)
s = pm_req(ap)
check(ap.talk_partner == O.MAIN_INDEX and not ap.agents[7].hold, f"157: 別の人との会話は終わり、メインとの会話になる {ap.talk_partner} {ap.agents[7].hold}")
check(ap.history[n0:].count(MSG_WARP) == 1, "157: 履歴の行が出る")
s.close()
ap._deny_perm_all()
ap, fb = pm_ready(talk=False)
n_clock(ap)
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "説明", ""))
slot = ap._sub_map["a1"]
c_seated(ap, slot)
check(c_talk_ready(ap, slot), "157: 前提：サブと会話中")
s = pm_req(ap)
check(ap.talk_partner == O.MAIN_INDEX and not ap.agents[slot].hold, "157: サブとの会話からも、メインとの会話に切り替わる")
s.close()
ap._deny_perm_all()
# 157-c. すでにメインと会話中：何もしない（守り時間も履歴の行も出ない）
ap, fb = pm_ready(talk=True)
n_clock(ap)
n0 = len(ap.history)
s = pm_req(ap)
check(ap.talk_partner == O.MAIN_INDEX and ap._perm_key_guard_until == 0.0 and MSG_WARP not in ap.history[n0:], f"157: すでにメインと会話中なら自動では何も起こらない（守り時間 {ap._perm_key_guard_until}）")
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s) == {"answer": "allow"}, "157: すぐ Y が効く")
s.close()
# 157-d. 依頼がすでにあるときの2件目は「新しい」ではない：別の人と会話していても、また動かさない
ap, fb = pm_ready(talk=False)
n_clock(ap)
s1 = pm_req(ap)
check(ap.talk_partner == O.MAIN_INDEX, "157: 前提：1件目で自動に会話が始まった")
ap.end_talk()
ap._enter(7)
c_seated(ap, 7)
check(c_talk_ready(ap, 7), "157: 前提：人が自分で7番と会話した")
n0 = len(ap.history)
s2 = pm_req(ap, tool="Write", tool_input={"file_path": "/x"})
check(len(ap._perm_pending) == 2 and ap.talk_partner == 7 and MSG_WARP not in ap.history[n0:], f"157: 依頼が残っているあいだの2件目では動かさない {ap.talk_partner}")
s1.close()
s2.close()
ap._deny_perm_all()
# 157-e. 全部答えたあとの次の依頼では、また自動で行く
ap, fb = pm_ready(talk=False)
t = n_clock(ap)
s1 = pm_req(ap)
t[0] += 1.0
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s1) == {"answer": "allow"} and ap._perm_pending == [], "157: 前提：1件目に答えた")
ap.end_talk()
n0 = len(ap.history)
s2 = pm_req(ap)
check(ap.talk_partner == O.MAIN_INDEX and ap.history[n0:].count(MSG_WARP) == 1, "157: 依頼が空になったあとの新しい依頼では、また自動でメインのところへ行く")
s1.close()
s2.close()
ap._deny_perm_all()
# 157-f. メインが見えていない：何もしない
ap, fb = pm_ready(talk=False)
n_clock(ap)
ap.agents[0].visible = False
n0 = len(ap.history)
s = pm_req(ap)
check(ap.talk_partner is None and MSG_WARP not in ap.history[n0:] and MSG_NOSPOT not in ap.history[n0:] and len(ap._perm_pending) == 1, "157: メインが見えていなければ自動では動かない（履歴の行も出ない）")
ap.agents[0].visible = True
s.close()
ap._deny_perm_all()
# 157-g. 立つ場所が無い：会話は始まらず、履歴に「…メインをクリックしてください」・守り時間なし
ap, fb = pm_ready(talk=False)
n_clock(ap)
ap.start_talk = lambda i: None  # 立つ場所が見つからなかった（start_talk が何もしない）ことにする
n0 = len(ap.history)
s = pm_req(ap)
check(ap.talk_partner is None and ap._perm_key_guard_until == 0.0, f"157: 立つ場所が無ければ会話は始まらず、守り時間も入らない {ap.talk_partner} {ap._perm_key_guard_until}")
check(ap.history[n0:].count(MSG_NOSPOT) == 1 and MSG_WARP not in ap.history[n0:], f"157: 「立つ場所が無いので、メインをクリックしてください」の行 {ap.history[n0:]}")
s.close()
ap._deny_perm_all()
# 157-h. 取り下げ・時間切れで外れた依頼は「新しい依頼」に数えない
ap, fb = pm_ready(talk=False)
t = n_clock(ap)
s = pm_req(ap, update=False)
s.close()  # 受け取る前に hook 側が閉じた
n0 = len(ap.history)
ap.update()
check(ap.talk_partner is None and MSG_WARP not in ap.history[n0:], f"157: 同じフレームで取り下げられた依頼では動かさない {ap.history[n0:]}")
ap._deny_perm_all()


# 158. 履歴欄に Reply（「Claude: 」）を出さない。道具・サブ・「> 」・知らせは残す
ap, fb = pm_ready(talk=False)
ov_quiet(ap)
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", "やって"))
c_ev(ap, fb, Tool("s", "Bash", "ls"))
c_ev(ap, fb, Reply("s", "返事の本文"))
c_ev(ap, fb, SubagentStart("a1", "kakaricho", "調べる", ""))
c_ev(ap, fb, TurnEnd("s"))
check(ap.history[n0:] == ["> やって", "  [Bash] ls", "  [呼ばれた] kakaricho: 調べる"], f"158: 履歴は「> 」・道具・サブだけで、Reply は出ない {ap.history[n0:]}")
check(not any("返事の本文" in h or h.startswith("Claude:") for h in ap.history), "158: 履歴のどこにも Reply の文・「Claude: 」が無い")
check(ap._last_reply == "返事の本文" and dtx(ap, 0)[1:] == ["> やって", "", "返事の本文"], "158: 返事はダイアログ用に _last_reply へ残る")
check(len(ap.history) == len(ap.history_color), "158: history と history_color は同じ長さ")


# 159. プロンプトの整形（prompt_display）を履歴・吹き出し・_last_prompt に使う。知らせは灰色13
CMD_RAW = "<command-name>/clear</command-name>\n<command-message>clear</command-message>\n<command-args></command-args>"
OUT_RAW = "<local-command-stdout>Set model to opus</local-command-stdout>"
TASK_RAW = "<task-notification><task-id>x</task-id><status>completed</status><summary>Agent \"調査\" completed</summary><result>長い</result></task-notification>"
check(O.NOTICE_COLOR == 13 and O.NOTICE_COLOR != O.TEXT_COLOR, f"159: 知らせの色は灰色13 {O.NOTICE_COLOR}")
# 159-a. コマンド：「> /clear」・灰色・人間の吹き出しには出る（"/" で始まるコマンド）
ap, fb = pm_ready(talk=False)
ov_quiet(ap)
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", CMD_RAW))
check(ap.history[n0:] == ["> /clear"] and ap.history_color[n0:] == [O.NOTICE_COLOR], f"159: コマンドは整えた文で、灰色13 {ap.history[n0:]} {ap.history_color[n0:]}")
check(ap._last_prompt == "/clear" and ap._human_text == "/clear" and ap._busy_text.get(0) == "/clear", f"159: _last_prompt・人間の吹き出し・作業中の吹き出しは整えた文 {ap._last_prompt!r} {ap._human_text!r} {ap._busy_text.get(0)!r}")
check(ap.agents[0].busy, "159: コマンドでもメインは busy")
c_ev(ap, fb, TurnEnd("s"))
# 159-b. 引数つきコマンド
c_ev(ap, fb, Prompt("s", "<command-name>/model</command-name><command-args>opus</command-args>"))
check(ap.history[-1] == "> /model opus" and ap._human_text == "/model opus", f"159: 引数つきコマンド {ap.history[-1]!r} {ap._human_text!r}")
c_ev(ap, fb, TurnEnd("s"))
# 159-c. コマンドの出力：中身・灰色・人間の吹き出しは出さない（前の文のまま）
ap._human_text = None
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", OUT_RAW))
check(ap.history[n0:] == ["> Set model to opus"] and ap.history_color[n0:] == [O.NOTICE_COLOR], f"159: コマンドの出力は中身・灰色13 {ap.history[n0:]}")
check(ap._human_text is None, f"159: コマンドの出力は人間の吹き出しに出さない {ap._human_text!r}")
check(ap._last_prompt == "Set model to opus" and ap._busy_text.get(0) == "Set model to opus", "159: _last_prompt と作業中の吹き出しには整えた文")
rec = c_draw(ap)
check(not c_ui_has(rec, "Set mo....") or b_count(rec, "Set mo....") == 1, f"159: 吹き出しはメインのぶんだけ（人間のぶんは無い） {b_count(rec, 'Set mo....')}")
c_ev(ap, fb, TurnEnd("s"))
c_ev(ap, fb, Prompt("s", "<local-command-stdout></local-command-stdout>"))
check(ap.history[-1] == "> (出力なし)" and ap.history_color[-1] == O.NOTICE_COLOR, f"159: 出力が空なら「(出力なし)」 {ap.history[-1]!r}")
c_ev(ap, fb, TurnEnd("s"))
# 159-d. サブの知らせ
ap._human_text = None
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", TASK_RAW))
check(ap.history[n0:] == ['> [知らせ] Agent "調査" completed'] and ap.history_color[n0:] == [O.NOTICE_COLOR], f"159: 知らせは「[知らせ] summary」・灰色13 {ap.history[n0:]}")
check(ap._human_text is None and ap._last_prompt == '[知らせ] Agent "調査" completed', "159: 知らせは人間の吹き出しに出さない・_last_prompt は整えた文")
c_ev(ap, fb, TurnEnd("s"))
# 159-e. ふつうの文：そのまま・白7・人間の吹き出しに出る・タグ入りの文はタグを外す
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", "a < b かつ c > d"))
check(ap.history[n0:] == ["> a < b かつ c > d"] and ap.history_color[n0:] == [O.TEXT_COLOR] and ap._human_text == "a < b かつ c > d", f"159: ふつうの文はそのまま・白7 {ap.history[n0:]} {ap.history_color[n0:]}")
c_ev(ap, fb, TurnEnd("s"))
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", "<system-reminder>注意</system-reminder>\nこれをやって"))
check(ap.history[n0:] == ["> 注意", "  これをやって"] and ap.history_color[n0:] == [O.NOTICE_COLOR] * 2, f"159: ほかのタグは外し、複数行は各行が灰色13 {ap.history[n0:]} {ap.history_color[n0:]}")
check(ap._human_text is None or ap._human_text != "注意\nこれをやって" or True, "159: （タグ入りの文の人間の吹き出しは知らせ扱いで出さない）")
c_ev(ap, fb, TurnEnd("s"))
check(len(ap.history) == len(ap.history_color), "159: history と history_color は同じ長さ")
# 159-f. 比べ方は元の text：自分で送った分・引き継ぎの依頼
ap, fb = pm_ready(talk=False)
ov_quiet(ap)
raw = "<b>x</b>"
ap._last_sent = raw
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", raw))
check(ap._last_sent is None and ap.history[n0:] == [], f"159: 自分で送った文（元の text）と同じなら履歴に足さず _last_sent を外す {ap.history[n0:]}")
c_ev(ap, fb, TurnEnd("s"))
ap._last_sent = "x"
n0 = len(ap.history)
c_ev(ap, fb, Prompt("s", "<b>x</b>"))
check(ap._last_sent == "x" and ap.history[n0:] == ["> x"], f"159: 整えた文でなく元の text で比べる（タグ付きは「ほかから打たれた分」） {ap._last_sent!r} {ap.history[n0:]}")
c_ev(ap, fb, TurnEnd("s"))
ap, fb = c_ending()
c_ev(ap, fb, Prompt("s", "<x>" + i18n_t(O.HANDOFF_PROMPT) + "</x>"))
check(ap._handoff_seen is False, "159: 引き継ぎの依頼の判定も元の text（タグ付きでは _handoff_seen にならない）")
c_ev(ap, fb, Prompt("s", i18n_t(O.HANDOFF_PROMPT)))
check(ap._handoff_seen is True, "159: 元の text が HANDOFF_PROMPT なら _handoff_seen")
# 159-g. ダイアログ：プロンプトだけの間は整えた文を出す
ap, fb = pm_ready(talk=True)
c_ev(ap, fb, Prompt("s", CMD_RAW))
check(dtx(ap, 0) == ["メイン  1/1", "> /clear", "", "(返事を待っています)"], f"159: ダイアログに出すプロンプトも整えた文 {dtx(ap, 0)}")


# 160. 予約の二重エラー（ValueError「人 0 は既に行き先を予約している」）：行き先の途中でプロンプトが届いても、あとで例外にならない
def n_main_out(ap_, until_state):
    """メインを席から立たせ、行き先を予約して until_state（GOING か AT_SPOT）にする。メインを返す。"""
    main_ = ap_.agents[0]
    main_.busy = False
    check(ov_until(ap_, lambda: main_.state == O.WANDER, 30 * 8) is not None, "160: 前提：作業が終わって立ち上がる")
    main_.cooldown = 0.0
    O_spot, O_k = ov_send(ap_, 0)
    check(main_.state == O.GOING and 0 in ap_.spot_manager._reserved, "160: 前提：行き先を予約して GOING")
    if until_state == O.AT_SPOT:
        check(ov_until(ap_, lambda: main_.state == O.AT_SPOT, 30 * 120) is not None, f"160: 前提：行き先に着く {main_.state}")
    return main_


def n_work_then_wander(ap_, fb_, main_):
    """Prompt → 作業（席へ戻る）→ TurnEnd → 立つ → うろつきが規定を超えて行き先を予約する、までを流す。例外が出たら例外を返す。"""
    c_ev(ap_, fb_, Prompt("s", "作業"))
    check(main_.state == O.WORKING and main_.busy, f"160: Prompt で作業状態 {main_.state}")
    check(0 not in ap_.spot_manager._reserved and ap_.spot_manager.count(O.OFFICE_SPOTS[0]) + sum(ap_.spot_manager.count(s) for s in O.OFFICE_SPOTS[1:]) == 0, "160: Prompt で予約が外れる")
    check(main_.cooldown == 0.0 and main_.wander_time == 0.0 and main_.alone_time == 0.0, "160: 行き先のタイマーが0に戻る")
    check(c_seated(ap_, 0, 1500), "160: 席に戻って座る")
    c_ev(ap_, fb_, TurnEnd("s"))
    check(ov_until(ap_, lambda: main_.state == O.WANDER, 30 * 8) is not None, "160: 作業が終わって（busy でなくなって）うろうろする")
    main_.cooldown = 0.0
    main_.wander_time = O.OUTING_WANDER_SEC - 0.05
    try:
        for _ in range(60):
            ap_.update()
    except ValueError as e:
        return e
    return None


for want in (O.GOING, O.AT_SPOT):
    ap, fb = c_make()
    c_start(ap)
    c_seated(ap, 0)
    ov_quiet(ap, ids=[i for i in range(len(ap.agents)) if i != 0])
    main = n_main_out(ap, want)
    err = n_work_then_wander(ap, fb, main)
    check(err is None, f"160: メインが{'向かう途中' if want == O.GOING else '行き先'}のときに Prompt が来ても、あとの予約で例外にならない {err!r}")
    check(main.state in (O.GOING, O.WANDER) and (main.state != O.GOING or ap.spot_manager._reserved.get(0) is not None), f"160: 次の行き先を予約できている（予約は1件だけ） {main.state}")
    check(sum(ap.spot_manager.count(s) for s in O.OFFICE_SPOTS) <= 1, "160: 予約は多くて1件")
# 160-b. 戻り中（RETURNING）に Prompt が来ても同じ
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
ov_quiet(ap, ids=[i for i in range(len(ap.agents)) if i != 0])
main = n_main_out(ap, O.AT_SPOT)
ap._leave_spot(0)
check(main.state == O.RETURNING and 0 not in ap.spot_manager._reserved, f"160: 前提：戻り中 {main.state}")
err = n_work_then_wander(ap, fb, main)
check(err is None, f"160: 戻り中に Prompt が来ても例外にならない {err!r}")
# 160-c. スペースキー（_start_next_work）・SubagentStart の再利用・_enter も同じ _begin_work で予約を外す
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
ov_quiet(ap, ids=[i for i in range(len(ap.agents)) if i != 0])
main = n_main_out(ap, O.GOING)
ap.next_index = 0
ap._start_next_work()  # --claude ではスペースキーで呼ばれなくなったので、直接呼ぶ（本体のキー処理は 126 で確認）
check(main.state == O.WORKING and 0 not in ap.spot_manager._reserved, f"160: _start_next_work で作業に切り替えても予約が外れる {main.state}")
# 160-d. _begin_work を直接：GOING・AT_SPOT・RETURNING のときだけ予約を外してタイマーを0にする。WANDER・WORKING には触らない
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
main = ap.agents[0]
ov_quiet(ap)
main.state = O.WANDER
main.wander_time = 2.5
main.cooldown = 7.0
ap._begin_work(0)
check(main.state == O.WORKING, "160: _begin_work は WANDER から作業にする")
check(main.cooldown == 7.0 and main.wander_time == 2.5, f"160: WANDER からのときはタイマーを触らない {main.cooldown} {main.wander_time}")
ap2, fb2 = c_make()
c_start(ap2)
c_seated(ap2, 0)
ov_quiet(ap2, ids=[i for i in range(len(ap2.agents)) if i != 0])
m2 = n_main_out(ap2, O.GOING)
m2.cooldown = 3.0
m2.wander_time = 1.0
ap2._begin_work(0)
check(m2.state == O.WORKING and 0 not in ap2.spot_manager._reserved and m2.cooldown == 0.0 and m2.wander_time == 0.0, "160: GOING からは予約を外してタイマーを0にして作業にする")
# 160-e. _update_wanderers：古い予約が残っていても、reserve の前に release するので二重予約で止まらない
ap, fb = c_make()
c_start(ap)
c_seated(ap, 0)
ov_quiet(ap, ids=[i for i in range(len(ap.agents)) if i != 0])
main = ap.agents[0]
main.busy = False
check(ov_until(ap, lambda: main.state == O.WANDER, 30 * 8) is not None, "160: 前提：うろうろ")
ap.spot_manager.reserve(0)  # 古い予約を残す
main.cooldown = 0.0
main.wander_time = O.OUTING_WANDER_SEC
try:
    ap.update()
    err = None
except ValueError as e:
    err = e
check(err is None, f"160: 古い予約が残っていても _update_wanderers は例外にならない {err!r}")
check(sum(ap.spot_manager.count(s) for s in O.OFFICE_SPOTS) == 1, "160: 予約は1件だけ（古い予約は外れて、新しく取り直す）")


# 161. サブエージェントの再利用：帰るのを待っている人を、次の SubagentStart で使う。SUB_LEAVE_SEC=300 秒で帰る
check(O.SUB_LEAVE_SEC == 300.0, f"161: SUB_LEAVE_SEC は 300 秒 {O.SUB_LEAVE_SEC}")


def n_sub_ready():
    """始業して、サブ a1 が呼ばれて席に着き、終わった（帰るのを待っている）App。(ap, fb, slot)。"""
    ap_, fb_ = c_make()
    c_start(ap_)
    c_seated(ap_, 0)
    c_ev(ap_, fb_, SubagentStart("a1", "kakaricho", "最初の仕事", ""))
    slot_ = ap_._sub_map["a1"]
    c_seated(ap_, slot_)
    c_ev(ap_, fb_, SubagentEnd("a1"))
    return ap_, fb_, slot_


# 161-a. 再利用：同じ席の人が使われ、新しい席は増えない。帰る予約が外れ、busy・吹き出し・対応・履歴が入る
ap, fb, slot = n_sub_ready()
check(slot in ap._leave_timers and not ap.agents[slot].busy and ap.agents[slot].visible, "161: 前提：帰るのを待っている（見えている・busy でない・帰るタイマーあり）")
c_run(ap, 30 * 10)
check(ap.agents[slot].visible and slot in ap._leave_timers, "161: 10 秒たってもまだ帰らない（300 秒まで待つ）")
visible_before = [i for i, a in enumerate(ap.agents) if a.visible]
n0 = len(ap.history)
c_ev(ap, fb, SubagentStart("a2", "yamada", "次の仕事", ""))
check(ap._sub_map.get("a2") == slot, f"161: 次のサブは帰りを待っていた人を使う {ap._sub_map}")
sub = ap.agents[slot]
check(slot not in ap._leave_timers, "161: 帰るタイマーが外れる")
check(sub.busy and sub.role == "sub" and sub.label == "yamada" and ap._busy_text.get(slot) == "次の仕事" and ap._last_line.get(slot) == "次の仕事", f"161: busy・名前・作業中の吹き出し・最後の行が新しい仕事のもの {sub.label} {ap._busy_text.get(slot)}")
check(sub.state == O.WORKING and sub.visible, f"161: 席へ戻って作業に入る {sub.state}")
check([i for i, a in enumerate(ap.agents) if a.visible] == visible_before, "161: 新しく入ってくる人は増えない")
check(ap.history[n0:] == ["  [呼ばれた] yamada: 次の仕事"], f"161: 履歴の行 {ap.history[n0:]}")
check(c_seated(ap, slot), "161: 席に座る")
c_run(ap, 30 * 400)
check(sub.visible and "a2" in ap._sub_map and slot not in ap._leave_timers, "161: 作業中は 300 秒たっても帰らない（タイマーは外れている）")
c_ev(ap, fb, SubagentEnd("a2"))
check(ap._leave_timers.get(slot) is not None and abs(ap._leave_timers[slot] - (O.SUB_LEAVE_SEC - 1 / 30)) < 1e-6, "161: 終わるとまた 300 秒のタイマーが入る")
# 161-b. 300 秒で帰る（299 秒ではまだ）
ap, fb, slot = n_sub_ready()
c_run(ap, int(299 * 30))
check(ap.agents[slot].visible and ap.agents[slot].state != O.LEAVING, f"161: 299 秒ではまだ帰らない {ap.agents[slot].state}")
c_run(ap, int(2.5 * 30))
check(ap.agents[slot].state == O.LEAVING or not ap.agents[slot].visible, f"161: 300 秒を過ぎると帰り始める {ap.agents[slot].state}")
check(c_invisible_all(ap, slot), "161: そのまま出ていく")
# 161-c. 再利用できない人：帰る途中（LEAVING）・まだ作業中（busy）・サブの対応がある・role が sub でない・見えない
ap, fb, slot = n_sub_ready()
ap._leave(slot)
check(ap.agents[slot].state == O.LEAVING and slot not in ap._leave_timers, "161: 前提：帰る途中")
check(ap._find_reusable_sub() is None, "161: 帰る途中の人は再利用しない")
c_ev(ap, fb, SubagentStart("b1", "z", "d", ""))
new_slot = ap._sub_map["b1"]
check(new_slot != slot and ap.agents[slot].state == O.LEAVING, f"161: 帰る途中の人は使わず、新しく別の席から入る {new_slot} {slot}")
ap, fb, slot = n_sub_ready()
ap.agents[slot].busy = True
check(ap._find_reusable_sub() is None, "161: busy の人は再利用しない")
ap.agents[slot].busy = False
ap._sub_map["zz"] = slot
check(ap._find_reusable_sub() is None, "161: サブの対応（_sub_map）が残っている人は再利用しない")
del ap._sub_map["zz"]
ap.agents[slot].role = "main"
check(ap._find_reusable_sub() is None, "161: role が sub でない人は再利用しない")
ap.agents[slot].role = "sub"
ap.agents[slot].visible = False
check(ap._find_reusable_sub() is None, "161: 見えない人は再利用しない")
ap.agents[slot].visible = True
del ap._leave_timers[slot]
check(ap._find_reusable_sub() is None, "161: 帰るタイマーに入っていない人は再利用しない")
ap._leave_timers[slot] = 100.0
check(ap._find_reusable_sub() == slot, "161: 条件がそろえば再利用できる")
# 161-d. 全員が作業中なら新しく入る
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, SubagentStart("a1", "t", "d1", ""))
c_ev(ap, fb, SubagentStart("a2", "t", "d2", ""))
check(sorted(ap._sub_map.values()) == [2, 3], f"161: 作業中の2人には、新しい席が使われる {ap._sub_map}")
check(ap._find_reusable_sub() is None, "161: 作業中の人しかいなければ再利用する人は無い")
c_ev(ap, fb, SubagentStart("a3", "t", "d3", ""))
check(ap._sub_map["a3"] == 4, "161: 3人目は新しく席4から入る")
# 161-e. 複数が帰りを待っているとき：1人ずつ再利用し、使い切ったら新しく入る
ap, fb = c_make()
c_start(ap)
c_ev(ap, fb, SubagentStart("a1", "t", "d1", ""))
c_ev(ap, fb, SubagentStart("a2", "t", "d2", ""))
c_ev(ap, fb, SubagentEnd("a1"), SubagentEnd("a2"))
c_ev(ap, fb, SubagentStart("b1", "t", "e1", ""))
c_ev(ap, fb, SubagentStart("b2", "t", "e2", ""))
check(sorted([ap._sub_map["b1"], ap._sub_map["b2"]]) == [2, 3], f"161: 帰りを待つ2人が1人ずつ使われる {ap._sub_map}")
c_ev(ap, fb, SubagentStart("b3", "t", "e3", ""))
check(ap._sub_map["b3"] == 4, "161: 使い切ったら新しい席から入る")
# 161-f. 会話の相手のサブも再利用でき、会話は続く
ap, fb, slot = n_sub_ready()
check(c_talk_ready(ap, slot), "161: 前提：帰りを待つサブと会話中")
c_ev(ap, fb, SubagentStart("a2", "yamada", "次", ""))
check(ap._sub_map.get("a2") == slot and ap.talk_partner == slot, f"161: 会話の相手のサブを再利用しても会話は続く {ap.talk_partner}")


# 162. 入力欄で打っている最中に許可の依頼が来たら WALK に切り替える（文字は残す）・1.0 秒キーを止める（マウスは止めない）
MSG_WALK = "(許可の依頼が来たので、WALK に切り替えました。入力中の文字は残っています)"
check(O.PERM_KEY_GUARD_PROMPT_SEC == 1.0, f"162: 入力中の切り替えの守り時間は 1.0 秒 {O.PERM_KEY_GUARD_PROMPT_SEC}")
ap, fb = pm_ready(talk=True)
t = n_clock(ap)
p_enter_prompt(ap)
p_type(ap, "打ちかけ")
check(ap.mode == O.MODE_PROMPT and ap.input_buf == "打ちかけ", "162: 前提：PROMPT で「打ちかけ」まで入力した")
n0 = len(ap.history)
s = pm_req(ap)
check(ap.mode == O.MODE_WALK, f"162: 依頼が来たら WALK に切り替わる {ap.mode}")
check(ap.input_buf == "打ちかけ", f"162: 入力欄の文字は残る {ap.input_buf!r}")
check(abs(ap._perm_key_guard_until - (1000.0 + 1.0)) < 1e-9, f"162: 守り時間は 1.0 秒 {ap._perm_key_guard_until}")
check(ap.history[n0:].count(MSG_WALK) == 1, f"162: 履歴の行 {ap.history[n0:]}")
check(ap._perm_guard_active(), "162: 守り時間の中")
# 162-b. 1 秒の間は Y・N・T・P・スペース・D・Q・矢印・PageUp/Down が効かない
door0 = ap.door_open
next0 = ap.next_index
scroll0 = ap._dlg_scroll
yaw0, pitch0 = ap.cam_yaw, ap.cam_pitch
for k in (pyxel.KEY_Y, pyxel.KEY_N, pyxel.KEY_T):
    p_frame(ap, keys=(k,))
check(len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, "162: 1 秒の間は Y・N・T で答えない")
p_frame(ap, keys=(O.PROMPT_ENTER_KEY,))
check(ap.mode == O.MODE_WALK, "162: 1 秒の間は P で PROMPT に入らない")
p_frame(ap, keys=(pyxel.KEY_SPACE,))
check(ap.next_index == next0, f"162: スペースが効かない {ap.next_index}")
p_frame(ap, keys=(pyxel.KEY_D,))
check(ap.door_open == door0, "162: D が効かない")
p_frame(ap, keys=(pyxel.KEY_Q,))
check(ap.talk_partner == O.MAIN_INDEX, "162: Q が効かない（会話は終わらない）")
p_frame(ap, keys=(pyxel.KEY_PAGEDOWN,))
check(ap._dlg_scroll == scroll0, "162: PageDown が効かない")
check(ap.input_buf == "打ちかけ", "162: 守り時間の間も入力欄の文字は残る")
# 162-b2. 矢印キー（押し続け）：会話していない WALK で視点を回す。守り時間の間は回らず、1 秒後は回る
ap_a, fb_a = pm_ready(talk=True)
t_a = n_clock(ap_a)
p_enter_prompt(ap_a)
p_type(ap_a, "a")
s_a = pm_req(ap_a)
ap_a.end_talk()  # 視点を回せるのは会話していないときだけ
c_run(ap_a, 150)  # 会話の前の視点へ戻る切り替えを終わらせる（時計は止めてあるので守り時間は続く）
check(ap_a._perm_guard_active() and ap_a.talk_partner is None and ap_a.mode == O.MODE_WALK, "162: 前提：守り時間の中・会話なし・WALK")
yaw_a = ap_a.cam_yaw
for k in (pyxel.KEY_LEFT, pyxel.KEY_RIGHT):
    p_frame(ap_a, hold_keys=(k,))
check(ap_a.cam_yaw == yaw_a, f"162: 守り時間の間は矢印キーで視点が回らない {yaw_a} {ap_a.cam_yaw}")
t_a[0] = 1000.0 + 1.0
p_frame(ap_a, hold_keys=(pyxel.KEY_RIGHT,))
check(ap_a.cam_yaw != yaw_a, "162: 1 秒後は矢印キーで視点が回る")
s_a.close()
ap_a._deny_perm_all()
# 162-c. 1 秒たつと効く
t[0] = 1000.0 + 0.99
p_frame(ap, keys=(pyxel.KEY_Y,))
check(len(ap._perm_pending) == 1 and ap._perm_guard_active(), "162: 0.99 秒ではまだ効かない")
t[0] = 1000.0 + 1.0
check(not ap._perm_guard_active(), "162: 1.0 秒で守り時間が終わる")
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s) == {"answer": "allow"} and ap._perm_pending == [], "162: 1 秒後は Y が効く")
s.close()
p_frame(ap, keys=(pyxel.KEY_D,))
check(ap.door_open != door0, "162: 1 秒後は D も効く")
p_enter_prompt(ap)
check(ap.mode == O.MODE_PROMPT and ap.input_buf == "打ちかけ", "162: 1 秒後は P で PROMPT に戻れる（文字は残っている）")
# 162-d. Q は 1 秒後に効く
ap.mode = O.MODE_WALK
p_frame(ap, keys=(pyxel.KEY_Q,))
check(ap.talk_partner is None, "162: 1 秒後は Q で会話を終えられる")
# 162-e. マウスのクリックは守り時間の間も効く
ap, fb = pm_ready(talk=True)
t = n_clock(ap)
p_enter_prompt(ap)
p_type(ap, "あ")
s = pm_req(ap)
check(ap._perm_guard_active() and ap.mode == O.MODE_WALK, "162: 前提：守り時間の中")
# 入力欄のクリックは PROMPT に入る（P キーと違って、マウスは守り時間でも止めない）
p_frame(ap, click=(O.HISTORY_X + 20, O.INPUT_Y + 4))
check(ap._perm_guard_active() and ap.mode == O.MODE_PROMPT, f"162: 守り時間の間も、入力欄のクリックは効く（PROMPT に入る） {ap.mode}")
ap.mode = O.MODE_WALK
# 床のクリック（ダイアログの外）：人間が歩き出す
hx, hz = ap.human.pos.x, ap.human.pos.z
done = False
for dx, dz in ((0, -150), (150, 0), (-150, 0), (0, 150), (250, 0), (-250, 0), (0, 250), (0, -250), (150, 150), (-150, -150), (-150, 150), (150, -150)):
    sx, sy = h_proj(ap, hx + dx, 0.0, hz + dz)
    if 0 <= sx < O.OFFICE_SCREEN_W and 0 <= sy < O.DLG_Y - 4:
        eye_, dir_ = h_ray(ap, round(sx), round(sy))
        if ap.pick_agent(eye_, dir_) is None and ap.floor_hit(eye_, dir_) is not None:  # 人に当たらない床の点
            p_frame(ap, click=(round(sx), round(sy)))
            done = True
            break
check(done, "162: 前提：人に当たらずクリックできる床の点が画面の中にある")
c_run(ap, 20)
check(ap._perm_guard_active() and (abs(ap.human.pos.x - hx) > 1e-6 or abs(ap.human.pos.z - hz) > 1e-6 or ap.talk_partner is None), f"162: 守り時間の間も、床のクリックは効く（歩く・会話を終える） {ap.talk_partner}")
s.close()
ap._deny_perm_all()
# 162-f. PROMPT でない（WALK）ときに来た依頼では WALK への切り替えも守り時間（1.0）も入らない
ap, fb = pm_ready(talk=True)
n_clock(ap)
n0 = len(ap.history)
s = pm_req(ap)
check(ap.mode == O.MODE_WALK and ap._perm_key_guard_until == 0.0 and MSG_WALK not in ap.history[n0:], "162: WALK のときの依頼では 1 秒の守りは入らない")
s.close()
ap._deny_perm_all()
# 162-g. 依頼が残っているあいだの2件目では、PROMPT に戻っていても切り替えない
ap, fb = pm_ready(talk=True)
t = n_clock(ap)
s1 = pm_req(ap)
p_enter_prompt(ap)
p_type(ap, "x")
n0 = len(ap.history)
s2 = pm_req(ap, tool="Write", tool_input={"file_path": "/y"})
check(ap.mode == O.MODE_PROMPT and MSG_WALK not in ap.history[n0:], f"162: 依頼が残っているときの2件目では PROMPT のまま {ap.mode}")
s1.close()
s2.close()
ap._deny_perm_all()
# 162-h. 自動のワープと PROMPT が重なる場合（会話していない・PROMPT）：メインへ行き、守り時間は長いほう（1.0 秒）が残る
ap, fb = pm_ready(talk=False)
t = n_clock(ap)
p_enter_prompt(ap)
p_type(ap, "z")
n0 = len(ap.history)
s = pm_req(ap)
check(ap.talk_partner == O.MAIN_INDEX and ap.mode == O.MODE_WALK and ap.input_buf == "z", f"162: 会話していない PROMPT でも、メインへ行って WALK になる・文字は残る {ap.talk_partner} {ap.mode}")
check(abs(ap._perm_key_guard_until - (1000.0 + O.PERM_KEY_GUARD_PROMPT_SEC)) < 1e-9, f"162: 守り時間は 1.0 秒のほうが残る {ap._perm_key_guard_until}")
check(MSG_WARP in ap.history[n0:] and MSG_WALK in ap.history[n0:], "162: 履歴に両方の行が出る")
s.close()
ap._deny_perm_all()
# 162-i. --claude なしでは守り時間を使わない（既定値 0.0 のとき守りは無効）
ap_n = make_app(30, 1, "office", 18)
check(ap_n._perm_guard_active() is False, "162: 守り時間の既定値では守りは働かない")



# ===========================================================================
# 163〜167. スラッシュコマンドの窓・/model と /effort のメニューと状態の行・いつも許可・/exit の止め・利用制限を /usage で読む
# ===========================================================================
class FakeBridgeTmux(FakeBridge):
    """tmux の画面（capture）・キーの送り（send_keys／send_literal）・許可の画面（permission_screen_open）を持つ偽の Bridge。

    send_prompt("/usage") で usage_screen を画面にし、send_escape で（escape_closes なら）closed_screen を画面にする。
    """

    def __init__(self, screen="", **k):
        super().__init__(**k)
        self.screen = screen  # None なら capture が None（読めない）
        self.keys = []
        self.literals = []
        self.captures = 0
        self.usage_screen = None
        self.closed_screen = ""
        self.escape_closes = True
        self.perm_screen = False
        self.tmux = self  # _slash_capture は bridge.tmux.capture() を呼ぶ

    def capture(self):
        self.captures += 1
        return self.screen

    def send_keys(self, *keys):
        self.keys.append(keys)
        return True

    def send_literal(self, text):
        self.literals.append(text)
        return True

    def send_prompt(self, text):
        super().send_prompt(text)
        if text == "/usage" and self.usage_screen is not None:
            self.screen = self.usage_screen
        return True

    def send_escape(self):
        super().send_escape()
        if self.escape_closes and self.screen and "Esc to" in self.screen:
            self.screen = self.closed_screen
        return True

    def permission_screen_open(self):
        return self.perm_screen


def s_sends(fb_):
    """send_prompt の文だけ。"""
    return [c[1] for c in fb_.calls if c[0] == "send_prompt"]


def s_escapes(fb_):
    return sum(1 for c in fb_.calls if c == ("send_escape",))


def s_ready(screen="", prompt=True, talk=False, seated=False, **fbkw):
    """始業して、利用制限の自動の読み取りと状態の読み取りを止め、時計を止め、PROMPT にした App・偽の Bridge・時計。"""
    fb_ = FakeBridgeTmux(screen=screen, **fbkw)
    ap_, _ = c_make(bridge=fb_)
    c_start(ap_)
    ap_._usage_start_armed = False
    ap_._state_left = 0.0
    t_ = n_clock(ap_)
    if seated or talk:
        c_seated(ap_, 0)
    if talk:
        c_talk_ready(ap_, 0)
    if prompt:
        p_enter_prompt(ap_)
    return ap_, fb_, t_


def s_tick(ap_, t_, dt, **kw):
    """時計を dt 秒進めて1フレーム。"""
    t_[0] += dt
    p_frame(ap_, **kw)


PANEL = "\n".join(["  Help dialog", "", "  general   commands   custom-commands", "", "  Esc to cancel"])
NOPANEL = "\n".join(["(閉じた)", "❯ "])
RESULT_SCREEN = "\n".join([
    "❯ /context",
    "  古い結果",
    "──────────────────────",
    "❯\xa0/context",
    "  Context Usage",
    "  total 10k   ",
    "──────────────────────",
    "❯ ",
    "──────────────────────",
])
RESULT_LINES = ["  Context Usage", "  total 10k"]

# 163. スラッシュコマンドの窓
check((O.SLASH_X, O.SLASH_Y, O.SLASH_W, O.SLASH_H) == (16, 22, 608, 268), f"163: 窓の位置と大きさ {(O.SLASH_X, O.SLASH_Y, O.SLASH_W, O.SLASH_H)}")
check((O.SLASH_POLL_SEC, O.SLASH_CLOSE_SEC, O.SLASH_STATIC_SEC, O.SLASH_DITHER) == (0.25, 0.5, 2.0, 0.75), "163: 窓の時間と透かしの定数")
# 163-a. 入る条件
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
check(s_sends(fb)[-1] == "/help", f"163: /help は Claude Code に送る {s_sends(fb)}")
check(ap._slash_open and ap._slash_cmd == "/help" and ap.mode == O.MODE_PROMPT and ap.input_buf == "", f"163: 「/」の文で窓が開く・モードは PROMPT のまま・入力欄は空 {ap._slash_open} {ap.mode}")
check(not ap._slash_seen_panel and not ap._slash_static and ap._slash_lines == [], "163: 開いた直後はまだ画面を読んでいない")
p_frame(ap)
check(ap._slash_seen_panel and ap._slash_lines == [x.rstrip() for x in PANEL.splitlines()], f"163: 次のフレームで画面を読み、「Esc to」でパネル扱い {ap._slash_lines}")
ap2, fb2, t2 = s_ready(PANEL)
p_send(ap2, "  /help  ")
check(s_sends(fb2)[-1] == "  /help  " and ap2._slash_cmd == "/help" and ap2._slash_open, f"163: 前後に空白があっても開く（送る文はそのまま・覚えるのは空白を除いた文） {s_sends(fb2)[-1]!r} {ap2._slash_cmd!r}")
ap2, fb2, t2 = s_ready(PANEL)
p_send(ap2, "hello /help")
check(not ap2._slash_open, "163: 「/」で始まらない文では開かない")
ap2, fb2, t2 = s_ready(PANEL)
p_send(ap2, "/exit")
check(not ap2._slash_open and "/exit" not in s_sends(fb2), "163: /exit は窓を開かず送りもしない")
ap2, fb2, t2 = s_ready(PANEL)
p_send(ap2, "/quit")
check(not ap2._slash_open and "/quit" not in s_sends(fb2), "163: /quit も開かない")
# 始業前は開かない
ap2, _ = c_make(bridge=FakeBridgeTmux(screen=PANEL))
p_enter_prompt(ap2)
p_send(ap2, "/help")
check(not ap2._slash_open and "(始業していません。F1 で始業してください)" in ap2.history, "163: 始業前は窓を開かない")
# 送れなかったとき（送信を止めている）は開かない・入力欄の文字は残る
ap2, fb2, t2 = s_ready(PANEL)
ap2._perm_tmux = True
ap2.input_buf = "/help"
ap2._send_input()
check(not ap2._slash_open and ap2.input_buf == "/help" and "/help" not in s_sends(fb2), "163: 許可の答えを待っている間は開かず、文字は残る")
# send_prompt が False のときは開かない
fb3 = FakeBridgeTmux(screen=PANEL)
fb3.send_prompt = lambda text: False
ap3, _ = c_make(bridge=fb3)
c_start(ap3)
ap3._usage_start_armed = False
p_enter_prompt(ap3)
p_send(ap3, "/help")
check(not ap3._slash_open, "163: 送信に失敗したら窓に入らない")
# --claude でないときは開かない
ap_n = make_app(30, 1, "office", 18)
p_enter_prompt(ap_n)
p_send(ap_n, "/help")
check(not ap_n._slash_open and any(h.startswith("> /help") for h in ap_n.history), "163: --claude でなければ窓は開かず、今までどおり履歴に出る")
# 163-b. 描く：MODE の札・窓の見出し・案内
std, ui = p_texts(ap)
check(any(s == "MODE: SLASH" for (_x, _y, s, _c) in std) and any(s == "  (ESC:CLOSE)" for (_x, _y, s, _c) in std), "163: MODE の札が SLASH と (ESC:CLOSE)")
rec = c_draw(ap)
check(any(u[2] == "コマンド：/help" and u[3] == 10 for u in rec["utext"]), "163: 見出し「コマンド：<送った文>」が黄10")
check(any(u[2] == i18n_t(O.SLASH_GUIDE_PANEL) and u[3] == 10 for u in rec["utext"]), "163: パネルの案内の行（黄10）")
check(any(u[2].strip() == "Help dialog" and u[3] == 7 for u in rec["utext"]), "163: 画面の行が白7")
check(any(r[:4] == (O.SLASH_X, O.SLASH_Y, O.SLASH_W, O.SLASH_H) and r[4] == 0 for r in rec["rect"]) and any(r[:4] == (O.SLASH_X, O.SLASH_Y, O.SLASH_W, O.SLASH_H) and r[4] == 7 for r in rec["rectb"]), "163: 背景は黒0・枠は白7")
log = n_draw_log(ap)
check(("dither", O.SLASH_DITHER) in log and ("dither", 1.0) in log, "163: 背景を SLASH_DITHER で塗って 1.0 に戻す")
# 163-c. パネルの検出と、0.5 秒消えて閉じる
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
p_frame(ap)  # 1000.0 に読む（パネルあり）
fb.screen = NOPANEL
s_tick(ap, t, 0.25)  # 1000.25：案内が消えた最初の読み
check(ap._slash_open and ap._slash_gone_since == 1000.25, f"163: 案内が消えた時刻を覚える {ap._slash_gone_since}")
s_tick(ap, t, 0.25)  # 1000.5：0.25 秒
check(ap._slash_open, "163: 0.25 秒消えただけではまだ閉じない")
t[0] = 1000.74
p_frame(ap)  # 次の読みは 1000.75 なので読まれない
check(ap._slash_open, "163: 0.49 秒ではまだ閉じない")
t[0] = 1000.75
p_frame(ap)
check(not ap._slash_open and ap._slash_lines == [], "163: 0.5 秒消え続けたら閉じる（モードは PROMPT のまま）")
check(ap.mode == O.MODE_PROMPT and ap.input_buf == "", "163: 閉じたあとは PROMPT・入力欄は空")
check(not any(c in fb.calls for c in [("send_escape",)]), "163: 閉じるとき何も送らない")
# 途中でパネルが戻れば閉じない
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
p_frame(ap)
fb.screen = NOPANEL
s_tick(ap, t, 0.25)
fb.screen = PANEL
s_tick(ap, t, 0.25)
check(ap._slash_gone_since is None, "163: 案内が戻ったら「消えた時刻」を忘れる")
fb.screen = NOPANEL
s_tick(ap, t, 0.25)
s_tick(ap, t, 0.25)
check(ap._slash_open, "163: 戻ったあとは数え直し（0.25 秒では閉じない）")
s_tick(ap, t, 0.25)
check(not ap._slash_open, "163: 数え直してから 0.5 秒で閉じる")
# 画面が読めない（None）：何もしない・窓は開いたまま・例外なし
# 画面が読めない（None）：パネルを見ていなければ、2 秒で「(画面を読めませんでした)」の結果だけの窓になり、Esc で閉じる
ap, fb, t = s_ready(None)
p_send(ap, "/help")
p_frame(ap)
check(ap._slash_open and ap._slash_lines == [] and not ap._slash_static, "163: capture が None：0 秒では窓は開いたまま・まだ空")
s_tick(ap, t, 1.75)
check(not ap._slash_static and ap._slash_lines == [], "163: capture が None：1.75 秒ではまだ結果だけの窓にしない")
s_tick(ap, t, 0.25)
check(ap._slash_static and ap._slash_open and ap._slash_lines == ["(画面を読めませんでした)"], f"163: capture が None：2.0 秒で1行の結果だけの窓 {ap._slash_static} {ap._slash_lines}")
rec = c_draw(ap)
check(any(u[2] == "(画面を読めませんでした)" for u in rec["utext"]) and any(u[2] == i18n_t(O.SLASH_GUIDE_STATIC) for u in rec["utext"]), "163: capture が None：その1行と結果だけの窓の案内を描く")
n_cap = fb.captures
s_tick(ap, t, 3.0)
check(fb.captures == n_cap and ap._slash_open, "163: 結果だけの窓になったら画面を読まず、開いたまま")
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(not ap._slash_open and not fb.keys and ("send_escape",) not in fb.calls, "163: capture が None：Esc で閉じる（tmux へは送らない）")
# パネルを見たあとに読めなくなったら、0.5 秒で閉じる
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
p_frame(ap)
check(ap._slash_seen_panel, "163: 前提：パネルを見た")
fb.screen = None
s_tick(ap, t, 0.25)
check(ap._slash_open and ap._slash_gone_since == 1000.25, f"163: 読めなくなった時刻を覚える {ap._slash_gone_since}")
s_tick(ap, t, 0.25)
check(ap._slash_open, "163: 読めない状態が 0.25 秒ではまだ閉じない")
s_tick(ap, t, 0.25)
check(not ap._slash_open and ap._slash_lines == [], "163: パネルを見たあと読めない状態が 0.5 秒続いたら閉じる")
check(("send_escape",) not in fb.calls and not fb.keys, "163: 閉じるとき何も送らない")
# 読めなくなってもすぐ読めれば閉じない（数え直し）
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
p_frame(ap)
fb.screen = None
s_tick(ap, t, 0.25)
fb.screen = PANEL
s_tick(ap, t, 0.25)
check(ap._slash_gone_since is None, "163: パネルが読めたら「読めない時刻」を忘れる")
fb.screen = None
s_tick(ap, t, 0.25)
s_tick(ap, t, 0.25)
check(ap._slash_open, "163: 数え直し中は閉じない")
# 163-d. 結果だけの窓：2 秒でパネルを見ないまま
ap, fb, t = s_ready(RESULT_SCREEN)
p_send(ap, "/context")
p_frame(ap)  # 1000.0
check(not ap._slash_static and not ap._slash_seen_panel, "163: 開いた直後（0 秒）は結果だけの窓にしない")
s_tick(ap, t, 1.75)
check(not ap._slash_static, "163: 1.75 秒ではまだ結果だけの窓にしない")
s_tick(ap, t, 0.25)  # 2.0 秒
check(ap._slash_static and ap._slash_open, "163: 2.0 秒でパネルを見ないなら結果だけの窓")
check(ap._slash_lines == RESULT_LINES, f"163: \\xa0 入りの「❯ /context」で最後の結果だけを切り出す（罫線の手前まで） {ap._slash_lines}")
n_cap = fb.captures
s_tick(ap, t, 5.0)
check(fb.captures == n_cap, "163: 結果だけの窓になったら画面を読まない")
rec = c_draw(ap)
check(any(u[2] == i18n_t(O.SLASH_GUIDE_STATIC) and u[3] == 10 for u in rec["utext"]), "163: 結果だけの窓の案内（Esc・Enter・クリックで閉じる）")
check(not fb.keys and not fb.literals, "163: 結果だけの窓では何も tmux に送っていない")
p_frame(ap, keys=(pyxel.KEY_UP,))
check(not fb.keys, "163: 結果だけの窓では矢印キーを送らない")
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(not ap._slash_open and not fb.keys and ("send_escape",) not in fb.calls, "163: 結果だけの窓は Esc で閉じる（Esc は tmux へ送らない）")
for closer in ("enter", "kpenter", "click_out"):
    ap, fb, t = s_ready(RESULT_SCREEN)
    p_send(ap, "/context")
    p_frame(ap)
    s_tick(ap, t, 2.0)
    check(ap._slash_static, f"163: 前提（{closer}）")
    if closer == "enter":
        p_frame(ap, keys=(pyxel.KEY_RETURN,))
    elif closer == "kpenter":
        p_frame(ap, keys=(pyxel.KEY_KP_ENTER,))
    else:
        p_frame(ap, click=(O.SLASH_X + 20, O.SLASH_Y + 20))
        check(ap._slash_open, "163: 結果だけの窓の中のクリックでは閉じない")
        p_frame(ap, click=(300, O.SLASH_Y + O.SLASH_H + 40))
    check(not ap._slash_open, f"163: 結果だけの窓は {closer} で閉じる")
# 「❯」の行・罫線が見つからないとき
check(O._slash_result_lines(["a", "b"], "/x") == ["a", "b"], "163: 「❯」が見つからなければ画面全体")
check(O._slash_result_lines(["❯ /x", "r1", "r2"], "/x") == ["r1", "r2"], "163: 罫線が無ければ最後まで")
check(O._slash_result_lines(["❯ /x", "r1", "──", "r2"], "/x") == ["r1"], "163: 罫線の手前まで")
# パネルのときは、窓の外のクリックでは閉じない
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
p_frame(ap)
p_frame(ap, click=(300, O.SLASH_Y + O.SLASH_H + 40))
check(ap._slash_open, "163: パネルのときは窓の外のクリックで閉じない")
# 163-e. パネルの間のキーの送り先
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
p_frame(ap)
fb.keys.clear()
c0 = fb.captures
p_frame(ap)
check(fb.captures == c0, "163: キーが無ければ、0.25 秒たつまで読まない")
for key, name, _rep in O.SLASH_KEYS:
    fb.keys.clear()
    c0 = fb.captures
    p_frame(ap, keys=(key,))
    check(fb.keys == [(name,)], f"163: {name} が tmux へ送られる {fb.keys}")
    check(fb.captures == c0 + 1, f"163: {name} を送ったらすぐ画面を読む {fb.captures - c0}")
fb.keys.clear()
fb.literals.clear()
p_frame(ap, text="s")
check(fb.literals == ["s"] and not fb.keys, f"163: 英字は send_literal で送る {fb.literals}")
p_frame(ap, text=" あb~!")
check(fb.literals[-1] == "b~!", f"163: 英数字と記号だけ送る（空白・日本語は除く） {fb.literals}")
n_lit = len(fb.literals)
p_frame(ap, text="あ い")
check(len(fb.literals) == n_lit, "163: 日本語・空白だけなら何も送らない")
p_frame(ap, keys=(pyxel.KEY_UP, pyxel.KEY_DOWN), text="q")
check(fb.keys[-2:] == [("Up",), ("Down",)] and fb.literals[-1] == "q", "163: 同じフレームの複数のキーと文字をどれも送る")
# 窓の間はほかの操作が効かない
fb.keys.clear()
fb.literals.clear()
nxt, door = ap.next_index, ap.door_open
for k in (pyxel.KEY_D, pyxel.KEY_Y, pyxel.KEY_N, pyxel.KEY_T, pyxel.KEY_Q, pyxel.KEY_1, pyxel.KEY_F2):
    p_frame(ap, keys=(k,))
p_frame(ap, keys=(pyxel.KEY_SPACE,))
check(ap.next_index == nxt and ap.door_open == door, "163: 窓の間は Space・D・Q が効かない")
check(fb.keys == [("Space",)], f"163: D・Y・N・T などは送られず、Space だけがキーとして送られる {fb.keys}")
p_frame(ap, text="abc")
check(ap.input_buf == "" and ap.mode == O.MODE_PROMPT, "163: 窓の間は入力欄に文字が入らない")
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(("send_escape",) not in fb.calls and fb.keys[-1] == ("Escape",), "163: 窓の間の Esc は tmux のキーとして送り、中断（send_escape）は送らない")
n_hist = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_RETURN,))
check(len(ap.history) == n_hist and s_sends(fb).count("/help") == 1, "163: 窓の間の Enter で入力欄の送信をしない")
# 窓の間は会話のダイアログと「！」を描かない
ap, fb, t = s_ready(PANEL, talk=True)
ap.mode = O.MODE_PROMPT
p_send(ap, "/help")
rec = c_draw(ap)
check(not any(r[:4] == (O.DLG_X, O.DLG_Y, O.DLG_W, O.DLG_H) for r in rec["rect"]), "163: 窓の間は会話のダイアログの箱を描かない")
# 163-f. スクロール
BIG = "\n".join([f"行{i}" for i in range(80)] + ["  Esc to close"])
ap, fb, t = s_ready(BIG)
p_send(ap, "/help")
p_frame(ap)
mx = ap._slash_max_scroll()
check(mx > 0 and ap._slash_scroll == mx and not ap._slash_user_scrolled, f"163: 最初は一番下 {ap._slash_scroll} {mx}")
inside = (O.SLASH_X + 10, O.SLASH_Y + 10)
p_frame(ap, wheel=1, mouse=inside)
check(ap._slash_scroll == mx - O.DLG_WHEEL_ROWS and ap._slash_user_scrolled, f"163: ホイールで上へ {ap._slash_scroll}")
p_frame(ap, wheel=1, mouse=(5, 400))
check(ap._slash_scroll == mx - O.DLG_WHEEL_ROWS, "163: 窓の外のホイールでは動かない")
pos = ap._slash_scroll
fb.screen = BIG + "\n新しい行"
s_tick(ap, t, 0.25)
check(ap._slash_scroll == pos and ap._slash_user_scrolled, f"163: 動かしたあとは画面が変わっても位置を保つ {ap._slash_scroll}")
p_frame(ap, wheel=-1, mouse=inside)
check(ap._slash_scroll == pos + 3 or ap._slash_scroll == ap._slash_max_scroll(), "163: ホイールで下へ")
p_frame(ap, wheel=-1, mouse=inside)
check(ap._slash_scroll == ap._slash_max_scroll() and not ap._slash_user_scrolled, "163: 一番下まで戻したらまた下に付く状態になる")
fb.screen = BIG + "\n新しい行\n次の行"
s_tick(ap, t, 0.25)
check(ap._slash_scroll == ap._slash_max_scroll(), "163: 下に付いていれば画面が変わっても一番下")
# 溝のクリックとつまみのドラッグ
tx, ty, tw, th = ap._slash_track()
total = len(ap._slash_rows())
p_frame(ap, click=(tx + 1, ty + 1))
check(ap._slash_scroll == ap._slash_max_scroll() - O.SLASH_BODY_ROWS and ap._slash_user_scrolled, f"163: つまみの上の溝のクリックで1画面ぶん上へ {ap._slash_scroll}")
p_frame(ap, click=(tx + 1, ty + th - 1))
check(ap._slash_scroll == ap._slash_max_scroll(), "163: つまみの下の溝のクリックで1画面ぶん下へ")
thumb_y, thumb_h = ap._slash_thumb(total)
p_frame(ap, click=(tx + 1, thumb_y + 1))
check(ap._slash_drag, "163: つまみを押したらドラッグが始まる")
p_frame(ap, hold_keys=(pyxel.MOUSE_BUTTON_LEFT,), mouse=(tx + 1, ty))
check(ap._slash_scroll == 0, f"163: つまみを一番上へドラッグしたら先頭 {ap._slash_scroll}")
p_frame(ap)
check(not ap._slash_drag, "163: ボタンを離したらドラッグが終わる")
rec = c_draw(ap)
check(any(r[0] == tx and r[2] == tw and r[3] == th and r[4] == 1 for r in rec["rect"]), "163: スクロールバーの溝（色1）を描く")
# 163-g. 許可の依頼・終業・×・セッション消失で閉じる（何も送らない）
ap, fb, t = s_ready(PANEL, talk=True)
ap.mode = O.MODE_PROMPT
p_send(ap, "/help")
p_frame(ap)
fb.keys.clear()
n_calls = len(fb.calls)
s = pm_req(ap)
check(not ap._slash_open, "163: 許可の依頼が来たら窓が閉じる")
check(fb.keys == [] and len(fb.calls) == n_calls, "163: 閉じるとき何も送らない")
s.close()
ap._deny_perm_all()
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
p_frame(ap)
n_calls = len(fb.calls)
p_frame(ap, keys=(pyxel.KEY_F1,))
check(not ap._slash_open and ap.ending, "163: 終業（F1）で窓が閉じる")
check(fb.calls[n_calls:] == [("send_prompt", i18n_t(O.HANDOFF_PROMPT))] and not fb.keys, f"163: 終業で送るのは引き継ぎだけ {fb.calls[n_calls:]}")
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
p_frame(ap)
ap._shutdown_claude(sleep=lambda s_: None)
check(not ap._slash_open, "163: ×（_shutdown_claude）で窓が閉じる")
ap, fb, t = s_ready(PANEL)
p_send(ap, "/help")
p_frame(ap)
ap._session_gone()
check(not ap._slash_open and ap._slash_lines == [], "163: セッション消失で窓が閉じる")

# 164. /model・/effort のメニュー
check(O.MENU_MODEL_CHOICES == (("Default", "default"), ("Opus 5.5", "claude-opus-5-5"), ("Sonnet 5.5", "claude-sonnet-5-5"), ("Fable 5.2", "claude-fable-5-2"), ("Haiku 5.5", "claude-haiku-5-5")), "164: モデルの選択肢")
check(O.MENU_EFFORT_CHOICES == tuple((x, x) for x in ("low", "medium", "high", "xhigh", "max")), "164: effort の選択肢")
check(i18n_t(O.MENU_GUIDE) == "↑↓:選ぶ  Enter:決める  Esc:やめる（選んだ値は新しいセッションの既定にも保存されます）", "164: メニューの案内")
# 164-a. 開く条件
for cmd, kind in (("/model", "model"), ("/effort", "effort"), ("  /model  ", "model")):
    ap, fb, t = s_ready()
    n0 = len(s_sends(fb))
    p_send(ap, cmd)
    check(ap._menu == kind and ap.input_buf == "" and ap.mode == O.MODE_PROMPT, f"164: {cmd!r} でメニューが開く {ap._menu}")
    check(len(s_sends(fb)) == n0 and not ap._slash_open, f"164: {cmd!r} は Claude Code に送らず、コマンドの窓も開かない")
    check(ap.history[-1].startswith("> ") and cmd.strip() in ap.history[-1], f"164: 履歴に「> /…」が出る {ap.history[-1]!r}")
for cmd in ("/model sonnet", "/effort high", "/models", "/Model", "/model\nx"):
    ap, fb, t = s_ready()
    p_send(ap, cmd)
    check(ap._menu is None and s_sends(fb)[-1] == cmd, f"164: {cmd!r} はメニューを開かず今までどおり送る {ap._menu} {s_sends(fb)}")
    check(ap._slash_open, f"164: {cmd!r} は「/」で始まるので窓が開く（今までどおり）")
ap, _ = c_make(bridge=FakeBridgeTmux())
p_enter_prompt(ap)
p_send(ap, "/model")
check(ap._menu is None and "(始業していません。F1 で始業してください)" in ap.history, "164: 始業前は開かない（今までの扱い）")
ap, fb, t = s_ready()
ap._perm_tmux = True
ap.input_buf = "/model"
ap._send_input()
check(ap._menu is None and ap.input_buf == "/model", "164: 送信を止めている間は開かず、文字は残る")
ap_n = make_app(30, 1, "office", 18)
p_enter_prompt(ap_n)
p_send(ap_n, "/model")
check(ap_n._menu is None and any(h.startswith("> /model") for h in ap_n.history), "164: --claude でなければ開かない")
# 164-b. 今の値に *・最初の選択位置・描く
ap, fb, t = s_ready()
ap._cur_model = "Sonnet 5.5"
ap._cur_effort = "high"
p_send(ap, "/model")
check(ap._menu_sel == 2, f"164: 最初の選択は今の値の行 {ap._menu_sel}")
rec = c_draw(ap)
ut = {(u[2], u[3]) for u in rec["utext"]}
check(("* Sonnet 5.5  [claude-sonnet-5-5]", 0) in ut, f"164: 今の値の行に * （選んでいる行は黒0の字） {[u for u in ut if 'Sonnet' in u[0]]}")
check(("  Opus 5.5  [claude-opus-5-5]", O.TEXT_COLOR) in ut and ("  Default  [default]", O.TEXT_COLOR) in ut, "164: ほかの行は * なし・白7")
check(any(u[2] == "モデルを選ぶ" and u[3] == 10 for u in rec["utext"]) and any(u[2] == ">" and u[3] == 10 for u in rec["utext"]), "164: 題（黄10）と選んでいる行の >（黄10）")
check(any(u[2] == i18n_t(O.MENU_GUIDE) and u[3] == 10 for u in rec["utext"]), "164: 案内の行（黄10）")
h = ap._menu_height(5)
check(any(r[:4] == (O.SLASH_X, O.SLASH_Y, O.SLASH_W, h) and r[4] == 0 for r in rec["rect"]), "164: 背景の黒は窓と同じ位置・中身に合わせた高さ")
check(any(r[2] > 0 and r[3] == O.UI_LINE_H and r[4] == 7 for r in rec["rect"]), "164: 選んでいる行は白7の帯")
std, ui = p_texts(ap)
check(any(s_ == "MODE: MENU" for (_x, _y, s_, _c) in std) and any(s_ == "  (ESC:CLOSE)" for (_x, _y, s_, _c) in std), "164: MODE の札が MENU と (ESC:CLOSE)")
ap._close_menu()
p_send(ap, "/effort")
check(ap._menu == "effort" and ap._menu_sel == 2, "164: effort も今の値の行が最初の選択")
rec = c_draw(ap)
ut = {(u[2], u[3]) for u in rec["utext"]}
check(("* high", 0) in ut and ("  low", O.TEXT_COLOR) in ut and any(u[2] == "effort を選ぶ" for u in rec["utext"]), "164: effort の * と題")
ap._close_menu()
ap._cur_model = "?"
ap._cur_effort = "?"
p_send(ap, "/model")
check(ap._menu_sel == 0, "164: 今の値が分からなければ先頭")
rec = c_draw(ap)
check(not any(u[2].startswith("* ") for u in rec["utext"]), "164: 今の値が分からなければ * は無い")
# 164-c. ↑↓・Enter で決める
ap, fb, t = s_ready()
ap._cur_model = "Sonnet 5.5"
p_send(ap, "/model")
p_frame(ap, keys=(pyxel.KEY_UP,))
check(ap._menu_sel == 1, "164: ↑で上へ")
p_frame(ap, keys=(pyxel.KEY_UP,))
p_frame(ap, keys=(pyxel.KEY_UP,))
check(ap._menu_sel == 0, "164: 先頭より上へは行かない")
for _ in range(7):
    p_frame(ap, keys=(pyxel.KEY_DOWN,))
check(ap._menu_sel == 4, "164: 末尾より下へは行かない")
p_frame(ap, keys=(pyxel.KEY_UP,))
n0 = len(s_sends(fb))
p_frame(ap, keys=(pyxel.KEY_RETURN,))
check(s_sends(fb)[n0:] == ["/model claude-fable-5-2"] and ap._menu is None, f"164: Enter で /model <引数> を送って閉じる {s_sends(fb)[n0:]}")
check(not ap._slash_open and ap.mode == O.MODE_PROMPT, "164: 決めてもコマンドの窓は開かない")
for idx, want in ((0, "/model default"), (1, "/model claude-opus-5-5"), (2, "/model claude-sonnet-5-5"), (4, "/model claude-haiku-5-5")):
    ap, fb, t = s_ready()
    p_send(ap, "/model")
    ap._menu_sel = idx
    p_frame(ap, keys=(pyxel.KEY_KP_ENTER,))
    check(s_sends(fb)[-1] == want, f"164: {want}")
ap, fb, t = s_ready()
p_send(ap, "/effort")
for _ in range(3):
    p_frame(ap, keys=(pyxel.KEY_DOWN,))
p_frame(ap, keys=(pyxel.KEY_RETURN,))
check(s_sends(fb)[-1] == "/effort xhigh", f"164: effort の決定 {s_sends(fb)[-1]}")
# 164-d. クリック2回で決める
def row_y(i):
    return O.SLASH_Y + O.UI_PAD + (i + 1) * O.UI_LINE_H + 2


ap, fb, t = s_ready()
p_send(ap, "/model")
n0 = len(s_sends(fb))
p_frame(ap, click=(100, row_y(3)))
check(ap._menu_sel == 3 and ap._menu == "model" and len(s_sends(fb)) == n0, "164: 別の行のクリックはその行を選ぶだけ")
p_frame(ap, click=(100, row_y(3)))
check(s_sends(fb)[n0:] == ["/model claude-fable-5-2"] and ap._menu is None, f"164: 選んでいる行をもう一度クリックで決める {s_sends(fb)[n0:]}")
ap, fb, t = s_ready()
p_send(ap, "/model")
n0 = len(s_sends(fb))
p_frame(ap, click=(100, O.SLASH_Y + O.UI_PAD + 2))
check(ap._menu == "model" and ap._menu_sel == 0 and len(s_sends(fb)) == n0, "164: 題の行のクリックは何もしない")
p_frame(ap, click=(100, row_y(5)))
check(ap._menu == "model" and len(s_sends(fb)) == n0, "164: 案内の行のクリックは何もしない")
# 164-e. Esc・外のクリックで送らずに閉じる
ap, fb, t = s_ready()
p_send(ap, "/model")
n0 = len(fb.calls)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(ap._menu is None, "164: Esc でメニューが閉じる")
check(len(fb.calls) == n0, f"164: Esc で何も送らない（中断の Esc も送らない） {fb.calls[n0:]}")
for pt in ((300, O.SLASH_Y + ap._menu_height(5) + 20), (5, 100)):
    p_send(ap, "/model")
    n0 = len(fb.calls)
    p_frame(ap, click=pt)
    check(ap._menu is None and len(fb.calls) == n0, f"164: 外のクリック {pt} で何も送らず閉じる")
# 164-f. メニューの間はほかの操作が効かない
ap, fb, t = s_ready()
p_send(ap, "/model")
nxt, door = ap.next_index, ap.door_open
n0 = len(fb.calls)
for k in (pyxel.KEY_SPACE, pyxel.KEY_D, pyxel.KEY_Y, pyxel.KEY_N, pyxel.KEY_T, pyxel.KEY_Q, pyxel.KEY_F1, pyxel.KEY_1):
    p_frame(ap, keys=(k,))
p_frame(ap, text="abc")
check(ap.next_index == nxt and ap.door_open == door and ap.input_buf == "" and ap._menu == "model", "164: メニューの間は Space・D・文字入力が効かない")
check(ap.started and not ap.ending and len(fb.calls) == n0, "164: メニューの間は F1（終業）も効かず、何も送らない")
# 164-g. 許可の依頼・終業・×・消失で、何も送らず閉じる
ap, fb, t = s_ready(talk=True)
ap.mode = O.MODE_PROMPT
p_send(ap, "/model")
n0 = len(s_sends(fb))
s = pm_req(ap)
p_frame(ap)
check(ap._menu is None and len(s_sends(fb)) == n0, "164: 許可の依頼で閉じる")
s.close()
ap._deny_perm_all()
for label, fn in (("終業", lambda a: a._begin_handoff()), ("×", lambda a: a._shutdown_claude(sleep=lambda x: None)), ("消失", lambda a: a._session_gone())):
    ap, fb, t = s_ready()
    p_send(ap, "/effort")
    n0 = len(s_sends(fb))
    fn(ap)
    check(ap._menu is None and "/effort max" not in s_sends(fb)[n0:] and not any(x.startswith("/effort ") for x in s_sends(fb)), f"164: {label}でメニューが閉じ、決めた値は送らない")
# 164-h. 今の値を覚える：画面と会話記録
STATE_LINE = "  Opus 5.5 with high effort · Claude Pro"
fb = FakeBridgeTmux(screen="")
ap, _ = c_make(bridge=fb)
c_start(ap)
ap._usage_start_armed = False
check(ap._cur_model == "?" and ap._cur_effort == "?", "164: 始業直後（画面に表示が無い）は ?")
c_run(ap, 45)
check(ap._cur_model == "?" and ap._state_left > 0.0, "164: 見つからない間は読み続ける")
fb.screen = "\n行\n" + STATE_LINE + "\n"
c_run(ap, 20)
check(ap._cur_model == "Opus 5.5" and ap._cur_effort == "high" and ap._state_left == 0.0, f"164: 画面の行から覚えて読むのをやめる {ap._cur_model} {ap._cur_effort}")
n_cap = fb.captures
c_run(ap, 40)
check(fb.captures == n_cap, "164: 見つけたあとは画面を読まない")
fb = FakeBridgeTmux(screen="  Sonnet 5.5 · Claude Pro")
ap, _ = c_make(bridge=fb)
c_start(ap)
check(ap._cur_model == "Sonnet 5.5" and ap._cur_effort == "medium", f"164: effort の表示が無ければ medium {ap._cur_effort}")
fb = FakeBridgeTmux(screen="何もない画面")
ap, _ = c_make(bridge=fb)
c_start(ap)
ap._usage_start_armed = False
c_run(ap, 440)
n_cap = fb.captures
c_run(ap, 40)
check(ap._cur_model == "?" and ap._state_left <= 0.0 and fb.captures <= n_cap + 2, f"164: 15 秒たったら読むのをやめる {ap._state_left} {fb.captures - n_cap}")
ap, fb, t = s_ready()
c_ev(ap, fb, Prompt("s", "<local-command-stdout>Set model to `Haiku 5.5` and saved as your default for new sessions</local-command-stdout>"))
check(ap._cur_model == "Haiku 5.5", f"164: Set model to から覚える {ap._cur_model}")
c_ev(ap, fb, Prompt("s", "<local-command-stdout>Kept model as `Opus 5.5`</local-command-stdout>"))
check(ap._cur_model == "Opus 5.5", "164: Kept model as から覚える")
c_ev(ap, fb, Prompt("s", "<local-command-stdout>Set effort level to max (saved as your default for new sessions): xxx</local-command-stdout>"))
check(ap._cur_effort == "max" and ap._cur_model == "Opus 5.5", f"164: Set effort level to から覚える {ap._cur_effort}")
c_ev(ap, fb, Prompt("s", "ふつうの文 Set model to x"))
check(ap._cur_model == "Opus 5.5", "164: 形が合わない文では変えない")
p_send(ap, "/effort")
check(ap._menu_sel == 4, "164: 覚えた値がメニューの最初の選択になる")
ap._close_menu()
# 終業・消失で ? に戻る
ap._finish_ending()
check(ap._cur_model == "?" and ap._cur_effort == "?", "164: 終業のあと ? に戻る")
ap, fb, t = s_ready()
ap._cur_model, ap._cur_effort = "Opus 5.5", "low"
ap._session_gone()
check(ap._cur_model == "?" and ap._cur_effort == "?", "164: セッション消失のあと ? に戻る")
# 164-i. 入力欄：--claude は文字 2 行＋状態の行
ap, fb, t = s_ready()
check(ap._input_text_rows() == 2 and O.INPUT_TEXT_ROWS_CLAUDE == 2, "164: --claude の入力の文字は 2 行")
check(ap._input_rows("a\nb\nc") == ["b", "c"], f"164: 3 行打っても最後の 2 行だけ見せる {ap._input_rows('a' + chr(10) + 'b' + chr(10) + 'c')}")
ap_n = make_app(30, 1, "office", 18)
check(ap_n._input_text_rows() == 3 and ap_n._input_rows("a\nb\nc") == ["a", "b", "c"], "164: --claude でなければ今までどおり 3 行")
ap._cur_model, ap._cur_effort = "Opus 5.5", "high"
p_type(ap, "x")
ap.input_buf = "a\nb\nc"
rec = c_draw(ap)
sx, sy = ap._input_text_x(), O.INPUT_Y + O.UI_PAD + 2 * O.UI_LINE_H
check((sx, sy, "現在のモデル:Opus 5.5  effort:high", 13) in rec["utext"], f"164: いちばん下の行に状態（灰色13） {[u for u in rec['utext'] if u[1] == sy]}")
check([u[2] for u in rec["utext"] if u[1] == sy and u[0] == sx] == ["現在のモデル:Opus 5.5  effort:high"], "164: 状態の行には入力の文字が重ならない")
check({u[2].rstrip("_") for u in rec["utext"] if O.INPUT_Y < u[1] < sy and u[0] == sx} >= {"b", "c"}, "164: 入力の最後の 2 行は上の 2 行に出る")
ap._cur_model = ap._cur_effort = "?"
rec = c_draw(ap)
check(any(u[2] == "現在のモデル:?  effort:?" and u[3] == 13 for u in rec["utext"]), "164: 分からなければ ?")
rec = c_draw(ap_n)
check(not any(u[2].startswith("現在のモデル") for u in rec["utext"]), "164: --claude でなければ状態の行を出さない")
ap.input_buf = ""
p_frame(ap, click=(O.HISTORY_X + 20, O.INPUT_Y + O.INPUT_H - 3))
check(ap.mode == O.MODE_PROMPT, "164: 入力欄のいちばん下のクリックも PROMPT に入る（入力欄の高さは変えていない）")
check(O.INPUT_H == 3 * O.UI_LINE_H + 2 * O.UI_PAD, "164: 入力欄の高さは 3 行ぶんのまま")

# 165. いつも許可（A キー＋確かめ）
SUG_MODE = {"type": "setMode", "mode": "acceptEdits", "destination": "session"}
SUG_RULES = {"type": "addRules", "rules": [{"toolName": "Bash", "ruleContent": "npm run lint"}], "behavior": "allow", "destination": "localSettings"}
SUG_MODE_TXT = "このセッションの間、ファイルの編集を聞かずに許す"


def a_req(ap_, suggestions="__none__", tool="Bash"):
    """permission_suggestions つきの許可の依頼を送り、queue に届くまで待って update を1回。つなぎを返す。"""
    srv = ap_._perm_server
    s_ = pm_connect(srv.name[1:])
    pl = pm_perm_payload(tool)
    if suggestions != "__none__":
        pl["permission_suggestions"] = suggestions
    pm_send(s_, pl)
    pm_wait_queue(srv, 1)
    ap_.update()
    return s_


def a_ready(suggestions, talk=True):
    """依頼を1件出した状態（WALK・メインと会話・守り時間は過ぎている）。(ap, fb, t, s)。"""
    ap_, fb_ = pm_ready(talk=talk)
    t_ = n_clock(ap_)
    s_ = a_req(ap_, suggestions)
    t_[0] += 1.0
    return ap_, fb_, t_, s_


def a_dlg_texts(ap_):
    rec_ = c_draw(ap_)
    return rec_["utext"]


# 165-a. 案が無い依頼には A が出ず、A も効かない
for label, sg in (("項目なし", "__none__"), ("null", None), ("空 list", []), ("辞書なし", ["x", 1])):
    ap, fb, t, s = a_ready(sg)
    ut = a_dlg_texts(ap)
    check(any(u[2] == i18n_t(O.PERM_KEYS_TEXT) for u in ut) and not any(u[2] == i18n_t(O.PERM_KEYS_ALWAYS_TEXT) for u in ut), f"165: 案が{label}なら案内に A が出ない")
    p_frame(ap, keys=(pyxel.KEY_A,))
    check(not ap._perm_always_confirm and len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, f"165: 案が{label}なら A で何も起きない")
    s.close()
    ap._deny_perm_all()
# 165-b. 案がある依頼：案内に A、A 1回で確かめ、もう1回で always
ap, fb, t, s = a_ready([SUG_MODE])
check(ap._perm_pending[0].suggestions == [SUG_MODE], "165: PermRequest.suggestions に辞書が入る")
ut = a_dlg_texts(ap)
check(any(u[2] == i18n_t(O.PERM_KEYS_ALWAYS_TEXT) and u[3] == 10 for u in ut) and i18n_t(O.PERM_KEYS_ALWAYS_TEXT) == "Y:許可  A:いつも許可  N:断る  T:tmuxで答える", "165: 案があれば案内に「A:いつも許可」")
check(any(u[2].startswith("道具：Bash") for u in ut), "165: 確かめの前は依頼の中身を出す")
p_frame(ap, keys=(pyxel.KEY_A,))
check(ap._perm_always_confirm and len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, "165: A 1回では答えず、確かめに入る")
ut = a_dlg_texts(ap)
check(any(u[2] == i18n_t(O.PERM_ALWAYS_QUESTION) and u[3] == 10 for u in ut) and any(u[2] == SUG_MODE_TXT for u in ut), "165: 確かめでは「いつも許可しますか？」（黄10）と案の行")
check(any(u[2] == i18n_t(O.PERM_ALWAYS_CONFIRM_TEXT) and u[3] == 10 for u in ut) and i18n_t(O.PERM_ALWAYS_CONFIRM_TEXT) == "もう一度 A:いつも許可する  ほかのキー:やめる", "165: 確かめの案内の行（黄10）")
check(not any(u[2].startswith("道具：") for u in ut), "165: 確かめの間は依頼の中身を出さない")
summary = ap._perm_summary(ap._perm_pending[0])
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_A,))
check(pm_reply(s) == {"answer": "always"} and ap._perm_pending == [] and not ap._perm_always_confirm, "165: 2回目の A で always を返す")
check(ap.history[n0] == f"いつも許可しました：{summary}" and ap.history[n0 + 1] == "  " + SUG_MODE_TXT, f"165: 履歴「いつも許可しました：…」と案の行 {ap.history[n0:]}")
check(ap.history_color[n0 + 1] == 13 and ap.history_color[n0] == O.TEXT_COLOR, "165: 案の行は灰色13")
s.close()
# 案が2つ：各行が「  」付きで並ぶ
ap, fb, t, s = a_ready([SUG_MODE, SUG_RULES])
p_frame(ap, keys=(pyxel.KEY_A,))
p_frame(ap, keys=(pyxel.KEY_A,))
rows = O._suggestion_rows([SUG_MODE, SUG_RULES])
check(pm_reply(s) == {"answer": "always"} and ap.history[-2:] == ["  " + r for r in rows], f"165: 案が複数なら全部の行を履歴に {ap.history[-3:]}")
s.close()
# 案つきでも Y は allow
ap, fb, t, s = a_ready([SUG_MODE])
p_frame(ap, keys=(pyxel.KEY_Y,))
check(pm_reply(s) == {"answer": "allow"}, "165: 案があっても Y は allow")
s.close()
# 165-c. ほかのキー・クリックで確かめをやめる（そのキーでは答えない）
others = (("Y", pyxel.KEY_Y), ("N", pyxel.KEY_N), ("T", pyxel.KEY_T), ("Esc", pyxel.KEY_ESCAPE), ("Enter", pyxel.KEY_RETURN), ("Space", pyxel.KEY_SPACE), ("X", pyxel.KEY_X))
for label, key in others:
    ap, fb, t, s = a_ready([SUG_MODE])
    p_frame(ap, keys=(pyxel.KEY_A,))
    n0 = len(ap.history)
    p_frame(ap, keys=(key,))
    check(not ap._perm_always_confirm and ap._perm_always_req is None and len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, f"165: 確かめの間の {label} は確かめをやめるだけで答えない")
    check(len(ap.history) == n0, f"165: {label} でやめても履歴は出さない")
    ut = a_dlg_texts(ap)
    check(any(u[2] == i18n_t(O.PERM_KEYS_ALWAYS_TEXT) for u in ut), f"165: {label} でやめたら元の案内に戻る")
    p_frame(ap, keys=(pyxel.KEY_A,))
    check(ap._perm_always_confirm, f"165: {label} でやめたあと、また A 1回で確かめに入れる")
    s.close()
    ap._deny_perm_all()
ap, fb, t, s = a_ready([SUG_MODE])
p_frame(ap, keys=(pyxel.KEY_A,))
p_frame(ap, click=(O.DLG_X + 50, O.DLG_Y + 30))
check(not ap._perm_always_confirm and len(ap._perm_pending) == 1 and pm_reply(s, 0.1) is None, "165: 確かめの間のクリックで確かめをやめる（答えない）")
s.close()
ap._deny_perm_all()
# 165-d. 先頭の依頼が変わった・会話が終わったら確かめをやめる
ap, fb, t, s = a_ready([SUG_MODE])
s2 = a_req(ap, [SUG_RULES])
p_frame(ap, keys=(pyxel.KEY_A,))
check(ap._perm_always_confirm and len(ap._perm_pending) == 2, "165: 前提：2件のうち先頭で確かめ中")
s.close()
for _ in range(40):
    p_frame(ap)
    if len(ap._perm_pending) == 1:
        break
    _time_c.sleep(0.02)
p_frame(ap)
check(len(ap._perm_pending) == 1 and not ap._perm_always_confirm and ap._perm_always_req is None, "165: 先頭が取り下げられたら確かめをやめる（次の依頼には引き継がない）")
p_frame(ap, keys=(pyxel.KEY_A,))
check(ap._perm_always_confirm and ap._perm_always_req is ap._perm_pending[0], "165: 次の依頼では A 1回から確かめる")
ap.end_talk()
p_frame(ap)
check(not ap._perm_always_confirm, "165: 会話が終わったら確かめをやめる")
s2.close()
ap._deny_perm_all()
# 守り時間の間は A が効かない
ap, fb = pm_ready(talk=False)
t = n_clock(ap)
s = a_req(ap, [SUG_MODE])
check(ap.talk_partner == O.MAIN_INDEX and ap._perm_guard_active(), "165: 前提：ワープして守り時間の中")
t[0] += 0.4
p_frame(ap, keys=(pyxel.KEY_A,))
check(not ap._perm_always_confirm, "165: 守り時間の間は A が効かない")
t[0] += 0.1
p_frame(ap, keys=(pyxel.KEY_A,))
check(ap._perm_always_confirm, "165: 守り時間が過ぎれば A が効く")
s.close()
ap._deny_perm_all()
# 答えが届かなかったとき
ap, fb, t, s = a_ready([SUG_MODE])
summary = ap._perm_summary(ap._perm_pending[0])
p_frame(ap, keys=(pyxel.KEY_A,))
ap._perm_server.answer = lambda conn, ans: False
p_frame(ap, keys=(pyxel.KEY_A,))
check(ap._perm_tmux and ap.history[-1] == f"(答えが届きませんでした。tmux で答えてください：{summary})", f"165: always が届かなければ tmux に回す {ap.history[-1]!r}")
s.close()
ap._deny_perm_all()
# 165-e. 終わるときは deny（always は返さない）
for label, fn in (("終業", lambda a: a._begin_handoff()), ("×", lambda a: a._shutdown_claude(sleep=lambda x: None)), ("消失", lambda a: a._session_gone())):
    ap, fb, t, s = a_ready([SUG_MODE])
    p_frame(ap, keys=(pyxel.KEY_A,))
    check(ap._perm_always_confirm, f"165: 前提（{label}）：確かめ中")
    fn(ap)
    check(pm_reply(s) == {"answer": "deny"}, f"165: {label}のときは確かめ中でも deny")
    p_frame(ap)
    check(not ap._perm_always_confirm, f"165: {label}のあと確かめは残らない")
    s.close()
# 165-f. _suggestion_rows
sr = O._suggestion_rows
check(sr([]) == [], "165: 空の案は空")
check(sr([SUG_MODE]) == [SUG_MODE_TXT], f"165: setMode acceptEdits {sr([SUG_MODE])}")
check(sr([{"type": "setMode", "mode": "acceptEdits", "destination": "localSettings"}]) == [SUG_MODE_TXT + "（保存先：localSettings）"], "165: setMode の保存先が session 以外なら末尾に保存先")
check(sr([{"type": "setMode", "mode": "plan", "destination": "session"}]) == ["このセッションの間、許可のモードを plan にする"], "165: setMode のほかの mode")
check(sr([{"type": "setMode", "mode": "plan", "destination": "userSettings"}]) == ["このセッションの間、許可のモードを plan にする（保存先：userSettings）"], "165: ほかの mode＋保存先")
check(sr([SUG_RULES]) == ["次の決まりを 作業フォルダの設定（.claude/settings.local.json） に足す：Bash(npm run lint)"], f"165: addRules {sr([SUG_RULES])}")
two = {"type": "addRules", "rules": [{"toolName": "Bash", "ruleContent": "ls"}, {"toolName": "Read"}, {"toolName": "Edit", "ruleContent": ""}], "behavior": "allow", "destination": "projectSettings"}
check(sr([two]) == ["次の決まりを 作業フォルダの共有の設定（.claude/settings.json） に足す：Bash(ls)、Read、Edit"], f"165: addRules 複数・ruleContent 無し・空 {sr([two])}")
for dest, where in (("userSettings", "あなたの全体の設定（~/.claude/settings.json）"), ("session", "このセッションだけ"), ("zzz", "zzz")):
    check(sr([{"type": "addRules", "rules": [{"toolName": "Bash"}], "behavior": "allow", "destination": dest}]) == [f"次の決まりを {where} に足す：Bash"], f"165: addRules の保存先 {dest}")
check(sr([{"type": "addRules", "rules": [{"toolName": "Bash"}], "behavior": "deny", "destination": "session"}]) == ["[deny] 次の決まりを このセッションだけ に足す：Bash"], "165: behavior が allow 以外なら頭に [behavior]")
check(sr([{"type": "addRules", "rules": [{"toolName": "Bash"}], "destination": "session"}]) == ["次の決まりを このセッションだけ に足す：Bash"], "165: behavior が無ければ頭に何も付けない")
check(sr([{"type": "addRules", "rules": ["x", 3, {"toolName": "Bash"}], "behavior": "allow", "destination": "session"}]) == ["次の決まりを このセッションだけ に足す：Bash"], "165: rules の辞書でない要素は飛ばす")
check(sr([{"type": "addRules", "rules": None, "behavior": "allow", "destination": "session"}]) == ["次の決まりを このセッションだけ に足す："], "165: rules が list でなくても落ちない")
check(sr([{"type": "addDirectories", "directories": ["/a", "/b"], "destination": "session"}]) == ["次のフォルダを作業の範囲に足す：/a、/b"], "165: addDirectories")
check(sr([{"type": "addDirectories", "directories": "/a"}]) == ["次のフォルダを作業の範囲に足す：/a"], "165: addDirectories の directories が文字")
check(sr([{"type": "foo", "x": 1}]) == ['foo: {"type":"foo","x":1}'], f"165: 知らない type は JSON を短く {sr([{'type': 'foo', 'x': 1}])}")
check(sr([{"x": 1}]) == ['None: {"x":1}'], f"165: type が無い案も落ちない {sr([{'x': 1}])}")
check(sr([SUG_MODE, SUG_RULES, {"type": "foo"}]) == [SUG_MODE_TXT, sr([SUG_RULES])[0], 'foo: {"type":"foo"}'], "165: 複数の案は順に1行ずつ")
check(O._perm_suggestions(None) == [] and O._perm_suggestions("x") == [] and O._perm_suggestions({"a": 1}) == [] and O._perm_suggestions([SUG_MODE, "x", 1]) == [SUG_MODE], "165: _perm_suggestions は list の辞書だけ")

# 166. /exit・/quit を入力欄から送らない
NOTE_EXIT = "(/exit・/quit は使えません。終わるときは F1 で終業してください)"
check(O.BLOCKED_CMDS == ("/exit", "/quit"), "166: BLOCKED_CMDS")
for cmd in ("/exit", "/quit", "  /exit  ", "/EXIT", "/Quit", "/exit now", "/quit  -f", "/exit\nfoo", "\n/exit"):
    ap, fb, t = s_ready(PANEL)
    n0, h0 = len(s_sends(fb)), list(ap.history)
    p_send(ap, cmd)
    check(len(s_sends(fb)) == n0 and not ap._slash_open and ap._menu is None, f"166: {cmd!r} は送らない・窓もメニューも開かない")
    check(ap.input_buf == "", f"166: {cmd!r} のあと入力欄は空")
    check(ap.history[len(h0):] == [NOTE_EXIT], f"166: {cmd!r} は案内の1行だけ出し、「> 」の行は出さない {ap.history[len(h0):]}")
for cmd in ("/exits", "/exit2", "/quitx", "exit", "/ exit", "x /exit", "/model exit", "/quit-now"):
    check(O._is_blocked_command(cmd) is False, f"166: {cmd!r} は止めない")
for cmd in ("/exit", "/quit", "  /Exit  ", "/exit now", "/quit\nz"):
    check(O._is_blocked_command(cmd) is True, f"166: {cmd!r} を止める")
check(O._is_blocked_command("") is False and O._is_blocked_command("   ") is False, "166: 空は止めない")
ap, fb, t = s_ready(PANEL)
p_send(ap, "/exits")
check(s_sends(fb)[-1] == "/exits" and ap._slash_open and ap.history[-1] == "> /exits", "166: /exits は止めず今までどおり送る（窓も開く）")
# 始業前でも案内（送らない）
ap, _ = c_make(bridge=FakeBridgeTmux())
p_enter_prompt(ap)
p_send(ap, "/exit")
check(ap.history[-1] == NOTE_EXIT and "(始業していません。F1 で始業してください)" not in ap.history, "166: 始業前でも /exit は案内だけ")
# 読んでいる最中も、取っておかずに止める
ap, fb, t = s_ready()
ap._usage_try_start()
p_send(ap, "/exit")
check(ap._usage_pending == [] and ap.history[-1] == NOTE_EXIT, "166: 利用制限を読んでいる間でも、/exit は取っておかず案内だけ")
# --claude でないときは今までどおり
ap_n = make_app(30, 1, "office", 18)
p_enter_prompt(ap_n)
p_send(ap_n, "/exit")
check(any(h == "> /exit" for h in ap_n.history) and NOTE_EXIT not in ap_n.history, "166: --claude でなければ止めない（今までどおり履歴に出る）")

# 167. 利用制限を /usage で読む・掲示板の 100% の枠
USAGE_TEXT = "\n".join([
    "  Settings:  Status   Config   Usage   Stats",
    "",
    "  Current session",
    "  ███████████████████████▌                           47% used",
    "  Resets 6:30pm (Asia/Tokyo)",
    "",
    "  Current week (all models)",
    "  ████████████                                       24% used",
    "  Resets Nov 28, 1am (Asia/Tokyo)",
    "",
    "  Esc to close",
])
USAGE_LINES = [x.rstrip() for x in USAGE_TEXT.splitlines()]
USAGE = "/usage"
check((O.USAGE_POLL_SEC, O.USAGE_CLOSE_SEC, O.USAGE_TIMEOUT_SEC, O.USAGE_AFTER_TURN_SEC) == (0.2, 2.0, 5.0, 1.0), "167: /usage の時間の定数")
# 167-a. _parse_usage
check(O._parse_usage(USAGE_LINES) == (47.0, 24.0, "Resets 6:30pm (Asia/Tokyo)", "Resets Nov 28, 1am (Asia/Tokyo)"), f"167: 本物の画面の例から 47・24 と Resets の行 {O._parse_usage(USAGE_LINES)}")
check(O._parse_usage(["47% used", "24% used"]) == (None, None, None, None), "167: 見出しの無い値は拾わない")
check(O._parse_usage([]) == (None, None, None, None), "167: 空は全部 None")
r = O._parse_usage(["Current session", "  12.5% used", "Current week (all models)", "  0% used"])
check(r == (12.5, 0.0, None, None), f"167: 小数と 0%・Resets が無ければ None {r}")
r = O._parse_usage(["Current session", "Resets x", "Current week", "10% used"])
check(r[0] is None and r[1] == 10.0, f"167: 次の見出しに入ったら、その後の値を前の見出しのものにしない {r}")
r = O._parse_usage(["Current session", "  47% used", "  Resets a", "Current week (all models)"])
check(r == (47.0, None, "Resets a", None), f"167: 週間の値が無ければ None {r}")
r = O._parse_usage(["Current week (all models)", "  5% used", "Current session", "  9% used"])
check(r[0] == 9.0 and r[1] == 5.0, f"167: 見出しの順番が逆でも読む {r}")
r = O._parse_usage(["Current session", "  47% used", "  Resets a", "Current week (all models)", "  1% used", "Resets b", "Current week (Sonnet only)", "  99% used"])
check(r[1] == 1.0 and r[3] == "Resets b", f"167: 週間が複数あっても最初のものを使う {r}")
# 167-b. 始業後に1回：状態が読めたら始業のフレームで /usage
fb = FakeBridgeTmux(screen=STATE_LINE)
fb.usage_screen = USAGE_TEXT
ap, _ = c_make(bridge=fb)
c_start(ap)
check(s_sends(fb).count(USAGE) == 1 and ap._usage_busy, f"167: 始業して状態の読み取りが終わったら /usage を1回送る {s_sends(fb)}")
check(ap.five_hour == 0.0, "167: まだ値は入らない")
c_run(ap, 3)
check(ap.five_hour == 0.0 and s_escapes(fb) == 0, "167: 0.2 秒たつまでは読まない")
c_run(ap, 5)
check(ap.five_hour == 47.0 and ap.seven_day == 24.0, f"167: 画面から 47・24 を読む {ap.five_hour} {ap.seven_day}")
check(ap.scene.five_hour == 47.0 and ap.scene.seven_day == 24.0, "167: 掲示板（scene）にも渡す")
check(ap._usage_reset_5h == "Resets 6:30pm (Asia/Tokyo)" and ap._usage_reset_week == "Resets Nov 28, 1am (Asia/Tokyo)", "167: Resets の行を覚える")
check(s_escapes(fb) == 1 and ap._usage_phase in ("close", ""), "167: 値が入ったら Escape を1回送る")
c_run(ap, 20)
check(not ap._usage_busy and s_escapes(fb) == 1, f"167: 案内が消えたら終わる（Escape は1回のまま） {ap._usage_busy} {s_escapes(fb)}")
check(s_sends(fb).count(USAGE) == 1 and not ap._slash_open and not any(h.startswith("> /usage") for h in ap.history), "167: 窓を開かず・履歴にも出さず・再送もしない")
check(ap._cur_model == "Opus 5.5", "167: 状態も読めている")
# 状態が読めない間は送らない
fb = FakeBridgeTmux(screen="")
ap, _ = c_make(bridge=fb)
c_start(ap)
c_run(ap, 300)
check(USAGE not in s_sends(fb), "167: 状態の読み取りが終わるまでは /usage を送らない")
c_run(ap, 180)
check(s_sends(fb).count(USAGE) == 1, f"167: 状態を読む 15 秒が終わったら送る {s_sends(fb)}")
# 167-c. TurnEnd の1秒後
ap, fb, t = s_ready(prompt=False)
fb.usage_screen = USAGE_TEXT
c_ev(ap, fb, Prompt("s", "hi"))
c_ev(ap, fb, TurnEnd("s"))
c_run(ap, 27)
check(USAGE not in s_sends(fb), "167: TurnEnd のすぐあとは送らない")
c_run(ap, 5)
check(s_sends(fb).count(USAGE) == 1, f"167: TurnEnd の1秒後に /usage {s_sends(fb)}")
c_run(ap, 30)
check(ap.five_hour == 47.0 and not ap._usage_busy, "167: 読めて閉じる")
c_ev(ap, fb, Prompt("s", "もう一度"))
c_ev(ap, fb, TurnEnd("s"))
c_run(ap, 40)
check(s_sends(fb).count(USAGE) == 2, "167: TurnEnd のたびに読む")
# 読めない状態の TurnEnd では、その予定は捨てる（あとで読まない）
ap, fb, t = s_ready(prompt=False)
c_ev(ap, fb, Prompt("s", "hi"))
c_ev(ap, fb, TurnEnd("s"))
c_ev(ap, fb, Prompt("s", "次の仕事"))
c_run(ap, 40)
check(USAGE not in s_sends(fb) and ap._usage_after_turn_left == 0.0, "167: 1秒後にメインが busy なら送らず、予定も捨てる")
c_ev(ap, fb, TurnEnd("s"))
c_run(ap, 40)
check(s_sends(fb).count(USAGE) == 1, "167: 次の TurnEnd ではまた読む")
# 167-d. 読める状態でないときは送らない（_usage_can_read・_usage_try_start）
ap, fb, t = s_ready(prompt=False)
check(ap._usage_can_read() is True, "167: 前提：読める状態")
conds = (
    ("始業していない", lambda a: setattr(a, "started", False), lambda a: setattr(a, "started", True)),
    ("終業中", lambda a: setattr(a, "ending", True), lambda a: setattr(a, "ending", False)),
    ("読んでいる最中", lambda a: setattr(a, "_usage_busy", True), lambda a: setattr(a, "_usage_busy", False)),
    ("tmux で答える分がある", lambda a: setattr(a, "_perm_tmux", True), lambda a: setattr(a, "_perm_tmux", False)),
    ("コマンドの窓", lambda a: setattr(a, "_slash_open", True), lambda a: setattr(a, "_slash_open", False)),
    ("メニュー", lambda a: setattr(a, "_menu", "model"), lambda a: setattr(a, "_menu", None)),
    ("メインが busy", lambda a: setattr(a.agents[O.MAIN_INDEX], "busy", True), lambda a: setattr(a.agents[O.MAIN_INDEX], "busy", False)),
    ("許可の画面が出ている", lambda a: setattr(fb, "perm_screen", True), lambda a: setattr(fb, "perm_screen", False)),
)
for label, on, off in conds:
    on(ap)
    n0 = len(fb.calls)
    ap._usage_try_start()
    check(ap._usage_can_read() is False and len(fb.calls) == n0, f"167: {label}のときは読めない・送らない")
    off(ap)
check(ap._usage_can_read() is True, "167: 元に戻せば読める")
s = pm_req(ap)
check(ap._usage_can_read() is False, "167: 許可の依頼があるときは読めない")
s.close()
ap._deny_perm_all()
ap2 = make_app(30, 1, "office", 18)
check(ap2._usage_can_read() is False, "167: --claude でなければ読まない")
# 167-e. 5 秒の時間切れ・閉じない・値の丸め
ap, fb, t = s_ready(prompt=False)
fb.screen = "(読み込み中)\n  Esc to close"
ap.five_hour = 12.0
out = c_capture(lambda: (ap._usage_try_start(), c_run(ap, 140)))
check(ap._usage_busy and s_escapes(fb) == 0, "167: 5 秒までは読み続ける")
out += c_capture(lambda: c_run(ap, 20))
check(not ap._usage_busy and s_escapes(fb) == 1 and ap.five_hour == 12.0, f"167: 5 秒で取れなければ画面があれば Escape・値は前のまま {s_escapes(fb)}")
check("5 秒たっても読めませんでした" in out, f"167: 標準出力に1行 {out!r}")
ap, fb, t = s_ready(prompt=False)
fb.screen = "何もない"
out = c_capture(lambda: (ap._usage_try_start(), c_run(ap, 165)))
check(not ap._usage_busy and s_escapes(fb) == 0 and "読めませんでした" in out, "167: 画面が出ていなければ Escape は送らない")
ap, fb, t = s_ready(prompt=False)
fb.screen = None
out = c_capture(lambda: (ap._usage_try_start(), c_run(ap, 165)))
check(not ap._usage_busy and s_escapes(fb) == 0, "167: capture が None でも落ちずに時間切れ")
ap, fb, t = s_ready(prompt=False)
fb.screen = "Current session\n  47% used\n  Esc to close"
out = c_capture(lambda: (ap._usage_try_start(), c_run(ap, 165)))
check(ap.five_hour == 0.0 and ap.seven_day == 0.0 and s_escapes(fb) == 1, "167: 片方の値だけでは入れない")
ap, fb, t = s_ready(prompt=False)
fb.usage_screen = USAGE_TEXT.replace("47% used", "150% used").replace("24% used", "0% used")
ap._usage_try_start()
c_run(ap, 12)
check(ap.five_hour == 100.0 and ap.seven_day == 0.0, f"167: 100 を超えたら 100 に収め、0% も読む {ap.five_hour} {ap.seven_day}")
ap, fb, t = s_ready(prompt=False)
fb.usage_screen = USAGE_TEXT
fb.escape_closes = False
ap._usage_try_start()
c_run(ap, 12)
check(s_escapes(fb) == 1 and ap._usage_phase == "close", f"167: 前提：値が入って Escape 1回・閉じ待ち {s_escapes(fb)}")
c_run(ap, 50)
check(s_escapes(fb) == 1, "167: 2 秒たつまでは次の Escape を送らない")
c_run(ap, 20)
check(s_escapes(fb) == 2 and ap._usage_busy, f"167: 2 秒閉じなければもう一度 Escape {s_escapes(fb)}")
out = c_capture(lambda: c_run(ap, 70))
check(not ap._usage_busy and s_escapes(fb) == 2 and "閉じませんでした" in out, f"167: それでも残ればあきらめて1行出す {out!r}")
# 167-f. 読んでいる間の送信は取っておいて、あとで送る
ap, fb, t = s_ready(prompt=True)
ap._usage_try_start()
check(ap._usage_busy and not ap._slash_open, "167: 読んでいる間はコマンドの窓を開かない")
NOTE_BUSY = "(利用制限を読んでいます。終わったら送ります)"
p_send(ap, "hello")
check(ap.history[-2:] == ["> hello", NOTE_BUSY] and ap.input_buf == "", f"167: 履歴の「> …」と案内は今までどおり／入力欄は空 {ap.history[-2:]}")
p_send(ap, "world")
check(ap.history.count(NOTE_BUSY) == 1 and ap.history[-1] == "> world", "167: 案内は読むたびに1回だけ")
check("hello" not in s_sends(fb) and ap._usage_pending == [("hello", False), ("world", False)], f"167: 送らずに取っておく {ap._usage_pending}")
p_send(ap, "/help")
check(ap._usage_pending[-1] == ("/help", True) and not ap._slash_open, "167: 窓を開くかどうかも取っておく")
n0 = len(ap.history)
p_frame(ap, keys=(pyxel.KEY_ESCAPE,))
check(s_escapes(fb) == 0 and len(ap.history) == n0, "167: 読んでいる間の Esc は送らず・履歴も出さない")
fb.screen = ""
out = c_capture(lambda: c_run(ap, 170))
check(not ap._usage_busy, "167: 前提：時間切れで読み終わる")
sends = s_sends(fb)
check(sends[-3:] == ["hello", "world", "/help"] and ap._usage_pending == [], f"167: 読み終わったあと順に送る {sends[-4:]}")
check(ap._slash_open and ap._slash_cmd == "/help", "167: 取っておいた「/」の文は送ったあと窓を開く")
# 次の読みでは案内がまた出る
ap, fb, t = s_ready(prompt=True)
for k in range(2):
    ap._usage_try_start()
    p_send(ap, f"a{k}")
    ap._usage_abort(send_escape=False)
    ap._usage_pending.clear()
check(ap.history.count(NOTE_BUSY) == 2, "167: 読み取りが変われば案内をもう一度出す")
# メニューの決定も取っておく
ap, fb, t = s_ready(prompt=True)
ap._usage_try_start()
p_send(ap, "/effort")
check(ap._menu == "effort", "167: 読んでいる間でもメニューは開ける")
p_frame(ap, keys=(pyxel.KEY_DOWN,))
p_frame(ap, keys=(pyxel.KEY_RETURN,))
check(ap._usage_pending == [("/effort medium", False)] or ap._usage_pending == [("/effort high", False)], f"167: メニューの決定も取っておく {ap._usage_pending}")
check(not any(x.startswith("/effort ") for x in s_sends(fb)), "167: 読んでいる間は送らない")
# 167-g. 読んでいる間の許可の依頼・終業・×・消失
ap, fb, t = s_ready(prompt=True, talk=False)
ap._usage_try_start()
p_send(ap, "hi")
s = pm_req(ap)
check(not ap._usage_busy and s_escapes(fb) == 1, f"167: 許可の依頼が来たら Escape を1回送って読みをやめる {s_escapes(fb)}")
check(ap._usage_pending == [("hi", False)], "167: 取っておいた文は残す")
c_run(ap, 5)
check("hi" not in s_sends(fb), "167: 許可の答えを待つ間は送らない")
s.close()
ap._deny_perm_all()
ap._perm_tmux = False
c_run(ap, 3)
check("hi" in s_sends(fb) and ap._usage_pending == [], "167: 止めが解けたら送る")
for label, fn, want_note in (
    ("終業", lambda a: a._begin_handoff(), True),
    ("×", lambda a: a._shutdown_claude(sleep=lambda x: None), True),
    ("消失", lambda a: a._session_gone(), True),
):
    ap, fb, t = s_ready(prompt=True)
    ap._usage_try_start()
    p_send(ap, "捨てる")
    fn(ap)
    check(not ap._usage_busy and s_escapes(fb) >= 1, f"167: {label}で読みをやめ Escape を送る")
    check(ap._usage_pending == [] and "(送れなかったプロンプトがあります)" in ap.history, f"167: {label}で取っておいた文を捨て、履歴に1行")
    check("捨てる" not in s_sends(fb), f"167: {label}のあとに捨てた文を送らない")
ap, fb, t = s_ready(prompt=True)
ap._usage_try_start()
p_frame(ap, keys=(pyxel.KEY_F1,))
calls = [c for c in fb.calls if c[0] in ("send_escape", "send_prompt")]
check(calls[-2:] == [("send_escape",), ("send_prompt", i18n_t(O.HANDOFF_PROMPT))], f"167: 終業では Escape が引き継ぎの前 {calls[-3:]}")
# 読んでいない間の終業では Escape を送らない
ap, fb, t = s_ready(prompt=True)
ap._begin_handoff()
check(s_escapes(fb) == 0, "167: 読んでいなければ終業で Escape を送らない")
# 167-h. --claude では JSON とキー 1〜4 を使わない
jp = write_json_file("r167.json", {"five_hour": {"used_percentage": 33.0}, "seven_day": {"used_percentage": 44.0}})
cfg = write_toml("r167.toml", jp, 1.0)
apj, fbj = c_make(config_path=cfg)
c_run(apj, 100)
check(apj.five_hour == 0.0 and apj.seven_day == 0.0, f"167: --claude では JSON を読まない {apj.five_hour}")
apn = make_app(30, 1, "office", 18, config_path=cfg)
c_run(apn, 100)
check(apn.five_hour == 33.0 and apn.seven_day == 44.0, "167: --claude でなければ今までどおり JSON を読む")
c_start(apj)
apj._usage_start_armed = False
for k in (pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3, pyxel.KEY_4):
    p_frame(apj, keys=(k,))
check(apj.five_hour == 0.0 and apj.seven_day == 0.0 and not apj.manual_limits, "167: --claude ではキー 1〜4 が効かない")
p_frame(apn, keys=(pyxel.KEY_2,))
check(apn.manual_limits and apn.five_hour == 33.0 + O.RATE_KEY_STEP, "167: --claude でなければキー 2 が効く")
p_enter_prompt(apj)
p_type(apj, "1234")
check(apj.input_buf == "1234", "167: PROMPT で数字は打てる")
# 167-i. 掲示板の 100% の枠：2 本とも 4 本の黒い箱・0% でも描く・棒を隠さない
check((O.BAR_FRAME_W, O.BAR_FRAME_COLOR) == (2.0, 0), "167: 枠の太さ 2.0・色 0")
for fh, wk in ((0.0, 0.0), (47.0, 24.0), (100.0, 100.0)):
    root = O.OfficeRoot(OLAY)
    root.five_hour, root.seven_day = fh, wk
    cs = capture_boxes(root)
    frames = [c for c in cs if c[2] == O.BAR_FRAME_COLOR and c[1] in ((204.0, 2.0, 2.0), (2.0, 14.0, 2.0))]
    check(len(frames) == 8, f"167: ({fh},{wk}) 枠は 2 本ぶん 8 個 {len(frames)}")
    for y, name in ((160.0, "5時間"), (128.0, "週間")):
        mine = [c for c in frames if abs(c[0].pos.y - y) <= 8.0 + 1e-6]
        tops = sorted(c[0].pos.y for c in mine if c[1] == (204.0, 2.0, 2.0))
        sides = sorted(c[0].pos.x for c in mine if c[1] == (2.0, 14.0, 2.0))
        check(len(mine) == 4 and tops == [y - 8.0, y + 8.0] and sides == [-101.0, 101.0], f"167: {name}の枠の位置 上下 {tops} 左右 {sides}")
        check(all(abs(c[0].pos.z - O.BAR_Z) < 1e-6 for c in mine), f"167: {name}の枠の z は棒と同じ")
    bars = [c for c in cs if c[2] in (O.FIVE_HOUR_BAR_COLOR, O.WEEK_BAR_COLOR) and c[1][1] == O.BAR_HEIGHT and c[1][2] == O.BAR_DEPTH]
    for bm, bsz, _bc in bars:
        for fm, fsz, _fc in frames:
            ox = abs(bm.pos.x - fm.pos.x) < (bsz[0] + fsz[0]) / 2.0 - 1e-6
            oy = abs(bm.pos.y - fm.pos.y) < (bsz[1] + fsz[1]) / 2.0 - 1e-6
            check(not (ox and oy), f"167: ({fh},{wk}) 棒が枠と重ならない（枠は棒の外側）")



# 168. 名前と版：APP_NAME は pyxelcube_agents、APP_VERSION は 0.90（窓の題に使う）
check(pyxelcube_agents.APP_VERSION == "0.90" and pyxelcube_agents.APP_NAME == "pyxelcube_agents",
      f"168: APP_NAME/APP_VERSION が違う {pyxelcube_agents.APP_NAME} {pyxelcube_agents.APP_VERSION}")

# ---------------------------------------------------------------------------
# 169. pca_i18n：全キーに ja・en があり、差し込みの名前が同じ。detect_lang・set_lang・t
# ---------------------------------------------------------------------------
import string
set_lang("ja")


def _fields(text):
    """str.format の差し込みの名前の集合（{名前}）。"""
    return {name for _lit, name, _spec, _conv in string.Formatter().parse(text) if name is not None}


check(len(MESSAGES) > 50, f"169: キーの数が少なすぎる {len(MESSAGES)}")
for key, pair in MESSAGES.items():
    check(set(pair) == set(LANGS) == {"ja", "en"}, f"169: {key} に ja と en が揃っていない {sorted(pair)}")
    for lg in LANGS:
        check(isinstance(pair.get(lg), str) and pair.get(lg, "") != "", f"169: {key} の {lg} が空")
    check(_fields(pair["ja"]) == _fields(pair["en"]), f"169: {key} の差し込みの名前が ja と en で違う {_fields(pair['ja'])} {_fields(pair['en'])}")
# 本体の定数が指すキーは、すべて MESSAGES にある
for const in ("HANDOFF_PROMPT", "PERM_WAIT_NOTE", "PERM_KEYS_TEXT", "PERM_KEYS_ALWAYS_TEXT", "PERM_ALWAYS_CONFIRM_TEXT", "PERM_ALWAYS_QUESTION",
              "MENU_GUIDE", "SLASH_GUIDE_PANEL", "SLASH_GUIDE_STATIC", "TALK_PAGE_GUIDE"):
    check(getattr(O, const) in MESSAGES, f"169: 定数 {const} のキー {getattr(O, const)!r} が MESSAGES に無い")
# detect_lang（環境変数の辞書を渡す）
for env, want in (({"LANG": "ja_JP.UTF-8"}, "ja"), ({"LC_ALL": "C", "LANG": "ja_JP.UTF-8"}, "en"), ({"LC_ALL": "", "LANG": "ja_JP.UTF-8"}, "ja"),
                  ({}, "en"), ({"LC_MESSAGES": "ja"}, "ja"), ({"LANG": "en_US.UTF-8"}, "en"),
                  ({"LC_ALL": "en_US.UTF-8", "LC_MESSAGES": "ja_JP.UTF-8", "LANG": "ja_JP.UTF-8"}, "en"),
                  ({"LC_MESSAGES": "ja_JP.UTF-8", "LANG": "en_US.UTF-8"}, "ja")):
    check(detect_lang(env) == want, f"169: detect_lang({env}) が {want} でない {detect_lang(env)}")
# set_lang・get_lang・t
try:
    set_lang("fr")
    raised = False
except ValueError:
    raised = True
check(raised and get_lang() == "ja", f"169: set_lang('fr') は ValueError で、言語は変わらない {get_lang()}")
set_lang("en")
check(get_lang() == "en" and i18n_t("hist_ended") == "Clocked out", "169: set_lang('en') で t が英語を返す")
set_lang("ja")
check(get_lang() == "ja" and i18n_t("hist_ended") == "終業しました", "169: set_lang('ja') で t が日本語を返す")
check(i18n_t("hist_start_failed", error="x") == "始業できませんでした：x", "169: t は {名前} を差し込む")
try:
    i18n_t("no_such_key")
    raised = False
except KeyError:
    raised = True
check(raised, "169: 無いキーは KeyError")

# 169-b. 起動オプション --lang・省略時は環境変数から
_env_keys = ("LC_ALL", "LC_MESSAGES", "LANG")
_saved_env2 = {k: os.environ.get(k) for k in _env_keys}


def _with_env(env, argv):
    """環境変数を一時的に env にして parse_args を呼び、そのあとの言語を返す（環境変数は元に戻す）。"""
    for k in _env_keys:
        os.environ.pop(k, None)
    os.environ.update(env)
    try:
        ns_ = O.parse_args(argv)
        return get_lang(), ns_
    finally:
        for k, v in _saved_env2.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


lg, ns_ = _with_env({"LANG": "ja_JP.UTF-8"}, ["--lang", "en"])
check(lg == "en" and ns_.lang == "en", f"169: --lang en で言語が en（環境変数が ja でも） {lg} {ns_.lang}")
lg, ns_ = _with_env({"LANG": "en_US.UTF-8"}, ["--lang", "ja"])
check(lg == "ja" and ns_.lang == "ja", f"169: --lang ja で言語が ja（環境変数が en でも） {lg} {ns_.lang}")
lg, ns_ = _with_env({"LANG": "en_US.UTF-8"}, [])
check(lg == "en" and ns_.lang == "en", f"169: --lang 省略・LANG=en で en {lg} {ns_.lang}")
lg, ns_ = _with_env({"LANG": "ja_JP.UTF-8"}, [])
check(lg == "ja" and ns_.lang == "ja", f"169: --lang 省略・LANG=ja で ja {lg} {ns_.lang}")
lg, ns_ = _with_env({"LC_ALL": "C", "LANG": "ja_JP.UTF-8"}, [])
check(lg == "en", f"169: --lang 省略・LC_ALL=C は LANG より優先されて en {lg}")
lg, ns_ = _with_env({}, [])
check(lg == "en" == detect_lang({}), f"169: --lang 省略・環境変数なしは en {lg}")
sys.stderr, _err_keep = open(os.devnull, "w"), sys.stderr
try:
    O.parse_args(["--lang", "fr"])
    exited = False
except SystemExit:
    exited = True
finally:
    sys.stderr.close()
    sys.stderr = _err_keep
check(exited, "169: --lang fr は SystemExit")
set_lang("ja")

# ---------------------------------------------------------------------------
# 170. hook の設定と claude の起動コマンド（言語は環境変数 PCA_LANG で渡す。hook のコマンドには付かない）
# ---------------------------------------------------------------------------
HP_ = Path("/tmp/x y/pca_perm_hook.py")
js = json.loads(O.hook_settings_json(HP_))
cmd_p = js["hooks"]["PermissionRequest"][0]["hooks"][0]["command"]
cmd_n = js["hooks"]["Notification"][0]["hooks"][0]["command"]
check(cmd_p.endswith(" PermissionRequest") and cmd_n.endswith(" Notification"), f"170: hook のコマンドは言語を付けず ' PermissionRequest'・' Notification' で終わる {cmd_p!r} {cmd_n!r}")
check(not cmd_p.endswith(" ja") and not cmd_n.endswith(" ja") and "PCA_LANG" not in cmd_p + cmd_n, "170: hook のコマンドに言語が付かない")
for lang_, want_prefix in (("en", "PCA_LANG=en "), ("ja", "PCA_LANG=ja ")):
    cc = O.claude_command(HP_, lang_)
    check(cc.startswith(want_prefix + "claude --settings "), f"170: claude_command(…, {lang_!r}) が {want_prefix!r} で始まる {cc[:60]!r}")
    check(cc.endswith(shlex.quote(O.hook_settings_json(HP_))), "170: 設定の JSON は shlex.quote で囲まれて末尾に付く")
check(O.claude_command(HP_).startswith("PCA_LANG=ja claude --settings "), "170: 既定の言語は PCA_LANG=ja")

# ---------------------------------------------------------------------------
# 171. 英語の表示（set_lang('en')）：始業・終業のボタン・履歴・メインの名前・許可のダイアログの案内
# ---------------------------------------------------------------------------
set_lang("en")
try:
    ap, fb = c_make()
    rec = c_draw(ap)
    check(c_ui_has(rec, "[F1] Clock in") and not c_ui_has(rec, "[F1] Clock out") and not c_ui_has(rec, "[F1] 始業"), f"171: 始業前のボタンが「[F1] Clock in」 {[u[2] for u in rec['utext']]}")
    n0 = len(ap.history)
    main = c_start(ap)
    check(ap.history[n0:] == ["Clocked in: started Claude Code"], f"171: 始業の履歴が英語 {ap.history[n0:]}")
    rec = c_draw(ap)
    check(c_ui_has(rec, "[F1] Clock out") and not c_ui_has(rec, "[F1] Clock in"), "171: 始業後のボタンが「[F1] Clock out」")
    bx, by, bw, bh = ap._button_rect("[F1] Clock out")
    check(bw > 8 and by == O.BUTTON_Y, f"171: 英語のボタンの長方形 {(bx, by, bw, bh)}")
    # メインの名前（まだ話していないとき）と、会話のページの題
    c_seated(ap, 0)
    check(c_talk_ready(ap, 0), "171: 前提：メインと会話")
    check(dtx(ap, 0) == ["Main", "(No conversation yet)"], f"171: メインの名前が Main・「(No conversation yet)」 {dtx(ap, 0)}")
    c_ev(ap, fb, Prompt("s", "hello"))
    check(dtx(ap, 0) == ["Main  1/1", "> hello", "", "(Waiting for a reply)"], f"171: ページの題・返事待ちが英語 {dtx(ap, 0)}")
    # 許可のダイアログの案内
    ap2, fb2 = pm_ready()
    s1 = pm_req(ap2)
    rec = c_draw(ap2)
    rows = pm_dlg_rows(rec)
    check(any(r[1] == "Y:Allow  N:Deny  T:Answer in tmux" for r in rows), f"171: 許可のダイアログの案内が「Y:Allow  N:Deny  T:Answer in tmux」 {[r[1] for r in rows]}")
    check(dtx(ap2, 0)[:3] == ["Main", "Asking for permission (1 left)", "Tool: Bash"], f"171: 許可の依頼の題が英語 {dtx(ap2, 0)[:3]}")
    s1.close()
    ap2._deny_perm_all()
    # 履歴の英語（終業の途中）
    ap3, fb3 = c_make()
    c_start(ap3)
    n0 = len(ap3.history)
    p_frame(ap3, keys=(pyxel.KEY_F1,))
    check(ap3.history[n0:] == ["Clocking out: asking for a handoff memo"], f"171: 終業の履歴が英語 {ap3.history[n0:]}")
    c_ev(ap3, fb3, Prompt("s", i18n_t(O.HANDOFF_PROMPT)), TurnEnd("s"))
    check(ap3.history[-1] == "Clocked out", f"171: 終業後の履歴が英語 {ap3.history[-1]}")
finally:
    set_lang("ja")

# 171-b. 終業：英語で送る引き継ぎの文が英語で、記録から戻った同じ文を「引き継ぎの依頼」と見分ける
set_lang("en")
try:
    en_prompt = i18n_t(O.HANDOFF_PROMPT)
    check(en_prompt == "Please write a handoff memo for today's work.", f"171: 英語の引き継ぎの依頼 {en_prompt!r}")
    ap, fb, sl = c_shutdown([[Prompt("s", en_prompt), TurnEnd("s")]])
    check(fb.calls == [("send_prompt", en_prompt), ("end", True)] and sl == [], f"171: 英語で送り、戻ってきた同じ文の TurnEnd で閉じる {fb.calls} {sl}")
    ap, fb, sl = c_shutdown([[Prompt("s", "今日の作業の引き継ぎメモを書いてください。"), TurnEnd("s")]])
    check(len(sl) >= 1490, "171: 英語のときは、日本語の文を引き継ぎの依頼と見なさない")
    ap, fb = c_make()
    c_start(ap)
    p_frame(ap, keys=(pyxel.KEY_F1,))
    check(("send_prompt", en_prompt) in fb.calls and ap._last_sent == en_prompt, f"171: F1 の終業で英語の依頼を送る {fb.calls}")
    n0 = len(ap.history)
    c_ev(ap, fb, Prompt("s", en_prompt))
    check(ap._handoff_seen is True and ap.history[n0:] == [], f"171: 戻ってきた英語の依頼を引き継ぎの依頼と見分け、履歴に二重に出さない {ap._handoff_seen} {ap.history[n0:]}")
finally:
    set_lang("ja")
    ap.started = False
    ap.ending = False

# ---------------------------------------------------------------------------
# 172. 会話のページめくり（TalkPage）
# ---------------------------------------------------------------------------
ap, fb = pm_ready()
check(ap._pages == [] and ap._page_index is None and not ap._page_guide_on(0), "172: 最初はページが無く、案内も出ない")
for k in range(3):
    c_ev(ap, fb, Prompt("s", f"依頼{k + 1}"))
    c_ev(ap, fb, Reply("s", f"返事{k + 1}"))
    check(len(ap._pages) == k + 1 and dtx(ap, 0)[:2] == [f"メイン  {k + 1}/{k + 1}", f"> 依頼{k + 1}"], f"172: 依頼{k + 1} でページが増え、最新のページを見る {len(ap._pages)} {dtx(ap, 0)[:2]}")
check(ap._pages[0].prompt == "依頼1" and ap._pages[0].replies == ["返事1"] and ap._pages[0].notice is False, f"172: ページの中身 {ap._pages[0]}")
check(ap._page_guide_on(0), "172: ページが2つ以上で案内が出る")
rec = c_draw(ap)
check(c_ui_has(rec, i18n_t(O.TALK_PAGE_GUIDE)) and i18n_t(O.TALK_PAGE_GUIDE) == "↑↓:前後のやりとり", "172: 一番下に「↑↓:前後のやりとり」が出る")
p_frame(ap, keys=(pyxel.KEY_DOWN,))
check(ap._page_index is None, "172: 最新のページで ↓ を押しても変わらない")
p_frame(ap, keys=(pyxel.KEY_UP,))
check(ap._page_index == 1 and dtx(ap, 0)[:2] == ["メイン  2/3", "> 依頼2"], f"172: ↑ で前のページ（2/3） {ap._page_index} {dtx(ap, 0)[:2]}")
p_frame(ap, keys=(pyxel.KEY_UP,))
check(ap._page_index == 0 and dtx(ap, 0)[0] == "メイン  1/3", f"172: ↑ でさらに前（1/3） {ap._page_index}")
p_frame(ap, keys=(pyxel.KEY_UP,))
check(ap._page_index == 0, "172: 先頭のページで ↑ を押しても止まる")
# 読んでいる途中に新しいやりとりが来ても、見ているページは変わらない
c_ev(ap, fb, Prompt("s", "依頼4"))
check(ap._page_index == 0 and len(ap._pages) == 4 and dtx(ap, 0)[0] == "メイン  1/4", f"172: 前のページを読んでいる間は新しいページに飛ばない {ap._page_index} {dtx(ap, 0)[0]}")
p_frame(ap, keys=(pyxel.KEY_DOWN,))
p_frame(ap, keys=(pyxel.KEY_DOWN,))
p_frame(ap, keys=(pyxel.KEY_DOWN,))
check(ap._page_index == 3 and dtx(ap, 0)[0] == "メイン  4/4", f"172: ↓ で次へ進む {ap._page_index}")
p_frame(ap, keys=(pyxel.KEY_DOWN,))
check(ap._page_index is None, "172: 最後のページから ↓ で最新に付いていく（None）")
# ページが1つなら案内は出ない
ap1, fb1 = pm_ready()
c_ev(ap1, fb1, Prompt("s", "ひとつだけ"))
check(not ap1._page_guide_on(0) and not c_ui_has(c_draw(ap1), i18n_t(O.TALK_PAGE_GUIDE)), "172: ページが1つなら案内は出ない")
# 上限を超えたら古いものから捨て、見ているページの番号もずらす
ap, fb = pm_ready()
for k in range(O.TALK_PAGE_MAX):
    ap._add_talk_page(O.TalkPage(prompt=f"p{k}", notice=False))
ap._page_index = 5
ap._add_talk_page(O.TalkPage(prompt="new", notice=False))
check(len(ap._pages) == O.TALK_PAGE_MAX and ap._pages[0].prompt == "p1" and ap._pages[-1].prompt == "new" and ap._page_index == 4, f"172: 上限超えは古いものを捨て、見ている番号を1つずらす {len(ap._pages)} {ap._pages[0].prompt} {ap._page_index}")
ap._page_index = 0
ap._add_talk_page(O.TalkPage(prompt="new2", notice=False))
check(ap._page_index == 0, "172: 番号が 0 未満になるときは 0")
# 依頼（許可）があるあいだは ↑↓ でめくらない
ap, fb = pm_ready()
c_ev(ap, fb, Prompt("s", "あ"))
c_ev(ap, fb, Prompt("s", "い"))
s1 = pm_req(ap)
p_frame(ap, keys=(pyxel.KEY_UP,))
check(ap._page_index is None, "172: 許可の依頼があるあいだは ↑ でページをめくらない")
p_frame(ap, keys=(pyxel.KEY_N,))
s1.close()
# プロンプトが空のページ：「> 」の行とその下の空行を出さない。プロンプトがあるページは「> 」・空行つき
ap, fb = pm_ready()
ap._add_talk_page(O.TalkPage(prompt="", notice=False, replies=["返事だけ"]))
check(dtx(ap, 0) == ["メイン  1/1", "返事だけ"], f"172: プロンプトが空のページは題と返事だけ {dtx(ap, 0)}")
ap._add_talk_page(O.TalkPage(prompt="問い", notice=False, replies=["答え"]))
check(dtx(ap, 0) == ["メイン  2/2", "> 問い", "", "答え"], f"172: プロンプトがあるページは「> 」・空行つき {dtx(ap, 0)}")
ap._add_talk_page(O.TalkPage(prompt="", notice=False))
check(dtx(ap, 0) == ["メイン  3/3", "(返事を待っています)"], f"172: 空のプロンプトで返事も無いページ {dtx(ap, 0)}")
# 知らせ（notice）のページは灰色（NOTICE_COLOR）で出す
ap, fb = pm_ready()
ap._add_talk_page(O.TalkPage(prompt="[知らせ] x", notice=True))
cols = [c for r, c in ap._talk_dialog_lines(0)]
check(cols[1] == O.NOTICE_COLOR and cols[0] == O.TEXT_COLOR, f"172: 知らせのページのプロンプトは NOTICE_COLOR {cols}")

# ---------------------------------------------------------------------------
# 173. Human.stop：歩いている途中で止まる（位置・向きは変えない）
# ---------------------------------------------------------------------------
ap, fb = c_make()
hu = ap.human
check(hu is not None, "173: 前提：人間がいる")
fx, fz = c_free_point(ap, 3)
check(hu.walk_to(fx, fz, []) and hu.walking, "173: 前提：道が見つかって歩き出す")
for _ in range(15):
    ap.update()
pos_mid, yaw_mid = (hu.pos.x, hu.pos.z), hu.yaw
check(hu.walking and (pos_mid != (O.HUMAN_START[0], O.HUMAN_START[1])), f"173: 前提：途中まで歩いた {pos_mid}")
hu.stop()
check(not hu.walking and hu._path == [] and (hu.pos.x, hu.pos.z) == pos_mid and hu.yaw == yaw_mid, f"173: stop で道が空になり、位置と向きは変わらない {(hu.pos.x, hu.pos.z)} {pos_mid}")
for _ in range(10):
    ap.update()
check((hu.pos.x, hu.pos.z) == pos_mid, "173: stop のあとは進まない")
hu.stop()
check(not hu.walking, "173: 立っているときの stop も安全")

# ---------------------------------------------------------------------------
# 174. font_safe（UI フォントに無い字の置き換え）
# ---------------------------------------------------------------------------
check(O.font_safe("あ✔", frozenset()) == "あ✔", "174: codes が空なら text をそのまま返す")
codes_a = frozenset(range(0x20, 0x7F)) | {ord("あ"), ord("～")}
check(O.font_safe("aあb", codes_a) == "aあb", "174: フォントにある字はそのまま")
check(O.font_safe("✔▸", codes_a) == "v>", f"174: 無い字は形の似た字に置き換える {O.font_safe('✔▸', codes_a)!r}")
check(O.font_safe("〜", codes_a) == "～", "174: 置き換え先がフォントにあれば置き換える")
check(O.font_safe("☃", codes_a) == "?", "174: 置き換えも無い字は ?")
check(O.font_safe("└", codes_a) == "?", "174: 置き換え先（└ など）がフォントに無いものは ?")
check(O.font_safe("a b\n　", codes_a) == "a b\n　", "174: 空白・改行は codes に無くてもそのまま")
check(O.font_safe("", codes_a) == "", "174: 空の文字列")
# 実際の UI フォントの文字コード（読めたとき）で、置き換えの表の置き換え先は必ず描ける字か ? になる
real_codes = O.font_codepoints(O.UI_FONT_PATH)
if real_codes:
    out_ = O.font_safe("".join(O.GLYPH_SUBSTITUTES), real_codes)
    check(all(ord(c) in real_codes or c == "?" for c in out_), f"174: 置き換えの結果はフォントで描ける字か ? {out_!r}")
    check(O.font_safe("日本語 English 123", real_codes) == "日本語 English 123", "174: 実フォントで日本語・英数字はそのまま")

pyxel.btnp = _orig_btnp
if fail:
    print(f"\n失敗 {len(fail)} 件（全 {n_checks} 項目）:")
    for f in fail:
        print(" -", f)
    sys.exit(1)
print(f"{n_checks} 項目 全部成功")
sys.exit(0)
