#!/usr/bin/env python3
"""
空港混雑シミュレーション CLI エントリポイント

Usage:
    # 単一シナリオ実行
    python run_simulation.py --scenario config/scenario_base.yaml --demand data/demand.csv
    
    # パラメータスイープ実行
    python run_simulation.py --sweep config/scenario_sweep.csv --demand data/demand.csv
    
    # アニメーション出力付き
    python run_simulation.py --scenario config/scenario_base.yaml --demand data/demand.csv --animation
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import asdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.io.loader import DataLoader
from src.io.exporter import ResultExporter
from src.simulation.engine import SimulationEngine, SimulationConfig
from src.simulation.arrival import DemandSlot
from src.analysis.statistics import StatisticsCalculator
from src.analysis.heatmap import HeatmapGenerator
from src.analysis.animation import AnimationGenerator


def run_single_simulation(
    config: SimulationConfig,
    demand_slots: List[DemandSlot],
    nodes: Dict,
    areas: Dict,
    output_dir: str,
    layout_image: Optional[str] = None,
    generate_animation: bool = False,
    animation_format: str = "gif",
    scenario_name: str = "",
) -> Dict:
    """
    Run a single simulation.
    
    Args:
        config: Simulation configuration
        demand_slots: Demand slots
        nodes: Node coordinates
        areas: Area polygons
        output_dir: Output directory
        layout_image: Path to layout image
        generate_animation: Whether to generate animation
        animation_format: Animation format (mp4/gif)
        scenario_name: Name for this scenario
    
    Returns:
        Dictionary with results summary
    """
    print(f"\n{'='*60}")
    print(f"シミュレーション開始: {scenario_name or 'default'}")
    print(f"{'='*60}")
    
    # Initialize engine
    engine = SimulationEngine(
        config=config,
        nodes=nodes,
        areas=areas,
    )
    
    # Run simulation
    print("シミュレーション実行中...")
    result = engine.run(demand_slots)
    
    # Calculate statistics
    print("統計計算中...")
    stats_calc = StatisticsCalculator(result)
    process_stats = stats_calc.calculate_process_stats()
    queue_stats = stats_calc.calculate_queue_stats()
    overall_stats = stats_calc.calculate_overall_stats()
    
    # Print summary
    print(f"\n--- 結果サマリー ---")
    print(f"総グループ数: {overall_stats.total_groups}")
    print(f"総旅客数: {overall_stats.total_passengers}")
    print(f"シミュレーション時間: {result.simulation_duration_sec / 60:.1f} 分")
    
    print(f"\n工程別待ち時間 (秒):")
    for name, stats in process_stats.items():
        print(f"  {name}: 平均={stats.mean_wait:.1f}, 95%={stats.p95_wait:.1f}, 最大={stats.max_wait:.1f}")
    
    # Export results
    print("\n結果をエクスポート中...")
    prefix = f"{scenario_name}_" if scenario_name else ""
    exporter = ResultExporter(output_dir)
    files = exporter.export_all(result, prefix)
    
    # Generate heatmap
    print("ヒートマップ生成中...")
    heatmap_gen = HeatmapGenerator(
        layout_image_path=layout_image,
        image_size=(800, 1000),
    )
    heatmap_path = str(Path(output_dir) / f"{prefix}heatmap.png")
    heatmap_gen.generate_occupancy_heatmap(
        result=result,
        nodes=nodes,
        areas=areas,
        output_path=heatmap_path,
        title=f"滞留人数ヒートマップ - {scenario_name}" if scenario_name else "滞留人数ヒートマップ",
    )
    files['heatmap'] = heatmap_path
    
    # Generate queue chart
    anim_gen = AnimationGenerator(
        layout_image_path=layout_image,
    )
    queue_chart_path = str(Path(output_dir) / f"{prefix}queue_chart.png")
    anim_gen.generate_queue_chart(result, queue_chart_path)
    files['queue_chart'] = queue_chart_path
    
    # Generate animation if requested
    if generate_animation:
        print("アニメーション生成中 (時間がかかる場合があります)...")
        anim_path = str(Path(output_dir) / f"{prefix}animation.{animation_format}")
        anim_gen.generate_animation(
            result=result,
            nodes=nodes,
            areas=areas,
            output_path=anim_path,
            format=animation_format,
        )
        files['animation'] = anim_path
    
    print(f"\n出力ファイル:")
    for file_type, file_path in files.items():
        print(f"  {file_type}: {file_path}")
    
    # Return summary for comparison
    return {
        'scenario_name': scenario_name,
        'total_groups': overall_stats.total_groups,
        'total_pax': overall_stats.total_passengers,
        'stats': {
            name: {
                'mean': stats.mean_wait,
                'p95': stats.p95_wait,
                'max': stats.max_wait,
                'count': stats.count,
            }
            for name, stats in process_stats.items()
        },
        'files': files,
    }


def run_sweep(
    sweep_csv: str,
    demand_slots: List[DemandSlot],
    nodes: Dict,
    areas: Dict,
    output_dir: str,
    layout_image: Optional[str] = None,
    generate_animation: bool = False,
) -> List[Dict]:
    """
    Run parameter sweep simulations.
    
    Args:
        sweep_csv: Path to sweep CSV file
        demand_slots: Demand slots
        nodes: Node coordinates
        areas: Area polygons
        output_dir: Output directory
        layout_image: Path to layout image
        generate_animation: Whether to generate animation
    
    Returns:
        List of result summaries
    """
    # Load sweep configurations
    sweep_rows = DataLoader.load_scenario_sweep_csv(sweep_csv)
    
    if not sweep_rows:
        print("スイープファイルにシナリオがありません")
        return []
    
    print(f"\n{len(sweep_rows)} シナリオをスイープ実行します")
    
    base_config = SimulationConfig()
    results = []
    
    for i, row in enumerate(sweep_rows):
        scenario_name = row.get('scenario_name', f'scenario_{i}')
        
        # Create config from sweep row
        config = DataLoader.config_from_sweep_row(base_config, row)
        
        # Run simulation
        result = run_single_simulation(
            config=config,
            demand_slots=demand_slots,
            nodes=nodes,
            areas=areas,
            output_dir=output_dir,
            layout_image=layout_image,
            generate_animation=generate_animation and i == 0,  # Only first scenario
            scenario_name=scenario_name,
        )
        
        results.append(result)
    
    # Export comparison
    print("\n比較結果をエクスポート中...")
    exporter = ResultExporter(output_dir)
    comparison_path = exporter.export_scenario_comparison(results)
    print(f"比較CSV: {comparison_path}")
    
    # Generate comparison chart
    anim_gen = AnimationGenerator(layout_image_path=layout_image)
    comparison_chart_path = str(Path(output_dir) / "comparison_chart.png")
    anim_gen.generate_comparison_chart(results, comparison_chart_path)
    print(f"比較チャート: {comparison_chart_path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="空港混雑シミュレーション CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Input files
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        help="シナリオYAMLファイルのパス",
    )
    parser.add_argument(
        "--sweep",
        type=str,
        help="パラメータスイープCSVファイルのパス",
    )
    parser.add_argument(
        "--demand", "-d",
        type=str,
        required=True,
        help="需要CSVファイルのパス",
    )
    parser.add_argument(
        "--layout-json", "-l",
        type=str,
        help="レイアウトJSONファイルのパス",
    )
    parser.add_argument(
        "--layout-image", "-i",
        type=str,
        help="レイアウト画像ファイルのパス",
    )
    parser.add_argument(
        "--nodes-csv",
        type=str,
        help="ノードCSVファイルのパス",
    )
    parser.add_argument(
        "--areas-csv",
        type=str,
        help="エリアCSVファイルのパス",
    )
    
    # Output
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output",
        help="出力ディレクトリ (default: output)",
    )
    
    # Options
    parser.add_argument(
        "--animation", "-a",
        action="store_true",
        help="アニメーションを生成",
    )
    parser.add_argument(
        "--format", "-f",
        type=str,
        choices=["mp4", "gif"],
        default="gif",
        help="アニメーション形式 (default: gif)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="乱数シード",
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.scenario and not args.sweep:
        parser.error("--scenario または --sweep を指定してください")
    
    # Load demand
    print(f"需要データを読み込み中: {args.demand}")
    demand_slots = DataLoader.load_demand_csv(args.demand)
    total_pax = sum(slot.pax_count for slot in demand_slots)
    print(f"  {len(demand_slots)} スロット, 総旅客数: {total_pax}")
    
    # Load layout
    nodes = {}
    areas = {}
    
    if args.layout_json:
        print(f"レイアウトJSONを読み込み中: {args.layout_json}")
        nodes, areas, _ = DataLoader.load_layout_json(args.layout_json)
    elif args.nodes_csv and args.areas_csv:
        print(f"レイアウトCSVを読み込み中: {args.nodes_csv}, {args.areas_csv}")
        nodes, areas = DataLoader.load_layout_csvs(args.nodes_csv, args.areas_csv)
    else:
        # Use default layout
        print("デフォルトレイアウトを使用")
        nodes = {
            "source": {"x": 120, "y": 800, "note": "旅客生成点"},
            "checkin_kiosk": {"x": 300, "y": 650, "note": "チェックインキオスク"},
            "checkin_counter": {"x": 520, "y": 640, "note": "チェックインカウンター"},
            "baggage_counter": {"x": 650, "y": 520, "note": "手荷物カウンター"},
            "tag_kiosk": {"x": 340, "y": 520, "note": "タグ発券機"},
            "drop_point": {"x": 520, "y": 500, "note": "ドロップポイント"},
            "security_gate": {"x": 700, "y": 250, "note": "保安検査入口"},
        }
        areas = {
            "checkin_zone": {"polygon": [[200,700],[600,700],[600,580],[200,580]], "note": "チェックイン"},
            "baggage_counter_zone": {"polygon": [[600,560],[750,560],[750,460],[600,460]], "note": "手荷物カウンター"},
            "tag_zone": {"polygon": [[250,560],[450,560],[450,460],[250,460]], "note": "タグ発券"},
            "drop_zone": {"polygon": [[450,560],[600,560],[600,430],[450,430]], "note": "ドロップ"},
            "security_front": {"polygon": [[620,320],[760,320],[760,220],[620,220]], "note": "保安入口前"},
        }
    
    print(f"  ノード数: {len(nodes)}, エリア数: {len(areas)}")
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run simulation
    if args.sweep:
        # Parameter sweep
        results = run_sweep(
            sweep_csv=args.sweep,
            demand_slots=demand_slots,
            nodes=nodes,
            areas=areas,
            output_dir=str(output_dir),
            layout_image=args.layout_image,
            generate_animation=args.animation,
        )
    else:
        # Single scenario
        if args.scenario:
            print(f"シナリオを読み込み中: {args.scenario}")
            config = DataLoader.load_scenario_yaml(args.scenario)
        else:
            config = SimulationConfig()
        
        if args.seed:
            config.random_seed = args.seed
        
        result = run_single_simulation(
            config=config,
            demand_slots=demand_slots,
            nodes=nodes,
            areas=areas,
            output_dir=str(output_dir),
            layout_image=args.layout_image,
            generate_animation=args.animation,
            animation_format=args.format,
        )
    
    print(f"\n{'='*60}")
    print("シミュレーション完了!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

