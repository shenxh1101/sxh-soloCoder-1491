from typing import List, Tuple, Optional
from models import GlassSheet, CuttingResult, CutLine, GlassType
from dataclasses import dataclass


@dataclass
class HorizontalSegment:
    y: float
    x_start: float
    x_end: float

    def length(self) -> float:
        return self.x_end - self.x_start


class HorizontalLine:
    def __init__(self, y: float, segments: List[HorizontalSegment] = None):
        self.y = y
        self.segments = segments or []

    def lowest_segment(self) -> Optional[HorizontalSegment]:
        if not self.segments:
            return None
        return min(self.segments, key=lambda s: s.x_start)


class BottomLeftAlgorithm:
    def __init__(self, saw_kerf: float = 3.0):
        self.saw_kerf = saw_kerf

    def pack(self, 
             sheet: GlassSheet, 
             pieces: List[GlassSheet]) -> CuttingResult:
        result = CuttingResult(original_sheet=sheet)
        sheet_length = sheet.length
        sheet_width = sheet.width
        
        segments = [HorizontalSegment(y=0, x_start=0, x_end=sheet_length)]
        cut_lines: List[CutLine] = []
        placed_pieces: List[GlassSheet] = []
        remaining_pieces = pieces.copy()
        
        for piece in pieces:
            if piece.quantity <= 0:
                continue
                
            for _ in range(piece.quantity):
                placed = self._try_place_piece(
                    piece, segments, sheet_length, sheet_width, 
                    placed_pieces, cut_lines
                )
                if placed:
                    remaining_pieces.remove(piece) if piece in remaining_pieces else None
                else:
                    piece_rotated = piece.rotate()
                    placed = self._try_place_piece(
                        piece_rotated, segments, sheet_length, sheet_width,
                        placed_pieces, cut_lines
                    )
                    if not placed:
                        break
        
        result.cut_pieces = placed_pieces
        result.remnants = self._calculate_remnants(
            segments, sheet_length, sheet_width, sheet.thickness, sheet.id
        )
        result.cut_lines = cut_lines
        result.calculate_utilization()
        
        return result

    def _try_place_piece(self, 
                         piece: GlassSheet,
                         segments: List[HorizontalSegment],
                         sheet_length: float,
                         sheet_width: float,
                         placed_pieces: List[GlassSheet],
                         cut_lines: List[CutLine]) -> bool:
        piece_len = piece.length + self.saw_kerf
        piece_wid = piece.width + self.saw_kerf
        
        for i, seg in enumerate(segments):
            if seg.length() >= piece_len and seg.y + piece_wid <= sheet_width + self.saw_kerf:
                placed_piece = GlassSheet(
                    length=piece.length,
                    width=piece.width,
                    thickness=piece.thickness,
                    glass_type=GlassType.PRODUCT,
                    x=seg.x_start,
                    y=seg.y,
                    parent_id=piece.id
                )
                placed_pieces.append(placed_piece)
                
                cut_lines.append(CutLine(
                    x1=seg.x_start, y1=seg.y,
                    x2=seg.x_start + piece.length, y2=seg.y,
                    is_primary=True
                ))
                cut_lines.append(CutLine(
                    x1=seg.x_start + piece.length, y1=seg.y,
                    x2=seg.x_start + piece.length, y2=seg.y + piece.width,
                    is_primary=False
                ))
                cut_lines.append(CutLine(
                    x1=seg.x_start, y1=seg.y + piece.width,
                    x2=seg.x_start + piece.length, y2=seg.y + piece.width,
                    is_primary=True
                ))
                cut_lines.append(CutLine(
                    x1=seg.x_start, y1=seg.y,
                    x2=seg.x_start, y2=seg.y + piece.width,
                    is_primary=False
                ))
                
                self._update_segments(segments, i, seg, piece_len, piece_wid)
                return True
        
        return False

    def _update_segments(self, 
                         segments: List[HorizontalSegment],
                         seg_idx: int,
                         seg: HorizontalSegment,
                         piece_len: float,
                         piece_wid: float) -> None:
        if seg.length() > piece_len:
            segments[seg_idx] = HorizontalSegment(
                y=seg.y,
                x_start=seg.x_start + piece_len,
                x_end=seg.x_end
            )
        else:
            segments.pop(seg_idx)
        
        new_seg = HorizontalSegment(
            y=seg.y + piece_wid - self.saw_kerf,
            x_start=seg.x_start,
            x_end=seg.x_start + piece_len
        )
        
        inserted = False
        for i, s in enumerate(segments):
            if s.y > new_seg.y:
                segments.insert(i, new_seg)
                inserted = True
                break
        if not inserted:
            segments.append(new_seg)
        
        self._merge_segments(segments)

    def _merge_segments(self, segments: List[HorizontalSegment]) -> None:
        if len(segments) < 2:
            return
        
        segments.sort(key=lambda s: (s.y, s.x_start))
        
        i = 0
        while i < len(segments) - 1:
            curr = segments[i]
            next_seg = segments[i + 1]
            
            if abs(curr.y - next_seg.y) < 0.001 and curr.x_end >= next_seg.x_start:
                merged = HorizontalSegment(
                    y=curr.y,
                    x_start=curr.x_start,
                    x_end=max(curr.x_end, next_seg.x_end)
                )
                segments[i] = merged
                segments.pop(i + 1)
            else:
                i += 1

    def _calculate_remnants(self,
                            segments: List[HorizontalSegment],
                            sheet_length: float,
                            sheet_width: float,
                            thickness: float,
                            parent_id: str) -> List[GlassSheet]:
        remnants = []
        
        for seg in segments:
            rem_len = seg.x_end - seg.x_start
            rem_wid = sheet_width - seg.y
            
            if rem_len > self.saw_kerf and rem_wid > self.saw_kerf:
                remnant = GlassSheet(
                    length=rem_len - self.saw_kerf,
                    width=rem_wid - self.saw_kerf,
                    thickness=thickness,
                    glass_type=GlassType.REMNANT,
                    x=seg.x_start,
                    y=seg.y,
                    parent_id=parent_id
                )
                if remnant.area > 0:
                    remnants.append(remnant)
        
        return remnants


class LowestHorizontalLineAlgorithm:
    def __init__(self, saw_kerf: float = 3.0):
        self.saw_kerf = saw_kerf

    def pack(self, 
             sheet: GlassSheet, 
             pieces: List[GlassSheet]) -> CuttingResult:
        result = CuttingResult(original_sheet=sheet)
        sheet_length = sheet.length
        sheet_width = sheet.width
        
        horizontal_lines: List[HorizontalLine] = [
            HorizontalLine(y=0, segments=[HorizontalSegment(y=0, x_start=0, x_end=sheet_length)])
        ]
        
        cut_lines: List[CutLine] = []
        placed_pieces: List[GlassSheet] = []
        
        expanded_pieces = []
        for p in pieces:
            if p.quantity > 0:
                expanded_pieces.extend([p] * p.quantity)
        
        expanded_pieces.sort(key=lambda p: p.length * p.width, reverse=True)
        
        for piece in expanded_pieces:
            placements = []
            
            for orientation in [piece, piece.rotate()]:
                p_len = orientation.length + self.saw_kerf
                p_wid = orientation.width + self.saw_kerf
                
                for hl in horizontal_lines:
                    for seg in hl.segments:
                        if seg.length() >= p_len and hl.y + p_wid <= sheet_width + self.saw_kerf:
                            placements.append((hl.y, seg.x_start, orientation, seg))
                            break
            
            if placements:
                placements.sort(key=lambda x: (x[0], x[1]))
                best_y, best_x, best_piece, best_seg = placements[0]
                
                placed_piece = GlassSheet(
                    length=best_piece.length,
                    width=best_piece.width,
                    thickness=best_piece.thickness,
                    glass_type=GlassType.PRODUCT,
                    x=best_x,
                    y=best_y,
                    parent_id=piece.id
                )
                placed_pieces.append(placed_piece)
                
                p_len = best_piece.length + self.saw_kerf
                p_wid = best_piece.width + self.saw_kerf
                
                cut_lines.append(CutLine(
                    x1=best_x, y1=best_y,
                    x2=best_x + best_piece.length, y2=best_y,
                    is_primary=True
                ))
                cut_lines.append(CutLine(
                    x1=best_x + best_piece.length, y1=best_y,
                    x2=best_x + best_piece.length, y2=best_y + best_piece.width,
                    is_primary=False
                ))
                cut_lines.append(CutLine(
                    x1=best_x, y1=best_y + best_piece.width,
                    x2=best_x + best_piece.length, y2=best_y + best_piece.width,
                    is_primary=True
                ))
                cut_lines.append(CutLine(
                    x1=best_x, y1=best_y,
                    x2=best_x, y2=best_y + best_piece.width,
                    is_primary=False
                ))
                
                self._update_horizontal_lines(
                    horizontal_lines, best_y, best_seg, p_len, p_wid
                )
        
        result.cut_pieces = placed_pieces
        result.remnants = self._calculate_remnants(
            horizontal_lines, sheet_length, sheet_width, sheet.thickness, sheet.id
        )
        result.cut_lines = cut_lines
        result.calculate_utilization()
        
        return result

    def _update_horizontal_lines(self,
                                  horizontal_lines: List[HorizontalLine],
                                  y_pos: float,
                                  used_seg: HorizontalSegment,
                                  piece_len: float,
                                  piece_wid: float) -> None:
        hl_idx = next(i for i, hl in enumerate(horizontal_lines) if abs(hl.y - y_pos) < 0.001)
        hl = horizontal_lines[hl_idx]
        
        seg_idx = hl.segments.index(used_seg)
        
        if used_seg.length() > piece_len:
            hl.segments[seg_idx] = HorizontalSegment(
                y=y_pos,
                x_start=used_seg.x_start + piece_len,
                x_end=used_seg.x_end
            )
        else:
            hl.segments.pop(seg_idx)
        
        if not hl.segments:
            horizontal_lines.pop(hl_idx)
        
        new_y = y_pos + piece_wid - self.saw_kerf
        new_seg = HorizontalSegment(
            y=new_y,
            x_start=used_seg.x_start,
            x_end=used_seg.x_start + piece_len
        )
        
        target_hl = None
        for hl in horizontal_lines:
            if abs(hl.y - new_y) < 0.001:
                target_hl = hl
                break
        
        if target_hl is None:
            target_hl = HorizontalLine(y=new_y)
            horizontal_lines.append(target_hl)
            horizontal_lines.sort(key=lambda h: h.y)
        
        target_hl.segments.append(new_seg)
        self._merge_segments(target_hl.segments)

    def _merge_segments(self, segments: List[HorizontalSegment]) -> None:
        if len(segments) < 2:
            return
        
        segments.sort(key=lambda s: s.x_start)
        
        i = 0
        while i < len(segments) - 1:
            curr = segments[i]
            next_seg = segments[i + 1]
            
            if curr.x_end >= next_seg.x_start:
                merged = HorizontalSegment(
                    y=curr.y,
                    x_start=curr.x_start,
                    x_end=max(curr.x_end, next_seg.x_end)
                )
                segments[i] = merged
                segments.pop(i + 1)
            else:
                i += 1

    def _calculate_remnants(self,
                            horizontal_lines: List[HorizontalLine],
                            sheet_length: float,
                            sheet_width: float,
                            thickness: float,
                            parent_id: str) -> List[GlassSheet]:
        remnants = []
        
        for hl in horizontal_lines:
            for seg in hl.segments:
                rem_len = seg.x_end - seg.x_start
                rem_wid = sheet_width - hl.y
                
                if rem_len > self.saw_kerf and rem_wid > self.saw_kerf:
                    remnant = GlassSheet(
                        length=rem_len - self.saw_kerf,
                        width=rem_wid - self.saw_kerf,
                        thickness=thickness,
                        glass_type=GlassType.REMNANT,
                        x=seg.x_start,
                        y=hl.y,
                        parent_id=parent_id
                    )
                    if remnant.area > 0:
                        remnants.append(remnant)
        
        return remnants


def find_best_packing(sheet: GlassSheet,
                      pieces: List[GlassSheet],
                      saw_kerf: float = 3.0) -> CuttingResult:
    bl_algo = BottomLeftAlgorithm(saw_kerf)
    lhl_algo = LowestHorizontalLineAlgorithm(saw_kerf)
    
    bl_result = bl_algo.pack(sheet, pieces)
    lhl_result = lhl_algo.pack(sheet, pieces)
    
    return max([bl_result, lhl_result], key=lambda r: r.utilization_rate)
