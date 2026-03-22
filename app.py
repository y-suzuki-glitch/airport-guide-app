"""
Airport Access Sheet Generator – Streamlit Web App
====================================================
Usage:
    pip install streamlit pillow requests
    streamlit run app.py

Environment variables (optional):
    NAVITIME_API_KEY=<your_rapidapi_key>
"""

import os
import io
import streamlit as st

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Airport Access Sheet Generator",
    page_icon="✈",
    layout="centered",
)

# ── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a6e;
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1rem;
        color: #555;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .stButton > button {
        background-color: #1a3a8f;
        color: white;
        border-radius: 8px;
        padding: 0.55rem 2.5rem;
        font-size: 1.1rem;
        font-weight: 600;
        border: none;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #2952b3;
    }
    .stDownloadButton > button {
        background-color: #1a7a3a;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-size: 1rem;
        width: 100%;
    }
    .info-box {
        background: #eef4ff;
        border-left: 4px solid #1a3a8f;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        margin-bottom: 1rem;
        font-size: 0.92rem;
    }
    .warning-box {
        background: #fff8e6;
        border-left: 4px solid #d08000;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        margin-bottom: 1rem;
        font-size: 0.92rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────
st.markdown('<div class="main-title">✈ Airport Access Sheet Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">成田・羽田空港へのアクセス案内画像を自動生成</div>', unsafe_allow_html=True)
st.divider()

# ── Import core module ───────────────────────────────────────
try:
    import airport_access_v10 as core
    MODULE_OK = True
except ImportError as e:
    MODULE_OK = False
    st.error(f"⚠ airport_access_v10.py が見つかりません: {e}")
    st.stop()

# ── Sidebar: API key ─────────────────────────────────────────
with st.sidebar:
    st.header("⚙ 設定")
    st.markdown("### NAVITIME APIキー")
    env_key = os.environ.get("NAVITIME_API_KEY", "")
    api_key_input = st.text_input(
        "RapidAPI キー（任意）",
        value=env_key,
        type="password",
        placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        help="設定すると NAVITIME から実際のルートを取得します。未設定でも固定DBで動作します。",
    )

    st.divider()
    st.markdown("### APIキー取得方法")
    st.markdown("""
1. [RapidAPI](https://rapidapi.com/navitimejapan-navitimejapan/api/navitime-route-totalnavi) にアクセス
2. 無料プランに登録（500回/月）
3. `X-RapidAPI-Key` をコピーして上に貼り付け
""")
    st.divider()
    st.markdown("**APIなし（固定DB）でも動作します**")
    st.markdown("経由地は主要路線の固定データを使用。精度はAPIより劣ります。")

# ── Main form ────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    address = st.text_input(
        "📍 物件住所",
        placeholder="例: 東京都葛飾区四つ木2-14-14",
        help="日本語住所を入力してください（番地まで入力すると精度が上がります）",
    )

with col2:
    prop_name = st.text_input(
        "🏠 物件名",
        placeholder="例: BAIYotsugi2chome101",
        value="My Property",
        help="画像フッターに表示されます",
    )

# API key from sidebar
api_key = api_key_input.strip()

# Info messages
if api_key:
    st.markdown('<div class="info-box">🔑 <b>NAVITIME APIキー設定済み</b> — 実際のルートを自動取得します（経由地も正確に表示）</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="warning-box">ℹ <b>APIキー未設定</b> — 固定データベースで経由地を表示します（主要路線のみ）</div>', unsafe_allow_html=True)

# Generate button
generate_btn = st.button("🎨 画像を生成する", use_container_width=True)

st.divider()

# ── Generation logic ─────────────────────────────────────────
if generate_btn:
    if not address.strip():
        st.error("⚠ 住所を入力してください")
        st.stop()

    progress = st.progress(0, text="処理を開始しています...")
    status   = st.empty()

    try:
        # 1. Geocode
        status.info("🌍 住所をジオコーディング中...")
        progress.progress(10, text="住所を座標に変換中...")
        coord = core.geocode(address.strip())
        if not coord:
            st.error("❌ 住所の座標が取得できませんでした。住所を確認して再試行してください。")
            progress.empty()
            st.stop()
        plat, plng = coord

        # 2. Nearest station
        status.info("🚉 最寄り駅を検索中...")
        progress.progress(30, text="最寄り駅を検索中...")
        stns    = core.nearest_stations(plat, plng, radius=2000)
        near_jp = ""; near_en = ""; walk_min = 10

        if stns:
            s       = stns[0]
            tags    = s.get("tags", {})
            near_jp = tags.get("name", "")
            near_en = tags.get("name:en") or tags.get("name:ja_rm") or near_jp
            for sfx in (" Sta.", "駅", " Station", " station"):
                if near_en.endswith(sfx):
                    near_en = near_en[:-len(sfx)].strip()
            for sfx in ("駅", " Sta.", " Station"):
                if near_jp.endswith(sfx):
                    near_jp = near_jp[:-len(sfx)].strip()
            wr = core.osrm_walk(plat, plng, s["lat"], s["lon"])
            walk_min = wr[0] if wr else 10
        else:
            near_jp = "最寄り駅"; near_en = "Nearest Sta."

        # 3. Routes
        route_source = "NAVITIME API" if api_key else "固定DB"
        status.info(f"🗺 ルートを計算中（{route_source}）...")
        progress.progress(55, text=f"ルートを取得中 ({route_source})...")
        route_data = core.gather_routes(plat, plng, api_key=api_key)
        for d in route_data.values():
            d["walk_min"]   = walk_min
            d["nearest_jp"] = near_jp
            d["nearest_en"] = near_en

        # 4. Image
        status.info("🎨 画像を生成中...")
        progress.progress(80, text="PNG画像を生成中...")
        png_bytes = core.generate_image(prop_name.strip() or "My Property", route_data)

        progress.progress(100, text="完了！")
        status.empty()
        progress.empty()

        # ── Show results ─────────────────────────────────────
        st.success("✅ 画像の生成が完了しました！")

        # Result info
        res_col1, res_col2, res_col3 = st.columns(3)
        with res_col1:
            st.metric("📍 座標", f"{plat:.4f}, {plng:.4f}")
        with res_col2:
            st.metric("🚉 最寄り駅", f"{near_en} ({walk_min}分)")
        with res_col3:
            st.metric("📡 データ源", route_source)

        # Preview
        st.image(png_bytes, caption=f"{prop_name} — Airport Access Sheet", use_container_width=True)

        # Download button
        filename = f"{prop_name.replace(' ', '_')}_airport_access.png"
        st.download_button(
            label="⬇ PNG画像をダウンロード",
            data=png_bytes,
            file_name=filename,
            mime="image/png",
            use_container_width=True,
        )

    except Exception as e:
        progress.empty()
        status.empty()
        st.error(f"❌ エラーが発生しました: {e}")
        import traceback
        with st.expander("エラー詳細"):
            st.code(traceback.format_exc())

# ── Footer ───────────────────────────────────────────────────
st.divider()
st.markdown("""
<div style="text-align:center; color:#888; font-size:0.85rem;">
Airport Access Sheet Generator v10.0 &nbsp;|&nbsp;
Nominatim / Overpass / OSRM (無料API) &nbsp;|&nbsp;
<a href="https://rapidapi.com/navitimejapan-navitimejapan/api/navitime-route-totalnavi" target="_blank">NAVITIME RapidAPI</a>
</div>
""", unsafe_allow_html=True)
