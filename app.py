"""
Airport Access Sheet Generator – Streamlit Web App v10.2
=========================================================
v10.2: Streamlit Secrets対応 (NAVITIME_API_KEY を secrets.toml で永続化)
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
    .success-box {
        background: #efffef;
        border-left: 4px solid #1a7a3a;
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

# ── Check font availability ──────────────────────────────────
if not core._FONT_BOLD:
    st.warning(
        "⚠ 日本語フォントが見つかりませんでした。\n\n"
        "Streamlit Cloudの場合：リポジトリに **packages.txt** を追加して "
        "`fonts-noto-cjk` と記載し、アプリを再デプロイしてください。"
    )

# ── APIキー取得（優先順位: secrets → 環境変数 → サイドバー入力）────
def _get_saved_api_key() -> str:
    """Streamlit Secrets → 環境変数 → 空文字 の順で取得"""
    # ① Streamlit Cloud Secrets (secrets.toml)
    try:
        key = st.secrets.get("NAVITIME_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    # ② 環境変数
    return os.environ.get("NAVITIME_API_KEY", "")

saved_key = _get_saved_api_key()

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙ 設定")
    st.markdown("### NAVITIME APIキー")

    if saved_key:
        st.success("✅ APIキー設定済み（Secrets）\n\n経由地を正確に取得します")
        api_key_input = saved_key
        st.markdown(
            "<small>キーは Streamlit Cloud の Secrets に保存されています。"
            "変更する場合は Streamlit Cloud ダッシュボードから更新してください。</small>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("⚠ APIキー未設定")
        api_key_input = st.text_input(
            "RapidAPI キー（任意）",
            value="",
            type="password",
            placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            help="入力したキーはこのセッション中のみ有効です。永続化するには下記の手順でSecretsに登録してください。",
        )
        with st.expander("🔑 APIキーを永続化する方法（推奨）"):
            st.markdown("""
**Streamlit Cloud Secrets に登録すると毎回入力不要になります：**

1. [Streamlit Cloud](https://share.streamlit.io/) にログイン
2. アプリの **「︙」メニュー → Settings → Secrets** を開く
3. 以下を貼り付けて **Save** をクリック：
```toml
NAVITIME_API_KEY = "ここにRapidAPIキーを貼り付け"
```
4. アプリが自動再起動して有効になります

**APIキーの取得：**
1. [RapidAPI NAVITIME](https://rapidapi.com/navitimejapan-navitimejapan/api/navitime-route-totalnavi) にアクセス
2. 無料プランに登録（500回/月）
3. `X-RapidAPI-Key` をコピー
""")

    st.divider()
    st.markdown("**APIなし（固定DB）でも動作します**")
    st.markdown("経由地は主要路線の固定データを使用。精度はAPIより劣ります。")

    st.divider()
    st.markdown("### フォント状態")
    if core._FONT_BOLD:
        st.success(f"✅ フォント OK\n\n`{os.path.basename(core._FONT_BOLD)}`")
    else:
        st.error("❌ 日本語フォントなし\n\npackages.txt に `fonts-noto-cjk` を追加して再デプロイ")

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

api_key = api_key_input.strip() if isinstance(api_key_input, str) else ""

if api_key:
    st.markdown('<div class="success-box">🔑 <b>NAVITIME APIキー設定済み</b> — 実際の経由駅を自動取得します ✅</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="warning-box">ℹ <b>APIキー未設定</b> — 固定データベースで経由地を表示します（住所によらず同じ主要駅が表示されます）</div>', unsafe_allow_html=True)

# ── APIキー確認ボタン ────────────────────────────────────────
if api_key:
    test_btn = st.button("🔍 APIキーをテストする", use_container_width=False)
    if test_btn:
        with st.spinner("NAVITIMEに接続中..."):
            # 成田空港 → 東京駅 で簡易テスト
            test_result = core.navitime_transit(
                35.76419, 140.38605,   # 成田空港
                35.68124, 139.76712,   # 東京駅
                api_key, limit=1
            )
        if test_result:
            st.success(f"✅ APIキー有効！ルート {len(test_result)} 件取得できました。")
        else:
            st.error(
                "❌ APIキーが無効か、APIの呼び出しに失敗しました。\n\n"
                "**確認事項：**\n"
                "- RapidAPI の NAVITIME ページでキーをコピーし直してください\n"
                "- Streamlit Cloud Secrets の `NAVITIME_API_KEY` の値を確認してください\n"
                "- 無料プラン（500回/月）の上限に達していないか確認してください"
            )

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
            near_jp = "Nearest"; near_en = "Nearest Sta."

        # 3. Routes
        route_source = "NAVITIME API" if api_key else "固定DB（APIキー未設定）"
        status.info(f"🗺 ルートを計算中（{route_source}）...")
        progress.progress(55, text=f"ルートを取得中 ({route_source})...")

        # NAVITIMEテスト呼び出し（成功/失敗をユーザーに通知）
        navitime_ok = False
        if api_key:
            test_r = core.navitime_transit(
                35.76419, 140.38605, plat, plng, api_key, limit=1
            )
            if not test_r:
                st.warning(
                    "⚠ **NAVITIMEへの接続に失敗しました** — 固定DBに切り替えます。\n\n"
                    "APIキーが正しいか確認するには、上の「🔍 APIキーをテストする」ボタンを使ってください。"
                )
            else:
                navitime_ok = True
                st.info("🔑 NAVITIME API から実際のルートを取得中...")

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

        st.success("✅ 画像の生成が完了しました！")

        res_col1, res_col2, res_col3 = st.columns(3)
        with res_col1:
            st.metric("📍 座標", f"{plat:.4f}, {plng:.4f}")
        with res_col2:
            st.metric("🚉 最寄り駅", f"{near_en} ({walk_min}分)")
        with res_col3:
            actual_source = "NAVITIME API ✅" if (api_key and navitime_ok) else "固定DB ⚠"
            st.metric("📡 データ源", actual_source)

        st.image(png_bytes, caption=f"{prop_name} — Airport Access Sheet", use_container_width=True)

        filename = f"{(prop_name or 'property').replace(' ', '_')}_airport_access.png"
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
Airport Access Sheet Generator v10.2 &nbsp;|&nbsp;
Nominatim / Overpass / OSRM (無料API) &nbsp;|&nbsp;
<a href="https://rapidapi.com/navitimejapan-navitimejapan/api/navitime-route-totalnavi" target="_blank">NAVITIME RapidAPI</a>
</div>
""", unsafe_allow_html=True)
