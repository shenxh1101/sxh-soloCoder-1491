from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
import uuid
from datetime import datetime
from copy import deepcopy


class GlassType(Enum):
    ORIGINAL = "original"
    REMNANT = "remnant"
    PRODUCT = "product"


@dataclass
class GlassSheet:
    length: float
    width: float
    thickness: float
    quantity: int = 1
    glass_type: GlassType = GlassType.ORIGINAL
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    x: float = 0.0
    y: float = 0.0
    parent_id: Optional[str] = None

    @property
    def area(self) -> float:
        return self.length * self.width

    def can_fit(self, piece: 'GlassSheet', saw_kerf: float = 0.0) -> bool:
        if self.thickness != piece.thickness:
            return False
        return (self.length >= piece.length + saw_kerf and 
                self.width >= piece.width + saw_kerf)

    def rotate(self) -> 'GlassSheet':
        return GlassSheet(
            length=self.width,
            width=self.length,
            thickness=self.thickness,
            quantity=self.quantity,
            glass_type=self.glass_type,
            id=self.id,
            x=self.x,
            y=self.y,
            parent_id=self.parent_id
        )

    def __repr__(self) -> str:
        return f"[{self.id}] {self.length}×{self.width}×{self.thickness}mm ({self.glass_type.value})"


@dataclass
class Order:
    id: str
    products: List[GlassSheet] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    priority: int = 0
    is_urgent: bool = False

    def total_product_area(self) -> float:
        return sum(p.area * p.quantity for p in self.products)


@dataclass
class CutLine:
    x1: float
    y1: float
    x2: float
    y2: float
    is_primary: bool = True


@dataclass
class CuttingResult:
    original_sheet: GlassSheet
    cut_pieces: List[GlassSheet] = field(default_factory=list)
    remnants: List[GlassSheet] = field(default_factory=list)
    cut_lines: List[CutLine] = field(default_factory=list)
    utilization_rate: float = 0.0

    @property
    def used_area(self) -> float:
        return sum(p.area for p in self.cut_pieces)

    @property
    def remnant_area(self) -> float:
        return sum(r.area for r in self.remnants)

    def calculate_utilization(self) -> float:
        if self.original_sheet.area == 0:
            return 0.0
        self.utilization_rate = self.used_area / self.original_sheet.area
        return self.utilization_rate


@dataclass
class ScheduleResult:
    order: Order
    cutting_results: List[CuttingResult] = field(default_factory=list)
    used_originals: List[GlassSheet] = field(default_factory=list)
    used_remnants: List[GlassSheet] = field(default_factory=list)
    new_remnants: List[GlassSheet] = field(default_factory=list)
    unfulfilled_products: List[GlassSheet] = field(default_factory=list)

    @property
    def total_original_area(self) -> float:
        return sum(s.area for s in self.used_originals)

    @property
    def total_remnant_used_area(self) -> float:
        return sum(s.area for s in self.used_remnants)

    @property
    def total_product_area(self) -> float:
        return sum(p.area for cr in self.cutting_results for p in cr.cut_pieces)

    @property
    def total_remnant_generated(self) -> float:
        return sum(r.area for r in self.new_remnants)

    @property
    def overall_utilization(self) -> float:
        total = self.total_original_area + self.total_remnant_used_area
        if total == 0:
            return 0.0
        return self.total_product_area / total


@dataclass
class Inventory:
    originals: List[GlassSheet] = field(default_factory=list)
    remnants: List[GlassSheet] = field(default_factory=list)
    saw_kerf: float = 3.0
    min_remnant_area: float = 10000.0

    def add_original(self, sheet: GlassSheet) -> None:
        self.originals.append(sheet)

    def add_remnant(self, remnant: GlassSheet) -> None:
        if remnant.area >= self.min_remnant_area:
            remnant.glass_type = GlassType.REMNANT
            self.remnants.append(remnant)

    def remove_original(self, sheet_id: str) -> Optional[GlassSheet]:
        for i, s in enumerate(self.originals):
            if s.id == sheet_id:
                return self.originals.pop(i)
        return None

    def remove_remnant(self, sheet_id: str) -> Optional[GlassSheet]:
        for i, s in enumerate(self.remnants):
            if s.id == sheet_id:
                return self.remnants.pop(i)
        return None

    def get_available_sheets(self, thickness: float) -> Tuple[List[GlassSheet], List[GlassSheet]]:
        remnants = [s for s in self.remnants if s.thickness == thickness]
        originals = [s for s in self.originals if s.thickness == thickness]
        return remnants, originals

    def snapshot(self) -> Dict[str, Any]:
        return {
            'originals': deepcopy(self.originals),
            'remnants': deepcopy(self.remnants),
            'saw_kerf': self.saw_kerf,
            'min_remnant_area': self.min_remnant_area,
        }

    def restore(self, snapshot: Dict[str, Any]) -> None:
        self.originals = deepcopy(snapshot['originals'])
        self.remnants = deepcopy(snapshot['remnants'])
        self.saw_kerf = snapshot['saw_kerf']
        self.min_remnant_area = snapshot['min_remnant_area']

    @property
    def total_area(self) -> float:
        return sum(s.area for s in self.originals) + sum(s.area for s in self.remnants)

    def __repr__(self) -> str:
        return (f"Inventory: {len(self.originals)} original sheets, "
                f"{len(self.remnants)} remnants, saw_kerf={self.saw_kerf}mm, "
                f"total_area={self.total_area:.0f}mm²")
