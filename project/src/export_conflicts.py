from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox


class ExportCancelled(Exception):
    """用户取消本次导出。"""


def resolve_conflicts(paths: list[Path]) -> tuple[set[Path], set[Path]]:
    """在实际写入文件前处理所有重名文件，返回替换和跳过的路径集合。"""
    replace_paths: set[Path] = set()
    skip_paths: set[Path] = set()

    parent = QApplication.activeWindow()
    for path in paths:
        if not path.exists():
            continue

        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("导出文件重名")
        box.setText(f"导出的切片与已有文件重名：\n{path.name}")
        box.setInformativeText("请选择如何处理该文件。取消将放弃本次导出，并且不会向导出目录写入新的切片。")
        replace_button = box.addButton("替换", QMessageBox.ButtonRole.AcceptRole)
        skip_button = box.addButton("跳过", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is replace_button:
            replace_paths.add(path)
        elif clicked is skip_button:
            skip_paths.add(path)
        elif clicked is cancel_button:
            raise ExportCancelled()
        else:
            raise ExportCancelled()

    return replace_paths, skip_paths
