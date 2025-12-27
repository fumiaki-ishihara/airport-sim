"""Data loading utilities."""

import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

from ..simulation.arrival import DemandSlot, parse_time_to_minutes
from ..simulation.engine import SimulationConfig


class DataLoader:
    """Loads input files for simulation."""
    
    @staticmethod
    def load_demand_csv(file_path: str) -> List[DemandSlot]:
        """
        Load demand CSV file.
        
        Expected format:
        time_slot_start,time_slot_end,pax_count
        06:00,06:30,50
        ...
        
        Args:
            file_path: Path to demand CSV file
        
        Returns:
            List of DemandSlot objects
        """
        slots = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                start_str = row.get('time_slot_start', '').strip()
                end_str = row.get('time_slot_end', '').strip()
                pax_count = int(row.get('pax_count', 0))
                
                if start_str and end_str:
                    start_min = parse_time_to_minutes(start_str)
                    end_min = parse_time_to_minutes(end_str)
                    
                    slots.append(DemandSlot(
                        start_minutes=start_min,
                        end_minutes=end_min,
                        pax_count=pax_count,
                    ))
        
        return slots
    
    @staticmethod
    def load_demand_from_string(content: str) -> List[DemandSlot]:
        """
        Load demand from CSV string content.
        
        Args:
            content: CSV content as string
        
        Returns:
            List of DemandSlot objects
        """
        slots = []
        lines = content.strip().split('\n')
        
        if not lines:
            return slots
        
        reader = csv.DictReader(lines)
        
        for row in reader:
            start_str = row.get('time_slot_start', '').strip()
            end_str = row.get('time_slot_end', '').strip()
            pax_count = int(row.get('pax_count', 0))
            
            if start_str and end_str:
                start_min = parse_time_to_minutes(start_str)
                end_min = parse_time_to_minutes(end_str)
                
                slots.append(DemandSlot(
                    start_minutes=start_min,
                    end_minutes=end_min,
                    pax_count=pax_count,
                ))
        
        return slots
    
    @staticmethod
    def load_layout_json(file_path: str) -> Tuple[Dict[str, Dict], Dict[str, Dict], float]:
        """
        Load layout JSON file.
        
        Expected format:
        {
            "px_per_meter": 10,
            "nodes": {
                "source": {"x": 120, "y": 800, "note": "..."},
                ...
            },
            "areas": {
                "checkin_zone": {
                    "polygon": [[200,700], [600,700], ...],
                    "note": "..."
                },
                ...
            }
        }
        
        Args:
            file_path: Path to layout JSON file
        
        Returns:
            Tuple of (nodes, areas, px_per_meter)
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        nodes = data.get('nodes', {})
        areas = data.get('areas', {})
        px_per_meter = data.get('px_per_meter', 10)
        
        return nodes, areas, px_per_meter
    
    @staticmethod
    def load_layout_from_dict(data: Dict) -> Tuple[Dict[str, Dict], Dict[str, Dict], float]:
        """
        Load layout from dictionary.
        
        Args:
            data: Layout dictionary
        
        Returns:
            Tuple of (nodes, areas, px_per_meter)
        """
        nodes = data.get('nodes', {})
        areas = data.get('areas', {})
        px_per_meter = data.get('px_per_meter', 10)
        
        return nodes, areas, px_per_meter
    
    @staticmethod
    def load_layout_csvs(
        nodes_csv_path: str,
        areas_csv_path: str,
    ) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
        """
        Load layout from CSV files.
        
        Args:
            nodes_csv_path: Path to nodes CSV
            areas_csv_path: Path to areas CSV
        
        Returns:
            Tuple of (nodes, areas)
        """
        nodes = {}
        areas = {}
        
        # Load nodes
        with open(nodes_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = row.get('node_id', '').strip()
                if node_id:
                    nodes[node_id] = {
                        'x': float(row.get('x_px', 0)),
                        'y': float(row.get('y_px', 0)),
                        'note': row.get('note', ''),
                    }
        
        # Load areas
        with open(areas_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                area_name = row.get('area_name', '').strip()
                if area_name:
                    polygon_str = row.get('polygon_px', '')
                    polygon = DataLoader._parse_polygon(polygon_str)
                    areas[area_name] = {
                        'polygon': polygon,
                        'note': row.get('note', ''),
                    }
        
        return nodes, areas
    
    @staticmethod
    def _parse_polygon(polygon_str: str) -> List[List[float]]:
        """
        Parse polygon string (format: x1:y1|x2:y2|...).
        
        Args:
            polygon_str: Polygon string
        
        Returns:
            List of [x, y] coordinates
        """
        if not polygon_str:
            return []
        
        points = []
        for point_str in polygon_str.split('|'):
            if ':' in point_str:
                x, y = point_str.split(':')
                points.append([float(x), float(y)])
        
        return points
    
    @staticmethod
    def load_scenario_yaml(file_path: str) -> SimulationConfig:
        """
        Load scenario YAML file.
        
        Args:
            file_path: Path to scenario YAML file
        
        Returns:
            SimulationConfig object
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return DataLoader.config_from_dict(data)
    
    @staticmethod
    def config_from_dict(data: Dict) -> SimulationConfig:
        """
        Create SimulationConfig from dictionary.
        
        Args:
            data: Configuration dictionary
        
        Returns:
            SimulationConfig object
        """
        arrival = data.get('arrival', {})
        branching = data.get('branching', {})
        group = data.get('group', {})
        capacity = data.get('capacity', {})
        service_time = data.get('service_time', {})
        sampling = data.get('sampling', {})
        
        return SimulationConfig(
            # Arrival
            arrival_df=arrival.get('df', 7),
            arrival_mean_min_before=arrival.get('mean_min_before_departure', 70),
            arrival_scale=arrival.get('scale', 20),
            arrival_range_min=arrival.get('range_min', 20),
            arrival_range_max=arrival.get('range_max', 120),
            
            # Branching
            p_online=branching.get('p_online', 0.3),
            p_kiosk=branching.get('p_kiosk', 0.5),
            p_counter=branching.get('p_counter', 0.2),
            p_baggage=branching.get('p_baggage', 0.5),
            p_baggage_counter=branching.get('p_baggage_counter', 0.4),
            
            # Group
            p_single=group.get('p_single', 0.7),
            group_multi_min=group.get('multi_min', 2),
            group_multi_max=group.get('multi_max', 4),
            
            # Capacity
            capacity_checkin_kiosk=capacity.get('checkin_kiosk', 8),
            capacity_checkin_counter=capacity.get('checkin_counter', 6),
            capacity_baggage_counter=capacity.get('baggage_counter', 4),
            capacity_tag_kiosk=capacity.get('tag_kiosk', 4),
            capacity_drop_point=capacity.get('drop_point', 4),
            
            # Service times
            service_checkin_kiosk_mean=service_time.get('checkin_kiosk', {}).get('mean', 70),
            service_checkin_kiosk_std=service_time.get('checkin_kiosk', {}).get('std', 15),
            service_checkin_counter_mean=service_time.get('checkin_counter', {}).get('mean', 180),
            service_checkin_counter_std=service_time.get('checkin_counter', {}).get('std', 40),
            service_baggage_counter_mean=service_time.get('baggage_counter', {}).get('mean', 150),
            service_baggage_counter_std=service_time.get('baggage_counter', {}).get('std', 35),
            service_tag_kiosk_mean=service_time.get('tag_kiosk', {}).get('mean', 45),
            service_tag_kiosk_std=service_time.get('tag_kiosk', {}).get('std', 10),
            service_drop_point_mean=service_time.get('drop_point', {}).get('mean', 120),
            service_drop_point_std=service_time.get('drop_point', {}).get('std', 30),
            
            # Sampling
            sample_interval_sec=sampling.get('interval_sec', 10),
            
            # Random seed
            random_seed=data.get('random_seed'),
        )
    
    @staticmethod
    def load_scenario_sweep_csv(file_path: str) -> List[Dict]:
        """
        Load scenario sweep CSV for parameter variation.
        
        Args:
            file_path: Path to sweep CSV file
        
        Returns:
            List of scenario parameter dictionaries
        """
        scenarios = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                scenario = {'scenario_name': row.get('scenario_name', '')}
                
                # Parse numeric fields
                for key, value in row.items():
                    if key == 'scenario_name':
                        continue
                    try:
                        if '.' in value:
                            scenario[key] = float(value)
                        else:
                            scenario[key] = int(value)
                    except (ValueError, TypeError):
                        scenario[key] = value
                
                scenarios.append(scenario)
        
        return scenarios
    
    @staticmethod
    def config_from_sweep_row(base_config: SimulationConfig, row: Dict) -> SimulationConfig:
        """
        Create config from sweep row, overriding base config.
        
        Args:
            base_config: Base configuration
            row: Sweep row with override values
        
        Returns:
            New SimulationConfig with overrides
        """
        import copy
        
        # Convert dataclass to dict
        config_dict = {
            'arrival': {
                'df': base_config.arrival_df,
                'mean_min_before_departure': base_config.arrival_mean_min_before,
                'scale': base_config.arrival_scale,
                'range_min': base_config.arrival_range_min,
                'range_max': base_config.arrival_range_max,
            },
            'branching': {
                'p_online': base_config.p_online,
                'p_kiosk': base_config.p_kiosk,
                'p_counter': base_config.p_counter,
                'p_baggage': base_config.p_baggage,
                'p_baggage_counter': base_config.p_baggage_counter,
            },
            'group': {
                'p_single': base_config.p_single,
                'multi_min': base_config.group_multi_min,
                'multi_max': base_config.group_multi_max,
            },
            'capacity': {
                'checkin_kiosk': base_config.capacity_checkin_kiosk,
                'checkin_counter': base_config.capacity_checkin_counter,
                'baggage_counter': base_config.capacity_baggage_counter,
                'tag_kiosk': base_config.capacity_tag_kiosk,
                'drop_point': base_config.capacity_drop_point,
            },
            'service_time': {
                'checkin_kiosk': {
                    'mean': base_config.service_checkin_kiosk_mean,
                    'std': base_config.service_checkin_kiosk_std,
                },
                'checkin_counter': {
                    'mean': base_config.service_checkin_counter_mean,
                    'std': base_config.service_checkin_counter_std,
                },
                'baggage_counter': {
                    'mean': base_config.service_baggage_counter_mean,
                    'std': base_config.service_baggage_counter_std,
                },
                'tag_kiosk': {
                    'mean': base_config.service_tag_kiosk_mean,
                    'std': base_config.service_tag_kiosk_std,
                },
                'drop_point': {
                    'mean': base_config.service_drop_point_mean,
                    'std': base_config.service_drop_point_std,
                },
            },
            'sampling': {
                'interval_sec': base_config.sample_interval_sec,
            },
            'random_seed': base_config.random_seed,
        }
        
        # Apply overrides from row
        field_mapping = {
            'p_online': ('branching', 'p_online'),
            'p_kiosk': ('branching', 'p_kiosk'),
            'p_counter': ('branching', 'p_counter'),
            'p_baggage_counter': ('branching', 'p_baggage_counter'),
            'cap_checkin_kiosk': ('capacity', 'checkin_kiosk'),
            'cap_checkin_counter': ('capacity', 'checkin_counter'),
            'cap_baggage_counter': ('capacity', 'baggage_counter'),
            'cap_tag_kiosk': ('capacity', 'tag_kiosk'),
            'cap_drop_point': ('capacity', 'drop_point'),
            'mean_checkin_kiosk_sec': ('service_time', 'checkin_kiosk', 'mean'),
            'mean_checkin_counter_sec': ('service_time', 'checkin_counter', 'mean'),
            'mean_baggage_counter_sec': ('service_time', 'baggage_counter', 'mean'),
            'mean_tag_kiosk_sec': ('service_time', 'tag_kiosk', 'mean'),
            'mean_drop_point_sec': ('service_time', 'drop_point', 'mean'),
            'arrival_df': ('arrival', 'df'),
            'arrival_mean_min_before_departure': ('arrival', 'mean_min_before_departure'),
            'arrival_scale': ('arrival', 'scale'),
        }
        
        for key, value in row.items():
            if key in field_mapping:
                path = field_mapping[key]
                if len(path) == 2:
                    config_dict[path[0]][path[1]] = value
                elif len(path) == 3:
                    config_dict[path[0]][path[1]][path[2]] = value
        
        return DataLoader.config_from_dict(config_dict)

