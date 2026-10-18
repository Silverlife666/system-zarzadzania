"""Czysta geometria układania kartonów na palecie."""

from __future__ import annotations

from typing import Iterable


Rectangle = tuple[float, float, float, float]


def layout_for_orientation(pallet_length: float, pallet_width: float, box_length: float, box_width: float) -> list[Rectangle]:
    """Układa kartony w jednej wskazanej orientacji i centruje całą warstwę."""
    if min(pallet_length, pallet_width, box_length, box_width) <= 0:
        return []
    count_x, count_y = int(pallet_length // box_length), int(pallet_width // box_width)
    if count_x <= 0 or count_y <= 0:
        return []
    used_length, used_width = count_x * box_length, count_y * box_width
    offset_x, offset_y = (pallet_length - used_length) / 2, (pallet_width - used_width) / 2
    return [
        (offset_x + x * box_length, offset_y + y * box_width, box_length, box_width)
        for x in range(count_x) for y in range(count_y)
    ]


def mixed_layout_for_orientation(pallet_length: float, pallet_width: float, box_length: float, box_width: float) -> list[Rectangle]:
    """Wyszukuje najlepszy układ warstwy z kartonami w obu obrotach 90°."""
    if min(pallet_length, pallet_width, box_length, box_width) <= 0:
        return []
    candidates: list[list[Rectangle]] = [
        layout_for_orientation(pallet_length, pallet_width, box_length, box_width),
        layout_for_orientation(pallet_length, pallet_width, box_width, box_length),
    ]
    for split_on_length in (True, False):
        limit = pallet_length if split_on_length else pallet_width
        first_strip, second_strip = box_length, box_width
        for first_count in range(int(limit // first_strip) + 1):
            remaining = limit - first_count * first_strip
            second_count = int(remaining // second_strip)
            rectangles: list[Rectangle] = []
            offset = 0.0
            for _ in range(first_count):
                if split_on_length:
                    rectangles.extend((offset, index * box_width, box_length, box_width) for index in range(int(pallet_width // box_width)))
                else:
                    rectangles.extend((index * box_width, offset, box_width, box_length) for index in range(int(pallet_length // box_width)))
                offset += first_strip
            for _ in range(second_count):
                if split_on_length:
                    rectangles.extend((offset, index * box_length, box_width, box_length) for index in range(int(pallet_width // box_length)))
                else:
                    rectangles.extend((index * box_length, offset, box_length, box_width) for index in range(int(pallet_length // box_length)))
                offset += second_strip
            candidates.append(rectangles)
    return max(candidates, key=len)


def overhang_mm(layout: Iterable[Rectangle], pallet_length: float, pallet_width: float) -> float:
    rectangles = list(layout)
    if not rectangles:
        return 0.0
    min_x = min(rectangle[0] for rectangle in rectangles)
    max_x = max(rectangle[0] + rectangle[2] for rectangle in rectangles)
    min_y = min(rectangle[1] for rectangle in rectangles)
    max_y = max(rectangle[1] + rectangle[3] for rectangle in rectangles)
    return max(0.0, -min_x, max_x - pallet_length, -min_y, max_y - pallet_width)


def overhang_status(layout: Iterable[Rectangle], pallet_length: float, pallet_width: float) -> tuple[str, float]:
    amount = overhang_mm(layout, pallet_length, pallet_width)
    return (f"⚠️ Overhang (Wystaje o {amount:.1f} mm)", amount) if amount > 1 else ("✅ Aligned (W obrysie palety)", 0.0)
