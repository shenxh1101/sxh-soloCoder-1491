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
                                    products: List[GlassSheet],
                                    min_remnant_area: float = 10000.0) -> Tuple[Dict[str, CuttingResult], List[GlassSheet]]:
        remnant_cutting_results: Dict[str, CuttingResult] = {}
        unmatched_products: List[GlassSheet] = []
        
        available_remnants = deepcopy(remnants)
        remaining_products = deepcopy(products)
        
        while remaining_products:
            product = remaining_products[0]
            if product.quantity <= 0:
                remaining_products.pop(0)
                continue
                
            best_remnant = self.find_best_remnant(product, available_remnants)
            
            if best_remnant is None:
                unmatched_products.append(product)
                remaining_products.pop(0)
                continue
            
            all_products_for_remnant = []
            for p in remaining_products:
                if p.thickness == product.thickness and p.quantity > 0:
                    all_products_for_remnant.append(p)
            
            result = find_best_packing(best_remnant, all_products_for_remnant, self.saw_kerf)
            
            if result.cut_pieces:
                remnant_cutting_results[best_remnant.id] = result
                
                cut_dict = {}
                for piece in result.cut_pieces:
                    key = (piece.length, piece.width, piece.thickness)
                    alt_key = (piece.width, piece.length, piece.thickness)
                    if key not in cut_dict:
                        cut_dict[key] = 0
                    cut_dict[key] += 1
                
                new_remaining = []
                for p in remaining_products:
                    if p.thickness != product.thickness:
                        new_remaining.append(p)
                        continue
                        
                    key = (p.length, p.width, p.thickness)
                    alt_key = (p.width, p.length, p.thickness)
                    cut_count = cut_dict.get(key, 0) + cut_dict.get(alt_key, 0)
                    remaining_qty = p.quantity - cut_count
                    
                    if remaining_qty > 0:
                        new_p = GlassSheet(
                            length=p.length,
                            width=p.width,
                            thickness=p.thickness,
                            quantity=remaining_qty,
                            glass_type=GlassType.PRODUCT,
                            id=p.id
                        )
                        new_remaining.append(new_p)
                    elif remaining_qty < 0:
                        new_p = GlassSheet(
                            length=p.length,
                            width=p.width,
                            thickness=p.thickness,
                            quantity=0,
                            glass_type=GlassType.PRODUCT,
                            id=p.id
                        )
                        new_remaining.append(new_p)
                
                remaining_products = new_remaining
                
                available_remnants = [r for r in available_remnants if r.id != best_remnant.id]
                
                for rem in result.remnants:
                    if rem.area >= min_remnant_area:
                        available_remnants.append(rem)
            else:
                unmatched_products.append(product)
                remaining_products.pop(0)
        
        return remnant_cutting_results, unmatched_products


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
            
            remnant_cutting_results, unmatched = self.remnant_matcher.match_remnants_to_products(
                remnants, products, self.inventory.min_remnant_area
            )
            
            for rem_id, cut_result in remnant_cutting_results.items():
                rem = self.inventory.remove_remnant(rem_id)
                if rem:
                    result.used_remnants.append(rem)
                    result.cutting_results.append(cut_result)
                    
                    for rem_piece in cut_result.remnants:
                        if rem_piece.area >= self.inventory.min_remnant_area:
                            self.inventory.add_remnant(rem_piece)
                            result.new_remnants.append(rem_piece)
            
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

    def insert_urgent_order(self, urgent_order: Order) -> Tuple[ScheduleResult, List[ScheduleResult], List[ScheduleResult], List[GlassSheet]]:
        urgent_order.is_urgent = True
        
        all_scheduled_orders = list(self.scheduled_orders)
        affected_original_sheets: List[GlassSheet] = []
        affected_remnant_sheets: List[GlassSheet] = []
        
        for schedule in all_scheduled_orders:
            affected_original_sheets.extend(schedule.used_originals)
            affected_remnant_sheets.extend(schedule.used_remnants)
            
            for sheet in schedule.used_originals:
                self.inventory.add_original(sheet)
            for rem in schedule.used_remnants:
                self.inventory.add_remnant(rem)
            for rem in schedule.new_remnants:
                self.inventory.remove_remnant(rem.id)
        
        self.scheduled_orders.clear()
        self.scheduled_order_ids.clear()
        
        urgent_result = self.process_order(urgent_order)
        
        rescheduled_orders = []
        for schedule in all_scheduled_orders:
            new_result = self.process_order(schedule.order)
            rescheduled_orders.append(new_result)
        
        all_affected_sheets = affected_original_sheets + affected_remnant_sheets
        
        return urgent_result, all_scheduled_orders, rescheduled_orders, all_affected_sheets

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
