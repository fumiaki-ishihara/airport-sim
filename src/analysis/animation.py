"""Animation generation for simulation visualization."""

from typing import Dict, List, Optional, Tuple
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter

# 日本語フォント設定
matplotlib.rcParams['font.family'] = ['Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

from ..simulation.engine import SimulationResult, PositionSnapshot
from .heatmap import HeatmapGenerator


class AnimationGenerator:
    """Generate animations from simulation results."""
    
    def __init__(
        self,
        layout_image_path: Optional[str] = None,
        image_size: Tuple[int, int] = (800, 1000),
        fps: int = 10,
    ):
        """
        Initialize animation generator.
        
        Args:
            layout_image_path: Path to background layout image
            image_size: Size of output if no layout image
            fps: Frames per second for animation
        """
        self.layout_image_path = layout_image_path
        self.fps = fps
        
        if layout_image_path and Path(layout_image_path).exists():
            self.background = Image.open(layout_image_path)
            self.image_size = self.background.size
        else:
            self.background = None
            self.image_size = image_size
    
    def generate_animation(
        self,
        result: SimulationResult,
        nodes: Dict[str, Dict],
        areas: Dict[str, Dict],
        output_path: str,
        format: str = "mp4",
        speed_factor: float = 60.0,
        max_frames: int = 1000,
    ) -> str:
        """
        Generate animation from simulation results.
        
        Args:
            result: Simulation result
            nodes: Node coordinates
            areas: Area polygons
            output_path: Path for output animation
            format: Output format ('mp4' or 'gif')
            speed_factor: Speedup factor (e.g., 60 = 1 sim minute = 1 sec video)
            max_frames: Maximum number of frames
        
        Returns:
            Path to output animation
        """
        snapshots = result.position_snapshots
        
        if not snapshots:
            # Create empty animation
            fig, ax = plt.subplots(figsize=(10, 12))
            ax.text(0.5, 0.5, "データがありません", ha='center', va='center', transform=ax.transAxes)
            plt.savefig(output_path.replace('.mp4', '.png').replace('.gif', '.png'))
            plt.close()
            return output_path
        
        # Subsample frames if needed
        if len(snapshots) > max_frames:
            step = len(snapshots) // max_frames
            snapshots = snapshots[::step]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 12))
        
        # Initialize
        def init():
            ax.set_xlim(0, self.image_size[0])
            ax.set_ylim(self.image_size[1], 0)
            return []
        
        # Animation function
        def animate(frame_idx):
            ax.clear()
            
            snapshot = snapshots[frame_idx]
            
            # Draw background
            if self.background:
                ax.imshow(self.background, extent=[0, self.image_size[0], self.image_size[1], 0])
            else:
                ax.set_facecolor('#e8e8e8')
            
            # Draw areas
            for area_name, area_data in areas.items():
                polygon = area_data.get('polygon', [])
                if polygon:
                    # Count passengers in this area
                    pax_in_area = sum(
                        g['group_size'] for g in snapshot.groups
                        if self._point_in_polygon(g['x'], g['y'], polygon)
                    )
                    
                    # Color based on occupancy
                    alpha = min(0.3 + pax_in_area * 0.05, 0.8)
                    color = 'lightcoral' if pax_in_area > 10 else 'lightblue'
                    
                    poly = patches.Polygon(
                        polygon,
                        closed=True,
                        facecolor=color,
                        edgecolor='navy',
                        linewidth=1.5,
                        alpha=alpha,
                    )
                    ax.add_patch(poly)
                    
                    # Label
                    center_x = np.mean([p[0] for p in polygon])
                    center_y = np.mean([p[1] for p in polygon])
                    ax.text(
                        center_x, center_y - 15,
                        f"{area_data.get('note', area_name)[:6]}",
                        ha='center', va='bottom',
                        fontsize=8, alpha=0.7,
                    )
                    ax.text(
                        center_x, center_y + 10,
                        f"{pax_in_area}人",
                        ha='center', va='top',
                        fontsize=10, fontweight='bold',
                    )
            
            # Draw nodes
            for node_name, node_data in nodes.items():
                x, y = node_data.get('x', 0), node_data.get('y', 0)
                ax.plot(x, y, 's', markersize=12, color='darkgray', alpha=0.6)
                ax.text(
                    x, y - 20,
                    node_data.get('note', node_name)[:8],
                    ha='center', va='bottom',
                    fontsize=7, alpha=0.8,
                )
            
            # Draw passenger groups
            for group in snapshot.groups:
                x, y = group['x'], group['y']
                size = group['group_size']
                
                # Size and color based on group size
                marker_size = 80 + size * 50
                color = 'red' if size == 1 else 'orange' if size <= 2 else 'yellow'
                
                ax.scatter(
                    x, y,
                    s=marker_size,
                    c=color,
                    alpha=0.8,
                    edgecolors='black',
                    linewidths=1,
                    zorder=10,
                )
                
                # Show group size
                if size > 1:
                    ax.text(
                        x, y,
                        str(size),
                        ha='center', va='center',
                        fontsize=8, fontweight='bold',
                        zorder=11,
                    )
            
            # Time display
            total_seconds = snapshot.time
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            
            ax.set_title(
                f"シミュレーション時刻: {hours:02d}:{minutes:02d}:{seconds:02d}  |  "
                f"旅客グループ数: {len(snapshot.groups)}  |  "
                f"総人数: {sum(g['group_size'] for g in snapshot.groups)}",
                fontsize=11,
                fontweight='bold',
            )
            
            ax.set_xlim(0, self.image_size[0])
            ax.set_ylim(self.image_size[1], 0)
            ax.set_aspect('equal')
            
            return []
        
        # Create animation
        anim = FuncAnimation(
            fig,
            animate,
            init_func=init,
            frames=len(snapshots),
            interval=1000 / self.fps,
            blit=True,
        )
        
        # Save animation
        if format.lower() == 'gif':
            writer = PillowWriter(fps=self.fps)
            anim.save(output_path, writer=writer)
        else:
            try:
                writer = FFMpegWriter(fps=self.fps, metadata={'title': 'Airport Simulation'})
                anim.save(output_path, writer=writer)
            except Exception as e:
                # Fallback to GIF if FFMpeg not available
                gif_path = output_path.replace('.mp4', '.gif')
                writer = PillowWriter(fps=self.fps)
                anim.save(gif_path, writer=writer)
                output_path = gif_path
        
        plt.close()
        
        return output_path
    
    def _point_in_polygon(self, x: float, y: float, polygon: List[List[float]]) -> bool:
        """Check if point is inside polygon using ray casting."""
        n = len(polygon)
        if n < 3:
            return False
        
        inside = False
        j = n - 1
        
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            
            j = i
        
        return inside
    
    def generate_queue_chart(
        self,
        result: SimulationResult,
        output_path: str,
        resample_interval: float = 60,
    ) -> str:
        """
        Generate queue length time series chart.
        
        Args:
            result: Simulation result
            output_path: Path for output image
            resample_interval: Resampling interval in seconds
        
        Returns:
            Path to output image
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        axes = axes.flatten()
        
        resources = ['checkin_kiosk', 'checkin_counter', 'tag_kiosk', 'drop_point']
        titles = ['チェックインキオスク', 'チェックインカウンター', 'タグ発券機', 'ドロップポイント']
        
        for ax, resource, title in zip(axes, resources, titles):
            history = result.queue_histories.get(resource, [])
            
            if history:
                times = [s.time / 60 for s in history]  # Convert to minutes
                queue_pax = [s.queue_pax_count for s in history]
                
                ax.fill_between(times, queue_pax, alpha=0.3)
                ax.plot(times, queue_pax, linewidth=1)
                ax.set_xlabel('時間 (分)')
                ax.set_ylabel('待ち人数')
                ax.set_title(title)
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, 'データなし', ha='center', va='center', transform=ax.transAxes)
                ax.set_title(title)
        
        plt.suptitle('工程別待ち人数の推移', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def generate_comparison_chart(
        self,
        comparison_data: List[Dict],
        output_path: str,
    ) -> str:
        """
        Generate scenario comparison chart.
        
        Args:
            comparison_data: List of {scenario_name, stats} dictionaries
            output_path: Path for output image
        
        Returns:
            Path to output image
        """
        if not comparison_data:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, 'データなし', ha='center', va='center', transform=ax.transAxes)
            plt.savefig(output_path)
            plt.close()
            return output_path
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        axes = axes.flatten()
        
        scenarios = [d.get('scenario_name', f'Scenario {i}') for i, d in enumerate(comparison_data)]
        processes = ['checkin_kiosk', 'checkin_counter', 'tag_kiosk', 'drop_point']
        titles = ['チェックインキオスク', 'チェックインカウンター', 'タグ発券機', 'ドロップポイント']
        
        for ax, process, title in zip(axes, processes, titles):
            means = []
            p95s = []
            
            for d in comparison_data:
                stats = d.get('stats', {}).get(process, {})
                means.append(stats.get('mean', 0))
                p95s.append(stats.get('p95', 0))
            
            x = np.arange(len(scenarios))
            width = 0.35
            
            ax.bar(x - width/2, means, width, label='平均', alpha=0.8)
            ax.bar(x + width/2, p95s, width, label='95%ile', alpha=0.8)
            
            ax.set_ylabel('待ち時間 (秒)')
            ax.set_title(title)
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.legend()
            ax.grid(True, alpha=0.3, axis='y')
        
        plt.suptitle('シナリオ別待ち時間比較', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path


