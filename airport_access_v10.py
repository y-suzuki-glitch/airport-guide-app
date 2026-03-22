import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import requests
from datetime import datetime
import io
import os

# --- 設定 ---
FONT_PATHS = {
    'bold': '/System/Library/Fonts/jp/Hiragino Sans W6.ttc',
    'regular': '/System/Library/Fonts/jp/Hiragino Sans W3.ttc',
    'emoji': '/System/Library/Fonts/Apple Color Emoji.ttc'
}

# サーバー環境(Linux)でフォントがない場合の代替設定
DEFAULT_FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

COLORS = {
    'narita': (230, 80, 50),
    'haneda': (40, 160, 80),
    'bg': (230, 240, 255),
    'text_dark': (20, 40, 80),
    'text_light': (255, 255, 255),
    'box_bg': (210, 230, 250),
    'house_bg': (255, 245, 220),
}

SIZE = {
    'width': 1200,
    'header_height': 80,
    'font_title': 50,
    'font_header': 35,
    'font_spot': 30,
    'font_info': 24,
    'icon_size': 40,
}

ICONS = {
    'train': '🚃', 'bus': '🚌', 'taxi': '🚕', 'walk': '🚶‍♂️', 'house': '🏠'
}

class AirportAccessGuide:
    def __init__(self, rapidapi_key):
        self.rapidapi_key = rapidapi_key
        self.headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": "navitime-transport.p.rapidapi.com"
        }
        self._load_fonts()

    def _load_fonts(self):
        self.fonts = {}
        sizes = {'title': SIZE['font_title'], 'header': SIZE['font_header'], 'spot': SIZE['font_spot'], 'info': SIZE['font_info']}
        
        for key, path in FONT_PATHS.items():
            if os.path.exists(path):
                self.fonts[key] = {name: ImageFont.truetype(path, s) for name, s in sizes.items()}
            else:
                # サーバー環境用。フォントがない場合はデフォルトを使用
                self.fonts[key] = {name: ImageFont.load_default() for name in sizes}

    def get_lat_lon(self, address):
        """住所から緯度経度を取得（簡易版：実際はジオコーディングAPI等を使用）"""
        # ここではNAVITIME APIの検索に渡すためのダミー値を返しますが、
        # 本来は住所検索APIを叩きます。
        return "35.7367", "139.8339" # 例：四ツ木駅周辺

    def fetch_route(self, start_node, goal_lat, goal_lon, date_time):
        """NAVITIME APIを使用してルートを検索"""
        url = "https://navitime-transport.p.rapidapi.com/transport_tyo/route"
        # 実際のリクエストパラメータ構築（簡略化しています）
        # 本来はここでAPIから最短・最安ルートを取得します
        # ユーザー様の要望に合わせ、現在は見本データを返すロジックを維持しつつ、
        # 入力された住所が反映されるように構成します。
        return [] 

    def _draw_text(self, draw, text, x, y, font_key, size_name, color):
        font = self.fonts[font_key][size_name]
        draw.text((x, y), text, font=font, fill=color)

    def generate_guide_image(self, address, house_name):
        """住所を基にガイド画像を生成"""
        # 1. 住所から目的地を特定（本来はここでAPIを叩く）
        # 2. 画像描画（見本デザインをベースに作成）
        
        height = 1200
        image = Image.new('RGB', (SIZE['width'], height), COLORS['bg'])
        draw = ImageDraw.Draw(image)
        
        # タイトル描画
        self._draw_text(draw, f"✈️ How to get to {house_name} ✈️", 250, 30, 'bold', 'title', COLORS['text_dark'])
        
        # --- 成田セクション ---
        self._draw_section(draw, 120, "Narita International Airport", COLORS['narita'])
        # --- 羽田セクション ---
        self._draw_section(draw, 580, "Haneda Airport", COLORS['haneda'])
        
        # 目的地表示
        draw.rounded_rectangle([(100, 1050), (1100, 1130)], radius=20, fill=COLORS['house_bg'], outline=COLORS['text_dark'])
        self._draw_text(draw, f"🏠 Destination: {address}", 150, 1070, 'bold', 'spot', COLORS['text_dark'])
        
        return image

    def _draw_section(self, draw, y, title, color):
        draw.rounded_rectangle([(50, y), (1150, y+70)], radius=15, fill=color)
        self._draw_text(draw, f"✈️ {title}", 80, y+15, 'bold', 'header', (255,255,255))
        # ここにルート詳細（電車・バス等）を並べる描画ロジックが入ります
