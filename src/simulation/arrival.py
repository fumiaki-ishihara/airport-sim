"""Arrival generation module for passenger groups."""

from typing import Generator, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
import simpy

from ..utils.distributions import TruncatedTDistribution
from ..models.passenger import PassengerGroup, PassengerGroupFactory


@dataclass
class DemandSlot:
    """A time slot with passenger demand."""
    
    start_minutes: float  # Start time in minutes from simulation start
    end_minutes: float  # End time in minutes from simulation start
    pax_count: int  # Number of passengers in this slot
    
    @property
    def duration_minutes(self) -> float:
        """Duration of this slot in minutes."""
        return self.end_minutes - self.start_minutes


class ArrivalGenerator:
    """
    Generates passenger group arrivals based on demand schedule.
    
    Uses truncated t-distribution for arrival times relative to departure.
    """
    
    def __init__(
        self,
        env: simpy.Environment,
        group_factory: PassengerGroupFactory,
        arrival_df: float = 7,
        arrival_mean_min_before: float = 70,
        arrival_scale: float = 20,
        arrival_range_min: float = 20,
        arrival_range_max: float = 120,
        random_state: Optional[int] = None,
    ):
        """
        Initialize arrival generator.
        
        Args:
            env: SimPy environment
            group_factory: Factory for creating passenger groups
            arrival_df: Degrees of freedom for t-distribution
            arrival_mean_min_before: Mean arrival time before departure (minutes)
            arrival_scale: Scale parameter for t-distribution
            arrival_range_min: Minimum minutes before departure
            arrival_range_max: Maximum minutes before departure
            random_state: Random seed for reproducibility
        """
        self.env = env
        self.group_factory = group_factory
        
        # Arrival time distribution (minutes before departure)
        self.arrival_dist = TruncatedTDistribution(
            df=arrival_df,
            loc=arrival_mean_min_before,
            scale=arrival_scale,
            lower=arrival_range_min,
            upper=arrival_range_max,
            random_state=random_state,
        )
        
        self.arrival_range_max = arrival_range_max
        
        # Generated groups for tracking
        self.generated_groups: List[PassengerGroup] = []
        
        if random_state is not None:
            np.random.seed(random_state)
    
    def generate_arrivals_for_slot(
        self,
        slot: DemandSlot,
    ) -> List[PassengerGroup]:
        """
        Generate passenger groups for a demand slot.
        
        The slot's pax_count represents passengers to depart in this time window.
        Arrival times are calculated based on the truncated t-distribution.
        
        Args:
            slot: Demand slot with departure time window and passenger count
        
        Returns:
            List of generated passenger groups
        """
        groups = []
        remaining_pax = slot.pax_count
        
        while remaining_pax > 0:
            # Create a group (factory determines size)
            # Departure time is the midpoint of the slot
            departure_time_min = (slot.start_minutes + slot.end_minutes) / 2
            
            # Calculate arrival time using truncated t-distribution
            # Sample how many minutes before departure they arrive
            min_before_departure = self.arrival_dist.sample_one()
            
            # Calculate actual arrival time (in simulation minutes)
            # arrival_time = departure_time - min_before_departure
            arrival_time_min = departure_time_min - min_before_departure
            
            # Ensure arrival time is not negative
            arrival_time_min = max(0, arrival_time_min)
            
            # Convert to seconds for SimPy
            arrival_time_sec = arrival_time_min * 60
            departure_time_sec = departure_time_min * 60
            
            group = self.group_factory.create_group(
                arrival_time=arrival_time_sec,
                departure_time=departure_time_sec,
            )
            
            groups.append(group)
            remaining_pax -= group.group_size
        
        return groups
    
    def generate_all_arrivals(
        self,
        demand_slots: List[DemandSlot],
    ) -> List[PassengerGroup]:
        """
        Generate all passenger groups for the entire demand schedule.
        
        Args:
            demand_slots: List of demand slots
        
        Returns:
            List of all generated passenger groups, sorted by arrival time
        """
        all_groups = []
        
        for slot in demand_slots:
            if slot.pax_count > 0:
                groups = self.generate_arrivals_for_slot(slot)
                all_groups.extend(groups)
        
        # Sort by arrival time
        all_groups.sort(key=lambda g: g.arrival_time)
        
        self.generated_groups = all_groups
        return all_groups
    
    def arrival_process(
        self,
        groups: List[PassengerGroup],
        process_callback,
    ) -> Generator:
        """
        SimPy process that spawns groups at their arrival times.
        
        Args:
            groups: Pre-generated list of groups (sorted by arrival time)
            process_callback: Function to call for each arriving group
        
        Yields:
            SimPy events
        """
        last_arrival_time = 0
        
        for group in groups:
            # Wait until this group's arrival time
            wait_time = group.arrival_time - last_arrival_time
            if wait_time > 0:
                yield self.env.timeout(wait_time)
            
            # Spawn the group's process
            self.env.process(process_callback(group))
            
            last_arrival_time = group.arrival_time


def parse_time_to_minutes(time_str: str, base_hour: int = 0) -> float:
    """
    Parse time string (HH:MM) to minutes from base hour.
    
    Args:
        time_str: Time in HH:MM format
        base_hour: Base hour (default 0 = midnight)
    
    Returns:
        Minutes from base hour
    """
    parts = time_str.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    
    return (hours - base_hour) * 60 + minutes


