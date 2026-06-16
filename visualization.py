from typing import List
from models import GlassSheet, CuttingResult
import os


class CuttingDiagram:
    @staticmethod
    def generate_ascii(cut_result: CuttingResult, scale: float = 0.1) -> str:
        sheet = cut_result.original_sheet
        width = int(sheet.length * scale)
        height = int(sheet.width * scale)
        
        if width < 10 or height < 5:
            scale = max(10 / sheet.length, 5 / sheet.width)
            width = int(sheet.length * scale)
            height = int(sheet.width * scale)
        
        grid = [[' ' for _ in range(width + 1)] for _ in range(height + 1)]
        
        for x in range(width + 1):
            grid[0][x] = '─'
            grid[height][x] = '─'
        for y in range(height + 1):
            grid[y][0] = '│'
            grid[y][width] = '│'
        
        grid[0][0] = '┌'
        grid[0][width] = '┐'
        grid[height][0] = '└'
        grid[height][width] = '┘'
        
        for i, piece in enumerate(cut_result.cut_pieces):
            x1 = int(piece.x * scale)
            y1 = int(piece.y * scale)
            x2 = int((piece.x + piece.length) * scale)
            y2 = int((piece.y + piece.width) * scale)
            
            x1 = max(1, min(x1, width - 1))
            y1 = max(1, min(y1, height - 1))
            x2 = max(1, min(x2, width - 1))
            y2 = max(1, min(y2, height - 1))
            
            for x in range(x1, x2 + 1):
                if grid[y1][x] == ' ':
                    grid[y1][x] = '─'
                if grid[y2][x] == ' ':
                    grid[y2][x] = '─'
            
            for y in range(y1, y2 + 1):
                if grid[y][x1] == ' ':
                    grid[y][x1] = '│'
                if grid[y][x2] == ' ':
                    grid[y][x2] = '│'
            
            if x1 < width and y1 < height:
                if grid[y1][x1] == '─':
                    grid[y1][x1] = '┬'
                elif grid[y1][x1] == '│':
                    grid[y1][x1] = '├'
                else:
                    grid[y1][x1] = '┌'
            
            if x2 < width and y1 < height:
                if grid[y1][x2] == '─':
                    grid[y1][x2] = '┬'
                elif grid[y1][x2] == '│':
                    grid[y1][x2] = '┤'
                else:
                    grid[y1][x2] = '┐'
            
            if x1 < width and y2 < height:
                if grid[y2][x1] == '─':
                    grid[y2][x1] = '┴'
                elif grid[y2][x1] == '│':
                    grid[y2][x1] = '├'
                else:
                    grid[y2][x1] = '└'
            
            if x2 < width and y2 < height:
                if grid[y2][x2] == '─':
                    grid[y2][x2] = '┴'
                elif grid[y2][x2] == '│':
                    grid[y2][x2] = '┤'
                else:
                    grid[y2][x2] = '┘'
            
            label = str(i + 1)
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            if mid_y > 0 and mid_y < height and mid_x > 0 and mid_x < width:
                if grid[mid_y][mid_x] in [' ', '─', '│']:
                    grid[mid_y][mid_x] = label[0]
        
        for i, rem in enumerate(cut_result.remnants):
            x1 = int(rem.x * scale)
            y1 = int(rem.y * scale)
            x2 = int((rem.x + rem.length) * scale)
            y2 = int((rem.y + rem.width) * scale)
            
            x1 = max(1, min(x1, width - 1))
            y1 = max(1, min(y1, height - 1))
            x2 = max(1, min(x2, width - 1))
            y2 = max(1, min(y2, height - 1))
            
            label = f"R{i+1}"
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            if mid_y > 0 and mid_y < height and mid_x > 0 and mid_x < width - 1:
                for j, c in enumerate(label):
                    if mid_x + j < width and grid[mid_y][mid_x + j] in [' ', '─', '│']:
                        grid[mid_y][mid_x + j] = c
        
        diagram_lines = []
        for row in grid:
            diagram_lines.append(''.join(row))
        
        header = f" 切割图纸: {sheet.length}×{sheet.width}×{sheet.thickness}mm "
        diagram_lines.insert(0, '╔' + '═' * (width - 1) + '╗')
        diagram_lines.insert(1, '║' + header.center(width - 1) + '║')
        diagram_lines.insert(2, '╠' + '═' * (width - 1) + '╣')
        
        footer = f" 利用率: {cut_result.utilization_rate*100:.1f}% | 产品: {len(cut_result.cut_pieces)}块 | 余料: {len(cut_result.remnants)}块 "
        diagram_lines.append('╠' + '═' * (width - 1) + '╣')
        diagram_lines.append('║' + footer.center(width - 1) + '║')
        diagram_lines.append('╚' + '═' * (width - 1) + '╝')
        
        legend = " 图例: 1,2...=成品编号 | R1,R2...=余料编号"
        diagram_lines.append(legend)
        
        return '\n'.join(diagram_lines)

    @staticmethod
    def generate_svg(cut_result: CuttingResult, filepath: str, scale: float = 2.0) -> str:
        sheet = cut_result.original_sheet
        width = sheet.length * scale
        height = sheet.width * scale
        
        svg_content = []
        svg_content.append('<?xml version="1.0" encoding="UTF-8"?>')
        svg_content.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width + 40}" height="{height + 80}" viewBox="0 0 {width + 40} {height + 80}">')
        svg_content.append(f'<rect x="20" y="20" width="{width}" height="{height}" fill="#f0f0f0" stroke="#333" stroke-width="3"/>')
        svg_content.append(f'<text x="{width/2 + 20}" y="15" text-anchor="middle" font-family="Arial" font-size="14" font-weight="bold">切割图纸: {sheet.length}×{sheet.width}×{sheet.thickness}mm</text>')
        
        for i, piece in enumerate(cut_result.cut_pieces):
            x = piece.x * scale + 20
            y = piece.y * scale + 20
            w = piece.length * scale
            h = piece.width * scale
            
            svg_content.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#a8e6cf" stroke="#2d8a5e" stroke-width="2"/>')
            svg_content.append(f'<text x="{x + w/2}" y="{y + h/2 + 5}" text-anchor="middle" font-family="Arial" font-size="12" font-weight="bold" fill="#1a5c3a">{i + 1}</text>')
            svg_content.append(f'<text x="{x + w/2}" y="{y + h/2 + 20}" text-anchor="middle" font-family="Arial" font-size="9" fill="#1a5c3a">{int(piece.length)}×{int(piece.width)}</text>')
        
        for i, rem in enumerate(cut_result.remnants):
            x = rem.x * scale + 20
            y = rem.y * scale + 20
            w = rem.length * scale
            h = rem.width * scale
            
            svg_content.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffd3b6" stroke="#c97a3a" stroke-width="2" stroke-dasharray="5,3"/>')
            svg_content.append(f'<text x="{x + w/2}" y="{y + h/2 + 5}" text-anchor="middle" font-family="Arial" font-size="11" font-weight="bold" fill="#994c1a">R{i + 1}</text>')
            svg_content.append(f'<text x="{x + w/2}" y="{y + h/2 + 18}" text-anchor="middle" font-family="Arial" font-size="8" fill="#994c1a">{int(rem.length)}×{int(rem.width)}</text>')
        
        legend_y = height + 45
        svg_content.append(f'<rect x="20" y="{legend_y}" width="20" height="15" fill="#a8e6cf" stroke="#2d8a5e" stroke-width="1"/>')
        svg_content.append(f'<text x="45" y="{legend_y + 12}" font-family="Arial" font-size="10">成品玻璃</text>')
        svg_content.append(f'<rect x="120" y="{legend_y}" width="20" height="15" fill="#ffd3b6" stroke="#c97a3a" stroke-width="1" stroke-dasharray="3,2"/>')
        svg_content.append(f'<text x="145" y="{legend_y + 12}" font-family="Arial" font-size="10">余料</text>')
        
        util_text = f"利用率: {cut_result.utilization_rate*100:.1f}%"
        svg_content.append(f'<text x="{width + 20}" y="{legend_y + 12}" text-anchor="end" font-family="Arial" font-size="10" font-weight="bold">{util_text}</text>')
        
        svg_content.append('</svg>')
        
        full_content = '\n'.join(svg_content)
        
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)
        
        return filepath

    @staticmethod
    def print_detailed_pieces(cut_result: CuttingResult) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append(f"原片: {cut_result.original_sheet}")
        lines.append(f"利用率: {cut_result.utilization_rate * 100:.2f}%")
        lines.append("-" * 60)
        lines.append("成品玻璃列表:")
        lines.append(f"{'编号':<6} {'尺寸(mm)':<15} {'位置(x,y)':<15} {'面积(mm²)':<12}")
        lines.append("-" * 60)
        
        for i, piece in enumerate(cut_result.cut_pieces):
            lines.append(f"{i+1:<6} {piece.length}×{piece.width:<8} ({piece.x:.0f},{piece.y:.0f}){'':<4} {piece.area:<12.0f}")
        
        if cut_result.remnants:
            lines.append("-" * 60)
            lines.append("余料列表:")
            lines.append(f"{'编号':<6} {'尺寸(mm)':<15} {'位置(x,y)':<15} {'面积(mm²)':<12}")
            lines.append("-" * 60)
            
            for i, rem in enumerate(cut_result.remnants):
                lines.append(f"R{i+1:<5} {rem.length}×{rem.width:<8} ({rem.x:.0f},{rem.y:.0f}){'':<4} {rem.area:<12.0f}")
        
        lines.append("=" * 60)
        return '\n'.join(lines)
