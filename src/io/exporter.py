"""Result export utilities."""

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import asdict

from ..simulation.engine import SimulationResult
from ..models.passenger import PassengerGroup


class ResultExporter:
    """Exports simulation results to various formats."""
    
    def __init__(self, output_dir: str):
        """
        Initialize exporter.
        
        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_stats_summary(
        self,
        result: SimulationResult,
        filename: str = "stats_summary.csv",
    ) -> str:
        """
        Export statistics summary to CSV.
        
        Args:
            result: Simulation result
            filename: Output filename
        
        Returns:
            Path to output file
        """
        import numpy as np
        
        groups = result.completed_groups
        
        if not groups:
            # Empty results
            output_path = self.output_dir / filename
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['process', 'mean_wait_sec', 'p95_wait_sec', 'max_wait_sec', 'count'])
            return str(output_path)
        
        # Calculate statistics for each process
        stats = {}
        
        # Check-in (kiosk)
        kiosk_waits = [g.checkin_wait_time for g in groups 
                       if g.checkin_wait_time is not None and g.checkin_type.value == 'kiosk']
        if kiosk_waits:
            stats['checkin_kiosk'] = self._calc_stats(kiosk_waits)
        
        # Check-in (counter)
        counter_waits = [g.checkin_wait_time for g in groups 
                         if g.checkin_wait_time is not None and g.checkin_type.value == 'counter']
        if counter_waits:
            stats['checkin_counter'] = self._calc_stats(counter_waits)
        
        # Baggage counter (手荷物カウンター)
        baggage_counter_waits = [g.baggage_counter_wait_time for g in groups 
                                  if g.baggage_counter_wait_time is not None]
        if baggage_counter_waits:
            stats['baggage_counter'] = self._calc_stats(baggage_counter_waits)
        
        # Tag kiosk (セルフ預け入れ用)
        tag_waits = [g.tag_wait_time for g in groups if g.tag_wait_time is not None]
        if tag_waits:
            stats['tag_kiosk'] = self._calc_stats(tag_waits)
        
        # Drop point (セルフ預け入れ用)
        drop_waits = [g.drop_wait_time for g in groups if g.drop_wait_time is not None]
        if drop_waits:
            stats['drop_point'] = self._calc_stats(drop_waits)
        
        # Total process time
        total_times = [g.total_process_time for g in groups if g.total_process_time is not None]
        if total_times:
            stats['total_process'] = self._calc_stats(total_times)
        
        # Write to CSV
        output_path = self.output_dir / filename
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['process', 'mean_wait_sec', 'p95_wait_sec', 'max_wait_sec', 'count'])
            
            for process, stat in stats.items():
                writer.writerow([
                    process,
                    f"{stat['mean']:.2f}",
                    f"{stat['p95']:.2f}",
                    f"{stat['max']:.2f}",
                    stat['count'],
                ])
        
        return str(output_path)
    
    def _calc_stats(self, values: List[float]) -> Dict:
        """Calculate statistics for a list of values."""
        import numpy as np
        arr = np.array(values)
        return {
            'mean': float(np.mean(arr)),
            'p95': float(np.percentile(arr, 95)),
            'max': float(np.max(arr)),
            'count': len(values),
        }
    
    def export_queue_length(
        self,
        result: SimulationResult,
        filename: str = "queue_length.csv",
    ) -> str:
        """
        Export queue length time series to CSV.
        
        Args:
            result: Simulation result
            filename: Output filename
        
        Returns:
            Path to output file
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['time_sec', 'resource', 'queue_groups', 'queue_pax', 'in_service'])
            
            for resource_name, history in result.queue_histories.items():
                for snapshot in history:
                    writer.writerow([
                        f"{snapshot.time:.2f}",
                        resource_name,
                        snapshot.queue_length,
                        snapshot.queue_pax_count,
                        snapshot.in_service,
                    ])
        
        return str(output_path)
    
    def export_area_occupancy(
        self,
        result: SimulationResult,
        filename: str = "area_occupancy.csv",
    ) -> str:
        """
        Export area occupancy time series to CSV.
        
        Args:
            result: Simulation result
            filename: Output filename
        
        Returns:
            Path to output file
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['time_sec', 'area', 'group_count', 'pax_count'])
            
            for occupancy in result.area_occupancy_history:
                writer.writerow([
                    f"{occupancy.time:.2f}",
                    occupancy.area_name,
                    occupancy.group_count,
                    occupancy.pax_count,
                ])
        
        return str(output_path)
    
    def export_passenger_details(
        self,
        result: SimulationResult,
        filename: str = "passenger_details.csv",
    ) -> str:
        """
        Export detailed passenger group data to CSV.
        
        Args:
            result: Simulation result
            filename: Output filename
        
        Returns:
            Path to output file
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'group_id', 'group_size', 'checkin_type', 'baggage_drop_type',
                'arrival_time', 'departure_time',
                'checkin_wait', 'baggage_counter_wait', 'tag_wait', 'drop_wait', 'total_time',
            ])
            
            for group in result.completed_groups:
                writer.writerow([
                    group.group_id,
                    group.group_size,
                    group.checkin_type.value,
                    group.baggage_drop_type.value,
                    f"{group.arrival_time:.2f}",
                    f"{group.departure_time:.2f}",
                    f"{group.checkin_wait_time:.2f}" if group.checkin_wait_time else "",
                    f"{group.baggage_counter_wait_time:.2f}" if group.baggage_counter_wait_time else "",
                    f"{group.tag_wait_time:.2f}" if group.tag_wait_time else "",
                    f"{group.drop_wait_time:.2f}" if group.drop_wait_time else "",
                    f"{group.total_process_time:.2f}" if group.total_process_time else "",
                ])
        
        return str(output_path)
    
    def export_scenario_comparison(
        self,
        results: List[Dict],
        filename: str = "scenario_comparison.csv",
    ) -> str:
        """
        Export scenario comparison results.
        
        Args:
            results: List of {scenario_name, stats} dictionaries
            filename: Output filename
        
        Returns:
            Path to output file
        """
        output_path = self.output_dir / filename
        
        if not results:
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['scenario_name'])
            return str(output_path)
        
        # Collect all stat keys
        all_keys = set()
        for r in results:
            if 'stats' in r:
                for process, stat in r['stats'].items():
                    for key in stat.keys():
                        all_keys.add(f"{process}_{key}")
        
        headers = ['scenario_name', 'total_pax', 'total_groups'] + sorted(all_keys)
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for r in results:
                row = [r.get('scenario_name', ''), r.get('total_pax', 0), r.get('total_groups', 0)]
                
                for key in sorted(all_keys):
                    parts = key.rsplit('_', 1)
                    if len(parts) == 2:
                        process, stat_key = parts
                        value = r.get('stats', {}).get(process, {}).get(stat_key, '')
                        if isinstance(value, float):
                            row.append(f"{value:.2f}")
                        else:
                            row.append(value)
                    else:
                        row.append('')
                
                writer.writerow(row)
        
        return str(output_path)
    
    def export_all(
        self,
        result: SimulationResult,
        prefix: str = "",
    ) -> Dict[str, str]:
        """
        Export all result files.
        
        Args:
            result: Simulation result
            prefix: Optional filename prefix
        
        Returns:
            Dictionary of {type: filepath}
        """
        files = {}
        
        files['stats'] = self.export_stats_summary(
            result, f"{prefix}stats_summary.csv" if prefix else "stats_summary.csv"
        )
        files['queue'] = self.export_queue_length(
            result, f"{prefix}queue_length.csv" if prefix else "queue_length.csv"
        )
        files['area'] = self.export_area_occupancy(
            result, f"{prefix}area_occupancy.csv" if prefix else "area_occupancy.csv"
        )
        files['passengers'] = self.export_passenger_details(
            result, f"{prefix}passenger_details.csv" if prefix else "passenger_details.csv"
        )
        
        return files

