#!/usr/bin/env python3
"""抓取并筛选每个站台的屏幕素材。

流程：读 README -> 抽出所有非 badge 图片 -> 下载 -> 去信箱边 -> 打分排序
     -> 前 3 名存进 work/candidates，第 1 名存成 work/screens/<slug>.png

用 `--sheet` 生成一张复核用的对比图；如果自动挑的那张不合适，就在 projects.json 的
screen.url 里写死想要的图片路径，重跑即可。
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
WORK = ROOT / "work"
CAND = WORK / "candidates"
PICK = WORK / "screens"
OWNER = "GOODDAYDAY"          # 由 projects.json 的 owner 字段覆盖
RAW = "https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"

SCREEN_AR = 40 / 24
BADGE = re.compile(
    r"img\.shields\.io|shields\.io|badge|badgen\.net|codecov|travis|circleci|"
    r"visitor|profile-counter|komarev|star-history|wakatime|github-readme-stats",
    re.I,
)
MAX_CANDIDATES = 12
MIN_SCORE = 52.0        # 低于这个分数就不配当"屏幕"，改用本地生成的语言卡片


def slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name).strip("-").lower()


def gh_api(url: str) -> dict:
    token = os.environ.get("GH_TOKEN") or subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True
    ).stdout.strip()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "pixelwalk",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


DEFAULT_OWNER = "GOODDAYDAY"


def split_repo(repo: str) -> str:
    """支持 "name"（用默认 owner）和 "owner/name"（外部仓库）"""
    return repo if "/" in repo else f"{DEFAULT_OWNER}/{repo}"


def readme_images(repo: str) -> list[str]:
    """README 里出现的、排除 badge 之后的图片路径（原样，可能是相对路径）"""
    try:
        d = gh_api(f"https://api.github.com/repos/{OWNER}/{repo}/readme")
        txt = base64.b64decode(d["content"]).decode("utf-8", "replace")
    except Exception:                                        # noqa: BLE001
        return []
    urls = re.findall(r"!\[[^\]]*\]\(([^)\s]+)", txt)
    urls += re.findall(r"<img[^>]+src=[\"']([^\"']+)", txt)
    out, seen = [], set()
    for u in urls:
        u = u.strip()
        if u.startswith("data:") or BADGE.search(u) or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def download(url: str) -> Image.Image | None:
    r = subprocess.run(["curl", "-sL", "--fail", "--max-time", "60", url],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        im = Image.open(io.BytesIO(r.stdout))
        im.seek(0)
        return im.convert("RGB")
    except Exception:                                        # noqa: BLE001
        return None


def trim_uniform(im: Image.Image, tol: int = 12, max_frac: float = 0.30) -> Image.Image:
    a = np.asarray(im).astype(np.int16)
    h, w, _ = a.shape
    max_y, max_x = int(h * max_frac), int(w * max_frac)
    top = 0
    while top < max_y and a[top].std(axis=0).max() <= tol:
        top += 1
    bot = h
    while bot > h - max_y and a[bot - 1].std(axis=0).max() <= tol:
        bot -= 1
    left = 0
    while left < max_x and a[:, left].std(axis=0).max() <= tol:
        left += 1
    right = w
    while right > w - max_x and a[:, right - 1].std(axis=0).max() <= tol:
        right -= 1
    if right - left < w * 0.4 or bot - top < h * 0.4:
        return im
    return im.crop((left, top, right, bot))


def best_crop(im: Image.Image, ar: float) -> Image.Image:
    w, h = im.size
    if w / h > ar:
        ch, cw = h, max(1, round(h * ar))
    else:
        cw, ch = w, max(1, round(w / ar))
    if cw >= w and ch >= h:
        return im
    small = im.convert("L").resize((max(2, w // 4), max(2, h // 4)), Image.BOX)
    s = np.asarray(small).astype(np.float32)
    sw, sh = max(1, cw // 4), max(1, ch // 4)
    if s.shape[1] <= sw or s.shape[0] <= sh:
        return im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch))
    ii = np.cumsum(np.cumsum(s, 0), 1)
    ii2 = np.cumsum(np.cumsum(s * s, 0), 1)

    def box(m, y, x):
        a = m[y + sh - 1, x + sw - 1]
        b = m[y - 1, x + sw - 1] if y > 0 else 0.0
        c = m[y + sh - 1, x - 1] if x > 0 else 0.0
        d = m[y - 1, x - 1] if y > 0 and x > 0 else 0.0
        return a - b - c + d

    ys = np.linspace(0, s.shape[0] - sh, min(26, s.shape[0] - sh + 1)).astype(int)
    xs = np.linspace(0, s.shape[1] - sw, min(26, s.shape[1] - sw + 1)).astype(int)
    n = sw * sh
    best, best_score = (0, 0), -1.0
    for y in ys:
        for x in xs:
            var = box(ii2, y, x) / n - (box(ii, y, x) / n) ** 2
            cy = (y + sh / 2) / s.shape[0] - 0.5
            cx = (x + sw / 2) / s.shape[1] - 0.5
            score = var * (1.0 - 0.18 * (abs(cy) + abs(cx)))
            if score > best_score:
                best_score, best = score, (int(y), int(x))
    y, x = best
    return im.crop((x * 4, y * 4, min(w, x * 4 + cw), min(h, y * 4 + ch)))


def score(im: Image.Image, orig: tuple[int, int]) -> tuple[float, dict]:
    """给候选图打分：要的是"像一块产品界面"，不是图标、不是 sprite sheet、不是一片纯色。

    图标/sprite 的特征是"高饱和 + 大片纯色背景 + 细节全挤在中间"，
    截图的特征是"细节铺满全画面 + 饱和度不高 + 有明暗面板"。
    """
    small = np.asarray(im.convert("RGB").resize((80, 48), Image.LANCZOS)).astype(np.float32)
    lum = small @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    mx, mn = small.max(axis=2), small.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0.0)

    mean_lum = float(lum.mean())
    std_lum = float(lum.std())
    q = (small // 24).astype(np.int32)
    key = q[..., 0] * 121 + q[..., 1] * 11 + q[..., 2]
    _, counts = np.unique(key, return_counts=True)
    flat = float(counts.max() / key.size)

    gx = np.abs(np.diff(lum, axis=1))
    gy = np.abs(np.diff(lum, axis=0))
    edge = float(gx.mean() + gy.mean())
    sat_mean = float(sat.mean())

    # 细节是不是铺满全画面：4x4 分块边缘密度的变异系数
    def grid_mean(a: np.ndarray, n: int = 4) -> np.ndarray:
        h, w = a.shape
        hh, ww = (h // n) * n, (w // n) * n
        return a[:hh, :ww].reshape(n, hh // n, n, ww // n).mean(axis=(1, 3))

    e = grid_mean(gx) + grid_mean(gy)
    cv = float(e.std() / max(e.mean(), 1e-6))
    uniformity = math.exp(-max(0.0, cv - 0.45) * 1.5)

    ow, oh = orig
    ar = ow / max(1, oh)
    ar_score = math.exp(-abs(math.log(max(ar, 0.05) / SCREEN_AR)) * 1.1)
    size_score = min(1.0, (ow * oh) / (700 * 440)) ** 0.5

    s = 0.0
    s += 18 * ar_score
    s += 22 * min(1.0, edge / 24) * uniformity          # 有细节，且铺满
    s += 14 * (1.0 - min(1.0, flat / 0.45))             # 不要大片纯色
    s += 16 * math.exp(-max(0.0, sat_mean - 0.22) * 5)  # 高饱和 = 图标，扣分
    s += 10 * min(1.0, std_lum / 55)
    s += 12 * math.exp(-((mean_lum - 132) / 90) ** 2)   # 别太黑也别过曝
    s += 6 * size_score
    return s, {"lum": round(mean_lum), "std": round(std_lum), "flat": round(flat, 2),
               "edge": round(edge, 1), "sat": round(sat_mean, 2), "cv": round(cv, 2),
               "ar": round(ar, 2)}


def resolve(repo: str, path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    return RAW.format(owner=OWNER, repo=repo,
                      path=urllib.parse.quote(path.lstrip("./"), safe="/"))


def candidates_for(st: dict) -> tuple[str, list]:
    """返回 (slug, [{'url','score','feat','img'} ...]) 按分数降序"""
    s = slug(st["name"])
    spec = st["screen"]
    if spec["source"] != "readme":
        return s, []
    repo = st["repos"][0]
    paths = readme_images(repo)
    if spec.get("url"):
        paths = [spec["url"]] + [p for p in paths if p != spec["url"]]
    paths = paths[:MAX_CANDIDATES]
    out = []

    def work(p: str):
        url = resolve(repo, p)
        im = download(url)
        if im is None:
            return None
        orig = im.size
        if orig[0] < 180 or orig[1] < 120:
            return None
        cropped = best_crop(trim_uniform(im), SCREEN_AR)
        sc, feat = score(cropped, orig)
        return {"url": p, "score": round(sc, 1), "feat": feat, "img": cropped}

    with ThreadPoolExecutor(max_workers=5) as pool:
        for r in pool.map(work, paths):
            if r:
                out.append(r)
    out.sort(key=lambda r: -r["score"])
    if spec.get("url"):                       # projects.json 里写死的图，必须排第一
        for i, r in enumerate(out):
            if r["url"] == spec["url"]:
                out.insert(0, out.pop(i))
                break
    return s, out


def build_sheet(rows: list[tuple[str, list]], dest: pathlib.Path, top: int = 3) -> None:
    f_name = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 15)
    f_meta = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 11)
    TW, TH, PAD, LAB = 200, 120, 12, 34
    cols = top
    W = PAD + cols * (TW + PAD)
    H = PAD + len(rows) * (TH + LAB + PAD)
    sheet = Image.new("RGB", (W, H), (18, 18, 24))
    d = ImageDraw.Draw(sheet)
    for r, (name, cands) in enumerate(rows):
        y = PAD + r * (TH + LAB + PAD)
        d.text((PAD, y - 1), name, font=f_name, fill=(235, 240, 250))
        for c in range(cols):
            x = PAD + c * (TW + PAD)
            if c < len(cands):
                cd = cands[c]
                tile = cd["img"].resize((40, 24), Image.LANCZOS).resize((TW, TH), Image.NEAREST)
                sheet.paste(tile, (x, y + 18))
                ft = cd["feat"]
                d.text((x, y + 18 + TH + 2),
                       f"#{c+1} score {cd['score']}  lum{ft['lum']} std{ft['std']} "
                       f"flat{ft['flat']} e{ft['edge']}", font=f_meta, fill=(140, 150, 170))
            else:
                d.rectangle([x, y + 18, x + TW, y + 18 + TH], outline=(40, 42, 52))
    sheet.save(dest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true", help="只生成复核图，不重新抓取")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "projects.json").read_text())
    global OWNER
    OWNER = cfg.get("owner", OWNER)     # 换账号只需改 projects.json 的 owner
    CAND.mkdir(parents=True, exist_ok=True)
    PICK.mkdir(parents=True, exist_ok=True)

    if args.sheet:
        rows = []
        for st in cfg["stations"]:
            s = slug(st["name"])
            files = sorted(CAND.glob(f"{s}-*.png"))
            cands = [{"img": Image.open(f), "score": f.stem.split("-")[-1],
                      "feat": {"lum": "", "std": "", "flat": "", "edge": ""}} for f in files]
            rows.append((st["name"], cands))
        build_sheet(rows, WORK / "_candidates.png")
        print(WORK / "_candidates.png")
        return 0

    rows, report = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(candidates_for, cfg["stations"]))

    for st, (s, cands) in zip(cfg["stations"], results):
        for old in CAND.glob(f"{s}-*.png"):
            old.unlink()
        forced = bool(st["screen"].get("force"))   # force: true 时无视质量线，硬用指定那张
        good = [c for c in cands if forced or c["score"] >= MIN_SCORE]
        for i, cd in enumerate(cands[:3]):
            cd["img"].save(CAND / f"{s}-{i+1}.png")
        if good:
            good[0]["img"].save(PICK / f"{s}.png")
            ft = good[0]["feat"]
            report.append(f"  ok   {st['name']:<24} {len(cands):>2} 候选  首选 {good[0]['score']:>5}  "
                          f"lum{ft['lum']} std{ft['std']} flat{ft['flat']} e{ft['edge']} "
                          f"sat{ft['sat']} cv{ft['cv']}  <- {good[0]['url'][:52]}")
        else:
            (PICK / f"{s}.png").unlink(missing_ok=True)
            top = cands[0]["score"] if cands else 0
            report.append(f"  gen  {st['name']:<24} {'无图' if not cands else f'最佳仅 {top} 分，不够格'} -> 本地生成")
        rows.append((st["name"], cands[:3]))

    # 清掉生成型站台的残留
    for st in cfg["stations"]:
        if st["screen"]["source"] != "readme":
            (PICK / f"{slug(st['name'])}.png").unlink(missing_ok=True)

    build_sheet(rows, WORK / "_candidates.png")
    print("\n".join(report))
    print(f"\n复核图 {WORK / '_candidates.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
