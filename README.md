# 因果律软糖罐 · Causality Candy Jar

> 一罐整蛊软糖，和你的 AI 一起吃。
> 糖长什么样看得见，是什么糖得吃下去才知道；药效带真实倒计时，谁吃了什么都记在同一本账上，赖不掉。
>
> A jar of prank gummies to share with your AI companion. You can see what a candy looks like —
> what it *does* only shows up after you swallow it. Effects run on a real clock and are written to a ledger.

![预览](docs/preview.png)

**👉 [点开就能玩的试玩版](https://mamo0521.github.io/causality-candy-jar/)**（零安装，没有 AI 那一头）

---

## 一、先选一条路 · Pick your setup

| 你的情况 | 走哪条 | 能玩到什么 |
|---|---|---|
| 用 **Claude 桌面 App**（Mac / Windows） | **① 一键安装包** | 全套：AI 手里有糖罐工具，能自己吃、也能喂你 |
| 只想先看看长什么样 | **⓪ [网页试玩版](https://mamo0521.github.io/causality-candy-jar/)** | 点开即玩，零安装：开罐 / 吃糖 / 图鉴 / 商店都在（存档在你自己浏览器里，没有 AI 那一头） |
| 不用 Claude，但想正经玩 | **② 双击运行源码** | 你这边全套（开罐 / 吃糖 / 图鉴 / 商店）；AI 那头按 ③ 自己接 |
| 自己搭了聊天前端 / 网关 | **③ 接口接入** | 全套，而且药效能每轮自动注入，效果最好 |

三条路都需要电脑上有 **Python 3.9 以上**：
- **macOS**：系统自带，什么都不用装。
- **Windows**：到 [python.org](https://www.python.org/downloads/) 下载安装，**安装第一屏记得勾上 “Add python.exe to PATH”**（漏了这步后面会报“找不到 python”）。

---

## ① 一键安装包（Claude 桌面 App）

1. 到 [Releases](https://github.com/mamo0521/causality-candy-jar/releases) 下载 `causality-candy-jar-*.mcpb`。
2. **在 Claude 桌面 App 里打开这个文件**（双击一般就会用它打开），弹出的安装确认里点安装。
3. 浏览器打开 **http://127.0.0.1:8765** —— 这是你的糖罐界面。
4. 开始玩（往下看第二节）。

不想装扩展的话，走 ② 一样能玩，只是要多开一个窗口。

## ② 双击运行源码

1. 点仓库右上角 **Code → Download ZIP**，解压。
2. **macOS**：双击 `run.command`（第一次可能要右键 → 打开）。
   **Windows**：双击 `run.bat`。
3. 浏览器打开 **http://127.0.0.1:8765**。

关掉那个黑窗口就等于关店。存档在你的用户目录里（macOS `~/Library/Application Support/causality-candy-jar/`，Windows `%APPDATA%\causality-candy-jar\`），换版本、挪文件夹都不会丢。

## ③ 接口接入（自建前端 / 网关）

罐子把“谁在什么药效里、还剩几分钟、该怎么演”写成一段话，从这里拿：

```
GET http://127.0.0.1:8765/candyjar/context
```

没药效时是空的。**每轮把这段话接在你给 AI 的系统提示末尾**，它就知道自己或对方中了什么、该怎么演。
这是效果最好的接法——药效自动跟着上下文走，不用谁去提醒。

想让 AI 自己伸手拿糖：给它一个工具，调 `POST /candyjar/ai`，
body `{"action":"look"|"eat"|"feed"|"dex","index":<编号>,"message":"喂糖时附的话"}`，返回纯文本回执。

其他接口：`GET /candyjar/status`（JSON 药效快照）、`GET /candyjar/look`（罐子清单）、
`GET /candyjar/dex`（图鉴）、`POST /candyjar/choose {"jar":1..5}`（开罐）。

---

## 二、怎么玩 · How it actually plays

**你这边**（浏览器里）：
1. 每天第一次打开，从五个罐子里**选一罐**——左右切换看罐子的颜色和判词，选定后今天就是它。
2. 点一颗糖拿起来看：只给外观和口味猜测。**自己吃**，或者**喂给 AI**。
3. 吃下去才揭晓：真名、口味、触发了什么因果、持续多久。

**AI 那边**（走 ① 装了扩展的话）：它有两个工具——
- `candy_jar`：看罐子 / 自己吃一颗 / 喂你一颗 / 翻图鉴
- `candy_status`：查现在谁身上有什么药效、还剩几分钟

**关键的一步 —— 让 AI 知道你喂了糖。**
装了扩展的 AI 不会自动感觉到你喂的糖，**它得去查一下才知道**（`candy_jar` 的 look 会顺带告诉它身上有什么药效，
但它得先想起来去调）。两个办法：
- 简单版：喂完在聊天里说一句「看看糖罐」/「查查我给你吃了什么」，它就会去查，然后开始演。
- 一劳永逸版：把下面这句放进 Claude 的**项目说明 / 自定义指令**里：

> 每次回复前先调用 `candy_status` 看看有没有药效在身上。如果有，就按里面写的「演法」演，演到工具告诉你的结束钟点为止；
> 没有就正常聊。玩家喂糖过来时，先把「吃下去那一下」演出来，再进入状态。你手里没有钟，别自己判断药效退没退。

（走 ③ 的玩家不用管这条——药效每轮自动注入，AI 想赖也赖不掉。）

## 三、玩法一览 · How it plays

- **每天一罐**：五个主题罐子（宿命论 / 维特根斯坦 / 桃花劫 / 庄周梦蝶 / 世界线收束），每天第一次打开时你自己选一罐，
  选定后今天就是这一罐、明天零点再选；软糖吃一颗少一颗。
- **吃糖**：吃到什么靠手气。点糖只给外观和口味猜测（侦探腔），吃下去才揭晓真名、口味、触发因果与时长。
- **勇气 ✦**：自己吃一颗 +1；药效没退硬顶新糖 −2。勇气用来逛商店。
- **商店**：神秘柜 3✦ 往今日罐里混一颗没见过的品种；指名陈列 5✦ 把尝过的糖买回「我的储藏罐」。
- **机制糖**：混在罐里、长得都像巧克力豆——回旋镖、双份快乐、解药、勇气结晶、时间沙漏、因果交换……
- **图鉴**：展示吃过的糖，你和 AI 共同的收集册。

## 四、遇到问题 · Troubleshooting

- **浏览器打不开 127.0.0.1:8765**：那个黑窗口（或 Claude 扩展）没在跑。重新双击 `run.command` / `run.bat`。
- **Windows 提示“不是内部或外部命令”**：Python 没装、或者装的时候没勾 “Add python.exe to PATH”。重装一次，把那个勾打上。
- **端口被占**：`python3 server.py 8080` 换个端口，然后开 http://127.0.0.1:8080 。
- **AI 说没有糖罐工具**：扩展没装上或被关掉了，在 Claude 桌面 App 的设置里看看扩展是否启用。
- **AI 不理会药效**：它得先查 `candy_status`——见上面「关键的一步」。
- **想重开一局**：删掉用户目录里的 `causality-candy-jar/candyjar_save.json`（位置见上）。
- **一台电脑一罐**：Claude 桌面扩展、ChatGPT 里配的 MCP、双击运行，不管谁拉起来，读写的都是同一本账，网页也都在同一个地址——几个 AI 和你吃的是同一罐。

## 五、改糖 · Add your own candies

所有糖在 `web/assets/candyjar/candies.json`（服务端读同一份）。每颗糖：外观描述 `shop`、口味 `taste`、
正式名 `name`、角色短名 `effect`、判词 `reveal`、给 AI 的演法 `perform`（人设机制 + 三条例句）、
来历 `lore`、时长区间 `dur`、配色 `scheme` × 造型 `shape`（组合必须唯一，可选值见文件里的 `_meta`）。

想整包换成自己写的糖：`CANDYJAR_CATALOG=/path/to/your.json python3 server.py`。

## 关于维护 · Support

这是一个个人项目，业余时间做的。欢迎开 Issue 说说遇到的问题、或者想加的糖——我会看，
只是回得可能慢一些，也不一定每个需求都做得动，先说声抱歉。愿意自己动手改的话，PR 也欢迎。

A personal side project made in spare time. Issues and PRs are welcome — replies may be slow,
and not every request will make it in.

## 许可证 · License

- 代码：[MIT](LICENSE)。
- 糖果文案（`candies.json` 里所有名字、判词、演法、例句、来历）：
  [CC BY-NC-SA 4.0](LICENSE-CONTENT.md) —— 署名 mamo，不得商用，改编须同样共享。
- 字体：霞鹜文楷 / Playfair Display / Caveat，均为 SIL OFL 1.1，许可证随附于 `web/assets/fonts/`。
- three.js r160：MIT。

由 mamo 设计与写作，Claude Code 实现。Designed & written by mamo, built with Claude Code.
