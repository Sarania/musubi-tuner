# Copyright 2024-2025 The Alibaba Wan Team Authors. All rights reserved.
import copy
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from .wan_i2v_14B import i2v_14B
from .wan_t2v_1_3B import t2v_1_3B
from .wan_t2v_14B import t2v_14B

# the config of t2i_14B is the same as t2v_14B
t2i_14B = copy.deepcopy(t2v_14B)
t2i_14B.__name__ = "Config: Wan T2I 14B"

# support Fun models: deepcopy and change some configs. FC denotes Fun Control
t2v_1_3B_FC = copy.deepcopy(t2v_1_3B)
t2v_1_3B_FC.__name__ = "Config: Wan-Fun-Control T2V 1.3B"
t2v_1_3B_FC.in_dim = 48
i2v_14B.is_fun_control = True
t2v_14B_FC = copy.deepcopy(t2v_14B)
t2v_14B_FC.__name__ = "Config: Wan-Fun-Control T2V 14B"
t2v_14B_FC.in_dim = 48  # same as i2v_14B, use zeros for image latents
t2v_14B_FC.is_fun_control = True
i2v_14B_FC = copy.deepcopy(i2v_14B)
i2v_14B_FC.__name__ = "Config: Wan-Fun-Control I2V 14B"
i2v_14B_FC.in_dim = 48
i2v_14B_FC.is_fun_control = True

WAN_CONFIGS = {
    "t2v-14B": t2v_14B,
    "t2v-1.3B": t2v_1_3B,
    "i2v-14B": i2v_14B,
    "t2i-14B": t2i_14B,
    # Fun Control models
    "t2v-1.3B-FC": t2v_1_3B_FC,
    "t2v-14B-FC": t2v_14B_FC,
    "i2v-14B-FC": i2v_14B_FC,
}

SIZE_CONFIGS = {
    "720*1280": (720, 1280),
    "1280*720": (1280, 720),
    "480*832": (480, 832),
    "832*480": (832, 480),
    "1024*1024": (1024, 1024),
}

MAX_AREA_CONFIGS = {
    "720*1280": 720 * 1280,
    "1280*720": 1280 * 720,
    "480*832": 480 * 832,
    "832*480": 832 * 480,
}

SUPPORTED_SIZES = {
    "t2v-14B": ("720*1280", "1280*720", "480*832", "832*480"),
    "t2v-1.3B": ("480*832", "832*480"),
    "i2v-14B": ("720*1280", "1280*720", "480*832", "832*480"),
    "t2i-14B": tuple(SIZE_CONFIGS.keys()),
    # Fun Control models
    "t2v-1.3B-FC": ("480*832", "832*480"),
    "t2v-14B-FC": ("720*1280", "1280*720", "480*832", "832*480"),
    "i2v-14B-FC": ("720*1280", "1280*720", "480*832", "832*480"),
}
