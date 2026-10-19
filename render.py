#!/usr/bin/env python3
"""像素漫步 · Pixel Walk —— 把参与过的项目做成一条可以走过去的街。

世界在低分辨率（320x112）里绘制，最后统一放大 4 倍成 1280x448。
每站一间房：房高 = star 数，房色 = 主语言，亮着的窗户 = 那块屏幕。
小人在画面里走，世界在脚下滚。
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent

# ── 尺寸 ────────────────────────────────────────────────────────────────────
W, H = 320, 114            # 世界像素
SCALE = 4                  # 放大倍数 -> 1280x448
SCENE_BOTTOM = 72          # 地平线
GROUND_H = 8
RAIL_Y = 80                # 年份刻度轨
LINE1_Y = 87               # HUD 第一行
LINE2_Y = 100              # HUD 第二行
SCREEN_W, SCREEN_H = 40, 24
HOUSE_W = 48
PITCH = 60
MARGIN = 110

# 字体：按平台依次找第一个存在的，找不到才报错。
# 写死 macOS 路径的话，Linux / Windows clone 下来第一步就崩，这台机器之外等于不能用。
_FONT_CANDIDATES = {
    "latin": [
        "/System/Library/Fonts/Menlo.ttc",                                  # macOS
        "/System/Library/Fonts/Monaco.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",              # Debian/Ubuntu
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/liberation-mono/LiberationMono-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",                          # Arch
        "C:/Windows/Fonts/consola.ttf",                                     # Windows
    ],
    "cjk": [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",                       # macOS
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",           # Linux
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "C:/Windows/Fonts/msyh.ttc",                                        # Windows 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",
    ],
}


def _resolve_font(kind: str) -> str:
    import pathlib
    for p in _FONT_CANDIDATES[kind]:
        if pathlib.Path(p).exists():
            return p
    return ""


FONT_LATIN = _resolve_font("latin") or FONT_CANDIDATES["latin"][0]
FONT_CJK = _resolve_font("cjk")
if not FONT_CJK:
    import sys as _sys
    print("[homepage-walk] ⚠️  没找到中文字体，HUD 中文会显示成方块。\n"
          "  装一个：apt install fonts-noto-cjk（Debian/Ubuntu）｜"
          " brew install --cask font-noto-sans-cjk（macOS）\n"
          "  然后重跑。或者把 render.py 里 FONT_CJK 直接改成你系统里的字体路径。",
          file=_sys.stderr)
    FONT_CJK = FONT_LATIN

# ── 调色板 ──────────────────────────────────────────────────────────────────
HAIR = (46, 36, 54)
SKIN = (232, 180, 140)
SHIRT = (86, 152, 236)
SCARF = (240, 104, 92)
PANTS = (51, 65, 92)
SHOE = (32, 34, 42)
EYE = (24, 24, 32)

HUD_BG = (16, 18, 26)
HUD_BG2 = (22, 25, 35)
HUD_DIM = (108, 118, 140)
HUD_TXT = (226, 232, 244)
HUD_ACC = (120, 200, 255)

# 天空：从清晨走到深夜，8 个色阶
SKY = [
    ((38, 34, 66), (86, 62, 96), (214, 130, 110)),   # 天没亮
    ((52, 52, 96), (128, 88, 118), (240, 168, 120)), # 破晓
    ((62, 92, 150), (150, 150, 190), (246, 206, 150)),  # 清晨
    ((58, 104, 178), (130, 176, 220), (200, 226, 240)),  # 上午
    ((54, 112, 196), (120, 184, 232), (196, 230, 246)),  # 正午
    ((64, 96, 168), (188, 150, 160), (238, 178, 128)),   # 午后
    ((52, 60, 118), (172, 96, 112), (232, 128, 96)),     # 黄昏
    ((22, 26, 62), (44, 48, 104), (88, 76, 140)),        # 入夜
]
GROUND_TOP = (86, 96, 92)
GROUND_MID = (54, 62, 62)
GROUND_LOW = (34, 40, 44)
STAR = (240, 240, 210)
MERGE = (137, 87, 229)          # GitHub merged PR 的紫，用来标记"贡献到别人的项目"

LANG_RGB = {
    "Python": (53, 114, 165), "Java": (176, 114, 25), "JavaScript": (241, 224, 90),
    "TypeScript": (49, 120, 198), "C#": (23, 134, 0), "Rust": (222, 165, 132),
    "Shell": (137, 224, 81), "Mermaid": (255, 54, 112), "HTML": (227, 76, 38),
}

# ── 小工具 ──────────────────────────────────────────────────────────────────
_fonts: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


def text(img: Image.Image, x: int, y: int, s: str, path: str, size: int,
         color: tuple[int, int, int], anchor: str = "lt", thresh: int = 110) -> int:
    """无抗锯齿地写字（阈值化 -> 就是像素字）。返回文字宽度。"""
    x, y = int(round(x)), int(round(y))
    f = font(path, size)
    w = int(f.getlength(s)) + 6
    m = Image.new("L", (w, size * 3), 0)
    ImageDraw.Draw(m).text((3, 2), s, font=f, fill=255)
    m = m.point(lambda v: 255 if v >= thresh else 0)
    bb = m.getbbox()
    if bb is None:
        return 0
    m = m.crop(bb)
    if "r" in anchor:
        x -= m.width
    elif "c" in anchor:
        x -= m.width // 2
    if "b" in anchor:
        y -= m.height
    elif "m" in anchor:
        y -= m.height // 2
    img.paste(Image.new("RGB", m.size, color), (x, y), m)
    return m.width


def fit(txt: str, path: str, size: int, max_w: int) -> str:
    """按像素宽度截断，超了补 ..（中文一个字就是一个 size 宽，很好算）"""
    f = font(path, size)
    if f.getlength(txt) <= max_w:
        return txt
    out = txt
    while out and f.getlength(out + "..") > max_w:
        out = out[:-1]
    return out + ".."


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def put(img: Image.Image, x: int, y: int, c) -> None:
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), c)


def shade(c, k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(v * k))) for v in c)


def mix(a, b, t: float) -> tuple[int, int, int]:
    return lerp(a, b, t)


def sky_at(t: float) -> tuple[tuple, tuple, tuple]:
    """t in [0,1] 沿全天色阶插值 -> (天顶, 中景, 地平线)"""
    p = t * (len(SKY) - 1)
    i = min(int(p), len(SKY) - 2)
    f = p - i
    return tuple(lerp(SKY[i][k], SKY[i + 1][k], f) for k in range(3))  # type: ignore[return-value]


# ── 像素画布 ────────────────────────────────────────────────────────────────
class Px:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def set(self, x: int, y: int, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def rect(self, x: int, y: int, w: int, h: int, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, c)

    def frame(self, x: int, y: int, w: int, h: int, c):
        for xx in range(x, x + w):
            self.set(xx, y, c)
            self.set(xx, y + h - 1, c)
        for yy in range(y, y + h):
            self.set(x, yy, c)
            self.set(x + w - 1, yy, c)

    def line(self, x0: int, y0: int, x1: int, y1: int, c):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def disc(self, cx: int, cy: int, r: int, c):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r * 0.6:
                    self.set(x, y, c)

    def to_image(self, bg) -> Image.Image:
        im = Image.new("RGB", (self.w, self.h), bg)
        p = im.load()
        for y in range(self.h):
            for x in range(self.w):
                if self.px[y][x] is not None:
                    p[x, y] = self.px[y][x]
        return im


# ── 每个项目的"店招"图案（自绘 20x16 徽章）────────────────────────────────
def emblem(kind: str, col: tuple[int, int, int]) -> Px:
    c = Px(20, 16)
    hi = tuple(min(255, round(v * 1.45 + 30)) for v in col)
    lo = shade(col, 0.55)
    deep = shade(col, 0.32)
    white = (238, 242, 250)
    warm = (242, 193, 78)

    if kind == "toolbox":
        c.rect(3, 6, 14, 8, lo)
        c.rect(3, 6, 14, 1, hi)
        c.rect(3, 13, 14, 1, deep)
        c.rect(6, 3, 8, 3, None)
        c.frame(6, 3, 8, 3, hi)
        c.rect(8, 9, 4, 2, warm)
    elif kind == "shield":
        for i, wdt in enumerate([16, 16, 16, 16, 14, 14, 12, 10, 8, 6, 4, 2]):
            c.rect(10 - wdt // 2, 1 + i, wdt, 1, col)
        c.rect(2, 1, 16, 1, hi)
        c.rect(2, 1, 1, 5, hi)
        for dy in (0, 1):
            c.line(7, 5 + dy, 9, 8 + dy, white)
            c.line(9, 8 + dy, 14, 3 + dy, white)
    elif kind == "board":                       # 五子棋
        c.rect(2, 1, 16, 13, col)
        c.frame(2, 1, 16, 13, deep)
        for i in range(4):
            c.line(5 + i * 3, 2, 5 + i * 3, 12, deep)
            c.line(3, 3 + i * 3, 17, 3 + i * 3, deep)
        for (bx, by, cc) in ((5, 3, white), (14, 6, (26, 26, 32)),
                             (8, 9, white), (11, 12, (26, 26, 32))):
            c.disc(bx, by, 2, cc)
            c.set(bx - 1, by - 1, shade(cc, 1.4))
    elif kind == "chart":                       # K 线
        for x, (t, b, up) in enumerate([(4, 10, 1), (7, 12, 0), (10, 7, 1), (13, 9, 0)]):
            xx = 4 + x * 4
            c.line(xx, t - 2, xx, b + 2, HUD_DIM)
            cc = (232, 96, 96) if up else (108, 208, 140)
            c.rect(xx - 1, t, 3, max(2, b - t), cc)
    elif kind == "window":
        c.rect(2, 2, 16, 12, shade(col, 0.42))
        c.rect(2, 2, 16, 3, lo)
        c.rect(3, 3, 1, 1, hi)
        c.rect(5, 3, 1, 1, hi)
        c.rect(7, 3, 1, 1, hi)
        c.rect(4, 7, 5, 5, lo)
        c.rect(11, 7, 5, 5, lo)
        c.frame(4, 7, 5, 5, hi)
        c.frame(11, 7, 5, 5, hi)
    elif kind == "pulse":
        pts = [(1, 8), (5, 8), (7, 3), (10, 13), (12, 6), (14, 10), (18, 10)]
        for i in range(len(pts) - 1):
            c.line(*pts[i], *pts[i + 1], hi)
    elif kind == "play":
        for i in range(7):
            c.rect(6 + i, 2 + i, 1, 11 - 2 * i, hi)
        c.rect(6, 2, 1, 11, hi)
        c.rect(2, 12, 16, 1, lo)
        c.rect(2, 14, 11, 1, deep)
    elif kind == "bars":
        for i, hgt in enumerate([4, 6, 5, 8, 11]):
            c.rect(3 + i * 3, 13 - hgt, 2, hgt, hi if i % 2 else col)
        c.rect(2, 14, 17, 1, deep)
        c.line(13, 5, 16, 2, warm)
        c.line(16, 2, 16, 5, warm)
        c.line(16, 2, 13, 2, warm)
    elif kind == "plug":
        c.rect(7, 6, 7, 7, lo)
        c.rect(7, 6, 7, 1, hi)
        c.rect(8, 3, 1, 3, hi)
        c.rect(12, 3, 1, 3, hi)
        c.rect(10, 13, 1, 3, deep)
        c.rect(6, 15, 9, 1, deep)
    elif kind == "prompt":
        c.line(4, 4, 8, 8, hi)
        c.line(8, 8, 4, 12, hi)
        c.rect(11, 11, 6, 2, hi)
    elif kind == "db":
        c.rect(4, 2, 12, 11, col)
        c.rect(3, 1, 14, 2, hi)
        c.rect(3, 2, 1, 10, hi)
        c.rect(16, 2, 1, 11, deep)
        c.rect(3, 5, 14, 1, deep)
        c.rect(3, 9, 14, 1, deep)
        c.rect(3, 13, 14, 1, deep)
    elif kind == "microservice":                # 三个服务 + 连线
        for (bx, by) in ((1, 1), (13, 1), (7, 10)):
            c.rect(bx, by, 6, 5, col)
            c.frame(bx, by, 6, 5, hi)
            c.set(bx + 1, by + 1, deep)
        c.line(4, 6, 4, 8, hi)
        c.line(4, 8, 10, 8, hi)
        c.line(10, 8, 10, 10, hi)
        c.line(16, 6, 16, 8, hi)
        c.line(16, 8, 10, 8, hi)
    elif kind == "graph":                       # 节点图
        pts = [(3, 12), (7, 3), (13, 6), (17, 12)]
        for a, b in ((0, 1), (1, 2), (2, 3), (0, 2)):
            c.line(*pts[a], *pts[b], lo)
        for (px, py) in pts:
            c.disc(px, py, 2, col)
            c.set(px, py, hi)
    elif kind == "cards":                       # 两张牌
        c.rect(2, 4, 8, 11, (238, 242, 250))
        c.frame(2, 4, 8, 11, deep)
        for dy in (6, 8, 10, 12):
            c.rect(4, dy, 4, 1, shade(col, 1.1))
        c.rect(9, 2, 8, 11, col)
        c.frame(9, 2, 8, 11, deep)
        c.set(12, 5, (238, 242, 250))
        c.set(13, 5, (238, 242, 250))
        c.set(11, 7, (238, 242, 250))
        c.set(12, 7, (238, 242, 250))
        c.set(13, 7, (238, 242, 250))
        c.set(14, 7, (238, 242, 250))
        c.set(12, 9, deep)
        c.set(13, 9, deep)
    elif kind == "page":                        # 一页文档
        c.rect(3, 1, 14, 14, (236, 240, 248))
        c.rect(12, 1, 5, 4, shade(col, 0.5))
        for i, wd in enumerate((9, 11, 7, 11, 6, 9)):
            c.rect(5, 5 + i * 2, wd, 1, shade(col, 0.75))
    elif kind == "tictactoe":                   # 井字棋
        c.rect(2, 1, 16, 14, (226, 196, 132))
        for gx in (7, 12):
            c.rect(gx, 1, 1, 14, (96, 72, 40))
        for gy in (5, 10):
            c.rect(2, gy, 16, 1, (96, 72, 40))
        ink = (44, 46, 58)
        c.line(3, 2, 6, 4, ink)
        c.line(6, 2, 3, 4, ink)
        c.frame(8, 6, 4, 4, ink)
        c.line(13, 11, 16, 13, ink)
        c.line(16, 11, 13, 13, ink)
    elif kind == "clipboard":                   # 带勾的板子
        c.rect(3, 2, 14, 13, col)
        c.rect(4, 3, 12, 11, shade(col, 0.55))
        c.rect(7, 1, 6, 3, hi)
        c.line(6, 9, 9, 12, (238, 242, 250))
        c.line(9, 12, 14, 5, (238, 242, 250))
        c.line(6, 10, 9, 13, (238, 242, 250))
    elif kind == "chip":                        # 芯片
        c.rect(5, 3, 10, 10, col)
        c.frame(5, 3, 10, 10, hi)
        c.rect(7, 5, 6, 6, deep)
        for i in range(3):
            c.rect(2, 5 + i * 3, 3, 1, hi)
            c.rect(15, 5 + i * 3, 3, 1, hi)
            c.rect(7 + i * 3, 1, 1, 2, hi)
            c.rect(7 + i * 3, 13, 1, 2, hi)
    elif kind == "book":                        # 一本书
        c.rect(3, 2, 14, 12, col)
        c.rect(3, 2, 3, 12, shade(col, 0.6))       # 书脊
        c.rect(3, 2, 14, 1, hi)
        c.rect(3, 13, 14, 1, deep)
        c.rect(15, 3, 2, 10, (236, 240, 248))      # 露出的书页
        c.rect(7, 5, 7, 1, (236, 240, 248))
        c.rect(7, 8, 5, 1, shade(col, 0.55))
        c.rect(6, 11, 3, 1, warm)
    elif kind == "avatar":                      # 小头像
        c.disc(10, 7, 6, col)
        c.disc(10, 7, 5, hi)
        c.set(7, 6, deep)
        c.set(8, 6, deep)
        c.set(12, 6, deep)
        c.set(13, 6, deep)
        c.rect(7, 9, 6, 1, deep)
        c.rect(8, 10, 4, 1, deep)
        c.rect(9, 1, 2, 2, col)
    elif kind == "gear":                        # 齿轮
        c.disc(10, 8, 5, col)
        for dx, dy in ((0, -6), (0, 6), (-6, 0), (6, 0), (-4, -4), (4, -4), (-4, 4), (4, 4)):
            c.rect(10 + dx - 1, 8 + dy - 1, 3, 3, col)
        c.disc(10, 8, 2, deep)
        c.disc(10, 8, 1, hi)
    elif kind == "mask":                        # 假面舞会面具
        for i, wd in enumerate((8, 12, 14, 16, 16, 16, 14, 12, 8)):
            c.rect(10 - wd // 2, 3 + i, wd, 1, col)
        c.rect(3, 3, 14, 1, hi)
        c.rect(5, 6, 3, 3, deep)                   # 左眼洞
        c.rect(12, 6, 3, 3, deep)
        c.rect(9, 5, 2, 5, hi)                     # 鼻梁
        c.rect(8, 10, 4, 1, shade(col, 0.45))
        c.rect(2, 4, 1, 4, shade(col, 1.35))       # 两侧羽毛
        c.rect(17, 4, 1, 4, shade(col, 1.35))
    elif kind == "sparkle":                     # 星点
        for (sx, sy, sz) in ((5, 4, 3), (14, 3, 2), (10, 9, 4), (4, 11, 2), (16, 11, 2)):
            c.rect(sx - sz, sy, sz * 2 + 1, 1, hi)
            c.rect(sx, sy - sz, 1, sz * 2 + 1, hi)
            c.rect(sx - 1, sy - 1, 3, 3, col)
            c.set(sx, sy, (250, 250, 250))
    elif kind == "nodes":                       # 一个中枢带三个小弟
        c.disc(6, 8, 3, col)
        c.set(6, 8, hi)
        for (nx, ny) in ((15, 3), (16, 10), (12, 14)):
            c.line(6, 8, nx, ny, lo)
        for (nx, ny) in ((15, 3), (16, 10), (12, 14)):
            c.disc(nx, ny, 2, hi)
    elif kind == "phone":                       # 手机
        c.rect(6, 1, 8, 14, col)
        c.frame(6, 1, 8, 14, hi)
        c.rect(7, 3, 6, 9, deep)
        c.rect(8, 4, 4, 3, shade(col, 1.2))
        c.rect(9, 13, 2, 1, hi)
    elif kind == "potion":                      # 药水瓶
        c.rect(8, 1, 4, 4, hi)
        c.rect(7, 4, 6, 1, col)
        for i in range(6):
            c.rect(7 - i, 5 + i, 6 + i * 2, 1, col)
        c.rect(4, 11, 12, 3, shade(col, 0.55))
        c.rect(5, 10, 10, 1, shade(col, 0.9))
        c.set(8, 12, (250, 250, 250))
        c.set(11, 11, (250, 250, 250))
    elif kind == "robot":                       # 小机器人
        c.rect(4, 4, 12, 9, col)
        c.frame(4, 4, 12, 9, hi)
        c.rect(9, 1, 2, 3, hi)
        c.disc(10, 1, 1, (242, 96, 96))
        c.rect(6, 7, 3, 3, (250, 250, 250))
        c.rect(11, 7, 3, 3, (250, 250, 250))
        c.set(7, 8, deep)
        c.set(12, 8, deep)
        c.rect(7, 11, 6, 1, deep)
    elif kind == "merge":                       # git 分支合并图
        c.line(6, 4, 6, 13, col)                # 主线
        c.line(14, 4, 14, 9, hi)                # 分支
        c.line(14, 9, 6, 9, hi)                 # 汇入主线
        for (px, py, cc) in ((6, 4, col), (14, 4, hi), (6, 13, col)):
            c.disc(px, py, 2, cc)
            c.set(px, py, (250, 250, 250))
        c.disc(6, 9, 3, MERGE)                  # 合并点
        c.set(6, 9, (250, 250, 250))
    else:
        c.rect(5, 4, 10, 8, lo)
    return c


# ── 小人 ────────────────────────────────────────────────────────────────────
WALKER_W, WALKER_H = 10, 17
KEY: dict[str, tuple[int, int, int] | None] = {".": None}
KEY.update({"h": HAIR, "s": SKIN, "b": SHIRT, "c": SCARF, "p": PANTS, "o": SHOE, "e": EYE})


def _rows(*lines: str) -> list[list]:
    return [[KEY[ch] for ch in ln] for ln in lines]


_CONTACT = (
    "..hhhhh...",
    ".hhhhhhh..",
    ".hhssshh..",
    ".hhsessh..",
    "..sssss...",
    "...ccc....",
    "..bbbbb...",
    "{ARM}bbbbbb..",
    "{ARM}bbbbbb..",
    "..bbbbbb..",
    "..bbbbb...",
    "..ppppp...",
    ".ppp.ppp..",
    ".pp...pp..",
    ".pp...pp..",
    ".oo...oo..",
    "..........",
)
_PASSING = (
    "..........",
    "..hhhhh...",
    ".hhhhhhh..",
    ".hhssshh..",
    ".hhsessh..",
    "..sssss...",
    "...ccc....",
    "..bbbbb...",
    "..bbbbbb..",
    "..bbbbbb..",
    "..bbbbbb..",
    "..bbbbb...",
    "..pp.pp...",
    "..pp.pp...",
    "..pp.pp...",
    "..oo.oo...",
    "..........",
)

WALK_FRAMES = [
    _rows(*[ln.replace("{ARM}", "s") for ln in _CONTACT]),   # 0 触地：左臂前摆
    _rows(*_PASSING),   # 1 过渡：腿并拢，身体最高
    _rows(*[ln.replace("{ARM}", ".").replace("..bbbbbb..", "..bbbbbs..", 1)
            for ln in _CONTACT]),                      # 2 触地：右臂前摆
    _rows(*_PASSING),   # 3 过渡
]


def draw_walker(img: Image.Image, x: int, y: int, frame: int, flip: bool = False) -> None:
    """x,y = 脚底中心。先铺一圈暗色描边，再上色，免得糊在背景里。"""
    grid = WALK_FRAMES[frame % len(WALK_FRAMES)]
    x0 = x - WALKER_W // 2
    y0 = y - WALKER_H
    outline = (14, 14, 22)
    for j, row in enumerate(grid):
        for i, c in enumerate(row):
            if c is None:
                continue
            xx = x0 + (WALKER_W - 1 - i if flip else i)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)):
                put(img, xx + dx, y0 + j + dy, outline)
    for j, row in enumerate(grid):
        for i, c in enumerate(row):
            if c is None:
                continue
            xx = x0 + (WALKER_W - 1 - i if flip else i)
            put(img, xx, y0 + j, c)


# ── 屏幕素材（真实截图 -> 像素化）────────────────────────────────────────────
def pixelate(im: Image.Image, palette_img: Image.Image) -> Image.Image:
    return im.resize((SCREEN_W, SCREEN_H), Image.LANCZOS) \
             .quantize(palette=palette_img, dither=Image.NONE).convert("RGB")


def build_palette(screens: list[Image.Image], budget: int = 72) -> Image.Image:
    """世界色 + 截图色，合成一张全局调色板。"""
    world = [HAIR, SKIN, SHIRT, SCARF, PANTS, SHOE, EYE,
             HUD_BG, HUD_BG2, HUD_DIM, HUD_TXT, HUD_ACC,
             GROUND_TOP, GROUND_MID, GROUND_LOW, STAR,
             (250, 250, 250), (28, 28, 34), (232, 96, 96), (108, 208, 140),
             (242, 193, 78), (238, 242, 250)]
    for tri in SKY:
        world.extend(tri)
    for c in LANG_RGB.values():
        world.extend([c, shade(c, 0.55), shade(c, 0.32),
                      tuple(min(255, round(v * 1.45 + 30)) for v in c)])
    world = list(dict.fromkeys(world))

    n_img = max(8, budget - len(world))
    if screens:
        sw, sh = SCREEN_W, SCREEN_H
        mont = Image.new("RGB", (sw * len(screens), sh))
        for i, s in enumerate(screens):
            mont.paste(s, (i * sw, 0))
        img_pal = mont.quantize(colors=n_img, method=Image.MEDIANCUT).getpalette()
        img_cols = [tuple(img_pal[i * 3:i * 3 + 3]) for i in range(n_img)]
    else:
        img_cols = []

    allc = list(dict.fromkeys(world + img_cols))[:256]
    pal_img = Image.new("P", (1, 1))
    flat = [v for c in allc for v in c]
    flat += [0] * (768 - len(flat))
    pal_img.putpalette(flat)
    return pal_img


# ── 场景 ────────────────────────────────────────────────────────────────────
def draw_sky(img: Image.Image, cam_x: int, world_w: int) -> None:
    """整帧同一时刻的天空，只做竖直渐变。

    这样天空是大片纯色：LZW 压得动，帧间差分也能把没变的部分标成透明。
    """
    t = min(1.0, max(0.0, (cam_x + W / 2) / max(1, world_w - W)))
    top, mid, bot = sky_at(t)
    d = ImageDraw.Draw(img)
    for y in range(SCENE_BOTTOM):
        c = lerp(top, mid, y / 30) if y < 30 else lerp(mid, bot, (y - 30) / max(1, SCENE_BOTTOM - 30))
        c = tuple(round(v / 8) * 8 for v in c)        # 收成 8 级色阶，色带更明确也更省
        d.line([(0, y), (W - 1, y)], fill=tuple(min(255, v) for v in c))


def draw_stars(img: Image.Image, cam_x: int, t: float) -> None:
    """越晚星星越亮"""
    if t < 0.55:
        return
    a = min(1.0, (t - 0.55) / 0.35)
    rng = np.random.default_rng(7)
    for _ in range(58):
        wx = int(rng.integers(0, 2400))
        wy = int(rng.integers(2, 34))
        sx = wx - int(cam_x * 0.18)
        sx %= (W + 60)
        if 0 <= sx < W and rng.random() < a:
            img.putpixel((sx, wy), STAR)


def draw_clouds(img: Image.Image, cam_x: int, t: float) -> None:
    rng = np.random.default_rng(11)
    c = lerp((250, 250, 255), (150, 140, 170), min(1.0, t * 1.1))
    for _ in range(16):
        wx = int(rng.integers(0, 3000))
        wy = int(rng.integers(6, 40))
        wdt = int(rng.integers(10, 26))
        sx = (wx - int(cam_x * 0.22)) % (W + 120)
        if sx > W:
            continue
        for i in range(wdt):
            hgt = 2 + round(math.sin(i / wdt * math.pi) * 2.4)
            for j in range(hgt):
                if 0 <= sx + i < W and 0 <= wy + j < SCENE_BOTTOM:
                    img.putpixel((sx + i, wy + j), c)


def draw_far(img: Image.Image, cam_x: int, t: float) -> None:
    """远山 + 中景楼群剪影，视差 0.28 / 0.55"""
    far = mix(mix((70, 84, 120), (120, 96, 110), t), sky_at(t)[1], 0.45)
    mid = shade(mix((40, 48, 74), (58, 44, 68), t), 1.0)
    rng = np.random.default_rng(3)
    ridge = 46
    for sx in range(W):
        wx = cam_x * 0.28 + sx
        y = ridge + int(7 * math.sin(wx / 34.0) + 4 * math.sin(wx / 13.0) + 3 * math.sin(wx / 61.0))
        for yy in range(y, SCENE_BOTTOM):
            img.putpixel((sx, yy), far)
    rng = np.random.default_rng(5)
    blocks = [(int(rng.integers(0, 2600)), int(rng.integers(6, 20))) for _ in range(150)]
    for bx, bh in blocks:
        sx = int(bx - cam_x * 0.55)
        if not (-30 <= sx <= W):
            continue
        top = SCENE_BOTTOM - bh
        for yy in range(top, SCENE_BOTTOM):
            for xx in range(sx, sx + 9):
                if 0 <= xx < W:
                    img.putpixel((xx, yy), mid)
        # 零星窗灯
        if bh > 10:
            for wy in range(top + 2, SCENE_BOTTOM - 1, 4):
                for wxx in (sx + 2, sx + 5):
                    if 0 <= wxx < W and (wy + bx) % 3 == 0:
                        img.putpixel((wxx, wy), shade(mix((230, 200, 120), (250, 220, 150), t), 0.9))


def draw_ground(img: Image.Image, cam_x: int) -> None:
    for sx in range(W):
        wx = int(cam_x) + sx
        img.putpixel((sx, SCENE_BOTTOM), GROUND_TOP)
        for y in range(SCENE_BOTTOM + 1, SCENE_BOTTOM + 3):
            img.putpixel((sx, y), GROUND_MID if (wx // 7 + y) % 3 else shade(GROUND_MID, 0.8))
        for y in range(SCENE_BOTTOM + 4, SCENE_BOTTOM + GROUND_H):
            img.putpixel((sx, y), GROUND_LOW)
        # 路面的碎石
        if (wx * 7919) % 23 == 0:
            img.putpixel((sx, SCENE_BOTTOM + 1), shade(GROUND_TOP, 1.25))


def draw_house(img: Image.Image, st: dict, x: int, t: float, lit: float) -> None:
    x = int(round(x))
    col = st["rgb"]
    h = int(st["house_h"])
    top = SCENE_BOTTOM - h
    left = x - HOUSE_W // 2
    body = shade(col, 0.44)
    edge = shade(col, 0.62)
    face = shade(col, 0.56)

    img.paste(Image.new("RGB", (HOUSE_W, h), body), (left, top))
    d = ImageDraw.Draw(img)
    d.rectangle([left, top, left + HOUSE_W - 1, top + h - 1], outline=edge)
    # 屋檐
    roof_top = MERGE if st.get("upstream") else shade(col, 1.35)
    d.rectangle([left - 2, top - 3, left + HOUSE_W + 1, top - 1], fill=col)
    d.rectangle([left - 2, top - 3, left + HOUSE_W + 1, top - 3], fill=roof_top)
    if st.get("upstream"):
        # 顶上一个小合并箭头，跟"自己的项目"区分开
        mx = x
        for i in range(4):
            d.rectangle([mx - i, top - 5 - i, mx + i, top - 5 - i], fill=MERGE)
        d.rectangle([mx, top - 12, mx, top - 6], fill=MERGE)
    # 高 star 的房子插一面小旗
    if not st.get("upstream") and st["stars"] >= 2:
        fx = left + HOUSE_W - 6
        d.line([fx, top - 3, fx, top - 12], fill=shade(col, 0.9))
        d.polygon([fx, top - 12, fx + 8, top - 9, fx, top - 6], fill=shade(col, 1.4))
    # 屏幕：嵌在房子上半部，是一扇亮着的窗
    sx0 = x - SCREEN_W // 2
    sy0 = top + 5
    glow = mix(shade(col, 0.5), col, lit)
    d.rectangle([sx0 - 2, sy0 - 2, sx0 + SCREEN_W + 1, sy0 + SCREEN_H + 1], fill=glow)
    d.rectangle([sx0 - 1, sy0 - 1, sx0 + SCREEN_W, sy0 + SCREEN_H], fill=shade(col, 0.22))
    img.paste(st["screen"], (sx0, sy0))
    # 亮屏时四角闪一下
    if lit > 0.5:
        for (cx, cy) in ((sx0 - 2, sy0 - 2), (sx0 + SCREEN_W + 1, sy0 - 2),
                         (sx0 - 2, sy0 + SCREEN_H + 1), (sx0 + SCREEN_W + 1, sy0 + SCREEN_H + 1)):
            put(img, cx, cy, mix(glow, (255, 255, 255), lit * 0.7))
    # 门和台阶
    door_y = sy0 + SCREEN_H + 4
    if door_y + 6 < SCENE_BOTTOM:
        d.rectangle([x - 5, door_y, x + 4, SCENE_BOTTOM - 1], fill=shade(col, 0.2))
        d.rectangle([x - 5, door_y, x + 4, door_y], fill=shade(col, 0.7))
        put(img, x + 2, door_y + 3, shade(col, 1.5))
    # 门口年份石牌
    py0 = SCENE_BOTTOM + 1
    d.rectangle([x - 11, py0, x + 10, py0 + 4], fill=shade(col, 0.16))
    d.rectangle([x - 11, py0, x + 10, py0], fill=shade(col, 0.6))
    text(img, x, py0, str(st["year"]), FONT_LATIN, 8,
         mix(STAR, col, 0.35), anchor="ct")


def draw_rail(img: Image.Image, stations: list[dict], cam_x: int, head_x: int) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([0, RAIL_Y, W - 1, RAIL_Y + 3], fill=HUD_BG2)
    d.line([0, RAIL_Y + 1, W - 1, RAIL_Y + 1], fill=shade(HUD_BG2, 1.6))
    seen: set[int] = set()
    for st in stations:
        sx = st["x"] - cam_x
        if not (-24 <= sx <= W + 24):
            continue
        passed = head_x >= st["x"]
        col = mix(HUD_DIM, HUD_ACC, 1.0 if passed else 0.15)
        d.line([sx, RAIL_Y, sx, RAIL_Y + 3], fill=col)
        if st["year"] not in seen:
            seen.add(st["year"])
            text(img, sx, RAIL_Y - 8, str(st["year"]), FONT_LATIN, 8, col, anchor="ct")
    mx = head_x - cam_x
    d.rectangle([mx - 1, RAIL_Y - 3, mx + 1, RAIL_Y + 5], fill=HUD_ACC)
    d.rectangle([mx - 3, RAIL_Y + 1, mx + 3, RAIL_Y + 2], fill=HUD_ACC)


def draw_hud(img: Image.Image, st: dict, idx: int, n: int) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([0, RAIL_Y + 5, W - 1, H - 1], fill=HUD_BG)
    d.line([0, RAIL_Y + 5, W - 1, RAIL_Y + 5], fill=shade(HUD_BG, 2.2))
    if st is None:
        return
    if st.get("upstream"):
        meta = f"{st['year']} · {st['lang']} · merged {st.get('commits', 1)}c"
    else:
        meta = f"{st['year']} · {st['lang']} · ★{st['stars']}"
    mw = int(font(FONT_LATIN, 10).getlength(meta)) + 2
    text(img, 6, LINE1_Y, fit(st["name"], FONT_LATIN, 11, W - 20 - mw),
         FONT_LATIN, 11, HUD_TXT)
    text(img, W - 6, LINE1_Y + 1, meta, FONT_LATIN, 10, st["rgb_hi"], anchor="rt")
    text(img, 6, LINE2_Y, fit(st["zh"], FONT_CJK, 12, W - 12 - 34),
         FONT_CJK, 12, HUD_DIM)
    text(img, W - 6, LINE2_Y + 3, f"{idx + 1}/{n}", FONT_LATIN, 9,
         shade(HUD_DIM, 0.8), anchor="rt")


# ── 主流程 ──────────────────────────────────────────────────────────────────
def load(cfg: dict) -> list[dict]:
    stations = []
    for s in cfg["stations"]:
        s = dict(s)
        col = LANG_RGB.get(s["lang"], (120, 120, 128))
        s["rgb"] = col
        s["rgb_hi"] = tuple(min(255, round(v * 1.35 + 40)) for v in col)
        s["stars"] = int(s["stars"])
        if s.get("upstream"):
            # 给别人的项目做的贡献：房高按你在那边提交多少算，屋顶画合并箭头
            s["house_h"] = 32 + round(math.sqrt(max(1, int(s.get("commits", 1)))) * 2.6)
        else:
            s["house_h"] = 30 + round(math.sqrt(s["stars"]) * 5)
        shot = (ROOT / "assets" / "screens" / s["shot"]) if s.get("shot") else None
        s["shot_path"] = shot if shot and shot.exists() else None
        s["emblem"] = s.get("emblem") or default_emblem(s)
        stations.append(s)
    return stations


def default_emblem(s: dict) -> str:
    """配置里没写 emblem 时的兜底映射"""
    return {
        "goody-utils": "toolbox",
        "basic-check": "shield",
        "gomoku": "board",
        "mybatis-gen-plugins": "db",
        "AStock-MCP": "chart",
        "my-harness-desktop": "window",
        "Synapulse": "pulse",
        "Afterglow": "play",
        "FinancialAnalysis": "bars",
        "pi plugins": "plug",
        "my-skills": "prompt",
    }.get(s["name"], "window")


def emblem_screen(st: dict, emb: Image.Image) -> Image.Image:
    """把徽章装进一块"应用窗口"：标题栏 + 发光分隔线 + 内容，免得屏幕空荡荡。"""
    col = st["rgb"]
    body = shade(col, 0.13)
    s = Image.new("RGB", (SCREEN_W, SCREEN_H), body)
    d = ImageDraw.Draw(s)
    d.rectangle([0, 0, SCREEN_W - 1, 3], fill=shade(col, 0.72))
    d.rectangle([0, 4, SCREEN_W - 1, 4], fill=shade(col, 1.0))
    for wx in (2, 5, 8):
        s.putpixel((wx, 2), shade(col, 1.6))
    s.paste(emb, (10, 5))
    d.rectangle([0, 0, SCREEN_W - 1, SCREEN_H - 1], outline=shade(col, 0.52))
    return s


def compose_screens(stations: list[dict], budget: int = 72) -> Image.Image:
    """决定每站屏幕上放什么：真截图优先，否则画语言色徽章。顺带产出全局调色板。"""
    shots = [Image.open(st["shot_path"]).convert("RGB") for st in stations if st["shot_path"]]
    # 徽章和截图一起进调色板，免得徽章的颜色被截图的调色板挤掉
    embs = [emblem(st["emblem"], st["rgb"]).to_image(shade(st["rgb"], 0.13))
            for st in stations]
    windows = [emblem_screen(st, em) for st, em in zip(stations, embs)]
    pal_img = build_palette(shots + windows, budget)
    for st, win in zip(stations, windows):
        if st["shot_path"]:
            st["screen"] = pixelate(Image.open(st["shot_path"]).convert("RGB"), pal_img)
            st["screen_kind"] = "shot"
        else:
            st["screen"] = win.quantize(palette=pal_img, dither=Image.NONE).convert("RGB")
            st["screen_kind"] = "emblem"
    return pal_img


def layout(stations: list[dict]) -> int:
    for i, st in enumerate(stations):
        st["x"] = MARGIN + i * PITCH
    return MARGIN * 2 + (len(stations) - 1) * PITCH


def frame_at(stations: list[dict], world_w: int, head_x: float, tick: int) -> Image.Image:
    cam_x = min(max(head_x - 130, 0), max(0, world_w - W))
    t = cam_x / max(1, world_w - W)
    img = Image.new("RGB", (W, H), HUD_BG)
    draw_sky(img, cam_x, world_w)
    draw_stars(img, cam_x, t)
    draw_clouds(img, cam_x, t)
    draw_far(img, cam_x, t)
    draw_ground(img, cam_x)
    for st in stations:
        if -HOUSE_W <= st["x"] - cam_x <= W + HOUSE_W:
            d = abs(head_x - st["x"])
            lit = max(0.0, 1.0 - d / 46.0)
            draw_house(img, st, st["x"] - cam_x, t, lit)
    # 影子 + 小人
    wx = head_x - cam_x
    ImageDraw.Draw(img).ellipse([wx - 5, SCENE_BOTTOM - 2, wx + 5, SCENE_BOTTOM + 1],
                                fill=shade(GROUND_MID, 0.6))
    draw_walker(img, round(wx), SCENE_BOTTOM, tick)
    near_i = min(range(len(stations)), key=lambda i: abs(stations[i]["x"] - head_x))
    near = stations[near_i] if abs(stations[near_i]["x"] - head_x) <= 60 else None
    draw_rail(img, stations, cam_x, head_x)
    draw_hud(img, near, near_i if near else 0, len(stations))
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--title", action="store_true", help="封面上加标题")
    ap.add_argument("--poster", type=float, default=None,
                    help="生成封面静帧（进度 0~1）到 out/pixelwalk-poster.png")
    ap.add_argument("--preview", type=float, default=None,
                    help="只渲染进度 t(0~1) 的一张静帧到 out/preview.png")
    ap.add_argument("--colors", type=int, default=64, help="全局调色板颜色数")
    ap.add_argument("--scale", type=int, default=3, help="放大倍数")
    ap.add_argument("--out", default=str(ROOT / "out"))
    args = ap.parse_args()

    cfg = json.loads((ROOT / "projects.json").read_text())
    stations = load(cfg)
    world_w = layout(stations)
    pal_img = compose_screens(stations, args.colors)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    walk_from, walk_to = 40, world_w - 40

    if args.poster is not None:
        head = walk_from + (walk_to - walk_from) * args.poster
        img = frame_at(stations, world_w, head, 6)
        if args.title:
            bar = 16
            d = ImageDraw.Draw(img)
            d.rectangle([0, 0, W - 1, bar - 1], fill=(12, 14, 22))
            d.rectangle([0, bar, W - 1, bar], fill=(58, 130, 190))
            d.rectangle([0, bar + 1, W - 1, bar + 1], fill=(26, 32, 48))
            text(img, 6, 2, "PIXEL WALK", FONT_LATIN, 13, (248, 250, 255))
            text(img, W - 6, 4, "2019 - 2026   /   14 PROJECTS",
                 FONT_LATIN, 10, (150, 200, 240), anchor="rt")
        img.resize((W * args.scale, H * args.scale), Image.NEAREST) \
           .save(out / "pixelwalk-poster.png")
        print(out / "pixelwalk-poster.png")
        return 0

    if args.preview is not None:
        head = walk_from + (walk_to - walk_from) * args.preview
        img = frame_at(stations, world_w, head, int(args.preview * 24))
        img.resize((W * args.scale, H * args.scale), Image.NEAREST).save(out / "preview.png")
        print(out / "preview.png")
        return 0

    n = args.frames
    frames = []
    for i in range(n):
        head = walk_from + (walk_to - walk_from) * (i / max(1, n - 1))
        frames.append(frame_at(stations, world_w, head, i))
    # 低分辨率下量化，再最近邻放大 —— 又快又保证每个像素块颜色一致。
    # 注：Pillow 的 GIF 编码器只做矩形差分、不认逐像素透明，所以帧间差分在这里
    # 省不出体积，别白费劲；要更小只能压画布或减帧数。
    pframes = [f.quantize(palette=pal_img, dither=Image.NONE)
                .resize((W * args.scale, H * args.scale), Image.NEAREST) for f in frames]
    gif = out / "pixelwalk.gif"
    pframes[0].save(gif, save_all=True, append_images=pframes[1:],
                    duration=round(1000 / args.fps), loop=0, optimize=True)
    mb = gif.stat().st_size / 1024 / 1024
    print(f"{gif}  {len(pframes)} 帧  {W*args.scale}x{H*args.scale}  {args.colors}色  {args.fps}fps  "
          f"{len(pframes)/args.fps:.1f}s  {mb:.2f} MiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
