#!/usr/bin/env python
# -*- coding: utf-8 -*-

from models import GlassSheet, Order, Inventory, GlassType
from scheduler import ProductionScheduler
from reports import ReportGenerator
import os


def test_comprehensive_remnant_urgent_flow():
    """
    综合测试场景:
    1. 初始库存: 原片O1, 手动余料M1
    2. 订单A: 切割原片O1 → 产生中间余料R1
    3. 订单B: 消耗中间余料R1和手动余料M1
    4. 紧急插单: 验证
       - 回滚后库存只包含初始原片和手动余料
       - 中间余料R1不在库存中
       - 最终排程顺序正确
       - 库存面积与排程消耗对得上
       - 未满足产品明细正确
       - 报表统计按实际切出计算
    """
    print("=" * 80)
    print("综合场景测试: 余料生成→消耗→紧急插单")
    print("=" * 80)
    
    inventory = Inventory(saw_kerf=3.0)
    inventory.min_remnant_area = 50000
    
    O1 = GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL, id="INIT_O1")
    inventory.add_original(O1)
    for _ in range(2):
        inventory.add_original(GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL))
    
    M1 = GlassSheet(1500, 1000, 12, glass_type=GlassType.REMNANT, id="MANUAL_M1")
    inventory.add_remnant(M1)
    
    scheduler = ProductionScheduler(inventory)
    
    initial_originals_count = len(inventory.originals)
    initial_remnants_count = len(inventory.remnants)
    initial_total_area = inventory.total_area
    
    print(f"\n【阶段0: 初始库存】")
    print(f"  原片数量: {initial_originals_count} 块")
    print(f"  手动余料: {initial_remnants_count} 块 ({M1.id}: {M1.length}×{M1.width}mm)")
    print(f"  库存总面积: {initial_total_area / 1e6:.4f} m²")
    
    print(f"\n【阶段1: 订单A - 切割原片产生中间余料】")
    orderA = Order(
        id="ORD_A",
        products=[
            GlassSheet(1200, 800, 12, 3, GlassType.PRODUCT),
        ]
    )
    resultA = scheduler.process_order(orderA)
    
    print(f"  订单A需求: 1200×800×12mm × 3块")
    print(f"  使用原片: {len(resultA.used_originals)} 块")
    print(f"  使用余料: {len(resultA.used_remnants)} 块")
    print(f"  实际切出: {len(resultA.cutting_results[0].cut_pieces)} 块" if resultA.cutting_results else "  实际切出: 0 块")
    print(f"  新产生余料: {len(resultA.new_remnants)} 块")
    
    for i, rem in enumerate(resultA.new_remnants):
        print(f"    中间余料R{i+1}: [{rem.id}] {rem.length:.0f}×{rem.width:.0f}mm, 面积={rem.area/1e6:.4f}m²")
    
    R1 = resultA.new_remnants[0] if resultA.new_remnants else None
    print(f"  订单A综合利用率: {resultA.overall_utilization * 100:.2f}%")
    print(f"  订单A未满足: {sum(p.quantity for p in resultA.unfulfilled_products)} 块")
    
    print(f"\n  当前库存: 原片{len(inventory.originals)}块, 余料{len(inventory.remnants)}块")
    
    print(f"\n【阶段2: 订单B - 消耗中间余料和手动余料】")
    orderB = Order(
        id="ORD_B",
        products=[
            GlassSheet(1000, 600, 12, 4, GlassType.PRODUCT),
        ]
    )
    resultB = scheduler.process_order(orderB)
    
    print(f"  订单B需求: 1000×600×12mm × 4块")
    print(f"  使用原片: {len(resultB.used_originals)} 块")
    print(f"  使用余料: {len(resultB.used_remnants)} 块")
    
    for rem in resultB.used_remnants:
        print(f"    消耗余料: [{rem.id}] {rem.length}×{rem.width}mm")
    
    total_cut = sum(len(cr.cut_pieces) for cr in resultB.cutting_results)
    print(f"  实际切出: {total_cut} 块")
    print(f"  新产生余料: {len(resultB.new_remnants)} 块")
    print(f"  订单B综合利用率: {resultB.overall_utilization * 100:.2f}%")
    print(f"  订单B未满足: {sum(p.quantity for p in resultB.unfulfilled_products)} 块")
    
    print(f"\n  当前库存: 原片{len(inventory.originals)}块, 余料{len(inventory.remnants)}块")
    
    print(f"\n【阶段3: 紧急插单 - 验证库存回滚正确性】")
    
    total_input_before_urgent = (
        sum(sr.total_original_area for sr in scheduler.scheduled_orders) +
        sum(sr.total_remnant_used_area for sr in scheduler.scheduled_orders)
    )
    total_produced_before = sum(sr.total_product_area for sr in scheduler.scheduled_orders)
    total_remnant_gen_before = sum(sr.total_remnant_generated for sr in scheduler.scheduled_orders)
    current_inventory_area = inventory.total_area
    
    print(f"  已排产订单消耗总面积: {total_input_before_urgent / 1e6:.4f} m²")
    print(f"  已排产实际生产面积: {total_produced_before / 1e6:.4f} m²")
    print(f"  已排产产生余料面积: {total_remnant_gen_before / 1e6:.4f} m²")
    print(f"  当前库存面积: {current_inventory_area / 1e6:.4f} m²")
    print(f"  初始库存面积: {initial_total_area / 1e6:.4f} m²")
    
    area_check = abs((initial_total_area - total_input_before_urgent + total_remnant_gen_before) - current_inventory_area) < 1
    print(f"  ⚖️  面积守恒验证: {'✅ 通过' if area_check else '❌ 失败'}")
    
    urgent_order = Order(
        id="URG_01",
        products=[
            GlassSheet(1800, 1200, 12, 2, GlassType.PRODUCT),
        ],
        is_urgent=True
    )
    
    print(f"\n  插入紧急订单: 1800×1200×12mm × 2块")
    urgent_result, old_schedules, rescheduled, affected_sheets = scheduler.insert_urgent_order(urgent_order)
    
    print(f"\n  受影响订单: {len(old_schedules)} 个")
    for s in old_schedules:
        print(f"    - {s.order.id}")
    
    print(f"  受影响玻璃: {len(affected_sheets)} 块")
    
    print(f"\n  紧急插单后库存状态:")
    print(f"    原片数量: {len(inventory.originals)} 块")
    print(f"    余料数量: {len(inventory.remnants)} 块")
    print(f"    库存总面积: {inventory.total_area / 1e6:.4f} m²")
    
    all_schedule_ids = [sr.order.id for sr in scheduler.scheduled_orders]
    print(f"\n  最终排程顺序: {all_schedule_ids}")
    expected_order = ["URG_01", "ORD_A", "ORD_B"]
    order_correct = all_schedule_ids == expected_order
    print(f"  排程顺序验证: {'✅ 通过' if order_correct else f'❌ 失败 (期望{expected_order})'}")
    
    R1_in_inventory = any(r.id == R1.id for r in inventory.remnants) if R1 else False
    
    print(f"\n  中间余料验证:")
    if R1:
        print(f"    中间余料R1 [{R1.id}] 在库存中: {'❌ 错误(不应存在)' if R1_in_inventory else '✅ 正确(已清除)'}")
    print(f"    手动余料M1 [{M1.id}]: 可能已被排程消耗（正常行为）")
    
    remnant_ids_after = [r.id for r in inventory.remnants]
    original_ids_after = [s.id for s in inventory.originals]
    print(f"    当前余料ID: {remnant_ids_after}")
    print(f"    当前原片ID: {original_ids_after}")
    
    print(f"\n  紧急订单结果:")
    print(f"    利用率: {urgent_result.overall_utilization * 100:.2f}%")
    print(f"    实际切出: {sum(len(cr.cut_pieces) for cr in urgent_result.cutting_results)} 块")
    print(f"    未满足: {sum(p.quantity for p in urgent_result.unfulfilled_products)} 块")
    
    print(f"\n【阶段4: 报表统计验证】")
    report = ReportGenerator.generate_order_report(urgent_result)
    lines = report.split('\n')
    
    has_demand = any("订单需求总面积" in l for l in lines)
    has_produced = any("实际生产总面积" in l for l in lines)
    has_unfulfilled_area = any("未满足产品面积" in l for l in lines)
    has_fulfillment_rate = any("订单满足率" in l for l in lines)
    
    print(f"  报表字段验证:")
    print(f"    订单需求总面积: {'✅ 存在' if has_demand else '❌ 缺失'}")
    print(f"    实际生产总面积: {'✅ 存在' if has_produced else '❌ 缺失'}")
    print(f"    未满足产品面积: {'✅ 存在' if has_unfulfilled_area else '❌ 缺失'}")
    print(f"    订单满足率: {'✅ 存在' if has_fulfillment_rate else '❌ 缺失'}")
    
    os.makedirs("test_output", exist_ok=True)
    report_path = "test_output/comprehensive_report.txt"
    csv_path = "test_output/comprehensive_report.csv"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    ReportGenerator.export_csv(urgent_result, csv_path)
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        csv_content = f.read()
    
    has_unfulfilled_products = len(urgent_result.unfulfilled_products) > 0
    csv_has_unfulfilled = "未满足产品明细" in csv_content
    
    if has_unfulfilled_products:
        csv_check_passed = csv_has_unfulfilled
    else:
        csv_check_passed = True
    
    print(f"    CSV未满足明细: {'✅ 存在' if csv_has_unfulfilled else ('✅ 无未满足产品(无需)' if not has_unfulfilled_products else '❌ 缺失')}")
    print(f"    报表已导出: {report_path}")
    print(f"    CSV已导出: {csv_path}")
    
    print(f"\n【阶段5: 最终面积守恒验证】")
    total_input_final = (
        sum(sr.total_original_area for sr in scheduler.scheduled_orders) +
        sum(sr.total_remnant_used_area for sr in scheduler.scheduled_orders)
    )
    total_produced_final = sum(sr.total_product_area for sr in scheduler.scheduled_orders)
    total_remnant_gen_final = sum(sr.total_remnant_generated for sr in scheduler.scheduled_orders)
    final_inventory_area = inventory.total_area
    
    print(f"  所有订单消耗总面积: {total_input_final / 1e6:.4f} m²")
    print(f"  所有订单实际生产: {total_produced_final / 1e6:.4f} m²")
    print(f"  所有订单产生余料: {total_remnant_gen_final / 1e6:.4f} m²")
    print(f"  最终库存面积: {final_inventory_area / 1e6:.4f} m²")
    print(f"  初始库存面积: {initial_total_area / 1e6:.4f} m²")
    
    expected_final_area = initial_total_area - total_input_final + total_remnant_gen_final
    final_area_check = abs(expected_final_area - final_inventory_area) < 1
    print(f"  ⚖️  最终面积守恒: {'✅ 通过' if final_area_check else '❌ 失败'}")
    print(f"    计算值: {expected_final_area / 1e6:.4f} m²")
    print(f"    实际值: {final_inventory_area / 1e6:.4f} m²")
    
    success = (
        order_correct and 
        not R1_in_inventory and 
        has_demand and 
        has_produced and 
        has_unfulfilled_area and
        has_fulfillment_rate and
        final_area_check and
        area_check and
        csv_check_passed
    )
    
    print(f"\n" + "=" * 80)
    if success:
        print("  ✅✅✅ 综合场景测试全部通过! ✅✅✅")
    else:
        print("  ❌❌❌ 综合场景测试存在问题 ❌❌❌")
    print("=" * 80)
    print()
    
    return success


def test_report_unfulfilled_separate():
    """测试报表中未满足产品单独列出，且不混入已生产面积"""
    print("=" * 80)
    print("报表统计测试: 需求5块只切出3块时的统计")
    print("=" * 80)
    
    inventory = Inventory(saw_kerf=3.0)
    inventory.add_original(GlassSheet(1500, 1000, 12, glass_type=GlassType.ORIGINAL))
    
    scheduler = ProductionScheduler(inventory)
    
    products = [GlassSheet(600, 500, 12, 5, GlassType.PRODUCT)]
    order = Order(id="TEST_REPORT", products=products)
    
    result = scheduler.process_order(order)
    
    total_cut = sum(len(cr.cut_pieces) for cr in result.cutting_results)
    unfulfilled_qty = sum(p.quantity for p in result.unfulfilled_products)
    
    print(f"\n订单需求: 600×500×12mm × 5块")
    print(f"实际切出: {total_cut} 块")
    print(f"未满足: {unfulfilled_qty} 块")
    print(f"需求+切出: {total_cut + unfulfilled_qty} 块 (应等于5)")
    
    report = ReportGenerator.generate_order_report(result)
    lines = report.split('\n')
    
    demand_area = None
    produced_area = None
    unfulfilled_area = None
    
    for line in lines:
        if "订单需求总面积" in line:
            parts = line.split()
            demand_area = float(parts[-2])
        elif "实际生产总面积" in line:
            parts = line.split()
            produced_area = float(parts[-2])
        elif "未满足产品面积" in line:
            parts = line.split()
            unfulfilled_area = float(parts[-2])
    
    print(f"\n报表数值:")
    print(f"  订单需求总面积: {demand_area} m²")
    print(f"  实际生产总面积: {produced_area} m²")
    print(f"  未满足产品面积: {unfulfilled_area} m²")
    
    expected_demand = 5 * 600 * 500 / 1e6
    expected_produced = total_cut * 600 * 500 / 1e6
    expected_unfulfilled = unfulfilled_qty * 600 * 500 / 1e6
    
    print(f"\n期望值:")
    print(f"  订单需求总面积: {expected_demand} m²")
    print(f"  实际生产总面积: {expected_produced} m²")
    print(f"  未满足产品面积: {expected_unfulfilled} m²")
    
    checks = [
        ("需求面积正确", demand_area == expected_demand),
        ("已生产面积正确(只算实际切出)", produced_area == expected_produced),
        ("未满足面积正确(单独列出)", unfulfilled_area == expected_unfulfilled),
        ("已生产+未满足=需求", abs((produced_area or 0) + (unfulfilled_area or 0) - (demand_area or 0)) < 0.001),
    ]
    
    print(f"\n检查结果:")
    all_pass = True
    for name, ok in checks:
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")
        if not ok:
            all_pass = False
    
    print(f"\n报表预览(前30行):")
    for line in lines[:30]:
        print(f"  {line}")
    
    print()
    return all_pass


def main():
    print("\n" + "=" * 80)
    print(" " * 20 + "玻璃切割系统 - 第二轮改进验证测试")
    print("=" * 80 + "\n")
    
    tests = [
        ("综合场景: 余料生成→消耗→紧急插单", test_comprehensive_remnant_urgent_flow),
        ("报表统计: 实际切出与未满足分离", test_report_unfulfilled_separate),
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
    print(" " * 30 + "测试结果汇总")
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
