"""Passenger and PassengerGroup models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import random


class CheckinType(Enum):
    """Type of check-in process."""
    ONLINE = "online"
    KIOSK = "kiosk"
    COUNTER = "counter"  # チェックインカウンター（チェックインのみ）


class BaggageDropType(Enum):
    """Type of baggage drop method."""
    NONE = "none"  # 預け荷物なし
    COUNTER = "counter"  # 手荷物カウンター（タグ発券＋預け入れ一括）
    SELF = "self"  # セルフ（タグ発券機→ドロップポイント）


@dataclass
class Passenger:
    """Individual passenger within a group."""
    
    passenger_id: int
    group_id: int
    
    def __repr__(self) -> str:
        return f"Passenger(id={self.passenger_id}, group={self.group_id})"


@dataclass
class PassengerGroup:
    """
    Group of passengers traveling together.
    
    Processing at each stage is done once per group (representative handles it).
    Occupancy counts reflect the full group_size.
    """
    
    group_id: int
    group_size: int
    arrival_time: float  # Simulation time when group arrives
    departure_time: float  # Scheduled flight departure time
    checkin_type: CheckinType
    has_baggage: bool
    baggage_drop_type: BaggageDropType = BaggageDropType.NONE
    
    # Tracking timestamps
    checkin_queue_enter: Optional[float] = None
    checkin_start: Optional[float] = None
    checkin_end: Optional[float] = None
    
    # 手荷物カウンター用タイムスタンプ
    baggage_counter_queue_enter: Optional[float] = None
    baggage_counter_start: Optional[float] = None
    baggage_counter_end: Optional[float] = None
    
    # セルフ預け入れ用タイムスタンプ
    tag_queue_enter: Optional[float] = None
    tag_start: Optional[float] = None
    tag_end: Optional[float] = None
    drop_queue_enter: Optional[float] = None
    drop_start: Optional[float] = None
    drop_end: Optional[float] = None
    
    security_arrival: Optional[float] = None
    
    # Current position for visualization
    current_x: float = 0.0
    current_y: float = 0.0
    current_node: str = "source"
    
    # Individual passengers in this group
    passengers: list = field(default_factory=list)
    
    def __post_init__(self):
        """Create individual passenger objects."""
        if not self.passengers:
            self.passengers = [
                Passenger(
                    passenger_id=self.group_id * 100 + i,
                    group_id=self.group_id
                )
                for i in range(self.group_size)
            ]
    
    @property
    def checkin_wait_time(self) -> Optional[float]:
        """Calculate check-in waiting time."""
        if self.checkin_type == CheckinType.ONLINE:
            return 0.0
        if self.checkin_queue_enter is not None and self.checkin_start is not None:
            return self.checkin_start - self.checkin_queue_enter
        return None
    
    @property
    def baggage_counter_wait_time(self) -> Optional[float]:
        """Calculate baggage counter waiting time."""
        if self.baggage_counter_queue_enter is not None and self.baggage_counter_start is not None:
            return self.baggage_counter_start - self.baggage_counter_queue_enter
        return None
    
    @property
    def tag_wait_time(self) -> Optional[float]:
        """Calculate tag kiosk waiting time."""
        if self.tag_queue_enter is not None and self.tag_start is not None:
            return self.tag_start - self.tag_queue_enter
        return None
    
    @property
    def drop_wait_time(self) -> Optional[float]:
        """Calculate drop point waiting time."""
        if self.drop_queue_enter is not None and self.drop_start is not None:
            return self.drop_start - self.drop_queue_enter
        return None
    
    @property
    def total_process_time(self) -> Optional[float]:
        """Calculate total time from arrival to security gate."""
        if self.arrival_time is not None and self.security_arrival is not None:
            return self.security_arrival - self.arrival_time
        return None
    
    def __repr__(self) -> str:
        return (
            f"PassengerGroup(id={self.group_id}, size={self.group_size}, "
            f"checkin={self.checkin_type.value}, baggage={self.baggage_drop_type.value})"
        )


class PassengerGroupFactory:
    """Factory for creating passenger groups with configured probabilities."""
    
    def __init__(
        self,
        p_online: float = 0.3,
        p_kiosk: float = 0.5,
        p_counter: float = 0.2,
        p_baggage: float = 0.5,
        p_baggage_counter: float = 0.4,  # 預け荷物ありの人が手荷物カウンターを使う率
        p_single: float = 0.7,
        multi_min: int = 2,
        multi_max: int = 4,
    ):
        """
        Initialize factory with probabilities.
        
        Args:
            p_online: Probability of online check-in
            p_kiosk: Probability of kiosk check-in
            p_counter: Probability of counter check-in
            p_baggage: Probability of having checked baggage
            p_baggage_counter: Probability of using baggage counter (vs self drop) when has baggage
            p_single: Probability of single traveler
            multi_min: Minimum group size for multi-person groups
            multi_max: Maximum group size for multi-person groups
        """
        # Normalize check-in probabilities
        total = p_online + p_kiosk + p_counter
        self.p_online = p_online / total
        self.p_kiosk = p_kiosk / total
        self.p_counter = p_counter / total
        
        self.p_baggage = p_baggage
        self.p_baggage_counter = p_baggage_counter
        self.p_single = p_single
        self.multi_min = multi_min
        self.multi_max = multi_max
        
        self._next_group_id = 0
    
    def create_group(
        self,
        arrival_time: float,
        departure_time: float,
    ) -> PassengerGroup:
        """
        Create a new passenger group.
        
        Args:
            arrival_time: Simulation time when group arrives
            departure_time: Scheduled flight departure time
        
        Returns:
            New PassengerGroup instance
        """
        group_id = self._next_group_id
        self._next_group_id += 1
        
        # Determine group size
        if random.random() < self.p_single:
            group_size = 1
        else:
            group_size = random.randint(self.multi_min, self.multi_max)
        
        # Determine check-in type
        rand = random.random()
        if rand < self.p_online:
            checkin_type = CheckinType.ONLINE
        elif rand < self.p_online + self.p_kiosk:
            checkin_type = CheckinType.KIOSK
        else:
            checkin_type = CheckinType.COUNTER
        
        # Determine baggage
        has_baggage = random.random() < self.p_baggage
        
        # Determine baggage drop type
        if has_baggage:
            if random.random() < self.p_baggage_counter:
                baggage_drop_type = BaggageDropType.COUNTER
            else:
                baggage_drop_type = BaggageDropType.SELF
        else:
            baggage_drop_type = BaggageDropType.NONE
        
        return PassengerGroup(
            group_id=group_id,
            group_size=group_size,
            arrival_time=arrival_time,
            departure_time=departure_time,
            checkin_type=checkin_type,
            has_baggage=has_baggage,
            baggage_drop_type=baggage_drop_type,
        )
    
    def reset(self):
        """Reset the factory state."""
        self._next_group_id = 0
