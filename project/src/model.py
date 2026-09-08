from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SplitLine:
    """A horizontal split line stored in original-image Y coordinates."""

    y: int


@dataclass
class Region:
    """A region between two split lines."""

    top: int
    bottom: int
    keep: bool = True

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


@dataclass
class DocumentState:
    """Editable state independent from the preview viewport."""

    image_path: str = ""
    image_width: int = 0
    image_height: int = 0
    split_lines: list[SplitLine] = field(default_factory=list)
    deleted_regions: set[int] = field(default_factory=set)

    def normalized_lines(self) -> list[int]:
        return sorted({max(0, min(self.image_height, line.y)) for line in self.split_lines})

    def regions(self) -> list[Region]:
        points = [0, *self.normalized_lines(), self.image_height]
        result: list[Region] = []
        for i in range(len(points) - 1):
            result.append(Region(points[i], points[i + 1], i not in self.deleted_regions))
        return result
