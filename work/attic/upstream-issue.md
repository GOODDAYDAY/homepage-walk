# 待提交 Issue 草稿 · JilinJL/PixelWalk

> 状态：**草稿，尚未提交**。
> 目标仓库：`JilinJL/PixelWalk`（`main` @ `1c36162`，`node v24.21.0`）
> 建议标题：`[讨论] 想提代码贡献：让"有背景的图"也能进创作页`
> 建议标签：无（先不开标签，等维护者判断）

---

## 中文正文

先说明来意：我想提的是**代码**，不是风景投稿。翻了一下仓库，`CONTRIBUTING.md` 只覆盖美术投稿，贡献者里也只有你自己，所以先开 Issue 问方向——如果不收代码贡献、或者这个方向不对，直接说就行，我不会硬塞 PR。

### 我试创作页时遇到的问题

随手拿一张普通截图（GitHub 自动生成的仓库卡片 PNG，完全不透明）去试，走不下去。查代码之后发现是三件事叠在一起，我都做了最小复现。

### 最小复现

纯 RGBA 合成，不依赖任何外部文件，放在仓库根目录 `node repro-issue.cjs` 即可：

```js
const P = require('./pixelate.js');
const make = (w, h, draw) => {
  const data = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const [r, g, b, a] = draw(x, y), i = (y * w + x) * 4;
    data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = a;
  }
  return { width: w, height: h, data };
};
const subj = (x, y) => x > 200 && x < 440 && y > 180 && y < 300;
const run = (name, img) => {
  try {
    const r = P.pixelate(img, 'large'), tally = {};
    for (let i = 0; i < 160 * 160; i++) if (r.data[i * 4 + 3]) {
      const k = r.data[i*4] + ',' + r.data[i*4+1] + ',' + r.data[i*4+2];
      tally[k] = (tally[k] || 0) + 1;
    }
    const top = Object.entries(tally).sort((a, b) => b[1] - a[1])[0];
    console.log(name, 'ACCEPT', 'grid=' + r.grid.cols + 'x' + r.grid.rows,
                ' dominant=' + top[0] + ' (' + top[1] + 'px)');
  } catch (e) { console.log(name, 'REJECT', e.message); }
};
run('1 opaque white background  ', make(640, 480, (x,y) => subj(x,y) ? [220,120,80,255] : [255,255,255,255]));
run('2 transparent, 1px margin  ', make(640, 640, (x,y) => (x>0&&x<639&&y>0&&y<639) ? [120,160,210,255] : [0,0,0,0]));
run('3 letterbox bars           ', make(640, 480, (x,y) => (y<60||y>420) ? [0,0,0,255] : subj(x,y) ? [220,120,80,255] : [0,0,0,0]));
run('4 clean cut-out (control)  ', make(640, 480, (x,y) => subj(x,y) ? [220,120,80,255] : [0,0,0,0]));
```

实际输出：

```
1 opaque white background   REJECT 需要透明背景
2 transparent, 1px margin   REJECT 需要透明背景
3 letterbox bars            ACCEPT grid=37x28  dominant=0,0,0 (1890px)
4 clean cut-out (control)   ACCEPT grid=37x19  dominant=227,115,69 (5355px)
```

（第 4 行是作为对照的合规输入。）

### 三件事

**① 不透明的图直接被拒（第 1 行）**

`pixelate.js:50` 的 `if(clear/(W*H)<.01)fail('需要透明背景')`。白底截图、纯色底的图、GitHub 卡片，全都过不去。这个是主要痛点。

顺带一提，前面还有一道闸：`app.js:88` 只收 `image/png` 和 `image/webp`，**JPEG 截图连选都选不了**。而截图最常见的格式就是 JPEG。

**② 这条判断卡的是"透明面积"，不是"有没有透明背景"（第 2 行）**

第 2 行的输入有**完整的透明背景**，只是主体留了 1px 的透明边（clear = 0.62%），照样被拒，错误信息还是 `需要透明背景`。用户明明已经抠好图了，却被告知需要透明背景 —— 他没法从这句话知道下一步该做什么。

**③ 信箱黑边能过检，但会被当成画面画进去（第 3 行）**

这条我觉得最值得处理。`pixelate()` 用 alpha≥128 求包围盒，上下两条不透明黑边把包围盒撑成了整个画框，于是：

| | 网格 | 主导颜色 | 主体像素 |
| --- | --- | --- | --- |
| 3 有信箱黑边 | 37×28 | `0,0,0`（1890px） | 702px |
| 4 干净抠好的对照 | 37×19 | `227,115,69`（5355px） | 5355px |

同一个主体，被黑边一撑：网格比例从 2:1 变成 4:3，**主体像素缩到 1/7.6**，黑边本身成了画面里最大的一块。

关键在于**它通过了全部自动校验**——`clear` 是 65.6%，远超 1%，`sanitizePng` 也不会拦。坏结果会一路走到人工审核，占用你的时间。

### 根因

`pixelate()` 把两件不同的事用一个判断兜住了：

- 「这张图没有透明通道，用户得先抠图」——这是用户要解决的问题；
- 「这张图有透明通道，只是主体占比大 / 边上有不透明的东西」——这不是问题。

两者都落到 `clear/(W*H)<.01`，所以拿到同一句 `需要透明背景`。

### 我建议的改法

在 `pixelate()` 前面加一步**纯函数预处理**，把两种情况分开，并补上"从带底的图里找出主体"。不碰 `World`，不改 `settings.js` 的 schema：

```
1. 先按现有逻辑算 alpha 边界与 clear 比例
2. clear >= 1%  → 保持现在的行为，一步不动
3. clear < 1%   → 先尝试分离背景：
     · 从四边逐行/逐列扫描，找出近似纯色（容差可调）的边缘并逐层裁掉
     · 裁完重算 clear，达标就继续走原流程
     · 四边都不是纯色（真的是一张全幅插画）→ 仍然报错，
       但换成可区分的错误信息，例如「没有找到可分离的背景，请先抠掉背景再上传」
4. 第 3 步同时能修掉信箱边：先裁边再求包围盒，网格比例和主体大小就回到对照组的水平
```

覆盖白底、黑底、纯色底、信箱边——这几种占了"用户手里的图"的大多数。第 4 步和第 3 步是同一段代码，不额外增加改动面。

我还做过一个独立的小点，可以拆开单独讨论：裁切窗口默认居中，主体偏在角落时会切歪，按信息量挑窗口可以缓解。你觉得没必要就砍掉。

这两步我在自己的项目里用 Python 实现过，可以先发对比图再决定要不要。

### 测试计划

按 `tests/pixelate.test.cjs` 的写法补：

- 不透明纯色底 + 居中主体 → 裁边后网格尺寸与"已抠好版本"一致
- 上下黑条的信箱图 → 黑条被裁掉，不再出现在输出里（对应上面第 3 行）
- 全幅插画（四边都非纯色）→ 仍然报错，且错误信息可与"没有透明通道"区分
- **已经合规的透明 PNG → 输出与改动前逐字节一致**（回归保护，这条最关键）
- 容差边界：背景带渐变或噪点时不应误裁主体

### 两个附带的问题

1. **这个仓库收代码贡献吗？** 仓库里没有面向代码的贡献说明，贡献者也只有你自己。如果不收，或者你希望先在你自己的分支上验证再决定合不合，都请直说。
2. **LICENSE**：仓库根目录没有 LICENSE（只有 `assets/audio/LICENSE.md`），`package.json` 是 `"private": true`。如果要接外部代码，可能需要先明确授权方式。

如果这个方向不合适，也完全没问题——我就把它做成自己的离线工具，不往上游推。

---

## English

First, what I'm asking for: **code**, not a scenery submission. I read the repo — `CONTRIBUTING.md` only covers artwork, and you're the only contributor — so I'd rather ask first. If code contributions aren't wanted, or this direction is wrong, just say so and I won't push a PR.

### What I hit in the studio

I tried an ordinary screenshot (a fully opaque GitHub repository card PNG) and couldn't get through. Reading the code, it's three separate things stacked up. Minimal reproduction for all three below.

### Reproduction

Pure RGBA synthesis, no external files. Drop this in the repo root and run `node repro-issue.cjs`:

```js
const P = require('./pixelate.js');
const make = (w, h, draw) => {
  const data = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const [r, g, b, a] = draw(x, y), i = (y * w + x) * 4;
    data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = a;
  }
  return { width: w, height: h, data };
};
const subj = (x, y) => x > 200 && x < 440 && y > 180 && y < 300;
const run = (name, img) => {
  try {
    const r = P.pixelate(img, 'large'), tally = {};
    for (let i = 0; i < 160 * 160; i++) if (r.data[i * 4 + 3]) {
      const k = r.data[i*4] + ',' + r.data[i*4+1] + ',' + r.data[i*4+2];
      tally[k] = (tally[k] || 0) + 1;
    }
    const top = Object.entries(tally).sort((a, b) => b[1] - a[1])[0];
    console.log(name, 'ACCEPT', 'grid=' + r.grid.cols + 'x' + r.grid.rows,
                ' dominant=' + top[0] + ' (' + top[1] + 'px)');
  } catch (e) { console.log(name, 'REJECT', e.message); }
};
run('1 opaque white background  ', make(640, 480, (x,y) => subj(x,y) ? [220,120,80,255] : [255,255,255,255]));
run('2 transparent, 1px margin  ', make(640, 640, (x,y) => (x>0&&x<639&&y>0&&y<639) ? [120,160,210,255] : [0,0,0,0]));
run('3 letterbox bars           ', make(640, 480, (x,y) => (y<60||y>420) ? [0,0,0,255] : subj(x,y) ? [220,120,80,255] : [0,0,0,0]));
run('4 clean cut-out (control)  ', make(640, 480, (x,y) => subj(x,y) ? [220,120,80,255] : [0,0,0,0]));
```

Actual output:

```
1 opaque white background   REJECT 需要透明背景
2 transparent, 1px margin   REJECT 需要透明背景
3 letterbox bars            ACCEPT grid=37x28  dominant=0,0,0 (1890px)
4 clean cut-out (control)   ACCEPT grid=37x19  dominant=227,115,69 (5355px)
```

(Row 4 is a compliant control input.)

### The three things

**1. Opaque images are rejected outright (row 1)**

`pixelate.js:50`: `if(clear/(W*H)<.01)fail('需要透明背景')`. White-background screenshots, flat-colour backgrounds, GitHub cards — none get through. This is the main pain point.

There's an earlier gate too: `app.js:88` accepts only `image/png` and `image/webp`, so **a JPEG screenshot can't even be selected** — and JPEG is what screenshots usually are.

**2. The check tests transparent *area*, not whether a transparent background *exists* (row 2)**

Row 2 has a complete transparent background; the subject just leaves a 1px margin (clear = 0.62%). It's rejected with `需要透明背景` all the same. The user has already cut the image out and is told they need a transparent background — the message gives them nothing to act on.

**3. Letterbox bars pass validation but get baked into the artwork (row 3)**

This one seems most worth fixing. `pixelate()` takes the bounding box of alpha≥128, so two opaque bars stretch the box to the whole frame:

| | grid | dominant colour | subject pixels |
| --- | --- | --- | --- |
| 3 with letterbox bars | 37×28 | `0,0,0` (1890px) | 702px |
| 4 clean control | 37×19 | `227,115,69` (5355px) | 5355px |

Same subject: the grid aspect goes from 2:1 to 4:3, **the subject shrinks to 1/7.6**, and the bars become the largest single element in the artwork.

The important part is that **it passes every automated check** — `clear` is 65.6%, far above 1%, and `sanitizePng` doesn't stop it. The bad result reaches human review and costs your time.

### Root cause

`pixelate()` uses one check for two different situations:

- "this image has no alpha channel; the user must remove the background" — the user's problem;
- "this image has alpha, but the subject covers most of it / something opaque sits at the edges" — not a problem at all.

Both land on `clear/(W*H)<.01`, hence the same `需要透明背景`.

### Proposed change

Add a **pure-function preprocessing step** in front of `pixelate()`, separating the two cases and covering "find the subject in an image that has a background". No changes to `World`, no changes to the `settings.js` schema:

```
1. Compute the alpha bounds and clear ratio exactly as today.
2. clear >= 1%  -> keep today's behaviour, not a single step different.
3. clear < 1%   -> try to separate a background first:
     - scan inward from each edge, row by row / column by column, for
       near-uniform (tolerance-based) borders and trim them
     - recompute clear; if it passes now, continue through the existing path
     - if no edge is uniform (a genuine full-bleed illustration) -> still fail,
       but with a distinguishable message, e.g. "no separable background found;
       please remove the background before uploading"
4. Step 3 also fixes the letterbox case: trimming first and taking the bounds
   afterwards restores the grid aspect and subject size to the control's level.
```

That covers white, black, flat-colour and letterboxed backgrounds — most of what users actually have. Steps 3 and 4 are the same code path, so this doesn't widen the change.

There's one separate, smaller thing I can split out if you prefer: the crop window is centred today, so a subject in a corner gets cut off; choosing the window by information density would help. Happy to drop it.

I've implemented both in Python in my own project and can send comparison images before you decide.

### Test plan

Following the style of `tests/pixelate.test.cjs`:

- opaque flat background + centred subject → after trimming, grid dimensions match the pre-cut-out version
- letterboxed image → bars trimmed and absent from the output (row 3 above)
- full-bleed illustration (no uniform edge) → still fails, with a message distinguishable from "no alpha channel"
- **an already-compliant transparent PNG → byte-identical output before and after the change** (regression guard; this one matters most)
- tolerance boundaries: a gradient or noisy background must not eat into the subject

### Two side questions

1. **Are code contributions welcome here?** There's no code-facing contribution guide and you're the only contributor. If the answer is no, or you'd rather validate it on your own branch first, please just say.
2. **LICENSE**: there's no root LICENSE (only `assets/audio/LICENSE.md`), and `package.json` is `"private": true`. Accepting outside code may need an explicit grant first.

If this direction doesn't fit, that's completely fine — I'll keep it as my own offline tool instead of pushing it upstream.
