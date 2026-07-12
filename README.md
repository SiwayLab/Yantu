# Markdown 离线交互式思维导图生成器

将 Markdown 中的标题、列表和图片转换为可离线打开的交互式 HTML 思维导图。项目仅依赖 Python 标准库，无需安装第三方包。

生成结果会自动打包字体、本地图片、封面背景和 Logo，适合课堂汇报、论文答辩、项目演示以及层级大纲浏览。

## 主要能力

- 解析 `#` 至 `######` 六级标题。
- 解析无序列表和有序列表，并根据缩进建立父子层级。
- 生成带折叠、聚焦、局部清晰、全图缩放、浏览器全屏和图片预览的交互式导图。
- 生成类似 PPT 的演示封面，支持主副标题、作者、单位、日期、背景和四角 Logo。
- 支持键盘和常见翻页笔的前后节点导航。
- 自动打包 Markdown 和配置文件引用的本地资源。
- 处理同名图片冲突、缺失资源和不安全资源协议。
- 对普通文本和 HTML 属性进行转义，避免输入破坏输出页面。
- 支持交互选择文件，也支持完整的命令行参数。

## 环境要求

- Python 3.10 或更高版本。
- 支持现代 HTML、CSS 和 JavaScript 的浏览器。

```bash
python3 --version
```

## 快速开始

### 直接生成

在项目目录中执行：

```bash
python3 md_to_mindmap.py "大纲.md" --cover --show-cover-on-open
```

默认会在 Markdown 文件旁创建一个同名目录：

```text
大纲/
├── 大纲.html
├── icons/
│   ├── iconfont.woff2
│   ├── iconfont.woff
│   └── iconfont.ttf
└── images/
    └── Markdown、背景和 Logo 使用的本地资源
```

双击 `大纲/大纲.html` 即可离线查看。移动生成结果时，应整体移动输出目录，不要只复制 HTML 文件。

### 交互选择

把待转换的 `.md` 文件放在项目根目录，然后运行：

```bash
python3 md_to_mindmap.py
```

程序会列出项目根目录中的 Markdown 文件。隐藏文件和 `README.md` 不会出现在选择列表中。

当封面功能已启用且没有传入默认展示参数时，终端会继续询问：

```text
是否在打开生成文件时默认显示封面？ [Y/n]:
```

直接回车使用 `config.conf` 中 `show_on_open` 的默认值。

### 指定输出目录

```bash
python3 md_to_mindmap.py "大纲.md" --output-dir "/tmp/大纲导图"
```

`-o` 是 `--output-dir` 的缩写。

## 页面交互

### 封面

- 封面任意位置均可点击进入导图。
- 封面显示时，空格、回车、`Esc`、方向键或 `PageDown` 均可进入导图。
- 进入导图时会展开并聚焦根节点，然后自动执行“全图缩放”，展示第一层分支概览。
- 双击工具栏主页按钮可以随时重新显示封面。
- 如果生成时完全关闭封面，双击主页按钮不会产生封面。

### 节点

| 操作 | 结果 |
| --- | --- |
| 点击节点内容 | 聚焦当前节点及其祖先路径，并将当前节点移动到视口中央。 |
| 点击左侧 `+` | 展开直接子节点。 |
| 点击左侧 `−` | 折叠直接子节点。 |
| 点击已展开节点旁的眼睛按钮 | 保持该节点的直接子节点清晰；再次点击可主动结束。 |

“保持直接子节点清晰”是一个局部状态：

- 节点折叠时按钮不可用。
- 焦点可以在父节点及其直接子节点之间自由切换，直接子节点不会重新模糊。
- 当某个直接子节点继续展开下一级，状态自动结束。
- 当焦点跳到这组节点之外，状态自动结束。
- 该状态不会显示或隐藏节点，只控制直接子节点的模糊效果。

### 图片

| 图片状态 | 操作 | 结果 |
| --- | --- | --- |
| 所在节点未聚焦 | 单击 | 只聚焦图片所在节点。 |
| 所在节点未聚焦 | 双击 | 聚焦节点并打开全视口预览。 |
| 所在节点已聚焦 | 单击 | 直接打开全视口预览。 |
| 预览已打开 | 再次双击或按 `Esc` | 退出预览。 |
| 图片节点已聚焦 | 翻页笔“下一步” | 打开全视口预览。 |
| 预览已打开 | 翻页笔“下一步” | 退出预览；再按一次前往后续节点。 |

### 工具栏

| 按钮 | 单击 | 双击或再次单击 |
| --- | --- | --- |
| 主页 | 当前焦点离开视口时先找回焦点，否则返回根节点。 | 双击显示封面。 |
| 模糊开关 | 关闭所有非当前路径节点的模糊效果。 | 再次单击恢复焦点模糊。 |
| 全图缩放 | 缩放到一个屏幕内，保护当前聚焦路径。 | 只有当前聚焦是全局最深叶子时，双击才将其纳入折叠；其他情况下单击和双击结果相同。进入无差异或双击缩放后，再次单击或双击均退出。 |
| 浏览器全屏 | 隐藏浏览器界面并进入页面全屏。 | 再次单击或按 `Esc` 退出全屏。 |

“全图缩放”只调整导图在当前窗口中的大小；“浏览器全屏”则与视频网站的全屏按钮相同。两者可以独立使用，也可以组合使用。浏览器出于安全限制，只允许在用户主动点击全屏按钮时进入全屏。

工具栏沿用原有的右侧停靠位置，并在鼠标离开时自动淡化；将鼠标移到按钮区域后会完整显示。触屏设备无法悬停，因此会保持较高的可见度。如果配置了右上角 Logo，工具栏会自动移到右下角避让。

关闭全局模糊后，继续点击其他节点不会重新模糊旁支节点。

页面中的所有按钮均不参与键盘 Tab 焦点链，包括工具栏、节点展开/折叠按钮和直接子节点清晰按钮。使用鼠标点击后焦点会自动返回导图，不会在按钮外层持续显示焦点圈。

导图超出当前视口时，“全图缩放”会先计算整张导图的全局最大层级，只临时折叠位于这个全局最深层的可见叶子节点之父。其他较浅但已经结束的分支保持展开。单击时保护当前聚焦路径；双击时允许折叠位于全局最深层的当前聚焦节点或包含它的分支。退出缩放模式后，系统会自动恢复这些临时折叠的分支，不影响用户原有的折叠状态。

### 键盘与翻页笔

| 方向 | 支持的按键 |
| --- | --- |
| 下一步 | `PageDown`、右方向键、下方向键、空格、回车、下一首媒体键 |
| 上一节点 | `PageUp`、左方向键、上方向键、退格、上一首媒体键 |

节点导航按页面中的深度优先顺序进行，并自动展开目标节点的祖先路径。从根节点继续后退时，如果文档包含封面，则返回封面。

常见翻页笔通常会发送 `PageDown` / `PageUp` 或方向键，因此可以直接复用上述逻辑。媒体键是否生效取决于操作系统和浏览器是否将按键事件交给页面。

## Markdown 输入格式

建议每份文件只使用一个一级标题作为根节点，其余内容通过后续标题和列表展开。

```markdown
# 项目计划

## 目标

- 提升稳定性
- 改善使用体验

## 开发任务

- 后端
    - 输入校验
    - 资源打包
- 前端
    - 节点折叠
    - 全图缩放

## 里程碑

1. 完成原型
2. 编写测试
3. 发布版本
```

解析规则：

- 标题级别决定标题节点的层级。
- 列表项挂在最近出现的标题或列表父节点下。
- 列表缩进增加时进入下一层，缩进减少时返回上层。
- 兼容常见的 2 空格和 4 空格缩进。
- 支持 `-`、`+`、`*` 无序列表，以及 `1.`、`1)` 有序列表。
- 空行不影响层级。
- 不属于标题或列表的普通段落会被忽略。
- 当前只专门渲染 Markdown 图片；粗体、链接、代码块和表格不会转换为富文本。
- Markdown 中的原始 HTML 会被转义并作为普通文字显示。

## 图片与资源打包

支持标准 Markdown 图片语法：

```markdown
- ![架构图](assets/architecture.png)
- ![带空格的文件](<assets/my diagram.png>)
- ![网络图片](https://example.com/image.png)
```

路径规则：

- Markdown 图片的相对路径以 Markdown 文件所在目录为基准。
- 配置中的背景和 Logo 相对路径以配置文件所在目录为基准。
- 本地文件会复制到输出目录的 `images/`。
- 网络图片保留原始 URL，不会下载；离线打开时仍然需要网络。
- 如果同名文件内容不同，后出现的文件名会追加内容摘要，例如 `diagram-a1b2c3d4.png`。
- 再次生成时会刷新当前引用的同名资源。
- 找不到的图片会显示文字占位符，并在终端输出警告。
- `javascript:` 等不受支持的协议会被拒绝。

如需完全离线使用，请将远程图片下载到本地后再引用。

## 命令行参数

```bash
python3 md_to_mindmap.py --help
```

| 参数 | 说明 |
| --- | --- |
| `input` | Markdown 文件路径；省略时进入交互选择。 |
| `-o, --output-dir` | 输出目录；默认与 Markdown 文件同目录且同名。 |
| `--template` | 使用另一份 HTML 模板。 |
| `--config` | 使用另一份 `.conf` 配置文件。 |
| `--cover` | 强制生成封面，覆盖配置中的 `enabled`。 |
| `--no-cover` | 强制不生成封面。 |
| `--show-cover-on-open` | 打开 HTML 时默认显示封面。 |
| `--skip-cover-on-open` | 生成封面，但打开时直接进入导图。 |
| `-h, --help` | 显示帮助。 |

无需终端询问地生成并显示封面：

```bash
python3 md_to_mindmap.py "大纲.md" --cover --show-cover-on-open
```

生成封面但默认跳过：

```bash
python3 md_to_mindmap.py "大纲.md" --cover --skip-cover-on-open
```

在交互式终端中，只指定输入文件但不指定上述封面展示参数时，程序仍可能询问是否默认显示封面。用于脚本或自动化流程时，建议显式传入 `--show-cover-on-open` 或 `--skip-cover-on-open`。

## 配置

默认配置文件是 `config.conf`。图片、Logo、标题等可选文本值可以留空；也可以在行首使用 `;` 注释配置行。布尔值和颜色等字段应保留合法格式。

### 页面背景

```ini
[Background]
color = #f4f7f9
image_url =
image_size = cover
image_repeat = no-repeat
```

| 选项 | 说明 | 常用值 |
| --- | --- | --- |
| `color` | 页面背景颜色。 | `white`、`#f4f7f9`、`rgb(...)` |
| `image_url` | 本地图片路径或网络 URL。 | `assets/bg.jpg`、`https://...` |
| `image_size` | 背景尺寸。 | `cover`、`contain`、`auto` |
| `image_repeat` | 背景重复方式。 | `no-repeat`、`repeat`、`repeat-x`、`repeat-y`、`space`、`round` |

### 页面 Logo

页面 Logo 与封面四角 Logo 是两套独立配置。

```ini
[Logo]
image_url =
position = top-left
scale = 0.35
margin = 20px
opacity = 0.8
```

| 选项 | 说明 |
| --- | --- |
| `image_url` | 本地 Logo 路径或网络 URL。 |
| `position` | `top-left`、`top-right`、`bottom-left` 或 `bottom-right`。 |
| `scale` | 相对原始尺寸的缩放比例，范围会限制在 `0.05` 至 `10`。 |
| `margin` | 与页面边缘的距离，例如 `20px`、`1rem`、`5vw`。 |
| `opacity` | 透明度，范围 `0` 至 `1`。 |

### 演示封面

```ini
[Cover]
enabled = true
show_on_open = true

title =
subtitle =
auto_split_title = true

presenter = 张三
presenter_label =
organization = XX大学
date = 2026年7月

background_image = assets/cover-default.svg
background_overlay = rgba(8, 26, 58, 0.42)
text_color = #ffffff
accent_color = #8ed7ff

logo_top_left =
logo_top_right =
logo_bottom_left =
logo_bottom_right =
logo_size = 96px
logo_margin = 32px
```

| 选项 | 说明 |
| --- | --- |
| `enabled` | 是否在生成结果中包含封面。 |
| `show_on_open` | 没有命令行覆盖时的默认展示值，也是终端询问的默认答案。 |
| `title` | 封面标题；留空时使用 Markdown 的第一个标题。 |
| `subtitle` | 可选副标题；设置后以第二行显示。 |
| `auto_split_title` | 副标题留空时，是否按冒号或破折号自动拆分主副标题。 |
| `presenter` | 作者或汇报人姓名；留空时不显示。 |
| `presenter_label` | 姓名前的可选标签；默认留空，不显示“汇报人”等前缀。 |
| `organization` | 单位；留空时不显示。 |
| `date` | 日期文本；留空时不显示。 |
| `background_image` | 本地背景图或网络 URL。 |
| `background_overlay` | 背景遮罩颜色，用于提高文字可读性。 |
| `text_color` | 封面文字颜色。 |
| `accent_color` | 标题装饰线和封面焦点颜色。 |
| `logo_top_left` 等 | 四个角落的独立 Logo。 |
| `logo_size` | 封面 Logo 的最大宽度和高度。 |
| `logo_margin` | 封面 Logo 与页面边缘的距离。 |

项目自带可离线打包的默认背景 `assets/cover-default.svg`。可以将 `background_image` 替换为 JPG、PNG、WebP、SVG 或网络图片。

封面标题会根据长度自动选择字号：短标题优先保持一行，长标题自动缩小并在必要时换行。包含冒号或破折号的标题默认拆分为字号接近的主标题和副标题；显式设置 `subtitle` 时不会使用自动拆分结果。

只有姓名、单位或日期至少填写一项时，标题下方才显示分隔横线和信息区域。

### 节点和连接线

```ini
[Nodes]
connector_color = #a2b9d6

root_bg_color = #4a90e2
root_text_color = white
root_border_color = #357abd

level1_bg_color = #e8f0fe
level1_text_color = #333333
level1_border_color = #a2b9d6

level2_bg_color = #e2e8f0
level2_text_color = #333333
level2_border_color = #b8c6d9

level3_bg_color = #f8f9fa
level3_text_color = #333333
level3_border_color = #e0e0e0
```

`level3` 配色也用于更深层级的节点。

配置中的 CSS 值不能包含分号、大括号、尖括号或换行；不安全的值会被忽略。

使用另一份配置：

```bash
python3 md_to_mindmap.py "大纲.md" --config "configs/dark.conf"
```

## 自定义模板

默认模板是 `template.html`。

自定义模板必须保留 4 个必需占位符：

| 必需占位符 | 内容 |
| --- | --- |
| `{title}` | HTML 文档标题。 |
| `{content}` | 生成的节点 HTML。 |
| `{custom_styles}` | 配置生成的 CSS。 |
| `{logo_html}` | 页面 Logo；没有配置时为空字符串。 |

`{cover_html}` 是可选占位符。模板缺少该占位符但生成了封面时，程序会尝试把封面插入 `<body>` 后；如果模板也没有可识别的 `<body>`，生成会失败并给出明确错误。

```bash
python3 md_to_mindmap.py "大纲.md" --template "templates/custom.html"
```

## 项目结构

```text
.
├── md_to_mindmap.py      # 转换器、资源打包、配置解析和命令行入口
├── template.html         # 当前交互式导图模板
├── config.conf           # 默认外观与封面配置
├── assets/               # 默认封面和 Markdown 源图片
├── source_icons/         # 输出页面使用的离线字体
├── tests/                # 自动化测试
├── 测试示例.md           # 位于项目根目录的功能测试示例
├── README.md             # 本文档
└── *.md                  # 可转换的其他 Markdown 文件
```

`source_icons/` 中以下三个文件是运行必需项：

```text
iconfont.woff2
iconfont.woff
iconfont.ttf
```

## 开发与测试

运行测试：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

检查 Python 语法：

```bash
python3 -c "from pathlib import Path; compile(Path('md_to_mindmap.py').read_text(encoding='utf-8'), 'md_to_mindmap.py', 'exec'); print('Python syntax OK')"
```

检查模板 JavaScript 语法：

```bash
node -e "const fs=require('fs');const h=fs.readFileSync('template.html','utf8');const s=h.match(/<script>([\s\S]*?)<\/script>/);new Function(s[1]);console.log('JavaScript syntax OK');"
```

测试覆盖的主要场景：

- HTML 文本和标题转义。
- 2 空格与 4 空格嵌套列表。
- 同名图片冲突、带括号的路径和缺失图片。
- 不安全资源协议和配置值规范化。
- 交互文件发现和输入边界。
- 本地图片、Logo、背景及字体打包。
- 封面生成、默认展示、完全禁用和主副标题拆分。
- 关键页面交互代码是否写入生成结果。

## 常见问题

### 提示“未找到可转换的 Markdown 文件”

交互模式只扫描脚本所在项目目录中的非隐藏 `.md` 文件，并排除 `README.md`。可以把文件移到项目根目录，或在命令行中直接传入文件路径。

### 提示“缺少运行时字体”

确认 `source_icons/` 中同时存在 `iconfont.woff2`、`iconfont.woff` 和 `iconfont.ttf`。

### 图片显示为“图片未找到”

Markdown 图片路径应相对于 Markdown 文件，而不是相对于执行命令时的目录。配置中的背景和 Logo 路径则相对于配置文件。

### 修改图片后仍显示旧图

重新生成 HTML 并刷新浏览器。输出目录中不再被引用的旧资源不会自动删除，可以在确认无用后手动清理。

### 普通段落没有出现在导图中

转换器只把标题和列表项作为节点。请将需要展示的内容改为标题或列表项。

### 输出目录已经存在

程序会更新同名 HTML、运行时字体和当前引用的图片，不会删除目录中的其他文件。HTML 使用临时文件写入后再原子替换，避免生成过程中留下半写入文件。

## 已知边界

- 这不是完整的 Markdown 渲染器，主要面向“标题 + 列表 + 图片”的大纲结构。
- 建议使用单一一级标题；多个顶级节点可以生成，但只有第一个顶级节点作为主根节点。
- 远程图片不会转存，离线打开时可能无法显示。
- 超大图片或节点数量非常多的文档可能增加首次布局和全图缩放耗时。
