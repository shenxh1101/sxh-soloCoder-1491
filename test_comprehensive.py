#!/usr/bin/env python
# -*- coding: utf-8 -*-

from models import GlassSheet, Order, Inventory, GlassType
from scheduler import ProductionScheduler
from reports import ReportGenerator
from cli import GlassCuttingCLI
import os


def test_urgent_with_unfulfilled_and_manual_inventory():
    """
    综合场景测试（覆盖用户4项需求）:
    1. 手动录入原片+手动余料作为初始库存
    2. 订单A: 切割产生中间余料R1
    3. 订单B: 消耗中间余料R1
    4. 紧急插单(故意设置过大，确保有未满足产品):
       - 验证手动录入的库存保留，只有被消耗的才不在
       - 中间余料R1不留在库存
       - 排程顺序 [紧急, 原A, 原B]
       - 紧急订单有未满足产品，CSV有未满足明细
       - 面积守恒
    """
    print("=" * 80)
    print("综合测试: 手动录入库存 + 紧急插单有未满足 + 面积守恒 + CSV未满足明细")
    print("=" * 80)

    inventory = Inventory(saw_kerf=3.0)
    inventory.min_remnant_area = 50000

    orig1 = GlassSheet(3000, 2000, 12, glass_type=GlassType.ORIGINAL, is_manual=True, id="MAN_ORIG1")
    orig2 = GlassSheet(3000, 2000, 12, glass_type=GlassType.ORIGINAL, is_manual=True, id="MAN_ORIG2")
    orig3 = GlassSheet(3000, 2000, 12, glass_type=GlassType.ORIGINAL, is_manual=True, id="MAN_ORIG3")
    inventory.add_original(orig1)
    inventory.add_original(orig2)
    inventory.add_original(orig3)
    manual_orig_ids = {orig1.id, orig2.id, orig3.id}

    M1 = GlassSheet(1500, 1200, 12, glass_type=GlassType.REMNANT, is_manual=True, id="MAN_REM1")
    inventory.add_remnant(M1)
    manual_rem_ids = {M1.id}

    scheduler = ProductionScheduler(inventory)

    initial_total_area = inventory.total_area
    print(f"\n【阶段0: 初始库存(全部手动录入)】")
    print(f"  手动原片: {len(manual_orig_ids)} 块, ID={manual_orig_ids}")
    print(f"  手动余料: {len(manual_rem_ids)} 块, ID={manual_rem_ids}")
    print(f"  库存总面积: {initial_total_area / 1e6:.4f} m²")

    print(f"\n【阶段1: 订单A - 切割产生中间余料】")
    orderA = Order(id="ORD_A", products=[GlassSheet(1200, 800, 12, 4, GlassType.PRODUCT)])
    resultA = scheduler.process_order(orderA)
    total_cut_A = sum(len(cr.cut_pieces) for cr in resultA.cutting_results)
    unfulfilled_A = sum(p.quantity for p in resultA.unfulfilled_products)
    print(f"  订单A: 1200×800×12mm × 4块")
    print(f"    实际切出: {total_cut_A}, 未满足: {unfulfilled_A}, 新产生余料: {len(resultA.new_remnants)}")

    R_list = [r for r in resultA.new_remnants]
    for i, r in enumerate(R_list):
        print(f"    R{i+1}: [{r.id}] {r.length:.0f}×{r.width:.0f}mm, is_manual={r.is_manual}")

    print(f"\n【阶段2: 订单B - 消耗中间余料】")
    orderB = Order(id="ORD_B", products=[GlassSheet(1000, 700, 12, 5, GlassType.PRODUCT)])
    resultB = scheduler.process_order(orderB)
    total_cut_B = sum(len(cr.cut_pieces) for cr in resultB.cutting_results)
    unfulfilled_B = sum(p.quantity for p in resultB.unfulfilled_products)
    print(f"  订单B: 1000×700×12mm × 5块")
    print(f"    实际切出: {total_cut_B}, 未满足: {unfulfilled_B}")
    print(f"    使用余料: {len(resultB.used_remnants)} 块")
    for r in resultB.used_remnants:
        print(f"      - [{r.id}] {r.length:.0f}×{r.width:.0f}mm")

    current_area = inventory.total_area
    consumed_so_far = (
        (resultA.total_original_area + resultA.total_remnant_used_area) +
        (resultB.total_original_area + resultB.total_remnant_used_area)
    )
    new_rem_so_far = resultA.total_remnant_generated + resultB.total_remnant_generated
    area_ok1 = abs(initial_total_area - consumed_so_far + new_rem_so_far - current_area) < 1
    print(f"\n  当前库存面积: {current_area / 1e6:.4f} m², 面积守恒: {'✅' if area_ok1 else '❌'}")

    print(f"\n【阶段3: 紧急插单(故意设大，确保有未满足)】")
    urgent_order = Order(id="URG_01", products=[GlassSheet(2500, 1800, 12, 5, GlassType.PRODUCT)], is_urgent=True)
    print(f"  紧急订单: 2500×1800×12mm × 5块 (库存原片只有3块，肯定无法全部满足)")

    urgent_result, old_schedules, rescheduled, affected = scheduler.insert_urgent_order(urgent_order)

    total_cut_urg = sum(len(cr.cut_pieces) for cr in urgent_result.cutting_results)
    unfulfilled_urg = sum(p.quantity for p in urgent_result.unfulfilled_products)
    print(f"  紧急订单结果: 切出={total_cut_urg}, 未满足={unfulfilled_urg}")

    all_ids = [sr.order.id for sr in scheduler.scheduled_orders]
    expected_order = ["URG_01", "ORD_A", "ORD_B"]
    order_ok = all_ids == expected_order
    print(f"\n  最终排程: {all_ids} {'✅ 正确' if order_ok else '❌ 错误(期望'+str(expected_order)+')'}")

    rems_after = [r for r in inventory.remnants]
    orgs_after = [s for s in inventory.originals]
    print(f"\n  紧急插单后库存: 原片={len(orgs_after)}块, 余料={len(rems_after)}块")
    manual_orig_kept = [s.id for s in orgs_after if s.id in manual_orig_ids]
    print(f"    原片中手动录入保留的: {manual_orig_kept} ({len(manual_orig_kept)}块, 其余被消耗属正常)")

    R1_remaining = any(r.id == R_list[0].id for r in rems_after) if R_list else False
    print(f"    中间余料R1 [{R_list[0].id if R_list else 'N/A'}] 留在库存中: {'❌ 错误' if R1_remaining else '✅ 正确(已清除)'}")

    print(f"\n  紧急订单未满足明细:")
    for p in urgent_result.unfulfilled_products:
        print(f"    - {p.length}×{p.width}×{p.thickness}mm × {p.quantity}块")

    os.makedirs("test_output", exist_ok=True)
    report_path = "test_output/urgent_unfulfilled_report.txt"
    csv_path = "test_output/urgent_unfulfilled_report.csv"
    report = ReportGenerator.generate_order_report(urgent_result)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    ReportGenerator.export_csv(urgent_result, csv_path)

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        csv_content = f.read()
    csv_has_unfulfilled = "未满足产品明细" in csv_content
    print(f"\n  CSV 包含未满足明细: {'✅' if csv_has_unfulfilled else '❌'}")
    print(f"  报表: {report_path}, CSV: {csv_path}")

    lines = report.split('\n')
    has_demand = any("订单需求总面积" in l for l in lines)
    has_produced = any("实际生产总面积" in l for l in lines)
    has_unful_area = any("未满足产品面积" in l for l in lines)
    has_rate = any("订单满足率" in l for l in lines)
    print(f"  报表字段: 需求面积={'✅' if has_demand else '❌'}, 已生产面积={'✅' if has_produced else '❌'}, 未满足面积={'✅' if has_unful_area else '❌'}, 满足率={'✅' if has_rate else '❌'}")

    print(f"\n【阶段4: 最终面积守恒 + 订单都能排上】")
    total_consumed_all = 0
    total_new_rem_all = 0
    all_rescheduled_ok = True
    for sr in scheduler.scheduled_orders:
        consumed = sr.total_original_area + sr.total_remnant_used_area
        produced = sr.total_product_area
        new_rem = sr.total_remnant_generated
        unful = sum(p.quantity for p in sr.unfulfilled_products)
        total_consumed_all += consumed
        total_new_rem_all += new_rem
        print(f"  {sr.order.id}: 消耗={consumed/1e6:.4f}m², 生产={produced/1e6:.4f}m², 新余料={new_rem/1e6:.4f}m², 未满足={unful}块")

    final_area = inventory.total_area
    expected_final = initial_total_area - total_consumed_all + total_new_rem_all
    final_ok = abs(expected_final - final_area) < 1
    print(f"\n  初始={initial_total_area/1e6:.4f}, 总消耗={total_consumed_all/1e6:.4f}, 总新余料={total_new_rem_all/1e6:.4f}")
    print(f"  预期最终={expected_final/1e6:.4f}, 实际最终={final_area/1e6:.4f}")
    print(f"  面积守恒: {'✅ 通过' if final_ok else '❌ 失败'}")

    success = (
        order_ok and
        not R1_remaining and
        csv_has_unfulfilled and
        has_demand and has_produced and has_unful_area and has_rate and
        final_ok and
        area_ok1 and
        unfulfilled_urg > 0
    )

    print(f"\n" + "=" * 80)
    if success:
        print("  ✅✅✅ 综合场景测试全部通过! ✅✅✅")
    else:
        print("  ❌❌❌ 综合场景测试存在问题 ❌❌❌")
    print("=" * 80 + "\n")
    return success


def test_report_quantity_area_consistency():
    """
    需求2: 订单需求5块只切出3块时，
    - 未满足面积按剩下的2块算
    - 未满足数量 + 已生产数量 = 需求数量
    - 未满足面积 + 已生产面积 = 需求面积
    """
    print("=" * 80)
    print("报表测试: 需求5块只切出X块，数量/面积加起来等于需求")
    print("=" * 80)

    inventory = Inventory(saw_kerf=3.0)
    inventory.add_original(GlassSheet(1500, 1000, 12, glass_type=GlassType.ORIGINAL, is_manual=True))

    scheduler = ProductionScheduler(inventory)

    demand_qty = 5
    product_l, product_w, product_t = 600, 500, 12
    order = Order(
        id="TEST_QTY_AREA",
        products=[GlassSheet(product_l, product_w, product_t, demand_qty, GlassType.PRODUCT)]
    )
    result = scheduler.process_order(order)

    produced_qty = sum(len(cr.cut_pieces) for cr in result.cutting_results)
    unfulfilled_qty = sum(p.quantity for p in result.unfulfilled_products)
    print(f"\n订单需求: {product_l}×{product_w}×{product_t}mm × {demand_qty}块")
    print(f"实际切出: {produced_qty} 块")
    print(f"未满足: {unfulfilled_qty} 块")

    qty_sum_ok = (produced_qty + unfulfilled_qty) == demand_qty
    print(f"切出+未满足={produced_qty + unfulfilled_qty} == 需求={demand_qty} : {'✅' if qty_sum_ok else '❌'}")

    unit_area = product_l * product_w
    demand_area = demand_qty * unit_area / 1e6
    produced_area = produced_qty * unit_area / 1e6
    unfulfilled_area = unfulfilled_qty * unit_area / 1e6
    print(f"\n单块面积: {unit_area} mm² = {unit_area / 1e6:.4f} m²")
    print(f"需求总面积: {demand_area:.4f} m²")
    print(f"已生产面积: {produced_area:.4f} m²")
    print(f"未满足面积: {unfulfilled_area:.4f} m²")

    area_sum_ok = abs(produced_area + unfulfilled_area - demand_area) < 0.0001
    print(f"已生产+未满足={produced_area + unfulfilled_area:.4f} == 需求={demand_area:.4f} : {'✅' if area_sum_ok else '❌'}")

    report = ReportGenerator.generate_order_report(result)
    lines = report.split('\n')
    rep_demand = rep_produced = rep_unfulfilled = None
    for line in lines:
        if "订单需求总面积" in line:
            parts = line.split()
            rep_demand = float(parts[-2])
        elif "实际生产总面积" in line:
            parts = line.split()
            rep_produced = float(parts[-2])
        elif "未满足产品面积" in line:
            parts = line.split()
            rep_unfulfilled = float(parts[-2])

    print(f"\n报表数值验证:")
    r1 = abs(rep_demand - demand_area) < 0.0001 if rep_demand else False
    r2 = abs(rep_produced - produced_area) < 0.0001 if rep_produced else False
    r3 = abs(rep_unfulfilled - unfulfilled_area) < 0.0001 if rep_unfulfilled else False
    print(f"  需求面积: 报表={rep_demand}, 期望={demand_area:.4f} {'✅' if r1 else '❌'}")
    print(f"  已生产:   报表={rep_produced}, 期望={produced_area:.4f} {'✅' if r2 else '❌'}")
    print(f"  未满足:   报表={rep_unfulfilled}, 期望={unfulfilled_area:.4f} {'✅' if r3 else '❌'}")

    print(f"\n报表预览(前35行):")
    for l in lines[:35]:
        print(f"  {l}")

    success = qty_sum_ok and area_sum_ok and r1 and r2 and r3
    print(f"\n{'✅ 测试通过!' if success else '❌ 测试失败!'}")
    print("-" * 80 + "\n")
    return success


def test_input_validation_quantity_one():
    """
    需求3: 数量=1能正常添加，只拦截0/负数/小数/非数字
    同时验证余料和订单产品录入
    """
    print("=" * 80)
    print("输入验证测试: 数量=1正常通过, 仅拦截0/负数/小数/非数字")
    print("=" * 80)

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

    print(f"\n单值验证 (数量):")
    sv_tests = [
        ("1", True, "数量=1"),
        ("10", True, "数量=10"),
        ("0", False, "数量=0"),
        ("-1", False, "数量=-1"),
        ("2.7", False, "数量=2.7"),
        ("xyz", False, "数量=xyz"),
    ]
    for val, should_pass, desc in sv_tests:
        r = cli._validate_single_value(val, "数量", min_val=1, is_integer=True)
        ok = (r is not None) == should_pass
        if not ok:
            all_pass = False
        status = "✅" if ok else "❌"
        print(f"  {desc:<12}: 输入={val:<6} 期望={'通过' if should_pass else '拦截':<4} {status}")

    print(f"\n{'✅ 输入验证测试全部通过!' if all_pass else '❌ 输入验证存在问题!'}")
    print("-" * 80 + "\n")
    return all_pass


def test_urgent_keeps_manual_unused():
    """
    需求1补充: 手动录入的库存中，没被消耗的原片/余料必须保留
    使用超大库存 + 很小订单，紧急插单后仍有大量剩余库存
    """
    print("=" * 80)
    print("库存保留测试: 紧急插单后未被消耗的手动库存应保留")
    print("=" * 80)

    inventory = Inventory(saw_kerf=3.0)

    orig_ids = set()
    for i in range(10):
        s = GlassSheet(3000, 2000, 12, glass_type=GlassType.ORIGINAL, is_manual=True, id=f"MO{i}")
        inventory.add_original(s)
        orig_ids.add(s.id)

    rem_ids = set()
    for i in range(3):
        r = GlassSheet(1000 + i * 100, 800, 12, glass_type=GlassType.REMNANT, is_manual=True, id=f"MR{i}")
        inventory.add_remnant(r)
        rem_ids.add(r.id)

    initial_area = inventory.total_area
    print(f"\n初始: 手动原片={len(orig_ids)}块, 手动余料={len(rem_ids)}块, 总面积={initial_area/1e6:.4f}m²")

    scheduler = ProductionScheduler(inventory)

    orderA = Order(id="ORD_A", products=[GlassSheet(1200, 800, 12, 2, GlassType.PRODUCT)])
    scheduler.process_order(orderA)
    orderB = Order(id="ORD_B", products=[GlassSheet(600, 500, 12, 3, GlassType.PRODUCT)])
    scheduler.process_order(orderB)

    print(f"排完A+B后: 原片剩余={len(inventory.originals)}, 余料剩余={len(inventory.remnants)}")

    urgent = Order(id="URG_X", products=[GlassSheet(1500, 1000, 12, 1, GlassType.PRODUCT)], is_urgent=True)
    scheduler.insert_urgent_order(urgent)

    final_orig = set(s.id for s in inventory.originals)
    final_rem = set(r.id for r in inventory.remnants)

    manual_orig_kept = final_orig & orig_ids
    manual_rem_kept = final_rem & rem_ids
    total_kept = len(manual_orig_kept) + len(manual_rem_kept)

    print(f"\n紧急插单后:")
    print(f"  原片剩余={len(inventory.originals)}块, 其中手动录入保留 {len(manual_orig_kept)} 块")
    print(f"  余料剩余={len(inventory.remnants)}块, 其中手动录入保留 {len(manual_rem_kept)} 块")

    print(f"\n  所有最终原片ID: {sorted(final_orig)}")
    print(f"  所有最终余料ID: {sorted(final_rem)}")

    schedule_ids = [sr.order.id for sr in scheduler.scheduled_orders]
    print(f"  最终排程: {schedule_ids}")

    all_processed_ok = all(
        sum(p.quantity for p in sr.unfulfilled_products) == 0 or True
        for sr in scheduler.scheduled_orders
    )
    print(f"  所有订单都参与重排: {'✅' if len(schedule_ids) == 3 else '❌'}")

    expected_final = initial_area
    for sr in scheduler.scheduled_orders:
        expected_final -= (sr.total_original_area + sr.total_remnant_used_area)
        expected_final += sr.total_remnant_generated
    actual_final = inventory.total_area
    area_ok = abs(expected_final - actual_final) < 1
    print(f"  最终面积: 期望={expected_final/1e6:.4f}, 实际={actual_final/1e6:.4f}, 守恒={'✅' if area_ok else '❌'}")

    success = (
        len(schedule_ids) == 3 and
        total_kept > 0 and
        area_ok and
        len(manual_orig_kept) >= 7 and
        schedule_ids[0] == "URG_X"
    )

    print(f"\n{'✅ 库存保留测试通过!' if success else '❌ 库存保留测试失败!'}")
    print("-" * 80 + "\n")
    return success


def main():
    print("\n" + "=" * 80)
    print(" " * 20 + "玻璃切割系统 - 最终验收测试")
    print("=" * 80 + "\n")

    tests = [
        ("T1: 输入验证(数量=1通过,非法值拦截)", test_input_validation_quantity_one),
        ("T2: 报表数量/面积加总等于需求", test_report_quantity_area_consistency),
        ("T3: 紧急插单保留手动库存(未消耗部分)", test_urgent_keeps_manual_unused),
        ("T4: 紧急插单有未满足+CSV明细+面积守恒", test_urgent_with_unfulfilled_and_manual_inventory),
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
        print("-" * 80)

    print("\n" + "=" * 80)
    print(" " * 35 + "验收测试结果汇总")
    print("=" * 80)

    passed_count = 0
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {name}")
        if passed:
            passed_count += 1

    print("-" * 80)
    print(f"  总计: {passed_count}/{len(results)} 测试通过")
    print("=" * 80 + "\n")

    return passed_count == len(results)


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
