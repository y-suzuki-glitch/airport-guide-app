#!/usr/bin/env python3
"""
Airport Access Image Generator v10.1
======================================
v10.1 fixes for Streamlit Cloud deployment:
  - Auto-detect Japanese fonts via fc-list (works on any Ubuntu server)
  - All icons drawn with PIL (no emoji font dependency)
  - ¥ sign replaced with ASCII-safe alternative when font lacks glyph
  - packages.txt: add 'fonts-noto-cjk' for Streamlit Cloud
"""

import os, sys, math, time, argparse, re, io, requests, platform, subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

_IS_MACOS = (platform.system() == "Darwin")
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ────────────────────────────────────────────────────────────
# Font detection  (robust: works on Ubuntu cloud + local)
# ────────────────────────────────────────────────────────────
def _find_cjk_fonts() -> Tuple[str, str]:
    """Return (bold_path, medium_path) for CJK fonts. Never returns None."""

    # ① Explicit known paths (in priority order)
    candidates_bold = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        # Windows
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        # macOS
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    candidates_medium = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Medium.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    ]

    def first_existing(lst):
        for p in lst:
            if p and os.path.exists(p):
                return p
        return None

    bold_path   = first_existing(candidates_bold)
    medium_path = first_existing(candidates_medium)

    # ② fc-list fallback (Ubuntu cloud with fonts installed)
    if not bold_path or not medium_path:
        try:
            out = subprocess.check_output(
                ["fc-list", ":lang=ja", "--format=%{file}\n"],
                stderr=subprocess.DEVNULL, timeout=5,
            ).decode("utf-8", errors="ignore")
            paths = [p.strip() for p in out.split("\n") if p.strip()]
            if not bold_path:
                for p in paths:
                    if ("Bold" in p or "bold" in p) and os.path.exists(p):
                        bold_path = p
                        break
            if not medium_path:
                for p in paths:
                    if os.path.exists(p):
                        medium_path = p
                        break
        except Exception:
            pass

    # ③ Last resort: search common directories
    if not bold_path or not medium_path:
        for root in ["/usr/share/fonts", "/usr/local/share/fonts",
                     os.path.expanduser("~/.fonts")]:
            if not os.path.isdir(root):
                continue
            for dirpath, _, files in os.walk(root):
                for fn in files:
                    if fn.endswith((".ttc", ".ttf", ".otf")):
                        full = os.path.join(dirpath, fn)
                        fn_l = fn.lower()
                        if not bold_path and ("bold" in fn_l or "Bold" in fn):
                            try:
                                ImageFont.truetype(full, 12)
                                bold_path = full
                            except Exception:
                                pass
                        elif not medium_path:
                            try:
                                ImageFont.truetype(full, 12)
                                medium_path = full
                            except Exception:
                                pass

    if not bold_path:
        bold_path = medium_path  # use medium for both if no bold
    if not medium_path:
        medium_path = bold_path

    return bold_path or "", medium_path or ""


_FONT_BOLD, _FONT_MEDIUM = _find_cjk_fonts()
print(f"[font] bold={_FONT_BOLD!r}  medium={_FONT_MEDIUM!r}", file=sys.stderr)

_jp_cache: Dict[Tuple, ImageFont.FreeTypeFont] = {}

def jp(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    k = (size, bold)
    if k not in _jp_cache:
        path = _FONT_BOLD if bold else (_FONT_MEDIUM or _FONT_BOLD)
        if path:
            try:
                _jp_cache[k] = ImageFont.truetype(path, size)
            except Exception:
                _jp_cache[k] = ImageFont.load_default()
        else:
            _jp_cache[k] = ImageFont.load_default()
    return _jp_cache[k]


# ────────────────────────────────────────────────────────────
# Custom colored badge icons for named train lines
# ────────────────────────────────────────────────────────────
_BADGES: Dict[str, Tuple] = {
    "SKYLINER":  ((210,  55,  25), "SKYLINE"),
    "NEX":       (( 25,  80, 175), "N'EX"),
    "KEISEI":    ((195,  35, 115), "KEISEI"),
    "KEIKYU":    ((195,  15,  35), "KEIKYU"),
    "MONORAIL":  ((  0, 110, 175), "MONO"),
}


def _pil_badge(text: str, color: Tuple, size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    r   = size // 5
    d.rounded_rectangle([1, 3, size-1, size-3], radius=r, fill=color)
    font_sz = max(7, size // 4)
    f  = jp(font_sz, True)
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((size - tw) // 2, (size - th) // 2 + 1), text, font=f, fill=(255, 255, 255))
    return img


# ────────────────────────────────────────────────────────────
# ── Twemoji PNGs embedded as base64 (no emoji font needed) ─────
_TWEMOJI_B64: Dict[str, str] = {
    '✈': "iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAMAAABiM0N1AAAAwFBMVEVHcExVrO5VrO5VrO5VrO5VrO5VrO5VrO7M1t1VrO5VrO5VrO7M1t1mdX9mdX9VrO7M1t3M1t1VrO5Vq+vM1t3M1t1VrO5mdX/M1t3M1t3M1t1mdX9VrO5mdX9mdX+kyOPM1t1mdX+kyOPM1t2vusLM1t1kfY+RweakyONVrO5mdX/M1t1se4XF095cr+22zuCMmaKmsrpksey2wcijyOOEvehrtOuCj5m/ytGTn6hekbdig5uYxOTG0Nd6uelgiqlNiWZyAAAAKXRSTlMAEM+AIGCfv59w7zDvMO9AMGCvjxDPUCBwj79g30AQ7yCfv4C/UHC/j7N3QhkAAAKlSURBVHhezdbZdpswEIDhMWBjwA4J3h07W5O2Et73rH3/t2pAEUI5Gg+Um/639vmQZMAD/0fdp9G4F8fjH9WUYS+WVZDumnGu8T87w1asRQHt6cDoiOUUh645v2hjzozz2eoknB7pJBKyHp4024ozohwhmfe1XR8TKV3TiHKENMDOZ/0prRLoiXJEU5MjpVkCdSlH1MZ/ryPnubMOI5995btpUecl6TXtJ6iGsd46hYbCqbMiuUm/4m9t+SzbmcMKt4+NNSHNq+q07gTUr+SIExK5xZwD4jRBVusUcuaoo3I6VkVHVes3JhUdleNFiLMhnWILWywJx1xgW9UdtUnaGRKI2qR/1vkNxQs7E8Z2ZmfvQqmCW8RhJaEm5gioojM/sJLQCHNKQleYI6Dqjqiis9ywryo6C1YSuqQcJmYV0mlRDlOzSmlnl3eYnDDKO7dM65WWukanGRogMatgTs/oAPgGiE9LOiMAaJigdjnnSo0bOnQNWJlz+u5ATYd0py42PnHdhm2HYSAf+PcVP+UcUZSH/miOg/zDb2d8lXcMk8uLdIxDzVINh+9ybLk0X/YlcTBoL5xnzvlWOSorDyUOsrWFGBVWn87a5ECHqToA2EfsLXOejQ4ETGWDXkM5G+lkB93rgp6PQPox7ShHXhZ5aQeWXBDpQB+DRLY8odQ54g7UzkMQJBPpXF/PCExFGCTz/A/NWR4c8/coCJyH+Dlz5nvGQvPXSAjG68x5WzAMAouEHuV9uNvo9wl2ByPOzUX6XMzfBINCIQXd84vH8cMHy2qAOf88NOD3NwCOz8jDjM5DN4PU82iorkFobgZNEMhBIexFAUhWIQhsEvKKQWBRUM1PnQig4OaIRfeBil56A7nNzK9BH/ACOwAoKtWheuB4nlMK+AtMy4GynxGGywAAAABJRU5ErkJggg==",
    '🏠': "iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAMAAABiM0N1AAAAS1BMVEVHcEygBB6gBB6gBB5ckTtmdX9ckTtmdX9mdX+gBB5ckTtra3agBB5mdX//6LafoJRckTv/zE2pp5egBB58S1tVrO6zr5upm2nBaU/BI5AjAAAADXRSTlMAgCCvv48Qn4C/IK9gbf8AgQAAAOpJREFUeF7t09kKwjAQheFEmy7qpIvr+z+pFSqHmiYMM7lQzH8b+GACx+So5IhcDqehuSaLA0nnQNI5kNRO30NSOd5D0jmQdI5A2u27udPakUj2/KpbORIJEByJBAiORAIERyQBgiORAF3gBBBTsgyHJVmGw5Js2uEv2KYd/oItw2FJR4bDkRqWA0nrQNI6kIQOS3JRZ0ot2AVQ1PHpBQdQ1PHRl34Taokmv9mN6A7g4+jWhAG4Lr2pcYw8+AApUIEiAUK/CBWoQI8l9URCqEAFQv8I1dUgrqoNgiORDBpUHXJB2U/Tf/Z39gTttax73q0rOQAAAABJRU5ErkJggg==",
    '🚶': "iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAMAAABiM0N1AAAAvVBMVEVHcEwpQFL7zlf/11r+01f+qjf9qUpCicH+vUtAhr4qZ5f9xVUvR1r+yU4pLzMpLzP/rDP801kpLzMuapoqZ5f6dD7/rDP+2VspLzNCicEqZ5f6dD76eT//rDP/rDNCicFCicH7y1P3dED/3F0pLzNCicEqZ5f6dD5CicH6dD4yZ5H6dD5CicEpSWH5ylX6dD4pLzP6ylX/3F0qZ5f/v0f7ikT8m0n/rDP7gEFCicEpMzo2d6orSF7+wlM2XHp5K8iqAAAAL3RSTlMAJYP7QL8o7hAtQBQQa369pKLP1r9AgLnsSHjvq+tgj2Dvz9dMup+Az3D3UHDPz53UV2sAAAIsSURBVHhevdXbcqJAEAbgRpBgFlAhUbOeolE3yR5mhrOa5P0faxkccEj2hu6q/W+8sOqrv6eHGvhvcVaT/mhik53VMq+ytEhtRvk1KwI0ybUsHTzUz/V4eGjUgkZ4yEp0qE+AoihXFhkyo4Q+GjiRTELfPzxFVQR1/TCOVGjbB/hmKiiRy6fEU5C5AWK8upNNlRzLskXK2MIBcn4ymTm5kz1nF4naactUFjTnnjWhDbe4Qi8kiF2zJU6WZYWSKNALY+9RJN4r6J4A/ZBQmQrq06CogbIeGRIXaGNTocsZpWJMgFIJZQoSDv6LbUMW/h5lEioqqBDCw0OJOiIZIfB7qyZL6ZBjqkJEyJFPm1lcoTHhZTNTdoWmuD7K0aANei5RMA3CXaTpZ4dtUGuzS+dpoTtzT4g/uPfa2mrO1oaxnA0xWQ+MOD4fVdYA0OthVj8FOMRxXEM3gIs1tWAQa9BxAOjcSaiZ7QHt3MYtaE0ppM/2TCqkV3IphXToEecYytEuAO64D7UT7hsJdQNea+j24dhImGOqnQPAcyPtCZABMLhppF9oKASQEuGYQiVBW9qjrxF8ktZ4SEnYe/m9hqiSgkL4KvkuArqDL9KZB0bnj1+HQF3xD85nNAgeK+jE+ZAIwbp03spCLhWC8LV0gh2QoYDLPpj1/245Li/TqY/hn95kOG9BPu900Dt+yUn+GDpfOkGHwYZcy679x9DtNFdFBf6MB0O9kT/z/wn8BcdCxhbiMA66AAAAAElFTkSuQmCC",
    '🚌': "iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAMAAABiM0N1AAAAq1BMVEVHcEzM1t3M1t3M1t3M1t3M1t3M1t3M1t3M1t3M1t3M1t3M1t3M1t3M1t3M1t0pLzMpLzMvNDhJTE9YWVtVrO4/bpFXg6X/rDOTlZj0kAw2PEBydXiAgoWTlZemqKq1t7m8vsCPkZSipKZ2d3gvMDAAAAClpqgjJCQMDAyAgoWAgoUwNTmGlZ6ZqrWAgoWAgoW8vsC8vsC8vsCEhokAAAAAAAAAAAAAAAAAAAC1c97cAAAAOXRSTlMAIECAn7/P/48wEGDfr++//////////////////////////////////++f////IDDvIJ//v2DPIO97RqWiAAABc0lEQVR4AezTxQHDMAxAUYeZzd5/znLo6ErF6A3wb5/9IkIIIUEYxUmaeUrzgm2UVVxnz0rCOVPEGUxTsouyycDSS6loMwTJ3AFjXX8xjBMU6+9GrNCAFerBIc65mEOSe5L7EJ9D3BuFLiik1JeG4ItsQ0DfGRIoof5BgxgzhyxWyOGELKAzh4w5N0sWNhJDUQx8fWyYman/yi4OkxeEN4KAR/6ozKiabozomqpwuLsWmUgWdJNXMHctsowTFi0h7lqkGRc0UsJd2cewHXfEsfmc3rkoMvHl+e6C7+Gb7BN1UaQjC9yNAKn+XERdCRUVpRhjw8efx1tA3VCiafds/IuTNE1ivNlsv6kbSRZitg6ydAKpw9bG3DATyYvxDdXJHCZ4N0aeioxnt8hlpKyKKUwX1qKaF53doipl5RoK5717na5w3rvNeQMb4bx32/ORtsL54HbugU44n9x+2LOhv4Q/uX23jXHLfnTbBlFD9oe4/5g/tOYi7WbQdJMAAAAASUVORK5CYII=",
    '🚕': "iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAMAAABiM0N1AAAAq1BMVEVHcEwpLzP/zE3/zE0pLzMpLzMpLzP/zE3/zE3/zE3/zE3/zE3/zE3/zE0pLzP/zE3/zE3/zE30kAzM1t3M1t30kAzM1t3M1t30kAzM1t30kAzM1t3/zE3M1t3M1t3/zE3M1t30kAxVrO7/zE0pLzNcY2i4wchfVjpRTDjkuEqvkUNgruSVuLI2OTXqyGHVxHX0yleAtMa/wIlqsNqfuqjKwn+1vpOKtrzM1t0+VMsDAAAAIXRSTlMAYM8Qv88g3+9gMCBQv+9AgJ/vvzBQEM+v74Bgr48gcIAmSmOXAAABnklEQVR42u2V23KCMBBABVFASqXVXuxdgoCKWnvN/39Zs+K4yThlI+GhM+U8sePxiFkZOy0tLS0tLf+N8Q3no7F552nCBZNr49Aj33FvHBqVoReDhG+z33kIdDNByCrxfL3OwGME3kDrfjxG4uqEbDBfi2WMMEFcsizWMPl0JwJvgxk1BKm11i0FTPCJDQwdKGAkT+lCSOtlZSjW+W5dOOltXB3aiDEiQj4cUEyEvsQYEiFXON9U6EOMdnVnCJuPqdAWZvqo38jQO7m2LhhFVQjn4fG7n21WCzfqKsfistp4A3XfTZTOmBku/pAN8XHdZtjlDV1OjekAV9OGQndNhW6bCrnMnPLRaig0ZBKLLBFkC1WjDQhFOM7zZE8+lzXaEE+HK1mr5MBK9mhDfcryRCJnCG0oG1vAq7OU83QGV3gKtBF2ZC0Di+8AL2MIZfhKKBGkpZbCNUMIw4Yfo6rxPZJGG14gltZAyBYdWL/hVwuP//8d9Sidjr6hYqnLtU41kF4i0TvZQPrnaJ33axjo9Q6f1q9lIJYDkmNpGH+cH1WFLxnhHOQhAAAAAElFTkSuQmCC",
    '🚆': "iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAMAAABiM0N1AAAAwFBMVEVHcExYWVunqaynqaylp6qnqaynqayco6qnqaynqaycnaCnqaynqaynqaynqaynqaxYWVuAgoVtb3FcXV9kZWd3eHqHiYyTlZh8foGdn6KPkJPYrW38rjy7qpLpq1GMjpHKwbMiZpmnqazm5+jDxMbQ0tSHmadcg6HX2drg4eJ4kaV5u+0zbpthse6rrbBBdp62uLqLwuzU4On5u2BUf6Cfpausz+uvsbSZyOvxzpnr3cjL3OnC2OpVrO7/rDOipKcM8leCAAAAEHRSTlMAr4Aga+8wEN+/UECPz5+vV9SdoQAAA1lJREFUeF6U1WmK4zAQBeDQcSdtkuk+Q5V279l7nbn/rQZVRkaEKUl+P0LA8PmVXKAVm121r2uMUtf7ardalm31FgnDLeLeqm0xs34l4CaVdWKOs0rexdd1WZs9tZCREWly8NS+oNXmxTsx80h56WWTdZ59HSUSUb7Uc0baegetSMail9LT0cdSIhNFny/l7LwziWwmL+1yhZyI8/0dfqO4TKX1XOj43rY//+KB8L9t349zJX6dqvmESIihKPMpVSxEGy1KIEEbzkI1TZaFwmw1C9FOl0G030lIEdTzUE+QykKWoGvPQf2VIJuFxD3Hw/+hw1HcUwjRKvWPUE9LVABdPBTl63poA9Qerl8eiKALC2mCsgmQZqEGcVgANSxklkGGhbplo3UsBHoJpIFztmAQXZnjEE0C6hBtGWQRO+BHgwZlGSSxAR7qYMSpDJpwBP6wzwC67JAcaoAzC2mAEVUJpHAE0CxET4tmu9E7eYge27xjqVACQgPQlFyQDYDBFIRngEv+yr4AnDEFkWQGl3bcYMjB5HWEJnvekwaDyevoCX30+LDen+5hqUeNPk8stMEQGYyP02/K6eNzdkI2Kza/AvRHEkNKyIko+bfysultEIbBMB3txigTJl98rO0m99RL1esuy///V1PsCkRLcPYcU+mp/RInMHo+sjhbHLldzj+/D/ycLzcc2Ypvfsz1+/AoOnxfkRDe/TjuiePnTHX4PCIjRE0UiHPXiS0ntkwU2TolJlJmAjUmUWcSbwUmUKR8Q6AE70WZLYpssxQ2FgXsJsVTAggmC1BmCWFbANNjlN4A2ISwK/QGQDuM4DSA8VhJnj0imUC1uECrgDyIe6kxFgWU8zjDu6AhEe0kcWgbIMjV3mW+JQvTiEP7SmlqANAaluB13fOmFE5Iql91BhYwHf9KJ6TQWEt/3DVNpx6q0iqs0mK72lyOAapENYRV5i7TRlleo5IMBvK1a81xmHH4YTi+2OLD6kMFKBAq9NHhzXc8R2kinsddHmushcAXrvIFY97vscOak2wEzLgFsFy+0RwErCSyEHCLt1vNSU8FySVx3vVSY92sILGkjpt7vjp6HkiRcbD7pwulmpLGRKa8q/lphjjAf0UwkGk/b8xzggMmMfBz8WNzf8MyuZqhlVX/AAAAAElFTkSuQmCC",
}

_TWEMOJI_CACHE: Dict[str, Image.Image] = {}


def _load_twemoji(ch: str, size: int) -> Optional[Image.Image]:
    """Load a Twemoji PNG from embedded base64, scaled to size."""
    if ch not in _TWEMOJI_B64:
        return None
    import base64 as _b64
    key = (ch, size)
    if key not in _TWEMOJI_CACHE:
        raw = _b64.b64decode(_TWEMOJI_B64[ch])
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        _TWEMOJI_CACHE[key] = img.resize((size, size), Image.LANCZOS)
    return _TWEMOJI_CACHE[key]


def emoji_img(ch: str, size: int = 28) -> Image.Image:
    """Return a PIL image for the given icon character/code.
    Priority: custom badge → embedded Twemoji PNG → PIL fallback
    """
    # ① Colored badge for named train lines
    if ch in _BADGES:
        color, txt = _BADGES[ch]
        return _pil_badge(txt, color, size)

    # ② Embedded Twemoji PNG (airplane, house, bus, taxi, walk, train)
    twemoji_img = _load_twemoji(ch, size)
    if twemoji_img is not None:
        return twemoji_img

    # ③ PIL fallback
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.ellipse([1, 1, size-2, size-2], fill=(100, 100, 200))
    letter = ch[0] if ch else "?"
    f  = jp(size // 2)
    bb = d.textbbox((0, 0), letter, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((size - tw) // 2, (size - th) // 2), letter, font=f, fill=(255, 255, 255))
    return img


def paste_em(img: Image.Image, ch: str, cx: int, cy: int, size: int = 28):
    em  = emoji_img(ch, size)
    w, h = em.size
    img.paste(em, (cx - w // 2, cy - h // 2), em)



UA = "AirportAccessImageTool/10.1"


def navitime_transit(
    start_lat: float, start_lng: float,
    goal_lat:  float, goal_lng:  float,
    api_key:   str,
    departure_time: str = None,
    limit: int = 5,
) -> List[dict]:
    if not api_key:
        return []
    if not departure_time:
        departure_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    url     = "https://navitime-route-totalnavi.p.rapidapi.com/route_transit"
    headers = {
        "X-RapidAPI-Key":  api_key,
        "X-RapidAPI-Host": "navitime-route-totalnavi.p.rapidapi.com",
    }
    params  = {
        "start":      f"{start_lat},{start_lng}",
        "goal":       f"{goal_lat},{goal_lng}",
        "start_time": departure_time,
        "limit":      limit,
        "datum":      "wgs84",
        "coord_unit": "degree",
        "lang":       "en",
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        print(f"  [NAVITIME] API error: {e}", file=sys.stderr)
        return []


def parse_navitime_route(item: dict) -> Optional[dict]:
    try:
        summary   = item.get("summary", {})
        total_min = int(summary.get("move_time", 0)) // 60
        fare_info = summary.get("fare", {})
        fare      = int(fare_info.get("iccard") or fare_info.get("total_fare") or 0)

        sections      = item.get("sections", [])
        transit_legs  = [s for s in sections if s.get("type") in ("train", "bus")]

        if not transit_legs:
            return None

        first_leg = transit_legs[0]
        last_leg  = transit_legs[-1]
        tp        = first_leg.get("transport", {})
        mode_type = first_leg.get("type", "train")
        line_name = tp.get("line_name", tp.get("name", "Transit"))

        icon  = _choose_icon(line_name)
        label = _shorten_label(line_name)

        via = []
        for i, leg in enumerate(transit_legs):
            dep_name = leg.get("from_node", {}).get("name", "")
            arr_name = leg.get("to_node",   {}).get("name", "")
            if i == 0:
                if len(transit_legs) > 1:
                    via.append(_clean_station(arr_name))
            else:
                via.append(_clean_station(dep_name))
                if i < len(transit_legs) - 1:
                    via.append(_clean_station(arr_name))

        seen = set()
        clean_via = []
        for v in via:
            if v and v not in seen:
                seen.add(v)
                clean_via.append(v)

        hub_node = last_leg.get("to_node", {})
        hub_name = _clean_station(hub_node.get("name", ""))
        hub_lat  = hub_node.get("coord", {}).get("lat", 0)
        hub_lng  = hub_node.get("coord", {}).get("lon", 0)

        return dict(
            label=label, icon=icon,
            mode="bus" if mode_type == "bus" else "train",
            duration=max(1, total_min), fare=fare,
            via=clean_via, hub=hub_name,
            hub_lat=hub_lat, hub_lng=hub_lng,
        )
    except Exception as e:
        print(f"  [parse_navitime] {e}", file=sys.stderr)
        return None


def _clean_station(name: str) -> str:
    for sfx in (" Sta.", " Station", " station", "駅", "站"):
        if name.endswith(sfx):
            name = name[:-len(sfx)].strip()
    return name.strip()


def _shorten_label(name: str) -> str:
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
    if "skyliner" in ln or "スカイライナー" in line_name: return "SKYLINER"
    if "narita express" in ln or "成田エクスプレス" in line_name or "n'ex" in ln: return "NEX"
    if "keisei" in ln or "京成" in line_name:   return "KEISEI"
    if "keikyu" in ln or "京急" in line_name:   return "KEIKYU"
    if "monorail" in ln or "モノレール" in line_name: return "MONORAIL"
    if "bus" in ln or "バス" in line_name:       return "🚌"
    return "🚆"


# ────────────────────────────────────────────────────────────
# Fallback route database
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
# Geocoding helpers
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
            print(f"  [Nominatim] {e}", file=sys.stderr)
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
    except Exception as e:
        print(f"  [Overpass] {e}", file=sys.stderr)

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
        print(f"  [Nominatim stn] {e}", file=sys.stderr)
    return []


def osrm_walk(flat, flng, tlat, tlng) -> Optional[Tuple[int, int]]:
    url = f"https://router.project-osrm.org/route/v1/walking/{flng},{flat};{tlng},{tlat}"
    try:
        d = requests.get(url, params={"overview": "false"}, timeout=10).json()
        if d.get("routes"):
            rt = d["routes"][0]
            return max(1, int(rt["duration"]) // 60), int(rt["distance"])
    except Exception:
        pass
    return None


def osrm_drive(flat, flng, tlat, tlng) -> Optional[Tuple[int, int]]:
    url = f"https://router.project-osrm.org/route/v1/driving/{flng},{flat};{tlng},{tlat}"
    try:
        d = requests.get(url, params={"overview": "false"}, timeout=10).json()
        if d.get("routes"):
            rt = d["routes"][0]
            return max(1, int(rt["duration"]) // 60), int(rt["distance"])
    except Exception:
        pass
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
    results = []
    for r in db:
        extra = hub_to_prop_min(r["hub_lat"], r["hub_lng"], plat, plng)
        results.append(RouteInfo(
            mode=r["mode"], icon=r["icon"], label=r["label"],
            duration_min=r["duration"] + extra,
            fare_yen=r["fare"], via_stops=r["via"][:],
        ))
    return results


def compute_routes_navitime(alat, alng, plat, plng, api_key, limit=5) -> List[RouteInfo]:
    raw = navitime_transit(alat, alng, plat, plng, api_key, limit=limit)
    routes = []
    for item in raw:
        parsed = parse_navitime_route(item)
        if parsed:
            routes.append(RouteInfo(
                mode=parsed["mode"], icon=parsed["icon"], label=parsed["label"],
                duration_min=parsed["duration"], fare_yen=parsed["fare"],
                via_stops=parsed["via"],
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
    data = {}
    for ak, (alat, alng) in AIRPORT_COORDS.items():
        routes: List[RouteInfo] = []
        if api_key:
            print(f"  [NAVITIME] Fetching routes from {ak}...", file=sys.stderr)
            routes = compute_routes_navitime(alat, alng, plat, plng, api_key)
            if not routes:
                print(f"  [NAVITIME] No routes for {ak}, using fallback DB", file=sys.stderr)
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
    selected_f = jp(14)
    for sz in (17, 14, 12, 10):
        f = jp(sz)
        if _tw(draw, name_en, f) <= w - 8:
            selected_f = f
            break
    if _tw(draw, name_en, selected_f) > w - 8:
        while len(name_en) > 1 and _tw(draw, name_en.rstrip() + "...", selected_f) > w - 8:
            name_en = name_en[:-1]
        name_en = name_en.rstrip() + "..."
    rr(draw, [cx-w//2, cy-h//2, cx+w//2, cy+h//2], 16, fill=STN_BG, out=STN_OUT, lw=1)
    ct(draw, name_en, selected_f, cx,
       cy - h//2 + max(2, (h - _th(draw, name_en, selected_f)) // 2))


# Spacing constants
_SP_HDR_H   = 52
_SP_ARR     = 30
_SP_VIA_H   = 40
_SP_VIA_ARR = 24
_MAX_VIA    = 5
_MIN_COL_H  = 190


def col_h_px(r: RouteInfo) -> int:
    via = r.via_stops[:_MAX_VIA]
    h   = _SP_HDR_H + _SP_ARR
    h  += len(via) * (_SP_VIA_H + _SP_VIA_ARR)
    return max(h, _MIN_COL_H)


def draw_col(img, draw, route: RouteInfo, cx, y0, col_w,
             target_bottom: int = None) -> int:
    y = y0
    ICON_SZ = 30; GAP_IT = 5
    blk_w   = ICON_SZ + GAP_IT + 110
    blk_lx  = cx - blk_w // 2
    icon_lx = blk_lx
    text_lx = icon_lx + ICON_SZ + GAP_IT
    icon_cy = y + _SP_HDR_H // 2

    paste_em(img, route.icon, icon_lx + ICON_SZ // 2, icon_cy, ICON_SZ)

    lbl = route.label if len(route.label) <= 13 else route.label[:12] + "..."
    if route.is_recommended:
        lbl = "* " + lbl
    f_lbl = jp(19, True)
    lbl_y = y + 4
    draw.text((text_lx, lbl_y), lbl, font=f_lbl,
              fill=REC_C if route.is_recommended else (30, 30, 42))

    dm  = route.duration_min
    dur = f"{dm//60}H{dm%60}min" if dm >= 60 else f"{dm}min"
    fare_txt = f"JPY {route.fare_yen:,}" if route.fare_yen else "-"
    f_dur  = jp(17, True); f_fare = jp(15, False)
    row2_y = lbl_y + 26
    draw.text((text_lx, row2_y), dur, font=f_dur, fill=(32, 48, 162))
    dur_w = _tw(draw, dur, f_dur)
    draw.text((text_lx + dur_w + 3, row2_y + 1), fare_txt, font=f_fare, fill=(80, 80, 92))

    y += _SP_HDR_H
    via = route.via_stops[:_MAX_VIA]

    if route.mode == "taxi":
        return y

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
    HDR_H      = 52; PAD_IN = 16; SEP_PAD = 10
    NEAR_H_ACT = 46; WALK_H = 46; HOUSE_H = 50; PAD_BOT = 12

    routes  = d["routes"]
    near_jp = d.get("nearest_jp", "Nearest")
    near_en = d.get("nearest_en", "Nearest Sta.")
    walk    = d.get("walk_min", 0)
    n       = len(routes)

    hdr_color = HDR_NARITA if ak == "narita" else HDR_HANEDA
    col_w     = (panel_w - PAD_IN * 2) // n
    max_col_h = max(max(col_h_px(r) for r in routes), _MIN_COL_H)
    panel_h   = (HDR_H + max_col_h + 8
                 + SEP_PAD * 2 + 2
                 + NEAR_H_ACT + WALK_H + HOUSE_H + PAD_BOT)

    rr(draw, [px, py, px+panel_w, py+panel_h], 18, fill=WHITE, out=PANEL_OUT, lw=2)

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

    sep_y     = target_bottom_y + SEP_PAD
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

    # Station label: "En Sta.  /  日本語駅"
    f_en  = jp(24, True); f_sep = jp(22, False); f_ja = jp(22, False)
    en_str  = near_en + " Sta."
    sep_str = "  /  "
    ja_str  = near_jp + "eki"   # fallback plain ASCII for now
    # Try to use Japanese text — works if font has CJK glyphs
    try:
        test_str = near_jp + "駅"
        f_test   = jp(22, False)
        _tw(draw, test_str, f_test)
        ja_str = test_str          # font supports CJK, use it
    except Exception:
        pass

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
    h_label  = "House  /  Room"
    icon_size = 28; gap = 8
    tw_h = _tw(draw, h_label, f_house)
    th_h = _th(draw, h_label, f_house)
    total_house_w = icon_size + gap + tw_h
    hx = house_cx - total_house_w // 2
    hy_mid = house_y + HOUSE_H // 2
    paste_em(img, "🏠", hx + icon_size // 2, hy_mid, icon_size)
    draw.text((hx + icon_size + gap, hy_mid - th_h // 2),
              h_label, font=f_house, fill=(90, 56, 14))

    # Taxi arrow
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
    PAD = 10; TITLE_H = 38; GAP = 8; FOOT_H = 52
    HDR_H = 52; PAD_IN = 16; SEP_PAD = 10
    NEAR_H_ACT = 46; WALK_H = 46; HOUSE_H = 50; PAD_BOT = 12

    def panel_h_calc(routes, panel_w):
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
    W = H     = SIDE
    extra_top = max(20, (SIDE - H_content) // 2)

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Title
    f_tit = jp(31, True)
    title = "How to get from the Airport to the House"
    ty    = extra_top + 8
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
        print(f"Saved: {out_path}  ({W}x{H}px)")
        return None
    else:
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue()


# ────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="Airport Access Image Generator v10.1")
    p.add_argument("--address", "-a", help="Property address")
    p.add_argument("--name",    "-n", default="My Property")
    p.add_argument("--output",  "-o", default="airport_access.png")
    p.add_argument("--demo",    action="store_true")
    p.add_argument("--api-key", "-k", default="")
    args = p.parse_args()

    api_key = args.api_key or os.environ.get("NAVITIME_API_KEY", "")

    if args.demo or not args.address:
        print("Demo mode (mock data)")
        generate_image(args.name, build_mock(), args.output)
        return

    print(f"Address: {args.address}")
    coord = geocode(args.address)
    if not coord:
        print("Could not geocode address. Using demo data.")
        generate_image(args.name, build_mock(), args.output)
        return

    plat, plng = coord
    print(f"  -> ({plat:.5f}, {plng:.5f})")

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
        wr = osrm_walk(plat, plng, s["lat"], s["lon"])
        walk_min = wr[0] if wr else 10
        print(f"  -> Station: {near_en} ({near_jp}), walk {walk_min}min")
    else:
        near_jp = "Nearest"; near_en = "Nearest Sta."

    route_data = gather_routes(plat, plng, api_key=api_key)
    for d in route_data.values():
        d["walk_min"]   = walk_min
        d["nearest_jp"] = near_jp
        d["nearest_en"] = near_en

    generate_image(args.name, route_data, args.output)


if __name__ == "__main__":
    main()
