from typing import List
from models import ScheduleResult, Inventory
import os
from datetime import datetime


class ReportGenerator:
    @staticmethod
    def generate_order_report(schedule_result: ScheduleResult) -> str:
        order = schedule_result.order
        lines = []
        
        lines.append("=" * 80)
        lines.append(" " * 25 + "玻璃切割订单耗材统计表")
        lines.append("=" * 80)
        lines.append(f"订单编号: {order.id}")
        lines.append(f"创建时间: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"紧急订单: {'是' if order.is_urgent else '否'}")
        lines.append("-" * 80)
        
        lines.append(f"{'项目':<30} {'数值':<20} {'单位':<15}")
        lines.append("-" * 80)
        
        total_product_area = order.total_product_area() / 1e6
        total_original_area = schedule_result.total_original_area / 1e6
        total_remnant_used = schedule_result.total_remnant_used_area / 1e6
        total_remnant_gen = schedule_result.total_remnant_generated / 1e6
        total_input = total_original_area + total_remnant_used
        overall_util = schedule_result.overall_utilization
        
        lines.append(f"{'订单产品总面积':<30} {total_product_area:<20.4f} {'平方米':<15}")
        lines.append(f"{'消耗原片总面积':<30} {total_original_area:<20.4f} {'平方米':<15}")
        lines.append(f"{'消耗余料总面积':<30} {total_remnant_used:<20.4f} {'平方米':<15}")
        lines.append(f"{'总投入面积':<30} {total_input:<20.4f} {'平方米':<15}")
        lines.append(f"{'产生余料总面积':<30} {total_remnant_gen:<20.4f} {'平方米':<15}")
        lines.append("-" * 80)
        lines.append(f"{'综合利用率':<30} {overall_util * 100:<20.2f} {'%':<15}")
        lines.append("-" * 80)
        
        lines.append("\n原片消耗明细:")
        lines.append(f"{'编号':<12} {'尺寸(mm)':<18} {'数量':<8} {'面积(m²)':<12} {'利用率':<10}")
        lines.append("-" * 70)
        
        for i, cr in enumerate(schedule_result.cutting_results):
            sheet = cr.original_sheet
            area = sheet.area / 1e6
            lines.append(f"{sheet.id:<12} {sheet.length}×{sheet.width:<10} {1:<8} {area:<12.4f} {cr.utilization_rate*100:<10.2f}%")
        
        if schedule_result.used_remnants:
            lines.append("\n余料消耗明细:")
            lines.append(f"{'编号':<12} {'尺寸(mm)':<18} {'数量':<8} {'面积(m²)':<12}")
            lines.append("-" * 60)
            
            for rem in schedule_result.used_remnants:
                area = rem.area / 1e6
                lines.append(f"{rem.id:<12} {rem.length}×{rem.width:<10} {1:<8} {area:<12.4f}")
        
        if schedule_result.new_remnants:
            lines.append("\n新产生余料明细:")
            lines.append(f"{'编号':<12} {'尺寸(mm)':<18} {'数量':<8} {'面积(m²)':<12} {'位置':<12}")
            lines.append("-" * 72)
            
            for i, rem in enumerate(schedule_result.new_remnants):
                area = rem.area / 1e6
                lines.append(f"{rem.id:<12} {rem.length}×{rem.width:<10} {1:<8} {area:<12.4f} ({rem.x:.0f},{rem.y:.0f})")
        
        if schedule_result.unfulfilled_products:
            lines.append("\n未满足产品明细:")
            lines.append(f"{'尺寸(mm)':<18} {'厚度':<10} {'需求量':<10}")
            lines.append("-" * 50)
            
            for prod in schedule_result.unfulfilled_products:
                lines.append(f"{prod.length}×{prod.width:<10} {prod.thickness:<10} {prod.quantity:<10}")
        
        lines.append("\n" + "=" * 80)
        
        return '\n'.join(lines)

    @staticmethod
    def generate_inventory_report(inventory: Inventory) -> str:
        lines = []
        
        lines.append("=" * 80)
        lines.append(" " * 30 + "库存统计表")
        lines.append("=" * 80)
        lines.append(f"锯缝宽度: {inventory.saw_kerf}mm")
        lines.append(f"最小余料入库面积: {inventory.min_remnant_area} mm²")
        lines.append("-" * 80)
        
        lines.append("\n原片库存:")
        lines.append(f"{'编号':<12} {'尺寸(mm)':<18} {'厚度':<10} {'数量':<8} {'面积(m²)':<12}")
        lines.append("-" * 70)
        
        total_original_area = 0
        for sheet in inventory.originals:
            area = sheet.area / 1e6
            total_original_area += area
            lines.append(f"{sheet.id:<12} {sheet.length}×{sheet.width:<10} {sheet.thickness:<10} {sheet.quantity:<8} {area:<12.4f}")
        
        lines.append("-" * 70)
        lines.append(f"{'合计':<60} {total_original_area:<12.4f}")
        
        lines.append("\n余料库存:")
        lines.append(f"{'编号':<12} {'尺寸(mm)':<18} {'厚度':<10} {'数量':<8} {'面积(m²)':<12} {'来源原片':<12}")
        lines.append("-" * 82)
        
        total_remnant_area = 0
        for rem in inventory.remnants:
            area = rem.area / 1e6
            total_remnant_area += area
            parent = rem.parent_id if rem.parent_id else "N/A"
            lines.append(f"{rem.id:<12} {rem.length}×{rem.width:<10} {rem.thickness:<10} {rem.quantity:<8} {area:<12.4f} {parent:<12}")
        
        lines.append("-" * 82)
        lines.append(f"{'合计':<72} {total_remnant_area:<12.4f}")
        
        lines.append("\n" + "=" * 80)
        lines.append(f"库存总价值面积: {total_original_area + total_remnant_area:.4f} 平方米")
        lines.append("=" * 80)
        
        return '\n'.join(lines)

    @staticmethod
    def generate_full_report(schedule_results: List[ScheduleResult], 
                             inventory: Inventory,
                             output_dir: str = "reports") -> str:
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(output_dir, f"full_report_{timestamp}.txt")
        
        content = []
        content.append("=" * 100)
        content.append(" " * 35 + "玻璃切割优化系统 - 综合统计报告")
        content.append("=" * 100)
        content.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("")
        
        total_original_used = sum(s.total_original_area for s in schedule_results) / 1e6
        total_remnant_used = sum(s.total_remnant_used_area for s in schedule_results) / 1e6
        total_product = sum(s.total_product_area for s in schedule_results) / 1e6
        total_remnant_gen = sum(s.total_remnant_generated for s in schedule_results) / 1e6
        total_input = total_original_used + total_remnant_used
        overall_util = total_product / total_input if total_input > 0 else 0
        
        content.append("一、总体统计")
        content.append("-" * 100)
        content.append(f"处理订单数: {len(schedule_results)} 个")
        content.append(f"总产品面积: {total_product:.4f} 平方米")
        content.append(f"总消耗原片面积: {total_original_used:.4f} 平方米")
        content.append(f"总消耗余料面积: {total_remnant_used:.4f} 平方米")
        content.append(f"总投入面积: {total_input:.4f} 平方米")
        content.append(f"总产生余料面积: {total_remnant_gen:.4f} 平方米")
        content.append(f"综合利用率: {overall_util * 100:.2f}%")
        content.append("")
        
        content.append("二、各订单明细")
        content.append("-" * 100)
        content.append(f"{'订单号':<15} {'产品面积(m²)':<15} {'原片消耗(m²)':<15} {'余料消耗(m²)':<15} {'利用率(%)':<12}")
        content.append("-" * 72)
        
        for sr in schedule_results:
            product_area = sr.total_product_area / 1e6
            original_area = sr.total_original_area / 1e6
            remnant_area = sr.total_remnant_used_area / 1e6
            util = sr.overall_utilization * 100
            content.append(f"{sr.order.id:<15} {product_area:<15.4f} {original_area:<15.4f} {remnant_area:<15.4f} {util:<12.2f}")
        
        content.append("")
        content.append("三、库存概况")
        content.append("-" * 100)
        
        inv_original = sum(s.area for s in inventory.originals) / 1e6
        inv_remnant = sum(s.area for s in inventory.remnants) / 1e6
        
        content.append(f"原片库存量: {len(inventory.originals)} 块, 总面积: {inv_original:.4f} 平方米")
        content.append(f"余料库存量: {len(inventory.remnants)} 块, 总面积: {inv_remnant:.4f} 平方米")
        content.append(f"库存总价值面积: {inv_original + inv_remnant:.4f} 平方米")
        content.append("")
        content.append("=" * 100)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
        
        for sr in schedule_results:
            order_report = ReportGenerator.generate_order_report(sr)
            order_file = os.path.join(output_dir, f"order_{sr.order.id}_{timestamp}.txt")
            with open(order_file, 'w', encoding='utf-8') as f:
                f.write(order_report)
        
        inv_report = ReportGenerator.generate_inventory_report(inventory)
        inv_file = os.path.join(output_dir, f"inventory_{timestamp}.txt")
        with open(inv_file, 'w', encoding='utf-8') as f:
            f.write(inv_report)
        
        return report_file

    @staticmethod
    def export_csv(schedule_result: ScheduleResult, filepath: str) -> str:
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write("玻璃切割订单耗材统计表\n")
            f.write(f"订单编号,{schedule_result.order.id}\n")
            f.write(f"创建时间,{schedule_result.order.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"紧急订单,{'是' if schedule_result.order.is_urgent else '否'}\n")
            f.write("\n")
            
            f.write("耗材统计\n")
            f.write("项目,数值,单位\n")
            total_product_area = schedule_result.order.total_product_area() / 1e6
            total_original_area = schedule_result.total_original_area / 1e6
            total_remnant_used = schedule_result.total_remnant_used_area / 1e6
            total_remnant_gen = schedule_result.total_remnant_generated / 1e6
            total_input = total_original_area + total_remnant_used
            overall_util = schedule_result.overall_utilization
            
            f.write(f"订单产品总面积,{total_product_area:.4f},平方米\n")
            f.write(f"消耗原片总面积,{total_original_area:.4f},平方米\n")
            f.write(f"消耗余料总面积,{total_remnant_used:.4f},平方米\n")
            f.write(f"总投入面积,{total_input:.4f},平方米\n")
            f.write(f"产生余料总面积,{total_remnant_gen:.4f},平方米\n")
            f.write(f"综合利用率,{overall_util * 100:.2f},%\n")
            f.write("\n")
            
            f.write("原片消耗明细\n")
            f.write("编号,尺寸(mm),厚度(mm),数量,面积(m²),利用率(%)\n")
            for cr in schedule_result.cutting_results:
                sheet = cr.original_sheet
                area = sheet.area / 1e6
                f.write(f"{sheet.id},{sheet.length}×{sheet.width},{sheet.thickness},1,{area:.4f},{cr.utilization_rate*100:.2f}\n")
            f.write("\n")
            
            if schedule_result.new_remnants:
                f.write("新产生余料明细\n")
                f.write("编号,尺寸(mm),厚度(mm),数量,面积(m²),位置(x,y)\n")
                for rem in schedule_result.new_remnants:
                    area = rem.area / 1e6
                    f.write(f"{rem.id},{rem.length}×{rem.width},{rem.thickness},1,{area:.4f},({rem.x:.0f},{rem.y:.0f})\n")
        
        return filepath
