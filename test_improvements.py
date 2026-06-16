#!/usr/bin/env python
# -*- coding: utf-8 -*-

from models import GlassSheet, Order, Inventory, GlassType
from scheduler import ProductionScheduler, RemnantMatcher
from cutting_algorithm import find_best_packing
from visualization import CuttingDiagram
from reports import ReportGenerator
import os


def test_remnant_cut_multiple_pieces():
    """测试1: 一块余料切多块成品"""
    print("=" * 70)
    print("测试1: 一块余料切多块成品验证")
    print("=" * 70)
    
    inventory = Inventory(saw_kerf=3.0)
    inventory.min_remnant_area = 10000
    
    remnant = GlassSheet(2000, 1500, 12, glass_type=GlassType.REMNANT)
    inventory.add_remnant(remnant)
    
    for _ in range(5):
        inventory.add_original(GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL))
    
    scheduler = ProductionScheduler(inventory)
    
    products = [
        GlassSheet(600, 500, 12, 8, GlassType.PRODUCT),
    ]
    order = Order(id="TEST001", products=products)
    
    print(f"\n余料尺寸: {remnant.length}×{remnant.width}×{remnant.thickness}mm")
    print(f"余料面积: {remnant.area:.0f} mm²")
    print(f"\n订单产品: 600×500×12mm × 8块")
    print(f"单块产品面积: 300000 mm²")
    print(f"8块总面积: {8 * 600 * 500:.0f} mm²")
    print(f"\n理论上余料可容纳: {(2000//600) * (1500//500)} = 3×3 = 9块")
    
    result = scheduler.process_order(order)
    
    remnant_cut = [cr for cr in result.cutting_results 
                   if cr.original_sheet.glass_type == GlassType.REMNANT]
    
    print(f"\n✅ 实际切割结果:")
    print(f"  使用余料: {len(result.used_remnants)} 块")
    print(f"  使用原片: {len(result.used_originals)} 块")
    
    if remnant_cut:
        cr = remnant_cut[0]
        print(f"  余料切割出的产品数: {len(cr.cut_pieces)} 块")
        print(f"  余料利用率: {cr.utilization_rate * 100:.2f}%")
        
        print(f"\n切割出的产品明细:")
        for i, p in enumerate(cr.cut_pieces):
            print(f"    {i+1}. {p.length}×{p.width}mm 位置:({p.x:.0f},{p.y:.0f})")
        
        print(f"\n余料切割后产生的边角料: {len(cr.remnants)} 块")
        for i, r in enumerate(cr.remnants):
            print(f"    R{i+1}. {r.length:.0f}×{r.width:.0f}mm 面积:{r.area:.0f}mm² 位置:({r.x:.0f},{r.y:.0f})")
        
        print(f"\n订单产品总数: 8块")
        print(f"余料实际切出: {len(cr.cut_pieces)} 块")
        
        if len(cr.cut_pieces) > 1:
            print(f"\n✅ 测试通过: 一块余料成功切出 {len(cr.cut_pieces)} 块成品!")
            success = True
        else:
            print(f"\n❌ 测试失败: 只切出 {len(cr.cut_pieces)} 块，期望大于1块")
            success = False
    else:
        print("\n❌ 测试失败: 未使用余料")
        success = False
    
    print()
    return success


def test_remnant_scrap_inventory():
    """测试2: 余料切割后的边角料入库，并在图纸和报表中显示"""
    print("=" * 70)
    print("测试2: 余料切割边角料入库及图纸报表显示验证")
    print("=" * 70)
    
    inventory = Inventory(saw_kerf=3.0)
    inventory.min_remnant_area = 10000
    
    remnant = GlassSheet(2000, 1500, 12, glass_type=GlassType.REMNANT, id="REM_TEST")
    inventory.add_remnant(remnant)
    
    for _ in range(3):
        inventory.add_original(GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL))
    
    scheduler = ProductionScheduler(inventory)
    
    initial_remnant_count = len(inventory.remnants)
    print(f"\n初始余料库存: {initial_remnant_count} 块")
    
    products = [
        GlassSheet(800, 600, 12, 4, GlassType.PRODUCT),
    ]
    order = Order(id="TEST002", products=products)
    
    result = scheduler.process_order(order)
    
    remnant_cut_results = [cr for cr in result.cutting_results 
                          if cr.original_sheet.glass_type == GlassType.REMNANT]
    
    print(f"\n使用余料切割: {len(remnant_cut_results)} 次")
    
    if remnant_cut_results:
        cr = remnant_cut_results[0]
        print(f"产生边角料: {len(cr.remnants)} 块")
        for i, r in enumerate(cr.remnants):
            print(f"  R{i+1}: {r.length:.0f}×{r.width:.0f}mm 面积:{r.area:.0f}mm² 位置:({r.x:.0f},{r.y:.0f})")
        
        print(f"\n新产生余料入库: {len(result.new_remnants)} 块")
        for r in result.new_remnants:
            if r.parent_id == "REM_TEST":
                print(f"  ✅ [{r.id}] {r.length:.0f}×{r.width:.0f}mm 已入库 (来自余料切割)")
        
        final_remnant_count = len(inventory.remnants)
        expected_count = initial_remnant_count - 1 + len([r for r in result.new_remnants if r.parent_id == "REM_TEST"])
        print(f"\n最终余料库存: {final_remnant_count} 块 (期望: {expected_count})")
        
        print(f"\n📄 切割图纸中的边角料显示:")
        ascii_diagram = CuttingDiagram.generate_ascii(cr, scale=0.04)
        if "R1" in ascii_diagram or "R2" in ascii_diagram:
            print("  ✅ 切割图纸中正确显示了边角料编号 (R1, R2...)")
        else:
            print("  ⚠️  切割图纸中可能未显示边角料编号")
        
        print(f"\n📊 订单报表中的边角料显示:")
        report = ReportGenerator.generate_order_report(result)
        if "新产生余料明细" in report:
            print("  ✅ 订单报表中包含新产生余料明细")
        else:
            print("  ❌ 订单报表中缺少新产生余料明细")
        
        success = len(result.new_remnants) > 0 and final_remnant_count == expected_count
        if success:
            print(f"\n✅ 测试通过: 边角料已正确入库并在图纸和报表中显示!")
        else:
            print(f"\n❌ 测试失败")
    else:
        print("\n❌ 测试失败: 未使用余料切割")
        success = False
    
    print()
    return success


def test_urgent_insert_all_orders():
    """测试3: 紧急插单时所有已排产订单重新排程"""
    print("=" * 70)
    print("测试3: 紧急插单时所有已排产订单重新排程验证")
    print("=" * 70)
    
    inventory = Inventory(saw_kerf=3.0)
    
    for _ in range(10):
        inventory.add_original(GlassSheet(2440, 1830, 12, glass_type=GlassType.ORIGINAL))
    
    scheduler = ProductionScheduler(inventory)
    
    products1 = [GlassSheet(1200, 800, 12, 5, GlassType.PRODUCT)]
    order1 = Order(id="ORD001", products=products1)
    result1 = scheduler.process_order(order1)
    
    products2 = [GlassSheet(1000, 600, 12, 8, GlassType.PRODUCT)]
    order2 = Order(id="ORD002", products=products2)
    result2 = scheduler.process_order(order2)
    
    print(f"\n初始已排产订单: {len(scheduler.scheduled_orders)} 个")
    print(f"  ORD001: 使用原片 {len(result1.used_originals)} 块, 利用率 {result1.overall_utilization*100:.2f}%")
    print(f"  ORD002: 使用原片 {len(result2.used_originals)} 块, 利用率 {result2.overall_utilization*100:.2f}%")
    
    old_used_sheets = []
    for sr in scheduler.scheduled_orders:
        old_used_sheets.extend(sr.used_originals)
        old_used_sheets.extend(sr.used_remnants)
    
    print(f"\n已分配原片总数: {len(old_used_sheets)} 块")
    
    urgent_products = [GlassSheet(1800, 1200, 12, 3, GlassType.PRODUCT)]
    urgent_order = Order(id="URG001", products=urgent_products, is_urgent=True)
    
    print(f"\n插入紧急订单 URG001: 1800×1200×12mm × 3块")
    print("-" * 50)
    
    urgent_result, old_schedules, rescheduled, affected_sheets = scheduler.insert_urgent_order(urgent_order)
    
    print(f"\n📋 受影响的订单: {len(old_schedules)} 个")
    for old in old_schedules:
        print(f"  - {old.order.id}")
    
    print(f"\n📦 受影响的原片: {len(affected_sheets)} 块")
    sheets_by_thickness = {}
    for sheet in affected_sheets:
        t = sheet.thickness
        if t not in sheets_by_thickness:
            sheets_by_thickness[t] = 0
        sheets_by_thickness[t] += 1
    for t, count in sheets_by_thickness.items():
        print(f"  - {t}mm 厚度: {count} 块")
    
    print(f"\n🔄 重新排程结果:")
    for old, new in zip(old_schedules, rescheduled):
        old_util = old.overall_utilization * 100
        new_util = new.overall_utilization * 100
        diff = new_util - old_util
        print(f"  {old.order.id}: {old_util:.2f}% → {new_util:.2f}% ({diff:+.2f}%)")
    
    print(f"\n🚑 紧急订单排产结果:")
    print(f"  利用率: {urgent_result.overall_utilization * 100:.2f}%")
    print(f"  使用原片: {len(urgent_result.used_originals)} 块")
    
    all_scheduled_ids = [sr.order.id for sr in scheduler.scheduled_orders]
    print(f"\n最终排程队列: {all_scheduled_ids}")
    
    expected_ids = ["URG001", "ORD001", "ORD002"]
    if all_scheduled_ids == expected_ids:
        print(f"✅ 排程顺序正确: 紧急订单优先，然后是原有订单")
        success = True
    else:
        print(f"❌ 排程顺序错误，期望: {expected_ids}")
        success = False
    
    if len(old_schedules) == 2 and len(affected_sheets) > 0:
        print(f"✅ 所有已排产订单都参与了重新排程")
    else:
        print(f"❌ 未正确回滚所有已排产订单")
        success = False
    
    if success:
        print(f"\n✅ 测试通过: 紧急插单功能完整!")
    else:
        print(f"\n❌ 测试失败")
    
    print()
    return success


def test_input_validation():
    """测试4: 输入验证功能"""
    print("=" * 70)
    print("测试4: 输入验证功能验证")
    print("=" * 70)
    
    from cli import GlassCuttingCLI
    cli = GlassCuttingCLI()
    
    test_cases = [
        ("-100,200,12,5", False, "负数长度"),
        ("0,200,12,5", False, "零长度"),
        ("100,0,12,5", False, "零宽度"),
        ("100,200,0,5", False, "零厚度"),
        ("100,200,12,0", False, "零数量"),
        ("100,200,12,-5", False, "负数数量"),
        ("abc,200,12,5", False, "非数字长度"),
        ("100,200,12,abc", False, "非整数数量"),
        ("100,200,12", False, "缺少参数"),
        ("100,200,12,5,extra", False, "多余参数"),
        ("2440,1830,12,5", True, "正常输入"),
        ("1000,800,8,10", True, "正常输入2"),
        ("  2440 , 1830 , 12 , 5  ", True, "带空格输入"),
    ]
    
    print(f"\n批量输入验证测试 (共 {len(test_cases)} 个用例):")
    print("-" * 70)
    
    passed = 0
    for input_str, expected_valid, description in test_cases:
        result = cli._validate_glass_input(input_str)
        is_valid = result is not None
        
        status = "✅" if is_valid == expected_valid else "❌"
        if is_valid == expected_valid:
            passed += 1
        
        print(f"  {status} [{description:15}] 输入: {input_str:30} → {'有效' if is_valid else '无效'}")
    
    print(f"\n批量验证结果: {passed}/{len(test_cases)} 通过")
    
    print(f"\n单值验证测试:")
    print("-" * 70)
    
    single_tests = [
        ("length", "-5", "长度", False),
        ("length", "0", "长度", False),
        ("length", "0.5", "长度", False),
        ("length", "100", "长度", True),
        ("quantity", "5.5", "数量", False),
        ("quantity", "5", "数量", True),
        ("kerf", "-1", "锯缝宽度", False),
        ("kerf", "3", "锯缝宽度", True),
        ("kerf", "100", "锯缝宽度", False),
    ]
    
    single_passed = 0
    for _, value, field, expected_valid in single_tests:
        min_val = 10 if field == "长度" else 0 if field == "锯缝宽度" else 1
        max_val = 50 if field == "锯缝宽度" else None
        is_int = field == "数量"
        
        result = cli._validate_single_value(value, field, min_val=min_val, max_val=max_val, is_integer=is_int)
        is_valid = result is not None
        
        status = "✅" if is_valid == expected_valid else "❌"
        if is_valid == expected_valid:
            single_passed += 1
        
        print(f"  {status} {field:10} = {value:10} → {'有效' if is_valid else '无效'}")
    
    print(f"\n单值验证结果: {single_passed}/{len(single_tests)} 通过")
    
    success = passed == len(test_cases) and single_passed == len(single_tests)
    if success:
        print(f"\n✅ 测试通过: 输入验证功能完整!")
    else:
        print(f"\n❌ 测试失败")
    
    print()
    return success


def test_display_remnant_cutting_diagram():
    """测试5: 余料切割图纸显示边角料"""
    print("=" * 70)
    print("测试5: 余料切割图纸和报表显示边角料")
    print("=" * 70)
    
    remnant = GlassSheet(2000, 1500, 12, glass_type=GlassType.REMNANT, id="REM_DISPLAY")
    
    products = [
        GlassSheet(600, 500, 12, 6, GlassType.PRODUCT),
    ]
    
    result = find_best_packing(remnant, products, saw_kerf=3.0)
    
    print(f"\n余料: {remnant.length}×{remnant.width}mm")
    print(f"切割产品: {len(result.cut_pieces)} 块")
    print(f"产生边角料: {len(result.remnants)} 块")
    
    print(f"\n📄 字符切割图纸:")
    print(CuttingDiagram.generate_ascii(result, scale=0.05))
    
    print(f"\n📋 详细切割明细:")
    print(CuttingDiagram.print_detailed_pieces(result))
    
    print(f"\n📊 SVG图纸导出:")
    os.makedirs("test_output", exist_ok=True)
    svg_path = "test_output/remnant_cutting_diagram.svg"
    CuttingDiagram.generate_svg(result, svg_path)
    print(f"  ✅ SVG图纸已导出到: {svg_path}")
    
    success = len(result.remnants) > 0 and "R1" in CuttingDiagram.generate_ascii(result, scale=0.05)
    if success:
        print(f"\n✅ 测试通过: 切割图纸正确显示边角料!")
    else:
        print(f"\n❌ 测试失败")
    
    print()
    return success


def main():
    print("\n" + "=" * 70)
    print(" " * 15 + "玻璃切割系统 - 功能改进专项测试")
    print("=" * 70 + "\n")
    
    tests = [
        ("余料切多块成品", test_remnant_cut_multiple_pieces),
        ("边角料入库与显示", test_remnant_scrap_inventory),
        ("紧急插单全量重排", test_urgent_insert_all_orders),
        ("输入验证拦截", test_input_validation),
        ("切割图纸显示边角料", test_display_remnant_cutting_diagram),
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
        print("-" * 70)
    
    print("\n" + "=" * 70)
    print(" " * 25 + "测试结果汇总")
    print("=" * 70)
    
    passed_count = 0
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {name}")
        if passed:
            passed_count += 1
    
    print("-" * 70)
    print(f"  总计: {passed_count}/{len(results)} 测试通过")
    print("=" * 70 + "\n")
    
    return passed_count == len(results)


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
