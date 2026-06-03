#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢持仓更新工具 (交互式)
=========================
交互式录入最新持仓快照，自动重算占比、校验合计，
并同步写入 data/portfolio.json 与 index.html 内联数据块。

用法:
    python3 scripts/update_portfolio.py            # 交互式更新（推荐）
    python3 scripts/update_portfolio.py --json x.json   # 从 json 批量导入
    python3 scripts/update_portfolio.py --no-git        # 不自动 git commit

交互规则:
    - 逐只基金提问，直接回车 = 保留旧值
    - 占比由脚本自动计算，无需手动输入
    - 可在末尾新增 / 删除标的
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

# ---- 路径定位（脚本在 scripts/ 下，项目根在上一级）----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
PORTFOLIO_JSON = os.path.join(ROOT, "data", "portfolio.json")
INDEX_HTML = os.path.join(ROOT, "index.html")

CATEGORIES = ["黄金", "AI/科技", "有色金属", "光伏/新能源", "高端制造", "货币基金", "纳指100", "标普500", "其他"]


# ============== 工具函数 ==============
def load_portfolio():
    with open(PORTFOLIO_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def ask(prompt, default=None, cast=str):
    """交互输入。回车则返回 default。cast 用于类型转换。"""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw == "":
            return default
        try:
            return cast(raw)
        except (ValueError, TypeError):
            print(f"  ⚠️ 输入无效，请输入 {cast.__name__} 类型")


def ask_float(prompt, default=None):
    return ask(prompt, default, lambda x: float(x.replace(",", "")))


def fmt2(v):
    return round(float(v), 2)


# ============== 交互式录入 ==============
def interactive_update(data):
    print("\n" + "=" * 56)
    print("  玄枢持仓更新 · 交互式录入")
    print("  规则：直接回车 = 保留旧值")
    print("=" * 56)

    today = datetime.date.today().isoformat()
    data["updateTime"] = ask("更新日期", today)

    holdings = data["holdings"]
    new_holdings = []

    for i, h in enumerate(holdings, 1):
        print(f"\n--- [{i}/{len(holdings)}] {h['name']} ({h['code']}) ---")
        keep = ask("  跳过这只？(y=保留全部旧值/回车=逐项录入)", "")
        if keep and keep.lower() == "y":
            new_holdings.append(h)
            continue
        h = dict(h)  # copy
        h["amount"] = fmt2(ask_float("  金额(元)", h["amount"]))
        h["dailyReturn"] = fmt2(ask_float("  今日盈亏", h["dailyReturn"]))
        h["holdingReturn"] = fmt2(ask_float("  持有收益", h["holdingReturn"]))
        h["holdingReturnRate"] = fmt2(ask_float("  持有收益率(%)", h["holdingReturnRate"]))
        h["totalReturn"] = fmt2(ask_float("  累计收益", h["totalReturn"]))
        new_holdings.append(h)

    # 删除标的
    print("\n--- 是否删除某些标的？---")
    rm = ask("  输入要删除的基金代码(逗号分隔，回车跳过)", "")
    if rm:
        codes = {c.strip() for c in rm.split(",")}
        before = len(new_holdings)
        new_holdings = [h for h in new_holdings if h["code"] not in codes]
        print(f"  已删除 {before - len(new_holdings)} 只")

    # 新增标的
    print("\n--- 是否新增标的？---")
    while True:
        add = ask("  新增一只？(y/回车=结束)", "")
        if not add or add.lower() != "y":
            break
        name = ask("    名称")
        code = ask("    代码")
        amount = fmt2(ask_float("    金额(元)", 0))
        print("    可选类别:", " / ".join(CATEGORIES))
        category = ask("    类别", "其他")
        new_holdings.append({
            "name": name, "code": code, "amount": amount,
            "dailyReturn": 0.0, "holdingReturn": 0.0,
            "holdingReturnRate": 0.0, "totalReturn": 0.0,
            "category": category,
        })
        print(f"    ✅ 已新增 {name}")

    data["holdings"] = new_holdings
    return data


def json_import(data, json_path):
    """从外部 json 文件导入 holdings（覆盖式）。"""
    with open(json_path, "r", encoding="utf-8") as f:
        incoming = json.load(f)
    if "updateTime" in incoming:
        data["updateTime"] = incoming["updateTime"]
    else:
        data["updateTime"] = datetime.date.today().isoformat()
    if "holdings" not in incoming:
        sys.exit("❌ 导入的 json 缺少 holdings 字段")
    data["holdings"] = incoming["holdings"]
    return data


# ============== 重算 & 校验 ==============
def recompute(data):
    total = round(sum(h["amount"] for h in data["holdings"]), 2)
    data["totalAsset"] = total
    for h in data["holdings"]:
        h["ratio"] = round(h["amount"] / total * 100, 2) if total else 0.0
    # 占比四舍五入误差校正到最大持仓
    ratio_sum = round(sum(h["ratio"] for h in data["holdings"]), 2)
    diff = round(100.0 - ratio_sum, 2)
    if abs(diff) >= 0.01 and data["holdings"]:
        biggest = max(data["holdings"], key=lambda x: x["amount"])
        biggest["ratio"] = round(biggest["ratio"] + diff, 2)
    return data


def validate(data):
    total = data["totalAsset"]
    amt_sum = round(sum(h["amount"] for h in data["holdings"]), 2)
    ratio_sum = round(sum(h["ratio"] for h in data["holdings"]), 2)
    print("\n" + "=" * 56)
    print("  校验")
    print("=" * 56)
    print(f"  总资产        : ¥{total:,.2f}")
    print(f"  金额合计      : ¥{amt_sum:,.2f}  (差 {total - amt_sum:+.2f})")
    print(f"  占比合计      : {ratio_sum:.2f}%")
    daily = round(sum(h["dailyReturn"] for h in data["holdings"]), 2)
    hold = round(sum(h["holdingReturn"] for h in data["holdings"]), 2)
    print(f"  今日盈亏合计  : {daily:+.2f}")
    print(f"  持有收益合计  : {hold:+.2f}")
    ok = abs(total - amt_sum) < 0.01 and abs(ratio_sum - 100.0) < 0.05
    print(f"  结果          : {'✅ 通过' if ok else '⚠️ 有偏差，请复核'}")
    # 集中度预警
    for h in data["holdings"]:
        if h["ratio"] > 25:
            print(f"  🚨 集中度预警: {h['name']} 占比 {h['ratio']}% (>25%)")
    return ok


# ============== 写入 ==============
def write_json(data):
    with open(PORTFOLIO_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  ✅ 已写入 {os.path.relpath(PORTFOLIO_JSON, ROOT)}")


def build_inline_block(data):
    """生成 index.html 内联 portfolioData 块（与历史风格一致）。"""
    lines = []
    lines.append('const portfolioData = {')
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
    return "\n".join(lines)


def write_html(data):
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()
    # 匹配 const portfolioData = {...}; 整块（非贪婪到首个 "}; ）
    pattern = re.compile(r"const portfolioData = \{.*?\n\};", re.DOTALL)
    if not pattern.search(html):
        sys.exit("❌ 未在 index.html 中找到 portfolioData 内联块，已中止（避免误写）")
    new_block = build_inline_block(data)
    html2 = pattern.sub(lambda m: new_block, html, count=1)
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html2)
    print(f"  ✅ 已写入 {os.path.relpath(INDEX_HTML, ROOT)} (内联块)")


def git_commit(data):
    msg = f"更新持仓快照 {data['updateTime']} (总额{data['totalAsset']})"
    try:
        subprocess.run(["git", "-C", ROOT, "add", "-A"], check=True)
        subprocess.run(["git", "-C", ROOT, "commit", "-m", msg], check=True)
        print(f"  ✅ git commit: {msg}")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ git commit 失败（可能无改动）: {e}")


# ============== 主流程 ==============
def main():
    ap = argparse.ArgumentParser(description="玄枢持仓更新工具")
    ap.add_argument("--json", help="从 json 文件批量导入 holdings")
    ap.add_argument("--no-git", action="store_true", help="不自动 git commit")
    args = ap.parse_args()

    data = load_portfolio()

    if args.json:
        data = json_import(data, args.json)
    else:
        data = interactive_update(data)

    data = recompute(data)
    ok = validate(data)

    confirm = input("\n确认写入？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消，未做任何写入。")
        return

    write_json(data)
    write_html(data)

    if not args.no_git:
        do_git = input("自动 git commit？(Y/n): ").strip().lower()
        if do_git != "n":
            git_commit(data)

    print("\n🎉 完成。")


if __name__ == "__main__":
    main()
