"""Passenger process definitions for simulation."""

from typing import Dict, Generator, Optional
import simpy

from ..models.passenger import PassengerGroup, CheckinType, BaggageDropType
from ..models.resources import AirportResources
from ..utils.distributions import ServiceTimeDistribution


class PassengerProcess:
    """
    Handles the movement of a passenger group through airport processes.
    
    Flow:
    1. Arrival at airport
    2. Check-in (online/kiosk/counter) - counter is check-in only
    3. If has baggage:
       - Baggage counter: タグ発券＋預け入れ一括 → 保安検査へ
       - Self: タグ発券機 → ドロップポイント → 保安検査へ
    4. Security gate (end)
    """
    
    def __init__(
        self,
        env: simpy.Environment,
        resources: AirportResources,
        service_times: Dict[str, ServiceTimeDistribution],
        nodes: Dict[str, Dict[str, float]],
    ):
        """
        Initialize passenger process handler.
        
        Args:
            env: SimPy environment
            resources: Airport resources container
            service_times: Dictionary of service time distributions per process
            nodes: Node coordinates for position tracking
        """
        self.env = env
        self.resources = resources
        self.service_times = service_times
        self.nodes = nodes
        
        # Completed groups for statistics
        self.completed_groups: list = []
    
    def _update_position(self, group: PassengerGroup, node_name: str):
        """Update group position based on current node."""
        if node_name in self.nodes:
            node = self.nodes[node_name]
            group.current_x = node.get("x", 0)
            group.current_y = node.get("y", 0)
            group.current_node = node_name
    
    def _get_area_for_node(self, node_name: str) -> Optional[str]:
        """Map node to area for occupancy tracking."""
        area_mapping = {
            "checkin_kiosk": "checkin_zone",
            "checkin_counter": "checkin_zone",
            "baggage_counter": "baggage_counter_zone",
            "tag_kiosk": "tag_zone",
            "drop_point": "drop_zone",
            "security_gate": "security_front",
        }
        return area_mapping.get(node_name)
    
    def run(self, group: PassengerGroup) -> Generator:
        """
        Main process for a passenger group.
        
        Args:
            group: The passenger group to process
        
        Yields:
            SimPy events
        """
        # Initial position
        self._update_position(group, "source")
        
        # === Check-in Process ===
        if group.checkin_type == CheckinType.ONLINE:
            # Online check-in: skip physical check-in, minimal delay
            yield self.env.timeout(5)  # Small delay for entering system
            self._update_position(group, "checkin_kiosk")  # Just pass through area
            
        elif group.checkin_type == CheckinType.KIOSK:
            # Kiosk check-in
            self._update_position(group, "checkin_kiosk")
            self.resources.enter_area("checkin_zone", group.group_id, group.group_size)
            
            group.checkin_queue_enter = self.env.now
            
            req = self.resources.checkin_kiosk.request(group.group_id, group.group_size)
            yield req
            
            group.checkin_start = self.env.now
            service_time = self.service_times["checkin_kiosk"].sample_one()
            yield self.env.timeout(service_time)
            
            group.checkin_end = self.env.now
            self.resources.checkin_kiosk.release(req, group.group_id)
            self.resources.leave_area("checkin_zone", group.group_id)
            
        else:  # Counter - check-in only (no baggage handling)
            self._update_position(group, "checkin_counter")
            self.resources.enter_area("checkin_zone", group.group_id, group.group_size)
            
            group.checkin_queue_enter = self.env.now
            
            req = self.resources.checkin_counter.request(group.group_id, group.group_size)
            yield req
            
            group.checkin_start = self.env.now
            service_time = self.service_times["checkin_counter"].sample_one()
            yield self.env.timeout(service_time)
            
            group.checkin_end = self.env.now
            self.resources.checkin_counter.release(req, group.group_id)
            self.resources.leave_area("checkin_zone", group.group_id)
        
        # === Baggage Process ===
        if group.baggage_drop_type == BaggageDropType.COUNTER:
            # 手荷物カウンター: タグ発券＋預け入れを一括で実施
            self._update_position(group, "baggage_counter")
            self.resources.enter_area("baggage_counter_zone", group.group_id, group.group_size)
            
            group.baggage_counter_queue_enter = self.env.now
            
            req = self.resources.baggage_counter.request(group.group_id, group.group_size)
            yield req
            
            group.baggage_counter_start = self.env.now
            service_time = self.service_times["baggage_counter"].sample_one()
            yield self.env.timeout(service_time)
            
            group.baggage_counter_end = self.env.now
            self.resources.baggage_counter.release(req, group.group_id)
            self.resources.leave_area("baggage_counter_zone", group.group_id)
            
            # 手荷物カウンター利用後は直接保安検査へ（ドロップ不要）
            
        elif group.baggage_drop_type == BaggageDropType.SELF:
            # セルフ預け入れ: タグ発券機 → ドロップポイント
            
            # Tag kiosk
            self._update_position(group, "tag_kiosk")
            self.resources.enter_area("tag_zone", group.group_id, group.group_size)
            
            group.tag_queue_enter = self.env.now
            
            req = self.resources.tag_kiosk.request(group.group_id, group.group_size)
            yield req
            
            group.tag_start = self.env.now
            service_time = self.service_times["tag_kiosk"].sample_one()
            yield self.env.timeout(service_time)
            
            group.tag_end = self.env.now
            self.resources.tag_kiosk.release(req, group.group_id)
            self.resources.leave_area("tag_zone", group.group_id)
            
            # Drop point
            self._update_position(group, "drop_point")
            self.resources.enter_area("drop_zone", group.group_id, group.group_size)
            
            group.drop_queue_enter = self.env.now
            
            req = self.resources.drop_point.request(group.group_id, group.group_size)
            yield req
            
            group.drop_start = self.env.now
            service_time = self.service_times["drop_point"].sample_one()
            yield self.env.timeout(service_time)
            
            group.drop_end = self.env.now
            self.resources.drop_point.release(req, group.group_id)
            self.resources.leave_area("drop_zone", group.group_id)
        
        # === Security Gate (End) ===
        self._update_position(group, "security_gate")
        self.resources.enter_area("security_front", group.group_id, group.group_size)
        
        # Small delay to pass through security front area
        yield self.env.timeout(10)
        
        group.security_arrival = self.env.now
        self.resources.leave_area("security_front", group.group_id)
        
        # Mark as completed
        self.completed_groups.append(group)
