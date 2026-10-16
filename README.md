# homepage-walk

把参与过的项目排成一条街，像素小人从左走到右，每经过一间房，房上那块"屏幕"就亮起来。
**房高 = star 数，房色 = 主语言**，天色随走过进度从破晓走到入夜。
底部 HUD 报出当前项目的名字、年份、语言、成绩和一句备注。

产出一张 **960×342 的循环 GIF**，挂在 GitHub 主页 README 上。

![封面](out/pixelwalk-poster.png)

**这个仓库是自包含的**：代码、配置、素材、产物、给 AI 用的 skills，全在里面。
换台机器 clone 下来就能跑，不需要别的任何东西。

---

## 目录里有什么

```
homepage-walk/
├── projects.json            ← 唯一的配置入口：14 个站台的全部内容
├── render.py                ← 渲染器（唯一的程序，913 行）
├── .dsh/skills/             ← 给 AI 用的操作手册，随仓库走
│   ├── homepage-walk/           「怎么改这个项目」
│   └── homepage-walk-guide/     「从零搭一条 / 抓项目 / 风格怎么分」
├── README.md
├── assets/screens/          ← 想用真实截图就放这里（.gitignore 忽略，不进仓库）
└── out/                     ← 产物（.gitignore 忽略，跑一次就有）
```

**仓库里只有文本**：代码、配置、skills。图片一律不进版本控制——
二进制会撑爆 git 历史，而且这仓库的历史已经为此清过一次。

## 跑一遍

```bash
PY=/Users/goodyhao/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
# 或者任何装了 Pillow 的 python3：python3 -m pip install pillow

$PY render.py                                   # 出正片（15 秒）
$PY render.py --preview 0.45                    # 只拍一张静帧，调画面用这个，秒出
$PY render.py --poster 0.52 --scale 4 --title   # 出封面
```

**全程离线**，不联网、不调 API。同样的输入永远出同样的结果。

> 改画面时**不要反复跑整段**。先 `--preview` 拍静帧看（0.02 破晓 / 0.45 白天 / 0.80 入夜），
> 定了再出片。

## 怎么改

全部内容在 `projects.json`：

```jsonc
{
  "name": "FrameRonin-MCP",   // 站台名，也是 HUD 第一行
  "repos": ["FrameRonin-MCP"],// 对应仓库（只备查，画面不显示）
  "year": 2026,               // 年份石牌 + 底部刻度轨
  "lang": "Python",           // 主语言 → 房子配色
  "stars": 12,                // 房高 = 30 + √stars × 5，HUD 显示 ★12
  "zh": "AI 生成像素游戏素材，12 颗星是全街最亮的招牌",   // 别超 274 像素
  "shot": "frameronin-mcp.png",   // 可选：assets/screens/ 里的真实截图
  "emblem": "chart",              // 没有 shot 时画这个自绘徽章（28 种可选）
  "upstream": true,               // 可选：给别人的开源项目做的贡献
  "commits": 14                   // upstream 专用
}
```

**加一站**复制一段、**删一站**删一段、**换顺序**调数组顺序（房子和刻度自动重排）。
**合并同类**把几个仓库名塞进同一个 `repos` 数组。

---

## 以后想更新，怎么用 AI

这是这个仓库存在的主要理由。三种情况：

### 情况 1：我在电脑前，用的是 DSH

skills 已经在 `.dsh/skills/` 里，**在这个仓库目录下开一个 session，AI 会自动加载**，直接说人话：

> 「给项目街加一个站台：仓库叫 xxx，2026 年，Python」
> 「把 AStock-MCP 的文案改一下」
> 「重出一版，顺便出个新封面」
> 「发到主页上」

### 情况 2：我在别的目录开 session

把 skills 装到用户级目录，之后在任何地方都能用：

```bash
mkdir -p ~/.dsh/skills
cp -r <这个仓库>/.dsh/skills/* ~/.dsh/skills/
```

### 情况 3：我换了台机器 / 重装了

```bash
git clone https://github.com/GOODDAYDAY/homepage-walk.git
cd homepage-walk
cp -r .dsh/skills/* ~/.dsh/skills/     # 让 AI 认识这个项目
$PY render.py                          # 验证能跑
```

clone 下来跑一次 `render.py`，产物会出现在 `out/`。

### 想从零重做一条（换账号 / 帮别人做）

用 `homepage-walk-guide` skill，里面带一个能跑的脚本：

```bash
python3 .dsh/skills/homepage-walk-guide/scripts/fetch_projects.py <用户名> > projects.json
```

10 秒拉完所有仓库，自动过滤（私有必丢、fork 默认丢）、猜徽章、猜该合并哪几组、
扫出哪些仓库有好截图可挑。产出的骨架再人工过一遍（脚本会打印一份 `_todo` 五条）。

---

## 发到主页

主页仓库的本地克隆在 `/Users/goodyhao/toy/contriboom-out/profile-repo`（和 contriboom 共用）：

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd /Users/goodyhao/toy/contriboom-out/profile-repo
git fetch origin && git status --short --branch     # 先确认干净

cp /Users/goodyhao/toy/homepage-walk/out/pixelwalk.gif images/pixelwalk/pixelwalk.gif

git add images/pixelwalk/pixelwalk.gif README.md
git -c user.name="GoodyHao" \
    -c user.email="15865822+GOODDAYDAY@users.noreply.github.com" \
    commit -m "Update Pixel Walk"
git push origin main
```

> ### 🚨 提交身份（最容易出事的一条）
>
> 那个仓库的本地 git 身份是 `865700600@qq.com`，**是专门从历史里脱敏掉的，不能用来提交**。
> 必须像上面那样用 `-c user.email=...` 覆盖成 GitHub noreply 身份。
> **别用 `git config` 改**（会持久化污染配置），每次带 `-c` 最安全。
>
> 那个克隆里还装着 contriboom 的产物，**别动 `images/contriboom/` 和
> `.github/workflows/contriboom.yml`**。

### 推完验收

```bash
gh api repos/GOODDAYDAY/GOODDAYDAY/commits --jq '.[0] | "\(.sha[0:7])  \(.commit.author.name)  \(.commit.message|split("\n")[0])"'
curl -sIL -o /dev/null -w "%{http_code}\n" https://raw.githubusercontent.com/GOODDAYDAY/GOODDAYDAY/main/images/pixelwalk/pixelwalk.gif
curl -sL "https://github.com/GOODDAYDAY" | grep -oE 'src="[^"]*pixelwalk[^"]*"'
```

---

## 版本历史

`git log` 第一条是**精简前的基线**：`a06a98e` —— 32 站 / 280 帧 / 23 秒的全量版本，
里面还留着当时那套自动抓图管线（`fetch_screens.py`）和一份 issue 草稿。

```bash
git show a06a98e:projects.json                   # 看 32 站配置
git show a06a98e:work/attic/upstream-issue.md    # 找回那份草稿
```

> **历史清过一次**：所有 `.png` / `.gif` 已从全部提交里移除（`git filter-repo --invert-paths`）。
> 那 3 张截图在 `projects.json` 里留了 `shot_source` 字段记着出处，想用随时能重新裁。

精简砍掉的：18 个站台、`fetch_screens.py` 整条抓图管线、`work/` 目录、`fork` 分支（保留 `upstream`）。
理由写在 `homepage-walk` skill 的 §1 末尾——**别把它加回来**。

## 关于名字

叫 `homepage-walk` 是为了跟另一个项目区分开：GitHub 上有个活跃的
[`JilinJL/PixelWalk`](https://github.com/JilinJL/PixelWalk)（`pixelwalk.fun`），
是个**浏览器里的实时像素世界**，跟这个出图的工具零关系。
账号上那个 `PixelWalk` fork 是它的副本，跟本项目无关。

## 以后可以做的

**重新加回真实截图**：3 个站台的 `shot_source` 记着原来的出处
（`practice1/picture/architecture.png`、`ChromePilot/docs/images/1. drink water 10 times.gif`、
`FrameRonin-MCP/docs/assets/demo-full-pipeline.png`）。取回来裁成 5:3 丢进 `assets/screens/`，
那一站加回 `shot` 字段即可。

**SMIL 动画 SVG**：同一套世界模型换成 SVG —— 静态世界一个 `<g>`、镜头一个 `animateTransform`、
小人一个 `animateTransform` + 4 帧 `<set>`、屏幕点亮用 `opacity`、素材 base64 内嵌。
预计 **50–80 KB、任意缩放都清晰、GitHub camo 直接播**，比 2.15 MiB 的 GIF 强得多。
缺点是要重写渲染层。想做的信号：**你开始嫌 GIF 糊或者嫌 2 MB 大**。
