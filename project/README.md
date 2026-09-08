# Screenshot Splitter

Windows 10/11 长截图水平分割工具。项目采用 Python + PySide6，目标是提供比 Photoshop Slice 更直接的“分割线 + 区域筛选 + 一键导出”工作流。

## 1. 当前实现

- 仅支持水平分割。
- 原图宽度在整个编辑过程中保持不变。
- 分割线以原始图片 Y 像素坐标保存。
- 鼠标点击区域可选中区域。
- 默认 `S` 在鼠标当前位置创建水平分割线。
- 已创建分割线可鼠标拖动调整位置。
- 选中分割线后支持方向键逐像素调整，`Shift + 方向键`按 10px 调整。
- `Delete` 删除选中分割线。
- `Space` 将当前选中区域切换为保留/删除状态；删除区域在预览中显示为灰色。
- `Alt + 滚轮`以鼠标位置为中心缩放预览。
- 中键拖动实现画布平移。
- 普通滚轮用于垂直滚动，`Shift + 滚轮`用于水平滚动。
- 预览缩放、平移不会修改原图，也不会影响最终导出尺寸或画质。
- 导出时仅输出保留区域，并从上到下重新编号为 `001.png`、`002.png`……
- 输出 PNG 使用原始图片像素进行裁剪，不使用缩放后的预览图。

## 2. 项目结构

```text
ScreenshotSplitter/
├─ main.py
├─ requirements.txt
├─ README.md
└─ src/
   ├─ __init__.py
   ├─ config.py
   ├─ model.py
   ├─ image_canvas.py
   ├─ exporter.py
   ├─ shortcut_dialog.py
   └─ main_window.py
```

### 模块职责

- `main.py`：程序入口及配置初始化。
- `config.py`：配置数据结构及 JSON 持久化。
- `model.py`：文档、分割线、区域等核心数据模型。
- `image_canvas.py`：图片预览、缩放、滚动、平移、分割线交互及绘制。
- `exporter.py`：根据原始图片坐标执行 PNG 裁剪和批量导出。
- `shortcut_dialog.py`：二级快捷键设置页面。
- `main_window.py`：主窗口、菜单/工具栏和模块协调。

## 3. 坐标与预览设计

编辑状态中的分割线始终使用原始图片坐标，例如：

```text
原图高度 = 20000
分割线 Y = 7350
```

预览显示时再通过：

```text
screen_y = image_y * zoom - vertical_scroll
```

转换为窗口坐标。

因此：

- 修改缩放比例不会改变分割线的真实位置。
- 平移不会改变分割线的真实位置。
- 导出时直接使用 `image_y`。
- 最终输出宽度始终等于原图宽度。

## 4. 区域模型

若图片高度为 `H`，分割线为：

```text
Y1 < Y2 < Y3
```

则形成：

```text
0    ~ Y1
Y1   ~ Y2
Y2   ~ Y3
Y3   ~ H
```

每个区域具有 `keep` 状态。删除区域只是编辑状态标记，原始图片数据不会修改。

## 5. 配置文件

程序会将用户配置保存在**程序运行目录**，即开发运行时通常为项目目录，打包为 EXE 后通常为 EXE 所在目录。

当前配置文件：

```text
settings.json
```

结构示例：

```json
{
  "shortcuts": {
    "add_split_line": "S",
    "toggle_region": "SPACE",
    "delete_split_line": "DELETE",
    "undo": "CTRL+Z",
    "redo": "CTRL+SHIFT+Z",
    "move_line_up": "UP",
    "move_line_down": "DOWN",
    "move_line_up_fast": "SHIFT+UP",
    "move_line_down_fast": "SHIFT+DOWN",
    "fit_window": "F",
    "zoom_100": "1"
  }
}
```

配置加载失败时使用默认配置，不阻止程序启动。

## 6. 开发环境

建议 Python 3.11+。

安装依赖：

```bash
pip install -r requirements.txt
```

运行：

```bash
python main.py
```

## 7. Windows 打包

推荐使用 PyInstaller：

```bash
pip install pyinstaller
pyinstaller --noconsole --onedir --name ScreenshotSplitter main.py
```

生成目录位于：

```text
dist/ScreenshotSplitter/
```

如需单文件 EXE，可使用：

```bash
pyinstaller --noconsole --onefile --name ScreenshotSplitter main.py
```

对于超长图片，建议优先使用 `--onedir` 版本，便于后续扩展资源和配置文件。

## 8. 后续二次开发建议

### 快捷键系统
当前设置页面已保存快捷键字符串，但部分复杂组合键的运行时解析仍可进一步统一。后续建议建立独立 `ShortcutManager`，负责解析、注册、冲突检测和事件分发。

### 撤销/重做
当前数据模型已集中管理分割线和区域状态。后续可增加 Command/Undo Stack，将“添加、移动、删除分割线”和“区域保留状态切换”全部纳入撤销栈。

### 项目文件
如后续需要保存编辑进度，可增加 `.ssp` 项目文件，保存：

- 原图路径
- 分割线 Y 坐标
- 区域保留状态
- 视图缩放
- 视图滚动位置
- 软件版本

不应把原始 PNG 嵌入项目文件，除非未来明确需要自包含项目。

### 超大图片
当前预览使用 QImage。若后续处理几十万像素高度的图片并出现内存或渲染压力，可进一步引入缩略图/分块渲染机制；导出仍应直接读取原始图片区域，保持与预览层解耦。

## 9. 重要约束

本项目的核心原则是：

> 预览层负责显示和交互，原始图片层负责最终导出。

因此任何缩放、平移、灰色遮罩、选中框等 UI 操作都不得修改原始图片数据。
