from __future__ import annotations

from pathlib import Path

from PIL import Image

from .export_conflicts import resolve_conflicts
from .model import DocumentState


def export_regions(state: DocumentState, output_dir: Path) -> list[Path]:
    """根据原始图片坐标裁剪并导出所有保留区域。"""
    if not state.image_path:
        raise ValueError("未选择原图。")

    regions = [region for region in state.regions() if region.keep and region.height > 0]
    paths = [output_dir / f"{number:03d}.png" for number in range(1, len(regions) + 1)]
    replace_paths, skip_paths = resolve_conflicts(paths)
    del replace_paths

    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(state.image_path) as source:
        if source.width != state.image_width or source.height != state.image_height:
            raise ValueError("原图尺寸与打开时记录的尺寸不一致。")

        outputs: list[Path] = []
        for number, region in enumerate(regions, 1):
            path = output_dir / f"{number:03d}.png"
            if path in skip_paths:
                continue
            crop = source.crop((0, region.top, source.width, region.bottom))
            crop.save(path, format="PNG")
            outputs.append(path)

    return outputs
