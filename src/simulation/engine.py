"""Main simulation engine."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import simpy
import numpy as np

from ..models.passenger import PassengerGroup, PassengerGroupFactory
from ..models.resources import AirportResources, AreaOccupancy
from ..utils.distributions import ServiceTimeDistribution
from .arrival import ArrivalGenerator, DemandSlot
from .processes import PassengerProcess


@dataclass
class SimulationConfig:
    """Configuration for the simulation."""
    
    # Arrival distribution
    arrival_df: float = 7
    arrival_mean_min_before: float = 70
    arrival_scale: float = 20
    arrival_range_min: float = 20
    arrival_range_max: float = 120
    
    # Branching probabilities
    p_online: float = 0.3
    p_kiosk: float = 0.5
    p_counter: float = 0.2
    p_baggage: float = 0.5
    p_baggage_counter: float = 0.4  # 預け荷物ありの人が手荷物カウンターを使う率
    
    # Group size
    p_single: float = 0.7
    group_multi_min: int = 2
    group_multi_max: int = 4
    
    # Capacities
    capacity_checkin_kiosk: int = 8
    capacity_checkin_counter: int = 6
    capacity_baggage_counter: int = 4
    capacity_tag_kiosk: int = 4
    capacity_drop_point: int = 4
    
    # Service times (mean, std in seconds)
    service_checkin_kiosk_mean: float = 70
    service_checkin_kiosk_std: float = 15
    service_checkin_counter_mean: float = 180
    service_checkin_counter_std: float = 40
    service_baggage_counter_mean: float = 150  # タグ発券＋預け入れ一括
    service_baggage_counter_std: float = 35
    service_tag_kiosk_mean: float = 45
    service_tag_kiosk_std: float = 10
    service_drop_point_mean: float = 120
    service_drop_point_std: float = 30
    
    # Sampling
    sample_interval_sec: float = 10
    
    # Random seed
    random_seed: Optional[int] = None


@dataclass
class PositionSnapshot:
    """Snapshot of all group positions at a time."""
    
    time: float
    groups: List[Dict]  # [{group_id, x, y, group_size, node}]


@dataclass
class SimulationResult:
    """Results from a simulation run."""
    
    config: SimulationConfig
    completed_groups: List[PassengerGroup]
    queue_histories: Dict[str, List]
    area_occupancy_history: List[AreaOccupancy]
    position_snapshots: List[PositionSnapshot]
    simulation_duration_sec: float


class SimulationEngine:
    """
    Main simulation engine orchestrating the DES.
    """
    
    def __init__(
        self,
        config: SimulationConfig,
        nodes: Dict[str, Dict],
        areas: Optional[Dict[str, Dict]] = None,
    ):
        """
        Initialize simulation engine.
        
        Args:
            config: Simulation configuration
            nodes: Node coordinates {name: {x, y, note}}
            areas: Area polygons {name: {polygon, note}}
        """
        self.config = config
        self.nodes = nodes
        self.areas = areas or {}
        
        # Will be initialized on run
        self.env: Optional[simpy.Environment] = None
        self.resources: Optional[AirportResources] = None
        self.arrival_gen: Optional[ArrivalGenerator] = None
        self.passenger_process: Optional[PassengerProcess] = None
        
        # Position tracking
        self.position_snapshots: List[PositionSnapshot] = []
        self._active_groups: Dict[int, PassengerGroup] = {}
    
    def _create_service_times(self) -> Dict[str, ServiceTimeDistribution]:
        """Create service time distributions from config."""
        return {
            "checkin_kiosk": ServiceTimeDistribution(
                mean=self.config.service_checkin_kiosk_mean,
                std=self.config.service_checkin_kiosk_std,
            ),
            "checkin_counter": ServiceTimeDistribution(
                mean=self.config.service_checkin_counter_mean,
                std=self.config.service_checkin_counter_std,
            ),
            "baggage_counter": ServiceTimeDistribution(
                mean=self.config.service_baggage_counter_mean,
                std=self.config.service_baggage_counter_std,
            ),
            "tag_kiosk": ServiceTimeDistribution(
                mean=self.config.service_tag_kiosk_mean,
                std=self.config.service_tag_kiosk_std,
            ),
            "drop_point": ServiceTimeDistribution(
                mean=self.config.service_drop_point_mean,
                std=self.config.service_drop_point_std,
            ),
        }
    
    def _position_sampler(self, sample_interval: float, end_time: float):
        """
        Process to sample positions at regular intervals.
        
        Args:
            sample_interval: Sampling interval in seconds
            end_time: End time for sampling
        """
        while self.env.now < end_time:
            # Record current positions of all active groups
            snapshot = PositionSnapshot(
                time=self.env.now,
                groups=[
                    {
                        "group_id": g.group_id,
                        "x": g.current_x,
                        "y": g.current_y,
                        "group_size": g.group_size,
                        "node": g.current_node,
                    }
                    for g in self._active_groups.values()
                ]
            )
            self.position_snapshots.append(snapshot)
            
            yield self.env.timeout(sample_interval)
    
    def _group_process_wrapper(self, group: PassengerGroup):
        """Wrapper to track active groups."""
        self._active_groups[group.group_id] = group
        yield from self.passenger_process.run(group)
        del self._active_groups[group.group_id]
    
    def run(
        self,
        demand_slots: List[DemandSlot],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> SimulationResult:
        """
        Run the simulation.
        
        Args:
            demand_slots: List of demand slots defining passenger arrivals
            progress_callback: Optional callback for progress updates (0-1)
        
        Returns:
            SimulationResult with all collected data
        """
        # Set random seed if specified
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)
        
        # Initialize SimPy environment
        self.env = simpy.Environment()
        
        # Initialize resources
        self.resources = AirportResources(
            env=self.env,
            capacity_checkin_kiosk=self.config.capacity_checkin_kiosk,
            capacity_checkin_counter=self.config.capacity_checkin_counter,
            capacity_baggage_counter=self.config.capacity_baggage_counter,
            capacity_tag_kiosk=self.config.capacity_tag_kiosk,
            capacity_drop_point=self.config.capacity_drop_point,
        )
        
        # Initialize group factory
        group_factory = PassengerGroupFactory(
            p_online=self.config.p_online,
            p_kiosk=self.config.p_kiosk,
            p_counter=self.config.p_counter,
            p_baggage=self.config.p_baggage,
            p_baggage_counter=self.config.p_baggage_counter,
            p_single=self.config.p_single,
            multi_min=self.config.group_multi_min,
            multi_max=self.config.group_multi_max,
        )
        
        # Initialize arrival generator
        self.arrival_gen = ArrivalGenerator(
            env=self.env,
            group_factory=group_factory,
            arrival_df=self.config.arrival_df,
            arrival_mean_min_before=self.config.arrival_mean_min_before,
            arrival_scale=self.config.arrival_scale,
            arrival_range_min=self.config.arrival_range_min,
            arrival_range_max=self.config.arrival_range_max,
            random_state=self.config.random_seed,
        )
        
        # Initialize passenger process handler
        service_times = self._create_service_times()
        self.passenger_process = PassengerProcess(
            env=self.env,
            resources=self.resources,
            service_times=service_times,
            nodes=self.nodes,
        )
        
        # Generate all arrivals
        groups = self.arrival_gen.generate_all_arrivals(demand_slots)
        
        if not groups:
            # No passengers to simulate
            return SimulationResult(
                config=self.config,
                completed_groups=[],
                queue_histories={},
                area_occupancy_history=[],
                position_snapshots=[],
                simulation_duration_sec=0,
            )
        
        # Calculate simulation end time
        # Add buffer after last departure for all passengers to complete
        last_departure = max(g.departure_time for g in groups)
        simulation_end = last_departure + 3600  # 1 hour buffer
        
        # Start arrival process
        self.env.process(
            self.arrival_gen.arrival_process(
                groups,
                self._group_process_wrapper,
            )
        )
        
        # Start position sampler
        self.position_snapshots = []
        self._active_groups = {}
        self.env.process(
            self._position_sampler(
                self.config.sample_interval_sec,
                simulation_end,
            )
        )
        
        # Run simulation
        self.env.run(until=simulation_end)
        
        # Collect results
        queue_histories = {}
        for name, resource in self.resources.get_all_resources().items():
            queue_histories[name] = resource.queue_history
        
        return SimulationResult(
            config=self.config,
            completed_groups=self.passenger_process.completed_groups,
            queue_histories=queue_histories,
            area_occupancy_history=self.resources.area_occupancy_history,
            position_snapshots=self.position_snapshots,
            simulation_duration_sec=self.env.now,
        )
