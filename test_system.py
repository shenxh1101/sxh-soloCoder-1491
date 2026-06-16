#!/usr/bin/env python
# -*- coding: utf-8 -*-

from models import GlassSheet, Order, Inventory, GlassType
from cutting_algorithm import LowestHorizontalLineAlgorithm, find_best_packing
from scheduler import ProductionScheduler, RemnantMatcher
from visualization import CuttingDiagram
from reports import ReportGenerator
import os


def test_cutting_algorithm():
    print("=" * 60)
    print("测试1: 切割算法验证")
    print("=" * 60)
    
    sheet = GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL)
    
    pieces = [
        GlassSheet(1200, 800, 12, 3, GlassType.PRODUCT),
        GlassSheet(1000, 600, 12, 4, GlassType.PRODUCT),
        GlassSheet(800, 600, 12, 5, GlassType.PRODUCT),
    ]
    
    algo = LowestHorizontalLineAlgorithm(saw_kerf=3.0)
    result = algo.pack(sheet, pieces)
    
    print(f"\n原片尺寸: {sheet.length}×{sheet.width}×{sheet.thickness}mm")
    print(f"原片面积: {sheet.area:.0f} mm²")
    print(f"切割产品数: {len(result.cut_pieces)} 块")
    print(f"产生余料数: {len(result.remnants)} 块")
    print(f"利用率: {result.utilization_rate * 100:.2f}%")
    print()
    
    print("切割产品列表:")
    for i, p in enumerate(result.cut_pieces):
        print(f"  {i+1}. {p.length}×{p.width}mm 位置:({p.x:.0f},{p.y:.0f}) 面积:{p.area:.0f}mm²")
    
    print("\n余料列表:")
    for i, r in enumerate(result.remnants):
        print(f"  R{i+1}. {r.length:.0f}×{r.width:.0f}mm 位置:({r.x:.0f},{r.y:.0f}) 面积:{r.area:.0f}mm²")
    
    print("\n切割图纸(字符画):")
    print(CuttingDiagram.generate_ascii(result, scale=0.03))
    print()
    
    return result.utilization_rate > 0.5


def test_remnant_matching():
    print("=" * 60)
    print("测试2: 余料优先匹配验证")
    print("=" * 60)
    
    inventory = Inventory(saw_kerf=3.0)
    
    remnants = [
        GlassSheet(1500, 1200, 12, glass_type=GlassType.REMNANT),
        GlassSheet(1000, 800, 12, glass_type=GlassType.REMNANT),
        GlassSheet(1800, 1000, 8, glass_type=GlassType.REMNANT),
    ]
    
    for rem in remnants:
        inventory.add_remnant(rem)
    
    originals = [
        GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL),
        GlassSheet(2440, 1830, 8, glass_type=GlassType.ORIGINAL),
    ]
    
    for sheet in originals:
        inventory.add_original(sheet)
    
    print(f"\n库存状态:")
    print(f"  原片: {len(inventory.originals)} 块")
    print(f"  余料: {len(inventory.remnants)} 块")
    
    products = [
        GlassSheet(900, 700, 12, 2, GlassType.PRODUCT),
        GlassSheet(1200, 800, 8, 1, GlassType.PRODUCT),
    ]
    
    matcher = RemnantMatcher(saw_kerf=3.0)
    remnants_available, _ = inventory.get_available_sheets(12.0)
    
    best_rem = matcher.find_best_remnant(products[0], remnants_available)
    
    print(f"\n产品: {products[0].length}×{products[0].width}×{products[0].thickness}mm")
    if best_rem:
        print(f"匹配到最佳余料: {best_rem.length}×{best_rem.width}mm")
        result = find_best_packing(best_rem, [products[0]], 3.0)
        print(f"切割利用率: {result.utilization_rate * 100:.2f}%")
        success = True
    else:
        print("未找到匹配的余料")
        success = False
    
    print()
    return success


def test_scheduler():
    print("=" * 60)
    print("测试3: 完整排产流程验证")
    print("=" * 60)
    
    inventory = Inventory(saw_kerf=3.0)
    
    for _ in range(5):
        inventory.add_original(GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL))
    
    for _ in range(3):
        inventory.add_original(GlassSheet(2440, 1830, 8, glass_type=GlassType.ORIGINAL))
    
    inventory.add_remnant(GlassSheet(1500, 1200, 12, glass_type=GlassType.REMNANT))
    
    scheduler = ProductionScheduler(inventory)
    
    products1 = [
        GlassSheet(1200, 800, 12, 5, GlassType.PRODUCT),
        GlassSheet(1000, 600, 12, 6, GlassType.PRODUCT),
        GlassSheet(1500, 1000, 12, 2, GlassType.PRODUCT),
    ]
    order1 = Order(id="ORD001", products=products1)
    
    products2 = [
        GlassSheet(800, 600, 8, 10, GlassType.PRODUCT),
        GlassSheet(1200, 500, 8, 4, GlassType.PRODUCT),
    ]
    order2 = Order(id="ORD002", products=products2)
    
    print(f"\n处理订单 ORD001...")
    result1 = scheduler.process_order(order1)
    
    print(f"  使用原片: {len(result1.used_originals)} 块")
    print(f"  使用余料: {len(result1.used_remnants)} 块")
    print(f"  新产生余料: {len(result1.new_remnants)} 块")
    print(f"  综合利用率: {result1.overall_utilization * 100:.2f}%")
    
    if result1.unfulfilled_products:
        print(f"  ⚠️  未满足产品: {[(p.length, p.width, p.quantity) for p in result1.unfulfilled_products]}")
    
    print(f"\n处理订单 ORD002...")
    result2 = scheduler.process_order(order2)
    
    print(f"  使用原片: {len(result2.used_originals)} 块")
    print(f"  使用余料: {len(result2.used_remnants)} 块")
    print(f"  新产生余料: {len(result2.new_remnants)} 块")
    print(f"  综合利用率: {result2.overall_utilization * 100:.2f}%")
    
    print(f"\n当前余料库存: {len(inventory.remnants)} 块")
    
    summary = scheduler.get_schedule_summary()
    print(f"\n排产总结:")
    print(f"  订单总数: {summary['orders_count']}")
    print(f"  总产品面积: {summary['total_product_area'] / 1e6:.4f} m²")
    print(f"  综合利用率: {summary['overall_utilization'] * 100:.2f}%")
    
    success = len(result1.cutting_results) > 0 and len(result2.cutting_results) > 0
    print()
    return success


def test_urgent_insert():
    print("=" * 60)
    print("测试4: 紧急插单功能验证")
    print("=" * 60)
    
    inventory = Inventory(saw_kerf=3.0)
    
    for _ in range(3):
        inventory.add_original(GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL))
    
    scheduler = ProductionScheduler(inventory)
    
    products1 = [
        GlassSheet(1200, 800, 12, 8, GlassType.PRODUCT),
        GlassSheet(1000, 600, 12, 10, GlassType.PRODUCT),
    ]
    order1 = Order(id="ORD001", products=products1)
    
    print(f"\n先处理正常订单 ORD001...")
    result1 = scheduler.process_order(order1)
    print(f"  利用率: {result1.overall_utilization * 100:.2f}%")
    print(f"  使用原片: {len(result1.used_originals)} 块")
    
    if result1.unfulfilled_products:
        print(f"  ⚠️  有未满足产品: {sum(p.quantity for p in result1.unfulfilled_products)} 块")
    else:
        print("  订单完全满足，为了测试紧急插单，我们创建一个有未满足产品的订单...")
        inventory.add_original(GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL))
        products1.append(GlassSheet(2000, 1500, 12, 5, GlassType.PRODUCT))
        order1_big = Order(id="ORD001", products=products1)
        scheduler = ProductionScheduler(inventory)
        result1 = scheduler.process_order(order1_big)
        print(f"  新利用率: {result1.overall_utilization * 100:.2f}%")
        print(f"  未满足产品: {sum(p.quantity for p in result1.unfulfilled_products)} 块")
    
    urgent_products = [
        GlassSheet(1800, 1200, 12, 2, GlassType.PRODUCT),
    ]
    urgent_order = Order(id="URG001", products=urgent_products, is_urgent=True)
    
    print(f"\n插入紧急订单 URG001...")
    urgent_result, old_schedules, rescheduled, affected_sheets = scheduler.insert_urgent_order(urgent_order)
    
    print(f"  受影响订单数: {len(rescheduled)}")
    print(f"  受影响原片数: {len(affected_sheets)}")
    print(f"  紧急订单利用率: {urgent_result.overall_utilization * 100:.2f}%")
    
    if rescheduled:
        for r in rescheduled:
            status = "已重新排产"
            if r.unfulfilled_products:
                status += f" (仍缺货{sum(p.quantity for p in r.unfulfilled_products)}块)"
            print(f"  - {r.order.id}: {status}")
    
    success = urgent_result is not None and len(old_schedules) > 0
    print()
    return success


def test_reports():
    print("=" * 60)
    print("测试5: 报表生成验证")
    print("=" * 60)
    
    inventory = Inventory(saw_kerf=3.0)
    
    for _ in range(3):
        inventory.add_original(GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL))
    
    scheduler = ProductionScheduler(inventory)
    
    products = [
        GlassSheet(1200, 800, 12, 5, GlassType.PRODUCT),
        GlassSheet(1000, 600, 12, 6, GlassType.PRODUCT),
    ]
    order = Order(id="TEST01", products=products)
    result = scheduler.process_order(order)
    
    print("\n订单报表预览:")
    report = ReportGenerator.generate_order_report(result)
    lines = report.split('\n')[:20]
    for line in lines:
        print(f"  {line}")
    print("  ...")
    
    os.makedirs("test_output", exist_ok=True)
    
    report_path = "test_output/test_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n报表已保存到: {report_path}")
    
    csv_path = "test_output/test_report.csv"
    ReportGenerator.export_csv(result, csv_path)
    print(f"CSV已保存到: {csv_path}")
    
    svg_path = "test_output/test_diagram.svg"
    if result.cutting_results:
        CuttingDiagram.generate_svg(result.cutting_results[0], svg_path)
        print(f"SVG图纸已保存到: {svg_path}")
    
    success = os.path.exists(report_path) and os.path.exists(csv_path)
    print()
    return success


def test_svg_export():
    print("=" * 60)
    print("测试6: SVG图纸导出验证")
    print("=" * 60)
    
    sheet = GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL)
    pieces = [
        GlassSheet(1200, 800, 12, 2, GlassType.PRODUCT),
        GlassSheet(1000, 600, 12, 3, GlassType.PRODUCT),
    ]
    
    result = find_best_packing(sheet, pieces, saw_kerf=3.0)
    
    os.makedirs("test_output", exist_ok=True)
    svg_path = "test_output/cutting_diagram.svg"
    exported_path = CuttingDiagram.generate_svg(result, svg_path)
    
    print(f"\nSVG文件已导出到: {exported_path}")
    print(f"文件大小: {os.path.getsize(exported_path)} 字节")
    
    with open(exported_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if '<svg' in content and '</svg>' in content:
            print("SVG格式验证通过")
            success = True
        else:
            print("SVG格式验证失败")
            success = False
    
    print()
    return success


def main():
    print("\n" + "=" * 60)
    print(" " * 15 + "玻璃切割优化系统 - 自动化测试")
    print("=" * 60 + "\n")
    
    tests = [
        ("切割算法验证", test_cutting_algorithm),
        ("余料优先匹配验证", test_remnant_matching),
        ("完整排产流程验证", test_scheduler),
        ("紧急插单功能验证", test_urgent_insert),
        ("报表生成验证", test_reports),
        ("SVG图纸导出验证", test_svg_export),
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
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print(" " * 20 + "测试结果汇总")
    print("=" * 60)
    
    passed_count = 0
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {name}")
        if passed:
            passed_count += 1
    
    print("-" * 60)
    print(f"  总计: {passed_count}/{len(results)} 测试通过")
    print("=" * 60 + "\n")
    
    return passed_count == len(results)


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
