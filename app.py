"""
Airport Access Sheet Generator – Streamlit Web App v10.3
=========================================================
v10.3: Secretsを廃止し、サイドバーで常にAPIキーを入力できるシンプル設計
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
    .main-title { font-size:2rem; font-weight:700; color:#1a1a6e; text-align:center; margin-bottom:0.2rem; }
    .sub-title  { font-size:1rem; color:#555; text-align:center; margin-bottom:1.5rem; }
    .stButton > button {
        background-color:#1a3a8f; color:white; border-radius:8px;
        padding:0.55rem 2.5rem; font-size:1.1rem; font-weight:600; border:none; width:100%;
    }
    .stButton > button:hover { background-color:#2952b3; }
    .stDownloadButton > button {
        background-color:#1a7a3a; color:white; border-radius:8px;
        padding:0.5rem 2rem; font-size:1rem; width:100%;
    }
    .info-box    { background:#eef4ff; border-left:4px solid #1a3a8f; padding:0.8rem 1rem; border-radius:4px; margin-bottom:1rem; font-size:0.92rem; }
    .warning-box { background:#fff8e6; border-left:4px solid #d08000; padding:0.8rem 1rem; border-radius:4px; margin-bottom:1rem; font-size:0.92rem; }
    .success-box { background:#efffef; border-left:4px solid #1a7a3a; padding:0.8rem 1rem; border-radius:4px; margin-bottom:1rem; font-size:0.92rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────
st.markdown('<div class="main-title">✈ Airport Access Sheet Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">成田・羽田空港へのアクセス案内画像を自動生成</div>', unsafe_allow_html=True)
st.divider()

# ── Import core module ───────────────────────────────────────
try:
    import airport_access_v10 as core
except ImportError as e:
    st.error(f"⚠ airport_access_v10.py が見つかりません: {e}")
    st.stop()

if not core._FONT_BOLD:
    st.warning("⚠ 日本語フォントが見つかりません。packages.txt に `fonts-noto-cjk` を追加して再デプロイしてください。")

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙ 設定")

    st.markdown("### 🔑 NAVITIME APIキー")
    st.markdown(
        "<small>入力すると実際の経由駅を取得します。"
        "入力しなくても固定データで動作します。</small>",
        unsafe_allow_html=True,
    )

    # 常にテキスト入力欄を表示（Secrets不使用）
    api_key_input = st.text_input(
        "RapidAPI キーを貼り付け",
        value="",
        type="password",
        placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        help="RapidAPIのNAVITIMEページから「X-RapidAPI-Key」をコピーして貼り付けてください",
    )

    # APIキーテストボタン
    if api_key_input.strip():
        if st.button("🔍 このキーをテスト", use_container_width=True):
            with st.spinner("NAVITIME に接続中..."):
                items, err = core.navitime_transit(
                    35.76419, 140.38605,  # 成田空港
                    35.68124, 139.76712,  # 東京駅
                    api_key_input.strip(), limit=1
                )
            if err:
                st.error(f"❌ 失敗\n\n`{err}`")
            elif items:
                st.success(f"✅ 成功！ルート {len(items)} 件取得")
            else:
                st.warning("⚠ 接続OK、ただしルート0件（APIは動作中）")

    st.markdown("""
---
**APIキーの取得方法：**
1. [RapidAPI NAVITIME](https://rapidapi.com/navitimejapan-navitimejapan/api/navitime-route-totalnavi) を開く
2. 無料登録（500回/月）
3. **「X-RapidAPI-Key」** の値をコピー
4. 上の入力欄に貼り付け
---
**APIなしでも動作します**
固定データで主要経由駅を表示（住所によらず同一）
""")

    st.divider()
    st.markdown("### フォント状態")
    if core._FONT_BOLD:
        st.success(f"✅ フォント OK\n\n`{os.path.basename(core._FONT_BOLD)}`")
    else:
        st.error("❌ フォントなし")

# ── Main form ────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    address = st.text_input(
        "📍 物件住所",
        placeholder="例: 東京都葛飾区四つ木2-14-14",
        help="日本語住所（番地まで入力すると精度が上がります）",
    )
with col2:
    prop_name = st.text_input(
        "🏠 物件名",
        placeholder="例: BAIYotsugi2chome101",
        value="My Property",
        help="画像フッターに表示されます",
    )

api_key = api_key_input.strip()

if api_key:
    st.markdown('<div class="success-box">🔑 <b>APIキー入力済み</b> — 実際の経由駅をNAVITIMEから取得します</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="warning-box">ℹ <b>APIキー未入力</b> — 固定データで経由地を表示（住所によらず同じ主要駅が表示されます）</div>', unsafe_allow_html=True)

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
            progress.empty(); st.stop()
        plat, plng = coord

        # 2. Nearest station
        status.info("🚉 最寄り駅を検索中...")
        progress.progress(30, text="最寄り駅を検索中...")
        stns = core.nearest_stations(plat, plng, radius=2000)
        near_jp = ""; near_en = ""; walk_min = 10
        if stns:
            s = stns[0]; tags = s.get("tags", {})
            near_jp = tags.get("name", "")
            near_en = tags.get("name:en") or tags.get("name:ja_rm") or near_jp
            for sfx in (" Sta.", "駅", " Station", " station"):
                if near_en.endswith(sfx): near_en = near_en[:-len(sfx)].strip()
            for sfx in ("駅", " Sta.", " Station"):
                if near_jp.endswith(sfx): near_jp = near_jp[:-len(sfx)].strip()
            wr = core.osrm_walk(plat, plng, s["lat"], s["lon"])
            walk_min = wr[0] if wr else 10
        else:
            near_jp = "Nearest"; near_en = "Nearest Sta."

        # 3. Routes
        route_label = "NAVITIME API" if api_key else "固定DB"
        status.info(f"🗺 ルートを取得中（{route_label}）...")
        progress.progress(55, text=f"ルート取得中 ({route_label})...")
        route_data = core.gather_routes(plat, plng, api_key=api_key)

        # NAVITIMEエラーがあれば画面に表示
        navitime_errors = route_data.pop("_navitime_errors", {})
        navitime_raw    = route_data.pop("_navitime_raw", {})
        if api_key and navitime_errors:
            err_msgs = "\n".join(f"- {k}: {v}" for k, v in navitime_errors.items())
            st.warning(
                f"⚠ **NAVITIME API エラー** — 固定DBにフォールバックしました\n\n"
                f"エラー詳細：\n{err_msgs}"
            )
            # RAW JSON をデバッグ表示
            if navitime_raw:
                import json as _json
                with st.expander("🔬 NAVITIMEレスポンス RAW JSON（開発者向け）"):
                    for airport_key, raw_items in navitime_raw.items():
                        st.markdown(f"**{airport_key.upper()} — {len(raw_items)} items取得**")
                        if raw_items:
                            # 最初の item の sections type 一覧を表示
                            item0 = raw_items[0]
                            sections0 = item0.get("sections", [])
                            types_found = [s.get("type","?") for s in sections0]
                            st.markdown(f"sections types: `{types_found}`")
                            st.code(_json.dumps(item0, ensure_ascii=False, indent=2)[:2000])
                        else:
                            st.markdown("_items が空 (API から0件返却)_")
            actual_source = "固定DB（APIエラー）"
        elif api_key:
            actual_source = "NAVITIME API ✅"
        else:
            actual_source = "固定DB"

        for d in route_data.values():
            d["walk_min"]   = walk_min
            d["nearest_jp"] = near_jp
            d["nearest_en"] = near_en

        # 4. Image
        status.info("🎨 画像を生成中...")
        progress.progress(80, text="PNG画像を生成中...")
        png_bytes = core.generate_image(prop_name.strip() or "My Property", route_data)

        progress.progress(100, text="完了！")
        status.empty(); progress.empty()
        st.success("✅ 画像の生成が完了しました！")

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("📍 座標", f"{plat:.4f}, {plng:.4f}")
        with c2: st.metric("🚉 最寄り駅", f"{near_en} ({walk_min}分)")
        with c3: st.metric("📡 データ源", actual_source)

        st.image(png_bytes, caption=f"{prop_name} — Airport Access Sheet", use_container_width=True)
        filename = f"{(prop_name or 'property').replace(' ', '_')}_airport_access.png"
        st.download_button(
            label="⬇ PNG画像をダウンロード",
            data=png_bytes, file_name=filename, mime="image/png",
            use_container_width=True,
        )

    except Exception as e:
        progress.empty(); status.empty()
        st.error(f"❌ エラーが発生しました: {e}")
        import traceback
        with st.expander("エラー詳細"):
            st.code(traceback.format_exc())

# ── Footer ───────────────────────────────────────────────────
st.divider()
st.markdown("""
<div style="text-align:center; color:#888; font-size:0.85rem;">
Airport Access Sheet Generator v10.3 &nbsp;|&nbsp;
<a href="https://rapidapi.com/navitimejapan-navitimejapan/api/navitime-route-totalnavi" target="_blank">NAVITIME RapidAPI</a>
</div>
""", unsafe_allow_html=True)
