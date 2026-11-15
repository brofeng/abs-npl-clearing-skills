# -*- coding: utf-8 -*-
"""把招行建鑫 payload 适配成「版式契约」（技能 3.1 build_single.py 的输入格式）

★ 为什么需要这一层
────────────────────────────────────────────────────────────
技能 3.0 的成稿器 `build_single.py` 是**版式唯一入口**（CSS 89KB、八节结构、
侧栏、图表引擎），是费了很大精力设计的资产。但它的输入契约是按中信惠元写的：
  · `payload.dist.recrate`（招行是顶层 `payload.recrate`）
  · `liquidation.terminate_date`（招行只有 `liquidation_date`）
  · `metrics.flows`（招行无）
  · `payload.waterfall_order`（分配顺序 14 步）
  · `payload.sources`（披露文件清单）
  · `meta.rf` / `meta.rf_note`（XNPV 折现率）

本脚本不做任何「改写口径」的事，只做**字段搬运与就地生成**，输出
`<proj>/02_提取数据/payload_layout.json`，供
    ABS_ASSETS=<临时目录> python build_single.py --out <dir>
使用。原始 payload.json 保持不动（09/10/13 那条产线继续用）。

★ waterfall_order 的诚实处理
  中信能给出合同约定的 14 步文字（说明书正文有列表）。
  招行的分配顺序在说明书里是**图示**（「图一：违约事件发生前的现金流分配机制」），
  文本层取不到，OCR 两页图也不可靠。
  故本脚本用「清算报告实际现金流出科目的发生顺序」生成顺序表，并在
  `_waterfall_basis` 里注明来源，报告正文据此标注「实际执行顺序」。

用法
  python 14_to_layout.py --proj "E:\\中国建设银行建鑫冒烟测试\\建鑫2023年第5期"
  python 14_to_layout.py --all
  python 14_to_layout.py --all --stage <目录>   # 同时铺好 build_single 的输入目录
"""
import argparse
import json
import os
import shutil
import sys

# ★ 路径无关（4.0）：技能根由本文件位置反推，不写死任何盘符/用户名。
#   pipeline/ 与 single/ 同级，故上溯两级即技能根；
#   把脚本单独拷到项目里用时，用 ABS_SKILL 环境变量指定技能根。
_HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = (os.environ.get("ABS_SKILL")
         or os.path.dirname(os.path.dirname(_HERE)))
# ★ BASE 是「**批次根**」——即各期子目录（兴瑞2021年第一期/…）的父目录，
#   不是技能目录、也不是单期目录。默认由 --proj 的父目录推出；
#   也可用 ABS_BATCH 环境变量指定。4.0 去掉了原先写死用户名/盘符的做法。
BASE = os.environ.get("ABS_BATCH") or ""
ASSET_SRC = (os.environ.get("ABS_ASSETS")
             or os.path.join(SKILL, "assets", "single"))

# 清算报告「资产池现金流出」科目的**报表排版顺序**（≠ 合同分配顺序）
FEE_ORDER = ["税收", "代理兑付费用", "发行费用", "受托机构报酬", "资金保管机构报酬",
             "执行费用及执行费用利息", "贷款服务机构报酬", "审计费", "跟踪评级服务费",
             "其他费用支出", "证券利息总支出", "证券本金总支出", "次级档超额收益",
             "转存下期金额"]

# ── 合同分配顺序 → 矩阵行 ────────────────────────────────────
# ★ 为什么不能沿用 FEE_ORDER 当矩阵行序（本轮实测的重大错误）
#   FEE_ORDER 是清算报告**表格的排版顺序**，把证券科目一律堆在费用科目之后。
#   而合同（说明书第七章）的真实顺序是交错的，其中最关键的一条：
#     **第9步 次级档本金 → 第10步 次级档固定资金成本**
#   与"固资在次级本金之前"的直觉相反。若照 FEE_ORDER 排，两者会颠倒，
#   而表内合计依旧配平（自洽但错），任何只看配平的门禁都查不出来。
#
#   故本表以**说明书抽出的合同步**为骨架（payload.waterfall.steps），
#   再把清算报告科目挂到对应步上。挂不上的一律另立行并注明，不猜。
#
# 键＝合同步的特征词（按顺序匹配 steps[].text）；值＝该步下的科目行定义
#   (档位, 科目名, 取数方式, 清算报告候选键, 备注)
#
# ★ 第 1 个字段是矩阵「档位」列的**显示文本**，必须能区分 优先 / 次级。
#   取值用 2 字（优先/次级），与「费用」「储备」对齐：该列固定 56px 宽、
#   单元格左右 padding 各 10px、字号 12px，只剩 36px —— 恰好只够 3 个汉字，
#   零余量配 nowrap 会挤，2 字留 12px 余量。
#   原实现证券端一律写「证券」，于是表中 18 行里有 5 行的档位都叫「证券」，
#   读者看不出哪些行属次级受偿 —— 而这张表最需要看清的恰恰是
#   「次级档本金(9) → 次级档固定资金成本(10)」这个反直觉次序，
#   档位却把两者都标成「证券」，等于把关键信息抹掉了。
#   该字段仅参与显示（build_single 1143 行直接输出，不做配色/计算），
#   故修正取值不影响任何数字与断言，只让"档"这一维真正可读。
_WF_MAP = [
    (("税",), [("费用", "税收", ("税收", "税费"), "")]),
    (("发行费用",), [("费用", "发行费用", ("发行费用", "发行登记服务费", "承销报酬"), "")]),
    (("支付代理机构", "受托人"),
     [("费用", "受托机构报酬", ("受托机构报酬",), ""),
      ("费用", "资金保管机构报酬", ("资金保管机构报酬",), ""),
      ("费用", "代理兑付费用", ("代理兑付费用",), ""),
      ("费用", "跟踪评级服务费", ("跟踪评级服务费", "跟踪评级费", "评级服务费"), ""),
      ("费用", "审计费", ("审计费",), ""),
      ("费用", "律师费", ("律师费",), "")]),
    # ★ 顺序敏感：第5步原文「将相应金额记入信托（**流动性**）储备账户，使该账户的
    #   余额不少于必备流动性储备金额，但若**优先档**资产支持证券全部未偿本金余额及
    #   **利息**当期预计可以偿付完…」——它同时含「优先档」和「利息」。
    #   若把 (优先档,利息) 排在前，第5步会被误判成第二个「优先档利息」：
    #   实测 20 单（2021二/五/九、2022一/四/六/八、2023一/五 等）出现
    #   "第4步消失、第5步出现两行优先档利息"，编号连续性断言当场报
    #   「最高 12 步／共 11 个编号」。
    #   故 (流动性) 必须排在 (优先档,利息) 之前。
    # ★ 房贷说明书多 3 步（15 步 vs 小微 12 步），第5–8步全部含「流动性」：
    #     第5步 流动性支持承诺费 → 费用科目
    #     第6步 信托（流动性）储备账户补足 → 储备
    #     第7步 特别信托受益人·**收益**部分
    #     第8步 特别信托受益人·**本金**部分
    #   若只用笼统的 ("流动性",)，这 4 步会全被吃成「流动性储备补足」——
    #   实测 2021四/七期矩阵出现 4 行同名「流动性储备补足」，其中 3 行的金额归属错。
    #   故必须按「具体 → 笼统」排。
    (("流动性支持承诺费",),
     [("费用", "流动性支持承诺费", ("流动性支持承诺费",), "流动性支持机构收取的承诺费")]),
    (("流动性", "储备"),
     [("储备", "流动性储备补足", None, "补足信托（流动性）储备账户至必备金额")]),
    (("特别信托受益", "收益"),
     [("其他", "特别信托受益人·收益", None, "流动性支持机构作为特别信托受益人的收益部分")]),
    (("特别信托受益", "本金"),
     [("其他", "特别信托受益人·本金", None, "流动性支持机构已支付未获分配的支持款项余额")]),
    (("流动性",), [("储备", "流动性储备补足", None, "本单无流动性储备账户")]),
    (("优先档", "利息"), [("优先", "优先档利息", None, "")]),
    (("超过", "优先支出上限"),
     [("费用", "超限费用支出", ("其他费用支出",), "")]),
    (("优先档", "本金"), [("优先", "优先档本金", None, "")]),
    (("基本服务费",), [("费用", "贷款服务机构报酬", ("贷款服务机构报酬",), "")]),
    # ★ 顺序敏感：第11步原文是「在次级档…固定资金成本偿还完毕后，将…超额奖励服务费
    #   …转入『费用和开支』账户」，它同时含「次级档」「固定资金成本」，若把
    #   (次级档,固定资金成本) 排在前，第11步会被误认成第10步的重复行。
    #   故「超额奖励服务费」必须先匹配。
    (("超额奖励服务费",),
     [("费用", "超额奖励服务费", ("超额奖励服务费",),
       "逐期受托报告「资产池现金流出」单列；清算报告未单列（已并入贷款服务机构报酬）")]),
    (("次级档", "本金"), [("次级", "次级档本金", None, "")]),
    (("次级档", "固定资金成本"), [("次级", "次级档固定资金成本", None, "")]),
    (("次级档", "收益"), [("次级", "次级档收益", None, "")]),
]


def build_waterfall_rows(P):
    """按**合同顺序**生成分配矩阵行

    返回 {"basis", "page_hint", "rows":[{step, step_tag, lvl, name, kind, cands, memo}]}
      step      合同步号（1..N）；0 表示资产池层面前置扣除，不在信托账户分配序列内
      step_tag  表格里显示的「第N步」文本
      kind      "out"（取逐期 outflow 科目） / "sen_int" / ... （取分档表字段）
    """
    W = P.get("waterfall") or {}
    steps = W.get("steps") or []
    rows = []

    # ① 资产池层面前置扣除：说明书第七章第4条明确「扣除『处置费用』和过渡期
    #    代缴税费后的所有『处置收入』应按照…顺序分配」——它发生在信托账户分配**之前**
    # ★ 逐期受托报告的「资产池现金流出」表**不含**处置费用，该项只在清算报告里
    #   以全周期单列科目出现（建鑫2021-1：61,433,367.10）。
    #   故取数方式为 lump：逐期留空、合计取清算报告值，并在 memo 注明口径，
    #   否则整行全「—」，读者会以为该单没有处置费用。
    # ★ lump 还是 out 必须**逐单判定**，不能一刀切：
    #     建行：逐期受托报告「资产池现金流出」里**没有**处置费用（该科目只在清算报告
    #           以全周期单列出现）→ 只能 lump，否则整行全「—」；
    #     招行：逐期表里**有**「执行费用及执行费用利息」→ 必须 out，
    #           若再 lump 加一次就是重复计入（和萃2021-1 会从 100% 虚增到 109%）。
    # ★ 科目名三家三叫法，判定表必须全都认：
    #   建行「处置费用」/ 中信·招行「执行费用及执行费用利息」/ **兴业「执行费用」**。
    #   漏了兴业这种写法，_in_per 判成 False → 走 lump（取清算报告一次性合计），
    #   而逐期表里本来就有「执行费用」→ 它又会以「未归集」再列一行，
    #   同一笔钱记两遍，矩阵合计占回收虚增到 157%~189%（实测 2021二/2022一/2022三）。
    _dc = ["处置费用", "执行费用及执行费用利息", "执行费用"]
    _in_per = any(((pp.get("outflow") or {}).get(k) is not None)
                  for pp in (P.get("periods") or []) for k in _dc)
    rows.append({"step": 0, "lvl": "前置" if not _in_per else "费用",
                 "name": "资产池处置费用",
                 "kind": "out" if _in_per else "lump",
                 "lump_key": "dispose_exec_fee", "cands": _dc,
                 "memo": ("逐期「资产池现金流出」已单列，按逐期取数"
                          if _in_per else
                          "资产池层面先行扣除；逐期受托报告不单列，合计取清算报告")})

    if steps:
        for st in steps:
            txt = st.get("text") or ""
            hit = None
            for keys, defs in _WF_MAP:
                if all(k in txt for k in keys):
                    hit = defs
                    break
            if not hit:
                # 合同里有、但映射表没覆盖 → 立一行占位并保留原文，绝不静默丢步
                hit = [("其他", (txt[:18] + "…") if len(txt) > 18 else txt, None,
                        "合同有此步，未配置取数口径")]
            for lvl, name, cands, memo in hit:
                if name in ("优先档利息", "优先档本金", "次级档本金",
                            "次级档固定资金成本", "次级档收益"):
                    kind = {"优先档利息": "sen_int", "优先档本金": "sen_prin",
                            "次级档本金": "sub_prin", "次级档固定资金成本": "sub_fix",
                            "次级档收益": "sub_inc"}[name]
                elif cands is None:
                    kind = "none"          # 合同有、本单清算报告未单列
                else:
                    kind = "out"
                rows.append({"step": st.get("no"), "lvl": lvl, "name": name,
                             "kind": kind, "cands": cands or [],
                             "memo": memo or (txt[:40] if not memo else memo)})
    else:
        # 说明书无文字层（图示体例）→ 退回 FEE_ORDER，并在 basis 里声明是实际顺序
        for name in FEE_ORDER:
            rows.append({"step": None, "lvl": _cat(name), "name": name,
                         "kind": "out", "cands": [name],
                         "memo": "说明书分配机制为图示体例，按清算报告科目发生顺序列示"})

    # ② 清算报告出现但合同 12 步里没有归属的科目：另立「未归集」区，附在尾部
    return rows


def _cat(name):
    """把科目归到 优先档 / 次级档 / 储备 / 费用 四类（矩阵「档位」列的显示文本）

    ★ 原实现把证券端统一归成「证券」，档位列因此分不出优先与次级。
      这张表的核心读点就是次级内部的受偿次序（本金先于固定资金成本），
      档位必须落到"哪一档"，不能停在"证券"这个科目大类上。
    ★ 该返回值只用于显示，不参与配色与计算（已核 build_single 唯一使用处是
      直接写入 <td>），故不影响任何数值与断言。
    """
    if "次级" in name:
        return "次级"
    if "优先" in name:
        return "优先"
    if ("证券" in name) or ("档" in name):     # 兜底：无明确档位标识的证券科目
        return "证券"
    if "储备" in name:
        return "储备"
    return "费用"


def build_waterfall(P):
    """实际执行顺序表 [[(a), 科目, 类别], ...]

    ★ 只保留该单清算报告里**真实出现过**的科目，不硬套 14 步：
      没发生的步骤列出来等于虚构分配过程。
    """
    fd = (P.get("liquidation") or {}).get("fee_detail") or {}
    seen = [k for k in FEE_ORDER if k in fd or k in
            ("证券利息总支出", "证券本金总支出", "次级档超额收益")]
    # 清算报告 fee_detail 用的是简称，映射回全称
    alias = {"处置费": "执行费用及执行费用利息", "贷款服务费": "贷款服务机构报酬",
             "代理兑付费": "代理兑付费用", "发行费": "发行费用",
             "其他费用": "其他费用支出", "跟踪评级费": "跟踪评级服务费"}
    present = set()
    for k in fd:
        present.add(alias.get(k, k))
    rows = []
    for name in FEE_ORDER:
        if name in present:
            rows.append(name)
    # 证券端三个科目即便 fee_detail 里没有，只要清算报告有兑付就补上
    L = P.get("liquidation") or {}
    if (L.get("sen_interest_paid") or 0) > 0 and "证券利息总支出" not in rows:
        rows.append("证券利息总支出")
    if (L.get("sen_principal_paid") or 0) > 0 and "证券本金总支出" not in rows:
        rows.append("证券本金总支出")
    if (L.get("sub_income_paid") or 0) > 0 and "次级档超额收益" not in rows:
        rows.append("次级档超额收益")
    if not rows:
        rows = FEE_ORDER[:]
    return [["(%s)" % chr(97 + i), n, _cat(n)] for i, n in enumerate(rows)]


def build_flows(P, M):
    """两档现金流（XIRR/XNPV 的输入），挂真实支付日

    ★ 与 08_assemble.py 的 xirr 口径必须**逐笔一致**，否则报告上会出现
      「卡片写 XIRR 51.57%，正下方折现表按自己的现金流算出来 49.78%」——
      读者一复算就发现对不上，且差额可达数百 bp。

    ★ 次级档修复（2026-10-30）：原实现是「发行日 −本金，每期 +本金，
      **收益总额一次性挂清算日**」。这等于把受托报告里**已按支付日实际派发**
      的两笔收益（第 3 期 2024-06-26 的固资＋超额、第 4 期 2024-07-18 的超额）
      合并挪到清算日 2024-07-30，现金流时点整体后移：
        兴瑞2023七期  表内 49.78% vs 卡片 51.57%（−179bp）
        兴瑞2024三期  表内 74.47% vs 卡片 80.95%（−648bp）
      现改为逐期挂「本金＋固定资金成本＋超额收益」，只有**逐期未覆盖**的
      清算分派（residual）才挂清算日 —— 与 08 的 build_metrics 同一判据。
    """
    meta = P.get("meta") or {}
    L = P.get("liquidation") or {}
    T = P.get("tranche") or {}
    PER = P.get("periods") or []
    iss = meta.get("issue_date")
    if not iss:
        return {}
    liq = L.get("liquidation_date") or L.get("liquidation_end")
    last_pay = max([p["pay_date"] for p in PER if p.get("pay_date")], default=None)

    def flows(side):
        base = ((T.get("senior") or {}).get("issue") if side == "sen"
                else (T.get("sub") or {}).get("issue"))
        if not base:
            return []
        out = [{"date": iss, "cf": -float(base)}]
        for p in PER:
            if side == "sen":
                amt = ((p.get("sen_principal") or 0.0)
                       + (p.get("sen_interest") or 0.0))
            else:
                amt = ((p.get("sub_principal") or 0.0)
                       + (p.get("sub_fixed_cost") or 0.0)
                       + (p.get("sub_income") or 0.0))
            if amt:
                out.append({"date": p.get("pay_date") or last_pay, "cf": round(float(amt), 2)})
        return out

    sen = flows("sen")
    sub = flows("sub")
    # 清算日只补「逐期未被覆盖」的部分（不得把已派发的收益再挂一次）
    _base_sub = (T.get("sub") or {}).get("issue") or 0.0
    _per_sub = sum((p.get("sub_principal") or 0.0) + (p.get("sub_fixed_cost") or 0.0)
                   + (p.get("sub_income") or 0.0) for p in PER)
    _want_sub = _base_sub + (L.get("sub_income_paid") or 0.0)
    _resid = round(_want_sub - _per_sub, 2)
    tail = liq or last_pay
    if sub and _resid > 0.01 and tail:
        sub.append({"date": tail, "cf": _resid})
    return {"sen": sen, "sub": sub}


def build_sources(P):
    """披露文件清单（版式第⑧节用）"""
    meta = P.get("meta") or {}
    idx = None
    p = os.path.join(BASE, meta.get("_proj_dir") or "", "")
    src = (P.get("_sources") or {})
    out = [
        {"key": "SM", "file": f"{meta.get('display_name') or ''}不良资产支持证券发行说明书.pdf",
         "pages": meta.get("sm_pages") or 0,
         "used": "资产池特征、结构分布、预测回收、证券分层、交易结构"},
        {"key": "ZZ", "file": "评级报告（中债资信）", "pages": 0,
         "used": "预计回收总额与回收率（权威口径）"},
        {"key": "TR", "file": "受托机构报告 逐期", "pages": 0,
         "used": "逐期回收、账户核算、分档兑付、现金流出"},
        {"key": "CL", "file": "清算报告 + 专项复核说明", "pages": 0,
         "used": "清算日、清仓回购、费用明细、剩余资金"},
    ]
    for k, v in src.items():
        if v:
            out.append({"key": str(k)[:8], "file": str(v)[:60], "pages": 0,
                        "used": str(k)})
    return out


def fill_balances(P):
    """期次表字段对齐 + 余额列前值填充

    ★ 字段对齐：版式契约用中信的期次字段名，招行少两个——
        · sub_fixed_cost（次级档固定资金成本）：招行 2023 起的新体例**没有**这个科目，
          按 0 处理（不是缺失，是结构上没有）。
        · sub_income（次级档收益）：招行放在 outflow["次级档超额收益"] 里。
    ★ 为什么余额必须填：版式第④节要画「分档累计本金走势」堆叠面积图，
      某期是 None 会让 svg 引擎算坐标时 TypeError（实测建鑫2023五期第12期
      次级余额缺失，直接崩栈）。
    ★ 为什么不填 0：余额缺口填 0 会让曲线出现假谷底，比缺失更误导。
      用前一期值填充（金额余额在「本期无兑付」时本就等于前一期），
      并把填过的位置记进 `_balance_filled`，报告正文可据此标注。
      真正的修法是在 05_parse_trustee.py 补齐解析，此处只作版式兜底。
    """
    PER = P.get("periods") or []
    for p in PER:
        if p.get("sub_fixed_cost") is None:
            p["sub_fixed_cost"] = 0.0
        if p.get("sub_income") is None:
            of = p.get("outflow") or {}
            p["sub_income"] = of.get("次级档超额收益") or 0.0
    filled = []
    for col in ("sen_balance_after", "sub_balance_after"):
        prev = None
        for p in PER:
            v = p.get(col)
            if v is None:
                if prev is not None:
                    p[col] = prev
                    filled.append({"period": p.get("period"), "col": col, "filled": prev})
            else:
                prev = v
    return filled


def build_materials(proj, P):
    """材料清册：按实际下载的文件与文本索引生成（供第⑧节列示）

    ★ 为什么必须动态：版式原先把惠元第三期的材料清单写死在文案里，
      换到招行就成了虚构事实——
        · 招行没有「联合资信」评级（只有中债资信 + 新世纪）
        · 说明书不是 681 页（招行 2021 二期 431 页、2023 五期 560 页）
        · 建鑫2021 年第 1 期**没有清算报告**（清算未结项）
      这些一旦套用，读者会以为报告引用了根本不存在的文件。
    """
    dat = os.path.join(proj, "02_提取数据")
    dl = os.path.join(proj, "01_下载文档")
    fs = os.listdir(dl) if os.path.isdir(dl) else []
    idx = []
    ip = os.path.join(dat, "_text_index.json")
    if os.path.exists(ip):
        try:
            idx = json.load(open(ip, encoding="utf-8"))
        except Exception:
            idx = []

    def pages_of(key):
        for r in idx:
            if r.get("key") == key:
                return r.get("pages")
        return None

    def has(*pats):
        return [f for f in fs if all(p in f for p in pats)]

    trs = [r for r in idx if str(r.get("key", "")).startswith("TR")
           and str(r.get("key", "TR"))[2:].isdigit()]
    trs.sort(key=lambda r: int(r["key"][2:]))
    n_tr = len(trs) or len([f for f in fs if "受托机构报告" in f and "复核" not in f])

    mats = []
    # ① 发行说明书
    sm = has("发行说明书")
    mats.append({"name": "发行说明书", "present": bool(sm),
                 "detail": (f"{pages_of('SM')} 页" if pages_of("SM") else "")})
    # ② 受托机构报告
    mats.append({"name": "受托机构报告", "present": n_tr > 0,
                 "detail": f"{n_tr} 期" if n_tr else ""})
    # ③ 中债资信评级（定源铁律：预计回收与发行规模只认它）
    zz = has("中债资信")
    mats.append({"name": "中债资信评级报告", "present": bool(zz),
                 "detail": (f"{pages_of('ZZ')} 页" if pages_of("ZZ") else "")})
    # ④ 新世纪评级（辅助，不作取数来源）
    xs = has("新世纪")
    mats.append({"name": "新世纪评级报告", "present": bool(xs),
                 "detail": "仅交叉校验，不作取数来源" if xs else ""})
    # ⑤ 清算文书：清算报告 / 清算审计报告 / 专项复核说明
    lq = [f for f in fs if "清算" in f or "专项复核" in f]
    mats.append({"name": "清算报告（含审计/复核说明）", "present": bool(lq),
                 "detail": (f"{len(lq)} 份" if lq else "源文件缺失")})
    # ⑥ 重大事件报告书
    zd = has("重大事件")
    mats.append({"name": "重大事件报告书", "present": bool(zd), "detail": ""})
    # ⑦ 法律意见书 / 会计意见书（通常不单独披露）
    mats.append({"name": "法律意见书", "present": bool(has("法律意见")),
                 "detail": "通常不单独披露" if not has("法律意见") else ""})
    mats.append({"name": "会计意见书", "present": bool(has("会计意见")),
                 "detail": "通常不单独披露" if not has("会计意见") else ""})
    # ⑧ 跟踪评级报告
    gz = has("跟踪评级")
    mats.append({"name": "跟踪评级报告", "present": bool(gz),
                 "detail": "报告不引用外部评级观点" if not gz else ""})

    # 清算类材料缺失时，说明降级取数方式
    deg = None
    L = (P.get("liquidation") or {})
    if not lq:
        deg = (L.get("degraded_note")
               or "无清算报告，清算相关字段按末次受托机构报告降级取数")
    return {"items": mats,
            "present_n": sum(1 for m in mats if m["present"]),
            "total_n": len(mats),
            "liquidation_absent": (not lq),
            "degraded": deg}


def adapt(proj):
    d = os.path.join(proj, "02_提取数据")
    P = json.load(open(os.path.join(d, "payload.json"), encoding="utf-8"))
    M = json.load(open(os.path.join(d, "metrics.json"), encoding="utf-8"))
    meta = dict(P.get("meta") or {})
    L = dict(P.get("liquidation") or {})
    T = dict(P.get("tranche") or {})
    DIST = dict(P.get("dist") or {})

    # ① 展示字段（版式契约必需）
    name = meta.get("display_name") or os.path.basename(proj)
    meta.setdefault("display_name", name)
    meta.setdefault("originator_short", (meta.get("originator_short")
                                         or meta.get("originator") or "").replace("股份有限公司", ""))
    # 品种由 02 从说明书读出后带过来；此处只做缺失兜底，不写死品类
    meta.setdefault("variety", (P.get("meta") or {}).get("variety") or "—")
    meta["file_name"] = f"{name}_不良ABS穿透分析_v2.html"
    meta["brand_short"] = "建鑫"      # 同业图/文案用简称
    meta["bank_group"] = "中国建设银行"
    meta["name"] = f"{name}不良资产支持证券"
    meta["_proj_dir"] = os.path.basename(proj)

    # ② XNPV 折现率：优先取数据里已有的，否则按发行年份给 1 年期国债收益率
    #    ★ 这是「按发行日就近取」的近似，不是精确到当日的曲线值。
    #      故写进 rf_note，报告正文会原样显示，读者能看见这是近似口径。
    RF_BY_YEAR = {2021: 0.0238, 2022: 0.0202, 2023: 0.0215, 2024: 0.0190, 2025: 0.0150}
    if meta.get("rf") is None:
        y = int(str(meta.get("issue_date") or "2023")[:4])
        meta["rf"] = RF_BY_YEAR.get(y, 0.0215)
        meta["rf_note"] = (f"1 年期国债到期收益率约 {meta['rf']*100:.2f}%"
                           f"（{y} 年，中债国债收益率曲线，按发行年份就近取）")
    else:
        meta.setdefault("rf_note", f"1 年期国债到期收益率 {meta['rf']*100:.2f}%")

    # ③ dist.recrate 搬运
    if "recrate" not in DIST and P.get("recrate"):
        DIST["recrate"] = P["recrate"]

    # ④ terminate_date：招行只有 liquidation_date
    if not L.get("terminate_date"):
        L["terminate_date"] = L.get("liquidation_date") or L.get("liquidation_end")

    # ⑤ flows：优先用 metrics 已有，否则生成
    if not (M.get("flows") or {}).get("sen"):
        M["flows"] = build_flows(P, M)

    out = dict(P)
    out["meta"] = meta
    out["liquidation"] = L
    out["tranche"] = T
    out["dist"] = DIST
    _filled = fill_balances(P)
    out["periods"] = P["periods"]
    out["_balance_filled"] = _filled
    # ★ 矩阵行序：优先用**合同顺序**（说明书第七章文字条款），
    #   退回时必须是"实际顺序"并如实标注 —— 报告标题写「合同约定顺序」就不能拿实际顺序充数。
    _WF = P.get("waterfall") or {}
    out["waterfall_rows"] = build_waterfall_rows(P)
    out["waterfall"] = _WF
    out["waterfall_order"] = build_waterfall(P)     # 兼容旧字段（瀑布图用）
    if _WF.get("steps"):
        out["_waterfall_basis"] = (
            f"合同约定顺序（{_WF.get('basis')}，{_WF.get('page_hint')}，"
            f"共 {len(_WF['steps'])} 步）")
        out["_waterfall_is_contract"] = True
    else:
        out["_waterfall_basis"] = ("实际执行顺序（按清算报告「资产池现金流出」科目发生顺序）；"
                                   "本单说明书分配机制为图示体例，文字层不可得")
        out["_waterfall_is_contract"] = False
    out["sources"] = build_sources(P)
    # ⑥ 材料清册：第⑧节「数据质量与披露」要用它列实际齐备/缺失的材料
    #   ★ 版式里原来把「5 期受托报告、清算审计报告、清算报告复核、681 页说明书、
    #     联合资信评级」写死在文案里，换行到招行就变成虚构事实（招行无联合资信、
    #     说明书非 681 页、有的单无清算报告）。改为按实际下载目录与文本索引生成。
    out["materials"] = build_materials(proj, P)
    fp = os.path.join(d, "payload_layout.json")
    json.dump(out, open(fp, "w", encoding="utf-8", newline=""), ensure_ascii=False, indent=1)
    M["file_name"] = meta["file_name"]
    mp = os.path.join(d, "metrics_layout.json")
    json.dump(M, open(mp, "w", encoding="utf-8", newline=""), ensure_ascii=False, indent=1)
    return fp, mp


def stage(proj, dst):
    """铺 build_single 的输入目录：payload/metrics + CSS + peer"""
    os.makedirs(dst, exist_ok=True)
    d = os.path.join(proj, "02_提取数据")
    shutil.copy2(os.path.join(d, "payload_layout.json"), os.path.join(dst, "payload.json"))
    shutil.copy2(os.path.join(d, "metrics_layout.json"), os.path.join(dst, "metrics.json"))
    for f in ("v11_base.css", "v11_enh.css"):
        shutil.copy2(os.path.join(ASSET_SRC, f), os.path.join(dst, f))
    # peer：优先用全行同业集（15 中信 + 17 建鑫），无则用技能自带
    peer = os.path.join(BASE, "脚本", "peer_all.json")
    src = peer if os.path.exists(peer) else os.path.join(ASSET_SRC, "peer28.json")
    shutil.copy2(src, os.path.join(dst, "peer28.json"))
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--stage", default=None, help="同时铺好 build_single 输入目录")
    ap.add_argument("--prefix", default=None,
                    help="--all 时的期次目录名前缀（如 兴瑞/建鑫/惠元/和萃）；缺省取 ABS_PREFIX")
    a = ap.parse_args()
    # ★ BASE（批次根）未显式指定时，由 --proj 的父目录推出 —— 这才符合
    #   「一个批次目录下放 N 个期次子目录」的通行结构，且不依赖本文件位置。
    global BASE
    if not BASE:
        if a.proj:
            BASE = os.path.dirname(os.path.abspath(a.proj))
        else:
            ap.error("--all 需要 ABS_BATCH 环境变量指定批次根目录")
    projs = []
    if a.all:
        _pre = a.prefix or os.environ.get("ABS_PREFIX") or ""
        if not _pre:
            ap.error("--all 必须给 --prefix（期次目录名前缀），不能沿用他行写死的品牌名")
        for n in sorted(os.listdir(BASE)):
            p = os.path.join(BASE, n)
            if n.startswith(_pre) and os.path.exists(
                    os.path.join(p, "02_提取数据", "payload.json")):
                projs.append(p)
    elif a.proj:
        projs = [a.proj]
    else:
        ap.error("需要 --proj 或 --all")
    for p in projs:
        fp, mp = adapt(p)
        n = len(json.load(open(fp, encoding="utf-8"))["waterfall_order"])
        print(f"  {os.path.basename(p):16s} → payload_layout.json（{n} 步分配顺序）")
    if a.stage and projs:
        stage(projs[0], a.stage)
        print(f"  staged → {a.stage}")
    print(f"\n共 {len(projs)} 期")
    return 0


if __name__ == "__main__":
    sys.exit(main())
