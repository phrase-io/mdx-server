## 词典 JSON API 说明

本文档总结 `/api/entry/{word}` 目前返回的 JSON 结构，并给出字段说明、示例和前端接入建议。

---

### 顶层结构

```json
{
  "word": "mean",
  "pronunciations": [
    {
      "region": "BrE",
      "ipa": "miːn",
      "audio": "/sound/mean__gb_2.mp3"
    },
    {
      "region": "NAmE",
      "ipa": "miːn",
      "audio": "/sound/mean__us_1.mp3"
    }
  ],
  "entries": [ /* 按词性划分的内容 */ ]
}
```

- `word`：解析后的主词头。如果查词命中了 lemma，则是归一化后的词。
- `pronunciations`：数组，包含不同地区的音标/音频。字段：
  - `region`：如 `BrE`、`NAmE`。
  - `ipa`：国际音标。
  - `audio`：音频路径（相对 `/`，直接拼接到站点即可播放）。

---

### entries（多个词性）

每个 `entries[i]` 是一个词性块：

```json
{
  "pos": "verb",
  "forms": [
    {"label": "present simple - he / she / it", "value": "means"},
    {"label": "-ing form", "value": "meaning"}
  ],
  "groups": [
    {
      "guideword": "have as meaning",
      "translation": "有含意",
      "senses": [ ... ],
      "usage_notes": [ ... ],
      "highlight_lists": [ ... ]
    }
  ],
  "idioms": [ ... ]
}
```

- `pos`：词性标签。优先取 `div#verb`/`#noun` 等 id，若缺失会 fallback 至 `<pos>` 的文本。
- `forms`：可选数组，描述动词时态或形容词比较级；`label` 是界面文本，`value` 是对应形式。如果值本身是数组（例如比较级 `["mean·er","mean·est"]`），前端可直接展示成多项。
- `groups`：同一词性内的语义分组（牛津的绿色 guideword）。字段：
  - `guideword` 与 `translation`：绿色标题及其中文。
  - `senses`：具体释义数组（详见下一节）。
  - `usage_notes`：蓝色用法盒（如 *Explaining what you mean*）。结构：
    ```json
    {
      "label": "i.e.",
      "title": "Explaining what you mean",
      "translation": "解释意思",
      "entries": [
        {"text": "Some poems are mnemonics...", "translation": "有些诗歌是记忆代码..."}
      ]
    }
    ```
  - `highlight_lists`：醒目的列表，如 “Verbs usually followed by infinitives”。字段：
    ```json
    {
      "title": "Verbs usually followed by infinitives",
      "translation": null,
      "items": ["afford","agree","appear",...]
    }
    ```

- `idioms`：该词性的短语/习语。字段：
  ```json
  {
    "text": "thank ˈGod / ˈgoodness / ˈheaven ( s )",
    "definition": "used to say you are happy...",
    "translation": "（用于表达庆幸或释然）谢天谢地",
    "examples": [...],   // 可选，结构与 senses.examples 相同
    "helps": [
      {
        "label": "HELP",
        "text": "Some people find the phrase thank God offensive.",
        "translation": "有人认为 thank God 含冒犯意。"
      }
    ]
  }
  ```

---

### sense（释义）结构

`groups[].senses` 中的每一项字段如下：

```json
{
  "id": "mean_sng_1",
  "definition": "to have sth as a meaning",
  "translation": "表示…的意思",
  "notes": [
    {"text": "not used in the progressive tenses", "translation": "不用于进行时"}
  ],
  "patterns": [
    {"pattern": "~ sth"},
    {"pattern": "~ sth to sb"}
  ],
  "labels": [
    {"type": "grammar", "text": "[ sing. ]"},
    {"type": "label", "text": "( informal )"}
  ],
  "topics": [
    ["Religion and politics","Religion","Types of religion"]
  ],
  "examples": [
    {
      "text": "Do you believe in God?",
      "translation": "你信仰上帝吗？",
      "audio": ["/sound/_god__gbs_1.mp3","/sound/_god__uss_1.mp3"]
    }
  ],
  "helps": [
    {"label": "HELP","text": "Some people find this use offensive.","translation": "有人认为此用法含冒犯意。"}
  ],
  "collocations": [
    {
      "title": "Religion",
      "translation": "宗教",
      "subtitle": "Being religious",
      "subtitle_translation": "笃信宗教的",
      "items": [
        {"pattern": "believe in God/Christ/...", "translation": "信仰上帝／耶稣基督..."}
      ]
    }
  ],
  "images": [
    {
      "thumbnail": "/apple_files/thumb_apple.png",
      "image": "/apple_files/fruit_comp.png",
      "caption": "（如果 ill-txt 存在，则带说明）"
    }
  ]
}
```

> 说明：
> - `definition/translation` 必填；其余字段按需存在。
> - `examples.audio` 为数组，顺序一般是英式/美式音频。
> - `helps` 来源于 “HELP” 小贴士；text 已去掉 “HELP” 前缀。
> - `collocations` 仅在词典给出与该义项相关的搭配盒时出现。
> - `images` 来自 `<ill-g>`；如果只有大图则只有 `image`，否则同时提供 `thumbnail` 和 `image`，caption 存在时附在每个图片对象上。

---

### 图片字段使用建议

- `thumbnail` 与 `image` 均为相对路径（`/apple_files/...`）；前端可直接拼接域名展示，或优先加载缩略图，点击后展示大图。
- 若 `thumbnail` 缺失，直接使用 `image`。
- caption 建议作为图片下方说明文字显示。

---

### 前端接入建议

1. **缓存与渐进加载**：一次请求包含大量文本/音频路径，建议在前端做按需渲染（例如折叠某些 group），减少一次性 DOM 渲染压力。
2. **音频播放**：`audio` 字段为数组，可显示多个音标按钮；点击时直接请求 `/sound/...`。可对同一条目做简易缓存，避免重复请求。
3. **富文本渲染**：`definition`/`examples` 已清洗为纯文本，无需额外 HTML 渲染；若要突出 `~ sth` 等 pattern，可用高亮样式。
4. **搭配与列表**：`usage_notes` 与 `highlight_lists` 都是数组结构，界面可分区块展示。`collocations` 与 `highlight_lists` 不必混在一起：前者跟随具体 sense，后者跟随 group。
5. **兼容性**：不同词条可能缺失某些字段（如 `forms`、`idioms`、`images`），前端渲染时应做好判空。
6. **缓存离线数据**：如果需要离线或本地化，建议存储完整 JSON；字段名已稳定，可直接供移动端/桌面端解析。

---

如需更多字段或示例（例如 `god` 的 collocations / HELP 区块、`apple` 的图片），可以直接在 `example/niujin/*.html` 数据上运行 `json_parser.parse_entry` 获取参考输出。欢迎在前端接入过程中反馈新的需求。 ***
