import os
import io
import streamlit as st
# airport_access_v10.py から必要な関数をインポート
import airport_access_v10 as core

st.set_page_config(page_title="Airport Access Sheet Generator", page_icon="✈", layout="centered")

st.markdown("<h1 style='text-align: center; color: #1a1a6e;'>🏠 Airport Access Sheet Generator</h1>", unsafe_allow_html=True)

# APIキーの取得
api_key = st.sidebar.text_input("X-RapidAPI-Key (NAVITIME)", type="password")
if not api_key and "NAVITIME_API_KEY" in st.secrets:
    api_key = st.secrets["NAVITIME_API_KEY"]

# 入力フォーム
with st.container():
    address = st.text_input("物件の正確な住所 (Exact Address)", value="東京都葛飾区四つ木2-10-1")
    prop_name = st.text_input("お部屋名 (Property Name)", value="BAIYotsugi2chome101")

if st.button("生成する (Generate)"):
    if not address:
        st.error("住所を入力してください")
    else:
        status = st.empty()
        status.info("⏳ 最短ルートを計算し、画像を生成しています...")
        try:
            # 修正した v10.py の generate_image を呼び出す
            # 元の v10.py の戻り値の数に合わせて受け取る
            result = core.generate_image(address, prop_name, api_key)
            png_bytes = result[0]
            
            status.success("✅ 生成完了！")
            st.image(png_bytes, use_container_width=True)
            
            st.download_button(
                label="⬇ PNG画像をダウンロード",
                data=png_bytes,
                file_name=f"{prop_name}_access.png",
                mime="image/png"
            )
        except Exception as e:
            status.empty()
            st.error(f"❌ エラーが発生しました: {e}")
