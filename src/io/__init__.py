"""IO package."""

from .loader import DataLoader
from .exporter import ResultExporter
from .demand_generator import (
    generate_demand_from_flights,
    generate_demand_csv_content,
    summarize_flights_by_slot,
    calculate_total_demand,
)

__all__ = [
    "DataLoader",
    "ResultExporter",
    "generate_demand_from_flights",
    "generate_demand_csv_content",
    "summarize_flights_by_slot",
    "calculate_total_demand",
]

# OCR is optional
try:
    from .ocr import extract_times_from_image, extract_times_from_multiple_images
    __all__.extend(["extract_times_from_image", "extract_times_from_multiple_images"])
except ImportError:
    pass

