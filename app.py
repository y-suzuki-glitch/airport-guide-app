import streamlit as st
from airport_access_v10 import AirportAccessGuide
import io

st.set_page_config(page_title="民泊アクセスガイド", layout="wide")

st.title("🏡 民泊物件アクセスガイド自動作成")
st.write("住所を入力するだけで、成田・羽田からの最短ルートを画像にします。")

# サイドバーでAPIキーを管理
with st.sidebar:
    api_key = st.text_input("X-RapidAPI-Key (NAVITIME)", type="password")
    if not api_key and "NAVITIME_API_KEY" in st.secrets:
        api_key = st.secrets["NAVITIME_API_KEY"]

# メインフォーム
with st.form("main_form"):
    address = st.text_input("物件の正確な住所を入力してください", placeholder="東京都葛飾区四ツ木2-10-1")
    house_name = st.text_input("お部屋の表示名", value="Yotsugi House")
    submitted = st.form_submit_button("ガイド画像を生成する")

if submitted:
    if not api_key:
        st.error("APIキーを入力してください。")
    elif not address:
        st.error("住所を入力してください。")
    else:
        with st.spinner("最短ルートを検索中..."):
            try:
                guide = AirportAccessGuide(api_key)
                img = guide.generate_guide_image(address, house_name)
                
                # 表示
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), use_container_width=True)
                
                # ダウンロード
                st.download_button("画像を保存する", buf.getvalue(), "access_guide.png", "image/png")
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
