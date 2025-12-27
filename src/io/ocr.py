"""OCR module for extracting departure times from timetable images."""

import re
from typing import List, Tuple, Optional
from pathlib import Path
from PIL import Image
import io


def extract_times_from_image(
    image_source,
    lang: str = "jpn+eng",
) -> List[str]:
    """
    Extract departure times from a timetable image using OCR.
    
    Args:
        image_source: Path to image file, PIL Image, or bytes
        lang: Tesseract language code (default: jpn+eng for Japanese + English)
    
    Returns:
        List of extracted time strings in HH:MM format
    """
    try:
        import pytesseract
    except ImportError:
        raise ImportError(
            "pytesseract is required for OCR. "
            "Install with: pip install pytesseract\n"
            "Also install Tesseract OCR:\n"
            "  macOS: brew install tesseract tesseract-lang\n"
            "  Ubuntu: apt install tesseract-ocr tesseract-ocr-jpn"
        )
    
    # Load image
    if isinstance(image_source, (str, Path)):
        image = Image.open(image_source)
    elif isinstance(image_source, bytes):
        image = Image.open(io.BytesIO(image_source))
    elif isinstance(image_source, Image.Image):
        image = image_source
    else:
        raise ValueError(f"Unsupported image source type: {type(image_source)}")
    
    # Preprocess image for better OCR
    image = preprocess_image(image)
    
    # Perform OCR
    try:
        text = pytesseract.image_to_string(image, lang=lang)
    except Exception as e:
        # Fallback to English only if Japanese not available
        try:
            text = pytesseract.image_to_string(image, lang="eng")
        except Exception:
            raise RuntimeError(f"OCR failed: {e}")
    
    # Extract times from OCR text
    times = extract_times_from_text(text)
    
    return times


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image for better OCR accuracy.
    
    Args:
        image: PIL Image
    
    Returns:
        Preprocessed PIL Image
    """
    # Convert to grayscale
    if image.mode != 'L':
        image = image.convert('L')
    
    # Increase contrast (simple thresholding)
    # This helps with typical timetable images
    threshold = 180
    image = image.point(lambda x: 255 if x > threshold else 0, mode='1')
    
    # Convert back to grayscale for Tesseract
    image = image.convert('L')
    
    return image


def extract_times_from_text(text: str) -> List[str]:
    """
    Extract time patterns from OCR text.
    
    Args:
        text: Raw OCR text
    
    Returns:
        List of time strings in HH:MM format
    """
    # Time patterns:
    # - HH:MM (standard format)
    # - HH時MM分 (Japanese format)
    # - HH.MM (sometimes OCR misreads : as .)
    # - HHMM (4 digits without separator)
    
    patterns = [
        r'\b([0-2]?[0-9]):([0-5][0-9])\b',           # HH:MM or H:MM
        r'\b([0-2]?[0-9])\.([0-5][0-9])\b',          # HH.MM (OCR misread)
        r'\b([0-2]?[0-9])時([0-5][0-9])分?\b',        # Japanese format
        r'\b([0-2][0-9])([0-5][0-9])\b',              # HHMM (4 digits)
    ]
    
    times = set()
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            hour, minute = match
            hour = int(hour)
            minute = int(minute)
            
            # Validate time range (5:00 - 23:59 for typical flight times)
            if 5 <= hour <= 23 and 0 <= minute <= 59:
                time_str = f"{hour:02d}:{minute:02d}"
                times.add(time_str)
    
    # Sort times chronologically
    sorted_times = sorted(times, key=lambda t: (int(t.split(':')[0]), int(t.split(':')[1])))
    
    return sorted_times


def extract_times_from_multiple_images(
    image_sources: List,
    lang: str = "jpn+eng",
) -> List[str]:
    """
    Extract departure times from multiple timetable images.
    
    Args:
        image_sources: List of image sources (paths, bytes, or PIL Images)
        lang: Tesseract language code
    
    Returns:
        Combined and deduplicated list of time strings
    """
    all_times = set()
    
    for source in image_sources:
        try:
            times = extract_times_from_image(source, lang)
            all_times.update(times)
        except Exception as e:
            print(f"Warning: Failed to process image: {e}")
            continue
    
    # Sort times chronologically
    sorted_times = sorted(all_times, key=lambda t: (int(t.split(':')[0]), int(t.split(':')[1])))
    
    return sorted_times


def validate_time(time_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validate and normalize a time string.
    
    Args:
        time_str: Time string to validate
    
    Returns:
        Tuple of (is_valid, normalized_time_or_error)
    """
    # Try to parse various formats
    patterns = [
        (r'^(\d{1,2}):(\d{2})$', lambda m: (int(m.group(1)), int(m.group(2)))),
        (r'^(\d{1,2})\.(\d{2})$', lambda m: (int(m.group(1)), int(m.group(2)))),
        (r'^(\d{1,2})時(\d{2})分?$', lambda m: (int(m.group(1)), int(m.group(2)))),
        (r'^(\d{4})$', lambda m: (int(m.group(1)[:2]), int(m.group(1)[2:]))),
    ]
    
    for pattern, extractor in patterns:
        match = re.match(pattern, time_str.strip())
        if match:
            try:
                hour, minute = extractor(match)
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return True, f"{hour:02d}:{minute:02d}"
            except (ValueError, IndexError):
                continue
    
    return False, f"Invalid time format: {time_str}"


