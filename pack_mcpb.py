#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把这个目录打成 Claude 桌面 App 能双击安装的 .mcpb（就是个 zip，标准库搞定）。

    python3 pack_mcpb.py            # 产出 causality-candy-jar-<版本>.mcpb

版本号取 manifest.json 里的 version。打包只收游戏本体，不收 data/ 存档与 .git。
（官方 CLI 是 `npx @anthropic-ai/mcpb pack`，效果一样；这里不想让人为了打包先装 Node。）
"""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
OUT = ROOT / f"{MANIFEST['name']}-{MANIFEST['version']}.mcpb"
FILES = ["manifest.json", "icon.png", "mcp_server.py", "server.py", "candyjar.py",
         "README.md", "LICENSE", "LICENSE-CONTENT.md"]
SKIP_DIRS = {"data", ".git", "__pycache__", "docs", ".github", "site"}   # demo.js/site 是 Pages 试玩版专用，不进安装包


def main():
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            p = ROOT / name
            if p.exists():
                z.write(p, name); n += 1
        for p in sorted((ROOT / "assets").rglob("*")):      # 多尺寸图标
            if p.is_file():
                z.write(p, str(p.relative_to(ROOT))); n += 1
        for p in sorted((ROOT / "web").rglob("*")):
            if p.is_file() and not any(d in p.parts for d in SKIP_DIRS):
                z.write(p, str(p.relative_to(ROOT))); n += 1
    print(f"✓ {OUT.name}（{n} 个文件，{OUT.stat().st_size / 1048576:.1f} MB）")
    print("  Claude 桌面 App 里双击它就能装；装完浏览器打开 http://127.0.0.1:8765")


if __name__ == "__main__":
    main()
