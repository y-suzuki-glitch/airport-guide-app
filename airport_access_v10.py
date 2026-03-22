import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import requests
from datetime import datetime
import io
import os

# --- 設定 ---
# 1. フォント設定 (Mac環境を想定)
# 見本のようなハッキリした文字にするため、太めのゴシック体と絵文字フォントを指定します。
FONT_PATHS = {
    'bold': '/System/Library/Fonts/jp/Hiragino Sans W6.ttc', # 太字ゴシック
    'regular': '/System/Library/Fonts/jp/Hiragino Sans W3.ttc', # 通常ゴシック
    'emoji': '/System/Library/Fonts/Apple Color Emoji.ttc' # 絵文字
}

# 2. カラー設定 (見本に合わせて濃く調整)
COLORS = {
    'narita': (230, 80, 50),     # 濃いオレンジ
    'haneda': (40, 160, 80),     # 濃いグリーン
    'bg': (230, 240, 255),       # 薄いブルー背景
    'text_dark': (20, 40, 80),   # 濃いネイビー（テキスト用）
    'text_light': (255, 255, 255),# 白（ヘッダー用）
    'box_bg': (210, 230, 250),   # 薄いブルーのボックス
    'house_bg': (255, 245, 220), # 薄いベージュのボックス
}

# 3. サイズ設定 (見本に合わせて大幅アップ)
SIZE = {
    'width': 1200,                # 全体の幅
    'header_height': 80,         # ヘッダーの高さ
    'font_title': 50,             # メインタイトルの文字サイズ
    'font_header': 35,            # 空港名の文字サイズ
    'font_spot': 30,              # 駅名・お部屋の文字サイズ
    'font_info': 24,              # 所要時間・金額の文字サイズ
    'icon_size': 40,              # アイコンのサイズ
}

# 4. アイコン設定 (見本に合わせて修正)
ICONS = {
    'skyliner': '🚃', # 京成スカイライナー
    'nex': '🚃',       # 成田エクスプレス
    'keisei': '🚃',    # 京成本線
    'keikyu': '🚃',    # 京急線
    'monorail': '🚝',   # モノレール
    'bus': '🚌',        # リムジンバス
    'taxi': '🚕',       # タクシー
    'walk': '🚶‍♂️',      # 徒歩
    'house': '🏠',      # お部屋
}


class AirportAccessGuide:
    def __init__(self, rapidapi_key):
        self.rapidapi_key = rapidapi_key
        self._load_fonts()

    def _load_fonts(self):
        """フォントを読み込む。存在しない場合はデフォルトフォントを使用。"""
        self.fonts = {}
        for key, path in FONT_PATHS.items():
            if os.path.exists(path):
                # sizes is a dictionary to store loaded fonts for different purposes
                sizes = {
                    'title': SIZE['font_title'],
                    'header': SIZE['font_header'],
                    'spot': SIZE['font_spot'],
                    'info': SIZE['font_info']
                }
                self.fonts[key] = {size_name: ImageFont.truetype(path, size_val) for size_name, size_val in sizes.items()}
            else:
                print(f"Warning: Font not found at {path}. Using default font.")
                self.fonts[key] = {size_name: ImageFont.load_default() for size_name in sizes}

    def _get_api_data(self, from_spot, to_spot, date_str):
        """NAVITIME APIからデータを取得する (簡易版)"""
        # ※本来はAPIリクエストを行うが、今回は見本画像を再現するために、
        #   提供されたデータに基づいてハードコーディングする。
        #   実際の運用時は、ここをAPIリクエストに書き換える必要がある。

        # 成田空港 (第2ターミナル) -> 四ツ木駅
        if from_spot == "Narita International Airport (Terminal 2)" and to_spot == "Yotsugi Sta. / 四ツ木駅":
             return [
                {"name": "Skyliner", "type": "skyliner", "time": "1H7min", "fare": "¥1,423", "change": ["Nippori", "Ueno"]},
                {"name": "N'EX", "type": "nex", "time": "1H15min", "fare": "¥3,070", "change": ["Tokyo"]},
                {"name": "Keisei Expre...", "type": "keisei", "time": "1H29min", "fare": "¥1,050", "change": ["Aoto", "Ueno"]},
                {"name": "Limousine Bus", "type": "bus", "time": "1H52min", "fare": "¥2,800", "change": ["Tokyo Sta."]},
                {"name": "Taxi", "type": "taxi", "time": "1H44min", "fare": "¥27,500", "change": []},
            ]
        # 羽田空港 (第3ターミナル) -> 四ツ木駅
        elif from_spot == "Haneda Airport (International Terminal 3)" and to_spot == "Yotsugi Sta. / 四ツ木駅":
            return [
                {"name": "Keikyu", "type": "keikyu", "time": "45min", "fare": "¥330", "change": ["Sengakuji"]},
                {"name": "Monorail", "type": "monorail", "time": "45min", "fare": "¥500", "change": ["Hamamatsucho"]},
                {"name": "Limousine Bus", "type": "bus", "time": "57min", "fare": "¥1,500", "change": ["Tokyo Sta."]},
                {"name": "Taxi", "type": "taxi", "time": "44min", "fare": "¥11,800", "change": []},
            ]
        # 四ツ木駅 -> お部屋
        elif from_spot == "Yotsugi Sta. / 四ツ木駅" and to_spot == "House / お部屋":
             return [{"name": "10 min walk", "type": "walk", "time": "10min", "fare": "", "change": []}]
        else:
            return []

    def _draw_text_with_emoji(self, draw, text, x, y, font_key, size_name, color):
        """絵文字を含むテキストを描画する簡易関数 (Mac環境用)"""
        # Hiragino Sans は絵文字に対応していないため、絵文字部分だけ Apple Color Emoji に切り替える
        # この実装は簡易版であり、複雑なテキストには対応していません。
        
        current_x = x
        for char in text:
            if char in ICONS.values(): # 絵文字の場合
                font = self.fonts['emoji'][size_name]
                draw.text((current_x, y), char, font=font, embedded_color=True)
                current_x += SIZE['icon_size'] + 5 # 絵文字の幅分進める
            else: # 通常文字の場合
                font = self.fonts[font_key][size_name]
                draw.text((current_x, y), char, font=font, fill=color)
                current_x += font.getbbox(char)[2] # 文字の幅分進める


    def _generate_airport_section(self, draw, start_y, airport_name, routes, color_key):
        """1つの空港セクション（成田または羽田）を生成する"""
        
        # 1. ヘッダーを描画
        header_rect = [(50, start_y), (SIZE['width'] - 50, start_y + SIZE['header_height'])]
        draw.rounded_rectangle(header_rect, radius=15, fill=COLORS[color_key], outline=None)
        
        # ヘッダーテキスト (白抜き、太字)
        header_text = f"✈️ {airport_name}"
        self._draw_text_with_emoji(draw, header_text, 80, start_y + 15, 'bold', 'header', COLORS['text_light'])
        
        # 2. ルートを描画
        route_y = start_y + SIZE['header_height'] + 30
        col_width = (SIZE['width'] - 100) / len(routes)
        
        for i, route in enumerate(routes):
            current_x = 50 + i * col_width
            
            # アイコンとルート名
            icon = ICONS.get(route['type'], '❓')
            route_text = f"{icon} {route['name']}"
            self._draw_text_with_emoji(draw, route_text, current_x + 10, route_y, 'bold', 'spot', COLORS['text_dark'])
            
            # 所要時間と金額
            info_text = f"{route['time']} {route['fare']}"
            self._draw_text_with_emoji(draw, info_text, current_x + 10 + SIZE['icon_size'] + 5, route_y + 35, 'regular', 'info', COLORS['text_dark'])
            
            # 乗り換え駅 (もしあれば)
            if route['change']:
                change_y = route_y + 80
                for change in route['change']:
                    change_rect = [(current_x + 10, change_y), (current_x + col_width - 10, change_y + 50)]
                    draw.rounded_rectangle(change_rect, radius=25, fill=COLORS['box_bg'], outline=COLORS['text_dark'], width=1)
                    
                    # 駅名 (中央揃え)
                    font = self.fonts['regular']['spot']
                    bbox = draw.textbbox((0, 0), change, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_x = current_x + 10 + (col_width - 20 - text_width) / 2
                    draw.text((text_x, change_y + 10), change, font=font, fill=COLORS['text_dark'])
                    
                    # 矢印 (もしタクシー以外なら)
                    if route['type'] != 'taxi':
                         arrow_y = change_y + 50
                         arrow_x = current_x + col_width / 2
                         draw.line([(arrow_x, arrow_y), (arrow_x, arrow_y + 20)], fill=COLORS['text_dark'], width=2)
                         draw.polygon([(arrow_x - 5, arrow_y + 15), (arrow_x + 5, arrow_y + 15), (arrow_x, arrow_y + 25)], fill=COLORS['text_dark'])
                    
                    change_y += 80
            else: # タクシーの場合は、四ツ木駅まで矢印を伸ばす
                 arrow_start_y = route_y + 70
                 arrow_end_y = route_y + 280
                 arrow_x = current_x + col_width / 2
                 draw.line([(arrow_x, arrow_start_y), (arrow_x, arrow_end_y)], fill=COLORS['text_dark'], width=2)
                 draw.polygon([(arrow_x - 5, arrow_end_y - 10), (arrow_x + 5, arrow_end_y - 10), (arrow_x, arrow_end_y)], fill=COLORS['text_dark'])


    def generate_guide_image(self, date_str):
        """ガイド画像を生成する"""
        
        # 1. 土台の画像を作成
        height = 1200 # 全体の高さを調整
        image = Image.new('RGB', (SIZE['width'], height), COLORS['bg'])
        draw = ImageDraw.Draw(image)
        
        # 2. メインタイトル
        title_text = "✈️ How to get from the Airport to the House ✈️"
        # 中央揃え
        font = self.fonts['bold']['title']
        bbox = draw.textbbox((0, 0), title_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (SIZE['width'] - text_width) / 2
        self._draw_text_with_emoji(draw, title_text, text_x, 30, 'bold', 'title', COLORS['text_dark'])
        
        # 3. 成田空港セクション
        narita_routes = self._get_api_data("Narita International Airport (Terminal 2)", "Yotsugi Sta. / 四ツ木駅", date_str)
        self._generate_airport_section(draw, 100, "Narita International Airport (Terminal 2)", narita_routes, 'narita')
        
        # 4. 羽田空港セクション
        haneda_routes = self._get_api_data("Haneda Airport (International Terminal 3)", "Yotsugi Sta. / 四ツ木駅", date_str)
        self._generate_airport_section(draw, 600, "Haneda Airport (International Terminal 3)", haneda_routes, 'haneda')
        
        # 5. 共通部分 (四ツ木駅 -> お部屋)
        common_y = 1000
        
        # 四ツ木駅ボックス
        yotsugi_text = "四ツ木 Sta. / 四ツ木駅"
        yotsugi_rect = [(50, common_y), (SIZE['width'] - 50, common_y + 60)]
        draw.rounded_rectangle(yotsugi_rect, radius=30, fill=COLORS['box_bg'], outline=COLORS['text_dark'], width=1)
        
        # 駅名 (中央揃え)
        font = self.fonts['bold']['spot']
        bbox = draw.textbbox((0, 0), yotsugi_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (SIZE['width'] - text_width) / 2
        draw.text((text_x, common_y + 10), yotsugi_text, font=font, fill=COLORS['text_dark'])
        
        # 徒歩アイコンとルート
        walk_routes = self._get_api_data("Yotsugi Sta. / 四ツ木駅", "House / お部屋", date_str)
        walk_route = walk_routes[0]
        walk_text = f"{ICONS['walk']} {walk_route['name']}"
        
        walk_y = common_y + 70
        # 中央揃え
        font = self.fonts['regular']['spot']
        bbox = draw.textbbox((0, 0), walk_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (SIZE['width'] - text_width) / 2
        self._draw_text_with_emoji(draw, walk_text, text_x, walk_y, 'regular', 'spot', COLORS['haneda']) # 徒歩は緑色
        
        # お部屋ボックス
        house_text = f"{ICONS['house']} House / お部屋"
        house_y = walk_y + 50
        house_rect = [(50, house_y), (SIZE['width'] - 50, house_y + 60)]
        draw.rounded_rectangle(house_rect, radius=30, fill=COLORS['house_bg'], outline=COLORS['narita'], width=1)
        
        # お部屋名 (中央揃え)
        font = self.fonts['bold']['spot']
        bbox = draw.textbbox((0, 0), house_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (SIZE['width'] - text_width) / 2
        self._draw_text_with_emoji(draw, house_text, text_x, house_y + 10, 'bold', 'spot', COLORS['text_dark'])
        
        # 6. フッター
        footer_text = "Fares and travel times are estimates only. Actual costs and durations may vary depending on timing, traffic, and other conditions.\nBAIYotsugi2chome101"
        footer_y = height - 80
        # 中央揃え
        font = self.fonts['regular']['info']
        bbox = draw.textbbox((0, 0), footer_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (SIZE['width'] - text_width) / 2
        draw.text((text_x, footer_y), footer_text, font=font, fill=COLORS['text_dark'])
        
        return image


if __name__ == "__main__":
    # テスト用
    guide = AirportAccessGuide("dummy_key")
    img = guide.generate_guide_image("2024-05-20")
    img.save("airport_access_v11.png")
