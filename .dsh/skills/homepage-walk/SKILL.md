---
name: homepage-walk
description: 生成 / 更新 / 发布「homepage-walk」——把参与过的项目排成一条街，像素小人走过去、逐站点亮屏幕，输出一张放 GitHub 主页的循环 GIF。用于：重新渲染或更新这张图、增删改站台与文案、换某站的屏幕截图、加自绘徽章图案、调画布尺寸和体积、出封面、发布到 GitHub 主页。触发词：homepage-walk、像素漫步、Pixel Walk、项目街、项目编年史、主页那张图、更新主页动画、加一个站台、换屏幕图、生成封面、走一遍项目。
whenToUse: 用户提到 homepage-walk / 像素漫步 / 主页那张项目街的图，或要增删站台、换屏幕图、改文案、重渲染、调体积、发到 GitHub。
---

# homepage-walk

把参与过的项目排成一条 2018 → 2026 的街。像素小人从左走到右，每经过一间房，
房上那块"屏幕"就亮起来。**房高 = star 数，房色 = 主语言**，天色随走过进度从破晓走到入夜，
底部 HUD 报出当前项目的名字 / 年份 / 语言 / 成绩 / 一句中文备注。

| | |
|---|---|
| 项目目录 | **这个仓库的根目录**（下称项目目录；本机是 `/Users/goodyhao/toy/homepage-walk/`） |
| 主页仓库 | `GOODDAYDAY/GOODDAYDAY`，README 里 `images/pixelwalk/pixelwalk.gif` 那一段 |
| 主页仓库本地克隆 | `/Users/goodyhao/toy/contriboom-out/profile-repo` |
| 解释器 | `/Users/goodyhao/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3`（下称 `$PY`） |
| 依赖 | 只有 **Pillow + numpy**。**本机的 `/usr/bin/python3` 没装 Pillow**，所以一律用 `$PY`；换机器先 `pip install -r requirements.txt` |
| 当前产物 | 960×342，14 站，180 帧 / 12.5fps / **14.4 秒**，1.97 MiB |

**设计原则：全程离线。** 不联网、不调 GitHub API、不装依赖，同样输入永远出同样结果。
如果哪次改动需要联网才能跑，那多半是走错路了。

## 0 该跑哪条命令

| 改了什么 | 命令 |
|---|---|
| 文案 / 排序 / 站台增删 / 换 `shot` | `$PY render.py` （约 4 秒） |
| 调画面（布局、颜色、房子、小人、HUD） | `$PY render.py --preview 0.45` —— **秒出静帧，调画面一律用这个** |
| 出封面 | `$PY render.py --poster 0.52 --scale 4 --title` |
| 发布到主页 | 见 §6 |

**改画面时不要反复跑整段。** 先 `--preview` 看几个时刻（0.02 破晓 / 0.45 白天 / 0.80 入夜），定了再出片。

## 1 结构

```
projects.json ──┐
                ├──► render.py ──► out/pixelwalk.gif
assets/screens/ ┘                  out/pixelwalk-poster.png
```

```
homepage-walk/
├── projects.json      # 唯一配置入口：14 个站台
├── render.py          # 渲染器：320×114 世界像素绘制，最后最近邻放大 3 倍
├── assets/screens/    # 真实截图（当前为空；配置里 3 个 shot_source 记着出处）
└── out/
```

**判据**：配置里有 `"shot": "文件名.png"` 且 `assets/screens/` 里真有这个文件 → 用真实截图；
否则用 `"emblem"` 指定的自绘徽章。

> 早先有一套 `fetch_screens.py` 自动抓图管线（扫 README → 下载 → 打分 → 存候选 → 复核图），
> **已删除**。理由：30 个仓库只有 3 张图过质量线，为 3 张图养 330 行抓取代码不划算；
> 而且打分器经常把图标和 sprite sheet 排第一，最后都得人工纠。
> 手工放图 15 分钟，结果更好。**不要把它加回来。**

## 2 projects.json 全字段

```jsonc
{
  "name": "FrameRonin-MCP",   // 站台名 = HUD 第一行
  "repos": ["FrameRonin-MCP"],// 仓库名，只存配置里备查，画面不显示
  "year": 2026,               // 年份石牌 + 底部刻度轨
  "lang": "Python",           // 主语言 → 房子配色（见文件末尾 palette）
  "stars": 12,                // 房高 = 30 + round(√stars × 5)，HUD 显示 ★12
  "zh": "AI 生成像素游戏素材，12 颗星是全街最亮的招牌",
  "shot": "frameronin-mcp.png",  // 可选：assets/screens/ 里的文件名
  "emblem": "chart",             // 没有 shot 时画这个徽章
  "upstream": true,              // 可选：给别人的开源项目做的贡献
  "commits": 14                  // upstream 专用：在那边提交了多少次
}
```

- **加站 / 删站 / 换顺序** = 复制、删除、调数组顺序。房子位置和刻度轨自动重排。
- **合并同类**：`repos` 写多个仓库名，仍是一栋房（如 `basic-check-java-8` + `-17`）。
- **`upstream: true`**：房高改按 `commits` 算（`32 + √commits × 2.6`），屋顶画紫红合并箭头，
  HUD 显示 `merged 14c` 而不是 `★N`，并抑制屋顶小旗。用来把"我的项目"和"我给别人的贡献"分开。

**改完 `zh` 必须量宽度**（超了会被 `fit()` 静默截断成 `..`）：

```bash
$PY -c "
from PIL import ImageFont
f=ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc',12)
s='你的文案'; print(round(f.getlength(s)),'/ 274')"
```

上限 **274 世界像素**（`W - 12 - 34`，右边给 `n/14` 计数器留位），约 22 个汉字。
这个坑踩过两次，都是改文案时手滑加字。

## 3 换屏幕上的图

1. 裁成 **5:3**（屏幕是 40×24 世界像素，所以 640×384 之类）
2. 丢进 `assets/screens/`
3. 配置里写 `"shot": "文件名.png"`

没裁也能跑，渲染时按 5:3 居中裁切。想换回徽章就把 `shot` 删掉。

**挑图的判据**（当初打分器用的那套，人工判断时照这个来）：
细节要铺满全画面、不要大片纯色（sprite sheet、贴白底的 logo 会糊成一坨）、
饱和度别太高（图标不行）、亮度别太黑也别过曝。**像素化会把烂图变得更烂**，
深色 IDE 截图和单色 logo 一律别用，自绘徽章比糊掉的截图好看。

## 4 自绘徽章

28 种（`render.py` 的 `emblem()`）：

```
avatar bars board book cards chart chip clipboard db gear graph mask merge microservice
nodes page phone play plug potion prompt pulse robot shield sparkle tictactoe toolbox window
```

加新图案 = 加 `elif kind == "xxx":` 分支，用 `Px` 的 `rect / frame / line / disc / set`
在 **20×16** 画布上画。可用颜色变量：
`col`（语言色）、`hi`（提亮）、`lo`（压暗）、`deep`（更暗）、`white`、`warm`。

## 5 世界怎么画

世界在 **320×114** 低分辨率下绘制，最后整体最近邻放大（`--scale 3` → 960×342）。
**所有绘制按世界像素想，不要按输出像素想。**

| 常量 | 当前值 | 含义 |
|---|---|---|
| `W, H` | 320, 114 | 世界尺寸 |
| `SCENE_BOTTOM` | 72 | 地平线：房子底、小人脚底都在这 |
| `RAIL_Y` / `LINE1_Y` / `LINE2_Y` | 80 / 87 / 100 | 刻度轨 + HUD 两行 |
| `SCREEN_W, SCREEN_H` | 40, 24 | 房子上那块屏幕（= 素材尺寸） |
| `HOUSE_W` / `PITCH` / `MARGIN` | 48 / 60 / 110 | 房宽 / 站距 / 首尾留白 |
| `SKY` | 8 组 | 8 个时刻的天空色阶 |

**站台变多了要不要压 `PITCH`？** 实测：`HOUSE_W=48` / `PITCH=60` 在 **15 站**时世界宽 1060，
房子不重叠，**不用压**。判据是 `PITCH > HOUSE_W` 即可（60 > 48 有余量）；
压到 `HOUSE_W=40 / PITCH=52` 还能看，再小屏幕里的图就糊了。**先别压，撞了再压。**

**文字渲染**：`text()` 用"真字体渲染 → 阈值化"去抗锯齿，得到像素字。字号有硬下限：

- 拉丁 `Menlo.ttc`：**10–11px 最稳**，9px 会烂
- 中文 `Hiragino Sans GB.ttc`：**12px 是甜点**，11px 发虚
- **不要用 PIL 默认字体**（没有中文）；**这台机器上没有 `PingFang.ttc`**

## 6 输出与发布

体积只有**画布大小**和**帧数**两个旋钮：

| 配置 | 体积 |
|---|---|
| `--scale 3` (960×342) `--frames 180` | **1.97 MiB** ← 当前 |
| `--scale 3 --frames 240` | 2.6 MiB |
| `--scale 2` (640×228) `--frames 180` | 1.2 MiB |

体积**主要**由画布和帧数决定，但**画面内容也影响**：把 3 张复杂截图换成徽章后，
配置没变、帧数没变，体积从 2.15 掉到 1.97 MiB。

**别调调色板**（实测 32/44/72 色体积一样）；**别做帧间差分**（见 §7）。
**宽度只能选 960**：主页 `width="100%"`，GitHub 正文栏约 880px，640 会被拉伸变糊。

发布：

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd /Users/goodyhao/toy/contriboom-out/profile-repo
git fetch origin && git status --short --branch          # 先确认干净

cp /Users/goodyhao/toy/homepage-walk/out/pixelwalk.gif images/pixelwalk/pixelwalk.gif
git add images/pixelwalk/pixelwalk.gif README.md
git -c user.name="GoodyHao" \
    -c user.email="15865822+GOODDAYDAY@users.noreply.github.com" \
    commit -m "Update Pixel Walk"
git push origin main
```

### 🚨 提交身份红线

那个仓库的本地 git 身份是 `865700600@qq.com` —— **这个号是专门从历史里脱敏掉的，绝对不能用来提交**。
必须用 `-c user.email=...` 显式覆盖成 GitHub noreply 身份。
**不要用 `git config` 改它**（会持久化污染用户配置），每次带 `-c` 最安全。

那是个和 contriboom 共用的克隆，**别动 `images/contriboom/` 和 `.github/workflows/contriboom.yml`**。

### 推完验收

```bash
gh api repos/GOODDAYDAY/GOODDAYDAY/commits --jq '.[0] | "\(.sha[0:7])  \(.commit.author.name)  \(.commit.message|split("\n")[0])"'
curl -sIL -o /dev/null -w "%{http_code}\n" https://raw.githubusercontent.com/GOODDAYDAY/GOODDAYDAY/main/images/pixelwalk/pixelwalk.gif
curl -sL "https://github.com/GOODDAYDAY" | grep -oE 'src="[^"]*pixelwalk[^"]*"'
```

1. 提交作者必须是 `GoodyHao <15865822+GOODDAYDAY@users.noreply.github.com>`，不是 `865700600`
2. raw 地址 200
3. 主页 HTML 里能 grep 到引用

### 本地验收

1. `--preview` 拍 3 个时刻看画面
2. 抽 8–10 帧拼 filmstrip 检查整段（GIF 在这里只能看到第一帧，**必须自己拼**）
3. `Image.open(gif)` 看 `n_frames / size / info['duration'] / info['loop']`

## 7 踩过的坑

1. **Pillow 的 GIF 编码器只做矩形差分，不认逐像素透明。** 把"和上一帧相同的像素标成透明"
   的帧间差分实测**体积一模一样**（3.04 vs 3.04 MiB，scale=1 也是 0.53 vs 0.53）。这段代码删了。
2. **保存前必须自己最近邻放大。** 忘了 `resize((W*scale, H*scale), NEAREST)` 会得到 320×114 的 GIF。
   正确顺序：**先在低分辨率量化，再放大**。
3. **中文文案宽度上限 274 世界像素**，超了静默截断成 `..`。改文案必量。
4. **`Image.save()` 不写 `format=` 时**不认 BytesIO 的扩展名，临时验证要显式写。
5. **`draw_house` 里的坐标是浮点**（`cam_x` 来自浮点 head_x），函数开头已经 `int(round(x))`；
   裸露的 `putpixel` 换成了带边界检查的 `put()`。
6. **私有仓库绝不上街**（渲染成图 = 公开名字和描述）。
7. **别把"每天生成"当目标。** 这个账号 26/30 的仓库三个月没动过，日更会天天产出同一张图。
   真要自动化就做**事件驱动**：daily cron + 有变化才提交。
8. **README 里的数字会过期**（站台数、帧数、体积）。改完顺手核对。

## 8 版本历史与没做的事

`git log` 第一条是**精简前的基线**：`a06a98e` —— 32 站 / 280 帧 / 23 秒的全量版本。
想看或想回退：`git show a06a98e:projects.json`（**历史清过一次，旧的短哈希已失效**）。精简砍掉的是：18 个站台、
`fetch_screens.py` 整条抓图管线、`work/` 目录、`fork` 分支（保留 `upstream`）。

**没做但值得做的：SMIL 动画 SVG。** 同一套世界模型换成 SVG：
静态世界一个 `<g>`、镜头一个 `animateTransform`、小人一个 `animateTransform` + 4 帧 `<set>`、
屏幕点亮用 `opacity`、天空用 `fill` 的 `<animate>`，屏幕素材 base64 内嵌。
预计 **50–80 KB、任意缩放都清晰、GitHub camo 直接播**，比 1.97 MiB 的 GIF 强得多。
真要做的话这是下一步，也是"事件驱动更新"的前提（GIF 每天几 MB 扛不住，SVG 每次几 KB）。
