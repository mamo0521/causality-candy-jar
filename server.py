#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""因果律软糖罐 · 单文件小服务（只用 Python 标准库，无需安装任何东西）。

    python3 server.py            # 然后浏览器打开 http://127.0.0.1:8765

它做三件事：
1. 把 web/ 目录当网页根目录端出去（罐子页 + 3D 引擎 + 字体 + 图案）；
2. 记账：吃糖 / 喂糖 / 买糖 / 储藏罐 / 勇气 / 图鉴全落在 data/candyjar_save.json（"吃了就赖不掉"）；
3. 给你的 AI 一条接口：GET /candyjar/context 返回"Ta 正在 X 药效中…"那段话，塞进系统提示即可。
"""
import json
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import candyjar  # noqa: E402

HOST, PORT = "127.0.0.1", 8765
PORT_TRIES = 12          # 端口被占就往后挪：装死会让玩家在别人的罐子上玩（2026-09-05 实锤，见 serve()）
# 同一份存档有两头在写：网页（你）和 MCP（AI）。同进程里用一把锁把「读—改—写」串起来。
# mcp_server 起来时会把自己的锁赋到这里，保证两头用的是同一把。
LOCK = threading.RLock()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "web"), **kw)

    def log_message(self, fmt, *args):   # 只打接口，静态文件不刷屏
        if "/candyjar" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    # ── 小工具 ──
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, s, code=200):
        body = s.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    # ── 路由 ──
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/candyjar":                       # 罐子页开罐时拉一次（没开罐时 jar=None + choose 五罐候选）
            with LOCK:
                return self._json(candyjar.view(who="user"))
        if path == "/candyjar/context":               # 给 AI 的那段话（无药效时为空）
            with LOCK:
                return self._text(candyjar.context_line())
        if path == "/candyjar/status":                # 结构化药效快照
            with LOCK:
                return self._json(candyjar.status())
        if path == "/candyjar/look":                  # AI 看罐子（文本）
            with LOCK:
                return self._text(candyjar.look(who="ai"))
        if path == "/candyjar/dex":
            with LOCK:
                return self._text(candyjar.dex())
        if path == "/state":                          # 罐子页旧的余额显示，这里没有存钱罐
            return self._json({})
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            with LOCK:                                # 读—改—写整段独占：AI 那头可能同时在吃糖
                if path == "/candyjar/eat":           # 玩家在界面上吃/喂
                    b = self._body()
                    target = "ai" if b.get("feed") else "user"
                    text = candyjar.eat(index=b.get("index"), who="user", target=target,
                                        message=(b.get("message") or None),
                                        source=(b.get("source") or "jar"), candy_id=b.get("candy_id"))
                    st = candyjar._load()
                    return self._json({"ok": True, "text": text, "active": candyjar.status(),
                                       "courage": st.get("courage", {}),
                                       "reserve": candyjar._reserve(st, "user"), "dex": st.get("dex", {})})
                if path == "/candyjar/choose":        # 每天第一次打开：从五罐里选一罐
                    r = candyjar.choose(self._body().get("jar"), who="user")
                    return self._json(r, 400 if r.get("error") else 200)
                if path == "/candyjar/buy":
                    b = self._body()
                    r = candyjar.buy(candy_id=b.get("id"), dest=(b.get("dest") or "reserve"), who="user")
                    return self._json(r, 400 if r.get("error") else 200)
                if path == "/candyjar/ai":            # 走 API 的玩家给 AI 装工具时调这个
                    b = self._body()
                    act = b.get("action") or "look"
                    if act == "eat":
                        return self._text(candyjar.eat(index=b.get("index"), who="ai"))
                    if act == "feed":
                        return self._text(candyjar.eat(index=b.get("index"), who="ai", target="user",
                                                       message=b.get("message")))
                    if act == "dex":
                        return self._text(candyjar.dex())
                    return self._text(candyjar.look(who="ai"))
        except Exception as e:                        # 任何异常都回一句话，别让页面转圈
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
        self.send_error(HTTPStatus.NOT_FOUND)

def serve(port=None):
    """占一个能用的端口把网页端出去，返回 (httpd, 真实端口)。

    端口被占时**一定要换一个**：曾经出过事——另一个程序占着 8765，这边静悄悄放弃，
    玩家在浏览器里看到的是别人的罐子，AI 读的却是自己那本空账，两边对不上（2026-09-05）。
    """
    (ROOT / "data").mkdir(exist_ok=True)
    first = PORT if port is None else int(port)
    last = None
    for p in range(first, first + PORT_TRIES):
        try:
            return ThreadingHTTPServer((HOST, p), Handler), p
        except OSError as e:
            last = e
    raise OSError(f"{first}~{first + PORT_TRIES - 1} 全被占了：{last}")


if __name__ == "__main__":
    httpd, port = serve(sys.argv[1] if len(sys.argv) > 1 else None)
    if port != PORT:
        print(f"（{PORT} 被别的程序占着，改用 {port}）")
    print(f"🍬 因果律软糖罐已开张：http://{HOST}:{port}   （Ctrl+C 关店）")
    print(f"   给 AI 的药效状态：http://{HOST}:{port}/candyjar/context")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n打烊。")
