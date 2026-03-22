# Airport Access Sheet Generator

## ファイル構成
```
airport_access_v10.py  ← コアロジック（CLI + Webアプリ共用）
app.py                 ← Streamlit Webアプリ
requirements.txt       ← 必要ライブラリ
```

## セットアップ
```bash
pip install -r requirements.txt
```

## Webアプリの起動
```bash
streamlit run app.py
```
ブラウザが自動で開きます（通常 http://localhost:8501）

## CLIで使う場合
```bash
# APIキーなし（固定DB）
python3 airport_access_v10.py --address "東京都葛飾区四つ木2-14-14" --name "BAIYotsugi2chome101" --output output.png

# NAVITIMEキーあり（正確なルート）
NAVITIME_API_KEY=xxxx python3 airport_access_v10.py --address "東京都..." --name "物件名" --output output.png

# デモモード
python3 airport_access_v10.py --demo --output demo.png
```

## NAVITIMEキー取得
1. https://rapidapi.com/navitimejapan-navitimejapan/api/navitime-route-totalnavi
2. 無料プランに登録（500回/月）
3. X-RapidAPI-Key をアプリに設定

## 経由地表示
- APIキーなし：最大2経由地（固定DB）
- APIキーあり：最大5経由地（実際の乗換駅を全表示）
