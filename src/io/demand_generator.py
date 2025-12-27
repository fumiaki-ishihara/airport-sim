"""Demand generation from flight schedule."""

from typing import List, Dict, Tuple
from collections import defaultdict
import csv
from pathlib import Path

from ..simulation.arrival import DemandSlot


def generate_demand_from_flights(
    departure_times: List[str],
    pax_per_flight: int = 150,
    time_slot_minutes: int = 30,
    start_hour: int = 6,
    end_hour: int = 22,
) -> List[DemandSlot]:
    """
    Generate time-slotted demand from a list of departure times.
    
    Args:
        departure_times: List of departure times in HH:MM format
        pax_per_flight: Number of passengers per flight
        time_slot_minutes: Time slot duration in minutes
        start_hour: Start hour for demand (default: 6)
        end_hour: End hour for demand (default: 22)
    
    Returns:
        List of DemandSlot objects
    """
    # Count flights per time slot
    slot_counts = defaultdict(int)
    
    for time_str in departure_times:
        try:
            hour, minute = map(int, time_str.split(':'))
            # Calculate slot start
            slot_minute = (minute // time_slot_minutes) * time_slot_minutes
            slot_key = f"{hour:02d}:{slot_minute:02d}"
            slot_counts[slot_key] += 1
        except (ValueError, IndexError):
            continue
    
    # Generate all time slots from start to end
    slots = []
    current_hour = start_hour
    current_minute = 0
    
    while current_hour < end_hour or (current_hour == end_hour and current_minute == 0):
        # Slot start time
        start_time = f"{current_hour:02d}:{current_minute:02d}"
        
        # Calculate slot end time
        end_minute = current_minute + time_slot_minutes
        end_hour_slot = current_hour
        if end_minute >= 60:
            end_minute -= 60
            end_hour_slot += 1
        end_time = f"{end_hour_slot:02d}:{end_minute:02d}"
        
        # Get flight count for this slot
        flight_count = slot_counts.get(start_time, 0)
        pax_count = flight_count * pax_per_flight
        
        # Convert to minutes from midnight
        start_minutes = current_hour * 60 + current_minute
        end_minutes = end_hour_slot * 60 + end_minute
        
        slots.append(DemandSlot(
            start_minutes=start_minutes,
            end_minutes=end_minutes,
            pax_count=pax_count,
        ))
        
        # Move to next slot
        current_minute += time_slot_minutes
        if current_minute >= 60:
            current_minute -= 60
            current_hour += 1
    
    return slots


def generate_demand_csv_content(
    departure_times: List[str],
    pax_per_flight: int = 150,
    time_slot_minutes: int = 30,
    start_hour: int = 6,
    end_hour: int = 22,
) -> str:
    """
    Generate demand CSV content from departure times.
    
    Args:
        departure_times: List of departure times in HH:MM format
        pax_per_flight: Number of passengers per flight
        time_slot_minutes: Time slot duration in minutes
        start_hour: Start hour for demand
        end_hour: End hour for demand
    
    Returns:
        CSV content as string
    """
    # Count flights per time slot
    slot_counts = defaultdict(int)
    
    for time_str in departure_times:
        try:
            hour, minute = map(int, time_str.split(':'))
            slot_minute = (minute // time_slot_minutes) * time_slot_minutes
            slot_key = f"{hour:02d}:{slot_minute:02d}"
            slot_counts[slot_key] += 1
        except (ValueError, IndexError):
            continue
    
    # Generate CSV content
    lines = ["time_slot_start,time_slot_end,pax_count"]
    
    current_hour = start_hour
    current_minute = 0
    
    while current_hour < end_hour or (current_hour == end_hour and current_minute == 0):
        start_time = f"{current_hour:02d}:{current_minute:02d}"
        
        end_minute = current_minute + time_slot_minutes
        end_hour_slot = current_hour
        if end_minute >= 60:
            end_minute -= 60
            end_hour_slot += 1
        end_time = f"{end_hour_slot:02d}:{end_minute:02d}"
        
        flight_count = slot_counts.get(start_time, 0)
        pax_count = flight_count * pax_per_flight
        
        lines.append(f"{start_time},{end_time},{pax_count}")
        
        current_minute += time_slot_minutes
        if current_minute >= 60:
            current_minute -= 60
            current_hour += 1
    
    return "\n".join(lines)


def save_demand_csv(
    departure_times: List[str],
    output_path: str,
    pax_per_flight: int = 150,
    time_slot_minutes: int = 30,
    start_hour: int = 6,
    end_hour: int = 22,
) -> str:
    """
    Save demand data to CSV file.
    
    Args:
        departure_times: List of departure times in HH:MM format
        output_path: Path to output CSV file
        pax_per_flight: Number of passengers per flight
        time_slot_minutes: Time slot duration
        start_hour: Start hour
        end_hour: End hour
    
    Returns:
        Path to saved file
    """
    content = generate_demand_csv_content(
        departure_times,
        pax_per_flight,
        time_slot_minutes,
        start_hour,
        end_hour,
    )
    
    Path(output_path).write_text(content, encoding='utf-8')
    
    return output_path


def summarize_flights_by_slot(
    departure_times: List[str],
    time_slot_minutes: int = 30,
) -> Dict[str, int]:
    """
    Summarize flight counts by time slot.
    
    Args:
        departure_times: List of departure times
        time_slot_minutes: Time slot duration
    
    Returns:
        Dictionary of {slot_start: flight_count}
    """
    slot_counts = defaultdict(int)
    
    for time_str in departure_times:
        try:
            hour, minute = map(int, time_str.split(':'))
            slot_minute = (minute // time_slot_minutes) * time_slot_minutes
            slot_key = f"{hour:02d}:{slot_minute:02d}"
            slot_counts[slot_key] += 1
        except (ValueError, IndexError):
            continue
    
    return dict(sorted(slot_counts.items()))


def calculate_total_demand(
    departure_times: List[str],
    pax_per_flight: int = 150,
) -> Tuple[int, int]:
    """
    Calculate total demand statistics.
    
    Args:
        departure_times: List of departure times
        pax_per_flight: Number of passengers per flight
    
    Returns:
        Tuple of (total_flights, total_passengers)
    """
    total_flights = len(departure_times)
    total_passengers = total_flights * pax_per_flight
    
    return total_flights, total_passengers


