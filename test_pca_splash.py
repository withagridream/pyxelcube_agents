"""pca_splash.py（起動時のスプラッシュ）のテスト。窓は出ない（SDL_VIDEODRIVER=offscreen）。

実行: .venv/bin/python test_pca_splash.py
pyxel.init は1つのプロセスで1回しかできないので、画面の大きさごとに子プロセス（このファイルを --child で呼ぶ）を起こし、
測った値を JSON で受け取って、親がまとめて確かめる。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def child(mode: str, w: int, h: int) -> None:
    """子プロセス：画面を作って測り、JSON を1行出して終わる（pyxel.quit は使わず os._exit）。"""
    os.environ["SDL_VIDEODRIVER"] = "offscreen"
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, HERE)
    import pyxel
    pyxel.init(w, h, title="splash test", quit_key=pyxel.KEY_NONE)
    import pca_splash as S

    def shot() -> list[list[int]]:
        scr = pyxel.screen
        return [[scr.pget(x, y) for x in range(w)] for y in range(h)]

    def nonzero_bbox(pix):
        xs = [x for row in pix for x, c in enumerate(row) if c != 0]
        ys = [y for y, row in enumerate(pix) if any(c != 0 for c in row)]
        return (min(xs), max(xs), min(ys), max(ys)) if xs else None

    def row_runs(pix):
        """色0でない点がある行の連なり（上から順に [開始, 終了]）。"""
        runs, start = [], None
        for y, row in enumerate(pix):
            has = any(c != 0 for c in row)
            if has and start is None:
                start = y
            if not has and start is not None:
                runs.append([start, y - 1])
                start = None
        if start is not None:
            runs.append([start, h - 1])
        return runs

    def count(pix) -> int:
        return sum(1 for row in pix for c in row if c != 0)

    out: dict = {}
    if mode == "splash":
        s = S.Splash(w, h, 60, "pyxelcube_agents", "0.90")
        out["scales"] = [s.logo_scale, s.text_scale]
        for name, timer in (("s1", s.fade_frames + 1), ("s2", s.scene_frames + s.fade_frames + 1)):
            s.timer = timer
            pyxel.cls(0)
            s.draw()
            pix = shot()
            out[name] = {"bbox": nonzero_bbox(pix), "runs": row_runs(pix), "count": count(pix)}
        # 浮き出る途中は止めている時間より暗い（明るい点が少ない）
        s.timer = s.fade_frames // 2
        pyxel.cls(0)
        s.draw()
        out["mid_count"] = count(shot())
        # 終わったあとは全部色0
        s.skip()
        out["skip_finished"] = s.finished
        pyxel.cls(0)
        s.draw()
        out["finished_count"] = count(shot())
        # timer を進めて自然に終わる
        s2 = S.Splash(w, h, 60, "a", "1")
        for _ in range(s2.total_frames):
            s2.update()
        out["natural_finished"] = s2.finished
        s2.update()
        out["timer_stops"] = s2.timer == s2.total_frames
    else:
        img = pyxel.Image(4, 2)
        img.cls(7)
        pyxel.cls(0)
        S._blt_center(img, 16, 16, 3, None)
        out["blt"] = nonzero_bbox(shot())
    print("RESULT " + json.dumps(out), flush=True)
    os._exit(0)


if len(sys.argv) >= 5 and sys.argv[1] == "--child":
    child(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))

# ---------------------------------------------------------------------------
# 親：子プロセスを起こして結果を確かめる
# ---------------------------------------------------------------------------
fail: list[str] = []
n_checks = 0


def check(c, msg):
    global n_checks
    n_checks += 1
    if not c:
        fail.append(msg)
        print("NG:", msg)


def run_child(mode: str, w: int, h: int) -> dict:
    env = dict(os.environ)
    env["SDL_VIDEODRIVER"] = "offscreen"
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", mode, str(w), str(h)],
                          capture_output=True, text=True, env=env, timeout=120)
    lines = [x for x in proc.stdout.splitlines() if x.startswith("RESULT ")]
    if not lines:
        check(False, f"子プロセス {mode} {w}x{h} の結果が無い rc={proc.returncode} {proc.stdout[-300:]!r} {proc.stderr[-300:]!r}")
        return {}
    return json.loads(lines[0][7:])


for w, h in ((640, 500), (256, 192)):
    tag = f"{w}x{h}"
    r = run_child("splash", w, h)
    if not r:
        continue
    check(r["scales"] == ([6, 3] if w == 640 else [2, 1]), f"{tag}: 拡大率（ロゴ・文字） {r['scales']}")
    # 場面1：左右の中心が画面の真ん中から ±1
    x0, x1, y0, y1 = r["s1"]["bbox"]
    check(abs((x0 + x1) / 2 - w / 2) <= 1, f"{tag}: 場面1の左右の中心 {(x0 + x1) / 2} 画面の真ん中 {w / 2}")
    # 場面2：左右・上下の中心が ±1
    x0, x1, y0, y1 = r["s2"]["bbox"]
    check(abs((x0 + x1) / 2 - w / 2) <= 1, f"{tag}: 場面2の左右の中心 {(x0 + x1) / 2} 画面の真ん中 {w / 2}")
    check(abs((y0 + y1) / 2 - h / 2) <= 1, f"{tag}: 場面2の上下の中心 {(y0 + y1) / 2} 画面の真ん中 {h / 2}")
    # 場面1：ロゴ（上の行の塊）が Powered by Pyxel（下の行の塊）より上。ロゴの中心は上下の真ん中より上
    runs = r["s1"]["runs"]
    check(len(runs) >= 2, f"{tag}: 場面1に行の塊が2つ以上（ロゴと文字） {runs}")
    if len(runs) >= 2:
        logo_top, logo_bottom = runs[0]
        powered_top = runs[-1][0]
        check(logo_top < powered_top, f"{tag}: ロゴの上端 {logo_top} が Powered の上端 {powered_top} より上")
        check((logo_top + logo_bottom) / 2 < h / 2, f"{tag}: ロゴの中心 {(logo_top + logo_bottom) / 2} が画面の上下の真ん中 {h / 2} より上")
    # 場面1はロゴのあるぶん、場面2より点が多い（描かれている）
    check(r["s1"]["count"] > 0 and r["s2"]["count"] > 0, f"{tag}: 止めている時間に何かが描かれる")
    # 浮き出る途中は止めている時間より明るい点が少ない。終わったあとは全部色0
    check(0 < r["mid_count"] < r["s1"]["count"], f"{tag}: 浮き出る途中の点の数 {r['mid_count']} が止めている時間 {r['s1']['count']} より少ない")
    check(r["finished_count"] == 0, f"{tag}: finished のあとは全部色0 {r['finished_count']}")
    check(r["skip_finished"] is True, f"{tag}: skip() のあと finished が True")
    check(r["natural_finished"] is True and r["timer_stops"] is True, f"{tag}: 最後まで update すると finished になり、timer はそこで止まる")

# _blt_center 単体：4×2 を scale 3 で中心 (16, 16) に描く。実測 x 10〜21・y 13〜18 に ±1
r = run_child("blt", 64, 64)
if r:
    bx0, bx1, by0, by1 = r["blt"]
    check(abs(bx0 - 10) <= 1 and abs(bx1 - 21) <= 1 and abs(by0 - 13) <= 1 and abs(by1 - 18) <= 1, f"_blt_center の点の範囲 x:{bx0}〜{bx1} y:{by0}〜{by1}（期待 x10〜21・y13〜18）")
    check(abs((bx0 + bx1) / 2 - 16) <= 1 and abs((by0 + by1) / 2 - 16) <= 1, f"_blt_center の中心が (16, 16) の ±1 {((bx0 + bx1) / 2, (by0 + by1) / 2)}")

print(f"（子プロセスで {n_checks} 項目を確かめた）")
if fail:
    print(f"\n失敗 {len(fail)} 件（全 {n_checks} 項目）:")
    for f in fail:
        print(" -", f)
    sys.exit(1)
print(f"{n_checks} 項目 全部成功")
sys.exit(0)
