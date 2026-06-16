from typing import List, Dict, Tuple, Optional
from models import GlassSheet, Order, Inventory, ScheduleResult, CuttingResult, GlassType
from cutting_algorithm import find_best_packing
from copy import deepcopy


class RemnantMatcher:
    def __init__(self, saw_kerf: float = 3.0):
        self.saw_kerf = saw_kerf

    def find_best_remnant(self, 
                           product: GlassSheet, 
                           remnants: List[GlassSheet]) -> Optional[GlassSheet]:
        candidates = []
        
        for remnant in remnants:
            if remnant.thickness != product.thickness:
                continue
                
            if remnant.can_fit(product, self.saw_kerf):
                candidates.append(remnant)
                continue
                
            rotated = product.rotate()
            if remnant.can_fit(rotated, self.saw_kerf):
                candidates.append(remnant)
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda r: r.area)
        return candidates[0]

    def match_remnants_to_products(self,
                                    remnants: List[GlassSheet],
                                    products: List[GlassSheet]) -> Tuple[Dict[str, List[GlassSheet]], List[GlassSheet]]:
        remnant_usage: Dict[str, List[GlassSheet]] = {}
        unmatched_products: List[GlassSheet] = []
        
        available_remnants = deepcopy(remnants)
        
        for product in products:
            if product.quantity <= 0:
                continue
                
            remaining_qty = product.quantity
            
            while remaining_qty > 0:
                best_remnant = self.find_best_remnant(product, available_remnants)
                
                if best_remnant is None:
                    break
                    
                result = find_best_packing(best_remnant, [product], self.saw_kerf)
                
                if result.cut_pieces:
                    if best_remnant.id not in remnant_usage:
                        remnant_usage[best_remnant.id] = []
                    remnant_usage[best_remnant.id].append(result.cut_pieces[0])
                    remaining_qty -= len(result.cut_pieces)
                    
                    available_remnants = [r for r in available_remnants if r.id != best_remnant.id]
                    
                    for rem in result.remnants:
                        if rem.area > 10000:
                            available_remnants.append(rem)
                else:
                    break
            
            if remaining_qty > 0:
                remaining_product = GlassSheet(
                    length=product.length,
                    width=product.width,
                    thickness=product.thickness,
                    quantity=remaining_qty,
                    glass_type=GlassType.PRODUCT,
                    id=product.id
                )
                unmatched_products.append(remaining_product)
        
        return remnant_usage, unmatched_products


class ProductionScheduler:
    def __init__(self, inventory: Inventory):
        self.inventory = inventory
        self.remnant_matcher = RemnantMatcher(inventory.saw_kerf)
        self.scheduled_orders: List[ScheduleResult] = []
        self.scheduled_order_ids: List[str] = []

    def process_order(self, order: Order) -> ScheduleResult:
        result = ScheduleResult(order=order)
        
        products_by_thickness = self._group_by_thickness(order.products)
        
        for thickness, products in products_by_thickness.items():
            remnants, originals = self.inventory.get_available_sheets(thickness)
            
            remnant_usage, unmatched = self.remnant_matcher.match_remnants_to_products(
                remnants, products
            )
            
            for rem_id, cut_pieces in remnant_usage.items():
                rem = self.inventory.remove_remnant(rem_id)
                if rem:
                    result.used_remnants.append(rem)
                    
                    cut_result = CuttingResult(
                        original_sheet=rem,
                        cut_pieces=cut_pieces
                    )
                    cut_result.calculate_utilization()
                    result.cutting_results.append(cut_result)
            
            current_products = unmatched
            
            while current_products:
                best_sheet_idx = self._select_best_sheet(originals, current_products)
                
                if best_sheet_idx is None:
                    result.unfulfilled_products.extend(current_products)
                    break
                    
                sheet = originals.pop(best_sheet_idx)
                self.inventory.remove_original(sheet.id)
                
                cut_result = find_best_packing(
                    sheet, current_products, self.inventory.saw_kerf
                )
                
                if not cut_result.cut_pieces:
                    result.unfulfilled_products.extend(current_products)
                    self.inventory.add_original(sheet)
                    break
                
                result.cutting_results.append(cut_result)
                result.used_originals.append(sheet)
                
                for rem in cut_result.remnants:
                    if rem.area >= self.inventory.min_remnant_area:
                        self.inventory.add_remnant(rem)
                        result.new_remnants.append(rem)
                
                current_products = self._update_remaining_products(
                    current_products, cut_result.cut_pieces
                )
        
        self.scheduled_orders.append(result)
        self.scheduled_order_ids.append(order.id)
        
        return result

    def _group_by_thickness(self, products: List[GlassSheet]) -> Dict[float, List[GlassSheet]]:
        groups: Dict[float, List[GlassSheet]] = {}
        
        for product in products:
            t = product.thickness
            if t not in groups:
                groups[t] = []
            groups[t].append(product)
        
        for t in groups:
            groups[t].sort(key=lambda p: p.area, reverse=True)
        
        return groups

    def _select_best_sheet(self, 
                            sheets: List[GlassSheet], 
                            products: List[GlassSheet]) -> Optional[int]:
        if not sheets:
            return None
            
        best_idx = None
        best_util = -1
        
        for i, sheet in enumerate(sheets):
            result = find_best_packing(sheet, products, self.inventory.saw_kerf)
            if result.utilization_rate > best_util and result.cut_pieces:
                best_util = result.utilization_rate
                best_idx = i
        
        return best_idx

    def _update_remaining_products(self, 
                                    products: List[GlassSheet],
                                    cut_pieces: List[GlassSheet]) -> List[GlassSheet]:
        remaining: List[GlassSheet] = []
        
        cut_dict = {}
        for piece in cut_pieces:
            key = (piece.length, piece.width, piece.thickness)
            if key not in cut_dict:
                cut_dict[key] = 0
            cut_dict[key] += 1
        
        for product in products:
            key = (product.length, product.width, product.thickness)
            alt_key = (product.width, product.length, product.thickness)
            
            cut_count = cut_dict.get(key, 0) + cut_dict.get(alt_key, 0)
            remaining_qty = product.quantity - cut_count
            
            if remaining_qty > 0:
                remaining.append(GlassSheet(
                    length=product.length,
                    width=product.width,
                    thickness=product.thickness,
                    quantity=remaining_qty,
                    glass_type=GlassType.PRODUCT,
                    id=product.id
                ))
        
        return remaining

    def insert_urgent_order(self, urgent_order: Order) -> Tuple[ScheduleResult, List[ScheduleResult]]:
        urgent_order.is_urgent = True
        
        affected_orders: List[ScheduleResult] = []
        affected_sheets: List[GlassSheet] = []
        
        for schedule in self.scheduled_orders:
            if schedule.unfulfilled_products:
                affected_orders.append(schedule)
                affected_sheets.extend(schedule.used_originals)
                affected_sheets.extend(schedule.used_remnants)
                
                for sheet in schedule.used_originals:
                    self.inventory.add_original(sheet)
                for rem in schedule.used_remnants:
                    self.inventory.add_remnant(rem)
                for rem in schedule.new_remnants:
                    self.inventory.remove_remnant(rem.id)
        
        for schedule in affected_orders:
            self.scheduled_orders.remove(schedule)
            self.scheduled_order_ids.remove(schedule.order.id)
        
        urgent_result = self.process_order(urgent_order)
        
        rescheduled = []
        for schedule in affected_orders:
            new_result = self.process_order(schedule.order)
            rescheduled.append(new_result)
        
        return urgent_result, rescheduled

    def get_schedule_summary(self) -> Dict:
        total_original_used = sum(s.total_original_area for s in self.scheduled_orders)
        total_remnant_used = sum(s.total_remnant_used_area for s in self.scheduled_orders)
        total_product = sum(s.total_product_area for s in self.scheduled_orders)
        total_remnant_gen = sum(s.total_remnant_generated for s in self.scheduled_orders)
        
        total_input = total_original_used + total_remnant_used
        overall_util = total_product / total_input if total_input > 0 else 0
        
        return {
            'orders_count': len(self.scheduled_orders),
            'total_original_area': total_original_used,
            'total_remnant_used_area': total_remnant_used,
            'total_product_area': total_product,
            'total_remnant_generated': total_remnant_gen,
            'overall_utilization': overall_util
        }
