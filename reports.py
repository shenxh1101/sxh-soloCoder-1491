from typing import List, Dict, Tuple, Optional
from models import ScheduleResult, Inventory, GlassSheet
import os
from datetime import datetime


class ReportGenerator:
    @staticmethod
    def _summarize_products_by_spec(schedule_result: ScheduleResult) -> List[Dict]:
        """
        按产品规格(length,width,thickness)汇总：
        需求块数、已生产块数、未满足块数、需求面积、已生产面积、未满足面积
        """
        spec_map: Dict[Tuple[float, float, float], Dict] = {}

        for p in schedule_result.order.products:
            key = (p.length, p.width, p.thickness)
            alt_key = (p.width, p.length, p.thickness)
            if key not in spec_map and alt_key not in spec_map:
                spec_map[key] = {
                    'length': p.length, 'width': p.width, 'thickness': p.thickness,
                    'demand_qty': 0, 'produced_qty': 0, 'unfulfilled_qty': 0,
                }
            target_key = key if key in spec_map else alt_key
            spec_map[target_key]['demand_qty'] += p.quantity

        for cr in schedule_result.cutting_results:
            for piece in cr.cut_pieces:
                key = (piece.length, piece.width, piece.thickness)
                alt_key = (piece.width, piece.length, piece.thickness)
                if key in spec_map:
                    spec_map[key]['produced_qty'] += 1
                elif alt_key in spec_map:
                    spec_map[alt_key]['produced_qty'] += 1
                else:
                    spec_map[key] = {
                        'length': piece.length, 'width': piece.width, 'thickness': piece.thickness,
                        'demand_qty': 0, 'produced_qty': 1, 'unfulfilled_qty': 0,
                    }

        for p in schedule_result.unfulfilled_products:
            key = (p.length, p.width, p.thickness)
            alt_key = (p.width, p.length, p.thickness)
            if key in spec_map:
                spec_map[key]['unfulfilled_qty'] += p.quantity
            elif alt_key in spec_map:
                spec_map[alt_key]['unfulfilled_qty'] += p.quantity
            else:
                spec_map[key] = {
                    'length': p.length, 'width': p.width, 'thickness': p.thickness,
                    'demand_qty': 0, 'produced_qty': 0, 'unfulfilled_qty': p.quantity,
                }

        result = []
        for key, s in spec_map.items():
            unit_area = s['length'] * s['width']
            s['demand_area'] = s['demand_qty'] * unit_area / 1e6
            s['produced_area'] = s['produced_qty'] * unit_area / 1e6
            s['unfulfilled_area'] = s['unfulfilled_qty'] * unit_area / 1e6
            s['unit_area'] = unit_area / 1e6
            result.append(s)
        result.sort(key=lambda x: (-x['thickness'], -x['length'], -x['width']))
        return result

    @staticmethod
    def generate_order_report(schedule_result: ScheduleResult) -> str:
        order = schedule_result.order
        lines = []
        
        lines.append("=" * 110)
        lines.append(" " * 35 + "玻璃切割订单耗材统计表")
        lines.append("=" * 110)
        lines.append(f"订单编号: {order.id}")
        lines.append(f"创建时间: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"紧急订单: {'是' if order.is_urgent else '否'}")
        lines.append("-" * 110)
        
        lines.append(f"{'项目':<30} {'数值':<25} {'单位':<15}")
        lines.append("-" * 110)
        
        total_demand_area = order.total_product_area() / 1e6
        total_produced_area = schedule_result.total_product_area / 1e6
        total_unfulfilled_area = sum(p.area for p in schedule_result.unfulfilled_products) / 1e6
        total_original_area = schedule_result.total_original_area / 1e6
        total_remnant_used = schedule_result.total_remnant_used_area / 1e6
        total_remnant_gen = schedule_result.total_remnant_generated / 1e6
        total_input = total_original_area + total_remnant_used
        overall_util = schedule_result.overall_utilization
        
        lines.append(f"{'订单需求总面积':<30} {total_demand_area:<25.4f} {'平方米':<15}")
        lines.append(f"{'实际生产总面积':<30} {total_produced_area:<25.4f} {'平方米':<15}")
        lines.append(f"{'未满足产品面积':<30} {total_unfulfilled_area:<25.4f} {'平方米':<15}")
        lines.append(f"{'消耗原片总面积':<30} {total_original_area:<25.4f} {'平方米':<15}")
        lines.append(f"{'消耗余料总面积':<30} {total_remnant_used:<25.4f} {'平方米':<15}")
        lines.append(f"{'总投入面积':<30} {total_input:<25.4f} {'平方米':<15}")
        lines.append(f"{'产生余料总面积':<30} {total_remnant_gen:<25.4f} {'平方米':<15}")
        lines.append("-" * 110)
        fulfillment_rate = (total_produced_area / total_demand_area * 100) if total_demand_area > 0 else 0
        lines.append(f"{'订单满足率':<30} {fulfillment_rate:<25.2f} {'%':<15}")
        lines.append(f"{'综合利用率(基于实际生产)':<30} {overall_util * 100:<25.2f} {'%':<15}")
        lines.append("-" * 110)

        lines.append("\n【一、按产品规格汇总对账】")
        spec_summary = ReportGenerator._summarize_products_by_spec(schedule_result)
        header = (f"{'规格(mm)':<22} {'厚度':<8} "
                  f"{'需求块数':<10} {'已生产块数':<12} {'未满足块数':<12} "
                  f"{'需求面积':<12} {'已生产面积':<12} {'未满足面积':<12}")
        lines.append(header)
        lines.append("-" * 110)
        sum_d_qty = sum_p_qty = sum_u_qty = 0
        sum_d_area = sum_p_area = sum_u_area = 0.0
        for s in spec_summary:
            sum_d_qty += s['demand_qty']
            sum_p_qty += s['produced_qty']
            sum_u_qty += s['unfulfilled_qty']
            sum_d_area += s['demand_area']
            sum_p_area += s['produced_area']
            sum_u_area += s['unfulfilled_area']
            lines.append(
                f"{s['length']:.0f}×{s['width']:.0f}{'':<12} {s['thickness']:<8.0f} "
                f"{s['demand_qty']:<10} {s['produced_qty']:<12} {s['unfulfilled_qty']:<12} "
                f"{s['demand_area']:<12.4f} {s['produced_area']:<12.4f} {s['unfulfilled_area']:<12.4f}"
            )
        lines.append("-" * 110)
        lines.append(
            f"{'合计':<22} {'':<8} "
            f"{sum_d_qty:<10} {sum_p_qty:<12} {sum_u_qty:<12} "
            f"{sum_d_area:<12.4f} {sum_p_area:<12.4f} {sum_u_area:<12.4f}"
        )
        lines.append("  (核对: 需求块数 = 已生产块数 + 未满足块数)")
        lines.append("  (核对: 需求面积 = 已生产面积 + 未满足面积)")
        
        lines.append("\n【二、原片消耗明细】")
        lines.append(f"{'编号':<14} {'尺寸(mm)':<22} {'厚度':<10} {'数量':<8} {'面积(m²)':<14} {'利用率':<10}")
        lines.append("-" * 90)
        
        for cr in schedule_result.cutting_results:
            sheet = cr.original_sheet
            area = sheet.area / 1e6
            lines.append(f"{sheet.id:<14} {sheet.length}×{sheet.width:<14} {sheet.thickness:<10.0f} {1:<8} {area:<14.4f} {cr.utilization_rate*100:<10.2f}%")
        
        if schedule_result.used_remnants:
            lines.append("\n【三、余料消耗明细】")
            lines.append(f"{'编号':<14} {'尺寸(mm)':<22} {'厚度':<10} {'数量':<8} {'面积(m²)':<14}")
            lines.append("-" * 80)
            
            for rem in schedule_result.used_remnants:
                area = rem.area / 1e6
                lines.append(f"{rem.id:<14} {rem.length}×{rem.width:<14} {rem.thickness:<10.0f} {1:<8} {area:<14.4f}")
        
        if schedule_result.new_remnants:
            lines.append("\n【四、新产生余料明细】")
            lines.append(f"{'编号':<14} {'尺寸(mm)':<22} {'厚度':<10} {'数量':<8} {'面积(m²)':<14} {'位置':<14}")
            lines.append("-" * 100)
            
            for rem in schedule_result.new_remnants:
                area = rem.area / 1e6
                lines.append(f"{rem.id:<14} {rem.length:.0f}×{rem.width:.0f}{'':<8} {rem.thickness:<10.0f} {1:<8} {area:<14.4f} ({rem.x:.0f},{rem.y:.0f})")
        
        if schedule_result.unfulfilled_products:
            lines.append("\n【五、未满足产品明细】")
            lines.append(f"{'尺寸(mm)':<22} {'厚度':<10} {'未满足块数':<14} {'单块面积(m²)':<16} {'未满足面积(m²)':<16} {'对应已生产块数':<16}")
            lines.append("-" * 110)
            for s in spec_summary:
                if s['unfulfilled_qty'] > 0:
                    lines.append(
                        f"{s['length']:.0f}×{s['width']:.0f}{'':<12} {s['thickness']:<10.0f} "
                        f"{s['unfulfilled_qty']:<14} {s['unit_area']:<16.4f} {s['unfulfilled_area']:<16.4f} {s['produced_qty']:<16}"
                    )
        
        lines.append("\n" + "=" * 110)
        
        return '\n'.join(lines)

    @staticmethod
    def generate_inventory_report(inventory: Inventory) -> str:
        lines = []
        
        lines.append("=" * 100)
        lines.append(" " * 40 + "库存统计表")
        lines.append("=" * 100)
        lines.append(f"锯缝宽度: {inventory.saw_kerf}mm")
        lines.append(f"最小余料入库面积: {inventory.min_remnant_area} mm²")
        lines.append("-" * 100)
        
        lines.append("\n原片库存:")
        lines.append(f"{'编号':<14} {'尺寸(mm)':<22} {'厚度':<10} {'面积(m²)':<14} {'录入方式':<12}")
        lines.append("-" * 80)
        
        total_original_area = 0
        for sheet in inventory.originals:
            area = sheet.area / 1e6
            total_original_area += area
            source = "手动" if getattr(sheet, 'is_manual', True) else "排程"
            lines.append(f"{sheet.id:<14} {sheet.length}×{sheet.width:<14} {sheet.thickness:<10.0f} {area:<14.4f} {source:<12}")
        
        lines.append("-" * 80)
        lines.append(f"{'合计':<62} {total_original_area:<14.4f}")
        
        lines.append("\n余料库存:")
        lines.append(f"{'编号':<14} {'尺寸(mm)':<22} {'厚度':<10} {'面积(m²)':<14} {'来源':<12}")
        lines.append("-" * 80)
        
        total_remnant_area = 0
        for rem in inventory.remnants:
            area = rem.area / 1e6
            total_remnant_area += area
            source = "手动录入" if getattr(rem, 'is_manual', True) else "切割产生"
            lines.append(f"{rem.id:<14} {rem.length:.0f}×{rem.width:.0f}{'':<8} {rem.thickness:<10.0f} {area:<14.4f} {source:<12}")
        
        lines.append("-" * 80)
        lines.append(f"{'合计':<62} {total_remnant_area:<14.4f}")
        
        lines.append("\n" + "=" * 100)
        lines.append(f"库存总价值面积: {total_original_area + total_remnant_area:.4f} 平方米")
        lines.append(f"  原片: {len(inventory.originals)} 块, {total_original_area:.4f} m²")
        lines.append(f"  余料: {len(inventory.remnants)} 块, {total_remnant_area:.4f} m²")
        lines.append("=" * 100)
        
        return '\n'.join(lines)

    @staticmethod
    def generate_urgent_insert_summary(urgent_result: ScheduleResult,
                                        old_schedules: List[ScheduleResult],
                                        rescheduled: List[ScheduleResult],
                                        affected_sheets: List[GlassSheet],
                                        inventory: Inventory,
                                        output_dir: str = "reports") -> str:
        """
        生成紧急插单汇总报表：紧急订单 + 受影响订单在同一份
        显示排程顺序、谁缺货、库存剩余
        """
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(output_dir, f"urgent_insert_summary_{timestamp}.txt")

        all_results = [urgent_result] + rescheduled
        lines = []
        lines.append("=" * 120)
        lines.append(" " * 40 + "紧急插单汇总报表")
        lines.append("=" * 120)
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"受影响原片/余料总数: {len(affected_sheets)} 块")
        lines.append("-" * 120)

        lines.append("\n【一、最终排程顺序】")
        for idx, sr in enumerate(all_results):
            mark = "🚨 紧急" if sr.order.is_urgent else "普通"
            unful = sum(p.quantity for p in sr.unfulfilled_products)
            unful_str = f", 未满足 {unful} 块" if unful > 0 else ", 全部满足"
            lines.append(f"  {idx + 1}. [{mark}] {sr.order.id}{unful_str}")

        lines.append("\n【二、各订单对比（原排程 vs 新排程）】")
        lines.append("-" * 120)
        header = (f"{'订单号':<12} {'类型':<8} {'原利用率':<12} {'新利用率':<12} {'变化':<10} "
                  f"{'原原片数':<10} {'新原片数':<10} {'新余料数':<10} {'原未满足':<12} {'新未满足':<12}")
        lines.append(header)
        lines.append("-" * 120)

        urg_util_old = "-"
        urg_util_new = urgent_result.overall_utilization * 100
        unful_urg_new = sum(p.quantity for p in urgent_result.unfulfilled_products)
        lines.append(
            f"{urgent_result.order.id:<12} {'紧急':<8} {urg_util_old:<12} {urg_util_new:<12.2f} {'-':<10} "
            f"{'-':<10} {len(urgent_result.used_originals):<10} {len(urgent_result.used_remnants):<10} {'-':<12} {unful_urg_new:<12}"
        )

        for old_sr, new_sr in zip(old_schedules, rescheduled):
            old_util = old_sr.overall_utilization * 100
            new_util = new_sr.overall_utilization * 100
            change = f"{new_util - old_util:+.2f}%"
            unful_old = sum(p.quantity for p in old_sr.unfulfilled_products)
            unful_new = sum(p.quantity for p in new_sr.unfulfilled_products)
            lines.append(
                f"{new_sr.order.id:<12} {'普通':<8} {old_util:<12.2f} {new_util:<12.2f} {change:<10} "
                f"{len(old_sr.used_originals):<10} {len(new_sr.used_originals):<10} {len(new_sr.used_remnants):<10} {unful_old:<12} {unful_new:<12}"
            )

        lines.append("\n【三、各订单产品对账明细】")
        for sr in all_results:
            mark = "🚨 紧急订单" if sr.order.is_urgent else "普通订单"
            lines.append(f"\n  --- {sr.order.id} ({mark}) ---")
            spec = ReportGenerator._summarize_products_by_spec(sr)
            sub_header = (f"    {'规格(mm)':<20} {'厚度':<8} {'需求':<8} {'已生产':<10} {'未满足':<10} "
                          f"{'需求面积':<12} {'已生产面积':<12} {'未满足面积':<12}")
            lines.append(sub_header)
            for s in spec:
                lines.append(
                    f"    {s['length']:.0f}×{s['width']:.0f}{'':<10} {s['thickness']:<8.0f} "
                    f"{s['demand_qty']:<8} {s['produced_qty']:<10} {s['unfulfilled_qty']:<10} "
                    f"{s['demand_area']:<12.4f} {s['produced_area']:<12.4f} {s['unfulfilled_area']:<12.4f}"
                )

        lines.append("\n【四、最终库存概况】")
        inv_lines = ReportGenerator.generate_inventory_report(inventory).split('\n')
        for line in inv_lines:
            lines.append("  " + line)

        lines.append("\n" + "=" * 120)
        content = '\n'.join(lines)

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return report_file

    @staticmethod
    def generate_batch_verification(schedule_results: List[ScheduleResult],
                                     inventory_before: Inventory,
                                     inventory_after: Inventory,
                                     output_dir: str = "reports") -> str:
        """
        批量验收报表：输出每个订单的
        排程顺序、消耗原片、消耗余料、新增余料、最终库存面积、未满足明细
        适合复核紧急插单前后的变化
        """
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(output_dir, f"batch_verification_{timestamp}.txt")
        csv_file = os.path.join(output_dir, f"batch_verification_{timestamp}.csv")

        lines = []
        lines.append("=" * 130)
        lines.append(" " * 45 + "批量验收报表")
        lines.append("=" * 130)
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("-" * 130)

        lines.append(f"\n【库存变化概览】")
        lines.append(f"  初始库存面积: {inventory_before.total_area / 1e6:.4f} m² "
                      f"(原片 {len(inventory_before.originals)} 块, 余料 {len(inventory_before.remnants)} 块)")
        lines.append(f"  最终库存面积: {inventory_after.total_area / 1e6:.4f} m² "
                      f"(原片 {len(inventory_after.originals)} 块, 余料 {len(inventory_after.remnants)} 块)")
        diff = inventory_after.total_area - inventory_before.total_area
        lines.append(f"  面积变化: {diff / 1e6:+.4f} m²")

        total_input = 0
        total_produced = 0
        total_new_rem = 0

        lines.append(f"\n【各订单排程明细】")
        header = (f"{'#':<4} {'订单号':<12} {'类型':<8} "
                  f"{'原片数':<8} {'余料数':<8} {'投入面积':<14} "
                  f"{'已生产面积':<14} {'新余料面积':<14} {'利用率':<10} {'未满足块数':<12}")
        lines.append("-" * 130)
        lines.append(header)
        lines.append("-" * 130)

        for idx, sr in enumerate(schedule_results):
            input_area = (sr.total_original_area + sr.total_remnant_used_area) / 1e6
            produced_area = sr.total_product_area / 1e6
            new_rem_area = sr.total_remnant_generated / 1e6
            unful = sum(p.quantity for p in sr.unfulfilled_products)
            mark = "紧急" if sr.order.is_urgent else "普通"
            total_input += sr.total_original_area + sr.total_remnant_used_area
            total_produced += sr.total_product_area
            total_new_rem += sr.total_remnant_generated

            lines.append(
                f"{idx + 1:<4} {sr.order.id:<12} {mark:<8} "
                f"{len(sr.used_originals):<8} {len(sr.used_remnants):<8} {input_area:<14.4f} "
                f"{produced_area:<14.4f} {new_rem_area:<14.4f} {sr.overall_utilization * 100:<10.2f} {unful:<12}"
            )

        lines.append("-" * 130)
        lines.append(
            f"{'':<4} {'合计':<12} {'':<8} "
            f"{sum(len(sr.used_originals) for sr in schedule_results):<8} "
            f"{sum(len(sr.used_remnants) for sr in schedule_results):<8} "
            f"{total_input / 1e6:<14.4f} "
            f"{total_produced / 1e6:<14.4f} {total_new_rem / 1e6:<14.4f} "
            f"{(total_produced / total_input * 100) if total_input > 0 else 0:<10.2f} "
            f"{sum(sum(p.quantity for p in sr.unfulfilled_products) for sr in schedule_results):<12}"
        )

        expected_final = inventory_before.total_area - total_input + total_new_rem
        lines.append(f"\n【面积守恒校验】")
        lines.append(f"  初始库存 - 总投入 + 新余料 = {inventory_before.total_area / 1e6:.4f} - {total_input / 1e6:.4f} + {total_new_rem / 1e6:.4f} = {expected_final / 1e6:.4f} m²")
        lines.append(f"  实际最终库存面积 = {inventory_after.total_area / 1e6:.4f} m²")
        ok = abs(expected_final - inventory_after.total_area) < 1
        lines.append(f"  守恒校验: {'✅ 通过' if ok else '❌ 失败'}")

        lines.append("\n【各订单详细未满足明细】")
        for sr in schedule_results:
            if sr.unfulfilled_products:
                lines.append(f"\n  订单 {sr.order.id}:")
                for p in sr.unfulfilled_products:
                    area = p.area / 1e6
                    lines.append(f"    - {p.length:.0f}×{p.width:.0f}×{p.thickness:.0f}mm × {p.quantity}块 ({p.quantity * area:.4f} m²)")

        lines.append("\n【最终库存明细】")
        inv_lines = ReportGenerator.generate_inventory_report(inventory_after).split('\n')
        for line in inv_lines:
            lines.append("  " + line)

        lines.append("\n" + "=" * 130)
        content = '\n'.join(lines)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(content)

        with open(csv_file, 'w', encoding='utf-8-sig') as f:
            f.write("批量验收报表\n")
            f.write(f"生成时间,{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("排程顺序,订单号,类型,原片数,余料数,投入面积(m²),已生产面积(m²),新余料面积(m²),利用率(%),未满足块数\n")
            for idx, sr in enumerate(schedule_results):
                input_area = (sr.total_original_area + sr.total_remnant_used_area) / 1e6
                produced_area = sr.total_product_area / 1e6
                new_rem_area = sr.total_remnant_generated / 1e6
                unful = sum(p.quantity for p in sr.unfulfilled_products)
                mark = "紧急" if sr.order.is_urgent else "普通"
                f.write(f"{idx + 1},{sr.order.id},{mark},{len(sr.used_originals)},{len(sr.used_remnants)},{input_area:.4f},{produced_area:.4f},{new_rem_area:.4f},{sr.overall_utilization * 100:.2f},{unful}\n")

            f.write("\n面积守恒校验\n")
            f.write(f"初始库存(m²),{inventory_before.total_area / 1e6:.4f}\n")
            f.write(f"总投入(m²),{total_input / 1e6:.4f}\n")
            f.write(f"总新产生余料(m²),{total_new_rem / 1e6:.4f}\n")
            f.write(f"预期最终(m²),{expected_final / 1e6:.4f}\n")
            f.write(f"实际最终(m²),{inventory_after.total_area / 1e6:.4f}\n")
            f.write(f"守恒校验,{'通过' if ok else '失败'}\n")

            f.write("\n未满足明细\n")
            f.write("订单号,尺寸(mm),厚度(mm),未满足块数,未满足面积(m²)\n")
            for sr in schedule_results:
                for p in sr.unfulfilled_products:
                    area = p.quantity * p.area / 1e6
                    f.write(f"{sr.order.id},{p.length:.0f}×{p.width:.0f},{p.thickness:.0f},{p.quantity},{area:.4f}\n")

        return report_file

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
        content.append(f"{'订单号':<15} {'产品面积(m²)':<15} {'原片消耗(m²)':<15} {'余料消耗(m²)':<15} {'利用率(%)':<12} {'未满足块数':<12}")
        content.append("-" * 84)
        
        for sr in schedule_results:
            product_area = sr.total_product_area / 1e6
            original_area = sr.total_original_area / 1e6
            remnant_area = sr.total_remnant_used_area / 1e6
            util = sr.overall_utilization * 100
            unful = sum(p.quantity for p in sr.unfulfilled_products)
            content.append(f"{sr.order.id:<15} {product_area:<15.4f} {original_area:<15.4f} {remnant_area:<15.4f} {util:<12.2f} {unful:<12}")
        
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
            csv_path = os.path.join(output_dir, f"order_{sr.order.id}_{timestamp}.csv")
            ReportGenerator.export_csv(sr, csv_path)
        
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
            total_demand_area = schedule_result.order.total_product_area() / 1e6
            total_produced_area = schedule_result.total_product_area / 1e6
            total_unfulfilled_area = sum(p.area for p in schedule_result.unfulfilled_products) / 1e6
            total_original_area = schedule_result.total_original_area / 1e6
            total_remnant_used = schedule_result.total_remnant_used_area / 1e6
            total_remnant_gen = schedule_result.total_remnant_generated / 1e6
            total_input = total_original_area + total_remnant_used
            overall_util = schedule_result.overall_utilization
            fulfillment_rate = (total_produced_area / total_demand_area * 100) if total_demand_area > 0 else 0
            
            f.write(f"订单需求总面积,{total_demand_area:.4f},平方米\n")
            f.write(f"实际生产总面积,{total_produced_area:.4f},平方米\n")
            f.write(f"未满足产品面积,{total_unfulfilled_area:.4f},平方米\n")
            f.write(f"消耗原片总面积,{total_original_area:.4f},平方米\n")
            f.write(f"消耗余料总面积,{total_remnant_used:.4f},平方米\n")
            f.write(f"总投入面积,{total_input:.4f},平方米\n")
            f.write(f"产生余料总面积,{total_remnant_gen:.4f},平方米\n")
            f.write(f"订单满足率,{fulfillment_rate:.2f},%\n")
            f.write(f"综合利用率(基于实际生产),{overall_util * 100:.2f},%\n")
            f.write("\n")

            f.write("按产品规格汇总对账\n")
            f.write("规格(mm),厚度(mm),需求块数,已生产块数,未满足块数,需求面积(m²),已生产面积(m²),未满足面积(m²)\n")
            spec_summary = ReportGenerator._summarize_products_by_spec(schedule_result)
            for s in spec_summary:
                f.write(f"{s['length']:.0f}×{s['width']:.0f},{s['thickness']:.0f},{s['demand_qty']},{s['produced_qty']},{s['unfulfilled_qty']},{s['demand_area']:.4f},{s['produced_area']:.4f},{s['unfulfilled_area']:.4f}\n")
            f.write("\n")
            
            f.write("原片消耗明细\n")
            f.write("编号,尺寸(mm),厚度(mm),数量,面积(m²),利用率(%)\n")
            for cr in schedule_result.cutting_results:
                sheet = cr.original_sheet
                area = sheet.area / 1e6
                f.write(f"{sheet.id},{sheet.length}×{sheet.width},{sheet.thickness},1,{area:.4f},{cr.utilization_rate*100:.2f}\n")
            f.write("\n")

            if schedule_result.used_remnants:
                f.write("余料消耗明细\n")
                f.write("编号,尺寸(mm),厚度(mm),数量,面积(m²)\n")
                for rem in schedule_result.used_remnants:
                    area = rem.area / 1e6
                    f.write(f"{rem.id},{rem.length}×{rem.width},{rem.thickness},1,{area:.4f}\n")
                f.write("\n")
            
            if schedule_result.new_remnants:
                f.write("新产生余料明细\n")
                f.write("编号,尺寸(mm),厚度(mm),数量,面积(m²),位置(x,y)\n")
                for rem in schedule_result.new_remnants:
                    area = rem.area / 1e6
                    f.write(f"{rem.id},{rem.length}×{rem.width},{rem.thickness},1,{area:.4f},({rem.x:.0f},{rem.y:.0f})\n")
                f.write("\n")
            
            if schedule_result.unfulfilled_products:
                f.write("未满足产品明细\n")
                f.write("尺寸(mm),厚度(mm),需求量(块),单块面积(m²),未满足面积(m²),已生产块数,已生产面积(m²)\n")
                for s in spec_summary:
                    if s['unfulfilled_qty'] > 0:
                        f.write(f"{s['length']:.0f}×{s['width']:.0f},{s['thickness']:.0f},{s['unfulfilled_qty']},{s['unit_area']:.4f},{s['unfulfilled_area']:.4f},{s['produced_qty']},{s['produced_area']:.4f}\n")
        
        return filepath
