from __future__ import annotations

from pathlib import Path

from PIL import Image

from .export_conflicts import resolve_conflicts
from .model import DocumentState


def export_regions_named(state: DocumentState, output_dir: Path, prefix: str, suffix: str) -> list[Path]:
    """使用用户指定的前缀和包含 n 的后缀导出保留区域。"""
    if not state.image_path:
        raise ValueError("未选择原图。")

    output_dir.mkdir(parents=True, exist_ok=True)

    regions = [region for region in state.regions() if region.keep and region.height > 0]
    paths = [output_dir / f"{prefix}{suffix.replace('n', str(number))}.png" for number in range(1, len(regions) + 1)]
    replace_paths, skip_paths = resolve_conflicts(paths)

    with Image.open(state.image_path) as source:
        if source.width != state.image_width or source.height != state.image_height:
            raise ValueError("原图尺寸与打开时记录的尺寸不一致。")

        outputs: list[Path] = []
        for number, region in enumerate(regions, 1):
            path = output_dir / f"{prefix}{suffix.replace('n', str(number))}.png"
            if path in skip_paths:
                continue
            crop = source.crop((0, region.top, source.width, region.bottom))
            crop.save(path, format="PNG")
            outputs.append(path)

    return outputs
