import streamlit as st
import requests
from bs4 import BeautifulSoup
import json, re
from datetime import datetime
from urllib.parse import urlparse

# ── Konfiguráció ─────────────────────────────────────────────────────
BRAND_DB = {
    "aquashop": {
        "label": "Aquashop", "color": "#00d4ff", "chip": "chip-aq",
        "brands": [
            "Fairland","InverPro","Inver-X","WarriorX","Maytronics","Dolphin","Liberty",
            "Saci","Gemas","Microdos","BSV","Sopremapool","Flagpool","Hidroten",
            "Nature Works","Aquajet"
        ]
    },
    "aqualing": {
        "label": "Aqualing", "color": "#f5c842", "chip": "chip-al",
        "brands": [
            "Pontaqua","PoolTrend","Dekortrend","Bestway","Intex","Kokido",
            "Hydro Force","Gladiator","Wellis","VitalSpa","Azton","Wattsup"
        ]
    },
    "fluidra": {
        "label": "Fluidra-Kerex", "color": "#ff6b35", "chip": "chip-fl",
        "brands": [
            "Astralpool","Zodiac","Bayrol","GRE","Pahlen","Speck","Kripsol",
            "Fluidra","Kerex","Omniflex","Cepex","Emaux"
        ]
    }
}

TIER_CONFIG = {
    "PLATINUM": {"emoji":"🥇","color":"#00d4ff","label":"PLATINUM Partner"},
    "GOLD":     {"emoji":"🥈","color":"#f5c842","label":"GOLD Partner"},
    "SILVER":   {"emoji":"🥉","color":"#8fa8c8","label":"SILVER Partner"},
    "BASIC":    {"emoji":"⚠️","color":"#ff8c38","label":"BASIC Partner"},
    "INAKTÍV":  {"emoji":"🔴","color":"#ff4455","label":"INAKTÍV"},
}

DIM_DEFS = [
    ("exkluziv_termekek", "Aquashop exkluzív termékek", 40),
    ("kinalat_teljessege", "Kínálat teljessége", 25),
    ("tartalmi_minoseg", "Tartalmi minőség", 20),
    ("webshop_aktivitas", "Aktivitás & frissesség", 10),
    ("seo_elkotelezettsege", "SEO elkötelezettsége", 5),
]

MODELS = [
    "meta-llama/llama-4-maverick:free",
    "meta-llama/llama-4-scout:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "nvidia/llama-3.1-nemotron-nano-8b-v1:free",
]

# ── Stílus ────────────────────────────────────────────────────────────
st.set_page_config(page_title="Aquashop · Partner Scoring", page_icon="💧", layout="centered")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}
[data-testid="stAppViewContainer"]{background:#060912}
[data-testid="stHeader"]{background:#060912;border-bottom:1px solid #1c2a42}
[data-testid="stSidebar"]{background:#0d1424}
[data-testid="stSidebar"] *{color:#c8d8f0!important}
p,span,div,label{color:#c8d8f0}
input{background:#121d30!important;color:#e8f0fe!important;border-color:#243350!important}
.hero{background:linear-gradient(135deg,#0d1424,#121d30);border:1px solid #2a3f5a;border-radius:16px;padding:28px;margin:16px 0;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,#0055ff,#00d4ff,#00ffb3)}
.score-big{font-family:'Syne',sans-serif;font-weight:800;font-size:56px;line-height:1;background:linear-gradient(135deg,#00d4ff,#0055ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.tier-badge{font-family:'Syne',sans-serif;font-weight:800;font-size:26px}
.ratio-box{background:#0d1830;border:1px solid #2a3f5a;border-radius:12px;padding:20px;margin:12px 0}
.bar{height:32px;border-radius:10px;overflow:hidden;display:flex;margin:10px 0}
.seg{height:100%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:rgba(0,0,0,0.8)}
.s-aq{background:#00d4ff}.s-al{background:#f5c842}.s-fl{background:#ff6b35}
.chip{display:inline-block;padding:4px 11px;border-radius:20px;font-size:12px;font-weight:600;margin:3px}
.chip-aq{background:rgba(0,212,255,0.18);color:#5ee8ff;border:1px solid rgba(0,212,255,0.4)}
.chip-al{background:rgba(245,200,66,0.18);color:#fdd835;border:1px solid rgba(245,200,66,0.4)}
.chip-fl{background:rgba(255,107,53,0.18);color:#ff8c5a;border:1px solid rgba(255,107,53,0.4)}
.ev{background:#0d1830;border:1px solid #2a3f5a;border-radius:10px;padding:14px;margin:6px 0}
.ev-t{font-size:11px;color:#7a9fc0;margin-bottom:6px;font-weight:600;letter-spacing:1px}
.rec{background:#0d1830;border:1px solid #2a3f5a;border-radius:12px;padding:18px;margin:12px 0}
.slabel{font-family:'Syne',sans-serif;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#00d4ff;margin:20px 0 10px}
</style>""", unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state.history = []

# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 OpenRouter API kulcs")
    st.markdown("1. [openrouter.ai](https://openrouter.ai) → Sign up\n2. Settings → Secrets:\n```\nOPENROUTER_API_KEY = \"sk-or-...\"\n```")
    st.divider()
    for src, d in BRAND_DB.items():
        with st.expander(f"{d['label']} ({len(d['brands'])} márka)"):
            st.write(", ".join(d["brands"]))

# ── Webshop szöveg letöltése ──────────────────────────────────────────
def fetch_text(url, chars=3000):
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script","style","nav","footer","header"]):
            t.decompose()
        return re.sub(r'\s+', ' ', soup.get_text(" ", strip=True))[:chars]
    except:
        return ""

def fetch_sitemap(base):
    for path in ["/sitemap.xml", "/sitemap_index.xml"]:
        try:
            r = requests.get(base+path, headers={"User-Agent":"Mozilla/5.0"}, timeout=6)
            if r.status_code != 200:
                continue
            locs = re.findall(r'<loc>(.*?)</loc>', r.text)
            # Ha sitemap index, egy szinttel mélyebb
            subs = [l for l in locs if "sitemap" in l.lower()]
            if subs:
                all_locs = []
                for s in subs[:3]:
                    try:
                        sr = requests.get(s, headers={"User-Agent":"Mozilla/5.0"}, timeout=5)
                        all_locs += re.findall(r'<loc>(.*?)</loc>', sr.text)
                    except:
                        pass
                locs = all_locs or locs
            if locs:
                return " ".join(locs[:300])
        except:
            pass
    return ""

def collect_webshop_text(base):
    """Összegyűjti a webshop szövegét: főoldal + sitemap URL-ek + fix aloldalak."""
    parts = []
    # Főoldal
    t = fetch_text(base, 4000)
    if t:
        parts.append(t)
    # Sitemap URL-ek (a slug-ok tartalmazzák a márkaneveket)
    sm = fetch_sitemap(base)
    if sm:
        parts.append(sm)
    # Fix aloldalak
    for path in ["/termekek", "/kategoriak", "/medence", "/spa",
                 "/szivattyu", "/hoszivattyu", "/robot", "/pumpa"]:
        t = fetch_text(base+path, 1500)
        if t:
            parts.append(t)
    return "\n".join(parts)[:12000]

# ── OpenRouter hívás ──────────────────────────────────────────────────
def ai_score(api_key, prompt):
    import time
    last_err = ""
    for model in MODELS:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json",
                         "HTTP-Referer": "https://aquashop-scoring.streamlit.app"},
                json={"model": model,
                      "messages": [{"role":"user","content":prompt}],
                      "temperature": 0.1, "max_tokens": 1200},
                timeout=50
            )
            data = r.json()
            if "error" in data:
                msg = str(data["error"].get("message",""))
                last_err = f"{model}: {msg}"
                # Mindig folytatjuk a következő modellel
                continue
            text = data.get("choices",[{}])[0].get("message",{}).get("content","")
            if text and len(text) > 10:
                return text, model
            last_err = f"{model}: üres válasz"
        except Exception as e:
            last_err = f"{model}: {e}"
            time.sleep(2)
    raise Exception(f"Minden modell elérhetetlen: {last_err}")

# ── Header ────────────────────────────────────────────────────────────
st.markdown("""<div style='display:flex;align-items:center;gap:12px;padding:8px 0 24px'>
<div style='width:36px;height:36px;background:linear-gradient(135deg,#00d4ff,#0055ff);border-radius:8px;display:flex;align-items:center;justify-content:center;font-family:Syne;font-weight:800;font-size:16px;color:#fff'>A</div>
<span style='font-family:Syne;font-weight:700;font-size:18px;color:#dce8f5'>Aquashop <span style='color:#4a6080;font-weight:400'>/ Partner Scoring</span></span>
<div style='margin-left:auto;font-size:10px;letter-spacing:1px;color:#f5c842;background:rgba(245,200,66,0.08);border:1px solid rgba(245,200,66,0.2);border-radius:4px;padding:3px 8px'>OPENROUTER</div>
</div>""", unsafe_allow_html=True)

st.markdown("<h1 style='font-family:Syne;font-size:28px;font-weight:800;color:#dce8f5;margin-bottom:4px'>Partner webshop elemzés</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#7a9fc0;margin-bottom:20px'>Add meg a webshop domain nevét – az elemző letölti az oldalt és azonosítja a márkákat.</p>", unsafe_allow_html=True)

c1, c2 = st.columns([4,1])
with c1:
    domain_input = st.text_input("", placeholder="pl. medencefutar.hu", label_visibility="collapsed")
with c2:
    scan_btn = st.button("Elemzés →", type="primary", use_container_width=True)

# ── Elemzés ───────────────────────────────────────────────────────────
if scan_btn and domain_input.strip():
    try:
        api_key = st.secrets["OPENROUTER_API_KEY"]
    except:
        st.error("⚠️ OPENROUTER_API_KEY hiányzik a Secrets-ből!")
        st.stop()

    raw = domain_input.strip()
    if not raw.startswith("http"):
        raw = "https://" + raw
    domain = urlparse(raw).netloc.replace("www.", "") or raw
    base = f"https://{domain}"

    with st.status(f"Elemzés: {domain}", expanded=True) as status:

        # 1. Szöveg letöltése
        st.write("🌐 Webshop tartalom letöltése...")
        corpus = collect_webshop_text(base)
        char_count = len(corpus)
        st.write(f"✓ {char_count} karakter összegyűjtve")

        if char_count < 100:
            status.update(label="❌ Nem sikerült elérni a webshopot", state="error")
            st.error("A webshop nem volt elérhető. Ellenőrizd a domain nevet.")
            st.stop()

        # 2. Márka lista összeállítása az AI-nak
        all_brands_flat = []
        for src in BRAND_DB:
            all_brands_flat.extend(BRAND_DB[src]["brands"])

        aq_brands = ", ".join(BRAND_DB["aquashop"]["brands"])
        al_brands = ", ".join(BRAND_DB["aqualing"]["brands"])
        fl_brands = ", ".join(BRAND_DB["fluidra"]["brands"])

        # 3. AI elemzés
        st.write("🤖 AI elemzés folyamatban...")

        prompt = f"""Te egy webshop elemző vagy. Elemezd az alábbi webshop szöveget.

WEBSHOP: {domain}
LETÖLTÖTT SZÖVEG:
---
{corpus[:6000]}
---

FELADAT 1 – MÁRKAFELISMERÉS:
Nézd végig a fenti szöveget és keresd meg ezeket a márkaneveket.
CSAK olyan márkát jelölj meg amelyik SZÓSZERINT szerepel a fenti szövegben.
Ha nem látod a szövegben → NE add hozzá. Inkább maradjon ki mint hogy kitalálj egyet.

AQUASHOP márkák (csak ezekből választhatsz): {aq_brands}
AQUALING márkák (csak ezekből választhatsz): {al_brands}
FLUIDRA márkák (csak ezekből választhatsz): {fl_brands}

FELADAT 2 – PONTOZÁS a szöveg alapján:
- kinalat_teljessege (0-25): mennyire széles a medence/spa kínálat
- tartalmi_minoseg (0-20): leírások, képek, műszaki adatok minősége
- webshop_aktivitas (0-10): friss árak, készletjelzés megléte
- seo_elkotelezettsege (0-5): kulcsszavak használata

Válaszolj KIZÁRÓLAG az alábbi JSON formátumban, semmi más szöveg:
{{
  "partner_neve": "webshop neve",
  "osszefoglalo": "2-3 mondatos összefoglaló magyarul",
  "aquashop_markak": [],
  "aqualing_markak": [],
  "fluidra_markak": [],
  "kinalat_teljessege": 0,
  "tartalmi_minoseg": 0,
  "webshop_aktivitas": 0,
  "seo_elkotelezettsege": 0,
  "bizonyitek": "mit láttál a szövegben röviden",
  "javasolt_teendok": "konkrét fejlesztési javaslatok"
}}"""

        try:
            ai_text, used_model = ai_score(api_key, prompt)
            st.write(f"✓ Modell: {used_model.split('/')[-1]}")
        except Exception as e:
            status.update(label="❌ AI hiba", state="error")
            st.error(str(e))
            st.stop()

        # 4. JSON parse
        clean = re.sub(r'```json|```', '', ai_text).strip()
        js = clean.find('{')
        je = clean.rfind('}')
        if js == -1:
            status.update(label="❌ Érvénytelen AI válasz", state="error")
            st.error("Az AI nem adott JSON választ. Próbáld újra!")
            st.stop()
        try:
            data = json.loads(clean[js:je+1])
        except:
            status.update(label="❌ JSON hiba", state="error")
            st.error("Hibás JSON válasz. Próbáld újra!")
            st.stop()

        # 5. Márka validáció – csak adatbázisban szereplő márkák fogadhatók el
        def validate(ai_list, valid_list):
            valid_lower = {b.lower(): b for b in valid_list}
            result = []
            for b in (ai_list or []):
                canonical = valid_lower.get(b.lower())
                if canonical and canonical not in result:
                    result.append(canonical)
            return result

        found_aq = validate(data.get("aquashop_markak", []), BRAND_DB["aquashop"]["brands"])
        found_al = validate(data.get("aqualing_markak", []), BRAND_DB["aqualing"]["brands"])
        found_fl = validate(data.get("fluidra_markak", []), BRAND_DB["fluidra"]["brands"])

        st.write(f"✓ Aquashop: {len(found_aq)} | Aqualing: {len(found_al)} | Fluidra: {len(found_fl)}")

        # 6. Pontszám összerakása
        aq_score = (0 if not found_aq else
                    10 if len(found_aq) <= 2 else
                    20 if len(found_aq) <= 4 else
                    30 if len(found_aq) <= 7 else 40)

        scores = {
            "exkluziv_termekek":  aq_score,
            "kinalat_teljessege": min(25, int(data.get("kinalat_teljessege", 0))),
            "tartalmi_minoseg":   min(20, int(data.get("tartalmi_minoseg", 0))),
            "webshop_aktivitas":  min(10, int(data.get("webshop_aktivitas", 0))),
            "seo_elkotelezettsege": min(5, int(data.get("seo_elkotelezettsege", 0))),
        }
        total = sum(scores.values())

        tier_key = ("PLATINUM" if total >= 85 else
                    "GOLD"     if total >= 65 else
                    "SILVER"   if total >= 40 else
                    "BASIC"    if total >= 20 else "INAKTÍV")

        result = {
            "domain": domain,
            "partner_neve": data.get("partner_neve", domain),
            "osszefoglalo": data.get("osszefoglalo", ""),
            "scores": scores,
            "total": total,
            "tier": tier_key,
            "markak": {"aquashop": found_aq, "aqualing": found_al, "fluidra": found_fl},
            "bizonyitek": data.get("bizonyitek", ""),
            "javasolt_teendok": data.get("javasolt_teendok", ""),
        }
        st.session_state.last_result = result
        status.update(label="✅ Elemzés kész!", state="complete")

# ── Eredmény megjelenítése ────────────────────────────────────────────
result = st.session_state.get("last_result")
if result:
    total = result["total"]
    tier  = TIER_CONFIG[result["tier"]]
    scores = result["scores"]
    found_aq = result["markak"]["aquashop"]
    found_al = result["markak"]["aqualing"]
    found_fl = result["markak"]["fluidra"]

    # Hero kártya
    st.markdown(f"""<div class="hero">
<div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
  <div class="score-big">{total}</div>
  <div>
    <div class="tier-badge" style="color:{tier['color']}">{tier['emoji']} {tier['label']}</div>
    <div style="font-size:12px;color:#7a9fc0;font-family:monospace">{result['partner_neve']} · {result['domain']}</div>
    <div style="font-size:13px;color:#c8d8f0;margin-top:6px;max-width:480px">{result['osszefoglalo']}</div>
  </div>
</div>
</div>""", unsafe_allow_html=True)

    # Márka arány
    st.markdown('<div class="slabel">▸ Márkaösszetétel</div>', unsafe_allow_html=True)
    aq = len(found_aq); al = len(found_al); fl = len(found_fl)
    tb = max(aq+al+fl, 1)
    ap = round(aq/tb*100); alp = round(al/tb*100); fp = 100-ap-alp

    def seg(p, cls):
        return f'<div class="seg {cls}" style="width:{p}%">{""+str(p)+"%" if p>8 else ""}</div>' if p > 0 else ""

    st.markdown(f"""<div class="ratio-box">
<div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:8px;font-size:13px">
  <span style="color:#5ee8ff;font-weight:700">Aquashop {ap}% ({aq})</span>
  <span style="color:#fdd835;font-weight:700">Aqualing {alp}% ({al})</span>
  <span style="color:#ff8c5a;font-weight:700">Fluidra {fp}% ({fl})</span>
</div>
<div class="bar">{seg(ap,'s-aq')}{seg(alp,'s-al')}{seg(fp,'s-fl')}</div>
</div>""", unsafe_allow_html=True)

    # Márkachipek
    chips = ""
    for lst, cls in [(found_aq,"chip-aq"),(found_al,"chip-al"),(found_fl,"chip-fl")]:
        for b in lst:
            chips += f'<span class="chip {cls}">{b}</span>'
    if chips:
        st.markdown(f'<div style="margin:8px 0"><div style="font-size:11px;color:#7a9fc0;margin-bottom:6px;letter-spacing:1px">AZONOSÍTOTT MÁRKÁK</div>{chips}</div>', unsafe_allow_html=True)

    # Dimenzió bontás
    st.markdown('<div class="slabel">▸ Dimenzió bontás</div>', unsafe_allow_html=True)
    for key, label, max_pts in DIM_DEFS:
        pts = scores.get(key, 0)
        ca, cb = st.columns([4,1])
        with ca:
            st.markdown(f"<div style='font-size:13px;color:#e0eeff;margin-bottom:4px'>{label}</div>", unsafe_allow_html=True)
            st.progress(pts/max_pts)
        with cb:
            color = "#00d4ff" if pts > 0 else "#555"
            st.markdown(f"<div style='font-size:14px;font-weight:700;color:{color};text-align:right;padding-top:4px'>{pts}/{max_pts}</div>", unsafe_allow_html=True)

    # Bizonyíték + javaslat
    if result.get("bizonyitek"):
        st.markdown('<div class="slabel">▸ Mit talált az AI a szövegben</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ev"><div class="ev-t">BIZONYÍTÉK</div><div style="font-size:13px;color:#e0eeff">{result["bizonyitek"]}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="slabel">▸ Javasolt teendők</div>', unsafe_allow_html=True)
    jav = result.get("javasolt_teendok","")
    if jav:
        st.markdown(f'<div class="rec"><div style="font-size:13px;color:#e0eeff;line-height:1.8">{jav.replace(chr(10),"<br>")}</div></div>', unsafe_allow_html=True)

    # History
    aq_pct = round(len(found_aq)/max(len(found_aq)+len(found_al)+len(found_fl),1)*100)
    st.session_state.history.insert(0, {
        "domain": result["domain"], "partner": result["partner_neve"],
        "total": total, "tier": result["tier"],
        "aq_pct": aq_pct, "date": datetime.now().strftime("%Y.%m.%d"),
    })
    # Deduplikálás
    seen = set()
    st.session_state.history = [h for h in st.session_state.history
                                  if not (h["domain"] in seen or seen.add(h["domain"]))]

# ── Előzmények ────────────────────────────────────────────────────────
if st.session_state.history:
    st.markdown('<div class="slabel">▸ Korábbi értékelések</div>', unsafe_allow_html=True)
    tc = {"PLATINUM":"#00d4ff","GOLD":"#f5c842","SILVER":"#8fa8c8","BASIC":"#ff8c38","INAKTÍV":"#ff4455"}
    for h in st.session_state.history[:10]:
        c1,c2,c3,c4 = st.columns([3,1,1,1])
        with c1: st.markdown(f"<span style='font-size:13px;color:#c8d8f0'>{h['partner']} · {h['domain']}</span>", unsafe_allow_html=True)
        with c2: st.markdown(f"<span style='color:#5ee8ff;font-size:12px'>AQ: {h['aq_pct']}%</span>", unsafe_allow_html=True)
        with c3:
            color = tc.get(h["tier"], "#fff")
            st.markdown(f"<span style='color:{color};font-weight:700'>{h['total']} pt</span>", unsafe_allow_html=True)
        with c4: st.markdown(f"<span style='color:#7a9fc0;font-size:11px'>{h['date']}</span>", unsafe_allow_html=True)
