"""Models package."""

from .passenger import Passenger, PassengerGroup, CheckinType, BaggageDropType
from .resources import AirportResources

__all__ = ["Passenger", "PassengerGroup", "CheckinType", "BaggageDropType", "AirportResources"]

