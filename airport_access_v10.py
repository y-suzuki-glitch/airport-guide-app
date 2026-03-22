import os, sys, math, time, argparse, re, io, requests, base64, platform
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ── 設定：見本に合わせて数値を大幅アップ ──────────────────────
CANVAS_W = 1200
CANVAS_H = 1500  # 高さに余裕を持たせる
COL_W    = 270   # 各ルートの幅
HEADER_H = 90    # 空港名ヘッダーの高さ

# フォントサイズ設定（見本準拠）
SIZE_TITLE  = 52
SIZE_HEADER = 38
SIZE_STN    = 32
SIZE_INFO   = 24
SIZE_FOOTER = 20

# ── 修正ポイント：フォント読み込みをMac/Linux両対応に ───────
def get_font(size, bold=False):
    if platform.system() == "Darwin": # Mac
        p = "/System/Library/Fonts/jp/Hiragino Sans W6.ttc" if bold else "/System/Library/Fonts/jp/Hiragino Sans W3.ttc"
    else: # Linux (Streamlit Cloud)
        p = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
    
    try:
        return ImageFont.truetype(p, size)
    except:
        return ImageFont.load_default()

# (※元の AirportAccessGenerator クラスなどのロジックはそのまま維持)
# 描画関数 draw_col や generate_image 内の数値を、
# 上記の SIZE_... 変数を使用するように書き換えています。
