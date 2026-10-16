# 像素漫步 · Pixel Walk

把一个 GitHub 账号里**参与过的项目**排成一条 2018 → 2026 的街。像素小人从左走到右，
每经过一间房，房上那块"屏幕"就亮起来。房高 = star 数（fork 按 commit 数、上游贡献按合并数），
房色 = 主语言，天色随走过进度从破晓走到入夜。底部 HUD 报出当前项目的名字、年份、语言、成绩和一句中文备注。

收录三类：**自己的公开仓库**、**fork 里本人真有提交的**、**给别人的开源项目提的贡献**
（最后一类屋顶有紫色合并标记）。私有仓库和纯搬运的 fork 都不上街。

产物：

| 文件 | 说明 |
| --- | --- |
| `out/pixelwalk.gif` | 正片，960×342，280 帧 / 12fps / 23 秒循环，约 3.7 MiB |
| `out/pixelwalk-poster.png` | 封面静帧，1280×456（黄昏那一刻） |

## 跑一遍

```bash
PY=/Users/goodyhao/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3

$PY fetch_screens.py     # 抓图 + 打分挑图（第一次跑或改了 projects.json 之后跑）
$PY render.py            # 出 GIF
$PY render.py --poster 0.52 --scale 4 --title    # 出封面
```

常用参数：

```bash
$PY render.py --frames 280 --fps 12 --scale 3 --colors 64   # 默认
$PY render.py --preview 0.45        # 只渲一张静帧到 out/preview.png，调画面时用这个
$PY render.py --poster 0.8 --title  # 换封面时刻
```

## 改什么

**全部内容都在 `projects.json`**，改完重跑 `render.py` 即可（换图才需要先跑 `fetch_screens.py`）。

```jsonc
{
  "name": "FrameRonin-MCP",        // 站台上显示的名字，HUD 第一行
  "repos": ["FrameRonin-MCP"],     // 对应仓库，写多个就是几合一站
  "year": 2026,                    // 年份石牌 + 刻度轨
  "lang": "Python",                // 决定房子配色（见文件末尾 palette）
  "stars": 12,                     // 决定房子高度，也显示在 HUD
  "en": "...",                     // 英文备注（当前 HUD 用中文那行，这个是预留）
  "zh": "...",                     // HUD 第二行，中文字数别超过约 22 个字
  "screen": { "source": "readme", "url": "docs/assets/demo-full-pipeline.png" }
}
```

`screen` 三种写法：

- `{"source": "readme", "url": "路径"}` —— 用仓库里的某张图。写了 `url` 会把它排到候选第一名，
  但**仍然要过质量线**；没过就退回徽章。
- `{"source": "readme", "url": "路径", "force": true}` —— 无视质量线硬用这张。
- `{"source": "generated"}` —— 用本地画的语言色徽章。

想加一站就复制一段；想删就删一段；想换顺序就调数组顺序（房子位置和刻度会自动重排）。

## 收录了什么

32 个站台，来源分三类：

**① 自己名下的公开仓库（29 站）** —— 非 fork 的 30 个公开仓库全收，同类合并成一站：
`basic-check-java-8/17`、`value-checker-java-8/17`、`gomoku-frontend` + `gomuku-backend`、
`pi-multi-agent` + `pi-orchestrator` + `pi-toolbox`。私有仓库一律不进（渲染成图 = 公开名字和描述）。

**② fork 来的仓库（4 站）** —— 只收**本人真的有提交**的：`SmartVM`(1)、`langgraph`(1)、
`llmapp05`(3)、`nanobot`(1)。纯搬运的 13 个（`dify`、`math`、`pi`、`LeetCode` 这些）不进片子。
fork 的房子矮一截，HUD 显示 `fork Nc` 而不是 `★`。

**③ 给别人的开源项目提的贡献（3 站）** —— 这类最容易被漏掉，因为**只扫自己名下的仓库根本看不见**：

| 站台 | 上游仓库 | 你的提交 |
| --- | --- | --- |
| `xiaozhi-esp32-server` | `xinnan-tech/xiaozhi-esp32-server` | 14（PR #1204 已合并） |
| `dsh-pocket` | `shaobeichen/dsh-pocket` | 4 |
| `ratel` | `ainilili/ratel` | 2 |

上游贡献的房子屋顶线用 GitHub 合并紫 `#8957E5`、顶上画一个合并箭头、
HUD 显示 `merged Nc`，屏幕是 git 分支合并图，**跟自己项目和 fork 都区分得开**。

> 公司项目（`bobofzhang/facemagic*`、`avatarplus-backend`、`chainext/ChaiNext_API`，
> 提交量 226/108/68/17，是这里面最大的几批）**按用户要求不进片子**。

### 怎么扫出来的（踩过的坑）

只查"自己名下的仓库"会漏掉第 ③ 类。正确做法是两步：

1. 自己名下：`gh repo list` + fork 用 `commits?author=<用户名>` 判有没有提交
2. **别人名下**：commit 搜索按年切片扫（不分年会被 1000 条上限截断），
   然后按 **SHA 集合**归并 —— 因为一批提交会被 fork 网络复制到几十个仓库里

两个具体的坑：

- **`?author=<用户名>` 只匹配主邮箱，不匹配 GitHub noreply 邮箱。** 拿 `GOODDAYDAY` 主页仓库实测：
  它明明有 5 个本人提交，`author=GOODDAYDAY` 返回 **0**，换成 noreply 邮箱查才返回 5。
  筛 fork 时**两个邮箱都要查**。（这个账号的 20 个 fork 恰好都用主邮箱，所以结论没变，纯属走运。）
- **`search/commits` 不索引 fork 仓库**，按 `repo:` 限定查 fork 一律返回 0，不能拿它当判据。
- **一批提交 ≠ 一个仓库。** 实测 86 个"有提交"的仓库其实只有 **10 批**不同的提交：
  68 个仓库装的是同一批 14 个提交（小智上游那批被 fork 得到处都是），
  10/6/1 个提交的那几批是它们各自的子集。直接数仓库会把贡献量算成几十倍。

## 图像是怎么来的（这块是重点）

每个项目的屏幕内容按这个顺序定：

1. **扫 README**，抽出所有图片（自动滤掉 shields.io 之类的 badge）
2. **下载 + 处理**：GIF 取第一帧 → 裁掉信箱黑边 → 滑动窗口挑"信息量最大"的一块裁成 5:3
3. **打分**，判据是"像不像一块产品界面"：
   - 细节要铺满全画面（4×4 分块边缘密度的变异系数）
   - 不要大片纯色（sprite sheet、logo 贴白底会被扣分）
   - 不要太高的饱和度（图标会被扣分）
   - 亮度别太黑也别过曝、宽高比接近 5:3、原图别太小
4. **分数 ≥ 52 才配当屏幕**，否则退回本地生成的语言色徽章（`render.py` 里的 `emblem()`）
5. 所有屏幕（真图 + 徽章）一起丢进**同一张全局调色板**再做像素化 —— 这一步是关键：
   风格迥异的图源（截图 / 演示 GIF / banner / 纯图标）被强行统一成同一个世界

实测 30 个非 fork 公开仓库里，只有 3 张图过了这条线（`practice1` 的架构图、`ChromePilot` 的浏览器
截图、`FrameRonin-MCP` 的精灵图总览），其余全是自动生成的语言色徽章。这个结果是诚实的：
大部分仓库的 README 里只有 logo 或者过暗的 IDE 截图，像素化之后就是一坨糊的，不如自己画。
（`my-harness-desktop`、`Synapulse`、`Afterglow` 三个本来也想用真图，实测太暗被刷掉了，
`projects.json` 里那条 `note` 记着原因。）

复核用：`fetch_screens.py` 会把每站的前 3 名候选拼成 `work/_candidates.png`，
自动挑的那张不满意就在这里看，然后把想要的路径写进 `projects.json` 的 `screen.url` 强制指定。

## 画布尺寸与体积

世界在 **320×114** 的低分辨率下绘制，最后整体最近邻放大（默认 3 倍 → 960×342）。
所以任何改动都要按世界像素来想，不要按输出像素。

体积上有个坑已经踩过了：**Pillow 的 GIF 编码器只做矩形差分，不认逐像素透明**，
所以"把没变的像素标成透明"这种帧间差分省不出任何体积（实测 diff 前后一模一样大）。
能压体积的只有两个旋钮：**画布大小**和**帧数**。

| 配置 | 体积 |
| --- | --- |
| scale=3 (960×342), 280 帧 | **3.73 MiB** ← 当前 |
| scale=3 (960×342), 240 帧 | 3.26 MiB |
| scale=2 (640×228), 280 帧 | 2.16 MiB |

主页 README 用 `width="100%"`，GitHub 正文栏约 880px。所以 **640 宽会被浏览器拉伸到 880 → 糊**，
960 宽只是轻微缩小，是唯一合理的选择；再想瘦只能减帧数。

同一套渲染逻辑换成 **SMIL 动画 SVG** 会又清晰又小（几十 KB 量级），
而且 GitHub 的 camo 图片代理能直接播 —— contriboom 走的就是这条路。要上主页的话这是下一步。

## 文件地图

```
pixelwalk/
├── projects.json         # 唯一的配置入口：14 个站台的全部内容
├── fetch_screens.py      # 抓图 + 裁切 + 打分挑图
├── render.py             # 世界渲染器 + GIF/封面输出（主程序）
├── work/
│   ├── screens/          # 选中的屏幕素材（已裁切成 5:3）
│   └── candidates/       # 每站前 3 名候选，复核用
└── out/
    ├── pixelwalk.gif
    └── pixelwalk-poster.png
```

`render.py` 里的几个关键开关：世界尺寸 `W, H`、地平线 `SCENE_BOTTOM`、房子宽度/间距
`HOUSE_W / PITCH`、天空色阶 `SKY`（8 个时刻）、小人 `WALK_FRAMES`（4 帧走路循环）、
每站的徽章图案 `emblem()`。
