# homepage-walk

把参与过的项目排成一条街，像素小人从左走到右，每经过一间房，房上那块"屏幕"就亮起来。
**房高 = star 数，房色 = 主语言**，天色随走过进度从破晓走到入夜。
底部 HUD 报出当前项目的名字、年份、语言、成绩和一句备注。

产物是一张 **960×342 的循环 GIF**，放 GitHub 主页 README 用。

| 文件 | 说明 |
| --- | --- |
| `out/pixelwalk.gif` | 正片：14 站 / 180 帧 / 12fps / 15 秒循环 / 2.15 MiB |
| `out/pixelwalk-poster.png` | 封面静帧 1280×456，带标题条 |

![预览](out/pixelwalk-poster.png)

## 跑一遍

```bash
PY=/Users/goodyhao/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3

$PY render.py                                   # 出正片
$PY render.py --preview 0.45                    # 只拍一张静帧到 out/preview.png（调画面用，秒出）
$PY render.py --poster 0.52 --scale 4 --title   # 出封面
```

**全程离线**，不联网、不调 API、不装依赖（只要有 Pillow）。同样的输入永远出同样的结果。

改画面时**不要反复跑整段**（15 秒），先 `--preview` 拍静帧看，定了再出片。

## 改什么

全部内容在 `projects.json`，改完重跑 `render.py` 即可。

```jsonc
{
  "name": "FrameRonin-MCP",   // 站台名，也是 HUD 第一行
  "repos": ["FrameRonin-MCP"],// 对应仓库（只存配置里备查，画面不显示）
  "year": 2026,               // 年份石牌 + 底部刻度轨
  "lang": "Python",           // 主语言 → 房子配色
  "stars": 12,                // 房高 = 30 + √stars × 5，HUD 显示 ★12
  "zh": "AI 生成像素游戏素材，12 颗星是全街最亮的招牌",
  "shot": "frameronin-mcp.png",      // 可选：用 assets/screens/ 里的真实截图当屏幕
  "emblem": "chart"                  // 没有 shot 时，画这个自绘徽章
}
```

- **加一站**：复制一段。**删一站**：删一段。**换顺序**：调数组顺序（房子和刻度自动重排）。
- **合并同类**：`repos` 里写多个仓库名，还是一栋房。
- **给上游做的贡献**：加 `"upstream": true, "commits": 14` —— 房高按在那边提交多少算，
  屋顶画一个合并箭头，HUD 显示 `merged 14c`，跟自己项目区分开。

### 换屏幕上的图

把裁好的图丢进 `assets/screens/`，然后在配置里写 `"shot": "文件名.png"`。就这样。

建议裁成 **5:3**（屏幕是 40×24 世界像素），也就是 640×384 之类。不裁也能跑，
渲染时会按 5:3 居中裁切。

> 早先版本有一套自动抓图管线（扫 README → 下载 → 打分 → 挑候选）。已经删掉了：
> 30 个仓库里只有 3 张图真的配当屏幕，为了这 3 张养 300 多行抓取代码不划算，
> 而且自动挑经常挑到图标和 sprite sheet，最后还是要人工纠。手工放图 15 分钟搞定，结果还更好。

### 自绘徽章

27 种现成图案（`render.py` 的 `emblem()`）：

```
avatar bars board book cards chart chip clipboard db gear graph mask merge microservice
nodes page phone play plug potion prompt pulse robot shield sparkle tictactoe toolbox window
```

加新图案 = 加一个 `elif kind == "xxx":` 分支，用 `Px` 画布 API
（`rect / frame / line / disc / set`）在 **20×16** 画布上画。可用颜色：
`col`（语言色）、`hi`（提亮）、`lo`（压暗）、`deep`（更暗）、`white`、`warm`。

## 体积

只有**画布大小**和**帧数**两个旋钮：

| 配置 | 体积 |
| --- | --- |
| `--scale 3` (960×342) `--frames 180` | **2.15 MiB** ← 当前 |
| `--scale 3 --frames 240` | 2.8 MiB |
| `--scale 2` (640×228) `--frames 180` | 1.4 MiB |

**别去调调色板**：实测 32 色 / 44 色 / 72 色出来的文件一样大，编码器瓶颈不在调色板。
**也别想用帧间差分**：Pillow 的 GIF 编码器只做矩形差分，不认逐像素透明，实测前后体积一模一样。

**宽度选 960**：主页 README 用 `width="100%"`，GitHub 正文栏约 880px。
640 会被浏览器拉伸到 880 变糊，960 只是轻微缩小。

## 发到主页

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd /Users/goodyhao/toy/contriboom-out/profile-repo   # 主页仓库的本地克隆
git fetch origin && git status --short --branch      # 先确认干净

cp /Users/goodyhao/toy/homepage-walk/out/pixelwalk.gif images/pixelwalk/pixelwalk.gif

git add images/pixelwalk/pixelwalk.gif README.md
git -c user.name="GoodyHao" \
    -c user.email="15865822+GOODDAYDAY@users.noreply.github.com" \
    commit -m "Update Pixel Walk"
git push origin main
```

> ⚠️ **提交身份**：那个仓库的本地 git 身份是 `865700600@qq.com`，是专门从历史里脱敏掉的，
> **不能用来提交**。必须像上面那样用 `-c user.email=...` 覆盖成 GitHub noreply 身份。
> 别用 `git config` 改（会持久化污染配置），每次带 `-c` 最安全。
>
> 那个克隆里还装着 contriboom 的产物，**别动 `images/contriboom/` 和
> `.github/workflows/contriboom.yml`**。

## 文件地图

```
homepage-walk/
├── projects.json      # 唯一配置入口
├── render.py          # 渲染器（320×114 世界像素绘制，最后最近邻放大 3 倍）
├── assets/screens/    # 你自己放的真实截图
└── out/               # 产物
```

`render.py` 里的关键开关：世界尺寸 `W, H`、地平线 `SCENE_BOTTOM`、房子宽度/间距
`HOUSE_W / PITCH`、天空色阶 `SKY`（8 个时刻）、小人 `WALK_FRAMES`（4 帧走路循环）。

## 版本历史

`git log` 里第一条是精简前的基线（**32 站 / 280 帧 / 3.73 MiB 的全量版本**）。
想看或想回退：`git show 4e86147:projects.json`。
