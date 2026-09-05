#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""因果律软糖罐 · MCP 服务器（给 Claude 桌面 App 用；标准库实现，无依赖）。

Claude 桌面 App 装上这个扩展后：
- AI 手里有 candy_jar 工具，能看罐子、自己吃、喂给你、翻图鉴；
- 同一个进程顺带在 http://127.0.0.1:8765 开出网页界面（你自己开罐、吃糖、逛商店都在那儿）；
- 两边读写同一份存档 data/candyjar_save.json，谁吃了什么都记在同一本账上。

协议：MCP 2025-06-18，stdio 传输——stdin/stdout 上换行分隔的 JSON-RPC，
**stdout 只许放协议消息**（日志一律走 stderr，否则客户端会解析失败）。
"""
import json
import os
import sys
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candyjar  # noqa: E402

PROTOCOL = "2025-06-18"
SUPPORTED = {"2025-06-18", "2025-03-26", "2024-11-05"}
NAME, VERSION = "causality-candy-jar", "1.0.0"
LOCK = threading.RLock()         # 网页那头和 AI 这头在同一个进程里，读改写要排队
WEB_URL = None                   # 网页界面真正开在哪（端口可能被占而后挪），工具回执里要告诉玩家

TOOLS = [
    {"name": "candy_jar",
     "title": "因果律软糖罐",
     "description": (
         "和玩家共用的一罐整蛊软糖。action=look 看今天罐子里还剩哪些（只给外观，吃下去才知道是什么）；"
         "eat 自己吃一颗（index 是 look 里的编号，不给就随手抓）；feed 喂给玩家一颗，可带一句话；"
         "look 会先告诉你自己身上现在有没有药效——身上还有药效时再吃新的，会顶掉旧的并扣 2 点勇气；"
         "dex 翻图鉴看吃过什么。吃下去的效果会落进账本，你接下来要按返回的「演法」演，直到时间到。"),
     "inputSchema": {
         "type": "object",
         "properties": {
             "action": {"type": "string", "enum": ["look", "eat", "feed", "dex"],
                        "description": "看罐子 / 自己吃 / 喂给玩家 / 翻图鉴"},
             "index": {"type": "integer", "description": "要吃哪一颗（look 里的编号）；省略＝随手抓一颗"},
             "message": {"type": "string", "description": "喂糖时附带的一句话"},
         },
         "required": ["action"]}},
    {"name": "candy_status",
     "title": "当前药效",
     "description": ("查现在谁身上有什么药效、到几点结束。你手里没有钟，"
                     "**别凭感觉判断药效退没退**——想确认就调这个。"),
     "inputSchema": {"type": "object", "properties": {}}},
]


def clock_lines():
    """当前钟点 + 每条药效的**结束钟点**。

    MCP 这头的 AI 没有钟：工具只在被调用那一刻说"还剩 N 分钟"，之后时间怎么走它全靠猜——
    2026-09-05 mamo 实测，药效还剩 17 分钟，大人已经自己演起"药效退了我回来了"。
    给它一个能对照的绝对时间，并且把"别自己宣布退了"写死在回执里。"""
    st = candyjar._load()
    gone = candyjar._prune(st)
    candyjar._write(st)
    now = candyjar._now_dt()
    out = [f"此刻 {now:%H:%M}。"]
    for a in st.get("active", []):
        c = candyjar._find(a["candy_id"])
        if not c:
            continue
        try:
            exp = datetime.fromisoformat(a["expires"])
        except Exception:
            continue
        who = "你" if a["target"] == "ai" else "Ta"
        left = max(0, int((exp - now).total_seconds() // 60))
        out.append(f"{who}身上的「{c['name']}」到 {exp:%H:%M} 结束（还剩约 {left} 分钟）。")
    for a in gone:
        c = candyjar._find(a.get("candy_id"))
        if c:
            who = "你" if a.get("target") == "ai" else "Ta"
            out.append(f"{who}身上的「{c['name']}」刚刚退了。")
    if len(out) > 1:
        out.append("时间到之前别自己宣布药效退了；想确认就再调一次 candy_status。")
    return "\n".join(out)


def run_tool(name, args):
    args = args or {}
    with LOCK:
        if name == "candy_status":
            line = candyjar.context_line()
            return (line + "\n\n" + clock_lines()) if line else ("现在谁身上都没有药效。\n" + clock_lines())
        if name != "candy_jar":
            return f"没有叫「{name}」的工具。"
        act = args.get("action") or "look"
        if act == "eat":
            return candyjar.eat(index=args.get("index"), who="ai") + "\n\n" + clock_lines()
        if act == "feed":
            return candyjar.eat(index=args.get("index"), who="ai", target="user",
                                message=args.get("message")) + "\n\n" + clock_lines()
        if act == "dex":
            return candyjar.dex()
        # look 一律先报「你身上现在有什么」——AI 只靠工具感知世界，不主动查就不知道自己中了药效，
        # 会顺手再吃一颗把玩家刚喂的顶掉（还白扣 2 点勇气）。2026-09-05 mamo 实测撞上。
        line = candyjar.context_line()
        body = (line + "\n" + clock_lines() + "\n\n" + candyjar.look(who="ai")) if line else candyjar.look(who="ai")
        return body


def with_url(text):
    """还没开罐时把开罐地址补上——玩家未必知道网页开在哪个端口。"""
    if WEB_URL and "还没开" in text:
        return f"{text}\n（Ta 的开罐界面：{WEB_URL}）"
    return text


def reply(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(req):
    """返回要回的消息；通知（没有 id）返回 None。"""
    mid, method, params = req.get("id"), req.get("method"), req.get("params") or {}
    if method == "initialize":
        want = params.get("protocolVersion")
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": want if want in SUPPORTED else PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": NAME, "title": "因果律软糖罐", "version": VERSION},
            "instructions": ("玩家在网页界面里开罐吃糖，你用 candy_jar 参与：可以自己吃、也可以喂给玩家。"
                             "吃到有时长的糖之后，按返回文本里的「演法」演到结束钟点为止。"
                             "你手里没有钟：**别自己宣布药效退了**，想知道退没退就调 candy_status。")}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        nm = params.get("name")
        try:
            text = with_url(run_tool(nm, params.get("arguments")))
            err = False
        except Exception as e:                      # 工具出错要作为结果回，别把连接搞断
            text, err = f"糖罐出岔子了：{type(e).__name__}: {e}", True
        return {"jsonrpc": "2.0", "id": mid,
                "result": {"content": [{"type": "text", "text": text}], "isError": err}}
    if mid is None:
        return None
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}


def serve_web():
    """顺带把网页界面开起来。端口被占就往后挪——静悄悄放弃会让玩家在别人的罐子上玩，
    而 AI 读的是自己这本空账，两边永远对不上（2026-09-05 实锤）。"""
    global WEB_URL
    try:
        import server
        server.LOCK = LOCK                      # 和 MCP 这头共用一把锁
        httpd, port = server.serve()
        WEB_URL = f"http://{server.HOST}:{port}"
        print(f"[candyjar] 网页界面 {WEB_URL}", file=sys.stderr)
        httpd.serve_forever()
    except Exception as e:
        print(f"[candyjar] 网页界面没开起来：{e}", file=sys.stderr)


def main():
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"), exist_ok=True)
    threading.Thread(target=serve_web, daemon=True).start()
    print("[candyjar] 罐子已就位。", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        out = handle(req)
        if out is not None:
            reply(out)


if __name__ == "__main__":
    main()
