"""SimPy resource definitions for airport processes."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import simpy


@dataclass
class QueueSnapshot:
    """Snapshot of queue state at a point in time."""
    
    time: float
    queue_length: int  # Number of groups waiting
    queue_pax_count: int  # Number of passengers waiting (group_size sum)
    in_service: int  # Number of groups being served


@dataclass
class AreaOccupancy:
    """Occupancy data for an area at a point in time."""
    
    time: float
    area_name: str
    group_count: int
    pax_count: int


class MonitoredResource:
    """SimPy Resource with queue monitoring."""
    
    def __init__(
        self,
        env: simpy.Environment,
        name: str,
        capacity: int,
    ):
        """
        Initialize monitored resource.
        
        Args:
            env: SimPy environment
            name: Resource name
            capacity: Number of parallel servers
        """
        self.env = env
        self.name = name
        self.capacity = capacity
        self.resource = simpy.Resource(env, capacity=capacity)
        
        # Queue history
        self.queue_history: List[QueueSnapshot] = []
        
        # Current queue (groups waiting)
        self._current_queue: List[Tuple[int, int]] = []  # (group_id, group_size)
    
    def request(self, group_id: int, group_size: int):
        """
        Request the resource for a group.
        
        Args:
            group_id: ID of the requesting group
            group_size: Size of the requesting group
        
        Returns:
            SimPy request event
        """
        self._current_queue.append((group_id, group_size))
        self._record_snapshot()
        return self.resource.request()
    
    def release(self, request, group_id: int):
        """
        Release the resource after use.
        
        Args:
            request: The SimPy request to release
            group_id: ID of the group releasing
        """
        # Remove from queue tracking
        self._current_queue = [
            (gid, gs) for gid, gs in self._current_queue if gid != group_id
        ]
        self.resource.release(request)
        self._record_snapshot()
    
    def _record_snapshot(self):
        """Record current queue state."""
        queue_groups = len(self.resource.queue)
        queue_pax = sum(
            gs for gid, gs in self._current_queue[:queue_groups]
        ) if queue_groups > 0 else 0
        
        self.queue_history.append(QueueSnapshot(
            time=self.env.now,
            queue_length=queue_groups,
            queue_pax_count=queue_pax,
            in_service=self.resource.count,
        ))
    
    @property
    def current_queue_length(self) -> int:
        """Get current number of groups in queue."""
        return len(self.resource.queue)
    
    @property
    def current_queue_pax(self) -> int:
        """Get current number of passengers in queue."""
        queue_len = len(self.resource.queue)
        return sum(gs for _, gs in self._current_queue[:queue_len])


class AirportResources:
    """Container for all airport resources."""
    
    def __init__(
        self,
        env: simpy.Environment,
        capacity_checkin_kiosk: int = 8,
        capacity_checkin_counter: int = 6,
        capacity_baggage_counter: int = 4,
        capacity_tag_kiosk: int = 4,
        capacity_drop_point: int = 4,
    ):
        """
        Initialize airport resources.
        
        Args:
            env: SimPy environment
            capacity_checkin_kiosk: Number of check-in kiosks
            capacity_checkin_counter: Number of check-in counters (check-in only)
            capacity_baggage_counter: Number of baggage counters (tag + drop combined)
            capacity_tag_kiosk: Number of tag kiosks (for self drop)
            capacity_drop_point: Number of drop points (for self drop)
        """
        self.env = env
        
        self.checkin_kiosk = MonitoredResource(
            env, "checkin_kiosk", capacity_checkin_kiosk
        )
        self.checkin_counter = MonitoredResource(
            env, "checkin_counter", capacity_checkin_counter
        )
        self.baggage_counter = MonitoredResource(
            env, "baggage_counter", capacity_baggage_counter
        )
        self.tag_kiosk = MonitoredResource(
            env, "tag_kiosk", capacity_tag_kiosk
        )
        self.drop_point = MonitoredResource(
            env, "drop_point", capacity_drop_point
        )
        
        # Area occupancy tracking
        self.area_occupancy_history: List[AreaOccupancy] = []
        self._groups_in_area: Dict[str, List[Tuple[int, int]]] = {
            "checkin_zone": [],
            "baggage_counter_zone": [],
            "tag_zone": [],
            "drop_zone": [],
            "security_front": [],
        }
    
    def enter_area(self, area_name: str, group_id: int, group_size: int):
        """Record a group entering an area."""
        if area_name in self._groups_in_area:
            self._groups_in_area[area_name].append((group_id, group_size))
            self._record_area_occupancy(area_name)
    
    def leave_area(self, area_name: str, group_id: int):
        """Record a group leaving an area."""
        if area_name in self._groups_in_area:
            self._groups_in_area[area_name] = [
                (gid, gs) for gid, gs in self._groups_in_area[area_name]
                if gid != group_id
            ]
            self._record_area_occupancy(area_name)
    
    def _record_area_occupancy(self, area_name: str):
        """Record current area occupancy."""
        groups = self._groups_in_area[area_name]
        self.area_occupancy_history.append(AreaOccupancy(
            time=self.env.now,
            area_name=area_name,
            group_count=len(groups),
            pax_count=sum(gs for _, gs in groups),
        ))
    
    def get_all_resources(self) -> Dict[str, MonitoredResource]:
        """Get dictionary of all resources."""
        return {
            "checkin_kiosk": self.checkin_kiosk,
            "checkin_counter": self.checkin_counter,
            "baggage_counter": self.baggage_counter,
            "tag_kiosk": self.tag_kiosk,
            "drop_point": self.drop_point,
        }
    
    def get_current_occupancy(self, area_name: str) -> Tuple[int, int]:
        """Get current (group_count, pax_count) for an area."""
        if area_name in self._groups_in_area:
            groups = self._groups_in_area[area_name]
            return len(groups), sum(gs for _, gs in groups)
        return 0, 0
