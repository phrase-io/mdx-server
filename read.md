# MDX Server 项目解析与使用说明（中文）

## 1. 项目概述
MDX Server 是一个轻量级的本地 HTTP 服务，用来读取 MDX/MDD 词典文件并返回网页格式的查询结果。它将 `mdict-query` 的索引/解析能力与 PythonDictionaryOnline 的 Web 服务逻辑结合，使 Kindlemate、Anki 划词助手等软件可以共享同一份词典数据，无需再依赖 Mdict、GoldenDict 等客户端。

主要包含：
- `mdx_server.py`：程序入口与 WSGI 服务器。
- `mdict_query.py`、`readmdict.py`：读取词典、构建 SQLite 索引并完成查找。
- `mdx_util.py`：将查到的内容拼装为 HTML，同时注入静态资源。
- `mdx/` 目录：放置 CSS/JS/音频脚本等可注入的静态文件。
- `manual/mdx-server manual.pdf`：原作者制作的图文教程。

## 2. 目录与模块职责
| 文件/目录 | 作用 |
| --- | --- |
| `mdx_server.py` | 选择词典文件、创建 `IndexBuilder`、启动 `wsgiref` 服务器、路由到不同的响应逻辑。|
| `mdx_util.py` | 处理 MDX/MDD 查询结果、剔除 `entry:/` 前缀、追加 `mdx/` 下的注入 HTML、转发多媒体请求。|
| `file_util.py` | 文件/目录相关工具，供服务器查找静态资源使用。|
| `mdict_query.py` | 管理 `IndexBuilder` 类：首轮运行时构建 `*.mdx.db/*.mdd.db`，之后直接复用索引完成查找。|
| `readmdict.py`、`pureSalsa20.py`、`ripemd128.py`、`lzo.py` | 词典底层格式解析、加解密、解压缩算法实现。|
| `lemma.py` | 借助 `pattern.en` 将单词转换为词形原型，弥补词典缺词。|
| `mdx/` | 提供注入 HTML、CSS、JS 以及静态文件（如 `jquery/`、`O8C.css`）。|

## 3. 核心工作流程
1. **加载词典**：运行 `python mdx_server.py <词典>.mdx`，或直接执行程序并通过 Tk 文件选择框挑选 MDX 文件。`IndexBuilder` 会检查是否存在对应的 `*.mdx.db` 和可选的 `*.mdd.db` 索引，不存在则自动创建。
2. **启动服务**：程序在后台创建一个线程，调用 `wsgiref.simple_server.make_server('', 8000, application)`，监听 `http://127.0.0.1:8000/`。
3. **处理请求**：
   - `/{word}`：调用 `get_definition_mdx()`，返回词条 HTML，并自动拼接 `mdx/injection.html` 中定义的静态内容。
   - `/injection.*`、`/jquery/*`、`/O8C.css` 等：直接从 `mdx/` 目录读取并返回。
   - `/xxx.mp3`/`/xxx.png` 等资源：若后缀在 `content_type_map` 里，则通过 `IndexBuilder.mdd_lookup()` 从 `.mdd` 文件取出并返回原始数据。
4. **音频播放**：`mdx/injection.js` 监听 `sound://` 链接，自动创建 `<audio>` 标签播放 `.mdd` 中的音频资源。

## 4. 运行环境要求
- Python 3.5 以上（推荐 3.8+，与原始代码兼容）。
- Tkinter（用于 GUI 选词典，可以通过命令行参数绕过）。
- `pattern` 包（`lemma.py` 调用），如只在命令行指定词典并且不需要词形还原可忽略。
- 可选 `python-lzo`，用于解析旧版使用 LZO 压缩的词典，否则会提示缺失但一般不影响新版词典。

## 5. 安装与启动
1. **准备 Python 环境**：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install pattern lzo   # lzo 可按需安装
   ```
   Linux 需要另外安装 `python3-tk`，macOS 需要 `python-tk`。
2. **放置词典文件**：将 `.mdx` 与对应 `.mdd` 放在同一目录，程序会在相同位置生成 `*.db` 索引文件。
3. **启动方式**：
   ```bash
   # 直接指定词典
   python mdx_server.py /path/to/dictionary.mdx

   # 让程序弹出文件选择框
   python mdx_server.py
   ```
   控制台出现 `Serving HTTP on port 8000...` 即代表成功。
4. **查询**：在浏览器或其他 HTTP 客户端访问 `http://localhost:8000/<单词>`，即可获得 HTML 结果，例如 `http://localhost:8000/test`。

## 6. HTTP 接口说明
| 路径示例 | 方法 | 返回内容 |
| --- | --- | --- |
| `/`、`/word` | GET | 指定单词的 HTML 解释，附加 `mdx/` 里的注入内容。|
| `/injection.css`、`/injection.js`、`/jquery/jquery.min.js` | GET | `mdx/` 目录中的静态文件，可根据需要扩展。|
| `/audio/example.mp3` 等 | GET | 从 `.mdd` 中提取的音频/图片等多媒体资源，依据 `content_type_map` 设置返回类型。|

## 7. 自定义与扩展
- **注入内容**：编辑 `mdx/injection.html`、`injection.js`、`injection.css`，或在 `mdx/` 中增加新的文件，即可影响所有返回页面。
- **端口修改**：在 `mdx_server.py` 中将 `make_server('', 8000, ...)` 改为所需端口即可。
- **批量查询**：外部脚本可直接复用 `mdict_query.IndexBuilder` 类，绕过 HTTP 服务实现批量处理。
- **安全部署**：程序未做登录或 TLS，请仅在本机或内网使用；如需对外提供服务，需自行加上反向代理与鉴权策略。

## 8. 常见问题
- **缺少 pattern/Tk**：安装 `pip install pattern`，以及系统对应的 Tk 组件。
- **LZO 支持缺失**：对于旧词典需要 LZO 解压时，安装 `pip install python-lzo`。如果词典使用 zlib，则无需理会提示。
- **GUI 不可用**：在无图形环境下直接传入 `python mdx_server.py your_dict.mdx` 即可，绕过 Tk 窗口。
- **索引文件损坏**：删除对应的 `*.mdx.db/*.mdd.db` 重新运行，程序会自动重建。
- **欧陆/Eudic 拆分的 `.mdd.1/.mdd.2/...`**：将这些分卷与 `.mdx` 放在同目录即可，程序会自动串联读取，无需手动合并。

## 9. 参考资料
- 根目录 `README.md` 与 `manual/mdx-server manual.pdf`：包含原作者的操作截图。
- 上游项目：`mmjang/mdict-query`、`amazon200code/PythonDictionaryOnline`。

有了以上中文说明，即可在本地快速部署、定制并排查 MDX Server。
