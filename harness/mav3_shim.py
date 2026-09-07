# -*- coding: utf-8 -*-
"""
Mobile-Agent-v3 接入垫片：替代 `qwen_vl_utils` 的 `smart_resize`。

背景：MA-v3 的 `utils/call_mobile_agent_e.py` 只用到 `from qwen_vl_utils import smart_resize`，
但 `qwen_vl_utils` 在**导入时**就 `import torch` / `torchvision`（视频处理路径需要）。
本机无 GPU（`nvidia-smi` 不存在），为一个纯算术函数装数百 MB 的 torch 不划算，
因此这里按 **qwen_vl_utils 0.0.14 的实现逐字照抄** smart_resize 及其依赖的常量/辅助函数，
在导入 MA-v3 之前注册为同名模块。

若将来需要真依赖（例如用 MA-v3 的视频能力），删掉 install() 调用即可，
真实包已装在 venv 里（`qwen_vl_utils-0.0.14`），装上 torch 后优先生效。
"""
import math
import sys
import types
from typing import Optional, Tuple

# ---- 以下常量与函数逐字来自 qwen_vl_utils/vision_process.py (0.0.14) ----
MAX_RATIO = 200
SPATIAL_MERGE_SIZE = 2
IMAGE_MIN_TOKEN_NUM = 4
IMAGE_MAX_TOKEN_NUM = 16384
VIDEO_MIN_TOKEN_NUM = 128
VIDEO_MAX_TOKEN_NUM = 768


def round_by_factor(number: int, factor: int) -> int:
    """Returns the closest integer to 'number' that is divisible by 'factor'."""
    return round(number / factor) * factor


def ceil_by_factor(number: int, factor: int) -> int:
    """Returns the smallest integer greater than or equal to 'number' that is divisible by 'factor'."""
    return math.ceil(number / factor) * factor


def floor_by_factor(number: int, factor: int) -> int:
    """Returns the largest integer less than or equal to 'number' that is divisible by 'factor'."""
    return math.floor(number / factor) * factor


def smart_resize(height: int, width: int, factor: int, min_pixels: Optional[int] = None,
                 max_pixels: Optional[int] = None) -> Tuple[int, int]:
    """
    Rescales the image so that the following conditions are met:

    1. Both dimensions (height and width) are divisible by 'factor'.
    2. The total number of pixels is within the range ['min_pixels', 'max_pixels'].
    3. The aspect ratio of the image is maintained as closely as possible.
    """
    max_pixels = max_pixels if max_pixels is not None else (IMAGE_MAX_TOKEN_NUM * factor ** 2)
    min_pixels = min_pixels if min_pixels is not None else (IMAGE_MIN_TOKEN_NUM * factor ** 2)
    assert max_pixels >= min_pixels, "The max_pixels of image must be greater than or equal to min_pixels."
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(
            f"absolute aspect ratio must be smaller than {MAX_RATIO}, got {max(height, width) / min(height, width)}"
        )
    h_bar = max(factor, round_by_factor(height, factor))
    w_bar = max(factor, round_by_factor(width, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = floor_by_factor(height / beta, factor)
        w_bar = floor_by_factor(width / beta, factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = ceil_by_factor(height * beta, factor)
        w_bar = ceil_by_factor(width * beta, factor)
    return h_bar, w_bar
# ---- 照抄结束 ----


def install(force: bool = False) -> str:
    """把本模块的 smart_resize 注册为 `qwen_vl_utils`（仅当真包不可用时）。

    返回 'real' 表示用了真实包，'shim' 表示用了垫片。
    """
    if not force:
        try:
            import qwen_vl_utils  # noqa: F401
            return "real"
        except Exception:
            pass
    mod = types.ModuleType("qwen_vl_utils")
    mod.smart_resize = smart_resize
    mod.round_by_factor = round_by_factor
    mod.ceil_by_factor = ceil_by_factor
    mod.floor_by_factor = floor_by_factor
    mod.MAX_RATIO = MAX_RATIO
    mod.SPATIAL_MERGE_SIZE = SPATIAL_MERGE_SIZE
    mod.IMAGE_MIN_TOKEN_NUM = IMAGE_MIN_TOKEN_NUM
    mod.IMAGE_MAX_TOKEN_NUM = IMAGE_MAX_TOKEN_NUM
    mod.__doc__ = "shim of qwen_vl_utils providing smart_resize (no torch dependency)"
    sys.modules["qwen_vl_utils"] = mod
    return "shim"


if __name__ == "__main__":
    # 自检：与官方实现的行为对齐（同一组输入应得到同一组输出）
    print("install ->", install())
    cases = [(2760, 1256, 28, 3136, 10035200), (1280, 720, 28, 3136, 10035200),
             (100, 100, 28, 3136, 10035200), (4000, 3000, 28, 3136, 10035200)]
    for c in cases:
        print(f"  smart_resize{c} = {smart_resize(*c)}")
