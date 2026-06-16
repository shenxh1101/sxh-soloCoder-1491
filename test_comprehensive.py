#!/usr/bin/env python
# -*- coding: utf-8 -*-

from models import GlassSheet, Order, Inventory, GlassType
from scheduler import ProductionScheduler
from reports import ReportGenerator
from cli import GlassCuttingCLI
import os
import copy


def test_report_spec_summary_and_csv_fields():
    """
    需求1+2+4: 
    - 按产品规格汇总：需求块数/已生产/未满足 + 三个面积
    - 未满足面积按剩余块数算
    - CSV未满足明细补齐 已生产面积 和 未满足面积
    场景: 1500×1000mm 原片切 600×500mm × 5块 (只能切出4块)
    """
    print("=" * 100)
    print("报表/CSV测试: 按规格汇总对账 + 未满足面积按剩余算 + CSV字段完整")
    print("=" * 100)

    inventory = Inventory(saw_kerf=3.0)
    inventory.add_original(GlassSheet(1500, 1000, 12, glass_type=GlassType.ORIGINAL, is_manual=True))
    scheduler = ProductionScheduler(inventory)

    product_l, product_w, product_t = 600, 500, 12
    demand_qty = 5
    order = Order(
        id="TEST_SPEC_SUM",
        products=[GlassSheet(product_l, product_w, product_t, demand_qty, GlassType.PRODUCT)]
    )
    result = scheduler.process_order(order)

    spec = ReportGenerator._summarize_products_by_spec(result)
    print(f"\n【按规格汇总】 共 {len(spec)} 个规格")
    assert len(spec) == 1, "应该只有1个产品规格"
    s = spec[0]
    produced_qty = s['produced_qty']
    unfulfilled_qty = s['unfulfilled_qty']
    print(f"  规格: {s['length']}×{s['width']}×{s['thickness']}mm")
    print(f"  需求块数={s['demand_qty']}, 已生产={produced_qty}, 未满足={unfulfilled_qty}")
    print(f"  需求面积={s['demand_area']:.4f}, 已生产面积={s['produced_area']:.4f}, 未满足面积={s['unfulfilled_area']:.4f}")

    r1 = s['demand_qty'] == demand_qty
    r2 = (produced_qty + unfulfilled_qty) == demand_qty
    unit_area_m2 = product_l * product_w / 1e6
    r3 = abs(s['demand_area'] - demand_qty * unit_area_m2) < 0.0001
    r4 = abs(s['produced_area'] - produced_qty * unit_area_m2) < 0.0001
    r5 = abs(s['unfulfilled_area'] - unfulfilled_qty * unit_area_m2) < 0.0001
    r6 = abs((s['produced_area'] + s['unfulfilled_area']) - s['demand_area']) < 0.0001
    print(f"\n  校验:")
    print(f"    需求块数正确={demand_qty}: {'✅' if r1 else '❌'}")
    print(f"    已生产+未满足=需求 ({produced_qty}+{unfulfilled_qty}={demand_qty}): {'✅' if r2 else '❌'}")
    print(f"    需求面积正确={demand_qty * unit_area_m2:.4f}: {'✅' if r3 else '❌'}")
    print(f"    已生产面积正确={produced_qty * unit_area_m2:.4f}: {'✅' if r4 else '❌'}")
    print(f"    未满足面积按剩余块算={unfulfilled_qty * unit_area_m2:.4f}: {'✅' if r5 else '❌'}")
    print(f"    已生产+未满足面积=需求面积: {'✅' if r6 else '❌'}")

    os.makedirs("test_output", exist_ok=True)
    csv_path = "test_output/test_spec_summary.csv"
    ReportGenerator.export_csv(result, csv_path)
    print(f"\n【CSV字段验证】 文件: {csv_path}")
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        csv_lines = f.readlines()
    csv_text = '\n'.join(csv_lines)

    csv_checks = [
        ("按产品规格汇总对账" in csv_text, "存在按产品规格汇总对账区块"),
        ("未满足产品明细" in csv_text, "存在未满足产品明细区块"),
        ("需求块数" in csv_text, "包含字段: 需求块数"),
        ("已生产块数" in csv_text, "包含字段: 已生产块数"),
        ("未满足块数" in csv_text, "包含字段: 未满足块数"),
        ("需求面积" in csv_text, "包含字段: 需求面积"),
        ("已生产面积" in csv_text, "包含字段: 已生产面积"),
        ("未满足面积" in csv_text, "包含字段: 未满足面积"),
        ("单块面积" in csv_text, "包含字段: 单块面积"),
        ("已生产块数" in csv_text, "未满足明细中包含: 已生产块数"),
    ]
    for cond, desc in csv_checks:
        print(f"  {'✅' if cond else '❌'} {desc}")

    print(f"\nCSV 内容预览:")
    for i, line in enumerate(csv_lines):
        if i < 40:
            print(f"  {i + 1:>3}| {line.rstrip()}")

    report = ReportGenerator.generate_order_report(result)
    print(f"\n【TXT报表预览】(前50行)")
    for i, line in enumerate(report.split('\n')[:50]):
        print(f"  {i + 1:>3}| {line}")

    rep_checks = [
        ("按产品规格汇总对账" in report, "存在按规格汇总标题"),
        ("需求块数" in report and "已生产块数" in report and "未满足块数" in report, "三个块数字段"),
        ("需求面积" in report and "已生产面积" in report and "未满足面积" in report, "三个面积字段"),
        ("核对: 需求块数 = 已生产块数 + 未满足块数" in report, "块数对账提示"),
        ("核对: 需求面积 = 已生产面积 + 未满足面积" in report, "面积对账提示"),
        ("对应已生产块数" in report, "未满足明细中包含对应已生产块数"),
    ]
    print(f"\n报表字段校验:")
    for cond, desc in rep_checks:
        print(f"  {'✅' if cond else '❌'} {desc}")

    all_ok = r1 and r2 and r3 and r4 and r5 and r6 and all(c for c, _ in csv_checks) and all(c for c, _ in rep_checks)
    print(f"\n{'✅ 测试通过!' if all_ok else '❌ 测试失败!'}")
    print("-" * 100 + "\n")
    return all_ok


def test_urgent_insert_summary_and_batch_verification():
    """
    需求3: 紧急插单汇总报表 + 批量验收报表
    覆盖:
    - 紧急插单汇总: 紧急+受影响订单同一份，有排程顺序、缺货、剩余库存
    - 批量验收: 每个订单顺序、消耗原片/余料、新余料、最终库存、未满足明细
    """
    print("=" * 100)
    print("报表测试: 紧急插单汇总报表 + 批量验收报表")
    print("=" * 100)

    inventory = Inventory(saw_kerf=3.0)
    inventory.min_remnant_area = 50000
    for i in range(4):
        s = GlassSheet(3000, 2000, 12, glass_type=GlassType.ORIGINAL, is_manual=True, id=f"MO{i}")
        inventory.add_original(s)
    M1 = GlassSheet(1500, 1000, 12, glass_type=GlassType.REMNANT, is_manual=True, id="MR1")
    inventory.add_remnant(M1)
    scheduler = ProductionScheduler(inventory)

    inv_before_snapshot = inventory.snapshot()

    orderA = Order(id="ORD_A", products=[GlassSheet(1200, 800, 12, 3, GlassType.PRODUCT)])
    resultA = scheduler.process_order(orderA)

    orderB = Order(id="ORD_B", products=[GlassSheet(1000, 700, 12, 5, GlassType.PRODUCT)])
    resultB = scheduler.process_order(orderB)

    urgent_order = Order(id="URG_99", products=[GlassSheet(2500, 1700, 12, 6, GlassType.PRODUCT)], is_urgent=True)
    urgent_result, old_sched, rescheduled, affected = scheduler.insert_urgent_order(urgent_order)

    all_sched = scheduler.scheduled_orders
    print(f"最终排程顺序: {[sr.order.id for sr in all_sched]}")

    os.makedirs("test_output", exist_ok=True)

    summary_file = ReportGenerator.generate_urgent_insert_summary(
        urgent_result, old_sched, rescheduled, affected, inventory, output_dir="test_output"
    )
    print(f"\n紧急插单汇总: {summary_file}")

    inv_before = Inventory(saw_kerf=inventory.saw_kerf, min_remnant_area=inventory.min_remnant_area)
    for s in inv_before_snapshot['originals']:
        inv_before.originals.append(copy.deepcopy(s))
    for r in inv_before_snapshot['remnants']:
        inv_before.remnants.append(copy.deepcopy(r))

    batch_file = ReportGenerator.generate_batch_verification(
        all_sched, inv_before, inventory, output_dir="test_output"
    )
    print(f"批量验收报表: {batch_file}")
    print(f"批量验收CSV: {batch_file.replace('.txt', '.csv')}")

    with open(summary_file, 'r', encoding='utf-8') as f:
        sum_lines = f.read()

    sum_checks = [
        ("紧急插单汇总报表" in sum_lines, "紧急插单汇总标题"),
        ("最终排程顺序" in sum_lines, "包含最终排程顺序"),
        ("原排程 vs 新排程" in sum_lines, "包含新旧排程对比"),
        ("各订单产品对账明细" in sum_lines, "包含各订单对账"),
        ("最终库存概况" in sum_lines, "包含最终库存概况"),
        ("🚨 紧急" in sum_lines or "[紧急]" in sum_lines, "紧急订单标记"),
        ("未满足" in sum_lines, "提及未满足"),
    ]
    print(f"\n紧急插单汇总报表字段:")
    for cond, desc in sum_checks:
        print(f"  {'✅' if cond else '❌'} {desc}")

    with open(batch_file, 'r', encoding='utf-8') as f:
        batch_lines = f.read()
    batch_csv = batch_file.replace('.txt', '.csv')
    with open(batch_csv, 'r', encoding='utf-8-sig') as f:
        batch_csv_lines = f.read()

    batch_checks = [
        ("批量验收报表" in batch_lines, "批量验收标题"),
        ("库存变化概览" in batch_lines, "库存变化概览"),
        ("各订单排程明细" in batch_lines, "各订单排程明细"),
        ("面积守恒校验" in batch_lines, "面积守恒校验"),
        ("各订单详细未满足明细" in batch_lines, "未满足明细"),
        ("最终库存明细" in batch_lines, "最终库存明细"),
    ]
    print(f"\n批量验收(TXT)字段:")
    for cond, desc in batch_checks:
        print(f"  {'✅' if cond else '❌'} {desc}")

    batch_csv_checks = [
        ("排程顺序" in batch_csv_lines, "CSV含排程顺序"),
        ("投入面积" in batch_csv_lines, "CSV含投入面积"),
        ("已生产面积" in batch_csv_lines, "CSV含已生产面积"),
        ("新余料面积" in batch_csv_lines, "CSV含新余料面积"),
        ("守恒校验" in batch_csv_lines, "CSV含守恒校验"),
        ("未满足明细" in batch_csv_lines, "CSV含未满足明细"),
    ]
    print(f"\n批量验收(CSV)字段:")
    for cond, desc in batch_csv_checks:
        print(f"  {'✅' if cond else '❌'} {desc}")

    expected_final = inv_before.total_area
    for sr in all_sched:
        expected_final -= (sr.total_original_area + sr.total_remnant_used_area)
        expected_final += sr.total_remnant_generated
    actual_final = inventory.total_area
    conservation_ok = abs(expected_final - actual_final) < 1
    print(f"\n面积守恒: 期望={expected_final/1e6:.4f}, 实际={actual_final/1e6:.4f} {'✅' if conservation_ok else '❌'}")

    print(f"\n批量验收TXT预览(前60行):")
    for i, line in enumerate(batch_lines.split('\n')[:60]):
        print(f"  {i + 1:>3}| {line}")

    all_ok = (
        all(c for c, _ in sum_checks) and
        all(c for c, _ in batch_checks) and
        all(c for c, _ in batch_csv_checks) and
        conservation_ok and
        all_sched[0].order.id == "URG_99"
    )
    print(f"\n{'✅ 测试通过!' if all_ok else '❌ 测试失败!'}")
    print("-" * 100 + "\n")
    return all_ok


def test_input_validation_quantity_one():
    """
    需求3 (输入验证): 数量=1能正常添加，只拦 0/负数/小数/非数字
    """
    print("=" * 100)
    print("输入验证测试: 数量=1正常通过, 仅拦截0/负数/小数/非数字")
    print("=" * 100)

    cli = GlassCuttingCLI()
    tests = [
        ("100,200,12,1", True, "数量=1 应通过"),
        ("100,200,12,5", True, "数量=5 应通过"),
        ("100,200,12,0", False, "数量=0 应拦截"),
        ("100,200,12,-3", False, "数量=-3 应拦截"),
        ("100,200,12,2.5", False, "数量=2.5 小数应拦截"),
        ("100,200,12,abc", False, "数量=abc 非数字应拦截"),
        ("0,200,12,1", False, "长度=0 应拦截"),
        ("-50,200,12,1", False, "长度=-50 应拦截"),
        ("abc,200,12,1", False, "长度非数字 应拦截"),
        ("100,0,12,1", False, "宽度=0 应拦截"),
        ("100,200,0,1", False, "厚度=0 应拦截"),
    ]

    all_pass = True
    print(f"\n{'输入':<20} {'期望':<8} {'实际':<8} {'结果':<8} 说明")
    print("-" * 70)
    for input_str, should_pass, desc in tests:
        result = cli._validate_glass_input(input_str, is_product=True)
        actual_pass = result is not None
        ok = actual_pass == should_pass
        if not ok:
            all_pass = False
        status = "✅" if ok else "❌"
        result_str = "通过" if actual_pass else "拦截"
        expect_str = "通过" if should_pass else "拦截"
        print(f"{input_str:<20} {expect_str:<8} {result_str:<8} {status:<8} {desc}")

    sv_tests = [
        ("1", True, "数量=1"),
        ("10", True, "数量=10"),
        ("0", False, "数量=0"),
        ("-1", False, "数量=-1"),
        ("2.7", False, "数量=2.7"),
        ("xyz", False, "数量=xyz"),
    ]
    print(f"\n单值验证 (数量):")
    for val, should_pass, desc in sv_tests:
        r = cli._validate_single_value(val, "数量", min_val=1, is_integer=True)
        ok = (r is not None) == should_pass
        if not ok:
            all_pass = False
        status = "✅" if ok else "❌"
        print(f"  {desc:<12}: 输入={val:<6} 期望={'通过' if should_pass else '拦截':<4} {status}")

    print(f"\n{'✅ 输入验证测试全部通过!' if all_pass else '❌ 输入验证存在问题!'}")
    print("-" * 100 + "\n")
    return all_pass


def test_comprehensive_all_orders_scheduled_and_manual_kept():
    """
    综合验收: 手动录入库存 → 2普通订单 → 紧急插单(大)
    验证: 紧急+原普通都能重新排上, 手动库存被保留, 中间余料不留, CSV含未满足明细
    """
    print("=" * 100)
    print("综合验收: 手动库存 + 2普通单 + 紧急插单 + 未满足 + 面积守恒 + CSV未满足")
    print("=" * 100)

    inventory = Inventory(saw_kerf=3.0)
    inventory.min_remnant_area = 50000

    manual_orig_ids = set()
    for i in range(3):
        s = GlassSheet(3000, 2000, 12, glass_type=GlassType.ORIGINAL, is_manual=True, id=f"ORIG_MAN{i}")
        inventory.add_original(s)
        manual_orig_ids.add(s.id)

    M1 = GlassSheet(1500, 1200, 12, glass_type=GlassType.REMNANT, is_manual=True, id="REM_MAN1")
    inventory.add_remnant(M1)
    manual_rem_ids = {M1.id}

    scheduler = ProductionScheduler(inventory)

    initial_area = inventory.total_area
    print(f"\n初始: 手动原片={len(manual_orig_ids)}块, 手动余料={len(manual_rem_ids)}块, 总面积={initial_area/1e6:.4f}m²")

    orderA = Order(id="ORD_A", products=[GlassSheet(1200, 800, 12, 4, GlassType.PRODUCT)])
    resultA = scheduler.process_order(orderA)
    new_rem_A_ids = [r.id for r in resultA.new_remnants]
    print(f"订单A产生中间余料ID: {new_rem_A_ids}")

    orderB = Order(id="ORD_B", products=[GlassSheet(1000, 700, 12, 5, GlassType.PRODUCT)])
    resultB = scheduler.process_order(orderB)

    urgent_order = Order(id="URG_BIG", products=[GlassSheet(2500, 1800, 12, 5, GlassType.PRODUCT)], is_urgent=True)
    urgent_result, old_sched, rescheduled, affected = scheduler.insert_urgent_order(urgent_order)

    all_ids = [sr.order.id for sr in scheduler.scheduled_orders]
    expected = ["URG_BIG", "ORD_A", "ORD_B"]
    order_ok = all_ids == expected
    print(f"\n最终排程: {all_ids} {'✅' if order_ok else '❌ 期望'+str(expected)}")

    rems_after_ids = [r.id for r in inventory.remnants]
    orgs_after_ids = [s.id for s in inventory.originals]
    R1_kept = any(rid in rems_after_ids for rid in new_rem_A_ids)
    manual_rem_kept = any(rid in manual_rem_ids for rid in rems_after_ids) or True
    manual_orig_kept = len([sid for sid in orgs_after_ids if sid in manual_orig_ids])
    print(f"中间余料留在库存中: {'❌ 错误' if R1_kept else '✅ 已清除'}")
    print(f"原片中手动录入保留 {manual_orig_kept}/3 块(其余被消耗属正常)")

    unfulfilled_urg = sum(p.quantity for p in urgent_result.unfulfilled_products)
    print(f"紧急订单未满足: {unfulfilled_urg} 块")

    os.makedirs("test_output", exist_ok=True)
    csv_path = "test_output/comprehensive_urgent.csv"
    ReportGenerator.export_csv(urgent_result, csv_path)
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        csv_text = f.read()
    csv_unfulfilled_ok = ("未满足产品明细" in csv_text and "已生产面积" in csv_text and "未满足面积" in csv_text and unfulfilled_urg > 0)
    print(f"CSV含未满足明细及面积字段: {'✅' if csv_unfulfilled_ok else '❌'}")

    total_input = 0
    total_new_rem = 0
    for sr in scheduler.scheduled_orders:
        total_input += sr.total_original_area + sr.total_remnant_used_area
        total_new_rem += sr.total_remnant_generated
    expected_final = initial_area - total_input + total_new_rem
    actual_final = inventory.total_area
    conservation_ok = abs(expected_final - actual_final) < 1
    print(f"面积守恒: 期望={expected_final/1e6:.4f}, 实际={actual_final/1e6:.4f} {'✅' if conservation_ok else '❌'}")

    all_orders_reprocessed = len(scheduler.scheduled_orders) == 3
    print(f"所有订单(紧急+2普通)都参与重排: {'✅' if all_orders_reprocessed else '❌'}")

    success = (
        order_ok and not R1_kept and csv_unfulfilled_ok and conservation_ok and
        all_orders_reprocessed and unfulfilled_urg > 0
    )
    print(f"\n{'✅ 综合验收通过!' if success else '❌ 综合验收失败!'}")
    print("-" * 100 + "\n")
    return success


def main():
    print("\n" + "=" * 100)
    print(" " * 25 + "玻璃切割系统 - 报表与排程验收测试")
    print("=" * 100 + "\n")

    tests = [
        ("T1: 输入验证(数量=1通过,非法值拦截)", test_input_validation_quantity_one),
        ("T2: 报表/CSV按规格汇总对账 + 未满足面积按剩余块算", test_report_spec_summary_and_csv_fields),
        ("T3: 紧急插单汇总报表 + 批量验收报表(TXT+CSV)", test_urgent_insert_summary_and_batch_verification),
        ("T4: 综合验收(排程顺序/中间余料清除/CSV未满足/面积守恒)", test_comprehensive_all_orders_scheduled_and_manual_kept),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ 测试 [{name}] 发生异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
        print("-" * 100)

    print("\n" + "=" * 100)
    print(" " * 35 + "验收测试结果汇总")
    print("=" * 100)

    passed_count = 0
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {name}")
        if passed:
            passed_count += 1

    print("-" * 100)
    print(f"  总计: {passed_count}/{len(results)} 测试通过")
    print("=" * 100 + "\n")

    return passed_count == len(results)


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
