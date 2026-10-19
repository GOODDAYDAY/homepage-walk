#!/usr/bin/env python3
"""从一个 GitHub 账号拉出所有仓库 → 过滤 → 打标 → 生成 projects.json 骨架。

只产出**配置文本**，不下载任何图片。屏幕素材仍然手工放（原因见 SKILL.md）。

用法：
    python3 fetch_projects.py GOODDAYDAY > projects.json
    python3 fetch_projects.py GOODDAYDAY --include-forks
    python3 fetch_projects.py GOODDAYDAY --limit 300 --keep-archived

输出：stdout 是 projects.json；过滤报告和合并提示走 stderr，不污染 JSON。
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

# ── 徽章建议 ────────────────────────────────────────────────────────────────
# 顺序 = 优先级，越具体越靠前。短词按"词边界"匹配 —— 否则 "ios" 会命中
# scenarios、"orm" 会命中 platform、"sql" 会命中 sqlite，一错一大片。
EMBLEM_HINTS: list[tuple[tuple[str, ...], str]] = [
    # 中文描述很常见，每组都要带中文词，否则一个都命不中
    (("stock", "trading", "finance", "financial", "quant", "kline", "backtest",
      "股票", "行情", "选股", "财务", "量化", "交易", "金融", "投资"), "chart"),
    (("mcp", "model context protocol", "plugin", "addon", "add-on",
      "插件", "扩展"), "plug"),
    (("multi-agent", "orchestrator", "orchestration", "workflow", "pipeline",
      "langgraph", "swarm", "crew", "sub-agent",
      "多智能体", "编排", "工作流", "流水线"), "nodes"),
    (("skill", "prompt", "dotfile", "cli", "技能", "提示词", "命令行"), "prompt"),
    (("microservice", "micro-service", "gateway", "grpc", "rpc", "service mesh",
      "微服务", "网关", "服务化"), "microservice"),
    (("mybatis", "database", "postgres", "mysql", "jdbc", "redis", "orm",
      "数据库", "持久层"), "db"),
    (("chart", "metric", "statistic", "analytics", "visualization",
      "图表", "统计", "可视化", "看板"), "bars"),
    (("agent", "llm", "gpt", "deepseek", "claude", "openai", "chatbot",
      "智能体", "大模型", "机器人"), "robot"),
    (("chrome extension", "browser extension", "browser", "chrome", "firefox",
      "frontend", "react", "vue", "svelte", "桌面", "浏览器", "前端", "客户端"), "window"),
    (("blog", "website", "homepage", "wiki", "hexo", "jekyll", "hugo",
      "博客", "网站", "主页", "文档站"), "page"),
    (("android", "ios", "mobile app", "flutter", "wechat", "miniprogram",
      "移动端", "小程序", "安卓"), "phone"),
    (("toolbox", "toolkit", "utility", "utilities", "utils", "helper", "sdk",
      "工具箱", "工具库", "工具集", "常用工具"), "toolbox"),
    (("book", "vocabulary", "dictionary", "translation", "language learning",
      "词典", "生词", "翻译", "背单词", "语言学习"), "book"),
    (("game", "puzzle", "roguelike", "rpg", "游戏", "棋", "桌游"), "board"),
    (("auth", "secure", "validator", "validation", "guard", "permission",
      "校验", "验证", "鉴权", "权限"), "shield"),
    (("scheduler", "queue", "cron", "batch job", "定时", "任务队列", "表单"), "clipboard"),
    (("voice", "speech", "audio", "sound", "music", "tts", "asr",
      "语音", "音频", "声音", "波形", "音乐"), "pulse"),
    (("mod", "patch", "hook", "inject", "药水", "模组", "补丁"), "potion"),
    (("graph", "topology", "cluster", "拓扑", "关系图", "节点图"), "graph"),
    (("chip", "embedded", "esp32", "arduino", "firmware", "iot",
      "嵌入式", "单片机", "硬件", "物联网"), "chip"),
]

# 先看名字形状，命中就不走关键词（比关键词准）
NAME_RULES: list[tuple[tuple[str, ...], str]] = [
    ((".github.io",), "page"),
    (("tic-tac-toe", "tictactoe", "tic_tac_toe"), "tictactoe"),
    (("gomoku", "gomuku", "chess", "shogi"), "board"),
    (("leetcode", "algorithm", "awesome-"), "book"),
    (("werewolf", "masquerade", "undercover"), "mask"),
    (("curator", "tastebud", "recommend"), "sparkle"),
    (("desktop", "electron", "dashboard", "gui"), "window"),
]

# 名字里直接出现某个徽章名就用它（synapulse → pulse、my-potion-craft → potion）
EMBLEM_WORDS = (
    "microservice", "clipboard", "tictactoe", "toolbox", "sparkle", "avatar",
    "window", "potion", "shield", "prompt", "pulse", "chart", "board", "phone",
    "robot", "graph", "cards", "merge", "nodes", "book", "play", "mask", "chip",
    "gear", "bars", "page", "plug",
)

# 明显是练习/玩具的名字，只提示不强制排除
NOISE_HINTS = ("homework", "exercise", "lab", "practice", "study", "demo", "sample",
               "tutorial", "try", "tmp", "temp", "scratch")

# 用来猜"这几个仓库其实是一个项目"的后缀
MERGE_SUFFIXES = (
    "-java-8", "-java-11", "-java-17", "-java-21", "-java-25",
    "-frontend", "-front-end", "-backend", "-back-end", "-server", "-client",
    "-web", "-api", "-ui", "-core", "-lib", "-sdk", "-cli", "-service",
    "-orchestrator", "-toolbox", "-multi-agent", "-plugins", "-plugin",
    "-2", "-v2", "-old", "-new",
)

# README 里扫图用的 badge 黑名单
BADGE = re.compile(
    r"img\.shields\.io|shields\.io|badge|badgen\.net|codecov|travis|circleci|"
    r"visitor|profile-counter|komarev|star-history|wakatime|github-readme-stats", re.I)

ZH_LIMIT_PX = 274          # HUD 第二行的可用宽度（世界像素）
CJK_FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
ZH_PLACEHOLDER = "（用一句中文说明这个项目干了什么）"


def _run_gh(args: list[str]) -> subprocess.CompletedProcess:
    """调 gh，顺便把"没装 gh"变成一句人话。"""
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit(
            "找不到 `gh` 命令。这个脚本靠 GitHub CLI 拉仓库列表。\n"
            "  装：https://cli.github.com/    （macOS: brew install gh）\n"
            "  登录：gh auth login\n"
            "  只想手动写配置？这个脚本可以不用，projects.json 是纯文本，照 README 的字段手写即可。")


def gh_json(args: list[str]) -> list[dict]:
    out = _run_gh(args)
    if out.returncode != 0:
        sys.exit(f"gh 调用失败：{out.stderr.strip()}")
    return json.loads(out.stdout)


def readme_images(owner: str, repo: str) -> list[str]:
    """看这个仓库的 README 里有没有能当屏幕用的图（只查不下载）。"""
    r = _run_gh(["api", f"repos/{owner}/{repo}/readme", "--jq", ".content"])
    if r.returncode != 0:
        return []
    try:
        txt = base64.b64decode(r.stdout.strip()).decode("utf-8", "replace")
    except Exception:                                       # noqa: BLE001
        return []
    urls = re.findall(r"!\[[^\]]*\]\(([^)\s]+)", txt)
    urls += re.findall(r"<img[^>]+src=[\"\']([^\"\']+)", txt)
    out, seen = [], set()
    for u in urls:
        u = u.strip()
        if u.startswith("data:") or BADGE.search(u) or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _hit(blob: str, keys: tuple[str, ...]) -> bool:
    """纯字母词按词边界匹配，带符号的（.github.io / tic-tac-toe）直接子串匹配。"""
    for k in keys:
        bare = k.replace("-", "").replace(" ", "")
        if k.isascii() and bare.isalpha():
            pat = re.escape(k).replace(r"\ ", r"[\s-]").replace(r"\-", r"[\s-]")
            tail = r"s?\b" if len(bare) >= 4 else r"\b"     # skills / plugins / agents
            if re.search(r"\b" + pat + tail, blob):
                return True
        elif k in blob:
            return True
    return False


def suggest_emblem(name: str, *texts: str, owner: str = "") -> str:
    low = name.lower()
    if owner and low == owner.lower():
        return "avatar"                                   # 主页仓库自己
    for keys, emblem in NAME_RULES:
        if _hit(low, keys):
            return emblem
    flat = re.sub(r"[-_]", "", low)
    for w in EMBLEM_WORDS:
        if w in flat and w != "window":
            return w                                      # 名字自带徽章名
    blob = " ".join(t.lower() for t in texts if t)
    for keys, emblem in EMBLEM_HINTS:
        if _hit(blob, keys):
            return emblem
    return "window"                                       # 兜底


# ── 文案处理 ────────────────────────────────────────────────────────────────
def text_px(s: str) -> int:
    """量中文文案的像素宽度。没有 PIL 就按 1 个汉字 = 12px、其他 = 6px 估。"""
    try:
        from PIL import ImageFont
        return int(ImageFont.truetype(CJK_FONT, 12).getlength(s))
    except Exception:                                     # noqa: BLE001
        return sum(12 if ord(c) > 0x2E80 else 6 for c in s)


def fit_zh(desc: str | None, limit: int = ZH_LIMIT_PX) -> str:
    """仓库描述多半是英文，硬截断出来是半句废话，不如留中文占位让人来写。"""
    s = " ".join((desc or "").split())
    if not s:
        return ZH_PLACEHOLDER
    if sum(c.isascii() for c in s) / len(s) > 0.7:
        return ZH_PLACEHOLDER
    while s and text_px(s) > limit:
        s = s[:-1]
    return s.rstrip(" ,.;:-、，。；：") or ZH_PLACEHOLDER


def merge_key(name: str) -> str:
    n = name.lower()
    for suf in MERGE_SUFFIXES:
        if n.endswith(suf):
            return n[: -len(suf)]
    return n


# ── 主流程 ──────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("owner")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--include-forks", action="store_true",
                    help="把 fork 也收进来（默认丢；'给上游的贡献'另有 upstream 字段）")
    ap.add_argument("--keep-archived", action="store_true")
    ap.add_argument("--min-stars", type=int, default=0)
    ap.add_argument("--max-stations", type=int, default=0,
                    help="超过这个数量就按 star 排序截断（0 = 不截断）")
    ap.add_argument("--no-readme-scan", action="store_true",
                    help="跳过 README 扫图（默认会扫，用来告诉你哪些仓库有好截图可挑）")
    args = ap.parse_args()

    repos = gh_json([
        "repo", "list", args.owner, "--limit", str(args.limit), "--json",
        "name,description,primaryLanguage,createdAt,pushedAt,isFork,isArchived,"
        "isEmpty,stargazerCount,visibility,repositoryTopics",
    ])

    kept, dropped = [], []
    for r in repos:
        why = None
        if r.get("visibility") != "PUBLIC":
            why = "私有（渲染成图 = 公开名字和描述，绝不上街）"
        elif r.get("isEmpty"):
            why = "空仓库"
        elif r.get("isFork") and not args.include_forks:
            why = "fork（要收上游贡献请用 upstream 字段，或加 --include-forks）"
        elif r.get("isArchived") and not args.keep_archived:
            why = "已归档"
        elif r["stargazerCount"] < args.min_stars:
            why = f"star < {args.min_stars}"
        if why:
            dropped.append((r, why))
        else:
            kept.append(r)

    kept.sort(key=lambda r: (r["createdAt"], r["name"]))
    if args.max_stations and len(kept) > args.max_stations:
        kept.sort(key=lambda r: (-r["stargazerCount"], r["createdAt"]))
        for r in kept[args.max_stations:]:
            dropped.append((r, f"超出 max-stations={args.max_stations} 被截断"))
        kept = sorted(kept[: args.max_stations], key=lambda r: (r["createdAt"], r["name"]))

    stations = []
    for r in kept:
        topics = [t["name"] if isinstance(t, dict) else str(t)
                  for t in (r.get("repositoryTopics") or [])]
        desc = r.get("description") or ""
        stations.append({
            "name": r["name"],
            "repos": [r["name"]],
            "year": int(r["createdAt"][:4]),
            "lang": (r.get("primaryLanguage") or {}).get("name") or "Python",
            "stars": r["stargazerCount"],
            "zh": fit_zh(desc),
            "emblem": suggest_emblem(r["name"], desc, " ".join(topics), owner=args.owner),
        })

    print(json.dumps({
        "_comment": "由 homepage-walk-guide/scripts/fetch_projects.py 生成，必须人工过一遍。",
        "_todo": [
            "① zh 有占位的要逐条改写成中文，别超 274 像素（脚本里有 text_px 可以量）",
            "② 核对 emblem 猜得对不对，28 种可选，见 render.py 的 emblem()",
            "③ 同类仓库合并成一站：仓库名塞进同一个 repos 数组，删掉多余站台",
            "④ 给别人的开源项目做的贡献，加 upstream: true + commits: N",
            "⑤ 有合适截图的裁成 5:3 丢进 assets/screens/，这一站加 shot 字段",
        ],
        "stations": stations,
        "palette": {
            "Python": "#3572A5", "Java": "#B07219", "JavaScript": "#F1E05A",
            "TypeScript": "#3178C6", "C#": "#178600", "Rust": "#DEA584",
            "Shell": "#89E051", "Mermaid": "#FF3670", "HTML": "#E34C26",
        },
    }, ensure_ascii=False, indent=2))

    # ── 报告走 stderr，不污染 JSON ──
    e = sys.stderr
    print(f"\n仓库总数 {len(repos)} → 保留 {len(kept)}，丢弃 {len(dropped)}", file=e)
    if dropped:
        print("\n丢弃明细：", file=e)
        for r, why in dropped:
            print(f"  ✗ {r['name']:<40} {why}", file=e)

    noise = [r["name"] for r in kept
             if any(h in r["name"].lower() for h in NOISE_HINTS) or r["stargazerCount"] == 0]
    if noise:
        print(f"\n建议再人工筛一遍（练习/玩具/0 star，共 {len(noise)} 个，不一定都要删）：", file=e)
        for n in noise:
            print(f"  ? {n}", file=e)

    if not args.no_readme_scan and kept:
        with ThreadPoolExecutor(max_workers=6) as pool:
            found = list(pool.map(lambda r: readme_images(args.owner, r["name"]), kept))
        withimg = [(r["name"], imgs) for r, imgs in zip(kept, found) if imgs]
        if withimg:
            print(f"\nREADME 里有图可挑的仓库（{len(withimg)}/{len(kept)} 个）"
                  f"—— 裁成 5:3 放进 assets/screens/，这一站加 shot 字段：", file=e)
            for name, imgs in withimg:
                print(f"  📷 {name:<38} {len(imgs)} 张，例：{imgs[0][:56]}", file=e)
            print("  注意：有图 ≠ 能用。深色 IDE 截图 / 单色 logo / sprite sheet 像素化后是糊的，"
                  "宁可画徽章。", file=e)

    groups: dict[str, list[str]] = {}
    for r in kept:
        groups.setdefault(merge_key(r["name"]), []).append(r["name"])
    merges = {k: v for k, v in groups.items() if len(v) > 1}
    if merges:
        print("\n可能是同一个项目，建议合并成一站（几个仓库塞进同一个 repos 数组）：", file=e)
        for k, v in merges.items():
            print(f"  {k}  ←  {', '.join(v)}", file=e)

    print("\n下一步：stdout 存成 projects.json，按 _todo 五条人工过一遍。", file=e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
