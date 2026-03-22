import streamlit as st
import datetime
import io
import os
# airport_access_v10.py から AirportAccessGuide クラスを読み込む
from airport_access_v10 import AirportAccessGuide

# --- ページ設定 ---
st.set_page_config(page_title="空港アクセスガイド作成アプリ", page_icon="✈️")

# --- タイトル ---
st.title("✈️ 空港アクセスガイド作成アプリ")
st.markdown("見本（BAIYotsugi2chome101）のデザインで、ハッキリとした画像を作成します。")

# --- セキュリティ：APIキーの取得 ---
# GitHubに公開するため、APIキーは直接コードに書かず、
# StreamlitのSecrets機能または画面からの入力を利用します。

# 1. 優先：Streamlit Secrets から取得 (公開運用向け)
# ※GitHub公開時は、Streamlit CloudのSettings > SecretsでNAVITIME_API_KEYを設定してください。
if "NAVITIME_API_KEY" in st.secrets:
    api_key = st.secrets["NAVITIME_API_KEY"]
else:
    # 2. 次点：画面から入力 (テスト向け)
    st.warning("⚠️ Streamlit Secrets に APIキーが設定されていません。")
    api_key = st.text_input("NAVITIME APIキー (RapidAPI) を入力してください", type="password")

# --- 入力フォーム ---
with st.form("guide_form"):
    st.subheader("1. ガイドを作成する")
    
    # 住所（お部屋名）
    house_name = st.text_input("お部屋名 (画像に表示されます)", value="BAIYotsugi2chome101")
    
    # 日付 (APIリクエスト用)
    today = datetime.date.today()
    date_str = st.date_input("到着日", value=today).strftime("%Y-%m-%d")
    
    # 送信ボタン
    submit_button = st.form_submit_button(label="ガイド画像を作成する")


# --- 画像生成と表示 ---
if submit_button:
    if not api_key:
        st.error("❌ NAVITIME APIキーを入力してください。")
    else:
        with st.spinner("画像を生成しています..."):
            try:
                # 修正した AirportAccessGuide クラスのインスタンスを作成
                guide = AirportAccessGuide(api_key)
                
                # 画像を生成
                img = guide.generate_guide_image(date_str)
                
                # PIL画像をBytesIOに変換 (Streamlitで表示・ダウンロードするため)
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes = img_bytes.getvalue()
                
                # --- 結果の表示 ---
                st.success("✅ 画像が生成されました！")
                st.image(img_bytes, caption=f"{house_name} アクセスガイド", use_column_width=True)
                
                # --- ダウンロードボタン ---
                filename = f"{house_name}_airport_access.png"
                st.download_button(
                    label="ファイルをダウンロード",
                    data=img_bytes,
                    file_name=filename,
                    mime="image/png"
                )
                
            except Exception as e:
                st.error(f"❌ 画像の生成中にエラーが発生しました: {e}")

# --- サイドバー ---
with st.sidebar:
    st.subheader("⚙️ 使い方")
    st.markdown("""
    1.  **APIキーを設定**: 画面上部の入力欄、またはStreamlit Secretsに「X-RapidAPI-Key」を設定します。
    2.  **お部屋名を入力**: 画像に表示される名称を入力します。
    3.  **日付を選択**: ルート検索を行う日付を選択します。
    4.  **作成ボタンをクリック**: 「ガイド画像を作成する」ボタンを押すと、画像が生成されます。
    5.  **ダウンロード**: 生成された画像の下にあるボタンからダウンロードできます。
    """)
    st.info("※現在は見本データを再現するモードで動作しています。")
