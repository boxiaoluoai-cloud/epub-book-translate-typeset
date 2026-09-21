# EPUB 整书翻译排版

版本 **1.0.0** ｜ 适用于 WorkBuddy 及其他支持 `SKILL.md` 的 Agent

把一本**外文 EPUB 整本**翻成简体中文，并排成可以直接打印的 HTML + PDF。

---

## 它产出什么

一份**单文件 HTML**（浏览器打开可自行打印）和一份**印刷级 PDF**，后者含：

- 封面页、版权与说明页
- **目录，页码是渲染后真实回填的**，不是估算
- 正文书眉与页码（对开排版，左右页书眉不同）
- 章节与部分扉页
- 插图，以及图下的中文图注
- 引文块、要点框／练习框（对应原书的 `<aside>` 一类结构）
- 章前**导读**（可选，面向学生与普通读者）

实测样例：一本 12 章非虚构，成品 **149 页**、正文 **1004 段逐段核验全部命中**，
PDF 文字可搜索可复制（已校验不含康熙部首映射）。

## 安装

### 方式一 · 在 WorkBuddy 里导入（推荐）

1. 打开 WorkBuddy，左侧进入「技能」
2. 点「添加技能」→ 选「上传技能」
3. 把这个 zip 拖进去，或点「选择文件」选中它
4. 在「已安装」里确认它已被启用

导入后系统自动完成配置，无需额外操作。

### 方式二 · 手动放置

解压后应得到 `epub-book-translate-typeset/`，且 `SKILL.md` 就在这一层：

```
~/.workbuddy/skills/epub-book-translate-typeset/SKILL.md
```

Windows 上是 `C:\Users\<你的用户名>\.workbuddy\skills\...`。
放好后新建一个任务即可生效。

## 运行前提

| 项 | 要求 |
|---|---|
| Python | 3.9 以上 |
| 依赖库 | `pip install pymupdf pypdf reportlab fonttools playwright` |
| 浏览器 | 本机已装 Chrome 或 Edge |

**不需要** 执行 `playwright install chromium` —— 脚本直接驱动本机已有的浏览器。
完全不装 `playwright` 也能跑：`html_to_pdf.py` 会退回调用
`chrome --headless --print-to-pdf`，只是可控性差一些。

## 怎么用

在对话里直接说，例如：

> 把这个 epub 翻译成中文，排成可以打印的 PDF

把 epub 一并上传即可。也可以手动逐阶段跑脚本，见下文。

## 一次完整流程

八个阶段。脚本都在 `scripts/`，其中**只有第一个吃 `--epub`，其余都吃 `book.json`**。
不确定某个脚本怎么用，加 `--help` 即可：`python scripts/check_zh.py --help`。

```bash
# 1 抽取：先探查这本书的结构
python scripts/epub_extract.py --epub book.epub --list        # 有哪些文档
python scripts/epub_extract.py --epub book.epub --classes     # 结构由哪些 class 承载
python scripts/epub_extract.py --epub book.epub --probe 007_c002_Chapter_1 4000
# 填好 book.json 之后再抽取，写出 src/*.md
python scripts/epub_extract.py book.json

# 2 翻译    src/*.md → zh/*.md，每单元一个 agent，共用同一份 brief

# 3 检查（这一步不能省，漏译只在这里能抓到）
python scripts/check_zh.py book.json      # 漏译、残留英文
python scripts/lint_markers.py book.json  # 标记是否一一对应
python scripts/ratio_check.py book.json   # 逐行长度比，抓整句漏掉

# 4 清扫
python scripts/sweep_text.py book.json    # 引号、标点、错字、导读字数

# 5 建 HTML
python scripts/build_html.py book.json

# 6 渲染 + 目录页码回填（反复跑到 toc_pages 报 STABLE）
python scripts/html_to_pdf.py book.json
python scripts/toc_pages.py book.json
python scripts/build_html.py book.json
python scripts/html_to_pdf.py book.json
python scripts/toc_pages.py book.json
python scripts/stamp.py book.json         # 书眉、页码、字体子集

# 7 核验：逐段确认都进了 PDF
python scripts/verify_pdf.py book.json

# 8 交付 output/ 下的 HTML 与 PDF
```

## 每本书要改的，只有一个文件

`book.json`（模板见 `assets/book.json`，字段带注释）。里面放书名与作者、版权页文字、
单元清单、`file → href` 映射、分部分、导读字数区间等。

**永远不用改的**：脚本、标记体系、样式表、检查逻辑。

## 适配不熟悉的出版社

不同出版社用不同的 class 名承载章节结构（calibre 生成的书甚至没有有意义的 class）。
抽取器按三级信号还原结构：

1. `epub:type` 语义（`chapter` / `part` / `subtitle` / `bridgehead`）
2. class 名表（内置 Penguin Random House / Avery 的常见类名）
3. 结构回退（标签层级 + 在文档中的位置）

做法：先跑一次 `--classes`，把看到的类名抄进 `epub_extract.py` 顶部的表即可。
**这是唯一需要针对新书动手的地方**，其余全部通用。详见
`references/pipeline.md` 的 *Adapting to an unfamiliar publisher*。

## 已知边界

- 需要原书存在可识别的章节结构。纯扫描转文本、无层级结构的书抽不出骨架。
- 复杂多栏版式、含大量表格的书，版式会被简化。
- 不适用于单篇文章、字幕、非成书文本。

## 安全说明

包内全部为 Python 脚本与 Markdown，安装前可逐行审阅：

- **无网络访问** —— 不引用 `http` / `urllib` / `socket`，不外发任何内容
- **不读取凭据** —— 不读 token、密码、密钥，不碰浏览器数据
- **不删除文件** —— 无 `os.remove` / `rmtree` / `unlink`
- **唯一的子进程调用** —— 启动本机已安装的 Chrome / Edge 打印 PDF
- 只读写你在 `book.json` 中指定的项目目录

## 目录结构

```
epub-book-translate-typeset/
├── SKILL.md                      # 给 Agent 读：触发条件与工作流
├── README.md                     # 给  人  读：本文件
├── LICENSE
├── assets/
│   ├── book.json                 # 配置模板，每本书填一份
│   └── print.css                 # 印刷样式表
├── references/
│   ├── pipeline.md               # 八阶段 SOP + 最花时间的那些坑
│   ├── markers.md                # 全部标记及其渲染结果
│   ├── translation-guide.md      # 逐书翻译 brief 模板
│   └── guide-spec.md             # 章前导读规范
└── scripts/                      # 11 个文件：10 个命令 + 1 个共享模块
```

## 许可

MIT，见 `LICENSE`。
