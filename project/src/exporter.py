from __future__ import annotations

from pathlib import Path

from PIL import Image

from .model import DocumentState


def export_regions(state: DocumentState, output_dir: Path) -> list[Path]:
    """
    Export kept regions directly from the source image.

    No preview bitmap is used here, so zoom/pan has zero effect on output
    resolution or quality.
    """
    if not state.image_path:
        raise ValueError("No source image selected.")

    output_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(state.image_path)
    if source.width != state.image_width or source.height != state.image_height:
        raise ValueError("Source image dimensions changed since it was loaded.")

    outputs: list[Path] = []
    number = 1
    for region in state.regions():
        if not region.keep or region.height <= 0:
            continue
        crop = source.crop((0, region.top, source.width, region.bottom))
        path = output_dir / f"{number:03d}.png"
        crop.save(path, format="PNG")
        outputs.append(path)
        number += 1

    source.close()
    return outputs
