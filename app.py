import os
import io
import streamlit as st
from airport_access_v10 import generate_image, AirportAccessGenerator

st.set_page_config(page_title="Airport Access Generator", layout="wide")

st.markdown("<h1 style='text-align: center;'>✈️ Airport Access Sheet Generator</h1>", unsafe_allow_html=True)

# APIキーの取得
api_key = st.sidebar.text_input("NAVITIME (RapidAPI) Key", type="password")
if not api_key and "NAVITIME_API_KEY" in st.secrets:
    api_key = st.secrets["NAVITIME_API_KEY"]

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        prop_address = st.text_input("物件の住所 (Exact Address)", value="東京都葛飾区四つ木2-10-1")
    with col2:
        prop_name = st.text_input("お部屋名 (Property Name)", value="BAIYotsugi2chome101")

if st.button("生成する (Generate)"):
    if not prop_address:
        st.error("住所を入力してください")
    else:
        with st.spinner("作成中..."):
            # 元の v10.py の generate_image 関数を呼び出し
            png_bytes, plat, plng, near_en, walk_min, source = generate_image(
                prop_address, prop_name, api_key
            )
            st.image(png_bytes, use_container_width=True)
            st.download_button("ダウンロード", png_bytes, f"{prop_name}.png", "image/png")
