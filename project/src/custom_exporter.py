from __future__ import annotations

from pathlib import Path

from PIL import Image

from .model import DocumentState


def export_regions_named(state: DocumentState, output_dir: Path, prefix: str, suffix: str) -> list[Path]:
    """使用用户指定的前缀和包含 n 的后缀导出保留区域。"""
    if not state.image_path:
        raise ValueError("No source image selected.")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    with Image.open(state.image_path) as source:
        if source.width != state.image_width or source.height != state.image_height:
            raise ValueError("Source image dimensions changed since it was loaded.")

        number = 1
        for region in state.regions():
            if not region.keep or region.height <= 0:
                continue
            crop = source.crop((0, region.top, source.width, region.bottom))
            path = output_dir / f"{prefix}{suffix.replace('n', str(number))}.png"
            crop.save(path, format="PNG")
            outputs.append(path)
            number += 1

    return outputs
