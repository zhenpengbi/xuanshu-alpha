#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 持仓 OCR 更新工具
==============================
截图支付宝/天天基金持仓界面 → 自动识别持仓数据 → 更新 portfolio.json

用法：
    python3 scripts/portfolio_ocr.py 截图路径.png
    python3 scripts/portfolio_ocr.py 截图路径.png --yes          # 跳过确认直接写入
    python3 scripts/portfolio_ocr.py 截图路径.png --no-html      # 不更新 index.html
    python3 scripts/portfolio_ocr.py 截图路径.png --dry-run      # 只打印识别结果，不写入

OCR 后端（按优先级自动选择）：
    1. ocrmac    — 调用 macOS Apple Vision 框架（最准，仅 macOS）
                   安装：pip install ocrmac Pillow
    2. easyocr   — 纯 Python 多语言 OCR，支持离线
                   安装：pip install easyocr
    3. paddleocr — 百度飞桨 OCR，中文最强（但依赖较重）
                   安装：pip install paddlepaddle paddleocr

识别字段（支付宝/天天基金持仓截图）：
    - 基金名称（用于匹配 portfolio.json 中的持仓条目）
    - 持仓市值 / 当前金额
    - 今日收益 / 今日盈亏
    - 持仓收益 / 累计收益
    - 持仓收益率

匹配逻辑：
    1. 基金代码精确匹配（若截图包含代码）
    2. 名称子串匹配
    3. difflib SequenceMatcher 模糊匹配（相似度 ≥ 0.5）
    识别不确定的字段标注 "待确认(原值)"，由用户决定是否手动修正。

注意事项：
    - 截图需清晰，建议截全屏或完整基金卡片区域
    - 不会修改 data/news.json、signal_push.py 等非持仓文件
    - 建议搭配 scripts/update_portfolio.py 做最终确认
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ── 路径定位 ──────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
ROOT         = SCRIPT_DIR.parent
PORTFOLIO    = ROOT / "data" / "portfolio.json"
INDEX_HTML   = ROOT / "index.html"


# ══════════════════════════════════════════════════════════════
# OCR 后端：按优先级尝试，失败则降级
# ══════════════════════════════════════════════════════════════

def ocr_with_ocrmac(image_path: str) -> list[str]:
    """使用 macOS Apple Vision 框架（ocrmac），返回文本行列表。"""
    from ocrmac.ocrmac import OCR
    results = OCR(image_path,
                  recognition_level='accurate',
                  language_preference=['zh-Hans', 'en-US'],
                  confidence_threshold=0.1).recognize()
    return [text for text, conf, bbox in results if text.strip()]


def ocr_with_easyocr(image_path: str) -> list[str]:
    """使用 EasyOCR（需 pip install easyocr）。"""
    import easyocr
    reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
    results = reader.readtext(image_path)
    return [text for _, text, conf in results if conf > 0.1 and text.strip()]


def ocr_with_paddleocr(image_path: str) -> list[str]:
    """使用 PaddleOCR（需 pip install paddlepaddle paddleocr）。"""
    from paddleocr import PaddleOCR
    paddle = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
    results = paddle.ocr(image_path, cls=True)
    lines = []
    for line in (results[0] or []):
        text = line[1][0]
        if text.strip():
            lines.append(text)
    return lines


def run_ocr(image_path: str) -> list[str]:
    """
    按优先级依次尝试 OCR 后端。
    返回识别出的文本行列表（去重、去空白）。
    """
    backends = [
        ("ocrmac (Apple Vision)",  ocr_with_ocrmac),
        ("easyocr",                ocr_with_easyocr),
        ("paddleocr",              ocr_with_paddleocr),
    ]
    for name, fn in backends:
        try:
            lines = fn(image_path)
            if lines:
                print(f"  [OCR] 使用后端: {name}  识别到 {len(lines)} 行文本")
                return lines
        except ImportError:
            pass
        except Exception as e:
            print(f"  [OCR] {name} 失败: {e}", file=sys.stderr)

    sys.exit(
        "❌ 未找到可用的 OCR 后端。请安装其中一个：\n"
        "   pip install ocrmac Pillow          # macOS 推荐\n"
        "   pip install easyocr                # 跨平台\n"
        "   pip install paddlepaddle paddleocr  # 中文最强"
    )


# ══════════════════════════════════════════════════════════════
# 文本解析：从 OCR 文本行提取持仓数据
# ══════════════════════════════════════════════════════════════

# 支付宝/天天基金 持仓截图常见字段标签
LABEL_MARKET_VALUE  = re.compile(r'持仓市值|当前市值|市值|资产')
LABEL_DAILY_RETURN  = re.compile(r'今日收益|今日盈亏|今日|日收益')
LABEL_TOTAL_RETURN  = re.compile(r'持仓收益|累计收益|持有收益|总收益|盈亏')
LABEL_RETURN_RATE   = re.compile(r'收益率|盈亏率|持仓收益率')

# 数字提取：可选 ¥/￥，可选 +/-, 金额（含逗号），可选百分比
NUM_RE   = re.compile(r'[+\-－＋]?\s*[\d,，，.]+(?:\.\d+)?')
MONEY_RE = re.compile(r'[¥￥]?\s*([+\-－＋]?\s*[\d,，.]+(?:\.\d+)?)')
PCT_RE   = re.compile(r'([+\-－＋]?\s*[\d.]+)\s*%')

# 非基金名称的精确黑名单（常见截图 UI 标签）
_NON_FUND_EXACT = {
    '我的基金', '基金', '持仓市值', '当前市值', '市值',
    '今日收益', '今日盈亏', '持仓收益', '持有收益', '累计收益', '总收益',
    '收益率', '持仓收益率', '盈亏率', '资产',
    '全部', '排行', '自选', '热门', '搜索',
}
_NON_FUND_PREFIX = ('总资产', '我的', '全部资产', '昨日', '今日')

def parse_money(s: str) -> Optional[float]:
    """从字符串中提取第一个金额数值（处理逗号/全角符号）。"""
    s = s.replace('，', ',').replace('＋', '+').replace('－', '-').replace('，', ',')
    m = MONEY_RE.search(s)
    if not m:
        return None
    raw = m.group(1).replace(',', '').replace(' ', '')
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def parse_pct(s: str) -> Optional[float]:
    """提取百分比数值（如 -6.03% → -6.03）。"""
    s = s.replace('＋', '+').replace('－', '-')
    m = PCT_RE.search(s)
    if not m:
        return None
    raw = m.group(1).replace(' ', '')
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def is_fund_name(text: str) -> bool:
    """
    判断一行文本是否像基金名称。
    规则：4+ 个中文字、长度 5-35，含基金公司名或类型关键词，且不在黑名单中。
    """
    stripped = text.strip()
    # 黑名单：精确匹配和前缀
    if stripped in _NON_FUND_EXACT:
        return False
    if stripped.startswith(_NON_FUND_PREFIX):
        return False
    zh_chars = len(re.findall(r'[一-龥]', stripped))
    total    = len(stripped)
    # 基金名至少含 4 个汉字，总长 6-35
    if zh_chars < 4 or total < 6 or total > 35:
        return False
    # 可靠标识：基金公司名或确定性类型词（不含"收益""价值"等通用词）
    FUND_KEYWORDS = [
        'ETF', 'etf', 'LOF', 'FOF',
        '联接', '指数', '混合', '增强', '债券', '主题',
        '易方达', '天弘', '华夏', '南方', '广发', '博时', '富国',
        '汇添富', '嘉实', '工银', '建信', '兴全', '永赢', '平安',
        '中欧', '诺安', '鹏华', '华安', '招商', '国泰', '银华',
        '大成', '万家', '长城', '上投', '汇宽', '前海', '光大',
    ]
    return any(kw in stripped for kw in FUND_KEYWORDS)


def _scan_card_window(window: list[str]) -> dict:
    """
    在给定的文本行窗口中查找持仓市值/今日收益/持仓收益/收益率。

    设计：用 consumed 集合追踪已被「标签→下一行」模式消费的行索引，
    避免同一行被重复分配给多个字段。
    """
    result = {
        "amount":            None,
        "dailyReturn":       None,
        "holdingReturn":     None,
        "holdingReturnRate": None,
    }
    consumed: set[int] = set()

    def _try_label(j: int, wl: str, label_re, parse_fn, key: str) -> bool:
        """
        标签行处理：若 label_re 匹配当前行，尝试从当前行或下一行取值。
        成功后标记当前行及（若用了）下一行为已消费。
        """
        if result[key] is not None or not label_re.search(wl):
            return False
        # 值在同行
        v = parse_fn(wl)
        if v is not None:
            result[key] = v
            consumed.add(j)
            return True
        # 值在下一行
        nxt_j = j + 1
        if nxt_j < len(window) and nxt_j not in consumed:
            v = parse_fn(window[nxt_j].strip())
            if v is not None:
                result[key] = v
                consumed.add(j)
                consumed.add(nxt_j)
                # 同行含百分比时也捎带提取收益率（如"-1,277.41 -6.03%"）
                if key == "holdingReturn" and result["holdingReturnRate"] is None:
                    pct = parse_pct(window[nxt_j].strip())
                    if pct is not None:
                        result["holdingReturnRate"] = pct
                return True
        return False

    for j, raw in enumerate(window):
        if j in consumed:
            continue
        wl = raw.strip()

        # 有标签行：按优先级依次尝试（收益率须先于持仓收益，避免%被误读为金额）
        if _try_label(j, wl, LABEL_RETURN_RATE,   parse_pct,   "holdingReturnRate"):
            continue
        if _try_label(j, wl, LABEL_MARKET_VALUE,  parse_money, "amount"):
            continue
        if _try_label(j, wl, LABEL_DAILY_RETURN,  parse_money, "dailyReturn"):
            continue
        if LABEL_TOTAL_RETURN.search(wl) and result["holdingReturn"] is None:
            if not PCT_RE.fullmatch(wl):   # 跳过纯百分比行
                if _try_label(j, wl, LABEL_TOTAL_RETURN, parse_money, "holdingReturn"):
                    continue

        # 裸值行（标签与值各独占一行，常见于支付宝截图）
        # 先尝试百分比（防止"-1,277.41 -6.03%"中的%被忽略）
        bare_pct = parse_pct(wl)
        if bare_pct is not None and result["holdingReturnRate"] is None:
            result["holdingReturnRate"] = bare_pct
            consumed.add(j)
            # 若同行还有金额，继续按金额规则处理（不 continue）

        bare_num = parse_money(wl)
        if bare_num is not None:
            if bare_num > 500 and result["amount"] is None:
                result["amount"] = bare_num
            elif abs(bare_num) < 500 and result["dailyReturn"] is None:
                result["dailyReturn"] = bare_num
            elif result["holdingReturn"] is None:
                result["holdingReturn"] = bare_num
            consumed.add(j)

    return result


def extract_funds_from_lines(lines: list[str]) -> list[dict]:
    """
    从 OCR 文本行中提取基金卡片数据。
    两遍扫描：①找所有基金名称行位置；②对每段区间提取字段值。
    """
    # 第一遍：找基金名称位置
    name_positions = [i for i, ln in enumerate(lines) if is_fund_name(ln.strip())]
    if not name_positions:
        return []

    found = []
    n = len(lines)
    for k, pos in enumerate(name_positions):
        # 扫描范围：到下一基金名称前（最多往后 14 行）
        next_pos = name_positions[k + 1] if k + 1 < len(name_positions) else n
        window_end = min(next_pos, pos + 14)
        window = [lines[j] for j in range(pos + 1, window_end) if j < n]

        fields = _scan_card_window(window)

        # 持仓市值是必填项；若缺失则视为无效卡片
        if fields["amount"] is not None and fields["amount"] > 0:
            found.append({"ocr_name": lines[pos].strip(), **fields})

    return found


# ══════════════════════════════════════════════════════════════
# 匹配：OCR 识别的基金名称 → 现有 portfolio.json 条目
# ══════════════════════════════════════════════════════════════

def best_match(ocr_name: str, holdings: list[dict]) -> Optional[dict]:
    """
    用三级策略在现有持仓中找最佳匹配：
      1. 精确/子串名称匹配
      2. 基金代码出现在 ocr_name 中
      3. difflib 模糊比较（阈值 0.45）
    """
    ocr_lower = ocr_name.lower()

    # 1. 子串匹配（忽略大小写）
    for h in holdings:
        hname = h["name"].lower()
        if hname in ocr_lower or ocr_lower in hname:
            return h
        # 去掉 A/B/C 后缀后再匹配
        core = re.sub(r'[ABC]$', '', h["name"])
        if len(core) >= 4 and core in ocr_name:
            return h

    # 2. 代码出现在文本中
    for h in holdings:
        if h["code"] in ocr_name:
            return h

    # 3. 模糊匹配
    best_h, best_ratio = None, 0.0
    for h in holdings:
        ratio = difflib.SequenceMatcher(None, ocr_name, h["name"]).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_h = h
    if best_ratio >= 0.45:
        return best_h

    return None


# ══════════════════════════════════════════════════════════════
# 差异表：打印旧值 → 新值对照
# ══════════════════════════════════════════════════════════════

FIELD_LABELS = {
    "amount":            "持仓市值",
    "dailyReturn":       "今日收益",
    "holdingReturn":     "持仓收益",
    "holdingReturnRate": "持仓收益率",
}

UNCERTAIN = "待确认"


def build_patch(ocr_fund: dict, existing: dict) -> dict:
    """
    生成一个 patch dict，格式：
      { "field": {"old": v, "new": v, "uncertain": bool}, ... }
    """
    patch = {}
    for field, label in FIELD_LABELS.items():
        new_val = ocr_fund.get(field)
        old_val = existing.get(field)
        if new_val is None:
            # 识别失败 → 标记待确认，保留旧值
            patch[field] = {"old": old_val, "new": old_val, "uncertain": True}
        else:
            patch[field] = {"old": old_val, "new": new_val, "uncertain": False}
    return patch


def print_diff_table(matches: list[dict]) -> None:
    """打印彩色差异对照表（旧值 → 新值）。"""
    COL = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
           "gray": "\033[90m", "reset": "\033[0m", "bold": "\033[1m"}

    print()
    print("=" * 68)
    print(f"{COL['bold']}  OCR 识别结果对照表  →  请核实后确认{COL['reset']}")
    print("=" * 68)

    for m in matches:
        ocr_name = m["ocr_name"]
        h        = m["matched"]
        patch    = m["patch"]

        status = f"{COL['green']}✓ 匹配{COL['reset']}" if h else f"{COL['red']}✗ 未匹配{COL['reset']}"
        print(f"\n  {COL['bold']}{ocr_name}{COL['reset']}  {status}")
        if h:
            print(f"  → 现有条目: {h['name']} ({h['code']})")

        if not h:
            print(f"  {COL['gray']}  跳过（无法匹配现有持仓）{COL['reset']}")
            continue

        for field, label in FIELD_LABELS.items():
            info = patch.get(field, {})
            old  = info.get("old")
            new  = info.get("new")
            unc  = info.get("uncertain", False)

            if unc:
                print(f"    {label:10}: {COL['yellow']}{UNCERTAIN}（保留旧值 {old}）{COL['reset']}")
            elif old == new:
                print(f"    {label:10}: {COL['gray']}{old}（无变化）{COL['reset']}")
            else:
                arrow = f"{COL['red']}{old}{COL['reset']} → {COL['green']}{new}{COL['reset']}"
                print(f"    {label:10}: {arrow}")

    print()
    print("=" * 68)


# ══════════════════════════════════════════════════════════════
# 写入逻辑（复用 update_portfolio.py 的 recompute/validate/write）
# ══════════════════════════════════════════════════════════════

def recompute(data: dict) -> dict:
    """重算总资产和各持仓占比（与 update_portfolio.py 保持一致）。"""
    total = round(sum(h["amount"] for h in data["holdings"]), 2)
    data["totalAsset"] = total
    for h in data["holdings"]:
        h["ratio"] = round(h["amount"] / total * 100, 2) if total else 0.0
    # 占比四舍五入误差校正
    ratio_sum = round(sum(h["ratio"] for h in data["holdings"]), 2)
    diff = round(100.0 - ratio_sum, 2)
    if abs(diff) >= 0.01 and data["holdings"]:
        biggest = max(data["holdings"], key=lambda x: x["amount"])
        biggest["ratio"] = round(biggest["ratio"] + diff, 2)
    return data


def apply_patches(data: dict, matches: list[dict]) -> dict:
    """将 OCR patch 应用到 portfolio data。"""
    holdings_map = {h["code"]: h for h in data["holdings"]}

    for m in matches:
        h = m["matched"]
        if not h:
            continue
        patch = m["patch"]
        entry = holdings_map.get(h["code"])
        if not entry:
            continue
        for field, info in patch.items():
            if not info.get("uncertain"):
                entry[field] = info["new"]

    data["updateTime"] = datetime.date.today().isoformat()
    return data


def write_portfolio(data: dict) -> None:
    with open(PORTFOLIO, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  ✅ 已写入 data/portfolio.json")


def write_html_inline(data: dict) -> None:
    """更新 index.html 内联 portfolioData 块。"""
    import re as re_
    try:
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print("  ⚠️  index.html 未找到，跳过 HTML 更新")
        return

    # 构造内联块（与 update_portfolio.py 风格一致）
    lines = ['const portfolioData = {']
    lines.append(f'    "updateTime": "{data["updateTime"]}",')
    lines.append(f'    "totalAsset": {data["totalAsset"]},')
    lines.append('    "holdings": [')
    hrows = []
    for h in data["holdings"]:
        hrows.append(
            '        {{"name":"{name}","code":"{code}","amount":{amount},"ratio":{ratio},'
            '"dailyReturn":{dr},"holdingReturn":{hr},"holdingReturnRate":{hrr},'
            '"totalReturn":{tr},"category":"{cat}"}}'.format(
                name=h["name"], code=h["code"], amount=h["amount"], ratio=h["ratio"],
                dr=h["dailyReturn"], hr=h["holdingReturn"], hrr=h["holdingReturnRate"],
                tr=h["totalReturn"], cat=h["category"],
            )
        )
    lines.append(",\n".join(hrows))
    lines.append('    ],')
    ta = json.dumps(data["targetAllocation"], ensure_ascii=False)
    ta = ta.replace(", ", ",").replace(": ", ":")
    lines.append(f'    "targetAllocation": {ta}')
    lines.append('};')
    new_block = "\n".join(lines)

    pattern = re_.compile(r"const portfolioData = \{.*?\n\};", re_.DOTALL)
    if not pattern.search(html):
        print("  ⚠️  未在 index.html 中找到 portfolioData 内联块，跳过 HTML 更新")
        return
    html2 = pattern.sub(lambda _: new_block, html, count=1)
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html2)
    print("  ✅ 已更新 index.html 内联 portfolioData 块")


# ══════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(
        description="玄枢Alpha · 持仓 OCR 更新工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("image", help="持仓截图路径（JPG/PNG）")
    ap.add_argument("--yes",      action="store_true", help="跳过确认直接写入")
    ap.add_argument("--no-html",  action="store_true", help="不更新 index.html 内联块")
    ap.add_argument("--dry-run",  action="store_true", help="只打印识别结果，不写入任何文件")
    args = ap.parse_args()

    image_path = args.image
    if not os.path.exists(image_path):
        sys.exit(f"❌ 图片不存在: {image_path}")

    print(f"\n玄枢Alpha · 持仓 OCR 更新  [{datetime.datetime.now().strftime('%H:%M:%S')}]")
    print(f"  图片: {image_path}")

    # 1. OCR
    print("\n  [1/4] 运行 OCR...")
    lines = run_ocr(image_path)
    if not lines:
        sys.exit("❌ OCR 未识别到任何文本")

    if len(lines) < 5:
        print("  ⚠️  识别行数较少，可能截图不清晰或布局特殊")
    print(f"  原始文本行（{len(lines)} 行）:")
    for ln in lines:
        print(f"    {repr(ln)}")

    # 2. 解析基金卡片
    print("\n  [2/4] 解析基金数据...")
    ocr_funds = extract_funds_from_lines(lines)
    print(f"  识别到 {len(ocr_funds)} 个基金卡片")

    if not ocr_funds:
        # 降级：直接从所有文本行提取数字，按行分组
        print("  ⚠️  标准解析失败，尝试全文扫描模式...")
        ocr_funds = fallback_parse(lines)
        if not ocr_funds:
            print("  ❌ 无法从截图中提取持仓数据")
            print("  建议：确认截图包含基金名称、市值等字段，或改用 update_portfolio.py 手动输入")
            sys.exit(1)

    # 3. 匹配现有持仓
    print("\n  [3/4] 与 portfolio.json 匹配...")
    with open(PORTFOLIO, "r", encoding="utf-8") as f:
        data = json.load(f)
    holdings = data["holdings"]

    matches = []
    for of in ocr_funds:
        h = best_match(of["ocr_name"], holdings)
        patch = build_patch(of, h) if h else {}
        matches.append({"ocr_name": of["ocr_name"], "matched": h, "patch": patch})
        status = f"→ {h['name']} ({h['code']})" if h else "→ 未匹配（跳过）"
        print(f"    {of['ocr_name']}  {status}")

    matched_count = sum(1 for m in matches if m["matched"])
    print(f"  匹配成功: {matched_count}/{len(ocr_funds)}")

    # 4. 打印差异表
    print_diff_table(matches)

    if args.dry_run:
        print("  [dry-run] 已打印识别结果，未做任何写入。")
        return

    # 5. 确认写入
    if not args.yes:
        ans = input("  确认将以上识别结果写入 portfolio.json？(y/N): ").strip().lower()
        if ans != "y":
            print("  已取消，未写入任何文件。")
            return

    data = apply_patches(data, matches)
    data = recompute(data)

    # 校验
    total = data["totalAsset"]
    amt_sum = round(sum(h["amount"] for h in data["holdings"]), 2)
    print(f"\n  总资产: ¥{total:,.2f}  金额合计: ¥{amt_sum:,.2f}  差: {total - amt_sum:+.2f}")
    if abs(total - amt_sum) > 1:
        print("  ⚠️  金额差异较大，请检查识别结果")

    write_portfolio(data)
    if not args.no_html:
        write_html_inline(data)

    print("\n  🎉 完成。建议运行 python3 data/signals.py 重新生成交易信号。")


def fallback_parse(lines: list[str]) -> list[dict]:
    """
    降级模式：当标准基金卡片解析失败时，
    从文本行直接提取所有「基金名 + 最大附近金额」。
    """
    funds = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not is_fund_name(stripped):
            continue
        amounts = []
        for look in lines[i + 1 : i + 8]:
            v = parse_money(look)
            if v is not None and v > 100:
                amounts.append(v)
        if amounts:
            funds.append({
                "ocr_name":          stripped,
                "amount":            max(amounts),
                "dailyReturn":       None,
                "holdingReturn":     None,
                "holdingReturnRate": None,
            })
    return funds


if __name__ == "__main__":
    main()
