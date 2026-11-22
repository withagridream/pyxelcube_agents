# pyxelcube_agents.py メソッド別の仕様書（版 0.90）

`pyxelcube_agents.py`（5589 行）の定数・クラス・関数・メソッドを、行番号つきで説明する。クラスごとに概要と主な属性、メソッドごとに概要・引数・戻り値・主な変数を書く。行番号は版 0.90 のもの（日本語・英語の切り替え〔i18n〕を入れる前の行番号が多い。i18n で変わった所と、その節は「言語の切り替え（i18n）」の章に書いた）。コードを読んで確かめたことだけを書き、読み取れないことはそう書いた。

- 数：クラス 16、関数とメソッド 277（名前の種類 264）、定数 334
- 起動のしかたは [../README.md](../README.md)、全体の仕様は [../../pyxelcube_agents_spec.md](../../pyxelcube_agents_spec.md)

## 目次

- 先頭（1〜38 行）：docstring と import
  - モジュールの docstring（1〜12 行）
  - import（14〜37 行）
- 定数（40〜500 行。モジュール全体の分）
  - アプリの名前と版（39〜41 行）
  - 画面サイズ（43〜45 行）
  - 状態を表す文字列（47〜53 行）
  - 床の範囲（55〜62 行）
  - 行動のパラメータ（64〜70 行）
  - 当たり判定（72〜77 行。床を上から見た x-z 平面。高さは見ない）
  - 机と床の寸法・色（79〜93 行）
  - 席の位置（95〜96 行）
  - 椅子の寸法（98〜103 行。席の位置が原点、yaw=0 で -Z が前＝机の方）
  - 肌の色（105〜106 行）
  - キャラの見た目の寸法（108〜124 行。キャラのローカル座標。足の裏が y=0、yaw=0 で -Z が前）
  - 座ったときの体のずらし（126〜129 行）
  - 関節の角度の範囲（131〜135 行。度）
  - 歩幅・タイピング（137〜138 行）
  - 行き先（office だけ）の時間・くじの重み・身ぶり（140〜160 行）
  - 行き先の位置（162〜173 行。center は体を向ける先、slots は立つ場所の (x, z)）
  - 道探し（office だけ）（175〜192 行）
  - 人間（ユーザーの分身。office だけ）（194〜220 行）
  - office の画面の配分（222〜244 行。3D の範囲と、下の履歴・入力欄。proto は 256×192 のまま）
  - モード（246〜250 行。office だけ）
  - 日本語入力（fcitx5＋mozc）の「変換中」の推測（251〜261 行）
  - キャラの設定（263〜268 行）
  - office（本番に近い配置）の寸法（270〜280 行）
  - office の窓際の机と席（282〜285 行）
  - office の島（287〜290 行）
  - office の壁（左・右・手前）（292〜297 行）
  - REST ROOM のドア（299〜313 行。左の壁に付く。蝶番は奥側の端 (DOOR_X, 0, DOOR_Z - DOOR_WIDTH/2)）
  - 掲示板（利用制限の棒グラフ）（315〜329 行。奥の壁。文字は描かない）
  - 利用制限を /usage の画面から読む（330〜336 行。`--claude` のとき）
  - office の小物：書棚・観葉植物・丸テーブル・コーヒーメーカー（338〜369 行）
  - 利用制限（掲示板の棒）の設定（371〜375 行。設定ファイルが無い・壊れているときの既定値）
  - 本物の Claude Code とつなぐ（378〜396 行。`--claude` のときだけ使う）
  - 許可の依頼（hook から届く）（403〜429 行）
  - 会話のダイアログ（430〜438 行。3D の範囲の下寄り。x 16〜624、y 170〜288）
  - 今のモデルと effort（440〜446 行。`--claude` のとき。画面の文字から読む・`/model` と `/effort` の結果から覚える）
  - 選ぶメニュー（447〜462 行。`--claude` のとき、入力欄に「/model」「/effort」だけを送ったら出す。(表示名, 送る引数)）
  - コマンドの窓（SLASH）（464〜500 行。`--claude` で「/」で始まる文を送ったあとに、3D の範囲の中〔MODE の札の下〕へ出す）
  - 配置・行き先の定数（インスタンス。554〜624 行）
  - 描画・ズーム・カメラ操作の定数（729〜740 行）
- モジュールの関数（1〜1978 行の範囲）
  - `_is_blocked_command(text: str) -> bool`（480 行）
  - `_office_color(index: int) -> int`（521 行）
  - `_office_desks() -> tuple[Vec3, ...]`（526 行）
  - `_office_seats() -> tuple[tuple[Vec3, float, int], ...]`（535 行）
  - `_desk_rect(desk_center: Vec3) -> Rect`（645 行）
  - `_chair_rect(seat: Vec3, seat_yaw: float) -> Rect`（657 行）
  - `_wall_rect(wall_center: Vec3, wall_size: Vec3) -> Rect`（678 行）
  - `_build_obstacles(layout: Layout) -> list[Obstacle]`（690 行）
  - `_rect_from_center(cx: float, cz: float, half_x: float, half_z: float) -> Rect`（718 行）
  - `_build_circles(layout: Layout) -> list[tuple[float, float, float]]`（723 行）
  - `_clamp(value: float, low: float, high: float) -> float`（743 行）
  - `push_out_of_rect(x: float, z: float, r: float, rect: Rect) -> tuple[float, float]`（748 行）
  - `push_out_of_circle(x: float, z: float, r: float, cx: float, cz: float, cr: float) -> tuple[float, float]`（783 行）
  - `_as_finite_float(value: object) -> float | None`（802 行）
  - `load_rate_settings(config_path: Path) -> tuple[str, float]`（813 行）
  - `_parse_usage(lines: list[str]) -> tuple[float | None, float | None, str | None, str | None]`（834 行）
  - `_read_used_percentage(data: object, key: str) -> float`（860 行）
  - `separate(ax: float, az: float, bx: float, bz: float, r: float, a_fixed: bool, b_fixed: bool) -> tuple[float, float, float, float]`（873 行）
  - `_view_dir(yaw: float, pitch: float) -> Vec3`（912 行）
  - `facing_yaw(fx: float, fz: float, tx: float, tz: float, default: float = 0.0) -> float`（926 行）
  - `stand_pose() -> Pose`（1352 行）
  - `walk_pose(phase: float) -> Pose`（1368 行）
  - `sit_pose(t: float) -> Pose`（1385 行）
  - `drink_pose() -> Pose`（1403 行）
  - `shelf_pose() -> Pose`（1411 行）
  - `plant_pose() -> Pose`（1419 行）
  - `spot_pose(kind: str) -> Pose`（1438 行）
  - `gesture_pose(kind: str) -> Pose`（1447 行）
- クラス
  - クラス `Layout`（503〜519 行。`@dataclass(frozen=True)`）
  - クラス `Spot`（593〜603 行。`@dataclass(frozen=True)`）
  - クラス `Rect`（627〜634 行。`@dataclass(frozen=True)`）
  - クラス `Obstacle`（637〜642 行。`@dataclass(frozen=True)`）
  - クラス `NavGrid`（935 行）
  - クラス `SpotManager`（1241 行）
  - クラス `Chatter`（1304〜1311 行。`@dataclass`）
  - クラス `Pose`（1315〜1349 行。`@dataclass`）
  - クラス `Agent`（1464 行）
  - クラス `Human`（1917 行。`Agent` を継承）
- 描画・許可の受け取り・App の前半（1979〜3700 行）
  - クラス `AgentView`（1979 行）
  - クラス `MarkerView`（2052 行）
  - クラス `OfficeRoot`（2084 行）
  - モジュールの関数
  - クラス `PermRequest`（2264 行）
  - クラス `PermServer`（2303 行）
  - クラス `App`（2508 行）
- App の後半・起動（3701 行〜最後）
  - クラス `App` の続き（3701〜5523 行）
  - モジュールの関数
  - わからなかった点（コードからは読み取れない）
- 言語の切り替え（i18n）
  - `pca_i18n.py`（`LANGS`・`MESSAGES`・`detect_lang`・`set_lang`・`get_lang`・`t`）
  - 文の定数がキーの文字列になったこと
  - `parse_args` の 2 段の読み方
  - `hook_settings_json`・`claude_command`
  - `pca_perm_hook.py` の `DENY_MESSAGES`・`hook_lang`・`decision_output`
  - 英語の画面が前提の所
- スプラッシュ（`pca_splash.py`）

---

## 先頭（1〜38 行）：docstring と import

### モジュールの docstring（1〜12 行）
3 人のキャラが自分の席の周りをうろつき、スペースキーで順に作業状態へ切り替わる小さな 3D オフィスの試作。行動の計算は描画しない `Agent`、3D の描画は `Node`（Pyxel Cube の 3D 部品）を継承したクラスに分ける。キャラは肩・肘・足の付け根・膝が曲がる人型で、姿勢は `Pose` にまとめる。

docstring に書かれている使い方：
- 起動例：`python pyxelcube_agents.py --fps 30 --seed 1`
- 本番に近い配置：`python pyxelcube_agents.py --layout office --agents 18`
- office の配置には、左・右・手前の壁、REST ROOM のドア（D キーで開閉）、奥の壁の掲示板、書棚・観葉植物・丸テーブルを置く。
- 利用制限の値は設定ファイル `pyxelcube_agents.toml`（`--config` で変更可）の `json_path` から読む。キー 1〜4 で手動に変えられる。
- office では、キャラが席を離れて行き先（コーヒー・書棚・植木）へ道を探して行き、1 人か会話で過ごして席へ戻る。
- 道は障害物を避けて A*（最短の道を探す方法）で探す。`--time-scale` で行き先と会話の時間だけを早回しできる（歩く速さは変わらない）。

### import（14〜37 行）
| 取り込むもの | 用途（このファイルの 1〜1978 行で読み取れる範囲） |
|---|---|
| `argparse` `atexit` `json` `queue` `re` `select` `socket` `threading` `time` `unicodedata` | 1〜1978 行では `re`（`USAGE_PCT_RE` など）以外は使われていない。ほかは 1979 行以降で使う |
| `heapq` | `NavGrid._astar` の優先度つきの待ち行列（ヒープ） |
| `math` | 三角関数・距離（`hypot`）・`sqrt` など |
| `random` | 型 `random.Random`（乱数生成器）の指定と、うろつきの目標選び |
| `tomllib` | `load_rate_settings` で設定ファイル（TOML）を読む |
| `collections.deque` | `NavGrid._nearest_free` の幅優先探索の待ち行列 |
| `collections.abc.Callable, Sequence` | 型ヒント（`Agent` の依頼先関数、`people` の列） |
| `dataclasses.dataclass, field` | `Layout` `Spot` `Rect` `Obstacle` `Chatter` `Pose` の定義（`field` は 1〜1978 行では未使用） |
| `pathlib.Path` | `UI_FONT_PATH` `DEFAULT_CONFIG_PATH` `DEFAULT_PCA_WORKDIR` などのパス |
| `pyxel` | Pyxel 本体。定数のキーコード（`pyxel.KEY_*`）などに使う |
| `pyxel.cube` の `Camera, Mat4, Node, Shading, Vec3` | 3D 部品。1〜1978 行では `Vec3`（3 次元の点・ベクトル）を多用する |
| `pca_bridge` の `Bridge, Prompt, Reply, SubagentEnd, SubagentStart, Tool, TurnEnd, _tool_summary, prompt_display` | Claude Code とつなぐ部分（1979 行以降で使う） |
| `pca_perm_hook.socket_name`（別名 `perm_socket_name`） | 許可の依頼を受けるソケット名（1979 行以降で使う） |
| `pca_i18n` の `LANGS, detect_lang, get_lang, set_lang, t` | 表示と Claude へ送る文の、日本語・英語の切り替え（「言語の切り替え（i18n）」の章） |
| `shlex` | `hook_settings_json`・`claude_command` で、コマンドのパスと JSON を shell 用に囲む（`shlex.quote`） |

---

## 定数（40〜500 行。モジュール全体の分）

定数はすべて 1〜500 行と、729〜740 行にある。1979 行以降にモジュールの定数は無い（grep で確認した）。値の「単位」は、コードのコメントによると床の 100 単位が 1m。

### アプリの名前と版（39〜41 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `APP_NAME` | `"pyxelcube_agents"` | 窓の題・起動時の表示に使うアプリ名 |
| `APP_VERSION` | `"0.90"` | 版の文字列（窓の題・起動時の表示） |

### 画面サイズ（43〜45 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `SCREEN_W` | `256` | proto 配置の画面の幅（ピクセル） |
| `SCREEN_H` | `192` | proto 配置の画面の高さ（ピクセル） |

### 状態を表す文字列（47〜53 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `WANDER` | `"WANDER"` | 待機（席の周りをうろつく） |
| `WORKING` | `"WORKING"` | 作業中（席に戻って座る） |
| `GOING` | `"GOING"` | 行き先へ向かう（office だけ） |
| `AT_SPOT` | `"AT_SPOT"` | 行き先の立つ場所にいる（office だけ） |
| `RETURNING` | `"RETURNING"` | 行き先から席へ戻る（office だけ） |
| `LEAVING` | `"LEAVING"` | 部屋から出ていく（`--claude` のとき、ドアの内側まで歩く） |

### 床の範囲（55〜62 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `FLOOR_X_MIN` | `-380.0` | proto の床の x の下限 |
| `FLOOR_X_MAX` | `380.0` | 同・上限 |
| `FLOOR_Z_MIN` | `-280.0` | 床の z の下限 |
| `FLOOR_Z_MAX` | `280.0` | 床の z の上限 |
| `WANDER_Z_MIN` | `-50.0` | うろつきの z の下限。机の手前の面 z=-70 より手前に限り、机をすり抜けないようにする |

### 行動のパラメータ（64〜70 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `WANDER_RADIUS` | `120.0` | うろつく半径（単位） |
| `WANDER_SPEED` | `60.0` | うろつくときの速さ（単位/秒） |
| `WORK_SPEED` | `120.0` | 席へ戻る速さ（単位/秒） |
| `WAIT_MIN` | `1.0` | 立ち止まる時間の最小（秒） |
| `WAIT_MAX` | `3.0` | 立ち止まる時間の最大（秒） |
| `WORK_HOLD_SEC` | `5.0` | 席に着いてから WANDER に戻るまでの時間（秒） |

### 当たり判定（72〜77 行。床を上から見た x-z 平面。高さは見ない）
| 名前 | 値 | 用途 |
|---|---|---|
| `AGENT_RADIUS` | `14.0` | キャラの半径（腕を含めた体の幅に合わせる） |
| `STUCK_RATIO` | `0.3` | 予定の距離のこの割合より進めなければ「進めないフレーム」とみなす |
| `STUCK_SEC` | `1.0` | 進めないフレームがこの時間続いたら新しい目標を選び直す（秒） |
| `TARGET_TRIES` | `20` | うろつきの目標を障害物を避けて選ぶ最大回数 |
| `COLLISION_ITERATIONS` | `3` | 1 フレームに「障害物→人どうし」の押し出しを繰り返す回数 |

### 机と床の寸法・色（79〜93 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `DESK_XS` | `(-250.0, 0.0, 250.0)` | proto の机の x の 3 つ |
| `DESK_Y` | `19.0` | 机の中心の高さ（外形の高さ 38 の半分） |
| `DESK_Z` | `-100.0` | proto の机の z |
| `DESK_SIZE` | `Vec3(120, 38, 60)` | 机の外形（天板＋左右の側板） |
| `DESK_COLOR` | `13` | 机の天板と側板の色（既定パレット 13 番、灰色） |
| `DESK_TOP_SIZE` | `Vec3(120, 4, 60)` | 天板の寸法 |
| `DESK_TOP_Y` | `36.0` | 天板の中心の高さ（上面は 38） |
| `DESK_SIDE_SIZE` | `Vec3(4, 34, 60)` | 側板の寸法 |
| `DESK_SIDE_Y` | `17.0` | 側板の中心の高さ（床から 0〜34） |
| `DESK_SIDE_X` | `DESK_SIZE.x/2 - DESK_SIDE_SIZE.x/2`（= 58.0） | 側板の中心の x（机の中心から左右 ±58） |
| `FLOOR_CENTER` | `Vec3(0, -5, 0)` | proto の床の中心 |
| `FLOOR_SIZE` | `Vec3(800, 10, 600)` | proto の床の大きさ |
| `FLOOR_COLOR` | `1` | 床の色 |

### 席の位置（95〜96 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `SEAT_Z` | `-30.0` | proto の席の z（机の手前） |

### 椅子の寸法（98〜103 行。席の位置が原点、yaw=0 で -Z が前＝机の方）
| 名前 | 値 | 用途 |
|---|---|---|
| `CHAIR_SEAT_CENTER` | `Vec3(0, 14, -25)` | 座面の中心（人が引いて座る位置。机の方へ 25 ずれる） |
| `CHAIR_SEAT_SIZE` | `Vec3(30, 4, 30)` | 座面の寸法 |
| `CHAIR_BACK_CENTER` | `Vec3(0, 31, -10)` | 背もたれの中心（座面の後ろ側） |
| `CHAIR_BACK_SIZE` | `Vec3(30, 30, 4)` | 背もたれの寸法 |
| `CHAIR_COLOR` | `4` | 座面と背もたれの色 |

### 肌の色（105〜106 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `SKIN_COLOR` | `15` | 頭と両腕の色（既定パレット 15 番 EDC7B0、うすい肌色） |

### キャラの見た目の寸法（108〜124 行。キャラのローカル座標。足の裏が y=0、yaw=0 で -Z が前）
| 名前 | 値 | 用途 |
|---|---|---|
| `HIP_X` | `7.0` | 脚の付け根の x（左右は ±） |
| `HIP_Y` | `40.0` | 脚の付け根の高さ |
| `THIGH_LEN` | `20.0` | 太ももの長さ |
| `THIGH_THICK` | `10.0` | 太ももの太さ |
| `SHIN_LEN` | `20.0` | すねの長さ |
| `SHIN_THICK` | `9.0` | すねの太さ |
| `BODY_CENTER` | `Vec3(0, 53, 0)` | 胴の中心（y=40〜66） |
| `BODY_SIZE` | `Vec3(28, 26, 16)` | 胴の寸法 |
| `HEAD_CENTER` | `Vec3(0, 75, 0)` | 頭の中心（y=66〜84） |
| `HEAD_SIZE` | `Vec3(18, 18, 18)` | 頭の寸法 |
| `SHOULDER_X` | `18.0` | 肩の x（左右は ±） |
| `SHOULDER_Y` | `64.0` | 肩の高さ |
| `UPPER_ARM_LEN` | `16.0` | 上腕の長さ |
| `UPPER_ARM_THICK` | `8.0` | 上腕の太さ |
| `FOREARM_LEN` | `15.0` | 前腕の長さ |
| `FOREARM_THICK` | `7.0` | 前腕の太さ |

### 座ったときの体のずらし（126〜129 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `SIT_BODY_Y` | `-20.0` | 座ったとき足の裏を床に付けるための、体全体の上下のずらし |
| `SIT_BODY_Z` | `-25.0` | 座ったとき体を前（-Z 側）へずらす量。椅子を机の方へ引いて座り、肩が机の縁に届くようにする |

### 関節の角度の範囲（131〜135 行。度）
| 名前 | 値 | 用途 |
|---|---|---|
| `SHOULDER_RANGE` | `(-60.0, 150.0)` | 肩の範囲 |
| `ELBOW_RANGE` | `(0.0, 150.0)` | 肘の範囲 |
| `HIP_RANGE` | `(-60.0, 120.0)` | 足の付け根の範囲 |
| `KNEE_RANGE` | `(0.0, 150.0)` | 膝の範囲 |

### 歩幅・タイピング（137〜138 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `STRIDE` | `40.0` | 歩幅（単位）。この距離進むと歩行の位相が 1 周期（2π）進む |
| `TYPING_PERIOD_SEC` | `0.3` | 作業中にキーボードを打つ動きの周期（秒） |

### 行き先（office だけ）の時間・くじの重み・身ぶり（140〜160 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `OUTING_WANDER_SEC` | `5.0` | うろつきの時間がこれを超えたら行き先を選ぶ（秒） |
| `OUTING_COOLDOWN_SEC` | `60.0` | 席へ戻ったあと、次に出かけるまでの休み（秒） |
| `ALONE_SEC` | `30.0` | 行き先に 1 人でいる時間（秒）。過ぎたら席へ戻る |
| `TALK_SEC` | `60.0` | 行き先で会話している時間（秒）。過ぎたら席へ戻る |
| `SPEAKER_MIN_SEC` | `4.0` | 話し手を交代するまでの時間の最小（秒） |
| `SPEAKER_MAX_SEC` | `6.0` | 同・最大（秒） |
| `GESTURE_MIN_SEC` | `2.0` | 話し手が身ぶりを選び直すまでの時間の最小（秒） |
| `GESTURE_MAX_SEC` | `4.0` | 同・最大（秒） |
| `LISTEN_MIN_SEC` | `3.0` | 聞き手が姿勢を選び直すまでの時間の最小（秒） |
| `LISTEN_MAX_SEC` | `6.0` | 同・最大（秒） |
| `SPOT_WEIGHT_COFFEE` | `50.0` | 行き先のくじの重み（コーヒー） |
| `SPOT_WEIGHT_SHELF` | `25.0` | 同（書棚 2 つ合わせて） |
| `SPOT_WEIGHT_PLANT` | `25.0` | 同（植木 2 つ合わせて） |
| `KIND_COFFEE` | `"coffee"` | 行き先の種類：コーヒー |
| `KIND_SHELF` | `"shelf"` | 行き先の種類：書棚 |
| `KIND_PLANT` | `"plant"` | 行き先の種類：植木 |
| `GESTURE_BOTH_UP` | `"BOTH_UP"` | 身ぶり：両手を上げる |
| `GESTURE_POINT_LISTENER` | `"POINT_LISTENER"` | 身ぶり：片手を聞き手に向ける |
| `GESTURE_POINT_DESK` | `"POINT_DESK"` | 身ぶり：メインの机を指す |
| `GESTURE_KINDS` | 上の身ぶり 3 つのタプル | 身ぶりの全種類（くじ引きの候補） |

### 行き先の位置（162〜173 行。center は体を向ける先、slots は立つ場所の (x, z)）
| 名前 | 値 | 用途 |
|---|---|---|
| `SPOT_COFFEE_CENTER` | `(0.0, 180.0)` | コーヒーの中心（丸テーブルの位置） |
| `SPOT_COFFEE_RADIUS` | `80.0` | 立つ場所の円の半径（丸テーブルの外側） |
| `SPOT_COFFEE_ANGLES` | `(0, 60, 120, 180, 240, 300)` | 立つ場所の角度（度） |
| `SPOT_SHELF_L_CENTER` | `(-700.0, -580.0)` | 左の書棚の中心 |
| `SPOT_SHELF_L_SLOTS` | 3 か所（x=-740・-700・-660、z=-538） | 左の書棚の立つ場所 |
| `SPOT_SHELF_R_CENTER` | `(700.0, -580.0)` | 右の書棚の中心 |
| `SPOT_SHELF_R_SLOTS` | 3 か所（x=660・700・740、z=-538） | 右の書棚の立つ場所 |
| `SPOT_PLANT_L_CENTER` | `(-740.0, 540.0)` | 左の植木の中心 |
| `SPOT_PLANT_L_SLOTS` | `((-686, 540), (-740, 486))` | 左の植木の立つ場所 |
| `SPOT_PLANT_R_CENTER` | `(740.0, 540.0)` | 右の植木の中心 |
| `SPOT_PLANT_R_SLOTS` | `((686, 540), (740, 486))` | 右の植木の立つ場所 |

### 道探し（office だけ）（175〜192 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `NAV_CELL` | `20.0` | 道探しのマス目の大きさ（単位） |
| `NAV_MARGIN` | `4.0` | 障害物から余分に離す距離（`AGENT_RADIUS` に足す） |
| `NAV_MAX_PER_FRAME` | `1` | 1 フレームに道を探す人数の上限（超えた人は列で順番を待つ） |
| `NAV_PERSON_RADIUS` | `2.0 * AGENT_RADIUS`（= 28.0） | 道探しで人をよける半径（人の中心どうしの距離） |
| `NAV_NEAR_DIST` | `60.0` | 引っかかって道を探し直すとき、この距離より近い人も障害物に入れる |
| `SIDESTEP_AFTER` | `3` | 引っかかりがこの回数続いたら横へよける |
| `SIDESTEP_SEC` | `1.0` | 横へよける時間（秒） |
| `SIDESTEP_PROBE` | `30.0` | よける向きを選ぶとき、この距離先が通れるかを調べる |
| `SQRT2` | `math.sqrt(2.0)` | √2。斜めの移動の距離に使う |
| `NEIGHBORS_8` | `((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))` | 隣り合う 8 方向のマスの差 (di, dj) |
| `NAV_STEPS` | `NEIGHBORS_8` の各方向に「斜めか」「移動の距離（斜めは `SQRT2`、他は 1.0）」を足したタプル | A* の内側の繰り返しで使う (di, dj, 斜めか, 移動の距離) |
| `WORK_PATH_MIN_DIST` | `150.0` | 席からこれより遠いとき、作業に戻る道を探す（単位） |
| `DEFAULT_TIME_SCALE` | `1.0` | 時間の早回し倍率の既定値（行き先・会話のタイマーだけに効く） |

### 人間（ユーザーの分身。office だけ）（194〜220 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `HUMAN_SKIN_COLOR` | `7` | 人間の頭と腕（白） |
| `HUMAN_BODY_COLOR` | `8` | 人間の胴と脚（赤紫 #D4186C） |
| `HUMAN_START` | `(0.0, 40.0)` | 人間の最初の位置 (x, z)。島の左右の列の間・丸テーブルより奥 |
| `HUMAN_SPEED` | `WORK_SPEED`（= 120.0） | 人間の歩く速さ（単位/秒） |
| `MARKER_COLOR` | `10` | 頭の上の▼の色（金 #E9C35B）。陰影なしで描く |
| `MARKER_Y` | `104.0` | ▼の中心の高さ |
| `MARKER_BOB` | `4.0` | ▼が上下に揺れる幅（±） |
| `MARKER_BOB_SEC` | `1.2` | 揺れの周期（秒） |
| `MARKER_HALF` | `7.0` | ▼の上面の正方形の半分の幅 |
| `MARKER_DEPTH` | `14.0` | ▼の高さ（上面から下の頂点まで） |
| `PICK_CENTER_Y` | `45.0` | クリックでエージェントを選ぶ球の中心の高さ |
| `PICK_RADIUS` | `30.0` | その球の半径 |
| `TALK_FRONT_GAP` | `60.0` | 座っている相手の机の中心から、机の正面に立つ位置までの距離 |
| `TALK_SIDE_DIST` | `60.0` | 相手のまわりに立つ位置を探すときの距離 |
| `TALK_DIRECTIONS` | `12` | 相手のまわりに立つ位置を探す方向の数 |
| `HEAD_YAW_LIMIT` | `70.0` | 座っている相手が頭だけを回す角度の上限（度、左右とも） |
| `TALK_CAM_PITCH` | `25.0` | 会話のカメラの見下ろす角度（度） |
| `TALK_CAM_MIN_DIST` | `320.0` | 会話のカメラの距離の下限 |
| `TALK_CAM_DIST_RATIO` | `2.5` | 会話のカメラの距離 ＝ 2 人の間の距離 × この値（下限あり） |
| `TALK_CAM_TARGET_Y` | `45.0` | 会話のカメラが見る高さ（胸のあたり） |
| `CAM_BLEND_SEC` | `0.5` | カメラの切り替えにかける時間（秒） |
| `FOLLOW_RATE` | `6.0` | ふだんのカメラが人間を追う速さ（大きいほど速い。1 - exp(-FOLLOW_RATE*dt) で近づく） |
| `FOLLOW_REPLAN_SEC` | `1.0` | 会話相手が歩いているとき、人間が道を探し直す間隔（秒） |
| `TALK_CLEAR` | `12.0` | 会話で立つ位置は、相手以外の人から 2*AGENT_RADIUS + この値 以上離す |
| `TALK_MIN_SCREEN_GAP` | `24.0` | 会話のカメラで、2 人の頭の画面上の横の差がこれ以上になるようにする（画面の点） |
| `TALK_YAW_OFFSETS` | `(20.0, -20.0, 40.0, -40.0)` | 会話のカメラの yaw をずらして試す量（度、この順） |

### office の画面の配分（222〜244 行。3D の範囲と、下の履歴・入力欄。proto は 256×192 のまま）
| 名前 | 値 | 用途 |
|---|---|---|
| `OFFICE_SCREEN_W` | `640` | office の画面の幅 |
| `OFFICE_SCREEN_H` | `500` | office の画面の高さ |
| `OFFICE_DISPLAY_SCALE` | `2` | 窓の表示倍率 |
| `VIEW3D_H` | `296` | 3D を描く範囲の高さ（0,0,640,296） |
| `UI_FONT_PATH` | `Path(pyxel.__file__).parent / "examples" / "assets" / "PixelMplus12-Regular.ttf"` | UI の日本語フォントのファイル（Pyxel 同梱の例のアセット） |
| `UI_FONT_SIZE` | `12` | フォントの大きさ |
| `UI_LINE_H` | `14` | 1 行の高さ |
| `UI_CHAR_W` | `6` | 半角 1 文字の幅（全角は 12） |
| `UI_PAD` | `6` | 枠の内側の余白 |
| `HISTORY_ROWS` | `9` | 履歴欄の行数 |
| `INPUT_ROWS` | `3` | 入力欄の行数 |
| `INPUT_TEXT_ROWS_CLAUDE` | `2` | `--claude` のとき入力の文字を見せる行数（いちばん下の行は今のモデルと effort） |
| `HISTORY_MAX` | `500` | 履歴に残す行数の上限（古い行から捨てる） |
| `SCROLLBAR_W` | `6` | スクロールバーの幅 |
| `HISTORY_X` | `4` | 履歴欄の左端 |
| `HISTORY_Y` | `VIEW3D_H + 4`（= 300） | 履歴欄の上端 |
| `HISTORY_W` | `632` | 履歴欄の幅 |
| `HISTORY_H` | `HISTORY_ROWS * UI_LINE_H + UI_PAD * 2`（= 138） | 履歴欄の高さ |
| `INPUT_Y` | `HISTORY_Y + HISTORY_H + 4`（= 442） | 入力欄の上端 |
| `INPUT_H` | `INPUT_ROWS * UI_LINE_H + UI_PAD * 2`（= 54） | 入力欄の高さ |
| `UI_COLS` | `(HISTORY_W - UI_PAD*2 - SCROLLBAR_W - 2) // UI_CHAR_W`（= 102） | 1 行の桁数（全角は 2 桁） |
| `COMPOSING_LABEL_RIGHT` | `620` | 「変換中」の札の右端の x（スクロールバーの溝 x 624〜629 より左） |

### モード（246〜250 行。office だけ）
| 名前 | 値 | 用途 |
|---|---|---|
| `MODE_WALK` | `"WALK"` | 3D の操作のモード |
| `MODE_PROMPT` | `"PROMPT"` | 文字の入力のモード |
| `PROMPT_ENTER_KEY` | `pyxel.KEY_P` | WALK → PROMPT に切り替えるキー（PROMPT → WALK は Ctrl+E、`_prompt_exit_pressed`） |

### 日本語入力（fcitx5＋mozc）の「変換中」の推測（251〜261 行）
コードのコメントによると、実機で分かった事実は次のとおり：日本語入力がオンのとき英字キーを押しても `pyxel.input_text` は来ない／変換中の Enter・Backspace・Esc は Pyxel にも届く／確定の Enter は次のフレームに確定した文字が届く／オフのとき英字は押したフレームに届く。
| 名前 | 値 | 用途 |
|---|---|---|
| `IME_GRACE_FRAMES` | `1` | 英字キーを押してから、文字が届くのを待つフレーム数 |
| `IME_ENTER_WAIT` | `2` | Enter のあと、確定した文字が届くのを待つフレーム数 |
| `IME_PRINTABLE_KEYS` | A〜Z・0〜9 の `pyxel.KEY_*` と `KEY_MINUS` のタプル | 日本語入力がオンのとき、押しても文字が届かないキー（英字と数字とマイナス） |

### キャラの設定（263〜268 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `AGENT_SETUP` | `(("A", 8, DESK_XS[0]), ("B", 11, DESK_XS[1]), ("C", 12, DESK_XS[2]))` | proto のキャラの設定（名前, 色, 机の x）。席は机の手前 |

### office（本番に近い配置）の寸法（270〜280 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `OFFICE_FLOOR_CENTER` | `Vec3(0, -5, 0)` | 床の中心 |
| `OFFICE_FLOOR_SIZE` | `Vec3(1600, 10, 1200)` | 床の大きさ |
| `OFFICE_WALL_CENTER` | `Vec3(0, 100, -605)` | 奥の壁の中心 |
| `OFFICE_WALL_SIZE` | `Vec3(1600, 200, 10)` | 奥の壁の大きさ |
| `OFFICE_WALL_COLOR` | `5` | 壁の色 |
| `OFFICE_AGENT_COLORS` | `(2, 3, 6, 7, 8, 9, 10, 11, 12, 14)` | office のキャラの色。床 1・椅子 4・壁 5・机 13・肌 15 を避ける。席番号の順に繰り返す |
| `OFFICE_WANDER_X` | `(-780.0, 780.0)` | うろつきの x の範囲 |
| `OFFICE_WANDER_Z` | `(-580.0, 580.0)` | うろつきの z の範囲 |
| `OFFICE_CAMERA_EYE` | `Vec3(0, 1100, 1300)` | office のカメラの目の位置 |

### office の窓際の机と席（282〜285 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `WINDOW_DESK_XS` | `(-150.0, 150.0)` | 窓際の机の x |
| `WINDOW_DESK_Z` | `-430.0` | 窓際の机の z |
| `WINDOW_SEAT_Z` | `-500.0` | 窓際の席の z（机と壁の間） |

### office の島（287〜290 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `ISLAND_CENTERS` | `((-450,-20),(450,-20),(-450,380),(450,380))` | 島 4 つの中心 (cx, cz) |
| `ISLAND_DESK_OFFSETS` | `((-62,-32),(62,-32),(-62,32),(62,32))` | 島の中の机 4 つの位置（中心からのずれ） |
| `ISLAND_SEAT_OFFSET` | `100.0` | 島の机から席までの距離（z 方向） |

### office の壁（左・右・手前）（292〜297 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `OFFICE_LEFT_WALL_CENTER` | `Vec3(-805, 100, 0)` | 左の壁の中心 |
| `OFFICE_RIGHT_WALL_CENTER` | `Vec3(805, 100, 0)` | 右の壁の中心 |
| `OFFICE_SIDE_WALL_SIZE` | `Vec3(10, 200, 1220)` | 左右の壁の大きさ |
| `OFFICE_FRONT_WALL_CENTER` | `Vec3(0, 22.5, 605)` | 手前の壁の中心（手前の壁は低い） |
| `OFFICE_FRONT_WALL_SIZE` | `Vec3(1620, 45, 10)` | 手前の壁の大きさ |

### REST ROOM のドア（299〜313 行。左の壁に付く。蝶番は奥側の端 (DOOR_X, 0, DOOR_Z - DOOR_WIDTH/2)）
| 名前 | 値 | 用途 |
|---|---|---|
| `DOOR_Z` | `-350.0` | ドアの中心の z |
| `DOOR_WIDTH` | `80.0` | ドアの幅（閉じたとき +Z 方向へ伸びる長さ） |
| `DOOR_HEIGHT` | `160.0` | ドアの高さ |
| `DOOR_THICK` | `6.0` | ドアの厚さ |
| `DOOR_X` | `-797.0` | ドアの x（壁の内側の面 x=-800 のすぐ内側） |
| `DOOR_COLOR` | `9` | ドアの色 |
| `DOOR_OPEN_ANGLE` | `90.0` | 開いたときの角度（度） |
| `DOOR_SPEED` | `180.0` | 開け閉めの速さ（度/秒） |
| `DOOR_SIGN_Y` | `175.0` | ドアの上の札の中心の高さ（動かない） |
| `DOOR_SIGN_SIZE` | `Vec3(4, 16, 70)` | 札の大きさ |
| `SIGN_COLOR` | `7` | 札の色 |
| `DOOR_AREA_X` | `(-800.0, -720.0)` | ドアが回る範囲の当たり判定の x の範囲 |
| `DOOR_AREA_HALF_Z` | `40.0` | 同・z の中心からの半分の幅（ドアが開いても閉じても障害物） |

### 掲示板（利用制限の棒グラフ）（315〜329 行。奥の壁。文字は描かない）
| 名前 | 値 | 用途 |
|---|---|---|
| `BOARD_CENTER` | `Vec3(0, 145, -598)` | 掲示板の中心 |
| `BOARD_SIZE` | `Vec3(240, 70, 2)` | 掲示板の大きさ |
| `BOARD_COLOR` | `7` | 掲示板の色 |
| `BAR_MAX_LEN` | `200.0` | 100% のときの棒の長さ |
| `BAR_LEFT_X` | `-100.0` | 棒の左端の x |
| `BAR_Z` | `-596.0` | 棒の z（板より手前） |
| `BAR_DEPTH` | `2.0` | 棒の奥行き |
| `BAR_HEIGHT` | `14.0` | 棒の高さ |
| `FIVE_HOUR_BAR_Y` | `160.0` | 5 時間の棒の高さ |
| `FIVE_HOUR_BAR_COLOR` | `10` | 5 時間の棒の色 |
| `WEEK_BAR_Y` | `128.0` | 週間の棒の高さ |
| `WEEK_BAR_COLOR` | `8` | 週間の棒の色 |
| `BAR_FRAME_W` | `2.0` | 100% の枠の太さ（棒の外側に置く細い箱） |
| `BAR_FRAME_COLOR` | `0` | 枠の色（黒） |

### 利用制限を /usage の画面から読む（330〜336 行。`--claude` のとき）
| 名前 | 値 | 用途 |
|---|---|---|
| `USAGE_COMMAND` | `"/usage"` | 送るコマンド |
| `USAGE_POLL_SEC` | `0.2` | 画面を読む間隔（秒） |
| `USAGE_CLOSE_SEC` | `2.0` | 画面が閉じるまで待つ時間（秒）。残れば Escape をもう一度送る |
| `USAGE_TIMEOUT_SEC` | `5.0` | 値が取れるまでの上限（秒） |
| `USAGE_AFTER_TURN_SEC` | `1.0` | メインの返事の終わりから読むまでの時間（秒） |
| `USAGE_PCT_RE` | `re.compile(r"(\d+(?:\.\d+)?)% used")` | 画面の「NN% used」を取り出す正規表現（文字の型を表す式）。**英語の画面が前提**（`/usage` の画面の英語の文字を読む。見出しの `Current session`・`Current week`、案内の `Esc to` も同じ） |

### office の小物：書棚・観葉植物・丸テーブル・コーヒーメーカー（338〜369 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `BOOKSHELF_XS` | `(-700.0, 700.0)` | 書棚の x（左右） |
| `BOOKSHELF_Y` | `90.0` | 本体の中心の高さ（床から 0〜180） |
| `BOOKSHELF_Z` | `-580.0` | 書棚の z |
| `BOOKSHELF_SIZE` | `Vec3(120, 180, 36)` | 書棚の大きさ |
| `BOOKSHELF_COLOR` | `4` | 書棚の色 |
| `BOOK_Z` | `-560.0` | 本の段の z（本体の手前に少し出す） |
| `BOOK_SIZE` | `Vec3(110, 30, 4)` | 本の段の大きさ |
| `BOOK_YS` | `(40.0, 90.0, 140.0)` | 本の段の中心の高さ（下から） |
| `BOOK_COLORS` | `(12, 11, 10)` | 本の段の色 |
| `PLANT_POSITIONS` | `((-740.0, 540.0), (740.0, 540.0))` | 観葉植物の (x, z) |
| `PLANT_POT_SIZE` | `Vec3(40, 40, 40)` | 鉢の大きさ |
| `PLANT_POT_Y` | `20.0` | 鉢の中心の高さ |
| `PLANT_POT_COLOR` | `9` | 鉢の色 |
| `PLANT_LEAF_Y` | `70.0` | 葉（球）の中心の高さ |
| `PLANT_LEAF_RADIUS` | `30.0` | 葉の半径 |
| `PLANT_LEAF_COLOR` | `3` | 葉の色 |
| `PLANT_HALF` | `30.0` | 当たり判定の半分の幅（x・z とも） |
| `TABLE_X` | `0.0` | 丸テーブルの x |
| `TABLE_Z` | `180.0` | 丸テーブルの z |
| `TABLE_RADIUS` | `50.0` | 天板の半径 |
| `TABLE_Y` | `72.0` | 天板の高さ |
| `TABLE_COLOR` | `13` | テーブルの色 |
| `TABLE_LEG_SIZE` | `Vec3(10, 72, 10)` | 脚の大きさ |
| `TABLE_LEG_Y` | `36.0` | 脚の中心の高さ |
| `TABLE_BASE_Y` | `1.0` | 台座の中心の高さ |
| `TABLE_BASE_DIAMETER` | `50.0` | 台座の直径 |
| `COFFEE_BODY_SIZE` | `Vec3(24, 32, 18)` | コーヒーメーカー本体の大きさ |
| `COFFEE_BODY_COLOR` | `0` | 本体の色 |
| `COFFEE_LAMP_POS` | `Vec3(8, TABLE_Y + 34, 171)` | ランプの位置 |
| `COFFEE_LAMP_SIZE` | `Vec3(4, 4, 4)` | ランプの大きさ |
| `COFFEE_LAMP_COLOR` | `8` | ランプの色 |

### 利用制限（掲示板の棒）の設定（371〜375 行。設定ファイルが無い・壊れているときの既定値）
| 名前 | 値 | 用途 |
|---|---|---|
| `DEFAULT_CONFIG_PATH` | `Path(__file__).resolve().with_name("pyxelcube_agents.toml")` | 設定ファイルの既定の場所（このファイルと同じフォルダ） |
| `DEFAULT_RATE_JSON_PATH` | `"~/.cache/pixel_office/rate_limits.json"` | 利用制限の JSON の既定の場所 |
| `DEFAULT_RELOAD_SEC` | `3.0` | JSON を読み直す間隔の既定（秒） |
| `RATE_KEY_STEP` | `10.0` | キー 1〜4 で一度に変える量（%） |

### 本物の Claude Code とつなぐ（378〜396 行。`--claude` のときだけ使う）
| 名前 | 値 | 用途 |
|---|---|---|
| `PARK_X` | `-900.0` | 見えていない人の置き場所の x（REST ROOM の中。z はドアの z） |
| `ENTER_INSIDE_X` | `DOOR_AREA_X[1] + 20.0`（= -700.0） | ドアの内側の点の x（部屋の中） |
| `SUB_LEAVE_SEC` | `300.0` | サブエージェントが仕事を終えてから帰るまで（秒）。その間はうろうろする |
| `IDLE_LEAVE_SEC` | `600.0` | メインが作業を止めて帰るまで（秒。tmux は動かしたまま） |
| `HANDOFF_WAIT_SEC` | `300.0` | 終業（と窓の×）で引き継ぎメモを待つ時間（秒） |
| `SESSION_CHECK_SEC` | `2.0` | 始業している間、Claude Code のセッションがあるかを確かめる間隔（秒） |
| `HANDOFF_PROMPT` | `"handoff_prompt"`（キーの文字列） | 終業のとき Claude Code に送る文のキー。使う所で `t(HANDOFF_PROMPT)` を通す。日本語のときの文の例：「今日の作業の引き継ぎメモを書いてください。」 |
| `BUBBLE_SEC` | `6.0` | 吹き出しを出す時間（秒） |
| `BUBBLE_CHARS` | `24` | 吹き出しに出す文字数（それより長ければ「…」） |
| `DOOR_IDLE_CLOSE_SEC` | `2.0` | 出入りが終わってからドアを閉めるまで（秒） |
| `SUB_SLOT_FIRST` | `2` | サブエージェントの席の番号の範囲（この番号から） |
| `SUB_SLOT_END` | `18` | 同（この番号の手前まで） |
| `BUTTON_Y` | `40` | 始業・終業のボタンの高さ |
| `DEFAULT_PCA_WORKDIR` | `Path(__file__).resolve().with_name("pca_work")` | Claude Code を動かすフォルダの既定 |
| `MAIN_INDEX` | `0` | メイン（Claude Code の本体につながる人）の番号 |
| `CLAUDE_TALK_PANEL_W` | `200` | 話しかけたときの様子の札の幅 |
| `LEAVE_ARRIVE_DIST` | `30.0` | 部屋を出る人は、出口の点からこの距離以内に入れば着いたことにする |
| `LEAVE_MAX_SEC` | `40.0` | 部屋を出ようとして、これだけ続いたら、その場で置き場所へ戻す（念のため） |
| `CLAUDE_DIALOG_OPTIONS` | `(("resume","dialog_resume"),("restart","dialog_restart"),("","dialog_cancel"))` | ダイアログの選び方（キーの 1〜3 とクリック）。`(モード, 文のキー)` の組で、描く所で文のキーに `t()` を通す。空の文字列のモードは「やめる」。日本語のときの文の例：「1: 続きから」「2: 前のを終わらせて新しく始める」「3: やめる」 |

### 許可の依頼（hook から届く）（403〜429 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `PERM_WAIT_SEC` | `290.0` | 許可の答えを待つ上限（秒）。hook の待ち（300 秒）より短くして、hook が先に切れたあとに Y が押せないようにする |
| `PERM_KEY_GUARD_SEC` | `0.5` | 自動でワープしたあと Y・N・T を受け付けない時間（秒）。直前に押していたキーで答えてしまわないように |
| `PERM_KEY_GUARD_PROMPT_SEC` | `1.0` | 入力欄で打っている最中に自動で WALK に切り替えたときの、Y・N・T を受け付けない時間（秒）。打ちかけの y などで答えてしまわないように長めにする |
| `PERM_ACCEPT_SEC` | `0.3` | 待ち受けの accept（接続を受ける呼び出し）を止められるか確かめる間隔（秒） |
| `PERM_READ_SEC` | `2.0` | 接続して依頼の 1 行を読むまでの時間（秒） |
| `PERM_MAX_LINE` | `65536` | 依頼の 1 行の最大バイト数 |
| `PERM_WAIT_NOTE` | `"perm_wait_note"`（キー） | 許可待ちのときに出す注記のキー（`t()` を通す）。日本語のときの文の例：「(許可の答えを待っています。送信は止めています)」 |
| `PERM_KEYS_TEXT` | `"perm_keys"`（キー） | 許可の案内の文のキー。日本語のときの文の例：「Y:許可  N:断る  T:tmuxで答える」 |
| `PERM_KEYS_ALWAYS_TEXT` | `"perm_keys_always"`（キー） | 案（permission_suggestions）がある依頼の案内のキー。日本語のときの文の例：「Y:許可  A:いつも許可  N:断る  T:tmuxで答える」 |
| `PERM_ALWAYS_CONFIRM_TEXT` | `"perm_always_confirm"`（キー） | 「いつも許可」の確かめの案内のキー。日本語のときの文の例：「もう一度 A:いつも許可する  ほかのキー:やめる」 |
| `PERM_ALWAYS_QUESTION` | `"perm_always_question"`（キー） | 確かめの 1 行目（黄色）のキー。日本語のときの文の例：「いつも許可しますか？」。確かめの行が黄色かどうかの判定は `row == t(PERM_ALWAYS_QUESTION)` で、言語で変わる文どうしを比べる |
| `PERM_ALWAYS_COLOR` | `10` | 黄色（確かめの文と案内） |
| `PERM_SUGGEST_COLOR` | `13` | 灰色（履歴に出す案の行） |
| `PERM_RULE_SCOPE` | 辞書（`localSettings`・`projectSettings`・`userSettings`・`session` → 文のキー `scope_local`・`scope_project`・`scope_user`・`scope_session`） | 案の保存先の言葉のキー。引く所で `t()` を通す。ここに無いものは（キーにせず）そのまま出す。日本語のときの言葉の例：「作業フォルダの設定（.claude/settings.local.json）」 |
| `PERM_CANCEL_BUTTONS` | `dir(pyxel)` のうち `KEY_` と `MOUSE_BUTTON_` で始まる名前から `KEY_A` を除いた全部のタプル | 確かめの間に押されたら、確かめをやめるキー・マウスのボタン（A 以外の全部） |

### 会話のダイアログ（430〜438 行。3D の範囲の下寄り。x 16〜624、y 170〜288）
背景だけ半透明（`pyxel.dither(0.5)`）、枠・文字・スクロールバーは通常の濃さで描く。高さ 119 は行数の計算（`DLG_BODY_ROWS` など）にも使う。
| 名前 | 値 | 用途 |
|---|---|---|
| `DLG_X` | `16` | ダイアログの左端 |
| `DLG_Y` | `170` | 上端 |
| `DLG_W` | `608` | 幅 |
| `DLG_H` | `119` | 高さ |
| `DLG_COLS` | `(DLG_W - UI_PAD*2 - SCROLLBAR_W - 2) // UI_CHAR_W`（= 98） | 中身の 1 行の桁数 |
| `DLG_WHEEL_ROWS` | `3` | ホイール 1 ノッチで動かす行数 |
| `DLG_BODY_ROWS` | `(DLG_H - UI_PAD*2) // UI_LINE_H`（= 7） | 中身が出せる行数（最後の行を除く前） |

### 今のモデルと effort（440〜446 行。`--claude` のとき。画面の文字から読む・`/model` と `/effort` の結果から覚える）
| 名前 | 値 | 用途 |
|---|---|---|
| `STATE_READ_SEC` | `15.0` | 始業したあと、画面から今のモデルを読む時間（秒）。見つかったら読むのをやめる |
| `STATE_READ_EVERY_SEC` | `0.5` | 画面を読む間隔（秒） |
| `STATE_RE` | `re.compile(r"(Opus|Sonnet|Fable|Haiku) (\d+(?:\.\d+)?)(?: with (\w+) effort)?")` | 画面の表示行（例 Opus 5.5 with medium effort）からモデル名・版・effort を取る正規表現。**英語の画面が前提**（`with ... effort` が英語の画面の文） |
| `SET_MODEL_RE` | `re.compile(r"(?:Set model to|Kept model as) `([^`]+)`")` | 会話記録の `/model` の結果から名前を取る正規表現。**英語の画面（会話記録）が前提** |
| `SET_EFFORT_RE` | `re.compile(r"Set effort level to (\w+)")` | 会話記録の `/effort` の結果から値を取る正規表現。**英語の画面（会話記録）が前提** |
| `STATE_DEFAULT_EFFORT` | `"medium"` | 画面に effort の表示が無いときの既定 |

### 選ぶメニュー（447〜462 行。`--claude` のとき、入力欄に「/model」「/effort」だけを送ったら出す。(表示名, 送る引数)）
| 名前 | 値 | 用途 |
|---|---|---|
| `MENU_MODEL_CHOICES` | Default・Opus 5.5・Sonnet 5.5・Fable 5.2・Haiku 5.5（引数は `default`・`claude-opus-5-5`・`claude-sonnet-5-5`・`claude-fable-5-2`・`claude-haiku-5-5`） | `/model` のメニューの選択肢 |
| `MENU_EFFORT_CHOICES` | low・medium・high・xhigh・max（表示名と引数は同じ） | `/effort` のメニューの選択肢 |
| `MENU_GUIDE` | `"menu_guide"`（キー） | メニューの案内の文のキー（`t()` を通す）。日本語のときの文の例：「↑↓:選ぶ  Enter:決める  Esc:やめる（選んだ値は新しいセッションの既定にも保存されます）」 |

### コマンドの窓（SLASH）（464〜500 行。`--claude` で「/」で始まる文を送ったあとに、3D の範囲の中〔MODE の札の下〕へ出す）
| 名前 | 値 | 用途 |
|---|---|---|
| `SLASH_X` | `16` | 窓の左端 |
| `SLASH_Y` | `22` | 上端 |
| `SLASH_W` | `608` | 幅 |
| `SLASH_H` | `268` | 高さ（y 22〜289） |
| `SLASH_POLL_SEC` | `0.25` | 画面を読む間隔（秒） |
| `SLASH_CLOSE_SEC` | `0.5` | パネルの案内が消えてから閉じるまで（秒） |
| `SLASH_STATIC_SEC` | `2.0` | パネルを一度も見ないまま、結果だけの窓に切り替えるまで（秒） |
| `SLASH_DITHER` | `0.75` | 背景を少し透かす（`pyxel.dither` の値） |
| `SLASH_COLS` | `(SLASH_W - UI_PAD*2 - SCROLLBAR_W - 2) // UI_CHAR_W`（= 98） | 画面の行の 1 行の桁数 |
| `SLASH_BODY_ROWS` | `(SLASH_H - UI_PAD*2) // UI_LINE_H - 2`（= 16） | 画面の行が出せる行数（1 行目はコマンド、最後は案内） |
| `SLASH_EXIT_CMDS` | `("/exit", "/quit")` | この文は窓を出さない。コメントによると `_send_input` で `BLOCKED_CMDS` に止められるので今は届かないが、そのまま残してある |
| `BLOCKED_CMDS` | `("/exit", "/quit")` | `--claude` のとき Claude Code に送らせない文（終わるときは F1 の終業を使う） |
| `SLASH_GUIDE_PANEL` | `"slash_guide_panel"`（キー） | パネル表示のときの案内のキー（`t()` を通す。関数 `_is_blocked_command` のあとに置かれている）。日本語のときの文の例：「キーは Claude Code に送られます（Esc で閉じる）」 |
| `SLASH_GUIDE_STATIC` | `"slash_guide_static"`（キー） | 結果だけの窓のときの案内のキー（`t()` を通す）。日本語のときの文の例：「Esc・Enter・クリックで閉じる」 |
| `TALK_PAGE_GUIDE` | `"talk_page_guide"`（キー） | 会話のダイアログにページが 2 つ以上あるとき、一番下に出す案内のキー（`t()` を通す）。日本語のときの文の例：「↑↓:前後のやりとり」 |
| `SLASH_KEYS` | 12 組のタプル（↑↓←→・Enter・KP Enter・Esc・Tab・Backspace・Space・PageUp・PageDown） | 窓の中で tmux へ送るキー：(pyxel のキー, tmux のキー名, 押しっぱなしで繰り返すか)。繰り返すのは矢印 4 つ・Backspace・PageUp・PageDown |

### 配置・行き先の定数（インスタンス。554〜624 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `PROTO_LAYOUT` | `Layout(...)`（机 3・壁なし・席 3・カメラ目 (0,450,650)・zoom 120〜1500） | proto の配置（`--layout proto`） |
| `OFFICE_LAYOUT` | `Layout(...)`（机 `_office_desks()`・壁 4・席 `_office_seats()`・カメラ目 `OFFICE_CAMERA_EYE`・zoom 150〜3000・`has_props=True`） | office の配置（`--layout office`） |
| `LAYOUTS` | `{"proto": PROTO_LAYOUT, "office": OFFICE_LAYOUT}` | 配置の名前から `Layout` を引く辞書 |
| `OFFICE_SPOTS` | `_office_spots()` の結果（`Spot` 5 つ） | office の行き先の一覧 |

### 描画・ズーム・カメラ操作の定数（729〜740 行）
| 名前 | 値 | 用途 |
|---|---|---|
| `TEXT_COLOR` | `7` | 文字の色（白） |
| `NOTICE_COLOR` | `13` | 決まった形の知らせ（コマンドの結果・サブエージェントの知らせ）を履歴に出す灰色 |
| `ZOOM_STEP` | `0.9` | マウスホイール 1 ノッチごとの距離の倍率 |
| `FAR_MARGIN` | `2500.0` | 遠方クリップ（奥の切り捨て）の余裕（単位） |
| `CAM_YAW_SPEED` | `90.0` | カーソルキーで視点を回す速さ（度/秒） |
| `CAM_PITCH_SPEED` | `60.0` | 見下ろす角度（pitch）を変える速さ（度/秒） |
| `CAM_PITCH_MIN` | `10.0` | pitch の下限（度） |
| `CAM_PITCH_MAX` | `85.0` | pitch の上限（度） |

---

## モジュールの関数（1〜1978 行の範囲）

座標の約束（コードのコメントより）：床は x と z の平面で、y が高さ。単位は 100 単位 = 1m。キャラの yaw=0 のとき前は -Z。`Vec3` は Pyxel Cube の 3 次元のベクトル（x・y・z の 3 つの値）。

### `_is_blocked_command(text: str) -> bool`（480 行）
概要：送る文が `BLOCKED_CMDS`（`/exit`・`/quit`）かを調べる。前後の空白を除き、小文字にして、先頭の語が `/exit` か `/quit` のとき True。「/exit now」は True、「/exits」「/exit2」は False。
- 引数：
  - `text`（`str`）：送ろうとしている文
- 戻り値：`bool`。ブロック対象なら True
- 主な変数：`parts` … 空白で最大 2 つに分けた語の並び（先頭の語だけを見る）
- 備考：この関数の定義の途中（定数の並びの間）に置かれている。直後に `SLASH_GUIDE_PANEL` などの定数が続く。

### `_office_color(index: int) -> int`（521 行）
概要：office の席番号 `index` のキャラの色を返す。床・机・壁・肌と重ならない色を、`OFFICE_AGENT_COLORS` から順に繰り返して割り当てる。
- 引数：
  - `index`（`int`）：席の番号
- 戻り値：`int`。Pyxel の色番号
- 主な変数：なし

### `_office_desks() -> tuple[Vec3, ...]`（526 行）
概要：office の机の中心の一覧を作る。窓際 2 つ（`WINDOW_DESK_XS`）、続いて島 4 つ × 机 4 つの順（計 18 個）。
- 引数：なし
- 戻り値：`tuple[Vec3, ...]`。机の中心（高さは `DESK_Y`）
- 主な変数：`desks` … 机の中心を入れるリスト（最後にタプルにする）

### `_office_seats() -> tuple[tuple[Vec3, float, int], ...]`（535 行）
概要：office の席の一覧（位置, 座ったときの yaw, 色）を作る。窓際 2 つ → 島の 16 席の順。yaw 180 は +Z（部屋の方）、yaw 0 は -Z（机の方）を向く。島の奥の列（`dz < 0`）の机は机の奥側（-Z 側）に席を置いて +Z を向く。手前の列の机は手前側（+Z 側）に席を置いて -Z を向く。
- 引数：なし
- 戻り値：`tuple[tuple[Vec3, float, int], ...]`。(席の位置, yaw, 色)。色は `_office_color(席番号)`
- 主な変数：`raw` … (席の位置, yaw) を入れるリスト（色を足す前）

### `_desk_rect(desk_center: Vec3) -> Rect`（645 行）
概要：机の中心から、机の外形（`DESK_SIZE`）の半分ずつ広げた長方形を返す（当たり判定用）。
- 引数：
  - `desk_center`（`Vec3`）：机の中心
- 戻り値：`Rect`。x と z の範囲
- 主な変数：`half_x`・`half_z` … 外形の半分の幅

### `_chair_rect(seat: Vec3, seat_yaw: float) -> Rect`（657 行）
概要：席の椅子（座面と背もたれをまとめた）の長方形を返す。席のローカル座標での範囲（z は座面の奥の端 -40 から背もたれの手前の端 -8）を、席の向きに合わせて世界の座標にする。`seat_yaw` は 0 か 180 だけを扱う。
- 引数：
  - `seat`（`Vec3`）：席の位置
  - `seat_yaw`（`float`）：座ったときの向き（度）。0（-Z が前）か 180（+Z が前）
- 戻り値：`Rect`。椅子の x・z の範囲
- 例外：`seat_yaw` が 0 でも 180 でもなければ `ValueError`
- 主な変数：`local_z_min`・`local_z_max` … 席のローカル座標での椅子の z の範囲。180 度のときは z の向きが反転する（x は左右対称なので変わらない）

### `_wall_rect(wall_center: Vec3, wall_size: Vec3) -> Rect`（678 行）
概要：壁の中心と大きさから長方形（x・z の範囲）を作る。
- 引数：
  - `wall_center`（`Vec3`）：壁の中心
  - `wall_size`（`Vec3`）：壁の大きさ（x と z を使う）
- 戻り値：`Rect`
- 主な変数：`half_x`・`half_z` … 大きさの半分

### `_build_obstacles(layout: Layout) -> list[Obstacle]`（690 行）
概要：配置の机・椅子・壁から障害物の一覧を作る。机 i と椅子 i は席 i の持ち物（`owner = i`）。壁は `owner=None`。`layout.has_props` が True のときは、ドアが回る範囲・書棚 2 つ・観葉植物 2 つも `owner=None` で足す。
- 引数：
  - `layout`（`Layout`）：配置の定義
- 戻り値：`list[Obstacle]`。順番は 机 → 椅子 → 壁 →（office のみ）ドア・書棚・植木
- 例外：机の数と席の数が違えば `ValueError("机の数と席の数が一致しない")`
- 主な変数：
  - `obstacles` … 結果のリスト
  - `door_rect` … ドアが回る範囲（開いても閉じても障害物）。`DOOR_AREA_X` と `DOOR_Z ± DOOR_AREA_HALF_Z`

### `_rect_from_center(cx: float, cz: float, half_x: float, half_z: float) -> Rect`（718 行）
概要：中心 (cx, cz) から x・z それぞれ half_x・half_z の半分ずつ広げた長方形を返す。（`_build_obstacles` より後に定義されているが、呼び出しは実行時なので動く）
- 引数：
  - `cx`（`float`）・`cz`（`float`）：中心の x・z
  - `half_x`（`float`）・`half_z`（`float`）：x・z の半分の幅
- 戻り値：`Rect`
- 主な変数：なし

### `_build_circles(layout: Layout) -> list[tuple[float, float, float]]`（723 行）
概要：配置の丸い障害物（中心の x, z, 半径）の一覧を返す。丸いものは `has_props` の配置の丸テーブル（`TABLE_X`・`TABLE_Z`・`TABLE_RADIUS`）だけ。`has_props` が False なら空のリスト。
- 引数：
  - `layout`（`Layout`）：配置の定義
- 戻り値：`list[tuple[float, float, float]]`
- 主な変数：なし

### `_clamp(value: float, low: float, high: float) -> float`（743 行）
概要：値を low〜high の範囲に収める（`min(max(value, low), high)`）。
- 引数：
  - `value`（`float`）：収めたい値
  - `low`（`float`）：下限
  - `high`（`float`）：上限
- 戻り値：`float`。範囲に収めた値
- 主な変数：なし

### `push_out_of_rect(x: float, z: float, r: float, rect: Rect) -> tuple[float, float]`（748 行）
概要：半径 r の円（中心 (x, z)）が長方形に重なっていれば、重ならない位置まで最短の向きに押し出した (x, z) を返す。重なっていなければ元の (x, z) をそのまま返す。中心が長方形の中にあるときは、いちばん近い辺の外（辺から r の位置）へ押し出す。
- 引数：
  - `x`（`float`）・`z`（`float`）：円の中心
  - `r`（`float`）：円の半径
  - `rect`（`Rect`）：長方形
- 戻り値：`tuple[float, float]`。押し出したあとの (x, z)
- 主な変数：
  - `cx`・`cz` … 長方形の中で円の中心にいちばん近い点
  - `dist_sq` … その点から円の中心までの距離の 2 乗（`r*r` 以上なら重なっていない）
  - `left`・`right`・`down`・`up` … 中心が中にあるとき、各辺までの距離。最小の辺から出す

### `push_out_of_circle(x: float, z: float, r: float, cx: float, cz: float, cr: float) -> tuple[float, float]`（783 行）
概要：半径 r の円（中心 (x, z)）が、中心 (cx, cz)・半径 cr の円に重なっていれば、中心の距離が r+cr になる位置まで外へ押し出した (x, z) を返す。重なっていなければ元の (x, z)。中心が完全に同じときは +X へ押し出す。
- 引数：
  - `x`（`float`）・`z`（`float`）：動く円の中心
  - `r`（`float`）：動く円の半径
  - `cx`（`float`）・`cz`（`float`）：固定の円の中心
  - `cr`（`float`）：固定の円の半径
- 戻り値：`tuple[float, float]`。押し出したあとの (x, z)
- 主な変数：`limit` … `r + cr`。中心の距離がこれ以上なら重なっていない

### `_as_finite_float(value: object) -> float | None`（802 行）
概要：bool を除く数なら有限の float にして返す。数でない・NaN（数でない値）・無限大・大きすぎて float にできない値は None。
- 引数：
  - `value`（`object`）：調べたい値
- 戻り値：`float | None`。変換できた有限の数、できなければ None
- 主な変数：`number` … `float(value)` の結果（`OverflowError` のときは None を返す）

### `load_rate_settings(config_path: Path) -> tuple[str, float]`（813 行）
概要：設定ファイル（TOML）の `[rate_limits]` 節から (json_path, reload_sec) を読む。ファイルが無い・壊れている（`OSError`・`ValueError`）・節や項目が無い・型が違うときは、それぞれ既定値（`DEFAULT_RATE_JSON_PATH`・`DEFAULT_RELOAD_SEC`）を使う。`reload_sec` は 0 より大きい有限の数のときだけ採用する。
- 引数：
  - `config_path`（`Path`）：設定ファイルの場所
- 戻り値：`tuple[str, float]`。(利用制限 JSON の場所, 読み直す間隔〔秒〕)
- 主な変数：
  - `json_path`・`reload_sec` … 結果（最初は既定値）
  - `section` … TOML の `rate_limits` 節（辞書でなければ既定値を返す）

### `_parse_usage(lines: list[str]) -> tuple[float | None, float | None, str | None, str | None]`（834 行）
概要：`/usage` の画面の行から、5 時間と週間の使った割合（%）と、その次の「Resets」の行を取る。見出し（`Current session`・`Current week`）の次の行から探し、次の見出し（`Current ` を含む行）の前までに限る。見つからないものは None。割合は `USAGE_PCT_RE`（「NN% used」）で取り、割合が見つかったあとの最初の「Resets」を含む行を前後の空白を除いて返す。
- 引数：
  - `lines`（`list[str]`）：画面の行
- 戻り値：`tuple[float | None, float | None, str | None, str | None]` ＝ (5 時間の %, 週間の %, 5 時間の Resets の行, 週間の Resets の行)
- 主な変数：
  - `results` … 見出しごとの (割合, Resets の行) を入れるリスト（2 件）
  - `start` … 見出しのある行の番号（無ければ None）
  - `pct`・`reset` … 見出しごとの割合と Resets の行

### `_read_used_percentage(data: object, key: str) -> float`（860 行）
概要：`data[key]["used_percentage"]` を 0〜100 に収めた値で返す。`data` が辞書でない・項目が無い・辞書でない・数でないときは 0.0。
- 引数：
  - `data`（`object`）：読み込んだ JSON（辞書のはず）
  - `key`（`str`）：第 1 階層のキー
- 戻り値：`float`。0.0〜100.0
- 主な変数：`item` … `data[key]`、`number` … 有限の float にした値

### `separate(ax: float, az: float, bx: float, bz: float, r: float, a_fixed: bool, b_fixed: bool) -> tuple[float, float, float, float]`（873 行）
概要：半径とも r の 2 つの円が重なっていたら引き離し、(ax, az, bx, bz) を返す。両方動けるなら半分ずつ動かす。片方が固定なら、もう片方だけ全部動かす。両方固定なら動かさない。中心が完全に同じなら x 方向に引き離す。
- 引数：
  - `ax`（`float`）・`az`（`float`）：A の中心
  - `bx`（`float`）・`bz`（`float`）：B の中心
  - `r`（`float`）：2 つとも同じ半径
  - `a_fixed`（`bool`）：A が固定（動かせない）か
  - `b_fixed`（`bool`）：B が固定か
- 戻り値：`tuple[float, float, float, float]`。引き離したあとの (ax, az, bx, bz)
- 主な変数：
  - `overlap` … 重なりの深さ（`2r - 距離`）。0 以下なら何もしない
  - `nx`・`nz` … A から B への向きの単位ベクトル（同じ点なら (1, 0)）
  - `half` … 両方動けるときの片方分（重なりの半分）

### `_view_dir(yaw: float, pitch: float) -> Vec3`（912 行）
概要：カメラの目の方向の単位ベクトルを返す。yaw は Y 軸まわりの向き（度）、pitch は水平からの見下ろし角（度、90 で真上）。yaw=0 のとき +Z 側から見る（目は +Z 側にある）。
- 引数：
  - `yaw`（`float`）：向き（度）
  - `pitch`（`float`）：見下ろす角度（度）
- 戻り値：`Vec3`。(cos(pitch)·sin(yaw), sin(pitch), cos(pitch)·cos(yaw))
- 主な変数：`yaw_rad`・`pitch_rad` … ラジアンに直した角度

### `facing_yaw(fx: float, fz: float, tx: float, tz: float, default: float = 0.0) -> float`（926 行）
概要：(fx, fz) から (tx, tz) の方を向くときの yaw（度）を返す。`_step_toward` と同じ式 `atan2(-dx, -dz)` を使う。同じ点なら default を返す。
- 引数：
  - `fx`（`float`）・`fz`（`float`）：今いる位置
  - `tx`（`float`）・`tz`（`float`）：向きたい先
  - `default`（`float`）：同じ点のときに返す値。既定 0.0
- 戻り値：`float`。yaw（度）
- 主な変数：`dx`・`dz` … 向きたい先との差

### `stand_pose() -> Pose`（1352 行）
概要：立っている姿勢を返す。肘だけ 5 度曲げ、あとは 0。範囲に収めて返す。
- 引数：なし
- 戻り値：`Pose`
- 主な変数：なし

### `walk_pose(phase: float) -> Pose`（1368 行）
概要：歩いている姿勢を返す。左右の脚と腕は逆に振れる。肩は ±20·sin、足の付け根は ±25·sin、肘は両方 15 度、膝は後ろへ下がる脚だけ 30·max(0, ±sin) 曲げる。
- 引数：
  - `phase`（`float`）：歩行の位相（ラジアン）
- 戻り値：`Pose`
- 主な変数：`s` … `sin(phase)`（左右の振りの大きさ）

### `sit_pose(t: float) -> Pose`（1385 行）
概要：座って作業している姿勢を返す。肩 80 度で腕を机の縁まで届かせ、肘は 15±5 度（左右で逆向き）で、キーボードを打つ動きを付ける。足の付け根と膝は 90 度（太ももは水平、すねは垂直）。体は `SIT_BODY_Y`・`SIT_BODY_Z` ぶんずらす。
- 引数：
  - `t`（`float`）：席に着いてからの秒数
- 戻り値：`Pose`
- 主な変数：`wave` … 5·sin(2π·t / `TYPING_PERIOD_SEC`)。肘の曲げに足し引きする

### `drink_pose() -> Pose`（1403 行）
概要：飲む姿勢を返す。立ち姿勢の右肩を 40 度、右肘を 120 度にする（左は立ち姿勢のまま）。
- 引数：なし
- 戻り値：`Pose`
- 主な変数：`pose` … 立ち姿勢を元に右腕だけ変えたもの

### `shelf_pose() -> Pose`（1411 行）
概要：本を取る姿勢を返す。立ち姿勢の右肩を 110 度、右肘を 10 度にして手を伸ばす。
- 引数：なし
- 戻り値：`Pose`
- 主な変数：`pose` … 立ち姿勢を元に右腕だけ変えたもの

### `plant_pose() -> Pose`（1419 行）
概要：かがむ姿勢を返す。足の付け根 40 度・膝 80 度を左右とも、肩 20 度。足の裏が床に付くよう、太ももとすねの高さの分だけ `body_y` を下げる（`THIGH_LEN·cos(hip) + SHIN_LEN·cos(hip - knee) - (THIGH_LEN + SHIN_LEN)`）。
- 引数：なし
- 戻り値：`Pose`
- 主な変数：`hip`・`knee` … かがむときの角度（40・80）

### `spot_pose(kind: str) -> Pose`（1438 行）
概要：行き先に 1 人でいるときの姿勢を返す。コーヒーは `drink_pose`、書棚は `shelf_pose`、それ以外（植木）は `plant_pose`。
- 引数：
  - `kind`（`str`）：行き先の種類（`KIND_COFFEE`・`KIND_SHELF`・`KIND_PLANT`）
- 戻り値：`Pose`
- 主な変数：なし

### `gesture_pose(kind: str) -> Pose`（1447 行）
概要：話し手の身ぶりの姿勢を返す。`GESTURE_BOTH_UP` は両肩 150 度・両肘 20 度、`GESTURE_POINT_LISTENER` は右肩 80 度・右肘 10 度、それ以外（`GESTURE_POINT_DESK`）は右肩 95 度・右肘 0 度。
- 引数：
  - `kind`（`str`）：身ぶりの種類（`GESTURE_*`）
- 戻り値：`Pose`
- 主な変数：`pose` … 立ち姿勢を元に腕だけ変えたもの

---

## クラス

### クラス `Layout`（503〜519 行。`@dataclass(frozen=True)`）
概要：配置の定義。床・壁・机・席・うろつきの範囲・カメラをまとめる。frozen（作ったあとは変更できない）の dataclass（属性を書くだけで `__init__` などが自動で作られるクラス）。メソッドは無い。`PROTO_LAYOUT` と `OFFICE_LAYOUT` がこの型のインスタンス。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `floor_center` | `Vec3` | 床の中心 |
| `floor_size` | `Vec3` | 床の大きさ |
| `desks` | `tuple[Vec3, ...]` | 机の中心の一覧 |
| `walls` | `tuple[tuple[Vec3, Vec3, int], ...]` | 壁の (中心, 大きさ, 色) |
| `seats` | `tuple[tuple[Vec3, float, int], ...]` | 席の (位置, 座ったときの yaw, キャラの色) |
| `wander_x` | `tuple[float, float]` | うろつきの x の範囲 |
| `wander_z` | `tuple[float, float]` | うろつきの z の範囲 |
| `camera_eye` | `Vec3` | カメラの目の位置 |
| `camera_target` | `Vec3` | カメラが見る点 |
| `zoom_min` | `float` | マウスホイールで寄れる最短のカメラ距離 |
| `zoom_max` | `float` | マウスホイールで引ける最長のカメラ距離 |
| `has_props` | `bool` | 壁・ドア・掲示板・小物・丸い障害物を置くか（office だけ True）。既定 False |

### クラス `Spot`（593〜603 行。`@dataclass(frozen=True)`）
概要：行き先 1 つ。`kind` は `KIND_COFFEE`・`KIND_SHELF`・`KIND_PLANT` のどれか。`center` は体を向ける先、`slots` は立つ場所 (x, z) の一覧で、上限人数は slots の数。メソッドは無い。`_office_spots()` が 5 つ作る。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `name` | `str` | 行き先の名前（`coffee`・`shelf_l`・`shelf_r`・`plant_l`・`plant_r`）。`SpotManager` の予約の鍵に使う |
| `kind` | `str` | 行き先の種類 |
| `center` | `tuple[float, float]` | 体を向ける先の (x, z) |
| `slots` | `tuple[tuple[float, float], ...]` | 立つ場所の (x, z) の一覧 |

#### `_office_spots() -> tuple[Spot, ...]`（606 行）
（モジュールの関数。クラスの直後にあるので、ここに書く）
概要：office の行き先の一覧を作る。コーヒー 1 つ、書棚 2 つ、植木 2 つ。コーヒーの立つ場所は `SPOT_COFFEE_CENTER` を中心に、半径 `SPOT_COFFEE_RADIUS`・角度 `SPOT_COFFEE_ANGLES`（度）の円の上に並べる。
- 引数：なし
- 戻り値：`tuple[Spot, ...]`（5 つ。この順：coffee・shelf_l・shelf_r・plant_l・plant_r）
- 主な変数：`coffee_slots` … 円の上に並べた 6 か所の (x, z)

### クラス `Rect`（627〜634 行。`@dataclass(frozen=True)`）
概要：床を上から見た、軸にそった長方形（x と z の範囲）。メソッドは無い。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `xmin` | `float` | x の下限 |
| `xmax` | `float` | x の上限 |
| `zmin` | `float` | z の下限 |
| `zmax` | `float` | z の上限 |

### クラス `Obstacle`（637〜642 行。`@dataclass(frozen=True)`）
概要：障害物 1 つ。`owner` は席の番号（机と椅子は席 i の持ち物）。壁などは None。メソッドは無い。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `rect` | `Rect` | 障害物の長方形 |
| `owner` | `int または None` | 持ち主の席の番号（壁・ドア・書棚・植木は None）。持ち主の扱いはこの範囲のコードからは読み取れない（`App` 側で使う） |

### クラス `NavGrid`（935 行）
概要：床を `NAV_CELL`（20 単位）のマス目に分け、障害物を避ける道を A* で探す。作るのは App の初期化で 1 回だけ。マスの中心が、障害物を `AGENT_RADIUS + NAV_MARGIN` だけ広げた範囲に入るマスは通れない。マスの番号は `j * nx + i`（j は z の列、i は x の列）。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `x0` | `float` | 床の x の下限（マス (0, ·) の左端） |
| `z0` | `float` | 床の z の下限 |
| `nx` | `int` | x 方向のマスの数（`ceil(幅 / NAV_CELL)`、最低 1） |
| `nz` | `int` | z 方向のマスの数 |
| `_tmp_people` | `Sequence[tuple[float, float]]` | `find_path` の探している間だけ、よける人の中心の列。普段は空 |
| `_boxes` | `list[tuple[float, float, float, float]]` | 人の半径と余白ぶん広げた長方形の障害物 (xmin, xmax, zmin, zmax)。点がこの中に入ると人の中心を置けない |
| `_round` | `list[tuple[float, float, float]]` | 同じく広げた丸い障害物 (cx, cz, 半径+余白) |
| `_bucket_boxes` | `list[tuple[tuple[float, float, float, float], ...]]` | マスごとに、そのマスに重なる長方形の障害物を覚えた表（判定を速くするため）。空のマスは空のタプルを共有してメモリを節約 |
| `_bucket_round` | `list[tuple[tuple[float, float, float], ...]]` | 同じく丸い障害物の表 |
| `_free_cells` | `bytearray` | 通れるマスの表。1 が通れる、0 が通れない（マスの中心が置けるかで決める） |

#### `__init__(self, x_range: tuple[float, float], z_range: tuple[float, float], rects: list[Rect], circles: list[tuple[float, float, float]]) -> None`（941 行）
概要：床の範囲（x・z）と障害物（長方形・丸）から、通れるマスの表を作る。まず障害物を広げ、マスごとの障害物の表（バケット）を作り、全マスの中心について `_point_free` で通れるかを `_free_cells` に入れる。
- 引数：
  - `x_range`（`tuple[float, float]`）：床の x の範囲（下限, 上限）
  - `z_range`（`tuple[float, float]`）：床の z の範囲
  - `rects`（`list[Rect]`）：長方形の障害物
  - `circles`（`list[tuple[float, float, float]]`）：丸い障害物（中心の x, z, 半径）
- 戻り値：なし
- 主な変数：
  - `margin` … `AGENT_RADIUS + NAV_MARGIN`。障害物を広げる量
  - `boxes_in`・`round_in` … マスごとの障害物のリスト（あとでタプルにして `_bucket_*` に入れる）
  - `size` … マスの総数 `nx * nz`

#### `find_path(self, start_xz: tuple[float, float], goal_xz: tuple[float, float], people: Sequence[tuple[float, float]] = ()) -> list[tuple[float, float]] | None`（994 行）
概要：start から goal までの道の点の列を返す。道が無ければ None。スタートかゴールのマスが通れないときは、いちばん近い通れるマスを使う。点の列は、まっすぐ行ける先の点まで飛ばしたもの。最後の点は goal そのもの（直線で行けないときは最後のマスの中心を残してその後ろに goal を足す。それも行けないときは最後の点をゴールのマスの中心にする）。`people` をよけて道が見つからなければ、people なしでもう一度探す。
- 引数：
  - `start_xz`（`tuple[float, float]`）：出発点 (x, z)
  - `goal_xz`（`tuple[float, float]`）：目的地 (x, z)
  - `people`（`Sequence[tuple[float, float]]`）：よけるほかの人の中心の列。人の中心から `NAV_PERSON_RADIUS` 未満のマスと直線は通らない。既定 `()`
- 戻り値：`list[tuple[float, float]] | None`。道の点の列、無ければ None
- 主な変数：なし（`_find_path_avoiding` を 1 回か 2 回呼ぶ）

#### `_find_path_avoiding(self, start_xz: tuple[float, float], goal_xz: tuple[float, float], people: Sequence[tuple[float, float]]) -> list[tuple[float, float]] | None`（1015 行）
概要：`find_path` の本体。探している間だけ `self._tmp_people` に people を入れ、戻るときは（`finally` で）必ず空に戻す。スタートとゴールを通れるマスに寄せ、同じマスなら 1 点だけ返す。それ以外は人の周りのマスを塞いで A* で探し、`_simplify` で点を減らす。最後の点の扱いは `find_path` の説明のとおり。
- 引数：`find_path` と同じ。ただし `people` に既定値は無い
- 戻り値：`list[tuple[float, float]] | None`
- 主な変数：
  - `start_cell`・`goal_cell` … 通れるマスに寄せたスタートとゴールのマス（見つからなければ None を返す）
  - `blocked` … 人の周りで通れないマスの番号の集まり
  - `cells` … A* が返したマスの列
  - `points` … 道の点の列（最後の点を goal に差し替える）

#### `_blocked_by_people(self, people: Sequence[tuple[float, float]], start_cell: tuple[int, int], goal_cell: tuple[int, int]) -> set[int]`（1047 行）
概要：ほかの人の周りのマスのうち、中心が人の中心から `NAV_PERSON_RADIUS` 未満のマスの番号（`j * nx + i`）の集まりを返す。人ごとに周りのマスだけを調べる。`start_cell` と `goal_cell` は除く。
- 引数：
  - `people`（`Sequence[tuple[float, float]]`）：人の中心の列
  - `start_cell`（`tuple[int, int]`）：出発のマス (i, j)
  - `goal_cell`（`tuple[int, int]`）：目的のマス (i, j)
- 戻り値：`set[int]`。通れないマスの番号
- 主な変数：`r` … `NAV_PERSON_RADIUS`、`blocked` … 結果の集まり

#### `_cell_of(self, x: float, z: float) -> tuple[int, int]`（1071 行）
概要：点 (x, z) を含むマスの (i, j) を返す。床の外は一番近いマスにする。
- 引数：
  - `x`（`float`）・`z`（`float`）：点
- 戻り値：`tuple[int, int]`。マスの (i, j)
- 主な変数：`i`・`j` … 床の下限からの距離を `NAV_CELL` で割った値（0〜nx-1、0〜nz-1 に収める）

#### `_free(self, i: int, j: int) -> bool`（1077 行）
概要：マス (i, j) が通れるかを `_free_cells` で答える。
- 引数：
  - `i`（`int`）：x 方向のマス番号
  - `j`（`int`）：z 方向のマス番号
- 戻り値：`bool`。通れるなら True
- 主な変数：なし

#### `_point_free(self, x: float, z: float) -> bool`（1081 行）
概要：人の中心を点 (x, z) に置けるか（障害物を人の半径と余白ぶん広げた範囲の外か）を調べる。点を含むマスに登録された障害物（長方形・丸）だけを調べる。結果は全部の障害物を調べるのと同じ。
- 引数：
  - `x`（`float`）・`z`（`float`）：点
- 戻り値：`bool`。置けるなら True
- 主な変数：`i`・`j` … 点を含むマス

#### `_centre(self, i: int, j: int) -> tuple[float, float]`（1095 行）
概要：マス (i, j) の中心の (x, z) を返す。
- 引数：
  - `i`（`int`）・`j`（`int`）：マスの番号
- 戻り値：`tuple[float, float]`。`(x0 + (i+0.5)·NAV_CELL, z0 + (j+0.5)·NAV_CELL)`
- 主な変数：なし

#### `_nearest_free(self, i: int, j: int) -> tuple[int, int] | None`（1099 行）
概要：マス (i, j) が通れればそれを返す。通れなければ幅優先探索（近い順に広げて探す方法）で、近い通れるマスを探す。8 方向に広げ、無ければ None。
- 引数：
  - `i`（`int`）・`j`（`int`）：マスの番号
- 戻り値：`tuple[int, int] | None`。通れるマスの (i, j)、無ければ None
- 主な変数：`seen` … 見たマスの集まり、`queue` … 待ち行列（`deque`）

#### `_octile(a: tuple[int, int], b: tuple[int, int]) -> float`（1118 行。`@staticmethod`）
概要：マス a から b までの推定距離を返す。8 方向で動くときの最短に近い値で、A* の評価（ヒューリスティック）に使う。式は `max(dx, dy) + (√2 - 1)·min(dx, dy)`。
- 引数：
  - `a`（`tuple[int, int]`）・`b`（`tuple[int, int]`）：マスの (i, j)
- 戻り値：`float`。推定距離（マスの単位）
- 主な変数：`dx`・`dy` … マスの差の絶対値

#### `_astar(self, start: tuple[int, int], goal: tuple[int, int], blocked: set[int] | frozenset[int] = frozenset()) -> list[tuple[int, int]] | None`（1124 行）
概要：通れるマスのうち blocked に入っていないマスだけを使って、start から goal までのマスの列を A* で探す。8 方向で、斜めは縦と横の 2 マスが通れて blocked でもないときだけ進める（角をすり抜けない）。見つからなければ None。内側の繰り返しは速さのため、`_octile` と同じ式を分岐で展開している。
- 引数：
  - `start`（`tuple[int, int]`）：出発のマス
  - `goal`（`tuple[int, int]`）：目的のマス
  - `blocked`（`set[int] | frozenset[int]`）：使えないマスの番号。既定は空
- 戻り値：`list[tuple[int, int]] | None`。start から goal までのマスの列（両端を含む）
- 主な変数：
  - `best` … マスの番号ごとの、ここまでの最小の距離
  - `came` … マスの番号ごとの、手前のマスの番号（-1 は無し）
  - `heap` … (評価値, ここまでの距離, マスの番号) のヒープ
  - `found` … goal に着いたか

#### `_simplify(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]`（1189 行）
概要：まっすぐ行ける一番遠い点まで飛ばして、点の数を減らす。先頭と末尾は必ず残す。遠い側から調べる（近い側から 1 つずつより直線の判定が少なくて済む）。どの区間も `_clear` で確かめる。点が 3 つ未満ならそのままコピーを返す。
- 引数：
  - `points`（`list[tuple[float, float]]`）：道の点の列
- 戻り値：`list[tuple[float, float]]`。減らした点の列
- 主な変数：`out` … 結果、`cur` … 今の点の番号、`nxt` … 次に進む点の番号（まっすぐ行ける点が無ければ次の点）

#### `_clear(self, p: tuple[float, float], q: tuple[float, float]) -> bool`（1210 行）
概要：点 p から q までの直線を、人の中心が置けない場所とほかの人の周り（`self._tmp_people`）を通らずに行けるかを調べる。`NAV_CELL / 4` ごとの点で調べる。`_point_free` と同じ判定を、呼び出しを減らして速くするため展開している。
- 引数：
  - `p`（`tuple[float, float]`）・`q`（`tuple[float, float]`）：直線の両端
- 戻り値：`bool`。行けるなら True
- 主な変数：
  - `steps` … 調べる点の数（長さ ÷ `NAV_CELL/4` の切り上げ、最低 1）
  - `people` … `self._tmp_people`（`find_path` の外では空）

### クラス `SpotManager`（1241 行）
概要：行き先の予約を管理する。1 つの立つ場所には 1 人だけ。`GOING`・`AT_SPOT` の人が予約を持ち、`RETURNING` で外す。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `spots` | `tuple[Spot, ...]` | 行き先の一覧 |
| `rng` | `random.Random` | 乱数生成器（App の rng を渡す） |
| `_holder` | `dict[tuple[str, int], int]` | (行き先の名前, 立つ場所の番号) → 予約した人の番号 |
| `_reserved` | `dict[int, tuple[Spot, int]]` | 人の番号 → (行き先, 立つ場所の番号) |

#### `__init__(self, spots: tuple[Spot, ...], rng: random.Random) -> None`（1244 行）
概要：行き先の一覧と乱数生成器を受け取り、予約の無い状態で始める。
- 引数：
  - `spots`（`tuple[Spot, ...]`）：行き先の一覧
  - `rng`（`random.Random`）：乱数生成器
- 戻り値：なし
- 主な変数：`_holder`・`_reserved` … 最初は空の辞書

#### `count(self, spot: Spot) -> int`（1251 行）
概要：行き先 spot の予約数（使われている立つ場所の数）を返す。
- 引数：
  - `spot`（`Spot`）：行き先
- 戻り値：`int`。立つ場所の総数 − 空いている数
- 主な変数：なし

#### `_free_slots(self, spot: Spot) -> list[int]`（1255 行）
概要：行き先 spot の空いている立つ場所の番号の一覧を返す。
- 引数：
  - `spot`（`Spot`）：行き先
- 戻り値：`list[int]`。`_holder` に無い立つ場所の番号
- 主な変数：なし

#### `reserve(self, agent_index: int) -> tuple[Spot, int] | None`（1259 行）
概要：空いている行き先の立つ場所を 1 つ予約して (行き先, 立つ場所の番号) を返す。空きが無ければ None。くじの重みは coffee 50、書棚 2 つ合わせて 25、植木 2 つ合わせて 25。空きの無い行き先は外し、書棚・植木の重みは空いているものの数で割る。残りの中から重みで 1 つ選び、その中の空いている立つ場所から 1 つを乱数で選ぶ。
- 引数：
  - `agent_index`（`int`）：予約する人の番号
- 戻り値：`tuple[Spot, int] | None`。予約した (行き先, 立つ場所の番号)、空きが無ければ None
- 例外：同じ人の二重予約は `ValueError`
- 主な変数：
  - `free_shelves`・`free_plants` … 空きのある書棚・植木の数（重みを割る数）
  - `candidates` … (行き先, 重み) のリスト
  - `pick` … 0〜重みの合計の乱数。重みを足していって超えたところの行き先を選ぶ（丸め誤差の保険に最後の候補が初期値）
  - `slot` … 選んだ立つ場所の番号

#### `release(self, agent_index: int) -> None`（1295 行）
概要：人の予約を外す。予約が無ければ何もしない。
- 引数：
  - `agent_index`（`int`）：人の番号
- 戻り値：なし
- 主な変数：`entry` … `_reserved` から取り出した (行き先, 立つ場所の番号)

### クラス `Chatter`（1304〜1311 行。`@dataclass`）
概要：行き先で会話中の 1 人の状態。話し手なら身ぶり、聞き手なら飲む・立つの切り替えに使う。メソッドは無い。この範囲のコードでは使われていない（使う側は 1979 行以降）。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `gesture` | `str` | 話し手の身ぶり（話し手のときだけ。空なら未選択）。既定 `""` |
| `gesture_listener` | `int` | 身ぶりの相手の番号（-1 なら未選択）。既定 -1 |
| `gesture_timer` | `float` | 身ぶりを選び直すまでの残り時間（秒）。既定 0.0 |
| `listen_timer` | `float` | 聞き手の姿勢を選び直すまでの残り時間（秒）。既定 0.0 |
| `listen_drink` | `bool` | 聞き手が今「飲む姿勢」か。既定 False |

### クラス `Pose`（1315〜1349 行。`@dataclass`）
概要：人型の関節の角度（度）と、体全体のずらしをまとめる。肩は正で腕を前へ振る。肘は曲げる量で、前腕が前（-Z 側）へ曲がる。足の付け根は正で脚を前へ振る。膝は曲げる量で、すねが後ろ（+Z 側）へ曲がる。左は -X 側、右は +X 側（キャラの正面は -Z）。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `shoulder_l`・`shoulder_r` | `float` | 左・右の肩の角度（度） |
| `elbow_l`・`elbow_r` | `float` | 左・右の肘の曲げる量（度） |
| `hip_l`・`hip_r` | `float` | 左・右の足の付け根の角度（度） |
| `knee_l`・`knee_r` | `float` | 左・右の膝の曲げる量（度） |
| `body_y` | `float` | 体全体の上下のずらし（立っているとき 0） |
| `body_z` | `float` | 体全体の前後のずらし。キャラの向きに対して（負＝前＝-Z 側）。既定 0.0 |
| `head_yaw` | `float` | 頭だけの Y 軸まわりの回転（度）。正の向きは `Mat4.from_axis_angle(Vec3.UP, 角度)` と同じ。既定 0.0 |

#### `clamped(self) -> "Pose"`（1335 行）
概要：各角度を関節の範囲内（`SHOULDER_RANGE`・`ELBOW_RANGE`・`HIP_RANGE`・`KNEE_RANGE`）に収めた新しい `Pose` を返す。`body_y`・`body_z`・`head_yaw` はそのまま引き継ぐ。
- 引数：なし（self 以外）
- 戻り値：`Pose`。範囲に収めた新しいインスタンス
- 主な変数：なし

### クラス `Agent`（1464 行）
概要：キャラ 1 人の行動ロジック。描画はしない。状態は `WANDER`（待機）と `WORKING`（作業中）に加え、office だけの `GOING`（行き先へ向かう）・`AT_SPOT`（行き先にいる）・`RETURNING`（席へ戻る）、`--claude` のときの `LEAVING`（部屋を出る）。行き先の予約と会話の判断は App が行う。位置 `pos` は床の上（y=0）に置き、姿勢は `pose` で別に持つ（体の上下のずらしは `pose.body_y`）。

#### 主な属性（`__init__` で作る）
| 属性 | 型 | 用途 |
|---|---|---|
| `name` | `str`（注釈なし） | キャラの名前 |
| `seat` | `Vec3`（注釈なし） | 席の位置 |
| `rng` | `random.Random`（注釈なし） | 乱数生成器 |
| `seat_yaw` | `float` | 席に着いたときの向き（度） |
| `wander_x`・`wander_z` | `tuple[float, float]` | うろつきの x・z の範囲 |
| `obstacles` | `tuple[Rect, ...]` | うろつきの目標が避ける障害物 |
| `circles` | `tuple[tuple[float, float, float], ...]` | うろつきの目標が避ける丸い障害物 |
| `intended_move` | `float` | このフレームで進もうとした距離（`_step_toward` が入れる。App の引っかかり判定に使う） |
| `state` | `str` | 今の状態（`WANDER` など）。最初は `WANDER` |
| `pos` | `Vec3` | 床の上の位置（y=0）。最初は席の位置 |
| `yaw` | `float` | Y 軸回転の角度（度）。0 のとき -Z（机の方向）を向く |
| `pose` | `Pose` | 今の姿勢（描画が読む） |
| `walk_phase` | `float` | 歩行の位相（ラジアン） |
| `_target` | `Vec3 または None` | 待機中の目標点 |
| `_wait` | `float` | 立ち止まる残り時間（秒） |
| `_seated_time` | `float` | 席に着いてからの経過時間（秒） |
| `_arrived` | `bool` | 作業中に席へ着いたか |
| `nav` | `NavGrid または None` | 道を探す地図（None なら道探しはしない） |
| `_on_path_request` | `Callable[[], None] または None` | 道の依頼先（App の列に並ぶ関数） |
| `path_wait` | `bool` | 道を探す順番待ち。True の間は立って待ち、歩かない |
| `spot` | `Spot または None` | 行き先（`GOING`・`AT_SPOT`・`RETURNING` のとき） |
| `slot_index` | `int` | 行き先で使う立つ場所の番号 |
| `wander_time` | `float` | うろついている時間（秒）。App が数える |
| `cooldown` | `float` | 席へ戻ったあとの休みの残り（秒）。App が減らす |
| `alone_time` | `float` | 行き先に 1 人でいる時間（秒）。App が数える |
| `talk_time` | `float` | 行き先で会話している時間（秒）。App が数える |
| `_path` | `list[Vec3]` | 道の点（先頭から順に進む） |
| `_goal` | `Vec3 または None` | 道の最後の目標（席・立つ場所・ドアの内側） |
| `avoid_near` | `bool` | 次に道を探すとき、近くの人もよけてほしい |
| `_sidestep_time` | `float` | 横へよけている残り時間（秒）。0 のときはよけていない |
| `_sidestep_dir` | `tuple[float, float]` | 横へよける向き（単位ベクトル） |
| `hold` | `bool` | 会話の相手になっている間 True（App が入れる）。作業中の 5 秒で立ち上がらない |
| `visible` | `bool` | False の人は、描かず・動かさず、部屋の外（`PARK_X`）に置く（`--claude`） |
| `busy` | `bool` | 作業中のまま（Claude Code が作業している間）。True の間は 5 秒で立ち上がらない |
| `role` | `str` | `"main"`・`"sub"`・`""` |
| `label` | `str` | 頭の上に出す名前の札（`--claude`） |
| `_busy_hold_time` | `float` | `busy` が False になってから座っている時間（秒） |

#### `__init__(self, name: str, seat: Vec3, rng: random.Random, seat_yaw: float = 0.0, wander_x: tuple[float, float] = (FLOOR_X_MIN, FLOOR_X_MAX), wander_z: tuple[float, float] = (WANDER_Z_MIN, FLOOR_Z_MAX), obstacles: tuple[Rect, ...] = (), circles: tuple[tuple[float, float, float], ...] = (), nav: NavGrid | None = None, on_path_request: Callable[[], None] | None = None) -> None`（1472 行）
概要：名前・席の位置・乱数生成器を受け取り、席に座った状態ではなく「席の位置に立った WANDER 状態」で初期化する（`state=WANDER`、`pos` は席の位置、`pose` は立ち姿勢。コードを読んで確かめた。docstring の「席に座った状態」とは表現が違う）。省略時は障害物なしで、既定値は proto の動きと同じ。
- 引数：
  - `name`（`str`）：名前
  - `seat`（`Vec3`）：席の位置
  - `rng`（`random.Random`）：乱数生成器
  - `seat_yaw`（`float`）：席に着いたときの向き（度）。既定 0.0
  - `wander_x`・`wander_z`（`tuple[float, float]`）：うろつく範囲。既定は proto の床の範囲
  - `obstacles`（`tuple[Rect, ...]`）：避ける長方形の障害物。既定は空
  - `circles`（`tuple[tuple[float, float, float], ...]`）：避ける丸い障害物。既定は空
  - `nav`（`NavGrid | None`）：道探しの地図。既定 None
  - `on_path_request`（`Callable[[], None] | None`）：道を探してほしいときに呼ぶ関数（App の列に並べる）。既定 None
- 戻り値：なし
- 主な変数：上の属性の表のとおり

#### `start_work(self) -> None`（1533 行）
概要：作業状態（`WORKING`）へ切り替える。席へ戻るところから始める。目標・待ち・行き先・道・よけの状態をすべて空にし、`_goal` を席の位置にする。道探しのある配置（`nav` あり）で席から `WORK_PATH_MIN_DIST` より遠ければ、`_ask_path` で道を探してもらう。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.state` を `WORKING` に／`self._goal` を席の位置に／`self._arrived`・`self._seated_time`・`self._busy_hold_time` を 0 や False に戻す

#### `is_seated(self) -> bool`（1554 行。`@property`）
概要：作業中で席に着いているかを返す。着いている間は他のキャラに押されない。
- 引数：なし
- 戻り値：`bool`。`state == WORKING` かつ `_arrived`
- 主な変数：なし

#### `is_fixed(self) -> bool`（1559 行。`@property`）
概要：他のキャラに押されないかを返す。席に着いている人と、行き先の立つ場所（`AT_SPOT`）にいる人。会話の相手（`hold` が True）も、作業中（`WORKING`）でなければ押されない。席へ歩いている途中の相手は今までどおり押される。
- 引数：なし
- 戻り値：`bool`。`is_seated or state == AT_SPOT or (hold and state != WORKING)`
- 主な変数：なし

#### `sidestepping(self) -> bool`（1566 行。`@property`）
概要：横へよけている最中かを返す。よけている間は道を使わず、決めた向きへ歩く。
- 引数：なし
- 戻り値：`bool`。`_sidestep_time > 0`
- 主な変数：なし

#### `begin_sidestep(self, ux: float, uz: float) -> None`（1570 行）
概要：向き (ux, uz) へ `SIDESTEP_SEC` 秒だけ横によける。今の道は捨てる。
- 引数：
  - `ux`（`float`）・`uz`（`float`）：よける向き（単位ベクトルのはず。コードでは正規化しない）
- 戻り値：なし
- 主な変数：`self._sidestep_time` … `SIDESTEP_SEC` にする／`self._sidestep_dir` … 向きを覚える／`self._path` … 空にする

#### `update(self, dt: float) -> None`（1576 行）
概要：dt 秒ぶん行動を進める。`intended_move` を 0 にしてから、①道の順番待ち（`path_wait`）なら立って何もしない、②横へよけている最中なら決めた向きへ歩き、時間が切れたら `avoid_near` を True にして道を探し直す（`request_replan`）、③それ以外は状態ごとに `_update_wander`・`_update_going`・`_update_returning`・`_update_working` を呼ぶ。`AT_SPOT` は何もしない（姿勢と向きは App が毎フレーム決める）。`LEAVING` は道をたどるだけ（着いたら App が置き場所に戻す）。
- 引数：
  - `dt`（`float`）：進める時間（秒）
- 戻り値：なし
- 主な変数：`self.intended_move`（0 に戻す）／`self.path_wait`／`self._sidestep_time`・`self._sidestep_dir`／`d` … よけで歩く距離（`WANDER_SPEED * dt`）

#### `leaving_done(self) -> bool`（1609 行。`@property`）
概要：部屋を出る道を歩き終えたかを返す。`LEAVING` でなければ False。道が空になったか、出口の点（`_goal`）から `LEAVE_ARRIVE_DIST` 以内に入ったとき True。
- 引数：なし
- 戻り値：`bool`
- 主な変数：`self._path`・`self._goal`

#### `begin_leaving(self, goal: Vec3) -> bool`（1619 行）
概要：goal（ドアの内側）へ部屋を出る道を探して `LEAVING` にする。順番待ちからは外れる（`path_wait=False`。待ち列から外すのは `_leave` の役目とコードのコメントにある）。道が無ければ False（その場合は App が置き場所に戻す）。
- 引数：
  - `goal`（`Vec3`）：ドアの内側の点
- 戻り値：`bool`。道が見つかれば True
- 主な変数：`self.state` を `LEAVING` に／`self._goal` を goal に／`self._path`（`_plan` が入れる。失敗時は空）

#### `park(self) -> None`（1635 行）
概要：見えていない人の置き場所（x=`PARK_X`、z=`DOOR_Z`）へ戻し、ふだんの状態（`WANDER`）にする。`visible`・`busy`・`hold` を False にし、道・予約（行き先）・時間（うろつき・休み・1 人・会話）は空にする。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.visible`（False）／`self.pos`（置き場所）／`self.state`（`WANDER`）

#### `_update_wander(self, dt: float) -> None`（1657 行）
概要：席の周りをうろつく。立ち止まっている間（`_wait > 0`）は立ち姿勢で待つ。目標が無ければ `_choose_target` で選ぶ（見つからなければ 1 秒待つ）。目標に着いたら `WAIT_MIN`〜`WAIT_MAX` 秒立ち止まって次の目標を選ぶ。
- 引数：
  - `dt`（`float`）：進める時間（秒）
- 戻り値：なし
- 主な変数：`self._wait`（立ち止まる残り時間）／`self._target`（今の目標。着いたら None）

#### `_update_working(self, dt: float) -> None`（1676 行）
概要：席へ戻り、着いたら席の向き（`seat_yaw`）を向いて座る。座ったらキーボードを打つ姿勢（`sit_pose`）にし、`busy` が False になってから `WORK_HOLD_SEC`（5 秒）たったら `_return_to_wander` で待機に戻る。会話の相手（`hold`）と `busy` の間は立ち上がらない。道が残っていれば道をたどり、無ければ席へまっすぐ進む。
- 引数：
  - `dt`（`float`）：進める時間（秒）
- 戻り値：なし
- 主な変数：`self._arrived`（席に着いたか）／`self._seated_time`（座ってからの秒数。キーを打つ動きに使う）／`self._busy_hold_time`（`busy` が False の間だけ増える）

#### `_return_to_wander(self) -> None`（1699 行）
概要：待機状態に戻し、目標をリセットして立ち上がる（立ち姿勢にし、うろつきの時間を 0 にする）。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.state`（`WANDER`）／`self._arrived`（False）／`self.wander_time`（0）

#### `begin_going(self, spot: Spot, slot_index: int) -> bool`（1711 行）
概要：行き先 spot の立つ場所 slot_index へ `GOING` にして、道を探してもらう。道は App の列の順番が来てから探す（その間は立って待つ）。道が見つからなければ WANDER に戻る。`nav` が無いときは False を返す。
- 引数：
  - `spot`（`Spot`）：行き先
  - `slot_index`（`int`）：立つ場所の番号
- 戻り値：`bool`。`GOING` のままなら True（依頼先が無い場合は道の結果で決まる）
- 主な変数：`self._goal` … 立つ場所の位置／`self.spot`・`self.slot_index` … 行き先を覚える／`self.alone_time`・`self.talk_time` … 0 に戻す

#### `begin_returning(self) -> bool`（1732 行）
概要：行き先から席へ戻る道を探してもらい、`RETURNING` にする。`nav` が無ければあきらめて WANDER に戻し（`give_up`）、False を返す。
- 引数：なし
- 戻り値：`bool`。`RETURNING` のままなら True
- 主な変数：`self._goal`（席の位置）／`self.spot`（None）

#### `request_replan(self) -> bool`（1744 行）
概要：引っかかったとき、今の位置から目標までの道を探し直してもらう（列に並ぶ）。目標が無ければ False。
- 引数：なし
- 戻り値：`bool`。依頼したら True
- 主な変数：`self._goal`

#### `_ask_path(self) -> None`（1751 行）
概要：道を探してほしいと頼む。`path_wait` を True にし、依頼先（`_on_path_request`、App の列）があれば並ぶだけで、探すのは順番が来てから。依頼先が無ければその場で `serve_path` し、失敗したら `path_failed` を呼ぶ。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.path_wait`（True）／`self._on_path_request`

#### `serve_path(self, people: Sequence[tuple[float, float]] = ()) -> bool`（1759 行）
概要：順番が来たので、今の位置から目標までの道を探す（App が呼ぶ）。`path_wait` を False に戻し、目標が無ければ False。
- 引数：
  - `people`（`Sequence[tuple[float, float]]`）：よけるほかの人の中心 (x, z) の列。既定は空（人をよけない）
- 戻り値：`bool`。道が見つかれば True
- 主な変数：`self.path_wait`（False に）／`self._goal`

#### `path_failed(self) -> bool`（1769 行）
概要：道が見つからなかったときの後始末。`WORKING` は道を空にして席へまっすぐ進む（今までどおり）で False を返す。それ以外（`GOING`・`RETURNING` など）はあきらめて WANDER に戻し（`give_up`）、True を返す（App が行き先の予約を外す）。
- 引数：なし
- 戻り値：`bool`。あきらめて WANDER に戻したら True
- 主な変数：`self._path`（`WORKING` のとき空に）／`self.state`

#### `give_up(self) -> None`（1780 行）
概要：行き先へ行けずにあきらめ、WANDER に戻す。`RETURNING` からなら休み `OUTING_COOLDOWN_SEC` をつけ、それ以外（`GOING` など）からなら休みは 0。
- 引数：なし
- 戻り値：なし
- 主な変数：なし（`_end_outing` を呼ぶ）

#### `reset_outing_timers(self) -> None`（1784 行）
概要：行き先のタイマー（うろつき・休み・1 人・会話）を 0 にする。スペースキーで作業に切り替えるときに使う。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.wander_time`・`self.cooldown`・`self.alone_time`・`self.talk_time`（すべて 0.0）

#### `_end_outing(self, cooldown: float) -> None`（1791 行）
概要：行き先の状態を終えて WANDER に戻す。行き先・道・目標・順番待ち・よけを空にし、うろつきの時間を 0 にして、休みを cooldown にし、立ち姿勢にする。
- 引数：
  - `cooldown`（`float`）：次に出かけるまでの休み（秒）
- 戻り値：なし
- 主な変数：`self.state`（`WANDER`）／`self.cooldown`（引数の値）／`self.wander_time`（0）

#### `_update_going(self, dt: float) -> None`（1807 行）
概要：行き先の立つ場所へ道を進む。道の最後まで着いたら `AT_SPOT` になり、立ち姿勢で行き先の中心（`spot.center`）を向く。
- 引数：
  - `dt`（`float`）：進める時間（秒）
- 戻り値：なし
- 主な変数：`self.state`（着いたら `AT_SPOT`）／`self.yaw`（`facing_yaw` で行き先の中心を向く）

#### `_update_returning(self, dt: float) -> None`（1817 行）
概要：席へ戻る道を進む。着いたら WANDER に戻り、休み `OUTING_COOLDOWN_SEC` をつける（`_end_outing`）。
- 引数：
  - `dt`（`float`）：進める時間（秒）
- 戻り値：なし
- 主な変数：なし

#### `_follow_path(self, distance: float) -> bool`（1822 行）
概要：道の点を順に、合計 distance だけ進む。先頭の点に着いたらその点を捨てる。`intended_move` には途中の点ごとに書き換わるので、最後に合計を入れ直す。
- 引数：
  - `distance`（`float`）：このフレームで進める距離
- 戻り値：`bool`。道の最後まで進み切ったら True（道が空のときも True）
- 主な変数：`remaining` … 残りの距離、`moved` … 進んだ合計、`self._path` … 先頭から消えていく

#### `_plan(self, goal: Vec3, people: Sequence[tuple[float, float]] = ()) -> bool`（1837 行）
概要：今の位置から goal までの道を `nav.find_path` で探す。見つかれば `_path`（道の点の `Vec3` の列）と `_goal` を入れて True。見つからなければ何も変えず False。`nav` が無ければ False。
- 引数：
  - `goal`（`Vec3`）：目的地
  - `people`（`Sequence[tuple[float, float]]`）：避ける人の中心の列。既定は空
- 戻り値：`bool`。道が見つかれば True
- 主な変数：`points` … `find_path` が返した (x, z) の列

#### `repick_target(self) -> None`（1848 行）
概要：引っかかったときに App が呼ぶ。待ち時間は 0 のまま、すぐ別の目標を選んで歩き出す。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._wait`（0）

#### `_choose_target(self) -> None`（1853 行）
概要：新しい目標を選ぶ。見つからなければ、目標なしで 1 秒立ち止まる（立ち姿勢）。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._target`（選んだ目標、無ければ None）／`self._wait`（見つからないとき 1.0）

#### `_pick_wander_target(self) -> Vec3 | None`（1863 行）
概要：席から半径 `WANDER_RADIUS` 以内のランダムな点を選び、うろつきの範囲に収める。障害物を `AGENT_RADIUS` だけ広げた範囲に入らない点を、最大 `TARGET_TRIES` 回まで探す。見つからなければ None。半径は `sqrt(乱数)` を掛けて、円の中で偏らないようにしている。
- 引数：なし
- 戻り値：`Vec3 | None`。目標の点（y=0）、無ければ None
- 主な変数：`angle`・`radius` … 席からの向きと距離

#### `_overlaps_obstacle(self, x: float, z: float) -> bool`（1877 行）
概要：点 (x, z) が、いずれかの障害物を `AGENT_RADIUS` だけ広げた範囲に入っていれば True。丸い障害物も同じ（半径に `AGENT_RADIUS` を足す）。
- 引数：
  - `x`（`float`）・`z`（`float`）：調べる点
- 戻り値：`bool`
- 主な変数：`self.obstacles`・`self.circles`

#### `_step_toward(self, target: Vec3, distance: float) -> bool`（1890 行）
概要：目標へ distance だけ進む。着いたら True。進んだ分だけ歩行の位相を進め、歩きの姿勢（`walk_pose`）にする。進むときは進行方向を向く（前方は -Z 基準で、Y 軸回転 θ の前方は (-sinθ, 0, -cosθ)）。目標に着いたときは yaw を変えない。
- 引数：
  - `target`（`Vec3`）：目標
  - `distance`（`float`）：進める距離
- 戻り値：`bool`。着いたら True
- 主な変数：
  - `self.intended_move` … 押し出し前に進もうとした距離（App の引っかかり判定に使う）
  - `self.walk_phase` … 進んだ距離 ÷ `STRIDE` × 2π だけ進む
  - `self.pos`・`self.yaw`・`self.pose`

### クラス `Human`（1917 行。`Agent` を継承）
概要：ユーザーの分身。クリックした場所へ道を探して歩く。行き先・作業・うろうろはしない。依頼先（列）は持たず（`on_path_request=None`）、道は `walk_to` で直接探す。独自の属性は無い（`Agent` の属性をそのまま使う）。

#### `__init__(self, seat: Vec3, rng: random.Random, wander_x: tuple[float, float], wander_z: tuple[float, float], obstacles: tuple[Rect, ...], circles: tuple[tuple[float, float, float], ...], nav: NavGrid | None, name: str = "YOU") -> None`（1920 行）
概要：最初の位置 seat に立たせる。道探しと障害物は App と同じものを使う。`Agent.__init__` を呼ぶだけ。
- 引数：
  - `seat`（`Vec3`）：最初の位置（`Agent` では席の位置として扱われる）
  - `rng`（`random.Random`）：乱数生成器
  - `wander_x`・`wander_z`（`tuple[float, float]`）：うろつきの範囲
  - `obstacles`（`tuple[Rect, ...]`）：障害物
  - `circles`（`tuple[tuple[float, float, float], ...]`）：丸い障害物
  - `nav`（`NavGrid | None`）：道探しの地図
  - `name`（`str`）：名前。既定 `"YOU"`
- 戻り値：なし
- 主な変数：なし

#### `walking(self) -> bool`（1945 行。`@property`）
概要：道を歩いている最中か（道の点が残っているか）を返す。
- 引数：なし
- 戻り値：`bool`。`len(_path) > 0`
- 主な変数：`self._path`

#### `update(self, dt: float) -> None`（1949 行。`Agent.update` を上書き）
概要：道があれば `HUMAN_SPEED` で進み、進み切ったら立ち姿勢にする。道がなければ立っている。うろつき・行き先・作業・順番待ち・横よけはしない。
- 引数：
  - `dt`（`float`）：進める時間（秒）
- 戻り値：なし
- 主な変数：`self.intended_move`（0 に戻す）／`self._path`

#### `walk_to(self, x: float, z: float, people: Sequence[tuple[float, float]]) -> bool`（1958 行）
概要：(x, z) へ道を探して歩く。見つかれば True。見つからなければ道を空にして False。先頭の点が後ろにあると、いったん戻ってから進んでしまう（逆走）ので、2 つ目の点へ直線で行けるなら先頭の点を捨てる（`nav._clear` で判定）。
- 引数：
  - `x`（`float`）・`z`（`float`）：目的地
  - `people`（`Sequence[tuple[float, float]]`）：避ける人の中心の列
- 戻り値：`bool`。道が見つかれば True
- 主な変数：`ok`（道が見つかったか）／`second`（道の 2 つ目の点）／`self._path`

#### `warp(self, x: float, z: float, yaw: float) -> None`（1971 行）
概要：(x, z) へ瞬間移動して、向き yaw で立つ。道は空にする。
- 引数：
  - `x`（`float`）・`z`（`float`）：移動先
  - `yaw`（`float`）：向き（度）
- 戻り値：なし
- 主な変数：`self.pos`・`self.yaw`・`self._path`・`self.pose`

## 描画・許可の受け取り・App の前半（1979〜3700 行）

注：`self.box`・`self.tri`・`self.sphere`・`self.elli`・`self.shaded` は Pyxel 3 の `Node`（3D の部品の親クラス）のメソッドで、本体ファイルの中には定義がない（コードからは読み取れない。使い方から、箱・三角形・球・楕円・陰影の切り替えと読める）。`Vec3`（3 つの数の組）・`Mat4`（4×4 の変換行列）も Pyxel 側の型。

### クラス `AgentView`（1979 行）
概要：`Node` を継承する。`Agent`（人間の `Human` も同じ）の位置・向き・姿勢を毎フレーム読み、人型（胴・頭・両腕・両脚）を箱で描く。描画だけを受け持ち、動きは `Agent` 側が決める。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `agent` | `Agent` | 描く対象。位置・向き・姿勢・見えているか（`visible`）を読む |
| `color` | `int` | 胴と両脚の色 |
| `skin_color` | `int` | 頭と両腕の色（既定は `SKIN_COLOR`） |
| `transform` | `Mat4` | `Node` の変換行列。`on_update` が毎フレーム書く（このクラスの `__init__` では作らず、親クラスのもの） |

#### `__init__(self, agent: Agent, color: int, skin_color: int = SKIN_COLOR) -> None`（1982 行）
概要：描画対象の Agent と、胴・脚の色、頭と腕の肌の色を受け取って保存する。
- 引数：
  - `agent`（`Agent`）：描く対象
  - `color`（`int`）：胴・脚の色
  - `skin_color`（`int`）：頭と腕の色。既定 `SKIN_COLOR`
- 戻り値：なし
- 主な変数：`self.agent`・`self.color`・`self.skin_color` に引数をそのまま入れる

#### `on_update(self) -> None`（1989 行）
概要：Agent の位置・姿勢の上下のずれ・向きを、変換行列 `self.transform` に反映する。順番は「位置へ平行移動 → 向きの回転 → 体の前後のずらし」で、体の前後のずらしはキャラの向きに対してかかる。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`position`（`Vec3`。x・z は Agent の位置、y は `pose.body_y`）／`pose.body_z`（体の前後のずらし）／`a.yaw`（向き。度）

#### `on_draw(self) -> None`（2000 行）
概要：頭と両腕は肌色、胴と両脚はキャラの色で箱を描く。腕と脚は肩・肘・股・膝の関節の角度（親の関節に対する相対）に合わせて `_limb` で描く。`agent.visible` が False なら何も描かない（`--claude` で見えていない人用）。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`p`（Agent の `pose`。関節角度と `head_yaw`）／`head`（頭の行列。頭だけ中心のまわりに `head_yaw` 度回す）／`x_sign`（左 -1.0・右 1.0）／`elbow_joint`・`knee_joint`（`_limb` が返した腕・脚の末端の行列。前腕・すねの根元になる）。前腕は角度を正に加え、すねは膝の角度を負にして描く

#### `_limb(self, joint: Mat4, angle: float, length: float, thickness: float, color: int) -> Mat4`（2031 行）
概要：関節 `joint` から X 軸まわりに `angle` 度（親に対する相対）回した棒を、色 `color` の箱で描く。棒は関節から下向き（-Y）に伸び、正の角度で前（-Z 側）へ振れる。末端の行列を返すので、次の関節（前腕・すね）の根元に使える。
- 引数：
  - `joint`（`Mat4`）：関節の位置・向きの行列
  - `angle`（`float`）：X 軸まわりの回転（度）
  - `length`（`float`）：棒の長さ
  - `thickness`（`float`）：棒の太さ（X・Z 方向の幅）
  - `color`（`int`）：箱の色
- 戻り値：`Mat4`。棒の末端（関節から `length` だけ下）の行列
- 主な変数：`bone`（関節を `angle` 度回した行列）

### クラス `MarkerView`（2052 行）
概要：`Node` を継承する。人間の頭の上に出す▼を描く。human の位置の真上で、`MARKER_BOB` の幅・`MARKER_BOB_SEC` の周期で上下に揺れる。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `human` | `Human` | ▼を出す対象の人間 |
| `_t0` | `float` | 作ったときの `time.perf_counter()` の値。揺れの経過時間の起点 |
| `transform` | `Mat4` | `Node` の変換行列。`on_update` が毎フレーム書く |

#### `__init__(self, human: Human) -> None`（2055 行）
概要：描く対象の人間を受け取り、揺れの起点の時刻を記録する。
- 引数：`human`（`Human`）：▼を出す対象
- 戻り値：なし
- 主な変数：`self.human`・`self._t0`

#### `on_update(self) -> None`（2061 行）
概要：人間の位置の真上（高さ `MARKER_Y`）へ、サイン波の揺れ（`bob`）の分だけずらした位置に置く。平行移動だけで、向きは変えない。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`elapsed`（起点からの経過秒）／`bob`（`MARKER_BOB * sin(2π × elapsed / MARKER_BOB_SEC)`。上下のずれ）／`pos`（人間の位置）

#### `on_draw(self) -> None`（2068 行）
概要：上面の正方形（三角形 2 枚）と、そこから下の頂点へ向かう 4 枚の三角形で、▼を `MARKER_COLOR` で描く。陰影はつけない（`self.shaded(False)`）。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`h`（`MARKER_HALF`。上面の半幅）／`c0`〜`c3`（上面の 4 つの角）／`tip`（下の頂点）

### クラス `OfficeRoot`（2084 行）
概要：`Node` を継承する。床・壁・机・椅子（配置が `has_props` のときはドア・掲示板・小物も）を描くルートの Node。キャラの描画は `AgentView` に任せる。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `layout` | `Layout` | 描く配置（床・壁・机・席の位置） |
| `five_hour` | `float` | 5 時間の利用制限（使った割合 0〜100）。App が毎フレーム書き込む |
| `seven_day` | `float` | 週間の利用制限（使った割合 0〜100）。App が毎フレーム書き込む |
| `door_angle` | `float` | ドアの開き角（度。0 で閉じ、正で部屋の中へ開く）。App が毎フレーム書き込む |

#### `__init__(self, layout: Layout) -> None`（2087 行）
概要：描く配置を受け取り、利用制限の値とドアの角度を 0 で始める。
- 引数：`layout`（`Layout`）：描く配置
- 戻り値：なし
- 主な変数：`self.layout`・`self.five_hour`・`self.seven_day`・`self.door_angle`

#### `on_draw(self) -> None`（2095 行）
概要：床・壁・机（天板と左右の側板）・椅子（座面と背もたれ）を描く。側板の間は空けて、座った人の脚が入るようにしている。椅子は全部の席に置く。`layout.has_props` が真なら、続けてドア・掲示板・小物を描く。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self.layout.floor_center`・`floor_size`（床）／`self.layout.walls`（壁の中心・大きさ・色）／`self.layout.desks`（机の中心）／`self.layout.seats`（席の位置・向き・色。椅子の向きに使う）

#### `_draw_door(self) -> None`（2141 行）
概要：REST ROOM のドアの板と、ドアの上の札（動かない）を描く。板は蝶番の位置から `door_angle` 度回した先に置き、正の角度で +X（部屋の中）へ開く。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`hinge`（蝶番の位置の行列。板の端）／`panel`（板の中心の行列。蝶番を `door_angle` 度回し、板の半分だけ離す）／`self.door_angle`

#### `_draw_board(self) -> None`（2157 行）
概要：奥の壁の白い板と、利用制限の 2 本の棒（5 時間は黄、週間は赤）を描く。それぞれ枠と棒を描く。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self.five_hour`・`self.seven_day`（棒の割合）／`FIVE_HOUR_BAR_Y`・`WEEK_BAR_Y`（棒の高さ）

#### `_draw_bar_frame(self, y: float) -> None`（2165 行）
概要：100% の長さの枠（細い黒い箱 4 本）を、棒の外側に描く。0% でも描く。枠は棒を隠さない。上下の箱は左右の箱の角まで覆う横幅にする。
- 引数：`y`（`float`）：枠の高さ（中心の Y）
- 戻り値：なし
- 主な変数：`w`（枠の太さ `BAR_FRAME_W`）／`half_len`（棒の最大長の半分）／`center_x`（枠の中心の X）

#### `_draw_bar(self, percent: float, y: float, color: int) -> None`（2185 行）
概要：左端 `BAR_LEFT_X` から、割合 `percent`（0〜100）に比例した長さの棒を描く。長さが 0 以下なら描かない。
- 引数：
  - `percent`（`float`）：使った割合（0〜100）
  - `y`（`float`）：棒の高さ
  - `color`（`int`）：棒の色
- 戻り値：なし
- 主な変数：`length`（`BAR_MAX_LEN * percent / 100`。棒の長さ）

#### `_draw_props(self) -> None`（2196 行）
概要：書棚（本の段つき）・観葉植物（鉢と葉の球）・丸テーブル（天板・脚・台座）・コーヒーメーカー（本体と赤いランプ）を描く。丸い板は `elli` で描き、X 軸まわりに -90 度回して上（+Y）向きにする。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`BOOKSHELF_XS`・`BOOK_YS`・`BOOK_COLORS`（書棚の位置と本の段）／`PLANT_POSITIONS`（植木の位置）／`table_top`・`base`（丸テーブルの天板・台座の行列）

### モジュールの関数

#### `_char_cols(ch: str) -> int`（2242 行）
概要：1 文字の桁数を返す。全角（東アジアの幅が W・F）は 2 桁、それ以外は 1 桁。
- 引数：`ch`（`str`）：1 文字
- 戻り値：`int`。2 または 1
- 主な変数：`unicodedata.east_asian_width(ch)`（文字の幅の種類）

#### `_wrap_text(text: str, cols: int) -> list[str]`（2247 行）
概要：`text` を桁数 `cols` で折り返した行の一覧を返す。空の文字列は `[""]` を返す。禁則処理（行頭・行末に置けない文字の扱い）は無い。
- 引数：
  - `text`（`str`）：折り返す文
  - `cols`（`int`）：1 行の桁数（全角は 2 桁と数える）
- 戻り値：`list[str]`。折り返した行
- 主な変数：`rows`（できた行）／`line`（作っている行）／`width`（作っている行の桁数）

#### `_recv_line(conn: socket.socket, timeout_sec: float) -> str`（2275 行）
概要：相手から 1 行（改行まで）読む。全体で `timeout_sec` 秒まで。時間切れは `TimeoutError`、相手が閉じたら `ConnectionError`、`PERM_MAX_LINE` を超えたら `ValueError` を出す。UTF-8 として復号して返す。
- 引数：
  - `conn`（`socket.socket`）：読む相手とのつながり
  - `timeout_sec`（`float`）：読み始めからの制限時間（秒）
- 戻り値：`str`。最初の改行の手前までの文字（改行は含まない）
- 主な変数：`deadline`（`time.monotonic()` で測った締め切り）／`buf`（受け取った分を貯める `bytearray`）

#### `_close_quietly(conn: socket.socket | None) -> None`（2293 行）
概要：つながりを閉じる。`None` のときや、閉じるときに `OSError` が出たときは何もしない。
- 引数：`conn`（`socket.socket | None`）：閉じるつながり
- 戻り値：なし

#### `_perm_suggestions(value: object) -> list[dict[str, object]]`（2422 行）
概要：許可の依頼の `permission_suggestions`（Claude Code の「いつも許可」の案）から、辞書だけを取り出す。list でなければ空の list を返す。
- 引数：`value`（`object`）：依頼の `permission_suggestions` の値
- 戻り値：`list[dict[str, object]]`。辞書の要素だけの list

#### `_suggestion_rows(s: list[dict[str, object]]) -> list[str]`（2429 行）
概要：Claude Code の案を、人の言葉の行の一覧にする（「いつも許可」の確かめの画面と履歴に出す）。案の `type` で言い方が変わる。`setMode`（`acceptEdits` は「ファイルの編集を聞かずに許す」、他は「許可のモードを …にする」。保存先が `session` 以外なら「（保存先：…）」を付ける）、`addRules`（「次の決まりを（保存先）に足す：道具名(内容)…」。`PERM_RULE_SCOPE` で保存先を言い換え、`behavior` が allow 以外なら先頭に `[behavior]` を付ける）、`addDirectories`（「次のフォルダを作業の範囲に足す：…」）。どれでもなければ `type: JSON` の形にする。
- 引数：`s`（`list[dict[str, object]]`）：案の辞書の list（`_perm_suggestions` の結果）
- 戻り値：`list[str]`。案 1 つにつき 1 行（案の数と同じ長さ）
- 主な変数：`kind`（案の type）／`destination`（保存先）／`names`（addRules の「道具名(内容)」の一覧）／`text`（その案の行）

#### `_tool_input_rows(tool_input: object) -> list[tuple[str, str]]`（2467 行）
概要：道具の入力を (項目名, 値の文字) の一覧にする。辞書なら項目ごと（文字列はそのまま、他は JSON の文字にする）、辞書でなければ「入力」という 1 項目だけにする。
- 引数：`tool_input`（`object`）：許可の依頼の `tool_input`
- 戻り値：`list[tuple[str, str]]`。(項目名, 値の文字)

#### `_first_line(text: str) -> str`（2478 行）
概要：文の 1 行目を、前後の空白を除いて返す。
- 引数：`text`（`str`）：文
- 戻り値：`str`。1 行目（空白を除く）

#### `_short_text(text: str) -> str`（2483 行）
概要：吹き出しに出す文字を作る。最初の 4 文字に `"...."` を付ける。4 文字以下ならそのまま（`"...."` は付けない）。文字数は `len` で数える（全角・半角を区別しない）。
- 引数：`text`（`str`）：元の文
- 戻り値：`str`。短くした文

#### `_slash_result_lines(lines: list[str], cmd: str) -> list[str]`（2488 行）
概要：tmux の画面の行から、送った文 `cmd` の後ろの結果だけを取り出す。最後の「❯ <送った文>」の行の次から、入力欄の上の罫線（`─` だけの行）の手前まで。「❯」の行が見つからなければ画面全体、罫線が見つからなければ最後まで返す。本物の画面では「❯」のあとが改行させない空白（`\xa0`）なので、ふつうの空白に直して比べる（コメントに「2026-11-21 実物で確認」とある）。
- 引数：
  - `lines`（`list[str]`）：画面の行
  - `cmd`（`str`）：送った文（複数行なら 1 行目で比べる）
- 戻り値：`list[str]`。結果の行（`lines` の一部。元の行のまま）
- 主な変数：`head`（探す行の頭「❯ ＋ 1 行目」）／`start`（最後に見つかった「❯」の行の番号。無ければ None）／`end`（罫線の行の番号。無ければ最後）

### クラス `PermRequest`（2264 行）
概要：許可の依頼 1 件を持つ `dataclass`（データを持つだけのクラス）。メソッドはない。`received` は受け取った時刻、`conn` は hook（Claude Code が道具を使う前に呼ぶ外部の小さなプログラム）とのつながりで、答えを返すまで開けておく。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `tool_name` | `str` | 許可を求められている道具の名前 |
| `tool_input` | `object` | 道具に渡す入力（辞書とは限らない） |
| `received` | `float` | 受け取った時刻（`PermServer.clock` の値） |
| `conn` | `socket.socket | None` | hook とのつながり。答えを返すまで開けておく |
| `suggestions` | `list[dict[str, object]]` | Claude Code の案（`permission_suggestions` の辞書だけ）。無ければ空（既定は空の list） |

### クラス `PermServer`（2303 行）
概要：hook（`pca_perm_hook.py`）からの許可の依頼を受ける待ち受け。接続を待つ `accept` と読み取りは裏のスレッド（並行して動く処理）、依頼は `queue` に入れてメインのスレッドが取り出す。通信は UNIX ソケット（同じ計算機の中の通信口）の抽象名前空間（ファイルを作らない名前）を使う。

#### 主な属性
| 属性 | 型 | 用途 |
|---|---|---|
| `_active`（クラス変数） | `PermServer | None` | このプロセスでいま待ち受けている PermServer。同じプロセスの前の待ち受けを次の `start` で止めるために持つ |
| `name` | `str` | 待ち受けの名前。先頭は必ず `\0`（抽象名前空間の印） |
| `clock` | `Callable[[], float]` | 受け取った時刻に使う時計（既定 `time.monotonic`） |
| `queue` | `queue.Queue[tuple[float, dict[str, object], socket.socket | None]]` | 依頼の (受け取った時刻, 辞書, つながり)。通知（notification）はつながりを閉じて `None` で入れる |
| `_sock` | `socket.socket | None` | 待ち受けのソケット。None なら待ち受けていない |
| `_thread` | `threading.Thread | None` | 接続を待つスレッド |
| `_stop` | `threading.Event` | 待ち受けを止める合図 |

#### `__init__(self, name: str | None = None, clock: Callable[[], float] = time.monotonic) -> None`（2309 行）
概要：待ち受けの名前と時計を決め、依頼の queue と状態の入れ物を作る（まだ待ち受けない）。
- 引数：
  - `name`（`str | None`）：待ち受けの名前。既定 None なら `perm_socket_name()`（環境変数 `PCA_PERM_SOCKET` か既定の名前）。先頭に `\0` が無ければ足す
  - `clock`（`Callable[[], float]`）：時計。既定 `time.monotonic`
- 戻り値：なし
- 主な変数：`self.name`・`self.clock`・`self.queue`・`self._sock`・`self._thread`・`self._stop`

#### `start(self) -> bool`（2323 行）
概要：待ち受けを始める。すでに待ち受け中なら何もせず True。同じ名前で同じプロセスの前の PermServer があれば先に止める（残りの依頼は deny）。bind（名前を結びつける）に失敗（ほかで使用中）なら、メッセージを出して False。成功したら裏のスレッドで `_accept_loop` を動かし、`_active` に自分を入れる。
- 引数：なし（self 以外）
- 戻り値：`bool`。待ち受け中なら True、bind できなければ False
- 主な変数：`previous`（`_active` にいた前の PermServer）／`sock`（新しいソケット。`listen(8)`、`PERM_ACCEPT_SEC` のタイムアウト）／`self._stop`（新しい Event に作り直す）

#### `_accept_loop(self, sock: socket.socket, stop: threading.Event) -> None`（2346 行）
概要：接続を待ち、つながるたびに読み取りのスレッド（`_read_one`）を作る。`stop` が立つか、待ち受けのソケットが閉じる（`OSError`）と終わる。タイムアウトは続けて待つ。
- 引数：
  - `sock`（`socket.socket`）：待ち受けのソケット
  - `stop`（`threading.Event`）：止める合図
- 戻り値：なし
- 主な変数：`conn`（新しいつながり）

#### `_read_one(self, conn: socket.socket) -> None`（2357 行）
概要：接続から依頼の 1 行を読み（`PERM_READ_SEC` 秒まで）、JSON として解釈して `queue` に入れる。`type` が `notification` ならつながりを閉じて `None` で、`permission` ならつながりごと入れる。辞書でない・種類が不明・読み取りの失敗は、つながりを閉じて捨てる。
- 引数：`conn`（`socket.socket`）：接続
- 戻り値：なし
- 主な変数：`data`（読んだ辞書）／`kind`（`data["type"]`）

#### `answer(self, conn: socket.socket | None, answer: str) -> bool`（2374 行）
概要：答え（`{"answer": ...}` の 1 行）を送ってからつながりを閉じる。送れたら True、送れなければ False（例外は出さない）。`conn` が None なら False。
- 引数：
  - `conn`（`socket.socket | None`）：答える相手
  - `answer`（`str`）：答えの文字（このファイルでは allow・deny・tmux・always が使われている）
- 戻り値：`bool`。送れたか
- 主な変数：`sent`（送れたか）

#### `is_closed(self, conn: socket.socket | None) -> bool`（2386 行）
概要：相手が閉じたかを調べる。読める状態で、中身を覗いても空（`MSG_PEEK`）なら閉じている（True）。読めない状態は False。`conn` が None・調べられない（`OSError`・`ValueError`）ときは True。
- 引数：`conn`（`socket.socket | None`）：調べるつながり
- 戻り値：`bool`。閉じていれば True
- 主な変数：`readable`（`select` が返した読める状態のつながり）

#### `deny_all(self) -> None`（2398 行）
概要：`queue` に残っている依頼のすべてに deny を返す（待ち受けは止めない）。通知（つながりが None）には何も返さない。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`conn`（取り出した依頼のつながり）

#### `stop(self) -> None`（2408 行）
概要：待ち受けを閉じ、queue に残っている依頼にも deny を返す。待ち受けスレッドの終わりを `PERM_ACCEPT_SEC × 4` 秒まで待つ（自分自身のスレッドからは待たない）。読み取りの途中の分は hook 側の時間切れに任せる。`_active` が自分なら None に戻す。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._stop`（立てて止める）／`thread`／`sock`（閉じる）

### クラス `App`（2508 行）
概要：Pyxel の初期化、シーンの構築、毎フレームの更新と描画を担当する、このファイルの中心のクラス。office 配置では、人間（ユーザーの分身）の操作、Claude Code（tmux 経由）とのつなぎ、許可の依頼、コマンドの窓、利用制限の読み取りも扱う。

#### 主な属性（`__init__` で作るもの）
| 属性 | 型 | 用途 |
|---|---|---|
| `fps` | `int` | 毎秒のフレーム数（1〜60 に収める） |
| `time_scale` | `float` | 行き先・会話のタイマーの早回し倍率。0 以下・不正は `DEFAULT_TIME_SCALE` |
| `layout_name` | `str` | 配置の名前（"proto" か "office"） |
| `layout` | `Layout` | 配置（`LAYOUTS[layout]`）。`has_props` が真で office の機能が有効 |
| `mode` | `str` | 操作のモード。起動時は `MODE_WALK`、入力欄に打つときは `MODE_PROMPT` |
| `input_buf` | `str` | PROMPT の入力中の文字 |
| `ime_composing` | `bool` | 日本語の変換中と推測しているか |
| `_ime_wait_text` | `int` | 英字キーのあと、文字を待っている残りフレーム数 |
| `_pending_enter` | `int` | Enter のあと、確定の文字を待っている残りフレーム数（0 なら送信待ちなし） |
| `ime_state` | `str` | 日本語入力の状態の札。"?"（不明）・"あ"（オン）・"A"（オフ） |
| `history` | `list[str]` | 履歴（折り返したあとの行） |
| `history_color` | `list[int]` | 履歴の行ごとの文字の色（`history` と同じ長さ） |
| `history_scroll` | `int` | 履歴で一番上に出ている行の番号 |
| `ui_font` | `pyxel.Font | None` | 画面の文字のフォント。office のときだけ作る |
| `rate_json_path` | `Path` | 利用制限の JSON の場所（設定ファイルから） |
| `_reload_every` | `int` | JSON を読み直すフレーム数 |
| `_reload_count` | `int` | 前回読み直してから数えたフレーム数 |
| `five_hour` | `float` | 5 時間の利用制限（使った割合 0〜100） |
| `seven_day` | `float` | 週間の利用制限（使った割合 0〜100） |
| `manual_limits` | `bool` | キー 1〜4 で手動に変えたら True（以後は JSON を読まない） |
| `door_open` | `bool` | ドアの目標（True で開く） |
| `door_angle` | `float` | ドアの今の角度（0〜90） |
| `rng` | `random.Random` | 乱数。ここで 1 つだけ作り各キャラに渡す |
| `agents` | `list[Agent]` | キャラの一覧（人間は入れない） |
| `next_index` | `int` | 次にスペースキーで作業状態にするキャラの番号 |
| `measured_fps` | `float` | 実測の fps |
| `_frame_times` | `deque[float]` | fps の実測用のフレーム時刻 |
| `camera` | `Camera` | カメラ（`_build_scene` で作る） |
| `cam_target` | `Vec3` | カメラの注視点 |
| `cam_dist` | `float` | 注視点から目までの距離（ホイールで変える） |
| `cam_yaw` | `float` | カメラの横の向き（度） |
| `cam_pitch` | `float` | カメラの縦の向き（度） |
| `cam_dir` | `Vec3` | 注視点から目への単位ベクトル |
| `obstacles` | `list[Obstacle]` | 障害物（机・椅子・壁）。席 i の机と椅子は owner = i |
| `circles` | `list[tuple[float, float, float]]` | 丸い障害物（中心の x, z, 半径）。丸テーブルだけ |
| `nav` | `NavGrid | None` | 道探しの地図。office だけ、初期化で 1 回作る |
| `spot_manager` | `SpotManager | None` | 行き先の予約の管理。office だけ |
| `_nav_queue` | `deque[int]` | 道を探す順番待ちの列（人の番号。同じ人は二重に並ばない） |
| `human` | `Human | None` | 人間（ユーザーの分身）。office だけ、`_build_scene` で作る |
| `talk_partner` | `int | None` | 会話している相手の番号。会話していなければ None |
| `_cam_from` | `tuple[Vec3, float, float, float] | None` | カメラ切り替え前の (target, yaw, pitch, dist)。切り替え中だけ入る |
| `_cam_to` | `tuple[Vec3, float, float, float] | None` | カメラ切り替えの行き先 |
| `_cam_blend` | `float` | 切り替えの進み（0〜1、1 で終わり） |
| `_saved_view` | `tuple[float, float, float] | None` | 会話の前の (yaw, pitch, dist) |
| `_follow_replan` | `float` | 会話相手が歩くとき、人間が道を探し直すまでの残り時間（秒） |
| `_talk_seat_moved` | `bool` | 会話相手が座ったあと、人間を机の正面へ動かし終えたか |
| `scene` | `OfficeRoot` | ルートの Node |
| `_stuck_time` | `list[float]` | 各キャラが進めず立ち止まっている時間（秒） |
| `_stuck_state` | `list[str]` | 前のフレームの状態（変わったら計り直す） |
| `_stuck_count` | `list[int]` | 引っかかりが続いた回数（この回数で横へよける） |
| `_chat` | `list[Chatter]` | 会話中の人の状態（office だけ使う） |
| `_speakers` | `dict[str, int]` | 行き先の名前 → 話し手の番号 |
| `_speaker_timers` | `dict[str, float]` | 行き先の名前 → 話し手を交代するまでの残り時間（秒） |
| `stat_replans` | `int` | 引っかかって道を探し直した回数（計測用） |
| `stat_sidesteps` | `int` | 引っかかって横へよけた回数（計測用） |
| `stat_give_ups` | `int` | 行き先へ行けずにあきらめた回数（計測用） |

#### 主な属性（`_init_claude` で作るもの）
| 属性 | 型 | 用途 |
|---|---|---|
| `claude` | `bool` | `--claude` が有効か（引数の claude かつ office のとき True） |
| `session` | `str` | tmux のセッション名 |
| `workdir` | `str` | Claude Code の作業フォルダ（省略時 `DEFAULT_PCA_WORKDIR`） |
| `bridge` | `Bridge | None` | Claude Code とつなぐ部品。`--claude` のときだけ作る |
| `started` | `bool` | 始業しているか |
| `ending` | `bool` | 終業で引き継ぎメモを待っているか |
| `_handoff_left` | `float` | 終業の待ちの残り時間（秒） |
| `_last_sent` | `str | None` | 直前に自分で送った文字（届いた Prompt と比べる） |
| `_sub_map` | `dict[str, int]` | サブエージェントの番号 → 席の番号 |
| `_leave_timers` | `dict[int, float]` | 帰るまでの残り時間（秒） |
| `_idle_main` | `float` | メインが作業を止めている時間（秒） |
| `_bubble` | `str` | 吹き出しの文 |
| `_bubble_left` | `float` | 吹き出しを出す残り時間（秒） |
| `_dialog` | `bool` | 「前のセッションが残っています」を出しているか |
| `_door_auto` | `bool` | 出入りのためにドアを開けたか（D キーで開けたら False） |
| `_door_idle` | `float` | 出入りが止まってからの時間（秒） |
| `_last_line` | `dict[int, str]` | 話しかけたときの様子に出す、最後の行 |
| `_leave_elapsed` | `dict[int, float]` | 部屋を出ようとしている時間（秒） |
| `_busy_text` | `dict[int, str]` | 作業中の吹き出しの文（人の番号 → 1 行目） |
| `_pending_reply` | `str | None` | 作業中に届いた、いちばん新しい返事（作業が終わったら 6 秒出す） |
| `_human_text` | `str | None` | 人間の吹き出しの文（送ったプロンプト） |
| `_session_check_left` | `float` | 次にセッションを確かめるまでの時間（秒） |
| `_handoff_seen` | `bool` | 引き継ぎメモの Prompt（自分で送った分）を記録で見たか |
| `_perm_clock` | `Callable[[], float]` | 許可の時刻に使う時計（既定 `time.monotonic`） |
| `_perm_server` | `PermServer | None` | 許可の依頼の待ち受け。`--claude` のときだけ作る |
| `_perm_pending` | `list[PermRequest]` | 答えを待っている許可の依頼（先頭から答える） |
| `_perm_key_guard_until` | `float` | 自動でワープしたあと Y・N・T を受け付けない時刻（`_perm_clock` の値） |
| `_perm_tmux` | `bool` | tmux で答える分があるか（次の Tool・Reply・TurnEnd で戻す） |
| `_perm_always_confirm` | `bool` | 「いつも許可」の確かめの途中か（A を 1 回押したあと、もう 1 回 A で答える） |
| `_perm_always_req` | `PermRequest | None` | 確かめの途中の依頼 |
| `_perm_lock` | `bool` | 送信を止めているか（依頼がある、または tmux で答える分がある） |
| `_perm_wait_noted` | `bool` | 送信の止めの行を出したか（止めが外れたら戻す） |
| `_last_reply` | `str | None` | 最新の Reply の全文（会話のダイアログに出す） |
| `_last_prompt` | `str | None` | 最新のプロンプトの全文（Reply が無いとき出す） |
| `_dlg_scroll` | `int` | 会話のダイアログのスクロール（先頭の行の番号） |
| `_dlg_drag` | `bool` | 会話のダイアログのつまみを押したまま動かしているか |
| `_slash_open` | `bool` | コマンドの窓（SLASH）が開いているか |
| `_slash_cmd` | `str` | 送った文（前後の空白を除いたもの） |
| `_slash_seen_panel` | `bool` | パネル（「Esc to」の案内）を見たか |
| `_slash_started` | `float` | 窓に入った時刻（`_perm_clock` の値） |
| `_slash_lines` | `list[str]` | 画面の行（末尾の空白は消してある） |
| `_slash_scroll` | `int` | 一番上に出ている行（折り返し後）の番号 |
| `_slash_user_scrolled` | `bool` | ユーザーが動かしたか（一番下まで戻したらまた下に付く） |
| `_slash_static` | `bool` | 結果だけの窓か（画面を読むのをやめた） |
| `_slash_gone_since` | `float | None` | パネルの案内が見えなくなった時刻 |
| `_slash_next_read` | `float` | 次に画面を読む時刻（`_perm_clock` の値） |
| `_slash_drag` | `bool` | スクロールバーのつまみを押したまま動かしているか |
| `_cur_model` | `str` | 今のモデル（画面の文字と /model の結果から覚える。分からなければ "?"） |
| `_cur_effort` | `str` | 今の effort（同上） |
| `_state_left` | `float` | 画面から今のモデルを読む残りの時間（秒）。0 なら読まない |
| `_state_next` | `float` | 次に画面を読むまでの時間（秒） |
| `_menu` | `str | None` | 選ぶメニュー（"model" か "effort"。None なら閉じている） |
| `_menu_sel` | `int` | メニューで選んでいる行の番号 |
| `_usage_busy` | `bool` | 利用制限を読んでいる最中か |
| `_usage_phase` | `str` | "read"（値を探す）・"close"（閉じるのを待つ）・""（読んでいない） |
| `_usage_elapsed` | `float` | 読み始めてからの時間（秒） |
| `_usage_poll_left` | `float` | 次に画面を読むまでの時間（秒） |
| `_usage_close_elapsed` | `float` | 閉じるのを待っている時間（秒） |
| `_usage_closes` | `int` | 閉じるために Escape を送った回数 |
| `_usage_panel_seen` | `bool` | 最後に読んだ画面に「Esc to」があったか |
| `_usage_note_shown` | `bool` | 今の読み取りで「読んでいます」の行を出したか |
| `_usage_start_armed` | `bool` | 始業してモデルの読み取りが終わったら 1 回だけ読む予定があるか |
| `_usage_after_turn_left` | `float` | 返事の終わりから読むまでの残り時間（秒）。0 なら予定なし |
| `_usage_pending` | `list[tuple[str, bool]]` | 読んでいる間に送ろうとした文（文, コマンドの窓を開くか） |
| `_usage_reset_5h` | `str | None` | 5 時間の「Resets」の行（表示には使わない） |
| `_usage_reset_week` | `str | None` | 週間の「Resets」の行（表示には使わない） |

#### `__init__(self, fps: int, seed: int | None, layout: str = "proto", agents: int = 3, config_path: str | None = None, time_scale: float = DEFAULT_TIME_SCALE, claude: bool = False, workdir: str | None = None, session: str = "pyxelcube_agents", bridge_factory: Callable[[str, str], Bridge] | None = None) -> None`（2511 行）
概要：`fps` を 1〜60 に収めて `pyxel.init` し、シーンと各種の状態を作る。`pyxel.run` は呼ばない。office（`has_props`）では大きい画面で、Esc で閉じない（`quit_key=KEY_NONE`）。`claude` が True なら本物の Claude Code とつなぐ準備をする。
- 引数：
  - `fps`（`int`）：毎秒のフレーム数（1〜60 に収める）
  - `seed`（`int | None`）：乱数の種。None なら毎回違う
  - `layout`（`str`）：配置の名前。"proto" か "office"（既定 "proto"）。`LAYOUTS` に無ければ `ValueError`
  - `agents`（`int`）：キャラの数。1〜その配置の席数に収める（既定 3）
  - `config_path`（`str | None`）：設定ファイル。省略時は `DEFAULT_CONFIG_PATH`（本体と同じフォルダの pyxelcube_agents.toml）
  - `time_scale`（`float`）：行き先・会話のタイマーの早回し倍率（0 以下は既定に戻す）。既定 `DEFAULT_TIME_SCALE`
  - `claude`（`bool`）：Claude Code とつなぐか。既定 False
  - `workdir`（`str | None`）：Claude Code の作業フォルダ。省略時 `DEFAULT_PCA_WORKDIR`
  - `session`（`str`）：tmux のセッション名。既定 "pyxelcube_agents"
  - `bridge_factory`（`Callable[[str, str], Bridge] | None`）：Bridge を作る関数（作業フォルダ・セッション名を受ける）。省略時は `Bridge(workdir, session)`（テストで偽物を入れるための口）
- 戻り値：なし
- 主な変数：`self.layout`（配置）／`self.nav`・`self.spot_manager`（office だけ作る）／`self.cam_*`（起動時のカメラ。今の目の位置から yaw・pitch を求める）／`self.scene`（`_build_scene` の結果）／`count`（`agents` を 1〜席数に収めた数）。最後に `_init_claude`、`claude` でなければ `reload_rate_limits()`（JSON を読む）、`_sync_scene_values()` を呼ぶ

#### `_build_scene(self, count: int) -> OfficeRoot`（2651 行）
概要：ルートの `OfficeRoot`、カメラ、先頭 `count` 席のキャラ（A, B, C…の名前）を組み立てる。office のときはキャラの起動時のうろつき時間を乱数でずらし、人間（`AgentView` と `MarkerView` つき）を作り、カメラの注視点を人間の位置にする。
- 引数：`count`（`int`）：作るキャラの数
- 戻り値：`OfficeRoot`。作ったルート
- 主な変数：`root`（ルート。`shading`・`camera` を設定）／`agent.wander_time`（0〜`OUTING_WANDER_SEC` の乱数。全員が同時に出かけないように）／`self.agents`（足していく）／`self.human`

#### `_apply_camera(self) -> None`（2703 行）
概要：カメラの位置・向きと遠方クリップ距離（これより遠くは描かない距離）を、今の注視点・yaw・pitch・距離に合わせて設定する。遠方クリップは距離に `FAR_MARGIN` を足す。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self.cam_dir`（`_view_dir` で更新）／`eye`（カメラの目の位置）／`self.camera.transform`・`self.camera.far`

#### `update(self) -> None`（2711 行）
概要：毎フレームの処理。キーとマウスを処理し、全員の行動とシーンを 1 フレーム進める。ダイアログ・メニュー・コマンドの窓（SLASH）が開いているフレームは、ほかの入力を処理しない。WALK のときだけ 3D の操作（スペース・ドア D・会話終了 Q・利用制限の手動キー）を受け付ける。左クリックは開いているものに応じて振り分け、ホイールは「コマンドの窓の中・会話のダイアログ・履歴・3D のズーム」のうち、マウスの下にあるものを動かす。その後、ドア・利用制限・視点・うろつき・道探し・`--claude` の更新・各キャラと人間の更新・押し出し・引っかかりの判定・行き先のグループ・カメラ・シーンの更新・fps の記録を順に行う。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`dialog_open`・`menu_open`（フレームの最初に覚えた、ダイアログ・メニューが開いていたか）／`slash`（コマンドの窓が開いていて `--claude` か）／`walking`（3D の操作を受け付けるか。ダイアログなし・PROMPT でない・守り時間でない）／`dt`（1 フレームの秒）／`timer_dt`（`dt × time_scale`。行き先・会話のタイマーだけ早回し）／`prev_xz`（行動の前の各キャラの位置。押し出し前後の移動距離を測る）

#### `_prompting(self) -> bool`（2811 行）
概要：今が PROMPT モードかを返す（office だけ。proto は常に False）。
- 引数：なし（self 以外）
- 戻り値：`bool`。PROMPT なら True

#### `_perm_guard_active(self) -> bool`（2815 行）
概要：自動で WALK に切り替えたあと、キー操作を受け付けない時間の中かを返す。既定値 0.0 のときは False。マウスは止めない。
- 引数：なし（self 以外）
- 戻り値：`bool`。守り時間の中なら True
- 主な変数：`self._perm_key_guard_until`（この時刻まで受け付けない）／`self._perm_clock()`（今の時刻）

#### `_ctrl_held(self) -> bool`（2820 行）
概要：Ctrl（左右どちらでも）を押しているかを返す。
- 引数：なし（self 以外）
- 戻り値：`bool`。押していれば True

#### `_prompt_exit_pressed(self) -> bool`（2824 行）
概要：PROMPT から WALK に戻るキー（Ctrl+E）が、今のフレームで押されたかを返す。
- 引数：なし（self 以外）
- 戻り値：`bool`。押されたら True

#### `_update_mode_keys(self) -> None`（2828 行）
概要：office のモード切り替えと、PROMPT の文字入力を 1 フレーム分処理する。WALK で P キーを押すと PROMPT になり（そのフレームの入力文字は足さない）、PROMPT で Ctrl+E を押すと WALK に戻る。Ctrl+J は改行（送信しない）、Enter は少し待ってから送信（確定の文字が来たら取り消す）、Backspace は 1 文字消す（連打つき）、Esc は変換中なら変換の取り消し、そうでなければ Claude Code に中断を送る（許可待ち・利用制限の読み取り中は送らない）。日本語入力の変換中かどうかと、Shift＋Ctrl による日本語入力の切り替え（`ime_state`）は、英字の届き方から推測する。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`switched`（このフレームに P で PROMPT へ入ったか）／`ctrl`（Ctrl を押しているか）／`letter_pressed`（英字キーが押されたか。`IME_PRINTABLE_KEYS`）／`printable`（英字が押され、かつ切り替えのフレームでも Ctrl 押下中でもない）／`text`（`pyxel.input_text`。Ctrl 中・切り替えのフレームは空）／`self.input_buf`・`self.ime_composing`・`self._ime_wait_text`・`self._pending_enter`・`self.ime_state`

#### `_send_input(self) -> None`（2917 行）
概要：入力中の文字を送る。改行と空白だけなら送らず、入力欄を空にする。許可の答えを待っている間は送らず、入力欄の文字は残す。`--claude` で `/exit`・`/quit`（`_is_blocked_command`）なら送らず案内を履歴に出す。それ以外は履歴に「> 」つきで足して入力欄を空にし、`/model`・`/effort` だけの文ならメニューを開き（始業中で許可待ちでないとき）、`--claude` なら Claude Code に送る（「/」始まりならコマンドの窓つき）。`--claude` でないときは履歴に出すだけ（試作）。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`text`（送る文）／`self.input_buf`（送ったら空にする）

#### `_reset_ime(self) -> None`（2942 行）
概要：日本語の変換中の推測と送信待ちを、全部 False／0 に戻す。PROMPT から WALK に戻るときに使う。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self.ime_composing`・`self._ime_wait_text`・`self._pending_enter`

#### `_init_claude(self, claude: bool, workdir: str | None, session: str, bridge_factory: Callable[[str, str], Bridge] | None) -> None`（2950 行）
概要：`--claude` のときの準備。`--claude` かどうかに関係なく、上の「`_init_claude` で作るもの」の属性に既定値を入れる。`--claude` のときは作業フォルダを作り、Bridge と PermServer を作り、全員を `park()`（部屋の外に置く）し、`atexit`（プロセスの終わりに呼ぶ後始末）に `_atexit_shutdown` を登録する。
- 引数：
  - `claude`（`bool`）：`--claude` を指定したか
  - `workdir`（`str | None`）：作業フォルダ。None なら `DEFAULT_PCA_WORKDIR`
  - `session`（`str`）：tmux のセッション名
  - `bridge_factory`（`Callable[[str, str], Bridge] | None`）：Bridge を作る関数。None なら `Bridge(w, s)`
- 戻り値：なし
- 主な変数：`self.claude`（`claude and layout.has_props`）／`make`（Bridge を作る関数）／`self.bridge`・`self._perm_server`（`--claude` のときだけ作る）

#### `_active_indices(self) -> list[int]`（3039 行）
概要：見えている人の番号の一覧を返す。`--claude` のとき見えていない人は、動かさず・描かず・道や予約にも入れない。
- 引数：なし（self 以外）
- 戻り値：`list[int]`。`visible` が真の `agents` の番号

#### `_bridge_error(self) -> str`（3043 行）
概要：つなぎの部品の最後の失敗の理由を返す（無ければ空文字）。`bridge.last_error`、無ければ `bridge.tmux.last_error` を見る。
- 引数：なし（self 以外）
- 戻り値：`str`。失敗の理由。bridge が None・理由が無いときは `""`

#### `_add_block(self, first: str, text: str, rest: str = "  ", color: int = TEXT_COLOR) -> None`（3052 行）
概要：`text` を改行で分け、1 行目に `first`、2 行目以降に `rest` を付け、`UI_COLS` 桁で折り返して履歴に足す。
- 引数：
  - `first`（`str`）：1 行目の頭に付ける文字
  - `text`（`str`）：足す文（複数行可）
  - `rest`（`str`）：2 行目以降の頭に付ける文字。既定 2 つの空白
  - `color`（`int`）：文字の色。既定 `TEXT_COLOR`
- 戻り値：なし
- 主な変数：`rows`（折り返した行。`_append_history_rows` に渡す）

#### `_send_to_claude(self, text: str, slash: bool = False) -> bool`（3060 行）
概要：入力の文字を Claude Code に送る。始業していなければ履歴に案内を出して False。許可の答えを待っている間は送らず False。利用制限を読んでいる間は `_usage_pending` に取っておいて False（読み終わったあとに送る）。送るときは、メインが見えていなければ部屋に入れ、送った文字を覚える。`slash` が True で送れたら、コマンドの窓に入る。
- 引数：
  - `text`（`str`）：送る文
  - `slash`（`bool`）：送ったあとコマンドの窓に入るか。既定 False
- 戻り値：`bool`。送れたら True
- 主な変数：`self._last_sent`・`self._human_text`（送った文を覚える。人間の吹き出し用）／`self._idle_main`（0 に戻す）／`self._usage_pending`（取っておく文）／`sent`（`bridge.send_prompt` の結果）

#### `_toggle_session(self) -> None`（3086 行）
概要：始業・終業（ボタンと F1）。終業の待ち中・`--claude` でない・bridge なしなら何もしない。始業していなければ、前のセッションが残っていればダイアログを出し（`_dialog` を True）、無ければ新規で始業する。始業していれば終業の手順を始める。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._dialog`（前のセッションの確認ダイアログを出すか）／`self.started`・`self.ending`

#### `_choose_dialog(self, mode: str) -> None`（3098 行）
概要：前のセッションのダイアログの選び方を受ける。ダイアログを閉じ、`mode` が空でなければその方法で始業する。空なら何もしない（やめる）。
- 引数：`mode`（`str`）："resume"（前のセッションにつなぐ）・"restart"（作り直す）、または空（やめる）
- 戻り値：なし
- 主な変数：`self._dialog`（False に戻す）

#### `_start_session(self, mode: str) -> None`（3104 行）
概要：`Bridge.begin(mode)` で始業する。成功ならメイン（番号 `MAIN_INDEX`）の役割・名前を "main" にし、許可の待ち受けを始め、モデルと利用制限の読み取りの予定を立て、メインを部屋に入れ、履歴に案内を出す。失敗なら履歴に理由を出す。
- 引数：`mode`（`str`）："new"・"resume"・"restart" など（`bridge.begin` へそのまま渡す。履歴の文は "resume" とそれ以外で分かれる）
- 戻り値：なし
- 主な変数：`self.started`（True にする）／`self._state_left`（`STATE_READ_SEC`。モデルを画面から読む時間）／`self._usage_start_armed`（モデルの読み取りのあと利用制限を 1 回読む予定）／`self._session_check_left`（`SESSION_CHECK_SEC`）

#### `_begin_handoff(self, sleep: Callable[[float], None] = time.sleep) -> None`（3127 行）
概要：終業の前に、引き継ぎメモを書いてもらう（`t(HANDOFF_PROMPT)` を送る。言語は起動のときに決めたもの）。コマンドの窓・メニューは何も送らずに閉じ、利用制限の読み取りは Escape を送って止め、残った許可の依頼は deny にする。セッションが無い・送れないときは、頼まずにすぐ終業を終える。送れたら `ending` を True にして待ち時間を数え始める（TurnEnd が来るか待ち時間を過ぎたら閉じる処理は別の場所）。
- 引数：`sleep`（`Callable[[float], None]`）：待つ関数（`_release_perm` へ渡す。テストで差し替える）。既定 `time.sleep`
- 戻り値：なし
- 主な変数：`self.ending`（True にする）／`self._handoff_left`（`HANDOFF_WAIT_SEC`）／`self._handoff_seen`（False に戻す）／`self._last_sent`・`self._human_text`（`t(HANDOFF_PROMPT)`）

#### `_finish_ending(self) -> None`（3149 行）
概要：終業を終える。見えている全員を部屋から出し、`bridge.end(kill_session=True)` で見張りと tmux のセッションを閉じ、許可の待ち受けを止め、始業・終業の状態と、サブエージェントの対応・吹き出しなどの記録を消し、履歴に「終業しました」を出す。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self.started`・`self.ending`（False に）／`self._sub_map`・`self._leave_timers`・`self._last_line`・`self._busy_text`（空にする）／`self._pending_reply`・`self._human_text`（None に）／`_forget_state()`（モデルと effort を "?" に戻す。本体は別の場所）

#### `_session_gone(self) -> None`（3167 行）
概要：Claude Code のセッションが無くなった（`/exit` など）ときの処理。利用制限の読み取りを止め、コマンドの窓を閉じ、モデルと effort を忘れ、全員を部屋から出し、`bridge.end(kill_session=False)`（tmux は閉じない）で見張りを止め、許可の依頼を deny にして待ち受けも止める。終業中だったなら「終業しました」も出す。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`was_ending`（呼ばれたとき終業中だったか）／`self.started`・`self.ending`（False に）／`self._sub_map` ほか記録（空にする）

#### `_shutdown_claude(self, sleep: Callable[[float], None] = time.sleep) -> None`（3191 行）
概要：窓を閉じるときの後始末。コマンドの窓・メニューを閉じ、利用制限の読み取りを止め、許可の依頼を deny にして待ち受けを止める。始業していて終業していなければ、引き継ぎメモを頼み、`TurnEnd` が来るまで（最大 `HANDOFF_WAIT_SEC` 秒、0.2 秒ごとに `bridge.poll()`）待ってから tmux を閉じる。セッションが無い・送れないときは待たずに閉じる。
- 引数：`sleep`（`Callable[[float], None]`）：待つ関数。既定 `time.sleep`
- 戻り値：なし
- 主な変数：`waited`（待った秒）／`done`（引き継ぎの返事の終わりを見たか）／`self._handoff_seen`（依頼の Prompt が記録に出たか。これが True のあとの TurnEnd だけを終わりとみなす）／`self.started`・`self.ending`（False にする）

#### `_atexit_shutdown(self) -> None`（3240 行）
概要：プロセスの終わりに呼ぶ後始末（`atexit` に登録する）。`_shutdown_claude()` を呼ぶだけ。
- 引数：なし（self 以外）
- 戻り値：なし

#### `_begin_work(self, i: int) -> None`（3244 行）
概要：人 `i` を作業状態にする。行き先へ向かう途中・行き先・戻り中（`GOING`・`AT_SPOT`・`RETURNING`）なら、予約を外してタイマーを 0 にしてから作業に入る。予約を外さないと、次の予約が二重予約で止まる。
- 引数：`i`（`int`）：人の番号（`agents` の添字）
- 戻り値：なし
- 主な変数：`self.spot_manager.release(i)`（行き先の予約を外す）／`reset_outing_timers()`（出かけるタイマーを戻す）

#### `_enter(self, i: int) -> None`（3251 行）
概要：人 `i` を部屋に入れる。ドアを開け（自動で開けた印を付ける）、ドアの内側（`ENTER_INSIDE_X`, `DOOR_Z`）に置き、見えるようにして、作業を始めさせる（席へ向かう）。
- 引数：`i`（`int`）：人の番号
- 戻り値：なし
- 主な変数：`self.door_open`（True）／`self._door_auto`（True）／`self._door_idle`（0）／`agent.pos`・`agent.visible`

#### `_leave(self, i: int) -> None`（3261 行）
概要：人 `i` を部屋から出す。見えていなければ何もしない。会話の相手なら会話を終え、ドアを開け、行き先の予約・会話の状態・道探しの順番待ち・帰る時間を消し、ドアの内側まで歩かせる（`begin_leaving`）。着いたあとは `_finish_leaving` が置き場所へ戻す。道が無ければ歩かずにすぐ `_park_agent` する。
- 引数：`i`（`int`）：人の番号
- 戻り値：なし
- 主な変数：`goal`（ドアの内側の位置）／`self._chat[i]`（空の `Chatter` に戻す）／`self._nav_queue`（`i` を外す）／`self._leave_timers`（`i` を外す）

#### `_finish_leaving(self, dt: float = 0.0) -> None`（3281 行）
概要：部屋を出る人を、見えない置き場所へ戻す。対象は `LEAVING` の状態の人のうち、歩き終えた人（`leaving_done`）と、`LEAVE_MAX_SEC` 秒続いた人。`LEAVING` でない人の経過時間の記録は消す。
- 引数：`dt`（`float`）：前の呼び出しからの秒。既定 0.0
- 戻り値：なし
- 主な変数：`self._leave_elapsed`（人の番号 → 出ようとしている秒）／`elapsed`（今の経過秒）

#### `_park_agent(self, i: int) -> None`（3294 行）
概要：人 `i` を見えない置き場所へ戻し（`park()`）、この人への対応（サブエージェントの番号の対応・帰る時間・最後の行・作業中の吹き出しの文）を消す。
- 引数：`i`（`int`）：人の番号
- 戻り値：なし
- 主な変数：`self._sub_map`（席が `i` の項目を消す）／`self._leave_timers`・`self._last_line`・`self._busy_text`

#### `_update_door_auto(self, dt: float) -> None`（3304 行）
概要：出入りが止まってから `DOOR_IDLE_CLOSE_SEC` 秒たったら、出入りのために開けたドアを閉める。見えている人が、席に着く途中の作業中か退出中（`LEAVING`）なら動いているとみなし、待ち時間を 0 に戻す。D キーで自分で開けたドア（`_door_auto` が False）は閉めない。
- 引数：`dt`（`float`）：経過秒
- 戻り値：なし
- 主な変数：`moving`（出入りが続いているか）／`self._door_idle`（出入りが止まってからの秒）／`self.door_open`・`self._door_auto`

#### `_usage_can_read(self) -> bool`（3322 行）
概要：今、`/usage` を送って読んでよいかを返す。`--claude` で始業していて、終業中でなく、bridge があり、読んでいる最中でなく、許可の依頼も無く、コマンドの窓もメニューも開いておらず、メインが作業していない（`busy` でない）、tmux に許可の画面が出ていない、のときだけ True。
- 引数：なし（self 以外）
- 戻り値：`bool`。読んでよければ True

#### `_usage_try_start(self) -> None`（3332 行）
概要：読めるなら `/usage`（`USAGE_COMMAND`）を送って読み始める。読めなければ何もしない（その予定は、そこで終わる）。送れなければ読み取りを終えて「/usage を送れませんでした」を出力する。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._usage_busy`（True）／`self._usage_phase`（"read"）／`self._usage_poll_left`（`USAGE_POLL_SEC`）／`self._usage_elapsed`・`_usage_close_elapsed`・`_usage_closes`・`_usage_panel_seen`・`_usage_note_shown`（読み始めの値に戻す）

#### `_usage_panel_open(self) -> bool`（3348 行）
概要：/usage の画面が出ていて、Escape で閉じる必要があるかを返す（「Esc to」の判定は英語の画面が前提）。読んでいる間（"read"）は True。閉じるのを待つ間（"close"）は、最後に見た画面に案内（「Esc to」）が残っているときだけ True。
- 引数：なし（self 以外）
- 戻り値：`bool`
- 主な変数：`self._usage_phase`・`self._usage_panel_seen`

#### `_usage_finish(self) -> None`（3354 行）
概要：読み取りを終える（値は前のままか、読んだ値）。取っておいた文（`_usage_pending`）は残す。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._usage_busy`（False）／`self._usage_phase`（""）／`self._usage_panel_seen`（False）

#### `_usage_abort(self, send_escape: bool) -> None`（3360 行）
概要：読んでいる最中なら読みをやめる。`send_escape` が True で画面が出ていそうなら、Escape を 1 回送る。取っておいた文は残す。読んでいなければ何もしない。
- 引数：`send_escape`（`bool`）：画面が出ていれば Escape を送るか
- 戻り値：なし

#### `_usage_drop_pending(self) -> None`（3368 行）
概要：取っておいた文を捨てる（終業・窓の×・セッション消失のとき）。1 つでもあれば「送れなかったプロンプトがあります」を履歴に出す。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._usage_pending`

#### `_usage_flush(self) -> None`（3374 行）
概要：取っておいた文を、読み終わったあと 1 フレームに 1 つずつ送る。読んでいる間・コマンドの窓の間・始業していないとき・許可の答えを待つ間（tmux に許可の画面があるときも）は送らない。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._usage_pending`（先頭から取り出す）／`text`・`slash`（取り出した文と、コマンドの窓を開くか）

#### `_update_usage(self, dt: float) -> None`（3384 行）
概要：利用制限の読み取りの 1 フレーム。始業の予定（モデルの読み取りが終わったとき）と、返事の終わりからの予定（残り時間が 0 になったとき）を確かめて読み始め、許可の依頼が来たら Escape を 1 回送って読みをやめ、読んでいれば `_usage_step` で進め、最後に取っておいた文を送る。
- 引数：`dt`（`float`）：経過秒
- 戻り値：なし
- 主な変数：`self._usage_start_armed`（始業後の 1 回の予定。`_state_left` が 0 以下になったら実行）／`self._usage_after_turn_left`（返事の終わりからの残り時間。0 なら予定なし）

#### `_usage_step(self, dt: float) -> None`（3400 行）
概要：読み取りを 1 フレーム進める。"read" では `USAGE_POLL_SEC` ごとに tmux の画面を読み、`_parse_usage` で 5 時間と週間の割合を探す。両方取れたら値を `five_hour`・`seven_day` に入れ（0〜100）、掲示板に渡し、Escape を送って "close" に移る。`USAGE_TIMEOUT_SEC` 秒たっても読めなければ、出力して終える（前の値のまま）。"close" では「Esc to」の案内が消えたら終わり、`USAGE_CLOSE_SEC` 秒残れば Escape をもう一度送り、それでも残ればあきらめて出力する。
- 引数：`dt`（`float`）：経過秒
- 戻り値：なし
- 主な変数：`self._usage_phase`（"read" か "close"）／`self._usage_elapsed`（読み始めからの秒）／`self._usage_poll_left`（次に画面を読むまでの秒）／`self._usage_close_elapsed`・`self._usage_closes`（閉じるのを待つ秒と、Escape を送った回数）／`five`・`week`・`reset_5h`・`reset_week`（`_parse_usage` が返した値。Resets の行は `_usage_reset_5h`・`_usage_reset_week` に保存）

#### `_start_perm(self) -> None`（3450 行）
概要：始業のとき、許可の待ち受けを始める。待ち受けが使えなければ、履歴に目立つ 1 行を出す（許可は tmux に出て、送信も止まらない）。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._perm_server`（None なら何もしない）

#### `_stop_perm(self) -> None`（3457 行）
概要：待ち受けを止める。残った依頼はすべて deny にする（tmux には回さない）。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._perm_tmux`（False に）／`self._perm_server`

#### `_deny_perm_all(self) -> None`（3466 行）
概要：今の依頼（待ちの列 `_perm_pending` と、server の queue の残り）のすべてに deny を返す。`_perm_tmux` は変えない。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._perm_pending`（空にする）

#### `_release_perm(self, sleep: Callable[[float], None]) -> None`（3476 行）
概要：終わるときの後始末。依頼は deny にし、tmux で答える分があれば Esc を 1 回送って 1 秒待つ（許可の画面を取り消す）。最後に送信の止めを外す。
- 引数：`sleep`（`Callable[[float], None]`）：待つ関数（1.0 を渡す）
- 戻り値：なし
- 主な変数：`self._perm_tmux`（False に）

#### `_sync_perm_lock(self) -> None`（3485 行）
概要：送信を止めるかを決める。依頼が 1 件でもある、または tmux で答える分がある間は止める。止めが外れたら、待ちの行を出した印（`_perm_wait_noted`）も戻す。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._perm_lock`・`self._perm_wait_noted`

#### `_clear_perm_tmux(self) -> None`（3491 行）
概要：Tool・Reply・TurnEnd の届いたとき、tmux で答える分の印を戻す。依頼が残っていれば戻さない。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`self._perm_tmux`

#### `_tmux_shows_permission(self) -> bool`（3497 行）
概要：tmux の画面に許可の画面が出ているかを返す（送る直前の 2 つ目の守り）。`--claude` でない・始業していない・偽の Bridge（`permission_screen_open` メソッドが無い）・調べて例外が出たときは False。
- 引数：なし（self 以外）
- 戻り値：`bool`
- 主な変数：`check`（`bridge.permission_screen_open`。無ければ None）

#### `_perm_block_send(self) -> bool`（3509 行）
概要：送信を止めているかを返す。止めていなくても、tmux の画面に許可の画面が出ていれば止める（`_perm_tmux` を立てる）。止めているなら、待ちの行（`PERM_WAIT_NOTE`）を同じ文が続けて出ないように 1 度だけ履歴に出し、True を返す。
- 引数：なし（self 以外）
- 戻り値：`bool`。止めていれば True
- 主な変数：`self._perm_lock`・`self._perm_tmux`・`self._perm_wait_noted`

#### `_perm_cwd_ok(self, cwd: object) -> bool`（3525 行）
概要：依頼の `cwd`（Claude Code が動いている場所）が、作業フォルダ（`self.workdir`）の中かを返す。文字でない・空・パスが壊れている（`OSError`・`ValueError`・`RuntimeError`）ときは False（tmux に回す）。
- 引数：`cwd`（`object`）：依頼の `cwd`
- 戻り値：`bool`。作業フォルダの中なら True

#### `_perm_summary(self, req: PermRequest) -> str`（3534 行）
概要：履歴に出す依頼の要約（道具名と入力の要約）を返す。入力の要約は `_tool_summary`（このファイルの別の場所）で作る。
- 引数：`req`（`PermRequest`）：依頼
- 戻り値：`str`。「道具名 入力の要約」（前後の空白を除く）

#### `_update_perm_requests(self) -> None`（3538 行）
概要：毎フレーム、server の queue から依頼を取り出し、時間切れと取り下げ（相手が閉じた）を確かめる。取り出し方：通知（つながりが None）で `notification_type` が `permission_prompt` なら tmux で答える扱いにする。`cwd` が作業フォルダの外の依頼は "tmux" と答えて tmux に回す。それ以外は `PermRequest` にして `_perm_pending` に足す。`PERM_WAIT_SEC` を過ぎた依頼は "tmux" と答えて履歴に出す。相手が閉じた依頼は履歴に出して外す。新しい依頼が来たとき（それまで空だった場合）は、コマンドの窓を閉じ、人間がメインと会話していなければメインのところへ行き（会話の相手を替える）、立つ場所が無ければ案内を出す。入力欄で打っていたら WALK に切り替える（入力中の文字は消さない）。最後に送信の止めを合わせる。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`server`（`self._perm_server`）／`was_empty`（このフレームの最初に依頼が無かったか）／`self._perm_pending`（待ちの依頼の列）／`self._perm_tmux`（tmux で答える分があるか）／`self._perm_key_guard_until`（ワープ後は `PERM_KEY_GUARD_SEC`、PROMPT から WALK に切り替えたら `PERM_KEY_GUARD_PROMPT_SEC` だけ Y・N・T などを受け付けない）／`self._dlg_scroll`（新しい依頼でダイアログのスクロールを先頭に戻す）

#### `_perm_always_done(self) -> bool`（3608 行）
概要：「いつも許可」の確かめを続けてよいかを返す。先頭の依頼が確かめの依頼（`_perm_always_req`）のままで、WALK で、メインと話していて、ダイアログが無いときだけ True。名前は「done」だが、True は「まだ続けてよい」の意味（コードの使われ方からの読み取り）。
- 引数：なし（self 以外）
- 戻り値：`bool`

#### `_update_perm_keys(self) -> None`（3618 行）
概要：Y・N・T で先頭の許可の依頼に答える（Y は allow、N は deny、T は tmux）。A は「いつも許可」で、案がある依頼だけ。1 回目の A で確かめに入り、2 回目の A で `_answer_always` を呼ぶ。確かめの途中に A 以外のキー・クリック（`PERM_CANCEL_BUTTONS`）が押されたら、確かめをやめるだけで答えない。WALK で、メインと会話しているときだけ効く。守り時間・ダイアログの間は受け付けない。答えが届かなければ tmux に回して履歴に案内を出す。
- 引数：なし（self 以外）
- 戻り値：なし
- 主な変数：`server`／`self._perm_always_confirm`・`self._perm_always_req`（確かめの状態。続けてよくなければここで解除）／`choice`（"allow"・"deny"・"tmux"）／`req`（取り出した依頼）／`summary`（履歴に出す要約）

#### `_answer_always(self, server: PermServer) -> None`（3663 行）
概要：「いつも許可」の 2 回目の A。先頭の依頼に "always" を返す。履歴に要約と案の行（灰色の `PERM_SUGGEST_COLOR`）を出す。答えが届かなければ tmux に回して案内を出す。
- 引数：`server`（`PermServer`）：答えを返す先
- 戻り値：なし
- 主な変数：`req`（取り出した先頭の依頼）／`summary`／`self._perm_always_confirm`・`self._perm_always_req`（確かめを終える）

#### `_is_slash_command(self, text: str) -> bool`（3681 行）
概要：送る文が、コマンドの窓を出すものかを返す。前後の空白を除いて「/」で始まり、`SLASH_EXIT_CMDS`（/exit・/quit）に入っていないとき True。
- 引数：`text`（`str`）：送る文
- 戻り値：`bool`

#### `_open_slash(self, text: str) -> None`（3686 行）
概要：コマンドの窓（SLASH）に入る。送った文を覚え、すぐ画面を読む状態にする（`_slash_next_read` を今の時刻に）。モードは PROMPT のまま。
- 引数：`text`（`str`）：送った文（前後の空白を除いて `_slash_cmd` に入れる）
- 戻り値：なし
- 主な変数：`now`（`_perm_clock()` の値）／`self._slash_open`（True）／`self._slash_cmd`／`self._slash_started`（窓に入った時刻）／`self._slash_lines`・`_slash_scroll`・`_slash_user_scrolled`・`_slash_static`・`_slash_gone_since`・`_slash_drag`・`_slash_seen_panel`（入ったときの値に戻す）

## App の後半・起動（3701 行〜最後）

以下の `self.` はすべて App のインスタンス。`pyxel` は描画・入力のライブラリ。

### クラス `App` の続き（3701〜5523 行）

#### コマンドの窓（スラッシュコマンドの結果を見せる窓。_slash_ で始まる属性を使う）

#### `_close_slash(self) -> None`（3701 行）
概要：コマンドの窓を閉じる。tmux（端末を分割して動かすツール）には何も送らない。モードは PROMPT のまま。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._slash_open` を False／`self._slash_lines` を空に／`self._slash_static`・`self._slash_seen_panel`・`self._slash_drag` を False／`self._slash_gone_since` を None

#### `_update_slash(self) -> None`（3710 行）
概要：コマンドの窓の 1 フレーム分。パネル（Claude Code が出す選択画面）のときはキーを tmux へ送り、時間が来たら画面を読んで閉じるか決める。結果だけの窓（`_slash_static`）は Esc・Enter で閉じる。
- 引数：なし
- 戻り値：なし
- 主な変数：`now`（`self._perm_clock()` の現在時刻）／`self._slash_next_read` 次に画面を読む時刻。キーを送ったら now にして待たずに読む／`self._slash_static` 結果だけの窓か

#### `_send_slash_keys(self) -> bool`（3724 行）
概要：このフレームに押されたキーと入力された文字を tmux へ送る。`SLASH_KEYS` の表のキーは名前で、英数字と記号（`!`〜`~`）は文字としてそのまま送る。日本語と空白は送らない（空白は Space キーで送る）。
- 引数：なし
- 戻り値：`bool`。何か送ったら True。`self.bridge` が None なら False
- 主な変数：`sent` 送ったかの印／`typed` 入力文字のうち送る分

#### `_slash_capture(self) -> str | None`（3741 行）
概要：tmux の画面の文字を 1 回取る。Bridge（Claude Code とつなぐ部品）に tmux が無い・取る関数が無いときは None。tmux の画面を読む共通の口で、状態の読み取りも使う。
- 引数：なし
- 戻り値：`str | None`。画面の文字、または None
- 主な変数：`tmux` `self.bridge.tmux`／`capture` その `capture` 関数

#### `_read_slash(self, now: float) -> None`（3749 行）
概要：画面を 1 回読んで窓の状態を決める。「Esc to」という案内が見えたらパネルが出ているとみなす。パネルを見たあと案内が `SLASH_CLOSE_SEC` 消えたら閉じる。一度もパネルを見ないまま `SLASH_STATIC_SEC` たったら、結果だけの窓に切り替える。画面が読めないときも同様に扱い、パネルを見ていなければ「(画面を読めませんでした)」（`t("slash_read_failed")`）の 1 行の窓にする。「Esc to」は英語の画面の文なので、**英語の画面が前提**。
- 引数：
  - `now`（`float`）：現在時刻
- 戻り値：なし
- 主な変数：`self._slash_next_read` を now＋`SLASH_POLL_SEC` に／`self._slash_seen_panel` パネルを見たか／`self._slash_gone_since` 案内が消え始めた時刻／`self._slash_started` 窓を開いた時刻／`lines` 画面の行

#### `_set_slash_lines(self, lines: list[str]) -> None`（3780 行）
概要：窓の行を入れ替える。ユーザーが動かしていなければ一番下へ、動かしていれば位置を保つ（範囲内に収める）。
- 引数：
  - `lines`（`list[str]`）：新しい行
- 戻り値：なし
- 主な変数：`self._slash_lines`／`self._slash_scroll` 先頭の行の番号／`self._slash_user_scrolled` ユーザーが動かしたか

#### `_slash_rows(self) -> list[str]`（3788 行）
概要：窓の行を `SLASH_COLS` 桁で折り返した表示用の行にする。
- 引数：なし
- 戻り値：`list[str]`。折り返した行

#### `_slash_max_scroll(self) -> int`（3795 行）
概要：窓の先頭の行の番号の上限。最後の行まで見える位置で、`max(0, 行数 - SLASH_BODY_ROWS)`。
- 引数：なし
- 戻り値：`int`

#### `_set_slash_scroll(self, value: int) -> None`（3799 行）
概要：窓の先頭の行を value にする（範囲内に収める）。一番下まで戻したら `_slash_user_scrolled` を False にして、また下に付いていく。
- 引数：
  - `value`（`int`）：先頭にしたい行の番号
- 戻り値：なし
- 主な変数：`self._slash_scroll`／`self._slash_user_scrolled`

#### `_scroll_slash(self, delta: int) -> None`（3805 行）
概要：窓の中身を delta 行動かす。
- 引数：
  - `delta`（`int`）：動かす行数（負は上）
- 戻り値：なし

#### `_slash_track(self) -> tuple[int, int, int, int]`（3809 行）
概要：窓のスクロールバーの溝の長方形を返す。窓の右端の内側で、画面の行の範囲。
- 引数：なし
- 戻り値：`(x, y, 幅, 高さ)`

#### `_slash_thumb(self, total: int) -> tuple[int, int]`（3818 行）
概要：スクロールバーのつまみの位置と長さを計算する。長さは見えている割合（最小 6）。
- 引数：
  - `total`（`int`）：全部の行数（`SLASH_BODY_ROWS` より多いときだけ使う）
- 戻り値：`(y, 高さ)`
- 主な変数：`thumb_h` つまみの高さ／`max_scroll` 動かせる最大の行数

#### `_slash_click(self, sx: int, sy: int) -> None`（3826 行）
概要：窓の上のクリック。溝を押したら 1 画面ぶん動かし、つまみを押したら引きずり開始。窓の外のクリックは、結果だけの窓のときだけ閉じる（パネルのときは何もしない）。
- 引数：
  - `sx`（`int`）：クリックの画面 x
  - `sy`（`int`）：クリックの画面 y
- 戻り値：なし
- 主な変数：`self._slash_drag` つまみを引きずり中か／`total` 折り返した行数

#### `_update_slash_drag(self) -> None`（3845 行）
概要：つまみを押したまま動かしている間、マウスの y 位置から窓の先頭の行を決める。ボタンを離したら引きずりを止める。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._slash_drag`／`span` つまみが動ける幅／`frac` つまみ位置の割合（0〜1）

#### `_slash_wheel(self, wheel: int) -> None`（3861 行）
概要：マウスが窓の上にあるとき、ホイールで窓の中身を動かす（3D はズームしない）。窓の外では何もしない。
- 引数：
  - `wheel`（`int`）：ホイールの回転量
- 戻り値：なし
- 主な変数：`DLG_WHEEL_ROWS`（1 回のホイールで動く行数の定数）を使って `-DLG_WHEEL_ROWS * wheel` 行動かす

#### `_draw_slash(self) -> None`（3866 行）
概要：コマンドの窓を描く。背景の黒を半透明（`SLASH_DITHER` = 0.75 の dither）、枠、1 行目に「コマンド：…」、画面の行、スクロールバー、一番下に案内。フォントが無ければ枠までで戻る。
- 引数：なし
- 戻り値：なし
- 主な変数：`rows` 折り返した行／`guide` 結果だけの窓なら `SLASH_GUIDE_STATIC`、パネルなら `SLASH_GUIDE_PANEL`

#### 今のモデル・effort と選ぶメニュー（--claude のとき。/model と /effort を入力欄で打ったときに使う）

#### `_note_state(self, text: str) -> None`（3895 行）
概要：会話記録の /model・/effort の結果の文から、今のモデルと effort を覚える（ほかの場所から打たれた分も含む）。正規表現（文字のパターン）`SET_MODEL_RE`・`SET_EFFORT_RE` で探す。
- 引数：
  - `text`（`str`）：記録の文
- 戻り値：なし
- 主な変数：`self._cur_model`／`self._cur_effort`

#### `_read_state_screen(self) -> bool`（3904 行）
概要：tmux の画面から今のモデルと effort を読む（`STATE_RE`）。effort が画面に無ければ `STATE_DEFAULT_EFFORT` を入れる。
- 引数：なし
- 戻り値：`bool`。見つけたら True。画面が読めない・見つからないなら False
- 主な変数：`self._cur_model`（`"グループ1 グループ2"` の形）／`self._cur_effort`

#### `_update_state_read(self, dt: float) -> None`（3917 行）
概要：始業したあとの読み取り。`STATE_READ_EVERY_SEC` ごとに画面を読み、見つかるか `STATE_READ_SEC` たったら止める。
- 引数：
  - `dt`（`float`）：前のフレームからの秒
- 戻り値：なし
- 主な変数：`self._state_left` 読み取りの残り時間（0 なら止まっている）／`self._state_next` 次の読み取りまでの秒

#### `_forget_state(self) -> None`（3929 行）
概要：終業・セッション消失のあと、今のモデルと effort を "?" に戻し、読み取りとメニューを止める。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._cur_model`・`self._cur_effort` を "?"／`self._state_left` を 0／`self._usage_start_armed` を False／`self._usage_after_turn_left` を 0／`_close_menu()` を呼ぶ

#### `_is_menu_command(self, text: str) -> bool`（3938 行）
概要：送る文が選ぶメニューを開く文か判定する。前後の空白を除いて、ちょうど `/model` か `/effort`。
- 引数：
  - `text`（`str`）：送る文
- 戻り値：`bool`

#### `_menu_choices(self, kind: str) -> tuple[tuple[str, str], ...]`（3942 行）
概要：メニューの選択肢の表を返す。
- 引数：
  - `kind`（`str`）："model" か "effort"
- 戻り値：`MENU_MODEL_CHOICES` か `MENU_EFFORT_CHOICES`（各要素は (表示名, 引数)）

#### `_menu_is_current(self, kind: str, choice: tuple[str, str]) -> bool`（3946 行）
概要：選択肢が今の値か。モデルは表示名と今のモデルを、effort は引数と今の effort を比べる。
- 引数：
  - `kind`（`str`）："model" か "effort"
  - `choice`（`tuple[str, str]`）：(表示名, 引数)
- 戻り値：`bool`

#### `_menu_height(self, count: int) -> int`（3953 行）
概要：メニューの高さ。1 行目は題、最後の行は案内なので、選択肢＋2 行ぶんに余白。
- 引数：
  - `count`（`int`）：選択肢の数
- 戻り値：`int`。`UI_PAD * 2 + (count + 2) * UI_LINE_H`

#### `_open_menu(self, kind: str) -> None`（3957 行）
概要：選ぶメニューを開く。選択している行は今の値の行（分からなければ先頭）。モードは PROMPT のまま。
- 引数：
  - `kind`（`str`）："model" か "effort"
- 戻り値：なし
- 主な変数：`self._menu` 開いているメニューの種類（None なら閉じている）／`self._menu_sel` 選んでいる行

#### `_close_menu(self) -> None`（3965 行）
概要：選ぶメニューを閉じる。何も送らない。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._menu` を None に

#### `_decide_menu(self) -> None`（3969 行）
概要：選んでいる値を /model か /effort の引数として送り、メニューを閉じる。送りかたは通常の送信と同じ（許可の待ち・始業前の扱いは `_send_to_claude` の中）。
- 引数：なし
- 戻り値：なし
- 主な変数：`kind` 開いているメニュー／`arg` 選んだ引数。`/{kind} {arg}` を `_send_to_claude` に渡す

#### `_update_menu(self) -> None`（3978 行）
概要：メニューの 1 フレーム。許可の依頼が来ている・許可の処理中なら何も送らず閉じる。↑↓で選ぶ（押しっぱなしで繰り返し）、Enter で決める、Esc で閉じる。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._perm_pending`／`self._perm_lock`（許可の状態）／`self._menu_sel`

#### `_menu_click(self, sx: int, sy: int) -> None`（3996 行）
概要：メニューのクリック。メニューの外なら何も送らず閉じる。選んでいない行ならその行を選び、選んでいる行をもう一度押したら決める。
- 引数：
  - `sx`（`int`）：クリックの画面 x
  - `sy`（`int`）：クリックの画面 y
- 戻り値：なし
- 主な変数：`row` クリックした選択肢の番号（1 行目は題なので 1 を引く）

#### `_draw_menu(self) -> None`（4012 行）
概要：選ぶメニューを描く。位置と背景の透かしはコマンドの窓と同じ。今の値の行の頭に `*`、選んでいる行は `>` と白い帯に黒い字。一番下に `MENU_GUIDE`。
- 引数：なし
- 戻り値：なし
- 主な変数：`label` 行の文字（モデルは `[引数]` も付く）／`height` メニューの高さ

#### 会話のダイアログ（3D の範囲に出す。--claude で、メインかサブエージェントと話しているとき）

#### `_talk_dialog_partner(self) -> int | None`（4045 行）
概要：ダイアログを出す相手の番号。`--claude` で、会話の相手がメインかサブエージェント（role が "sub"）のときだけ返す。
- 引数：なし
- 戻り値：`int | None`。相手の番号、出さないときは None
- 主な変数：`self.talk_partner` 会話の相手

#### `_talk_dialog_lines(self, partner: int) -> list[tuple[str, int]]`
概要：ダイアログの中身を `DLG_COLS` 桁で折り返した（字, 色）の行にする（最後の固定の案内の行は含まない）。メインに許可の依頼が来ていれば、その内容（道具名・入力）か「いつも許可」の確認を出す（色は `TEXT_COLOR`）。依頼が無いメインは `_talk_page_lines()`（今のページ）を返す。サブは最後の 1 行を出す。
- 引数：
  - `partner`（`int`）：相手の番号
- 戻り値：`list[tuple[str, int]]`（字, 色）
- 主な変数：`self._perm_pending`（許可の依頼の列。先頭を使う）／`self._perm_always_confirm`／`self._last_line`（サブの最後の 1 行）

#### `_talk_page_lines(self) -> list[tuple[str, int]]`
概要：メインとの会話のダイアログの中身（今見ているページ）。1 行目は題（ページが無ければ `t("main_name")`、あれば `t("dialog_main_page", page=今のページ番号, total=ページ数)`。例「メイン  2/3」）。ページが無いときは題のあとに `t("talk_none_yet")` だけ。ページがあるときは、**プロンプトが空でなければ**「`> `＋プロンプト」の行（色は知らせなら `NOTICE_COLOR`、そうでなければ `TALK_PROMPT_COLOR`。改行ごとに折り返す）とその下の空行を出す。**プロンプトが空のページ（Reply だけのページ）は、「`> `」の行と空行を出さない**（作者が決めた）。そのあとに返事（`replies` を空行 1 つで区切って並べる）。返事がまだ無ければ `t("talk_waiting_reply")`（`NOTICE_COLOR`）。
- 戻り値：`list[tuple[str, int]]`
- 主な変数：`self._pages`（`TalkPage` の列）／`self._page_index`（見ているページ。None は最新）

#### `_dlg_visible_rows(self, partner: int) -> int`（4080 行）
概要：ダイアログで中身を出せる行数。メインに許可の依頼があるときは、最後の行を Y・N・T の案内に使うので 1 行少ない。
- 引数：
  - `partner`（`int`）：相手の番号
- 戻り値：`int`。`DLG_BODY_ROWS` か `DLG_BODY_ROWS - 1`

#### `_dlg_track(self) -> tuple[int, int, int, int]`（4086 行）
概要：ダイアログのスクロールバーの溝の長方形。右端の内側。
- 引数：なし
- 戻り値：`(x, y, 幅, 高さ)`

#### `_dlg_thumb(self, total: int, visible: int) -> tuple[int, int]`（4090 行）
概要：ダイアログのスクロールバーのつまみの位置と長さ。
- 引数：
  - `total`（`int`）：全部の行数
  - `visible`（`int`）：見えている行数（total > visible のとき）
- 戻り値：`(y, 高さ)`

#### `_scroll_talk(self, partner: int, delta: int) -> None`（4098 行）
概要：ダイアログの中身を delta 行動かす（0 から最後の行までに収める）。
- 引数：
  - `partner`（`int`）：相手の番号
  - `delta`（`int`）：動かす行数
- 戻り値：なし
- 主な変数：`self._dlg_scroll` ダイアログの先頭の行の番号

#### `_click_talk_dialog(self, partner: int, sx: int, sy: int) -> None`（4104 行）
概要：ダイアログの上のクリック。つまみを押したら引きずり開始、溝を押したら 1 画面ぶん動かす。行数が見える数以下なら何もしない。
- 引数：
  - `partner`（`int`）：相手の番号
  - `sx`（`int`）：クリックの画面 x
  - `sy`（`int`）：クリックの画面 y
- 戻り値：なし
- 主な変数：`self._dlg_drag` つまみを引きずり中か

#### `_drag_talk_dialog(self, partner: int, sy: int) -> None`（4119 行）
概要：つまみを押したまま動かしたとき、つまみの位置から中身の先頭の行を決める。
- 引数：
  - `partner`（`int`）：相手の番号
  - `sy`（`int`）：マウスの画面 y
- 戻り値：なし
- 主な変数：`self._dlg_scroll`／`frac` つまみ位置の割合

#### `_update_talk_dialog(self) -> None`（4131 行）
概要：毎フレーム。ダイアログが出ていないときはスクロールと引きずりを戻す。つまみを押したままなら動かし、ボタンを離したら引きずりを止める。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._dlg_scroll`・`self._dlg_drag`

#### `_update_talk_dialog_keys(self) -> None`（4144 行）
概要：PageUp・PageDown でダイアログの中身を 1 画面ぶん動かす（WALK のとき。モードの判定は呼ぶ側）。
- 引数：なし
- 戻り値：なし

#### `_draw_talk_dialog(self, partner: int) -> None`（4155 行）
概要：会話のダイアログを 3D の範囲に半透明の黒い箱で描く。中身、許可の依頼のときの案内（Y・N・T）、スクロールバー。フォントが無ければ何も描かない。「いつも許可」の質問の行は色を変える。
- 引数：
  - `partner`（`int`）：相手の番号
- 戻り値：なし
- 主な変数：`lines`／`visible`／`guide` 許可の状態で `PERM_ALWAYS_CONFIRM_TEXT`・`PERM_KEYS_ALWAYS_TEXT`・`PERM_KEYS_TEXT` から選ぶ

#### Claude とのつなぎ（--claude）

#### `_update_claude_keys(self) -> None`（4185 行）
概要：F1（始業・終業）と、「前のセッションが残っています」のダイアログの 1〜3 を処理する。ダイアログが出ている間は 1〜3 以外を受け付けない。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._dialog`（ダイアログが出ているか）／1 は "resume"、2 は "restart"、3 は ""（やめる）を `_choose_dialog` に渡す

#### `_update_claude(self, dt: float) -> None`（4196 行）
概要：--claude の毎フレームの処理。セッションの生存確認、会話記録のイベント処理、状態の読み取り、許可の依頼、利用制限（/usage）、終業の待ち、吹き出しの時間切れ、サブの帰る時間、メインの帰る時間、ドアの自動開閉。`self.bridge` が None なら何もしない。
- 引数：
  - `dt`（`float`）：前のフレームからの秒
- 戻り値：なし
- 主な変数：`self._session_check_left` セッション確認までの秒（`SESSION_CHECK_SEC` で戻す）／`self._handoff_left` 終業の引き継ぎの待ち（切れたら `_finish_ending`）／`self._bubble_left`／`self._leave_timers` 席の番号→帰るまでの秒／`self._idle_main` メインが暇な秒（`IDLE_LEAVE_SEC` で帰る）

#### `_on_event(self, event: object) -> None`（4234 行）
概要：会話記録のイベント 1 つを画面の動きと履歴に反映する。種類は Prompt（人が送った文）・Tool（道具の使用）・Reply（返事）・TurnEnd（返事の終わり）・SubagentStart・SubagentEnd。サブの開始では、帰るのを待っている人がいれば再利用し、いなければ空き席を探して入室させる。
- 引数：
  - `event`（`object`）：上の種類のどれか
- 戻り値：なし
- 主な変数：`main` メインの Agent／`self._busy_text`（番号→作業中の吹き出しの文）／`self._sub_map`（サブの agent_id→席の番号）／`self._pending_reply` 作業が終わってから出す返事／`self._last_sent` 自分で送った文（履歴に二重に出さない）／`self._human_text` 人間の吹き出しの文

#### `_find_reusable_sub(self) -> int | None`（4338 行）
概要：再利用できるサブの席の番号を返す。見えていて、役が "sub" で、作業が終わって帰るのを待っている（`_leave_timers` にいる）人で、部屋を出る途中（LEAVING）でない人。
- 引数：なし
- 戻り値：`int | None`。席の番号、無ければ None

#### `_button_rect(self, label: str) -> tuple[int, int, int, int]`（4351 行）
概要：始業・終業ボタンの長方形。左上の人数表示の下。幅は文字の幅＋8。
- 引数：
  - `label`（`str`）：ボタンの文字
- 戻り値：`(x, y, 幅, 高さ)`。x は 4、y は `BUTTON_Y`

#### `_claude_click(self, sx: int, sy: int) -> bool`（4357 行）
概要：--claude のときのクリック（ボタンとダイアログ）。ダイアログが出ている間は、ほかのクリックを受けない。
- 引数：
  - `sx`（`int`）：クリックの画面 x
  - `sy`（`int`）：クリックの画面 y
- 戻り値：`bool`。処理したら True。--claude でないときや、ボタンを押していないときは False
- 主な変数：`CLAUDE_DIALOG_OPTIONS`（選択肢の表）／`label` 始業中なら `t("button_clock_out")`、そうでなければ `t("button_clock_in")`（日本語のとき「[F1] 終業」「[F1] 始業」、英語のとき「[F1] Clock out」「[F1] Clock in」）／選択肢の文は `t(キー)`

#### `_head_point(self, agent: Agent) -> tuple[float, float] | None`（4373 行）
概要：人の頭の画面上の位置。3D の範囲の外・カメラの後ろなら None。
- 引数：
  - `agent`（`Agent`）：対象の人
- 戻り値：`(x, y)` または None

#### `_draw_bubble(self, point: tuple[float, float], shown: str) -> None`（4388 行）
概要：白い吹き出し（黒い文字）を点の真上に描く。下に点を指す三角が付く。フォントが無い・文が空・画面の上に収まらないときは描かない。
- 引数：
  - `point`（`tuple[float, float]`）：指す点（画面）
  - `shown`（`str`）：吹き出しの文
- 戻り値：なし

#### `_draw_claude(self) -> None`（4404 行）
概要：--claude のときの 2D の表示。始業・終業ボタン、前のセッションのダイアログ、メインの 6 秒の吹き出し、作業中の吹き出し、許可待ちの「！」、人間の吹き出し、名前の札、話しかけたときの右上の小さな箱、会話のダイアログ（またはコマンドの窓）、選ぶメニュー（一番上）の順に描く。
- 引数：なし
- 戻り値：なし
- 主な変数：`perm_waiting` 許可の依頼があり、メインが見えているか（このとき、メインの吹き出しは出さず「！」を出す）／`bubble_shown`／`busy_shown`（吹き出しを出した番号。名前の札を省く）／`BUBBLE_CHARS`（吹き出しの最大文字数）

#### 部屋の世界の更新

#### `_update_door(self, dt: float) -> None`（4506 行）
概要：ドアの角度を目標（開く 90 度〔`DOOR_OPEN_ANGLE`〕・閉じる 0 度）へ `DOOR_SPEED` で近づける。目標を行き過ぎない。
- 引数：
  - `dt`（`float`）：前のフレームからの秒
- 戻り値：なし
- 主な変数：`self.door_open` 目標が開くか／`self.door_angle` 今の角度

#### `_update_rate_keys(self) -> None`（4515 行）
概要：数字キー 1〜4 で利用制限の値を `RATE_KEY_STEP` ずつ変える。1 は 5 時間を減らし、2 は増やす。3 は週間を減らし、4 は増やす。押したら以後は JSON を読まない。--claude のときは何もしない。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.manual_limits` 手動で変えたか／`self.five_hour`・`self.seven_day` 利用制限の割合（0〜100）

#### `_update_rate_limits(self) -> None`（4535 行）
概要：手動で変えていなければ、`_reload_every` フレームごとに JSON を読み直す。--claude のときは読まない。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._reload_count` フレームの数え／`self._reload_every` 読み直す間隔

#### `reload_rate_limits(self) -> None`（4544 行）
概要：JSON（`self.rate_json_path`）を読み、`five_hour` と `seven_day` に used_percentage を 0〜100 に収めて入れる。ファイルが無い・壊れている・項目が無い・数でないときはその値を 0.0 にする。例外は出さない。
- 引数：なし
- 戻り値：なし
- 主な変数：`data` 読んだ JSON／`_read_used_percentage`（モジュールの関数）で取り出す

#### `_sync_scene_values(self) -> None`（4558 行）
概要：利用制限の値とドアの角度を OfficeRoot（`self.scene`）に書き込む。描画がそれを読む。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.scene.five_hour`・`seven_day`・`door_angle`

#### `_update_view(self, dt: float) -> None`（4564 行）
概要：カーソルキーで視点を回す。押している間ずっと効くよう `pyxel.btn` を使う。→で yaw（左右の向き）を増やし、←で減らす。↑で pitch（上下の傾き）を増やし、↓で減らす。変わったら `_apply_camera` で視点を更新する。
- 引数：
  - `dt`（`float`）：前のフレームからの秒
- 戻り値：なし
- 主な変数：`self.cam_yaw`（0〜360 度で一周）／`self.cam_pitch`（`CAM_PITCH_MIN`〜`CAM_PITCH_MAX` に収める）

#### `_resolve_collisions(self) -> None`（4580 行）
概要：障害物・キャラどうし（人間を含む）・床の範囲の順に押し出し、結果を各 pos に書き戻す。この 3 つを 1 組として `COLLISION_ITERATIONS` 回繰り返す。WORKING のキャラは自分の席の机と椅子を無視する（座るため）。着席中と行き先の立つ場所にいるキャラ、人間は動かさない（相手のほうが押し出される）。部屋を出る人（LEAVING）はほかの人と押し合わない。
- 引数：なし
- 戻り値：なし
- 主な変数：`bodies` 押し出す対象（見えている人＋人間）／`owners` 障害物の持ち主の席の番号（人間は -1）／`fixed` 動かさない印／`xs`・`zs` 作業中の位置／`leaving` 部屋を出る人の印／`push_out_of_rect`・`push_out_of_circle`・`separate`（モジュールの関数）を使う

#### `_check_stuck(self, prev_xz: list[tuple[float, float]], dt: float) -> None`（4638 行）
概要：歩いているのに予定の `STUCK_RATIO` 未満しか進めないフレームが `STUCK_SEC` 続いたら、目標か道を選び直させる（`_repath`）。予定どおり進めたフレームがあれば計っていた時間を 0 に戻す。office では行き先へ向かう人・席へ戻る人・作業で席へ向かう人も数え、状態が変わったら計り直す。道探しの順番待ちの間と、横へよけている間は数えない。見えていない人も数えない。
- 引数：
  - `prev_xz`（`list[tuple[float, float]]`）：前のフレームの各人の位置（x, z）
  - `dt`（`float`）：前のフレームからの秒
- 戻り値：なし
- 主な変数：`self._stuck_time`（番号→引っかかっている秒）／`self._stuck_count`（番号→続けて引っかかった回数）／`self._stuck_state`（番号→最後に見た状態）／`moved` 実際に進んだ距離

#### `_stuck_counted(self, agent: Agent) -> bool`（4670 行）
概要：引っかかりを数える状態か。WANDER はいつでも。office（`layout.has_props`）では GOING・RETURNING・WORKING も数える。
- 引数：
  - `agent`（`Agent`）：対象の人
- 戻り値：`bool`

#### `_repath(self, i: int) -> None`（4676 行）
概要：引っかかった人 i の目標か道を選び直す。WANDER は目標を選び直す。それ以外は、同じ状態で `SIDESTEP_AFTER` 回続けて引っかかったら、近くの人から離れる向きへ横によける（道は探さない）。よける向きが無いときは、近くの人をよけて道を探し直し、探せなければ `_path_failed`。
- 引数：
  - `i`（`int`）：人の番号
- 戻り値：なし
- 主な変数：`self.stat_replans`・`self.stat_sidesteps`（統計の回数）／`self._stuck_count[i]`／`agent.avoid_near` 次の道探しで近くの人もよけるか

#### `_sidestep_direction(self, i: int) -> tuple[float, float] | None`（4699 行）
概要：引っかかった人 i が横へよける向き（単位ベクトル）を決める。いちばん近くて `NAV_NEAR_DIST` 以内の人 j から離れる向きを基準に、その左右（`SIDESTEP_PROBE` 先）で通れるほうを選ぶ。両方通れなければ離れる向きそのものを使う。よけるのは、i が j より番号が後ろか、j が席や立つ場所で動かない人のときだけ（動く人どうしが同時によけないため）。
- 引数：
  - `i`（`int`）：人の番号
- 戻り値：`tuple[float, float] | None`。向き (x, z)。近くに人がいない・重なって向きが決まらない・よけなくてよいとき・`self.nav` が無いときは None
- 主な変数：`self.nav` 道探しの部品（`_point_free` で通れるか調べる）／`nearest`・`nearest_dist` いちばん近い人とその距離

#### `_people_for(self, i: int) -> list[tuple[float, float]]`（4733 行）
概要：人 i が道を探すときに避けるほかの人の中心（x, z）の列を作る。席に着いている人と行き先にいる人（`is_fixed`）は必ず入れる。`avoid_near` が True なら `NAV_NEAR_DIST` 以内の人も入れる。人間は会話中なら必ず、そうでなくても avoid_near で近ければ入れる。最後に `avoid_near` を False に戻す（副作用）。
- 引数：
  - `i`（`int`）：人の番号
- 戻り値：`list[tuple[float, float]]`

#### `_request_path(self, i: int) -> None`（4757 行）
概要：道が要る人 i を列（`self._nav_queue`）の後ろに並べる。すでに並んでいれば二重に並べず、列の位置も変えない。
- 引数：
  - `i`（`int`）：人の番号
- 戻り値：なし

#### `_serve_nav_queue(self) -> None`（4762 行）
概要：列の先頭から順に道を探す。1 フレームに探すのは `NAV_MAX_PER_FRAME` 人まで。道がもう要らなくなった人（`path_wait` が False）は数えずに捨てる。見つからなければ `_path_failed`。
- 引数：なし
- 戻り値：なし
- 主な変数：`served` このフレームで探した人数／`self._nav_queue`（deque。両端の出し入れが速い列）

#### `_path_failed(self, i: int) -> None`（4773 行）
概要：道が見つからなかった人 i の後始末。行き先へ行く人（GOING）は行き先の予約を外し、あきらめた数を 1 増やす。
- 引数：
  - `i`（`int`）：人の番号
- 戻り値：なし
- 主な変数：`self.spot_manager`（行き先の予約係）／`self.stat_give_ups` あきらめた数

#### `_start_next_work(self) -> None`（4782 行）
概要：次の番号の人を作業状態にする。行き先にいた人の会話の状態はリセットする。--claude で見えていない人はドアから入らせ、それ以外は `_begin_work`。道探しの列に残った古い依頼は、道が要らなければ外す。最後に `next_index` を 1 進める。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.next_index` 次に作業させる番号（人数で一周）／`self._chat[index]` を新しい `Chatter` に

#### `_update_wanderers(self, timer_dt: float) -> None`（4798 行）
概要：うろついている人（WANDER）の休みとうろつき時間を数え、`OUTING_WANDER_SEC` たったら行き先を予約して GOING にする（office だけ）。休みの間はうろつき時間を数えず休みを減らす。行き先が取れなければ、うろつきを続けて後でまた選ぶ。会話の相手と見えていない人は数えない。
- 引数：
  - `timer_dt`（`float`）：早回し倍率（`--time-scale`）をかけた秒
- 戻り値：なし
- 主な変数：`agent.cooldown` 休みの残り秒／`agent.wander_time` うろついた秒／`manager.reserve(i)` 行き先の予約（(Spot, 枠) か None を返す）

#### `_update_spot_groups(self, timer_dt: float) -> None`（4825 行）
概要：行き先にいる人（AT_SPOT）を Spot（行き先）ごとに数える。1 人なら 1 人用の姿勢にして中心を向かせ、`ALONE_SEC` たったら席へ戻す。2 人以上なら会話として `_update_talk` を呼び、`TALK_SEC` たった人を戻す。人がいなくなった行き先の話し手の記録は消す（office だけ）。
- 引数：
  - `timer_dt`（`float`）：早回し倍率をかけた秒
- 戻り値：なし
- 主な変数：`groups`（行き先の名前→(Spot, 人の番号の列)）／`self._speakers`（行き先の名前→今の話し手）／`self._speaker_timers`／`agent.alone_time`・`agent.talk_time` 1 人・会話でいた秒／`leaving` 戻す人

#### `_update_talk(self, name: str, members: list[int], t: float) -> None`（4863 行）
概要：会話中の行き先の話し手を決め、話し手の身ぶりと聞き手の姿勢・向きを決める。話し手は `SPEAKER_MIN_SEC`〜`SPEAKER_MAX_SEC` ごとに乱数で交代する。身ぶり（`GESTURE_KINDS`）は一定時間ごとに選び直し、聞き手は一定時間ごとに飲み物を飲むか立つかを選ぶ。話し手は聞き手か机を、聞き手は話し手を向く。
- 引数：
  - `name`（`str`）：行き先の名前
  - `members`（`list[int]`）：そこにいる人の番号
  - `t`（`float`）：経過した秒
- 戻り値：なし
- 主な変数：`self.rng` 乱数／`chat`（`self._chat[i]` の `Chatter`。`gesture`・`gesture_timer`・`gesture_listener`・`listen_timer`・`listen_drink`）

#### `_leave_spot(self, i: int) -> None`（4914 行）
概要：行き先の予約を外し、席へ戻る道を探す。道が無ければあきらめて WANDER に戻る（`begin_returning` が False のとき `stat_give_ups` を増やす）。
- 引数：
  - `i`（`int`）：人の番号
- 戻り値：なし

#### `_is_held(self, i: int) -> bool`（4922 行）
概要：人 i が会話の相手で、作業中ではないか（止めて動かさない人か）を返す。作業中の相手は通常どおり動く。
- 引数：
  - `i`（`int`）：人の番号
- 戻り値：`bool`

#### `_stationary_people(self) -> list[tuple[float, float]]`（4926 行）
概要：座っている人と行き先にいる人の中心 (x, z) の列。人間の道探しで避ける人。
- 引数：なし
- 戻り値：`list[tuple[float, float]]`

#### `_overlaps_any_obstacle(self, x: float, z: float, margin: float = AGENT_RADIUS) -> bool`（4930 行）
概要：点 (x, z) が、いずれかの障害物（長方形・丸）を margin だけ広げた範囲に入っているか。
- 引数：
  - `x`（`float`）：点の x
  - `z`（`float`）：点の z
  - `margin`（`float`）：広げる幅。既定 `AGENT_RADIUS`
- 戻り値：`bool`
- 主な変数：`self.obstacles`（長方形の障害物。`.rect` に xmin・xmax・zmin・zmax）／`self.circles`（丸い障害物 (cx, cz, 半径)）

#### `_spot_free(self, x: float, z: float, partner: int | None = None) -> bool`（4944 行）
概要：人間が立つ点 (x, z) が空いているか。うろつきの範囲の内側で、障害物（`AGENT_RADIUS + TALK_CLEAR/2` だけ広げた範囲）に入らず、人から離れていること。相手 partner 以外の人からは `2*AGENT_RADIUS + TALK_CLEAR` 以上、相手からは `2*AGENT_RADIUS` 以上。
- 引数：
  - `x`（`float`）：点の x
  - `z`（`float`）：点の z
  - `partner`（`int | None`）：会話の相手の番号。既定 None
- 戻り値：`bool`

#### `_talk_spot(self, i: int, with_desk: bool = True) -> tuple[float, float] | None`（4964 行）
概要：相手 i と話すために人間が立つ位置を決める。相手が作業中（WORKING）で with_desk のときは、まず机の正面（席の反対側、`TALK_FRONT_GAP` 離れた点）を候補にする。そのあと相手のまわり `TALK_SIDE_DIST` の `TALK_DIRECTIONS` 方向を、相手の正面に近い順に候補にする。空いている最初の候補（`_spot_free`）を返す。
- 引数：
  - `i`（`int`）：相手の番号
  - `with_desk`（`bool`）：机の正面を候補に入れるか。既定 True
- 戻り値：`tuple[float, float] | None`。(x, z)、無ければ None
- 主な変数：`candidates` 候補の位置の列／`dirs`（正面との内積, 方向 x, 方向 z）を内積の大きい順に並べたもの／`self.layout.desks[i]` 席 i の机

#### クリックと会話

#### `handle_click(self, sx: int, sy: int) -> None`（5000 行）
概要：3D の範囲のクリック（office だけ）。先に人を当て、当たれば会話を始める（会話中に別の人なら今の会話を終えてから）。当たらなければ床に当て、そこへ人間を歩かせる（会話中なら先に終える）。同じ相手なら何もしない。3D の範囲の外（`sy >= VIEW3D_H`）や、人間のいない配置では何もしない。クリックで `self.mode` を WALK に戻し、日本語入力の状態もリセットする。
- 引数：
  - `sx`（`int`）：クリックの画面 x
  - `sy`（`int`）：クリックの画面 y
- 戻り値：なし
- 主な変数：`eye`・`direction` 画面の点を通る 3D の線／`picked` 当たった人の番号／`point` 床との交点

#### `screen_ray(self, sx: float, sy: float, vx: int, vy: int, vw: int, vh: int) -> tuple[Vec3, Vec3]`（5031 行）
概要：画面の点を通る 3D の線を返す。`_apply_camera` と同じ目の位置・向きを使い、fov は縦方向の度。
- 引数：
  - `sx`（`float`）：画面 x
  - `sy`（`float`）：画面 y
  - `vx`（`int`）：3D を描く範囲の左 x
  - `vy`（`int`）：同、上 y
  - `vw`（`int`）：同、幅
  - `vh`（`int`）：同、高さ
- 戻り値：`(目の位置, 向きの単位ベクトル)`
- 主な変数：`f`（前）・`r`（右）・`u`（上）カメラの 3 軸／`k` 画角の半分のタンジェント

#### `floor_hit(self, eye: Vec3, direction: Vec3) -> tuple[float, float] | None`（5049 行）
概要：線と床（y=0）の交わる (x, z)。線が上を向いている（direction.y が 0 以上）なら None。
- 引数：
  - `eye`（`Vec3`）：線の始点
  - `direction`（`Vec3`）：線の向き
- 戻り値：`tuple[float, float] | None`

#### `pick_agent(self, eye: Vec3, direction: Vec3) -> int | None`（5056 行）
概要：線が当たる人のうち、いちばん手前の人の番号を返す。各人を中心 (x, `PICK_CENTER_Y` + body_y, z)・半径 `PICK_RADIUS` の球として、線と球の交わりを解いて調べる。見えていない人は選べない。direction は単位ベクトルであること。
- 引数：
  - `eye`（`Vec3`）：線の始点
  - `direction`（`Vec3`）：線の向き（単位ベクトル）
- 戻り値：`int | None`。当たらなければ None
- 主な変数：`best`・`best_t` 今までで最も手前の人とそこまでの距離／`disc` 判別式（負なら当たらない）

#### `start_talk(self, i: int) -> None`（5082 行）
概要：人 i と会話を始める（office だけ）。立つ位置が無ければ何もしない。会話の前の視点を覚え、人間をその位置へ瞬間移動して相手を向かせ、相手を止め（`hold`）、会話のカメラへの切り替えを始める。
- 引数：
  - `i`（`int`）：相手の番号
- 戻り値：なし
- 主な変数：`self.talk_partner` 相手の番号／`self._saved_view` 会話の前の視点（戻しの切り替え中なら入れ直さない）／`self._talk_seat_moved` 座ってからの歩き直しを済ませたか／`self._follow_replan` 歩き直しまでの秒を 0 に

#### `end_talk(self) -> None`（5101 行）
概要：会話を終える（会話していなければ何もしない）。相手は動き出し（`hold` を False）、カメラは会話の前の視点へ切り替えて戻す。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.talk_partner` を None に／`self._saved_view`

#### `_talk_view(self) -> tuple[Vec3, float, float, float]`（5112 行）
概要：会話のカメラの目標 (target, yaw, pitch, dist) を返す。2 人の真ん中を見る。2 人を結ぶ線に直角な左右のうち、部屋（うろつきの範囲）の中に入るほうから見る。両方入る・両方入らないときの選びかたは、z の差が 1 未満なら x の小さいほう、そうでなければ z の大きいほう（部屋の手前）。最後に `_nudge_talk_view` で、2 人が画面で重ならないようずらす。会話相手がいなければ今のカメラをそのまま返す。
- 引数：なし
- 戻り値：`(target, yaw, pitch, dist)`
- 主な変数：`gap` 2 人の距離／`dist` カメラの距離（`TALK_CAM_MIN_DIST` と `gap * TALK_CAM_DIST_RATIO` の大きいほう）／`dirs` 直角な 2 つの向き／`inside` それぞれの目の位置が部屋の中か

#### `_nudge_talk_view(self, view: tuple[Vec3, float, float, float]) -> tuple[Vec3, float, float, float]`（5156 行）
概要：会話の視点で 2 人の頭の画面上の横の差が `TALK_MIN_SCREEN_GAP` 以上になるよう、yaw を `TALK_YAW_OFFSETS` の順にずらす。どれもだめなら差がいちばん大きかった視点を使う（最初の視点を含む）。
- 引数：
  - `view`（`tuple[Vec3, float, float, float]`）：(target, yaw, pitch, dist)
- 戻り値：ずらした視点（同じ形）

#### `_head_screen_gap(self, view: tuple[Vec3, float, float, float]) -> float`（5178 行）
概要：視点 view から見た、2 人（人間と会話相手）の頭の画面上の横の差を返す。どちらかがカメラの後ろなら 0。会話相手がいなければ 0。
- 引数：
  - `view`（`tuple[Vec3, float, float, float]`）：(target, yaw, pitch, dist)
- 戻り値：`float`（画面の点）

#### `world_to_screen(self, p: Vec3, vx: int, vy: int, vw: int, vh: int, view: tuple[Vec3, float, float, float] | None = None) -> tuple[float, float] | None`（5196 行）
概要：3D の点 p の画面上の位置（`screen_ray` の逆）。カメラの後ろ（奥行きが 0 以下）なら None。目・向き・fov は `screen_ray` と同じ決まり。
- 引数：
  - `p`（`Vec3`）：3D の点
  - `vx`（`int`）：描く範囲の左 x
  - `vy`（`int`）：同、上 y
  - `vw`（`int`）：同、幅
  - `vh`（`int`）：同、高さ
  - `view`（`tuple[Vec3, float, float, float] | None`）：(target, yaw, pitch, dist)。既定 None（今のカメラ）
- 戻り値：`tuple[float, float] | None`
- 主な変数：`eye` 目の位置（`target + _view_dir(yaw, pitch) * dist`）／`depth` カメラ前方向の奥行き

#### `_begin_blend(self, to: tuple[Vec3, float, float, float]) -> None`（5228 行）
概要：今のカメラから to へ、`CAM_BLEND_SEC` かけて切り替えを始める。
- 引数：
  - `to`（`tuple[Vec3, float, float, float]`）：目標の (target, yaw, pitch, dist)
- 戻り値：なし
- 主な変数：`self._cam_from`・`self._cam_to`（切り替えの始めと終わり）／`self._cam_blend` 進み具合（0〜1）

#### `_update_partner(self, dt: float) -> None`（5234 行）
概要：会話の相手の姿勢と向き、人間の向きと歩き直しを決める（office の会話中だけ）。相手が作業中でないとき：その場で立ち、人間を向く。相手が座っているとき：体は席の向きのまま頭だけ人間を向く（`HEAD_YAW_LIMIT` まで）。座ったら机の正面へ 1 回だけ人間を歩かせる。相手が席へ歩いているとき：`FOLLOW_REPLAN_SEC` ごとに相手のまわりの立つ位置へ歩き直す。人間は止まっているとき相手を向く。
- 引数：
  - `dt`（`float`）：前のフレームからの秒
- 戻り値：なし
- 主な変数：`self._talk_seat_moved`／`self._follow_replan` 歩き直しまでの秒／`partner.pose.head_yaw` 頭の向き／`turn` 人間を向くための回転角（-180〜180 度）

#### `_update_camera(self, dt: float) -> None`（5276 行）
概要：人間がいる配置のカメラを毎フレーム決める（office だけ）。切り替え中は from から to へ smoothstep（なめらかな補間 3b²−2b³）でつなぐ。会話中は 2 人を映す視点（毎フレーム計算し直す）、ふだんは人間を追う（`FOLLOW_RATE` で指数的に近づく）。切り替えが終わって会話の前の視点に戻ったら `_saved_view` を消す。最後に `_apply_camera`。
- 引数：
  - `dt`（`float`）：前のフレームからの秒
- 戻り値：なし
- 主な変数：`self._cam_blend`／`self.cam_target`・`cam_yaw`・`cam_pitch`・`cam_dist` カメラの今の状態／`s` 補間の割合

#### 画面・入力まわり

#### `_record_frame(self) -> None`（5315 行）
概要：直近約 1 秒のフレーム時刻から実測 FPS（1 秒あたりの描画回数）を求める。
- 引数：なし
- 戻り値：なし
- 主な変数：`self._frame_times`（時刻の deque）／`self.measured_fps` 実測 FPS

#### `_view_rect(self) -> tuple[int, int, int, int]`（5327 行）
概要：3D を描く範囲を返す。office は `(0, 0, OFFICE_SCREEN_W, VIEW3D_H)`、proto は画面全体。
- 引数：なし
- 戻り値：`(x, y, 幅, 高さ)`

#### `_in_rect(self, sx: float, sy: float, x: int, y: int, w: int, h: int) -> bool`（5333 行）
概要：画面の点が長方形の中か（右端・下端は含まない）。
- 引数：
  - `sx`（`float`）：点の x
  - `sy`（`float`）：点の y
  - `x`（`int`）：長方形の左
  - `y`（`int`）：同、上
  - `w`（`int`）：同、幅
  - `h`（`int`）：同、高さ
- 戻り値：`bool`

#### `_wheel_zooms(self, sx: float, sy: float) -> bool`（5337 行）
概要：ホイールで 3D を寄せ引きする位置か。proto は画面全体、office は 3D の範囲の上（`sy < VIEW3D_H`）だけ。
- 引数：
  - `sx`（`float`）：マウスの x（この関数では使わない）
  - `sy`（`float`）：マウスの y
- 戻り値：`bool`

#### `_max_scroll(self) -> int`（5343 行）
概要：履歴の一番上の行の番号の上限（最後の `HISTORY_ROWS` 行が見えるところ）。
- 引数：なし
- 戻り値：`int`

#### `_scroll_track(self) -> tuple[int, int, int, int]`（5347 行）
概要：履歴のスクロールバーの溝の長方形。枠の右端の内側。
- 引数：なし
- 戻り値：`(x, y, 幅, 高さ)`

#### `_on_left_click(self, sx: int, sy: int) -> None`（5356 行）
概要：左クリックの振り分け。proto は `handle_click` へ。office は、始業・終業ボタンとダイアログ（`_claude_click`）→会話のダイアログ上→入力欄（モードを PROMPT に）→履歴の枠（スクロールバーの溝なら押した位置へ飛ぶ）→それ以外は `handle_click`（歩く・話しかける）の順に、最初に当たったものだけを処理する。
- 引数：
  - `sx`（`int`）：クリックの画面 x
  - `sy`（`int`）：クリックの画面 y
- 戻り値：なし
- 主な変数：`self.mode` モード（PROMPT・WALK）／`self.history_scroll` 履歴の先頭の行

#### `_add_history(self, text: str) -> None`（5380 行）
概要：履歴の末尾に text を `UI_COLS` 桁で折り返して足す。
- 引数：
  - `text`（`str`）：足す文
- 戻り値：なし

#### `_append_history_rows(self, rows: list[str], color: int = TEXT_COLOR) -> None`（5384 行）
概要：履歴の末尾に行を足す。上限（`HISTORY_MAX`）を超えたら古い行から捨て、一番下まで見せる。
- 引数：
  - `rows`（`list[str]`）：足す行
  - `color`（`int`）：行の色。既定 `TEXT_COLOR`
- 戻り値：なし
- 主な変数：`self.history`（行）／`self.history_color`（行ごとの色。history と同じ長さを保つ）／`self.history_scroll`

#### `_draw_ui(self) -> None`（5394 行）
概要：office の下の部分（履歴・スクロールバー・入力欄）を描く。入力欄は PROMPT のとき黄色の枠と点滅するカーソル。左上に日本語入力の札（あ・A）、変換中なら右上に「変換中」の札（文は `t("ime_converting")`。日本語のとき「変換中」、英語のとき Converting。左上の「あ」「A」は日本語入力の状態の印なので言語で変えない。札の幅の計算も同じ文で行う）。--claude のときは入力欄の一番下の行に「現在のモデル・effort」（灰色）を出す。
- 引数：なし
- 戻り値：なし
- 主な変数：`prompting` 入力中か（`_prompting()`）／`self.input_buf` 入力中の文字／`self.ime_state`（札の文字）／`self.ime_composing` 変換中か

#### `_composing_label_pos(self, box_w: int) -> tuple[int, int]`（5444 行）
概要：「変換中」の札の左上の位置。右端は x=`COMPOSING_LABEL_RIGHT`（620）、上端は履歴の枠の下の線のすぐ下。
- 引数：
  - `box_w`（`int`）：札の幅
- 戻り値：`(x, y)`

#### `_input_text_x(self) -> int`（5453 行）
概要：入力欄の文字を書き始める x。日本語入力の札の幅のぶん右から。
- 引数：なし
- 戻り値：`int`

#### `_input_cols(self) -> int`（5459 行）
概要：入力欄の 1 行の桁数。日本語入力の札のぶん、また「変換中」の札の左側までの分だけ文字の領域が狭い。
- 引数：なし
- 戻り値：`int`

#### `_input_text_rows(self) -> int`（5466 行）
概要：入力の文字を見せる行数。--claude のときはいちばん下の行を状態の行にするので 1 行少ない（`INPUT_TEXT_ROWS_CLAUDE`、そうでなければ `INPUT_ROWS`）。
- 引数：なし
- 戻り値：`int`

#### `_input_rows(self, text: str) -> list[str]`（5470 行）
概要：入力中の文字を改行で分け、それぞれを `_input_cols` 桁で折り返し、最後の `_input_text_rows` 行だけを返す。
- 引数：
  - `text`（`str`）：入力中の文字
- 戻り値：`list[str]`

#### `draw(self) -> None`（5477 行）
概要：3D（`self.scene.draw`）を描いたあと、2D の文字を重ねる。左上に実測 FPS、人数（6 人まで名前と状態、超えたら人数だけ）、会話中は相手の名前。office では上の真ん中に MODE の札と操作の案内、左下に操作の案内、--claude なら `_draw_claude`、最後に `_draw_ui`。MODE の札はメニューが開いていれば MENU、コマンドの窓が開いていれば SLASH、そうでなければ今のモード。
- 引数：なし
- 戻り値：なし
- 主な変数：`self.measured_fps`／`self.fps` 目標 FPS／`count_lines` 人数表示の行数／`mode_part`・`hint_part` MODE の札の文字／`self.layout.has_props` office かどうか

### モジュールの関数

#### `parse_args(argv: list[str] | None = None) -> argparse.Namespace`（i18n で変わった。i18n の前は 5525 行）
概要：コマンドライン引数を解釈する。**2 段で読む**：最初に `argparse.ArgumentParser(add_help=False)` で `--lang` だけを `parse_known_args` で読み、`set_lang(pre_args.lang or detect_lang())` で言語を決めてから、本来の parser を作る。こうすると `--help` の説明文（`t("arg_…")`）も、決めた言語で出る。
- 引数：
  - `argv`（`list[str] | None`）：引数の列。既定 None（実際のコマンドラインを使う）
- 戻り値：`argparse.Namespace`。次の項目を持つ
  - `--lang`（"ja" か "en"、既定は `get_lang()`、つまり `--lang` の指定か `detect_lang()` の結果）：表示の言語
  - `--fps`（int、既定 30）：目標 FPS（1〜60）
  - `--seed`（int、既定 None）：乱数の種
  - `--layout`（"proto" か "office"、既定 "proto"）：配置
  - `--agents`（int、既定 3）：人数（proto は 1〜3、office は 1〜18。範囲の確認はここでは行わない）
  - `--config`（str、既定 None）：設定ファイル（省略時は pyxelcube_agents.py と同じフォルダの pyxelcube_agents.toml、とヘルプにある）
  - `--time-scale`（float、既定 `DEFAULT_TIME_SCALE`）：行き先・会話のタイマーの早回し倍率
  - `--claude`（フラグ）：本物の Claude Code とつなぐ（office のときだけ）
  - `--workdir`（str、既定 None）：Claude Code を動かすフォルダ（省略時は pca_work、とヘルプにある）
  - `--session`（str、既定 "pyxelcube_agents"）：tmux のセッション名
- 各 help 文は文のキー `arg_lang`・`arg_fps`・`arg_seed`・`arg_layout`・`arg_agents`・`arg_config`・`arg_speed`（`--time-scale`）・`arg_claude`・`arg_workdir`・`arg_session` を `t()` に通したもの
- 主な変数：`pre`（`--lang` だけを読む仮の parser）／`pre_args`／`parser`（`argparse.ArgumentParser`。説明は `APP_NAME APP_VERSION`）

#### `main() -> None`（5571 行）
概要：引数を解釈して App を作り、Pyxel のループ（`app.update` と `app.draw`）を始める。ファイル末尾の `if __name__ == "__main__":` から呼ばれる。
- 引数：なし
- 戻り値：なし
- 主な変数：`args` `parse_args()` の結果／`app` 作った App（`fps`・`seed`・`layout`・`agents` を位置引数で、`config_path`・`time_scale`・`claude`・`workdir`・`session` を名前つきで渡す）

### 補足
- `_update_door_auto`・`_begin_work`・`_enter`・`_leave`・`_toggle_session`・`_choose_dialog`・`_send_to_claude`・`_perm_clock` などは 3700 行より前で定義されている。それぞれの説明は「描画・許可の受け取り・App の前半」の章にある。
- 各メソッドを毎フレームどの順で呼ぶかは、`App.update` の説明を見る。
- 背景の透かしの濃さ：コマンドの窓（`_draw_slash`）は定数 `SLASH_DITHER`（0.75、472 行）を使い、会話のダイアログ（`_draw_talk_dialog`）は 0.5 を直接書いている。
- `App` の属性の一覧（型と用途）は、`App` のクラスの節（`__init__` と `_init_claude` の 2 つの表）にある。

---

## 言語の切り替え（i18n）

画面の表示と Claude へ送る文を、日本語（ja）と英語（en）で切り替える。言語は起動のときに 1 回だけ決める（`parse_args` の中の `set_lang`）。文は `pca_i18n.py` の表 `MESSAGES` にまとめ、使う所で `t("キー")` と引く。この章は、i18n で足したり変わったりしたものを書く。ほかの章の行番号は、i18n を入れる前のものが多い。

### `pca_i18n.py`（259 行。標準ライブラリだけ。`os`・`collections.abc.Mapping`）

#### 定数

| 名前 | 値 | 用途 |
|---|---|---|
| `LANGS` | `("ja", "en")` | 使える言語。`--lang` の `choices` と `set_lang` の確認に使う |
| `_lang` | `"ja"`（モジュールの変数） | いまの言語。`set_lang` で書き換え、`get_lang` で読む。起動前の既定は ja |
| `MESSAGES` | `dict[str, dict[str, str]]` | 文の表。キー → `{"ja": 日本語の文, "en": 英語の文}`。値を差し込む文は `str.format` の `{名前}`（例：`{value}`・`{sec}`・`{summary}`）。全部のキーに ja と en の両方を持つ |

`MESSAGES` のキーは、画面の文（ボタン・履歴・ダイアログ・案内）、エラーの文（`err_…`）、Claude へ送る引き継ぎの依頼（`handoff_prompt`）、起動オプションの help（`arg_…`）、`pca_bridge.py` の文（`err_tmux_failed`・`notice_…` など）、区切りの記号（`list_sep`：ja は「、」、en は「, 」）などである。

#### `detect_lang(environ: Mapping[str, str] | None = None) -> str`
概要：環境変数 `LC_ALL` → `LC_MESSAGES` → `LANG` の順に、空でない最初のものを見る。`"ja"` で始まれば `"ja"`、それ以外は `"en"`。どれも空か無ければ `"en"`。
- 引数：`environ`（`Mapping[str, str] | None`）：環境変数の辞書。既定 None（`os.environ`）。
- 戻り値：`str`（`"ja"` か `"en"`）
- 例：`{"LANG": "ja_JP.UTF-8"}` → ja／`{"LC_ALL": "C", "LANG": "ja_JP.UTF-8"}` → en（`LC_ALL` が先）／`{}` → en／`{"LC_MESSAGES": "ja"}` → ja

#### `set_lang(lang: str) -> None`
概要：使う言語を決める（モジュールの変数 `_lang` を書き換える）。`LANGS` に無い値は `ValueError`。
- 引数：`lang`（`str`）
- 戻り値：なし

#### `get_lang() -> str`
概要：いまの言語を返す。
- 引数：なし／戻り値：`str`

#### `t(key: str, **kwargs: object) -> str`
概要：キーの文を、いまの言語で返す。`kwargs` があるときだけ `str.format` で差し込む（無いときは format しないので、文の中の波かっこは壊れない）。キーが `MESSAGES` に無ければ `KeyError`。
- 引数：`key`（`str`）：文のキー／`kwargs`：差し込む値
- 戻り値：`str`
- 例：`t("err_seat_yaw", value=repr(seat_yaw))`

### 文の定数がキーの文字列になったこと（`pyxelcube_agents.py`）

`HANDOFF_PROMPT`・`PERM_WAIT_NOTE`・`PERM_KEYS_TEXT`・`PERM_KEYS_ALWAYS_TEXT`・`PERM_ALWAYS_CONFIRM_TEXT`・`PERM_ALWAYS_QUESTION`・`MENU_GUIDE`・`SLASH_GUIDE_PANEL`・`SLASH_GUIDE_STATIC`・`TALK_PAGE_GUIDE` は、import の時点ではまだ言語が決まっていないので、文ではなく **キーの文字列**（例：`HANDOFF_PROMPT = "handoff_prompt"`）を持つ。使う所で `t(定数)` を通す（例：`self.bridge.send_prompt(t(HANDOFF_PROMPT))`、比較も `event.text == t(HANDOFF_PROMPT)`）。

- `CLAUDE_DIALOG_OPTIONS` は `(モード, 文のキー)` の組。描く所で `t(キー)` を通し、クリックの判定はモードを使う。
- `PERM_RULE_SCOPE` は保存先の名前 → 文のキー。引く所（`_suggestion_rows`）で `t()` を通す。辞書に無い保存先は、そのまま出す。
- 日本語の入力の状態の印「あ」（`self.ime_state == "あ"`・`{"あ": 8, "A": 3}`・`font.text_width("あ")`）は言語で変えない。「変換中」の札だけ `t("ime_converting")`。
- 文書の中の文の例（日本語の画面の文）は、日本語のときの例である。

### `hook_settings_json(hook_path: Path) -> str`（`pyxelcube_agents.py` 51 行）
概要：`claude --settings` に渡す hook の設定（JSON の文字列）を返す。許可（`PermissionRequest`、timeout 330）と通知（`Notification`、timeout 10）の 2 つ。作業フォルダの設定ファイルは変えず、起動のときだけ hook を足す。コマンドは `python3 -I <hook のフルパス>`（パスは `shlex.quote`）で、末尾に **種類だけ** を足す：`... PermissionRequest`・`... Notification`。言語は付けない（作業フォルダの古い設定の hook とコマンドを同じにして、同じコマンドが 2 回呼ばれないようにするため）。言語は `claude_command` が環境変数 `PCA_LANG` で渡す。
- 引数：`hook_path`（`Path`）：`pca_perm_hook.py` のパス
- 戻り値：`str`（`json.dumps(…, ensure_ascii=False)`）

### `claude_command(hook_path: Path, lang: str = "ja") -> str`（`pyxelcube_agents.py` 70 行）
概要：tmux の `new-session` で起動する claude のコマンド文字列を返す。`"PCA_LANG=" + shlex.quote(lang) + " claude --settings " + shlex.quote(hook_settings_json(hook_path))`（例：`PCA_LANG=en claude --settings '<JSON>'`）。言語は環境変数 `PCA_LANG` で渡し、Claude Code が起動した hook に受け継がれる（実機で確認）。tmux は最後の引数を shell で解釈するので、JSON を `shlex.quote` で囲む。
- 引数：`hook_path`（`Path`）／`lang`（`str`。既定 `"ja"`）
- 戻り値：`str`
- 呼ぶ所：`App` の Bridge の作り方（`claude_cmd=claude_command(HOOK_PATH, get_lang())`）。いまの言語を渡す。

### `pca_perm_hook.py`（hook）

hook は `python3 -I` で動くので、同じフォルダの `pca_i18n` を import できない（`-I` はスクリプトのフォルダを `sys.path` に入れない）。そのため、hook の中に小さな辞書を持つ。

- `DENY_MESSAGES: dict[str, str]`：`{"ja": "ユーザーがツールの中で断りました", "en": "The user denied this in the pyxelcube_agents tool"}`。以前の `DENY_MESSAGE`（文が 1 つ）が、言語ごとの辞書になった。
- `LANG_ENV_NAME: str = "PCA_LANG"`：言語を受け取る環境変数の名前。
- `hook_lang() -> str`：言語を返す。`os.environ` の `PCA_LANG` を見て、`DENY_MESSAGES` にある値（`"ja"`・`"en"`）ならそれ、それ以外や無いときは `"ja"`。
- `decision_output(answer: str | None, suggestions: object = None, lang: str = "ja") -> str | None`：返事から、標準出力に出す判定の JSON を作る。`"deny"` の `message` は `DENY_MESSAGES.get(lang, DENY_MESSAGES["ja"])`（知らない言語は日本語）。許可・「いつも許可」の判定や、何も出さない場合は変わらない。
- `main()`：`kind = sys.argv[1]`（`PermissionRequest`・`Notification`）、言語は環境変数 `PCA_LANG`（`hook_lang()`）。`decision_output(answer, item(data, "permission_suggestions"), hook_lang())` と呼ぶ。
- 返事の時間切れなどの例外の文は、hook の外には出ないので言語で切り替えない。

### 英語の画面が前提の所

このツールは、Claude Code の画面（tmux の画面と会話記録）の **英語の文字** を読んで動く。言語の切り替え（`--lang`）は、ツールの表示と、Claude へ送る文・拒否の理由文だけを変える。Claude Code 2.1.330 では、language 設定や OS の言語を日本語にしても、画面は英語のままだった（実物で確かめた。変わるのは Claude の返事と、許可の画面の説明文だけ）。画面が翻訳される版では、次の所が動かなくなるおそれがある。

| 所 | 読んでいる英語の文字 |
|---|---|
| 許可の画面の判定（`pca_bridge.py` の `Bridge.permission_screen_open`） | `Do you want to` と `Esc to cancel` の両方（`pca_bridge.py` のコメントにも「画面が英語で出ることを前提」とある） |
| `USAGE_PCT_RE`、`_parse_usage` | `NN% used`、見出し `Current session`・`Current week`、次の行の `Resets` |
| `/usage` の読み取りの閉じる判定（`_usage_step`・`_usage_panel_open`） | 画面の `Esc to` の案内（`_usage_panel_seen`） |
| コマンドの窓（`_read_slash`） | 画面の `Esc to` の案内（`_slash_seen_panel`） |
| `STATE_RE` | 状態の行の `Opus 5.5 with medium effort` など（`with … effort`） |
| `SET_MODEL_RE`・`SET_EFFORT_RE` | 会話記録の `Set model to`・`Kept model as`・`Set effort level to` |

---

## スプラッシュ（`pca_splash.py`）

起動時の 2 場面（1：Pyxel のロゴと「Powered by Pyxel」、2：アプリ名と「Ver. 版」）を見せる。各場面は 2 秒で浮き出て、2 秒止まり、2 秒で消える（60fps で 120＋120＋120 フレーム。fps が変わっても同じ 2 秒になるようフレーム数を合わせる）。「じわっと」は黒を `pyxel.dither` の濃さを変えて重ねて表す。テストは `test_pca_splash.py`（窓は出ない）。

### 定数
| 名前 | 値 | 意味 |
|---|---|---|
| `FADE_FRAMES`・`HOLD_FRAMES` | `120`・`120` | 浮き出る・消える時間と、止める時間（60fps のフレーム数） |
| `SCENE_COUNT` | `2` | 場面の数 |
| `FONT_W`・`FONT_H` | `4`・`6` | Pyxel 標準フォントの 1 文字の枠 |
| `REF_W`・`REF_H` | `640`・`500` | 拡大率の基準の画面 |
| `REF_LOGO_SCALE`・`REF_TEXT_SCALE` | `6`・`3` | 基準の画面でのロゴ・文字の倍率 |
| `PYXEL_LOGO_SIZE`・`PYXEL_LOGO` | `(38, 16)`・文字列 | Pyxel のロゴ（1 画素 4 ビット・zlib・base64。MIT License、Copyright (c) 2018-2026 Takashi Kitao） |

### `_text_image(text: str) -> pyxel.Image`
概要：文字を Pyxel 標準フォントで小さな画像に描く。背景は色 0（`blt` の `colkey` で透明にする）。標準フォントは 1 字の枠 4×6 のうち、字は左上の 3×5 に収まる（右 1 列と下 1 行は空き）。その空きを除いた大きさ（**幅 `len(text) * 4 - 1`・高さ 5**。空の文字は幅 1）にして、描く中心を字の見た目の中心に合わせる。

### `_blt_center(img, cx: float, cy: float, scale: int, colkey: int | None) -> None`
概要：画像を、**中心が (cx, cy) に来るよう**に `scale` 倍で描く。Pyxel 3.0.3 の `blt` の `scale` は、渡した (x, y) と**元の大きさ**の四角の中心を基準に拡大する（左上を基準にしない）。そのため、拡大後の大きさではなく元の大きさの半分を中心から引いた位置 `(cx - 幅/2, cy - 高さ/2)` を渡す。`colkey` が None なら透明色なし。
- 実測の例：4×2 の画像を scale 3 で中心 (16, 16) に描くと、点の範囲は x 10〜21・y 13〜18。

### クラス `Splash`
進行と描画。`App.__init__` で `pyxel.init` のあとに 1 回だけ作る。
- `__init__(width, height, fps, app_name, app_version)`：`fade_frames`・`hold_frames`（fps に合わせた 2 秒）、`scene_frames`（1 場面）、`total_frames`（全体）、`timer`（0 から）を決める。拡大率は `k = min(width/640, height/500)` で、`logo_scale = max(1, round(6*k))`・`text_scale = max(1, round(3*k))`（640×500 で 6・3、256×192 で 2・1）。
- **位置は「中心」で持つ**（`_blt_center` で描く）：`center_x`（画面の左右の真ん中 `width/2`）、場面 1 の `logo_cy`（`int(height*0.36)`。真ん中より少し上）・`powered_cy`（ロゴの下に 2 行あけた「Powered by Pyxel」の中心）、場面 2 の `name_cy`（`height/2 - 1行`）・`version_cy`（`height/2 + 1行`。2 行のまとまりが上下の真ん中）。1 行 = `FONT_H * text_scale`。
- 画像：`logo`・`powered`・`name`・`version`。
- `finished`（`timer >= total_frames`）・`scene`（今の場面 0 か 1）・`brightness()`（0.0〜1.0。浮き出て・止まって・消える）・`skip()`（`timer = total_frames` にして全部飛ばす）・`update()`（1 フレーム進める。終わったら止まる）。
- `draw()`：画面を色 0 で塗り、終わっていれば何もしない。場面に応じた画像を `_blt_center` で描き、`darkness = 1 - brightness()` が 0 より大きければ `pyxel.dither(darkness)` で全面に黒い四角を重ねる（描いたあと `dither(1.0)` に戻す）。

