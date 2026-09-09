from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SplitLine:
    """表示一条使用原图 Y 坐标保存的水平分割线。"""

    y: int


@dataclass
class Region:
    """表示两条相邻分割线之间的图片区域。"""

    top: int
    bottom: int
    keep: bool = True

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


@dataclass
class DocumentState:
    """保存与预览视图无关的可编辑文档状态。"""

    image_path: str = ""
    image_width: int = 0
    image_height: int = 0
    split_lines: list[SplitLine] = field(default_factory=list)
    # 使用区域的上下边界作为稳定标识，而不是使用区域在当前 regions() 中的索引。
    # 这样在其他位置新增/删除分割线时，已有的未选中区域不会因为索引变化而改变。
    deleted_regions: set[tuple[int, int]] = field(default_factory=set)

    def normalized_lines(self) -> list[int]:
        return sorted({max(0, min(self.image_height, line.y)) for line in self.split_lines})

    def regions(self) -> list[Region]:
        points = [0, *self.normalized_lines(), self.image_height]
        result: list[Region] = []
        for i in range(len(points) - 1):
            top, bottom = points[i], points[i + 1]
            result.append(Region(top, bottom, (top, bottom) not in self.deleted_regions))
        return result

    def update_deleted_region_boundary(self, old_y: int, new_y: int) -> None:
        """分割线移动时同步更新以该分割线为边界的已删除区域。"""
        updated: set[tuple[int, int]] = set()
        for top, bottom in self.deleted_regions:
            if top == old_y:
                top = new_y
            if bottom == old_y:
                bottom = new_y
            updated.add((top, bottom))
        self.deleted_regions = updated

    def discard_invalid_deleted_regions(self) -> None:
        """删除已经不再对应当前实际区域的已删除区域记录。"""
        valid = {(region.top, region.bottom) for region in self.regions()}
        self.deleted_regions.intersection_update(valid)
