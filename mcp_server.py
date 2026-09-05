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
     "description": "查现在谁身上有什么药效、还剩几分钟。开新话题前想确认自己还在不在演，就查这个。",
     "inputSchema": {"type": "object", "properties": {}}},
]


def run_tool(name, args):
    args = args or {}
    with LOCK:
        if name == "candy_status":
            return candyjar.context_line() or "现在谁身上都没有药效。"
        if name != "candy_jar":
            return f"没有叫「{name}」的工具。"
        act = args.get("action") or "look"
        if act == "eat":
            return candyjar.eat(index=args.get("index"), who="ai")
        if act == "feed":
            return candyjar.eat(index=args.get("index"), who="ai", target="user",
                                message=args.get("message"))
        if act == "dex":
            return candyjar.dex()
        return candyjar.look(who="ai")


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
                             "吃到有时长的糖之后，按返回文本里的「演法」演，时间到了自然散。")}}
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
