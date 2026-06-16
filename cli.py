import sys
from typing import List
from models import GlassSheet, Order, Inventory, GlassType
from scheduler import ProductionScheduler
from visualization import CuttingDiagram
from reports import ReportGenerator
import os


class GlassCuttingCLI:
    def __init__(self):
        self.inventory = Inventory(saw_kerf=3.0)
        self.scheduler = ProductionScheduler(self.inventory)
        self.current_order_id = 0

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self):
        self.clear_screen()
        print("=" * 70)
        print(" " * 15 + "玻璃深加工企业 - 切割优化与余料管理系统")
        print("=" * 70)
        print()

    def main_menu(self):
        while True:
            self.print_header()
            print("【主菜单】")
            print("  1. 原片玻璃库存管理")
            print("  2. 余料库存管理")
            print("  3. 订单管理与排产")
            print("  4. 查看切割图纸")
            print("  5. 导出统计报表")
            print("  6. 紧急插单")
            print("  7. 系统设置")
            print("  8. 加载示例数据")
            print("  0. 退出系统")
            print()
            
            choice = input("请选择操作 (0-8): ").strip()
            
            if choice == '1':
                self.original_inventory_menu()
            elif choice == '2':
                self.remnant_inventory_menu()
            elif choice == '3':
                self.order_menu()
            elif choice == '4':
                self.view_cutting_diagram()
            elif choice == '5':
                self.export_reports()
            elif choice == '6':
                self.urgent_insert_menu()
            elif choice == '7':
                self.system_settings()
            elif choice == '8':
                self.load_sample_data()
            elif choice == '0':
                print("\n感谢使用，再见！")
                sys.exit(0)
            else:
                print("\n无效选择，请重新输入。")
                input("\n按回车键继续...")

    def original_inventory_menu(self):
        while True:
            self.print_header()
            print("【原片玻璃库存管理】")
            print("  1. 添加原片玻璃")
            print("  2. 查看原片库存")
            print("  3. 删除原片")
            print("  4. 批量导入原片")
            print("  0. 返回主菜单")
            print()
            
            choice = input("请选择操作 (0-4): ").strip()
            
            if choice == '1':
                self.add_original_sheet()
            elif choice == '2':
                self.view_original_inventory()
            elif choice == '3':
                self.remove_original_sheet()
            elif choice == '4':
                self.batch_import_originals()
            elif choice == '0':
                break
            else:
                print("\n无效选择。")
                input("\n按回车键继续...")

    def add_original_sheet(self):
        self.print_header()
        print("【添加原片玻璃】")
        try:
            length = float(input("请输入原片长度 (mm): "))
            width = float(input("请输入原片宽度 (mm): "))
            thickness = float(input("请输入原片厚度 (mm): "))
            quantity = int(input("请输入数量: "))
            
            for _ in range(quantity):
                sheet = GlassSheet(
                    length=length,
                    width=width,
                    thickness=thickness,
                    glass_type=GlassType.ORIGINAL
                )
                self.inventory.add_original(sheet)
            
            print(f"\n成功添加 {quantity} 块原片玻璃。")
        except ValueError:
            print("\n输入错误，请输入有效的数值。")
        input("\n按回车键继续...")

    def view_original_inventory(self):
        self.print_header()
        print("【原片库存列表】")
        print()
        
        if not self.inventory.originals:
            print("原片库存为空。")
        else:
            print(f"{'编号':<12} {'尺寸(mm)':<18} {'厚度(mm)':<12} {'面积(m²)':<12}")
            print("-" * 54)
            
            for sheet in self.inventory.originals:
                area = sheet.area / 1e6
                print(f"{sheet.id:<12} {sheet.length}×{sheet.width:<10} {sheet.thickness:<12} {area:<12.4f}")
            
            total_area = sum(s.area for s in self.inventory.originals) / 1e6
            print("-" * 54)
            print(f"{'合计':<42} {total_area:<12.4f}")
        
        input("\n按回车键继续...")

    def remove_original_sheet(self):
        self.print_header()
        print("【删除原片玻璃】")
        
        if not self.inventory.originals:
            print("原片库存为空。")
            input("\n按回车键继续...")
            return
        
        sheet_id = input("请输入要删除的原片编号: ").strip()
        removed = self.inventory.remove_original(sheet_id)
        
        if removed:
            print(f"\n成功删除原片: {removed}")
        else:
            print(f"\n未找到编号为 {sheet_id} 的原片。")
        
        input("\n按回车键继续...")

    def batch_import_originals(self):
        self.print_header()
        print("【批量导入原片】")
        print("输入格式: 长度,宽度,厚度,数量 (每行一个，空行结束)")
        print("示例: 2440,1830,12,5")
        print()
        
        count = 0
        while True:
            line = input(f"第 {count + 1} 行: ").strip()
            if not line:
                break
            
            try:
                parts = line.split(',')
                if len(parts) != 4:
                    print("  格式错误，跳过。")
                    continue
                
                length = float(parts[0].strip())
                width = float(parts[1].strip())
                thickness = float(parts[2].strip())
                quantity = int(parts[3].strip())
                
                for _ in range(quantity):
                    sheet = GlassSheet(
                        length=length,
                        width=width,
                        thickness=thickness,
                        glass_type=GlassType.ORIGINAL
                    )
                    self.inventory.add_original(sheet)
                
                count += quantity
                print(f"  成功添加 {quantity} 块。")
            except ValueError:
                print("  数值错误，跳过。")
        
        print(f"\n共添加 {count} 块原片玻璃。")
        input("\n按回车键继续...")

    def remnant_inventory_menu(self):
        while True:
            self.print_header()
            print("【余料库存管理】")
            print("  1. 查看余料库存")
            print("  2. 手动添加余料")
            print("  3. 删除余料")
            print("  0. 返回主菜单")
            print()
            
            choice = input("请选择操作 (0-3): ").strip()
            
            if choice == '1':
                self.view_remnant_inventory()
            elif choice == '2':
                self.add_remnant_manual()
            elif choice == '3':
                self.remove_remnant()
            elif choice == '0':
                break
            else:
                print("\n无效选择。")
                input("\n按回车键继续...")

    def view_remnant_inventory(self):
        self.print_header()
        print("【余料库存列表】")
        print(f"最小入库面积: {self.inventory.min_remnant_area} mm²")
        print()
        
        if not self.inventory.remnants:
            print("余料库存为空。")
        else:
            print(f"{'编号':<12} {'尺寸(mm)':<18} {'厚度(mm)':<12} {'面积(m²)':<12} {'来源':<12}")
            print("-" * 66)
            
            for rem in self.inventory.remnants:
                area = rem.area / 1e6
                parent = rem.parent_id if rem.parent_id else "手动"
                print(f"{rem.id:<12} {rem.length}×{rem.width:<10} {rem.thickness:<12} {area:<12.4f} {parent:<12}")
            
            total_area = sum(s.area for s in self.inventory.remnants) / 1e6
            print("-" * 66)
            print(f"{'合计':<54} {total_area:<12.4f}")
        
        input("\n按回车键继续...")

    def add_remnant_manual(self):
        self.print_header()
        print("【手动添加余料】")
        try:
            length = float(input("请输入余料长度 (mm): "))
            width = float(input("请输入余料宽度 (mm): "))
            thickness = float(input("请输入余料厚度 (mm): "))
            
            remnant = GlassSheet(
                length=length,
                width=width,
                thickness=thickness,
                glass_type=GlassType.REMNANT
            )
            
            if remnant.area < self.inventory.min_remnant_area:
                confirm = input(f"\n余料面积 ({remnant.area:.0f} mm²) 小于最小入库面积 "
                              f"({self.inventory.min_remnant_area} mm²)，是否仍要添加? (y/n): ")
                if confirm.lower() != 'y':
                    print("\n已取消。")
                    input("\n按回车键继续...")
                    return
            
            self.inventory.add_remnant(remnant)
            print(f"\n成功添加余料: {remnant}")
        except ValueError:
            print("\n输入错误。")
        input("\n按回车键继续...")

    def remove_remnant(self):
        self.print_header()
        print("【删除余料】")
        
        if not self.inventory.remnants:
            print("余料库存为空。")
            input("\n按回车键继续...")
            return
        
        rem_id = input("请输入要删除的余料编号: ").strip()
        removed = self.inventory.remove_remnant(rem_id)
        
        if removed:
            print(f"\n成功删除余料: {removed}")
        else:
            print(f"\n未找到编号为 {rem_id} 的余料。")
        
        input("\n按回车键继续...")

    def order_menu(self):
        while True:
            self.print_header()
            print("【订单管理与排产】")
            print("  1. 创建新订单并排产")
            print("  2. 查看已排产订单")
            print("  0. 返回主菜单")
            print()
            
            choice = input("请选择操作 (0-2): ").strip()
            
            if choice == '1':
                self.create_and_process_order()
            elif choice == '2':
                self.view_scheduled_orders()
            elif choice == '0':
                break
            else:
                print("\n无效选择。")
                input("\n按回车键继续...")

    def create_and_process_order(self):
        self.print_header()
        print("【创建新订单】")
        
        self.current_order_id += 1
        order_id = f"ORD{self.current_order_id:04d}"
        
        products = []
        print(f"\n订单编号: {order_id}")
        print("请输入产品尺寸 (格式: 长度,宽度,厚度,数量，空行结束):")
        print("示例: 1200,800,12,10")
        print()
        
        idx = 0
        while True:
            line = input(f"产品 {idx + 1}: ").strip()
            if not line:
                break
            
            try:
                parts = line.split(',')
                if len(parts) != 4:
                    print("  格式错误，跳过。")
                    continue
                
                length = float(parts[0].strip())
                width = float(parts[1].strip())
                thickness = float(parts[2].strip())
                quantity = int(parts[3].strip())
                
                product = GlassSheet(
                    length=length,
                    width=width,
                    thickness=thickness,
                    quantity=quantity,
                    glass_type=GlassType.PRODUCT
                )
                products.append(product)
                idx += 1
                print(f"  已添加: {length}×{width}×{thickness}mm × {quantity}块")
            except ValueError:
                print("  数值错误，跳过。")
        
        if not products:
            print("\n未添加任何产品，订单已取消。")
            input("\n按回车键继续...")
            return
        
        order = Order(id=order_id, products=products)
        
        self.print_header()
        print("【订单排产中...】")
        print(f"订单编号: {order_id}")
        print(f"产品总数: {sum(p.quantity for p in products)} 块")
        print()
        
        schedule_result = self.scheduler.process_order(order)
        
        self.display_schedule_result(schedule_result)
        input("\n按回车键继续...")

    def display_schedule_result(self, schedule_result):
        print("\n" + "=" * 70)
        print(" " * 20 + "排产结果")
        print("=" * 70)
        
        print(f"\n订单编号: {schedule_result.order.id}")
        print(f"综合利用率: {schedule_result.overall_utilization * 100:.2f}%")
        print(f"使用原片: {len(schedule_result.used_originals)} 块")
        print(f"使用余料: {len(schedule_result.used_remnants)} 块")
        print(f"新产生余料: {len(schedule_result.new_remnants)} 块")
        
        if schedule_result.unfulfilled_products:
            print("\n⚠️  未满足产品:")
            for prod in schedule_result.unfulfilled_products:
                print(f"   - {prod.length}×{prod.width}×{prod.thickness}mm × {prod.quantity}块")
        
        print("\n" + "-" * 70)
        print("切割方案明细:")
        
        for i, cr in enumerate(schedule_result.cutting_results):
            print(f"\n--- 原片 {i + 1} ---")
            print(CuttingDiagram.print_detailed_pieces(cr))
            
            show_diagram = input("\n显示字符切割图纸? (y/n): ").strip().lower()
            if show_diagram == 'y':
                print()
                print(CuttingDiagram.generate_ascii(cr))
                print()
            
            export_svg = input("导出SVG图纸? (y/n): ").strip().lower()
            if export_svg == 'y':
                svg_path = f"diagrams/{schedule_result.order.id}_sheet_{i+1}.svg"
                CuttingDiagram.generate_svg(cr, svg_path)
                print(f"已导出到: {svg_path}")
        
        export_report = input("\n导出订单统计报表? (y/n): ").strip().lower()
        if export_report == 'y':
            report_path = f"reports/order_{schedule_result.order.id}.txt"
            csv_path = f"reports/order_{schedule_result.order.id}.csv"
            report = ReportGenerator.generate_order_report(schedule_result)
            os.makedirs("reports", exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            ReportGenerator.export_csv(schedule_result, csv_path)
            print(f"已导出报表: {report_path}")
            print(f"已导出CSV: {csv_path}")

    def view_scheduled_orders(self):
        self.print_header()
        print("【已排产订单列表】")
        print()
        
        if not self.scheduler.scheduled_orders:
            print("暂无已排产订单。")
            input("\n按回车键继续...")
            return
        
        print(f"{'订单号':<12} {'产品数':<10} {'原片数':<10} {'利用率(%)':<12} {'状态':<15}")
        print("-" * 60)
        
        for sr in self.scheduler.scheduled_orders:
            product_count = sum(p.quantity for p in sr.order.products)
            util = sr.overall_utilization * 100
            status = "紧急" if sr.order.is_urgent else "正常"
            if sr.unfulfilled_products:
                status += "(部分缺货)"
            print(f"{sr.order.id:<12} {product_count:<10} {len(sr.used_originals):<10} {util:<12.2f} {status:<15}")
        
        print()
        order_id = input("输入订单号查看详情 (回车返回): ").strip()
        
        if order_id:
            for sr in self.scheduler.scheduled_orders:
                if sr.order.id == order_id:
                    self.display_schedule_result(sr)
                    break
            else:
                print(f"\n未找到订单 {order_id}")
                input("\n按回车键继续...")

    def view_cutting_diagram(self):
        self.print_header()
        print("【查看切割图纸】")
        print()
        
        if not self.scheduler.scheduled_orders:
            print("暂无已排产订单。")
            input("\n按回车键继续...")
            return
        
        for i, sr in enumerate(self.scheduler.scheduled_orders):
            print(f"{i + 1}. 订单 {sr.order.id} ({len(sr.cutting_results)} 张切割图)")
        
        print()
        choice = input("选择订单编号查看 (0 返回): ").strip()
        
        try:
            idx = int(choice) - 1
            if idx < 0:
                return
            if 0 <= idx < len(self.scheduler.scheduled_orders):
                sr = self.scheduler.scheduled_orders[idx]
                
                for j, cr in enumerate(sr.cutting_results):
                    self.print_header()
                    print(f"订单 {sr.order.id} - 原片 {j + 1}/{len(sr.cutting_results)}")
                    print()
                    print(CuttingDiagram.generate_ascii(cr))
                    print()
                    print(CuttingDiagram.print_detailed_pieces(cr))
                    
                    if j < len(sr.cutting_results) - 1:
                        input("\n按回车查看下一张...")
        except ValueError:
            print("\n无效输入。")
        
        input("\n按回车键继续...")

    def export_reports(self):
        self.print_header()
        print("【导出统计报表】")
        print()
        
        if not self.scheduler.scheduled_orders:
            print("暂无已排产订单。")
            input("\n按回车键继续...")
            return
        
        print("  1. 导出全部报表")
        print("  2. 导出库存报表")
        print("  3. 导出指定订单报表")
        print("  0. 返回")
        print()
        
        choice = input("请选择: ").strip()
        
        if choice == '1':
            report_file = ReportGenerator.generate_full_report(
                self.scheduler.scheduled_orders, self.inventory
            )
            print(f"\n综合报表已导出到: {report_file}")
        
        elif choice == '2':
            os.makedirs("reports", exist_ok=True)
            report = ReportGenerator.generate_inventory_report(self.inventory)
            filepath = "reports/inventory_report.txt"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n库存报表已导出到: {filepath}")
            print("\n" + report)
        
        elif choice == '3':
            order_id = input("请输入订单号: ").strip()
            for sr in self.scheduler.scheduled_orders:
                if sr.order.id == order_id:
                    os.makedirs("reports", exist_ok=True)
                    report = ReportGenerator.generate_order_report(sr)
                    filepath = f"reports/order_{order_id}_report.txt"
                    csv_path = f"reports/order_{order_id}.csv"
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(report)
                    ReportGenerator.export_csv(sr, csv_path)
                    print(f"\n订单报表已导出到: {filepath}")
                    print(f"CSV文件已导出到: {csv_path}")
                    break
            else:
                print(f"\n未找到订单 {order_id}")
        
        elif choice == '0':
            return
        
        input("\n按回车键继续...")

    def urgent_insert_menu(self):
        self.print_header()
        print("【紧急插单】")
        print("⚠️  紧急插单会将当前未完全满足的订单回滚并重新排产。")
        print()
        
        if not self.scheduler.scheduled_orders:
            print("当前没有已排产订单。")
            input("\n按回车键继续...")
            return
        
        confirm = input("确认进行紧急插单? (y/n): ").strip().lower()
        if confirm != 'y':
            return
        
        self.current_order_id += 1
        order_id = f"URG{self.current_order_id:04d}"
        
        products = []
        print(f"\n紧急订单编号: {order_id}")
        print("请输入产品尺寸 (格式: 长度,宽度,厚度,数量，空行结束):")
        print()
        
        idx = 0
        while True:
            line = input(f"产品 {idx + 1}: ").strip()
            if not line:
                break
            
            try:
                parts = line.split(',')
                if len(parts) != 4:
                    print("  格式错误，跳过。")
                    continue
                
                length = float(parts[0].strip())
                width = float(parts[1].strip())
                thickness = float(parts[2].strip())
                quantity = int(parts[3].strip())
                
                product = GlassSheet(
                    length=length,
                    width=width,
                    thickness=thickness,
                    quantity=quantity,
                    glass_type=GlassType.PRODUCT
                )
                products.append(product)
                idx += 1
                print(f"  已添加: {length}×{width}×{thickness}mm × {quantity}块")
            except ValueError:
                print("  数值错误，跳过。")
        
        if not products:
            print("\n未添加任何产品，操作已取消。")
            input("\n按回车键继续...")
            return
        
        urgent_order = Order(id=order_id, products=products, is_urgent=True)
        
        self.print_header()
        print("【紧急插单处理中...】")
        print()
        
        urgent_result, rescheduled = self.scheduler.insert_urgent_order(urgent_order)
        
        print("=" * 70)
        print(" " * 25 + "紧急插单结果")
        print("=" * 70)
        
        print(f"\n受影响的订单数: {len(rescheduled)} 个")
        if rescheduled:
            print("受影响的订单:")
            for r in rescheduled:
                status = "正常"
                if r.unfulfilled_products:
                    status = f"部分缺货 ({sum(p.quantity for p in r.unfulfilled_products)}块)"
                print(f"  - {r.order.id}: {status}")
        
        print("\n" + "-" * 70)
        print("紧急订单排产结果:")
        self.display_schedule_result(urgent_result)
        
        input("\n按回车键继续...")

    def system_settings(self):
        while True:
            self.print_header()
            print("【系统设置】")
            print(f"  1. 设置锯缝宽度 (当前: {self.inventory.saw_kerf}mm)")
            print(f"  2. 设置最小余料入库面积 (当前: {self.inventory.min_remnant_area} mm²)")
            print("  0. 返回主菜单")
            print()
            
            choice = input("请选择操作: ").strip()
            
            if choice == '1':
                try:
                    new_kerf = float(input("请输入新的锯缝宽度 (mm): "))
                    if new_kerf >= 0:
                        self.inventory.saw_kerf = new_kerf
                        self.scheduler.remnant_matcher.saw_kerf = new_kerf
                        print(f"\n锯缝宽度已设置为 {new_kerf}mm")
                    else:
                        print("\n锯缝宽度不能为负数。")
                except ValueError:
                    print("\n输入错误。")
                input("\n按回车键继续...")
            
            elif choice == '2':
                try:
                    new_min = float(input("请输入新的最小余料入库面积 (mm²): "))
                    if new_min >= 0:
                        self.inventory.min_remnant_area = new_min
                        print(f"\n最小入库面积已设置为 {new_min} mm²")
                    else:
                        print("\n面积不能为负数。")
                except ValueError:
                    print("\n输入错误。")
                input("\n按回车键继续...")
            
            elif choice == '0':
                break
            else:
                print("\n无效选择。")
                input("\n按回车键继续...")

    def load_sample_data(self):
        self.print_header()
        print("【加载示例数据】")
        print()
        
        self.inventory = Inventory(saw_kerf=3.0)
        self.scheduler = ProductionScheduler(self.inventory)
        self.current_order_id = 0
        
        originals = [
            (2440, 1830, 12, 10),
            (2440, 1830, 8, 8),
            (2134, 1830, 10, 5),
            (3000, 2000, 15, 3),
        ]
        
        for length, width, thickness, qty in originals:
            for _ in range(qty):
                sheet = GlassSheet(
                    length=length, width=width, thickness=thickness,
                    glass_type=GlassType.ORIGINAL
                )
                self.inventory.add_original(sheet)
        
        remnants = [
            (1500, 1200, 12),
            (1000, 800, 8),
        ]
        
        for length, width, thickness in remnants:
            rem = GlassSheet(
                length=length, width=width, thickness=thickness,
                glass_type=GlassType.REMNANT
            )
            self.inventory.add_remnant(rem)
        
        print("已加载示例数据:")
        print(f"  - 原片玻璃: {len(self.inventory.originals)} 块")
        print(f"  - 余料玻璃: {len(self.inventory.remnants)} 块")
        print()
        print("原片库存:")
        for t in sorted(set(s.thickness for s in self.inventory.originals)):
            count = len([s for s in self.inventory.originals if s.thickness == t])
            print(f"  - {t}mm 厚度: {count} 块")
        
        print("\n示例订单:")
        print("  ORD0001: 门窗玻璃订单 (12mm 厚)")
        print("  ORD0002: 家具玻璃订单 (8mm 厚)")
        
        order1_products = [
            GlassSheet(1200, 800, 12, 8, GlassType.PRODUCT),
            GlassSheet(1000, 600, 12, 10, GlassType.PRODUCT),
            GlassSheet(1500, 1000, 12, 3, GlassType.PRODUCT),
        ]
        order1 = Order(id="ORD0001", products=order1_products)
        
        order2_products = [
            GlassSheet(800, 600, 8, 15, GlassType.PRODUCT),
            GlassSheet(1200, 500, 8, 6, GlassType.PRODUCT),
        ]
        order2 = Order(id="ORD0002", products=order2_products)
        
        self.current_order_id = 2
        
        print("\n正在排产订单...")
        result1 = self.scheduler.process_order(order1)
        print(f"\n订单 ORD0001 完成，利用率: {result1.overall_utilization * 100:.2f}%")
        
        result2 = self.scheduler.process_order(order2)
        print(f"订单 ORD0002 完成，利用率: {result2.overall_utilization * 100:.2f}%")
        
        print(f"\n当前余料库存: {len(self.inventory.remnants)} 块")
        
        input("\n按回车键继续...")


def main():
    cli = GlassCuttingCLI()
    cli.main_menu()


if __name__ == "__main__":
    main()
