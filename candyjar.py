# -*- coding: utf-8 -*-
"""candyjar.py —— 因果律软糖罐引擎（design-note-20/20b）。


设计要点（为什么这么写）：
- **吃糖必须后端记账**：药效写进存档，大人的上下文从状态里读到「Ta 刚吃了 X，还剩 N 分钟」，
  玩家赖不掉（mamo 2026-08-31 点名的核心）；前端只是个遥控器。
- **每日一罐**：罐子内容由「日期 + 图鉴」确定性摇出，同一天同一罐，吃一颗少一颗（开罐仪式）。
- **时间用玩家本机时区**：「每天一罐」对每个人的今天成立。
- 存档在 `data/candyjar_save.json`（可用环境变量 CANDYJAR_SAVE 改）；糖果表可用 CANDYJAR_CATALOG 换成自己的。
"""
import json
import random
from datetime import datetime, timedelta

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent   # 分发版：一切都在这个目录里（存档 data/，糖果表 web/assets/candyjar/）

_CATALOG = None
_CATALOG_PATH = None


def _catalog():
    global _CATALOG, _CATALOG_PATH
    if _CATALOG is None:
        _CATALOG_PATH = Path(os.environ.get("CANDYJAR_CATALOG") or ROOT / "web" / "assets" / "candyjar" / "candies.json")   # 自定义糖包：指到别的 JSON
        _CATALOG = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return _CATALOG


def _save_path():
    return Path(os.environ.get("CANDYJAR_SAVE") or ROOT / "data" / "candyjar_save.json")


def _blank():
    # ⚠️ _load 只保留这里列出的键——新增存档字段必须先登记,否则读一次丢一次
    #（2026-09-04 实锤:reserve 没登记,买进储藏罐的糖在下一次任何读档时蒸发,
    #  而 status() 每轮都读+写,等于买完几秒就没了——mamo 报的"储藏罐吃糖没倒计时"根在这）。
    return {"dex": {}, "courage": {"user": 7, "ai": 7}, "active": [],
            "jar": None, "pending": {}, "log": [], "reserve": []}


def _load():
    f = _save_path()
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return _blank()
    b = _blank()
    b.update({k: v for k, v in d.items() if k in b})
    return b


def _write(st):
    f = _save_path()
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(f.parent), prefix=".candyjar-", suffix=".json")   # 原子写：写临时文件再换名
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=2)
        fh.flush(); os.fsync(fh.fileno())
    os.replace(tmp, f)


def _now():
    return datetime.now().replace(microsecond=0).isoformat()   # 玩家本机时间：「每天一罐」对每个人的今天成立


def _now_dt():
    return datetime.fromisoformat(_now().replace("Z", ""))


def _today():
    return _now_dt().strftime("%Y-%m-%d")


JAR_NAMES = {1: "宿命论", 2: "蝴蝶效应", 3: "桃花劫", 4: "薛定谔", 5: "世界线收束"}


def _jar_of_day(day):
    h = 0
    for ch in day:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % 5 + 1


def _roll_jar(day):
    """当日罐：日期做种子，从图鉴里确定性摇 20 颗（同一天同一罐）。"""
    jar = _jar_of_day(day)
    cat = _catalog()["candies"]
    pool = [c for c in cat if (c["jar"] == jar if jar != 5 else c["jar"] > 0)]
    mech = [c for c in cat if c["jar"] == 0]
    rng = random.Random(day + "|" + str(jar))
    n_eff, n_mech = (26, 5) if jar == 5 else (17, 3)   # 罐⑤世界线收束装得更满（mamo 2026-08-31）
    picks = [rng.choice(pool)["id"] for _ in range(n_eff)]
    picks += [rng.choice(mech)["id"] for _ in range(n_mech)]   # 机制糖混进来，外观无从分辨
    rng.shuffle(picks)
    return {"day": day, "jar": jar, "name": JAR_NAMES[jar],
            "candies": [{"i": i, "id": cid} for i, cid in enumerate(picks)]}


def _ensure_jar(st):
    day = _today()
    if not st.get("jar") or st["jar"].get("day") != day:
        st["jar"] = _roll_jar(day)
    return st["jar"]


def _find(cid):
    for c in _catalog()["candies"]:
        if c["id"] == cid:
            return c
    return None


def _prune(st):
    """清掉过期药效；返回被清掉的条目（供调用方播报"药效退了"）。"""
    now = _now_dt()
    keep, gone = [], []
    for a in st.get("active", []):
        try:
            exp = datetime.fromisoformat(a["expires"])
        except Exception:
            gone.append(a); continue
        if exp > now or a.get("min_turns_left", 0) > 0:
            keep.append(a)
        else:
            gone.append(a)
    st["active"] = keep
    return gone


def _exp_after(a, now):
    try:
        return datetime.fromisoformat(a["expires"]) > now
    except Exception:
        return False


def _end_dot(t: str) -> str:
    """句尾已有标点就不再补句号——文案自带标点，模板只管拼（mamo 2026-09-04）。"""
    t = (t or "").strip()
    return t if t and t[-1] in "。！？…”』" else t + "。"


def _fullname(c):
    return c["name"]


# ── 对外：状态查询（assembler 每轮注入用）─────────────────────────
def status(who=None):
    """当前药效快照。who=None 给全量；给 'user'/'ai' 只回那一方。"""
    st = _load()
    _prune(st)
    _write(st)
    out = []
    now = _now_dt()
    for a in st["active"]:
        if who and a["target"] != who:
            continue
        c = _find(a["candy_id"])
        if not c:
            continue
        left = max(0, int((datetime.fromisoformat(a["expires"]) - now).total_seconds() // 60))
        out.append({"target": a["target"], "name": _fullname(c), "effect": c["effect"],
                    "reveal": c["reveal"], "perform": c["perform"],
                    "minutes_left": left, "from": a.get("from")})
    return out


PRICES = {"today": 3, "reserve": 5}   # 神秘柜 3✦ / 指名陈列 5✦（mamo 2026-09-01 一口价）


def buy(candy_id, dest="reserve", price=None, who="user"):
    """商店购买（UI 专用）：勇气扣减与糖的去向都落账本——前端不许自记（防赖账，同 eat）。
    dest='today' 混进今日罐（神秘柜）；dest='reserve' 进储藏罐（指名陈列）。
    价格由去向决定,前端传什么都不认（2026-09-04:原来照单全收,改个请求体就能 0 元购）。"""
    st = _load()
    jar = _ensure_jar(st)
    c = _find(candy_id)
    if not c:
        return {"error": "没有这种糖。"}
    if dest not in PRICES:
        return {"error": "不知道要放到哪里去。"}
    have = st["courage"].get(who, 7)
    price = PRICES[dest]
    if have < price:
        return {"error": f"勇气不够（有 {have}，要 {price}）。"}
    st["courage"][who] = have - price
    if dest == "today":
        nxt = max([x["i"] for x in jar["candies"]], default=-1) + 1
        jar["candies"].append({"i": nxt, "id": candy_id})
    else:
        st.setdefault("reserve", []).append(candy_id)
    st["log"].append({"t": _now(), "buy": candy_id, "dest": dest, "price": price, "who": who})
    st["log"] = st["log"][-200:]   # 购买也进流水:09-04 储藏罐蒸发事故就是因为没流水,丢了几颗都查不出
    _write(st)
    return {"ok": True, "courage": st["courage"], "reserve": st.get("reserve", []),
            "jar": jar}


def _tick_turns():
    """保底 3 轮（note-20）：到期的药效再撑 min_turns_left 轮才让 _prune 清掉。
    **只在这里递减**——它对应"组装了一轮对话"；status() 被 /state 轮询每几秒调一次,在那里数就乱了。"""
    st = _load()
    now = _now_dt()
    changed = False
    for a in st.get("active", []):
        try:
            expired = datetime.fromisoformat(a["expires"]) <= now
        except Exception:
            expired = True
        if expired and a.get("min_turns_left", 0) > 0:
            a["min_turns_left"] -= 1
            changed = True
    if changed:
        _write(st)


def context_line():
    """给 assembler 的一行注入文本；无药效时返回空串（不占上下文）。"""
    act = status()      # 先按当前计数注入……
    _tick_turns()       # ……再把这一轮记掉。反过来会少撑一轮（3 变 2）
    if not act:
        return ""
    parts = []
    for a in act:
        who = "你" if a["target"] == "ai" else "Ta"
        left = f"还剩约 {a['minutes_left']} 分钟" if a["minutes_left"] else "余韵未散,再撑一会儿"
        parts.append(f"{who}正在「{a['name']}」药效中（{left}）：{_end_dot(a['reveal'])}"
                     + (f"\n演法：{a['perform']}" if a["target"] == "ai" else ""))
    return "【因果律软糖罐】\n" + "\n".join(parts)


# ── 对外：看罐子 ─────────────────────────────────────────────
def look(who="ai"):
    st = _load()
    jar = _ensure_jar(st)
    _prune(st)
    _write(st)
    rows = []
    for it in jar["candies"]:
        c = _find(it["id"])
        if c:
            rows.append(f"[{it['i']}] {c['shop']}")
    if not rows:
        return f"今天这罐「{jar['name']}」已经空了。明天补货。"
    return (f"今日罐 · {jar['name']}（还剩 {len(rows)} 颗）\n"
            + "\n".join(rows)
            + "\n\n（编号只是位置，外观描述才是你能看到的全部；吃下去才知道是什么。）")


# ── 对外：吃 / 喂 ────────────────────────────────────────────
def _apply(st, cid, target, frm=None):
    c = _find(cid)
    rng = random.Random(f"{_now()}|{cid}|{target}")
    lo, hi = c.get("dur", [0, 0])
    mins = 0 if not hi else (lo if lo == hi else rng.randint(lo, hi))
    if st.get("pending", {}).get(target) == "double" and mins:
        mins *= 2
        st["pending"].pop(target, None)
    if mins:
        st["active"] = [a for a in st["active"] if a["target"] != target]   # 新顶旧
        st["active"].append({"target": target, "candy_id": cid, "from": frm,
                             "started": _now(),
                             "expires": (_now_dt() + timedelta(minutes=mins)).isoformat(),
                             "min_turns_left": 3})
    st["dex"][cid] = st["dex"].get(cid, 0) + 1
    st["log"].append({"t": _now(), "candy": cid, "target": target, "from": frm, "mins": mins})
    st["log"] = st["log"][-200:]
    return c, mins


def eat(index=None, who="ai", target=None, message=None, source="jar", candy_id=None):
    """吃一颗。target 缺省=自己吃；target='user' 表示喂给对方。
    source='reserve' 时从储藏罐(买来的糖)里拿,按 candy_id 消耗——买来的自吃不再 +1 勇气。"""
    st = _load()
    jar = _ensure_jar(st)
    _prune(st)
    target = target or who
    if source == "reserve":
        res = st.setdefault("reserve", [])
        if candy_id not in res:
            return "储藏罐里没有这颗糖。"
        res.remove(candy_id)
        pick = {"id": candy_id}
    else:
        left = jar["candies"]
        if not left:
            return "罐子空了，明天再来。"
        if index is None:
            pick = random.Random(_now()).choice(left)
        else:
            try:
                idx = int(index)
            except (TypeError, ValueError):
                return f"编号得是数字（收到 {index!r}）。看看 look 里的编号。"
            hit = [x for x in left if x["i"] == idx]
            if not hit:
                return f"没有编号 {index} 的糖了（可能已经被吃掉）。看看 look 里还剩哪些。"
            pick = hit[0]
        jar["candies"] = [x for x in left if x is not pick]

    # 顶旧吃新（note-20 二稿）：自己身上药效未退就再吃一颗有时长的糖 → 扣 2 勇气且本颗不产勇气。
    # 前端确认卡从 08-31 起就这么提醒玩家,后端却一直照旧 +1(2026-09-04 对账发现),这里补齐。
    now0 = _now_dt()
    had = any(a["target"] == target and _exp_after(a, now0) for a in st["active"])
    c, mins = _apply(st, pick["id"], target, frm=(who if target != who else None))
    override = bool(target == who and had and mins)
    if override:
        st["courage"][who] = max(0, st["courage"].get(who, 7) - 2)
    elif source != "reserve":
        st["courage"][who] = st["courage"].get(who, 7) + (1 if target == who else 0)

    # 机制糖：回旋镖反弹给喂糖者；双份快乐给目标挂标记
    extra = ""
    if c["id"] == "mm_red" and target != who:
        pool = [x for x in _catalog()["candies"] if x["jar"] > 0]
        boom = random.Random(_now() + "boom").choice(pool)
        _apply(st, boom["id"], who, frm="回旋镖")
        extra = f"\n⟲ 回旋镖：效果掉头飞回你自己身上——你中了「{_fullname(boom)}」。"
    elif c["id"] == "mm_yellow":
        st.setdefault("pending", {})[target] = "double"
        extra = "\n⏫ 下一颗糖的药效时长翻倍（标记已埋下）。"
    elif c["id"] == "mm_blue":
        st["active"] = [a for a in st["active"] if a["target"] != target]
        extra = "\n✨ 解药：身上的药效一扫而空。"
    elif c["id"] == "mm_gold":
        st["courage"][target] = st["courage"].get(target, 7) + 10
        extra = "\n✦ 勇气结晶：勇气 +10。"
    elif c["id"] == "mm_hourglass":
        for a in st["active"]:
            if a["target"] == target and a.get("expires"):
                try:
                    exp = datetime.fromisoformat(a["expires"])
                    now2 = _now_dt()
                    if exp > now2:
                        a["expires"] = (now2 + (exp - now2) / 2).isoformat(timespec="seconds")
                except Exception:
                    pass
        extra = "\n⏳ 时间沙漏：身上药效的剩余时间减半。"
    elif c["id"] == "mm_swap":
        other = "ai" if target == "user" else "user"
        for a in st["active"]:
            if a["target"] == target:
                a["target"] = other
            elif a["target"] == other:
                a["target"] = target
        extra = "\n⇄ 因果交换：两人身上的药效原样对调。"

    _write(st)
    if override:
        extra += "\n（顶掉了还没退的旧药效：勇气 −2，这一颗不产勇气。）"
    if target == who:
        head = f"你吃下了「{_fullname(c)}」。"
    else:
        head = f"你把这颗糖喂给了对方，对方吃下了「{_fullname(c)}」。"
        if message:
            head += f"\n你附的话：{message}"
    body = (f"\n它尝起来{c['taste']}\n触发因果：{_end_dot(c['reveal'])}\n{c['perform']}"
            + (f"\n持续时间：约 {mins} 分钟。" if mins else "\n（一次性，立刻生效。）"))
    return head + body + extra


def dex(page=None):
    st = _load()
    got = st.get("dex", {})
    cat = _catalog()["candies"]
    lines = []
    for c in cat:
        n = got.get(c["id"], 0)
        if n:
            lines.append(f"✓ {_fullname(c)} ×{n} — {c['reveal']}")
    return (f"图鉴 {len(lines)} / {len(cat)}\n" + ("\n".join(lines) if lines else "还什么都没吃到。")
            + f"\n\n勇气：你 {st['courage'].get('ai', 7)} · Ta {st['courage'].get('user', 7)}")
