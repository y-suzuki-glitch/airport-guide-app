import streamlit as st
from airport_access_v10 import AirportAccessGuide
import io

st.set_page_config(page_title="民泊アクセスガイド生成", layout="wide")

st.title("🏠 民泊物件アクセスガイド自動作成")
st.markdown("住所を入力すると、成田・羽田からの最短ルート画像を生成します。")

# APIキー設定
if "NAVITIME_API_KEY" in st.secrets:
    api_key = st.secrets["NAVITIME_API_KEY"]
else:
    api_key = st.sidebar.text_input("X-RapidAPI-Keyを入力", type="password")

# 入力エリア
with st.form("input_form"):
    col1, col2 = st.columns(2)
    with col1:
        address = st.text_input("物件の住所", placeholder="東京都葛飾区四ツ木...")
    with col2:
        house_name = st.text_input("お部屋名（画像に表示）", value="My Guest House")
    
    submit = st.form_submit_button("アクセスガイド画像を生成")

if submit:
    if not api_key:
        st.error("APIキーが必要です。サイドバーに入力してください。")
    elif not address:
        st.error("住所を入力してください。")
    else:
        with st.spinner("最短ルートを計算し、画像を生成中..."):
            try:
                guide = AirportAccessGuide(api_key)
                img = guide.generate_guide_image(address, house_name)
                
                # 表示とダウンロード
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue())
                st.download_button("画像をダウンロード", buf.getvalue(), f"{house_name}_access.png", "image/png")
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
