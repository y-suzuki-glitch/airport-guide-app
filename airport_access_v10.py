#!/usr/bin/env python3
"""
Airport Access Image Generator v10.0
=====================================
Changes from v8:
  - NAVITIME Route API (RapidAPI) integration: when NAVITIME_API_KEY env var is set,
    actual transit routes are fetched; otherwise falls back to built-in fixed DB.
  - via_stops now supports up to 5 entries (all transfers shown).
  - col_h_px / draw_col updated to render up to 5 via boxes.
  - Single clean file – no duplicate dataclass definitions.
  - Web app compatible: generate_image() accepts bytes output (io.BytesIO).
"""

import os, sys, math, time, argparse, re, io, requests, base64, platform
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ── cairosvg optional ────────────────────────────────────────
_CAIROSVG_OK = False
try:
    import cairosvg as _cairosvg
    _CAIROSVG_OK = True
except (ImportError, OSError, Exception):
    _cairosvg = None

_IS_MACOS = (platform.system() == "Darwin")

# ── Font paths ───────────────────────────────────────────────
FONT_BOLD   = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_MEDIUM = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EMOJI_PATH  = os.path.join(_SCRIPT_DIR, "NotoColorEmoji.ttf")
EMOJI_PATH2 = os.path.join(_SCRIPT_DIR, "NotoColorEmoji-Regular.ttf")
_JP_FALLBACKS = [FONT_BOLD, "C:/Windows/Fonts/meiryo.ttc",
                 "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"]
_APPLE_EMOJI_PATHS = [
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "/System/Library/Fonts/Supplemental/Apple Color Emoji.ttc",
]
_EMOJI_FALLBACKS = (
    [EMOJI_PATH, EMOJI_PATH2]
    + (_APPLE_EMOJI_PATHS if _IS_MACOS else [])
)

_jp_cache: Dict[Tuple, ImageFont.FreeTypeFont] = {}

def jp(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    k = (size, bold)
    if k not in _jp_cache:
        paths = _JP_FALLBACKS if bold else [FONT_MEDIUM] + _JP_FALLBACKS
        for p in paths:
            if p and os.path.exists(p):
                try:
                    _jp_cache[k] = ImageFont.truetype(p, size)
                    break
                except Exception:
                    pass
        else:
            _jp_cache[k] = ImageFont.load_default()
    return _jp_cache[k]

# ── Embedded badge icons (no emoji font needed) ──────────────
_BADGES: Dict[str, Tuple] = {
    "SKYLINER":  ((220, 70, 30),  "SKYLINER"),
    "NEX":       ((30, 90, 180),  "N'EX"),
    "KEISEI":    ((200, 40, 120), "KEISEI"),
    "KEIKYU":    ((200, 20, 40),  "KEIKYU"),
    "MONORAIL":  ((0, 120, 180),  "MONO"),
    "BUS":       ((30, 140, 60),  "BUS"),
    "TAXI":      ((180, 140, 0),  "TAXI"),
}

_BASE64_ICONS: Dict[str, str] = {}  # populated lazily

def _pil_airplane(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = (50, 120, 220); m = size // 2; r = int(size * 0.38)
    d.ellipse([m-r, m-r, m+r, m+r], fill=c)
    d.polygon([(m, m-r-4),(m-10,m+4),(m+10,m+4)], fill=(255,255,255))
    d.polygon([(m-r-4,m+4),(m,m+10),(m,m-4)], fill=(255,255,255))
    d.polygon([(m+r+4,m+4),(m,m+10),(m,m-4)], fill=(255,255,255))
    return img

def _pil_badge(text: str, color: Tuple, size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 5
    d.rounded_rectangle([2, 4, size-2, size-4], radius=r, fill=color)
    f = jp(max(8, size // 4), True)
    tw = d.textbbox((0,0), text, font=f)[2]
    th = d.textbbox((0,0), text, font=f)[3]
    d.text(((size - tw) // 2, (size - th) // 2), text, font=f, fill=(255,255,255))
    return img

def emoji_img(ch: str, size: int = 28) -> Image.Image:
    # Custom badge icons
    if ch in _BADGES:
        color, txt = _BADGES[ch]
        return _pil_badge(txt, color, size)
    # Emoji font attempt
    for fp in _EMOJI_FALLBACKS:
        if fp and os.path.exists(fp):
            try:
                ef = ImageFont.truetype(fp, size)
                tmp = Image.new("RGBA", (size*2, size*2), (0,0,0,0))
                td  = ImageDraw.Draw(tmp)
                td.text((0, 0), ch, font=ef, embedded_color=True)
                bb  = tmp.getbbox()
                if bb:
                    crop = tmp.crop(bb).resize((size, size), Image.LANCZOS)
                    return crop
            except Exception:
                pass
    # PIL fallback
    if ch == "✈":
        return _pil_airplane(size)
    # Generic colored circle with letter
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.ellipse([1,1,size-2,size-2], fill=(100,100,200))
    letter = ch[0] if ch else "?"
    f  = jp(size // 2)
    tw = d.textbbox((0,0), letter, font=f)[2]
    th = d.textbbox((0,0), letter, font=f)[3]
    d.text(((size-tw)//2, (size-th)//2), letter, font=f, fill=(255,255,255))
    return img

def paste_em(img: Image.Image, ch: str, cx: int, cy: int, size: int = 28):
    em = emoji_img(ch, size)
    w, h = em.size
    img.paste(em, (cx - w // 2, cy - h // 2), em)

# ────────────────────────────────────────────────────────────
# NAVITIME API integration
# ────────────────────────────────────────────────────────────
UA = "AirportAccessImageTool/10.0"

def navitime_transit(
    start_lat: float, start_lng: float,
    goal_lat:  float, goal_lng:  float,
    api_key:   str,
    departure_time: str = None,          # "2025-06-01T10:00:00"
    limit: int = 5,
) -> List[dict]:
    """
    Call NAVITIME Route (totalnavi) API via RapidAPI.
    Returns list of route dicts (raw JSON items from 'items' array).
    Each item has: summary.move, summary.fare.iccard,
                   summary.move_section[].transport.name etc.
    Returns [] on error.
    """
    if not api_key:
        return []

    if not departure_time:
        departure_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    url     = "https://navitime-route-totalnavi.p.rapidapi.com/route_transit"
    headers = {
        "X-RapidAPI-Key":  api_key,
        "X-RapidAPI-Host": "navitime-route-totalnavi.p.rapidapi.com",
    }
    params = {
        "start":       f"{start_lat},{start_lng}",
        "goal":        f"{goal_lat},{goal_lng}",
        "start_time":  departure_time,
        "limit":       limit,
        "datum":       "wgs84",
        "coord_unit":  "degree",
        "lang":        "en",
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except Exception as e:
        print(f"  [NAVITIME] API error: {e}")
        return []


def parse_navitime_route(item: dict) -> Optional[dict]:
    """
    Convert one NAVITIME route item into our internal dict:
    { label, icon, mode, duration, fare, via, hub, hub_lat, hub_lng }
    via = list of transfer station names (all of them, up to 8)
    """
    try:
        summary = item.get("summary", {})
        total_min = int(summary.get("move_time", 0)) // 60
        fare_info  = summary.get("fare", {})
        fare       = int(fare_info.get("iccard") or fare_info.get("total_fare") or 0)

        # Extract sections
        sections = item.get("sections", [])
        # Collect transit legs (train / bus)
        transit_legs = [s for s in sections if s.get("type") in ("train", "bus")]
        walk_legs    = [s for s in sections if s.get("type") == "move"
                        and s.get("transport", {}).get("type") == "walk"]

        if not transit_legs:
            return None  # walk-only or error

        # Determine primary mode and label
        first_leg  = transit_legs[0]
        last_leg   = transit_legs[-1]
        tp         = first_leg.get("transport", {})
        mode_type  = first_leg.get("type", "train")
        line_name  = tp.get("line_name", tp.get("name", "Transit"))

        # Choose icon by line name
        icon = _choose_icon(line_name)
        # Short label (max 14 chars)
        label = _shorten_label(line_name)

        # Build via list: boarding station of each leg EXCEPT the very first
        # boarding + alighting of final leg excluded (airport / property handled elsewhere)
        via = []
        for i, leg in enumerate(transit_legs):
            dep_node = leg.get("from_node", {})
            arr_node = leg.get("to_node", {})
            dep_name = dep_node.get("name", "")
            arr_name = arr_node.get("name", "")
            if i == 0:
                # first departure is the airport – skip; add arrival if not last leg
                if len(transit_legs) > 1:
                    via.append(_clean_station(arr_name))
            else:
                # add departure (= transfer station) and arrival if transfer again
                via.append(_clean_station(dep_name))
                if i < len(transit_legs) - 1:
                    via.append(_clean_station(arr_name))

        # Remove empty / duplicate
        seen = set()
        clean_via = []
        for v in via:
            if v and v not in seen:
                seen.add(v)
                clean_via.append(v)

        # Hub = last transit arrival (nearest major station before walk to property)
        hub_node = last_leg.get("to_node", {})
        hub_name = _clean_station(hub_node.get("name", ""))
        hub_lat  = hub_node.get("coord", {}).get("lat", 0)
        hub_lng  = hub_node.get("coord", {}).get("lon", 0)

        return dict(
            label    = label,
            icon     = icon,
            mode     = "bus" if mode_type == "bus" else "train",
            duration = max(1, total_min),
            fare     = fare,
            via      = clean_via,
            hub      = hub_name,
            hub_lat  = hub_lat,
            hub_lng  = hub_lng,
        )
    except Exception as e:
        print(f"  [parse_navitime] {e}")
        return None


def _clean_station(name: str) -> str:
    for sfx in (" Sta.", " Station", " station", "駅", "站"):
        if name.endswith(sfx):
            name = name[:-len(sfx)].strip()
    return name.strip()


def _shorten_label(name: str) -> str:
    # Map common Japanese line names to short English labels
    TABLE = {
        "スカイライナー": "Skyliner",
        "成田エクスプレス": "N'EX",
        "京成本線": "Keisei Exp.",
        "京急本線": "Keikyu",
        "東京モノレール": "Monorail",
        "リムジンバス": "Limousine Bus",
        "空港リムジン": "Limousine Bus",
        "Skyliner": "Skyliner",
        "Narita Express": "N'EX",
        "Keisei Main Line": "Keisei",
        "Keikyu Main Line": "Keikyu",
        "Tokyo Monorail": "Monorail",
    }
    for k, v in TABLE.items():
        if k in name:
            return v
    return name[:14]


def _choose_icon(line_name: str) -> str:
    ln = line_name.lower()
    if "skyliner" in ln or "スカイライナー" in line_name:
        return "SKYLINER"
    if "narita express" in ln or "成田エクスプレス" in line_name or "n'ex" in ln:
        return "NEX"
    if "keisei" in ln or "京成" in line_name:
        return "KEISEI"
    if "keikyu" in ln or "京急" in line_name:
        return "KEIKYU"
    if "monorail" in ln or "モノレール" in line_name:
        return "MONORAIL"
    if "bus" in ln or "バス" in line_name:
        return "🚌"
    return "🚆"


# ────────────────────────────────────────────────────────────
# Airport route fallback database (used when no API key)
# ────────────────────────────────────────────────────────────
NARITA_ROUTES_DB = [
    dict(label="Skyliner",       icon="SKYLINER", mode="train", duration=51,
         fare=1423, via=["Nippori", "Ueno"],
         hub="Ueno",   hub_lat=35.7141, hub_lng=139.7774),
    dict(label="N'EX",           icon="NEX",      mode="train", duration=53,
         fare=3070, via=["Tokyo"],
         hub="Tokyo",  hub_lat=35.6812, hub_lng=139.7671),
    dict(label="Keisei Express", icon="KEISEI",   mode="train", duration=78,
         fare=1050, via=["Aoto", "Ueno"],
         hub="Aoto",   hub_lat=35.7567, hub_lng=139.8606),
    dict(label="Limousine Bus",  icon="🚌",       mode="bus",   duration=90,
         fare=2800, via=["Tokyo Sta."],
         hub="Tokyo",  hub_lat=35.6812, hub_lng=139.7671),
]

HANEDA_ROUTES_DB = [
    dict(label="Keikyu",        icon="KEIKYU",   mode="train", duration=13,
         fare=330,  via=["Sengakuji"],
         hub="Sengakuji",    hub_lat=35.6381, hub_lng=139.7397),
    dict(label="Monorail",      icon="MONORAIL", mode="train", duration=18,
         fare=500,  via=["Hamamatsucho"],
         hub="Hamamatsucho", hub_lat=35.6555, hub_lng=139.7572),
    dict(label="Limousine Bus", icon="🚌",       mode="bus",   duration=35,
         fare=1500, via=["Tokyo Sta."],
         hub="Tokyo",         hub_lat=35.6812, hub_lng=139.7671),
]

AIRPORT_COORDS = {
    "narita": (35.7647, 140.3863),
    "haneda": (35.5494, 139.7798),
}


# ────────────────────────────────────────────────────────────
# Geocoding helpers (free, no key)
# ────────────────────────────────────────────────────────────
def geocode(address: str) -> Optional[Tuple[float, float]]:
    candidates = [address, re.sub(r'[-\d]+$', '', address).strip()]
    for addr in dict.fromkeys(candidates):
        try:
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": addr, "format": "json", "countrycodes": "jp", "limit": 1},
                headers={"User-Agent": UA}, timeout=12,
            )
            d = r.json()
            if d:
                return float(d[0]["lat"]), float(d[0]["lon"])
        except Exception as e:
            print(f"  [Nominatim] {e}")
        time.sleep(1)
    return None


def nearest_stations(lat: float, lng: float, radius=2000) -> list:
    def _dist2(e):
        dy = (e["lat"] - lat) * 111000
        dx = (e["lon"] - lng) * 111000 * math.cos(math.radians(lat))
        return math.sqrt(dy*dy + dx*dx)

    q = f"""[out:json][timeout:30];
(
  node["railway"="station"](around:{radius},{lat},{lng});
  node["station"="subway"](around:{radius},{lat},{lng});
  node["railway"="halt"](around:{radius},{lat},{lng});
);
out body;"""
    try:
        r   = requests.post("https://overpass-api.de/api/interpreter", data=q, timeout=30)
        els = r.json().get("elements", [])
        stns = [e for e in els if e.get("tags", {}).get("name")]
        if stns:
            return sorted(stns, key=_dist2)
        print("  [Overpass] 結果0件、Nominatimで再試行")
    except Exception as e:
        print(f"  [Overpass] {e} → Nominatimで再試行")

    delta = radius / 111000
    try:
        params = {
            "q": "railway station", "format": "json", "limit": 10,
            "viewbox": f"{lng-delta},{lat-delta},{lng+delta},{lat+delta}",
            "bounded": 1, "addressdetails": 1,
        }
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params=params, headers={"User-Agent": UA}, timeout=15)
        results = r.json()
        converted = []
        for res in results:
            name = res.get("name") or res.get("display_name", "").split(",")[0]
            if not name:
                continue
            converted.append({
                "lat": float(res["lat"]), "lon": float(res["lon"]),
                "tags": {"name": name, "railway": "station"},
            })
        if converted:
            return sorted(converted, key=_dist2)
    except Exception as e:
        print(f"  [Nominatim] {e}")
    return []


def osrm_walk(flat, flng, tlat, tlng) -> Optional[Tuple[int, int]]:
    url = f"https://router.project-osrm.org/route/v1/walking/{flng},{flat};{tlng},{tlat}"
    try:
        d = requests.get(url, params={"overview": "false"}, timeout=10).json()
        if d.get("routes"):
            rt = d["routes"][0]
            return max(1, int(rt["duration"]) // 60), int(rt["distance"])
    except Exception as e:
        print(f"  [OSRM walk] {e}")
    return None


def osrm_drive(flat, flng, tlat, tlng) -> Optional[Tuple[int, int]]:
    url = f"https://router.project-osrm.org/route/v1/driving/{flng},{flat};{tlng},{tlat}"
    try:
        d = requests.get(url, params={"overview": "false"}, timeout=10).json()
        if d.get("routes"):
            rt = d["routes"][0]
            return max(1, int(rt["duration"]) // 60), int(rt["distance"])
    except Exception as e:
        print(f"  [OSRM drive] {e}")
    return None


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    R = 6371000; p = math.radians
    dlat = p(lat2-lat1); dlng = p(lng2-lng1)
    a = math.sin(dlat/2)**2 + math.cos(p(lat1))*math.cos(p(lat2))*math.sin(dlng/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def hub_to_prop_min(hub_lat, hub_lng, plat, plng) -> int:
    dist = haversine_m(hub_lat, hub_lng, plat, plng)
    return max(3, int(dist / (30000/60) + 5))


def taxi_fare(dist_m: int) -> int:
    b, bd, u, ud = 500, 1096, 100, 255
    return b if dist_m <= bd else b + math.ceil((dist_m - bd) / ud) * u


# ────────────────────────────────────────────────────────────
# Route data model
# ────────────────────────────────────────────────────────────
@dataclass
class RouteInfo:
    mode:           str
    icon:           str
    label:          str
    duration_min:   int
    fare_yen:       int
    via_stops:      List[str] = field(default_factory=list)
    is_recommended: bool = False


def compute_routes_db(plat, plng, db) -> List[RouteInfo]:
    """Compute routes using fixed DB (fallback mode)."""
    results = []
    for r in db:
        extra = hub_to_prop_min(r["hub_lat"], r["hub_lng"], plat, plng)
        results.append(RouteInfo(
            mode         = r["mode"],
            icon         = r["icon"],
            label        = r["label"],
            duration_min = r["duration"] + extra,
            fare_yen     = r["fare"],
            via_stops    = r["via"][:],
        ))
    return results


def compute_routes_navitime(
    airport_lat: float, airport_lng: float,
    prop_lat: float, prop_lng: float,
    api_key: str,
    limit: int = 5,
) -> List[RouteInfo]:
    """Fetch live routes from NAVITIME API."""
    raw_items = navitime_transit(
        airport_lat, airport_lng,
        prop_lat,    prop_lng,
        api_key,     limit=limit,
    )
    routes = []
    for item in raw_items:
        parsed = parse_navitime_route(item)
        if parsed:
            routes.append(RouteInfo(
                mode         = parsed["mode"],
                icon         = parsed["icon"],
                label        = parsed["label"],
                duration_min = parsed["duration"],
                fare_yen     = parsed["fare"],
                via_stops    = parsed["via"],
            ))
    return routes


def compute_taxi(alat, alng, plat, plng) -> RouteInfo:
    res = osrm_drive(alat, alng, plat, plng)
    if res:
        dur, dist = res
        return RouteInfo("taxi", "🚕", "Taxi", dur, taxi_fare(dist), [])
    dist = int(haversine_m(alat, alng, plat, plng) * 1.4)
    dur  = max(20, int(dist / (40000/60)))
    return RouteInfo("taxi", "🚕", "Taxi", dur, taxi_fare(dist), [])


def gather_routes(plat: float, plng: float, api_key: str = "") -> dict:
    """
    Build route_data dict for narita and haneda.
    Uses NAVITIME API when api_key is set; falls back to DB otherwise.
    """
    data = {}
    for ak, (alat, alng) in AIRPORT_COORDS.items():
        routes: List[RouteInfo] = []

        if api_key:
            print(f"  [NAVITIME] Fetching routes from {ak}...")
            routes = compute_routes_navitime(alat, alng, plat, plng, api_key)
            if routes:
                print(f"  [NAVITIME] Got {len(routes)} routes for {ak}")
            else:
                print(f"  [NAVITIME] No routes returned for {ak}, using fallback DB")

        if not routes:
            db = NARITA_ROUTES_DB if ak == "narita" else HANEDA_ROUTES_DB
            routes = compute_routes_db(plat, plng, db)

        routes.append(compute_taxi(alat, alng, plat, plng))

        def sc(r):
            return r.duration_min * 0.5 + (r.fare_yen or 99999) * 0.0008

        min(routes, key=sc).is_recommended = True
        data[ak] = dict(routes=routes, walk_min=0)
    return data


def build_mock() -> dict:
    return {
        "narita": dict(
            routes=[
                RouteInfo("train","SKYLINER","Skyliner",       75, 1423, ["Nippori","Ueno"], is_recommended=True),
                RouteInfo("train","NEX",     "N'EX",           80, 3070, ["Tokyo"]),
                RouteInfo("train","KEISEI",  "Keisei Express", 90, 1050, ["Aoto","Ueno"]),
                RouteInfo("bus",  "🚌",      "Limousine Bus",  95, 2800, ["Tokyo Sta."]),
                RouteInfo("taxi", "🚕",      "Taxi",          104,27500, []),
            ],
            walk_min=10, nearest_jp="四ツ木", nearest_en="Yotsugi",
        ),
        "haneda": dict(
            routes=[
                RouteInfo("train","KEIKYU",  "Keikyu",          45,  330, ["Sengakuji"], is_recommended=True),
                RouteInfo("train","MONORAIL","Monorail",         45,  500, ["Hamamatsucho"]),
                RouteInfo("bus",  "🚌",      "Limousine Bus",   57, 1500, ["Tokyo Sta."]),
                RouteInfo("taxi", "🚕",      "Taxi",             44,11800, []),
            ],
            walk_min=10, nearest_jp="四ツ木", nearest_en="Yotsugi",
        ),
    }


# ────────────────────────────────────────────────────────────
# Color palette
# ────────────────────────────────────────────────────────────
BG         = (210, 230, 255)
WHITE      = (255, 255, 255)
PANEL_OUT  = (155, 195, 225)
HDR_NARITA = (220,  70,  30)
HDR_HANEDA = ( 45, 175,  80)
STN_BG     = (240, 248, 255)
STN_OUT    = (150, 190, 220)
ARROW_C    = ( 85, 135, 200)
GARROW_C   = ( 35, 135,  45)
REC_C      = (198,  22,  22)
TITLE_C    = ( 18,  26,  88)
SEP_C      = (175, 210, 235)
NEAR_BG    = (222, 240, 255)
NEAR_OUT   = (125, 175, 215)
HOUSE_BG   = (255, 244, 220)
HOUSE_OUT  = (192, 158, 105)
WALK_C     = ( 28, 108,  32)


# ────────────────────────────────────────────────────────────
# Drawing utilities
# ────────────────────────────────────────────────────────────
def _tw(d, t, f):
    bb = d.textbbox((0,0), t, font=f); return bb[2] - bb[0]

def _th(d, t, f):
    bb = d.textbbox((0,0), t, font=f); return bb[3] - bb[1]

def ct(d, t, f, cx, y, c=TITLE_C):
    d.text((cx - _tw(d,t,f)//2, y), t, font=f, fill=c)

def rr(d, box, r, fill, out=None, lw=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=out, width=lw)

def arr(d, cx, y0, y1, c=ARROW_C, sz=6):
    if y1 <= y0 + sz:
        return
    d.line([(cx, y0), (cx, y1-sz)], fill=c, width=2)
    d.polygon([(cx-sz, y1-sz),(cx+sz, y1-sz),(cx, y1)], fill=c)


def via_box(draw, name_en: str, cx: int, cy: int, col_w: int):
    w = min(col_w - 10, 175)
    h = 40
    # Auto-size font to fit box width
    selected_f = jp(14)
    for sz in (17, 14, 12, 10):
        f = jp(sz)
        if _tw(draw, name_en, f) <= w - 8:
            selected_f = f
            break
    # Truncate if still too wide
    if _tw(draw, name_en, selected_f) > w - 8:
        while len(name_en) > 1 and _tw(draw, name_en.rstrip() + "…", selected_f) > w - 8:
            name_en = name_en[:-1]
        name_en = name_en.rstrip() + "…"
    rr(draw, [cx-w//2, cy-h//2, cx+w//2, cy+h//2], 16, fill=STN_BG, out=STN_OUT, lw=1)
    ct(draw, name_en, selected_f, cx,
       cy - h//2 + max(2, (h - _th(draw, name_en, selected_f)) // 2))


# ────────────────────────────────────────────────────────────
# Column layout constants (sync with draw_col)
# ────────────────────────────────────────────────────────────
_SP_HDR_H   = 52   # icon + label block height
_SP_ARR     = 30   # arrow from icon to first via
_SP_VIA_H   = 40   # via box height
_SP_VIA_ARR = 24   # arrow between via boxes
_MAX_VIA    = 5    # max via stops to display (NAVITIME can return many)
_MIN_COL_H  = 190  # minimum column content height


def col_h_px(r: RouteInfo) -> int:
    via = r.via_stops[:_MAX_VIA]
    h   = _SP_HDR_H + _SP_ARR
    h  += len(via) * (_SP_VIA_H + _SP_VIA_ARR)
    return max(h, _MIN_COL_H)


def draw_col(img, draw, route: RouteInfo, cx, y0, col_w,
             target_bottom: int = None) -> int:
    y = y0

    ICON_SZ = 30
    GAP_IT  = 5
    blk_w   = ICON_SZ + GAP_IT + 110
    blk_lx  = cx - blk_w // 2
    icon_lx = blk_lx
    text_lx = icon_lx + ICON_SZ + GAP_IT
    icon_cy = y + _SP_HDR_H // 2

    paste_em(img, route.icon, icon_lx + ICON_SZ // 2, icon_cy, ICON_SZ)

    # Label
    lbl = route.label if len(route.label) <= 13 else route.label[:12] + "…"
    if route.is_recommended:
        lbl = "★ " + lbl
    f_lbl = jp(19, True)
    lbl_y = y + 4
    draw.text((text_lx, lbl_y), lbl, font=f_lbl,
              fill=REC_C if route.is_recommended else (30, 30, 42))

    # Duration + fare
    dm  = route.duration_min
    dur = f"{dm//60}H{dm%60}min" if dm >= 60 else f"{dm}min"
    fare_txt = f"¥{route.fare_yen:,}" if route.fare_yen else "—"
    f_dur  = jp(17, True)
    f_fare = jp(15, False)
    row2_y = lbl_y + 26
    draw.text((text_lx, row2_y), dur, font=f_dur, fill=(32, 48, 162))
    dur_w = _tw(draw, dur, f_dur)
    draw.text((text_lx + dur_w + 3, row2_y + 1), fare_txt, font=f_fare, fill=(80, 80, 92))

    y += _SP_HDR_H

    # Via stops
    via = route.via_stops[:_MAX_VIA]

    if route.mode == "taxi":
        return y  # arrow drawn by panel

    if not via:
        end_y = max(y + _SP_ARR, target_bottom) if target_bottom else y + _SP_ARR
        arr(draw, cx, y, end_y, c=ARROW_C)
        y = end_y
    else:
        arr(draw, cx, y, y + _SP_ARR, c=ARROW_C)
        y += _SP_ARR
        for i, stop in enumerate(via):
            via_box(draw, stop, cx, y + _SP_VIA_H // 2, col_w)
            y += _SP_VIA_H
            if i < len(via) - 1:
                arr(draw, cx, y, y + _SP_VIA_ARR, c=ARROW_C)
                y += _SP_VIA_ARR
            else:
                end_y = max(y + _SP_VIA_ARR, target_bottom) if target_bottom else y + _SP_VIA_ARR
                arr(draw, cx, y, end_y, c=ARROW_C)
                y = end_y

    return y


# ────────────────────────────────────────────────────────────
# Airport panel
# ────────────────────────────────────────────────────────────
def draw_airport_panel(img, draw, ak: str, d: dict,
                        px, py, panel_w) -> int:
    HDR_H      = 52
    PAD_IN     = 16
    SEP_PAD    = 10
    NEAR_H_ACT = 46
    WALK_H     = 46
    HOUSE_H    = 50
    PAD_BOT    = 12

    routes  = d["routes"]
    near_jp = d.get("nearest_jp", "最寄り駅")
    near_en = d.get("nearest_en", "Nearest Sta.")
    walk    = d.get("walk_min", 0)
    n       = len(routes)

    hdr_color = HDR_NARITA if ak == "narita" else HDR_HANEDA
    col_w     = (panel_w - PAD_IN * 2) // n
    max_col_h = max(max(col_h_px(r) for r in routes), _MIN_COL_H)
    panel_h   = (HDR_H
                 + max_col_h + 8
                 + SEP_PAD * 2 + 2
                 + NEAR_H_ACT
                 + WALK_H
                 + HOUSE_H
                 + PAD_BOT)

    rr(draw, [px, py, px+panel_w, py+panel_h], 18,
       fill=WHITE, out=PANEL_OUT, lw=2)

    # Header
    rr(draw, [px+4, py+4, px+panel_w-4, py+HDR_H-2], 14, fill=hdr_color)
    ap_txt = ("Narita International Airport  (Terminal 2)"
              if ak == "narita" else
              "Haneda Airport  (International Terminal 3)")
    f_hdr = jp(25, True)
    tw_ap = _tw(draw, ap_txt, f_hdr)
    th_ap = _th(draw, ap_txt, f_hdr)
    ICON_W = 22; GAP_I = 7
    total_hdr_w = ICON_W + GAP_I + tw_ap
    hdr_cx      = px + panel_w // 2
    icon_left   = hdr_cx - total_hdr_w // 2
    text_left   = icon_left + ICON_W + GAP_I
    paste_em(img, "✈", icon_left + ICON_W//2, py + HDR_H//2, ICON_W)
    draw.text((text_left, py + (HDR_H - th_ap)//2), ap_txt, font=f_hdr, fill=WHITE)

    col_xs = [px + PAD_IN + col_w * k + col_w // 2 for k in range(n)]
    taxi_idx = next((i for i, r in enumerate(routes) if r.mode == "taxi"), None)
    taxi_cx  = col_xs[taxi_idx] if taxi_idx is not None else None

    col_start_y     = py + HDR_H + 8
    target_bottom_y = col_start_y + max_col_h
    taxi_content_y  = None

    for r, cx in zip(routes, col_xs):
        ret_y = draw_col(img, draw, r, cx, col_start_y, col_w,
                         target_bottom=target_bottom_y)
        if r.mode == "taxi":
            taxi_content_y = ret_y

    sep_y = target_bottom_y + SEP_PAD
    sep_end_x = (taxi_cx - col_w // 2 - 4) if taxi_cx is not None else (px + panel_w - PAD_IN)
    draw.line([(px + PAD_IN, sep_y), (sep_end_x, sep_y)], fill=SEP_C, width=2)
    cur_y = sep_y + SEP_PAD

    # Station box
    if taxi_cx is not None:
        stn_right  = taxi_cx - col_w // 2 - 8
        stn_w      = stn_right - (px + PAD_IN * 2)
        stn_cx_box = px + PAD_IN * 2 + stn_w // 2
    else:
        stn_w      = panel_w - PAD_IN * 4
        stn_cx_box = px + panel_w // 2

    box_y1 = cur_y
    box_y2 = cur_y + NEAR_H_ACT
    rr(draw, [stn_cx_box - stn_w // 2, box_y1,
              stn_cx_box + stn_w // 2, box_y2],
       18, fill=NEAR_BG, out=NEAR_OUT, lw=2)

    f_en  = jp(24, True);  f_sep = jp(22, False);  f_ja = jp(22, False)
    en_str  = near_en + " Sta."
    sep_str = "  /  "
    ja_str  = near_jp + "駅"
    w_en  = _tw(draw, en_str,  f_en)
    w_sep = _tw(draw, sep_str, f_sep)
    w_ja  = _tw(draw, ja_str,  f_ja)
    total_w = w_en + w_sep + w_ja
    x_start = stn_cx_box - total_w // 2
    text_y  = box_y1 + (NEAR_H_ACT - _th(draw, en_str, f_en)) // 2
    draw.text((x_start,                text_y),     en_str,  font=f_en,  fill=(16, 36, 112))
    draw.text((x_start + w_en,         text_y + 1), sep_str, font=f_sep, fill=(130,130,150))
    draw.text((x_start + w_en + w_sep, text_y + 1), ja_str,  font=f_ja,  fill=(72, 72, 92))

    cur_y = box_y2

    # Walk arrow
    wy0    = cur_y + 8
    arr_cx = stn_cx_box - 34
    arr(draw, arr_cx, wy0, wy0 + 30, c=GARROW_C)
    f_walk  = jp(22, True)
    wlabel  = f"{walk} min walk" if walk > 0 else "a few min walk"
    icon_x  = arr_cx + 30
    mid_y   = wy0 + 15
    walk_em = emoji_img("🚶", 20)
    wem_w, wem_h = walk_em.size
    img.paste(walk_em, (icon_x, mid_y - wem_h // 2), walk_em)
    label_x = icon_x + wem_w + 6
    draw.text((label_x, mid_y - _th(draw, wlabel, f_walk) // 2),
              wlabel, font=f_walk, fill=WALK_C)
    cur_y = wy0 + WALK_H - 8

    # House bar
    house_y = cur_y
    rr(draw, [px + PAD_IN, house_y, px + panel_w - PAD_IN, house_y + HOUSE_H],
       12, fill=HOUSE_BG, out=HOUSE_OUT, lw=2)
    house_cx = px + panel_w // 2
    f_house  = jp(27, True)
    h_label  = "House  /  お部屋"
    icon_size = 28; gap = 8
    tw_h = _tw(draw, h_label, f_house)
    th_h = _th(draw, h_label, f_house)
    total_house_w = icon_size + gap + tw_h
    hx = house_cx - total_house_w // 2
    hy_mid = house_y + HOUSE_H // 2
    paste_em(img, "🏠", hx + icon_size // 2, hy_mid, icon_size)
    draw.text((hx + icon_size + gap, hy_mid - th_h // 2),
              h_label, font=f_house, fill=(90, 56, 14))

    # Taxi arrow straight to house bar
    if taxi_cx is not None:
        arrow_start = taxi_content_y if taxi_content_y is not None else target_bottom_y
        arr(draw, taxi_cx, arrow_start, house_y, c=ARROW_C)

    return py + panel_h


# ────────────────────────────────────────────────────────────
# Image generator
# ────────────────────────────────────────────────────────────
def generate_image(
    property_name: str,
    data: dict,
    out_path: str = None,
) -> Optional[bytes]:
    """
    Generate airport access PNG.
    If out_path is given, save to file and return None.
    If out_path is None, return PNG bytes (for Streamlit).
    """
    PAD    = 10
    TITLE_H = 38
    GAP    = 8
    FOOT_H = 52

    HDR_H = 52; PAD_IN = 16; SEP_PAD = 10
    NEAR_H_ACT = 46; WALK_H = 46; HOUSE_H = 50; PAD_BOT = 12

    def panel_h_calc(routes, panel_w):
        n         = len(routes)
        max_col_h = max(col_h_px(r) for r in routes)
        return (HDR_H + max_col_h + 8
                + SEP_PAD * 2 + 2
                + NEAR_H_ACT + WALK_H + HOUSE_H + PAD_BOT)

    W_try   = 1100
    panel_w = W_try - PAD * 2
    nh = panel_h_calc(data["narita"]["routes"], panel_w)
    hh = panel_h_calc(data["haneda"]["routes"], panel_w)

    H_content = TITLE_H + PAD + nh + GAP + hh + GAP + FOOT_H + PAD
    SIDE      = max(W_try, H_content + 40)
    W = H = SIDE
    extra_top = max(20, (SIDE - H_content) // 2)

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Title
    f_tit = jp(31, True)
    title = "How to get from the Airport to the House"
    ty = extra_top + 8
    ct(draw, title, f_tit, W//2, ty, c=TITLE_C)
    tw = _tw(draw, title, f_tit)
    paste_em(img, "✈", W//2 - tw//2 - 28, ty + 10, 22)
    paste_em(img, "✈", W//2 + tw//2 + 28, ty + 10, 22)

    cur_y = extra_top + TITLE_H + PAD
    cur_y = draw_airport_panel(img, draw, "narita", data["narita"],
                               PAD, cur_y, panel_w) + GAP
    cur_y = draw_airport_panel(img, draw, "haneda", data["haneda"],
                               PAD, cur_y, panel_w) + GAP

    # Footer
    f_note = jp(15, False); f_prop = jp(14, True)
    note = ("Fares and travel times are estimates only. "
            "Actual costs and durations may vary depending on timing, "
            "traffic, and other conditions.")
    note_w = _tw(draw, note, f_note)
    note_h = _th(draw, note, f_note)
    note_y = cur_y + 6
    draw.text(((W - note_w) // 2, note_y), note, font=f_note, fill=(100,100,108))
    prop_y = note_y + note_h + 4
    pw_ = _tw(draw, property_name, f_prop)
    draw.text(((W - pw_) // 2, prop_y), property_name, font=f_prop, fill=(70,70,78))

    if out_path:
        img.save(out_path, "PNG", optimize=True)
        print(f"✅ Saved: {out_path}  ({W}×{H}px)")
        return None
    else:
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue()


# ────────────────────────────────────────────────────────────
# CLI entry point
# ────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="Airport Access Image Generator v10.0")
    p.add_argument("--address", "-a", help="Property address (Japanese OK)")
    p.add_argument("--name",    "-n", default="My Property", help="Property name")
    p.add_argument("--output",  "-o", default="airport_access.png")
    p.add_argument("--demo",    action="store_true", help="Demo mode (no internet)")
    p.add_argument("--api-key", "-k", default="",
                   help="NAVITIME RapidAPI key (or set NAVITIME_API_KEY env var)")
    args = p.parse_args()

    api_key = args.api_key or os.environ.get("NAVITIME_API_KEY", "")

    if args.demo or not args.address:
        print("📍 Demo mode (mock data)")
        generate_image(args.name, build_mock(), args.output)
        return

    print(f"📍 Address : {args.address}")
    print("🌍 Geocoding... (Nominatim)")
    coord = geocode(args.address)
    if not coord:
        print("⚠  Could not geocode address. Using demo data.")
        generate_image(args.name, build_mock(), args.output)
        return

    plat, plng = coord
    print(f"   → ({plat:.5f}, {plng:.5f})")

    print("🚉 Finding nearest station...")
    stns    = nearest_stations(plat, plng, radius=2000)
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
        print(f"   → near_en='{near_en}'  near_jp='{near_jp}'")
        wr = osrm_walk(plat, plng, s["lat"], s["lon"])
        walk_min = wr[0] if wr else 10
        print(f"   → Walk: {walk_min} min")
    else:
        print("  ⚠ 駅名取得失敗 — デフォルト表示を使用")
        near_jp = "最寄り駅"; near_en = "Nearest Sta."

    if api_key:
        print(f"🔑 NAVITIME API key detected — fetching live routes...")
    else:
        print("ℹ  No NAVITIME API key — using fallback database.")

    print("🗺  Computing routes...")
    route_data = gather_routes(plat, plng, api_key=api_key)
    for d in route_data.values():
        d["walk_min"]   = walk_min
        d["nearest_jp"] = near_jp
        d["nearest_en"] = near_en

    print("🎨 Generating image...")
    generate_image(args.name, route_data, args.output)


if __name__ == "__main__":
    main()
