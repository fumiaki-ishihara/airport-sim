"""Statistics calculation for simulation results."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from ..simulation.engine import SimulationResult
from ..models.passenger import PassengerGroup, CheckinType, BaggageDropType


@dataclass
class ProcessStats:
    """Statistics for a single process."""
    
    process_name: str
    count: int
    mean_wait: float
    std_wait: float
    p50_wait: float
    p95_wait: float
    max_wait: float
    min_wait: float


@dataclass
class QueueStats:
    """Statistics for queue lengths."""
    
    resource_name: str
    mean_queue_groups: float
    max_queue_groups: int
    mean_queue_pax: float
    max_queue_pax: int


@dataclass
class OverallStats:
    """Overall simulation statistics."""
    
    total_groups: int
    total_passengers: int
    mean_total_time: float
    p95_total_time: float
    max_total_time: float
    
    # Breakdown by check-in type
    online_count: int
    kiosk_count: int
    counter_count: int
    
    # Baggage breakdown
    with_baggage_count: int
    without_baggage_count: int


class StatisticsCalculator:
    """Calculate statistics from simulation results."""
    
    def __init__(self, result: SimulationResult):
        """
        Initialize calculator.
        
        Args:
            result: Simulation result to analyze
        """
        self.result = result
        self.groups = result.completed_groups
    
    def calculate_process_stats(self) -> Dict[str, ProcessStats]:
        """
        Calculate statistics for each process.
        
        Returns:
            Dictionary of process name to ProcessStats
        """
        stats = {}
        
        # Check-in kiosk
        kiosk_waits = [
            g.checkin_wait_time for g in self.groups
            if g.checkin_wait_time is not None and g.checkin_type == CheckinType.KIOSK
        ]
        if kiosk_waits:
            stats['checkin_kiosk'] = self._calc_process_stats('checkin_kiosk', kiosk_waits)
        
        # Check-in counter
        counter_waits = [
            g.checkin_wait_time for g in self.groups
            if g.checkin_wait_time is not None and g.checkin_type == CheckinType.COUNTER
        ]
        if counter_waits:
            stats['checkin_counter'] = self._calc_process_stats('checkin_counter', counter_waits)
        
        # Baggage counter (手荷物カウンター)
        baggage_counter_waits = [
            g.baggage_counter_wait_time for g in self.groups
            if g.baggage_counter_wait_time is not None
        ]
        if baggage_counter_waits:
            stats['baggage_counter'] = self._calc_process_stats('baggage_counter', baggage_counter_waits)
        
        # Tag kiosk (セルフ預け入れ用)
        tag_waits = [g.tag_wait_time for g in self.groups if g.tag_wait_time is not None]
        if tag_waits:
            stats['tag_kiosk'] = self._calc_process_stats('tag_kiosk', tag_waits)
        
        # Drop point (セルフ預け入れ用)
        drop_waits = [g.drop_wait_time for g in self.groups if g.drop_wait_time is not None]
        if drop_waits:
            stats['drop_point'] = self._calc_process_stats('drop_point', drop_waits)
        
        return stats
    
    def _calc_process_stats(self, name: str, waits: List[float]) -> ProcessStats:
        """Calculate stats for a process."""
        arr = np.array(waits)
        return ProcessStats(
            process_name=name,
            count=len(waits),
            mean_wait=float(np.mean(arr)),
            std_wait=float(np.std(arr)),
            p50_wait=float(np.percentile(arr, 50)),
            p95_wait=float(np.percentile(arr, 95)),
            max_wait=float(np.max(arr)),
            min_wait=float(np.min(arr)),
        )
    
    def calculate_queue_stats(self) -> Dict[str, QueueStats]:
        """
        Calculate queue statistics.
        
        Returns:
            Dictionary of resource name to QueueStats
        """
        stats = {}
        
        for resource_name, history in self.result.queue_histories.items():
            if history:
                queue_groups = [s.queue_length for s in history]
                queue_pax = [s.queue_pax_count for s in history]
                
                stats[resource_name] = QueueStats(
                    resource_name=resource_name,
                    mean_queue_groups=float(np.mean(queue_groups)),
                    max_queue_groups=int(np.max(queue_groups)),
                    mean_queue_pax=float(np.mean(queue_pax)),
                    max_queue_pax=int(np.max(queue_pax)),
                )
        
        return stats
    
    def calculate_overall_stats(self) -> OverallStats:
        """
        Calculate overall simulation statistics.
        
        Returns:
            OverallStats object
        """
        total_groups = len(self.groups)
        total_passengers = sum(g.group_size for g in self.groups)
        
        # Total process times
        total_times = [g.total_process_time for g in self.groups if g.total_process_time is not None]
        if total_times:
            arr = np.array(total_times)
            mean_total = float(np.mean(arr))
            p95_total = float(np.percentile(arr, 95))
            max_total = float(np.max(arr))
        else:
            mean_total = p95_total = max_total = 0.0
        
        # Check-in type breakdown
        online_count = sum(1 for g in self.groups if g.checkin_type == CheckinType.ONLINE)
        kiosk_count = sum(1 for g in self.groups if g.checkin_type == CheckinType.KIOSK)
        counter_count = sum(1 for g in self.groups if g.checkin_type == CheckinType.COUNTER)
        
        # Baggage breakdown
        with_baggage = sum(1 for g in self.groups if g.has_baggage)
        without_baggage = total_groups - with_baggage
        
        return OverallStats(
            total_groups=total_groups,
            total_passengers=total_passengers,
            mean_total_time=mean_total,
            p95_total_time=p95_total,
            max_total_time=max_total,
            online_count=online_count,
            kiosk_count=kiosk_count,
            counter_count=counter_count,
            with_baggage_count=with_baggage,
            without_baggage_count=without_baggage,
        )
    
    def get_time_series_queue(
        self,
        resource_name: str,
        resample_interval: float = 60,
    ) -> Tuple[List[float], List[int], List[int]]:
        """
        Get resampled queue time series.
        
        Args:
            resource_name: Name of the resource
            resample_interval: Resampling interval in seconds
        
        Returns:
            Tuple of (times, queue_groups, queue_pax)
        """
        history = self.result.queue_histories.get(resource_name, [])
        
        if not history:
            return [], [], []
        
        # Get time range
        max_time = max(s.time for s in history)
        times = np.arange(0, max_time, resample_interval)
        
        # Resample by taking last value before each time point
        queue_groups = []
        queue_pax = []
        
        for t in times:
            # Find last snapshot before this time
            last_snapshot = None
            for s in history:
                if s.time <= t:
                    last_snapshot = s
                else:
                    break
            
            if last_snapshot:
                queue_groups.append(last_snapshot.queue_length)
                queue_pax.append(last_snapshot.queue_pax_count)
            else:
                queue_groups.append(0)
                queue_pax.append(0)
        
        return times.tolist(), queue_groups, queue_pax
    
    def get_time_series_occupancy(
        self,
        area_name: str,
        resample_interval: float = 60,
    ) -> Tuple[List[float], List[int], List[int]]:
        """
        Get resampled area occupancy time series.
        
        Args:
            area_name: Name of the area
            resample_interval: Resampling interval in seconds
        
        Returns:
            Tuple of (times, group_counts, pax_counts)
        """
        # Filter occupancy for this area
        area_history = [o for o in self.result.area_occupancy_history if o.area_name == area_name]
        
        if not area_history:
            return [], [], []
        
        # Get time range
        max_time = max(o.time for o in area_history)
        times = np.arange(0, max_time, resample_interval)
        
        # Resample
        group_counts = []
        pax_counts = []
        
        for t in times:
            last_occupancy = None
            for o in area_history:
                if o.time <= t:
                    last_occupancy = o
                else:
                    break
            
            if last_occupancy:
                group_counts.append(last_occupancy.group_count)
                pax_counts.append(last_occupancy.pax_count)
            else:
                group_counts.append(0)
                pax_counts.append(0)
        
        return times.tolist(), group_counts, pax_counts

