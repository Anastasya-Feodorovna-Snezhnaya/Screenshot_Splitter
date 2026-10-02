from __future__ import annotations

def minimum_number_width(total: int) -> int:
    """返回能够表示 1..total 的最少十进制位数。"""
    if total < 1:
        return 1
    return len(str(total))


def number_width(total: int, mode: str = "fixed", extra: int = 0, threshold_percent: int = 100) -> int:
    """根据导出总数和编号策略计算统一的编号位数。"""
    if not 0 <= extra <= 5:
        raise ValueError("编号额外位数必须在 0 到 5 之间。")
    if not 0 <= threshold_percent <= 100:
        raise ValueError("编号自动阈值必须在 0 到 100% 之间。")
    if mode not in {"fixed", "threshold"}:
        raise ValueError("未知的编号位数模式。")

    width = minimum_number_width(total)
    if mode == "fixed":
        return width + extra

    if total / (10 ** width) > threshold_percent / 100:
        width += 1
    return width


def format_number(number: int, width: int) -> str:
    """将切片序号格式化为指定宽度的十进制数字。"""
    return f"{number:0{width}d}"
