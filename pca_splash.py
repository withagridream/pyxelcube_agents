"""起動時のスプラッシュ。2つの場面を順に見せる。

1. Pyxelのロゴと「Powered by Pyxel」
2. アプリ名と「Ver. バージョン」

各場面は2秒かけてじわっと浮き出て、2秒止めてから、2秒かけてじわっと消える。
60fps で120フレーム＝2秒。fps が変わっても同じ2秒になるようにフレーム数を合わせる。
文字は Pyxel 標準のフォント（Image.text）で小さな画像に描き、blt の scale で拡大する（四角い粒のまま）。
「じわっと」は黒を pyxel.dither で重ねる濃さを変えて表す。

PYXEL_LOGO の出どころとライセンス：
- PYXEL_LOGO：Pyxelのロゴ（pyxelパッケージのexamples/assets/pyxel_logo_38x16.png）。
  Pyxel：MIT License、Copyright (c) 2018-2026 Takashi Kitao。1画素4ビット・zlib・base64
"""

import base64
import zlib

import pyxel

FADE_FRAMES: int = 120  # 浮き出る時間・消える時間（60fps で2秒）
HOLD_FRAMES: int = 120  # 浮き出たあと止めておく時間（60fps で2秒）
SCENE_COUNT: int = 2
FONT_W: int = 4  # Pyxel標準フォントの1文字の幅
FONT_H: int = 6  # Pyxel標準フォントの1文字の高さ
TEXT_COLOR: int = 7
TEXT_POWERED: str = "Powered by Pyxel"
TEXT_VERSION_PREFIX: str = "Ver. "

# 拡大率の基準（office の 640×500 のとき、ロゴは6倍・文字は3倍）。小さい画面では1倍まで下がる
REF_W: int = 640
REF_H: int = 500
REF_LOGO_SCALE: int = 6
REF_TEXT_SCALE: int = 3

PYXEL_LOGO_SIZE: tuple[int, int] = (38, 16)
PYXEL_LOGO: str = (
    "eNpl0MENxCAMBEDTgfflj5XU6Bf18U8TLiEd3EJyysW3EkIaGbEgItqkRE9rVfZzb0WAt8UGZtgPZdKGu+Ia5J7IbThcO650"
    "EtJAspWwmATHmiLM9ZCBE+gIPCRYB7vNEs4SCon7AmUJHz4b4NuXdnh9ZNr/VxT5AIE7JOU="
)


def _unpack4(data: str, count: int) -> list[int]:
    packed = zlib.decompress(base64.b64decode(data))
    pixels = []
    for byte in packed:
        pixels.append(byte & 15)
        pixels.append(byte >> 4)
    return pixels[:count]


def _image(data: str, size: tuple[int, int]) -> pyxel.Image:
    w, h = size
    img = pyxel.Image(w, h)
    for i, color in enumerate(_unpack4(data, w * h)):
        img.pset(i % w, i // w, color)
    return img


def _text_image(text: str) -> pyxel.Image:
    """文字を Pyxel 標準フォントで小さな画像に描く。背景は色0（blt で透明にする）。

    標準フォントは1字の枠 4×6 のうち、字は左上の 3×5 に収まる（右1列と下1行は空き）。
    空きを除いた大きさにして、真ん中を合わせる。空の文字のときは幅1にする。
    """
    img = pyxel.Image(max(1, len(text) * FONT_W - 1), FONT_H - 1)
    img.text(0, 0, text, TEXT_COLOR)
    return img


def _blt_center(img: pyxel.Image, cx: float, cy: float, scale: int, colkey: int | None) -> None:
    """画像を、中心が (cx, cy) に来るように scale 倍で描く。

    Pyxel の blt の scale は、(x, y) と元の大きさで作る四角の中心を基準に拡大する。
    そのため、拡大後ではなく元の大きさの半分を中心から引いた位置を渡す。
    """
    x = cx - img.width / 2
    y = cy - img.height / 2
    if colkey is None:
        pyxel.blt(x, y, img, 0, 0, img.width, img.height, scale=scale)
    else:
        pyxel.blt(x, y, img, 0, 0, img.width, img.height, colkey, scale=scale)


class Splash:
    """スプラッシュの進行と描画。App.__init__ で pyxel.init のあとに1回だけ作る。"""

    def __init__(self, width: int, height: int, fps: int, app_name: str, app_version: str) -> None:
        """width・height は画面の大きさ、fps は App の fps。app_name・app_version は2つめの場面に出す。"""
        self.width: int = width
        self.height: int = height
        # 120フレーム（60fps で2秒）を、fps に合わせて同じ2秒にする
        self.fade_frames: int = max(1, round(FADE_FRAMES * fps / 60))
        self.hold_frames: int = max(1, round(HOLD_FRAMES * fps / 60))
        self.scene_frames: int = self.fade_frames * 2 + self.hold_frames
        self.total_frames: int = self.scene_frames * SCENE_COUNT
        self.timer: int = 0

        # 拡大率は画面の大きさに合わせる（640×500 でロゴ6倍・文字3倍、256×192 でロゴ2倍・文字1倍）
        k = min(width / REF_W, height / REF_H)
        self.logo_scale: int = max(1, round(REF_LOGO_SCALE * k))
        self.text_scale: int = max(1, round(REF_TEXT_SCALE * k))

        # 位置はすべて「中心」で持つ（_blt_center で描く）。x の中心は画面の左右の真ん中
        self.center_x: float = width / 2
        line_h = FONT_H * self.text_scale

        # 場面1：ロゴは画面の真ん中より少し上（縦の中心）。「Powered by Pyxel」はロゴの下に2行あけた位置（縦の中心）
        self.logo: pyxel.Image = _image(PYXEL_LOGO, PYXEL_LOGO_SIZE)
        logo_h = PYXEL_LOGO_SIZE[1] * self.logo_scale
        self.logo_cy: float = int(height * 0.36)
        self.powered: pyxel.Image = _text_image(TEXT_POWERED)
        self.powered_cy: float = self.logo_cy + logo_h / 2 + line_h * 2 + line_h / 2

        # 場面2：アプリ名とその下の「Ver. 」の行の2行のまとまりを、上下の真ん中に置く（あいだは1行分）
        self.name: pyxel.Image = _text_image(app_name)
        self.version: pyxel.Image = _text_image(TEXT_VERSION_PREFIX + app_version)
        self.name_cy: float = height / 2 - line_h
        self.version_cy: float = height / 2 + line_h

    @property
    def finished(self) -> bool:
        return self.timer >= self.total_frames

    @property
    def scene(self) -> int:
        return min(SCENE_COUNT - 1, self.timer // self.scene_frames)

    def brightness(self) -> float:
        """今の場面の明るさ（0.0＝真っ黒、1.0＝そのまま）。浮き出て、止めて、消える。"""
        t = self.timer % self.scene_frames if not self.finished else self.scene_frames
        if t < self.fade_frames:
            return t / self.fade_frames
        if t < self.fade_frames + self.hold_frames:
            return 1.0
        return max(0.0, (self.scene_frames - t) / self.fade_frames)

    def skip(self) -> None:
        """今の場面を含めて全部飛ばし、終わりにする。"""
        self.timer = self.total_frames

    def update(self) -> None:
        if not self.finished:
            self.timer += 1

    def draw(self) -> None:
        pyxel.cls(0)
        if self.finished:
            return
        if self.scene == 0:
            _blt_center(self.logo, self.center_x, self.logo_cy, self.logo_scale, None)
            _blt_center(self.powered, self.center_x, self.powered_cy, self.text_scale, 0)
        else:
            _blt_center(self.name, self.center_x, self.name_cy, self.text_scale, 0)
            _blt_center(self.version, self.center_x, self.version_cy, self.text_scale, 0)
        # じわっと：黒を網点で重ねる濃さを変える
        darkness = 1.0 - self.brightness()
        if darkness > 0:
            pyxel.dither(darkness)
            pyxel.rect(0, 0, self.width, self.height, 0)
            pyxel.dither(1.0)
