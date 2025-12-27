"""Heatmap generation for visualization."""

from typing import Dict, List, Optional, Tuple
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap

# 日本語フォント設定
matplotlib.rcParams['font.family'] = ['Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

from ..simulation.engine import SimulationResult, PositionSnapshot


class HeatmapGenerator:
    """Generate heatmaps from simulation results."""
    
    def __init__(
        self,
        layout_image_path: Optional[str] = None,
        image_size: Tuple[int, int] = (800, 1000),
        px_per_meter: float = 10,
    ):
        """
        Initialize heatmap generator.
        
        Args:
            layout_image_path: Path to background layout image
            image_size: Size of output image (width, height) if no layout image
            px_per_meter: Pixels per meter for scaling
        """
        self.layout_image_path = layout_image_path
        self.px_per_meter = px_per_meter
        
        if layout_image_path and Path(layout_image_path).exists():
            self.background = Image.open(layout_image_path)
            self.image_size = self.background.size
        else:
            self.background = None
            self.image_size = image_size
    
    def generate_occupancy_heatmap(
        self,
        result: SimulationResult,
        nodes: Dict[str, Dict],
        areas: Dict[str, Dict],
        output_path: str,
        title: str = "滞留人数ヒートマップ",
        colormap: str = "hot",
    ) -> str:
        """
        Generate occupancy heatmap.
        
        Args:
            result: Simulation result
            nodes: Node coordinates
            areas: Area polygons
            output_path: Path for output image
            title: Plot title
            colormap: Matplotlib colormap name
        
        Returns:
            Path to output image
        """
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 12))
        
        # Draw background
        if self.background:
            ax.imshow(self.background, extent=[0, self.image_size[0], self.image_size[1], 0])
        else:
            ax.set_xlim(0, self.image_size[0])
            ax.set_ylim(self.image_size[1], 0)
            ax.set_facecolor('#f0f0f0')
        
        # Calculate average occupancy for each area
        area_occupancy = self._calculate_average_occupancy(result.area_occupancy_history)
        
        # Get max for normalization
        max_pax = max(area_occupancy.values()) if area_occupancy else 1
        
        # Create colormap
        cmap = plt.get_cmap(colormap)
        
        # Draw areas with occupancy coloring
        for area_name, area_data in areas.items():
            polygon = area_data.get('polygon', [])
            if not polygon:
                continue
            
            # Get occupancy value
            pax = area_occupancy.get(area_name, 0)
            normalized = pax / max_pax if max_pax > 0 else 0
            color = cmap(normalized)
            
            # Create polygon patch
            poly = patches.Polygon(
                polygon,
                closed=True,
                facecolor=color,
                edgecolor='black',
                linewidth=2,
                alpha=0.7,
            )
            ax.add_patch(poly)
            
            # Add label
            center_x = np.mean([p[0] for p in polygon])
            center_y = np.mean([p[1] for p in polygon])
            ax.text(
                center_x, center_y,
                f"{area_name}\n({pax:.0f}人)",
                ha='center', va='center',
                fontsize=10, fontweight='bold',
                color='white' if normalized > 0.5 else 'black',
            )
        
        # Draw nodes
        for node_name, node_data in nodes.items():
            x, y = node_data.get('x', 0), node_data.get('y', 0)
            ax.plot(x, y, 'ko', markersize=8)
            ax.text(x + 10, y, node_name, fontsize=8)
        
        # Add colorbar
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, max_pax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, label='平均滞留人数')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('X (px)')
        ax.set_ylabel('Y (px)')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _calculate_average_occupancy(
        self,
        occupancy_history: List,
    ) -> Dict[str, float]:
        """Calculate time-weighted average occupancy for each area."""
        if not occupancy_history:
            return {}
        
        area_data = {}
        
        for occ in occupancy_history:
            area = occ.area_name
            if area not in area_data:
                area_data[area] = []
            area_data[area].append((occ.time, occ.pax_count))
        
        averages = {}
        for area, data in area_data.items():
            if data:
                # Sort by time
                data.sort(key=lambda x: x[0])
                
                # Calculate time-weighted average
                total_time = 0
                weighted_sum = 0
                
                for i in range(len(data) - 1):
                    duration = data[i + 1][0] - data[i][0]
                    weighted_sum += data[i][1] * duration
                    total_time += duration
                
                averages[area] = weighted_sum / total_time if total_time > 0 else 0
        
        return averages
    
    def generate_snapshot_frame(
        self,
        snapshot: PositionSnapshot,
        nodes: Dict[str, Dict],
        areas: Dict[str, Dict],
        ax: plt.Axes,
    ):
        """
        Draw a single snapshot frame.
        
        Args:
            snapshot: Position snapshot
            nodes: Node coordinates
            areas: Area polygons
            ax: Matplotlib axes
        """
        ax.clear()
        
        # Draw background
        if self.background:
            ax.imshow(self.background, extent=[0, self.image_size[0], self.image_size[1], 0])
        else:
            ax.set_xlim(0, self.image_size[0])
            ax.set_ylim(self.image_size[1], 0)
            ax.set_facecolor('#f0f0f0')
        
        # Draw areas
        for area_name, area_data in areas.items():
            polygon = area_data.get('polygon', [])
            if polygon:
                poly = patches.Polygon(
                    polygon,
                    closed=True,
                    facecolor='lightblue',
                    edgecolor='blue',
                    linewidth=1,
                    alpha=0.3,
                )
                ax.add_patch(poly)
        
        # Draw nodes
        for node_name, node_data in nodes.items():
            x, y = node_data.get('x', 0), node_data.get('y', 0)
            ax.plot(x, y, 's', markersize=10, color='gray', alpha=0.5)
        
        # Draw passenger groups
        for group in snapshot.groups:
            x, y = group['x'], group['y']
            size = group['group_size']
            
            # Size based on group size
            marker_size = 50 + size * 30
            
            ax.scatter(
                x, y,
                s=marker_size,
                c='red',
                alpha=0.7,
                edgecolors='darkred',
                linewidths=1,
            )
        
        # Title with time
        minutes = snapshot.time / 60
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        ax.set_title(f"時刻: {hours:02d}:{mins:02d}", fontsize=12)
        
        ax.set_xlim(0, self.image_size[0])
        ax.set_ylim(self.image_size[1], 0)


