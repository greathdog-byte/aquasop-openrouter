import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from urllib.parse import urlparse, quote

st.set_page_config(page_title="Aquashop · Partner Scoring", page_icon="💧", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;color:#e8f0fe}
[data-testid="stAppViewContainer"]{background:#060912}
[data-testid="stHeader"]{background:#060912;border-bottom:1px solid #1c2a42}
[data-testid="stSidebar"]{background:#0d1424}
[data-testid="stSidebar"] *{color:#c8d8f0!important}
p,span,div,label{color:#c8d8f0}
h1,h2,h3{font-family:'Syne',sans-serif!important;color:#fff}
input,textarea{background:#121d30!important;color:#e8f0fe!important;border-color:#243350!important}
.score-hero{background:linear-gradient(135deg,#0d1424,#121d30);border:1px solid #2a3f5a;border-radius:16px;padding:28px;margin:16px 0;position:relative;overflow:hidden}
.score-hero::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,#0055ff,#00d4ff,#00ffb3)}
.score-big{font-family:'Syne',sans-serif;font-weight:800;font-size:56px;line-height:1;background:linear-gradient(135deg,#00d4ff,#0055ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.tier-badge{font-family:'Syne',sans-serif;font-weight:800;font-size:26px;margin-bottom:4px}
.ratio-bar-container{background:#0d1830;border:1px solid #2a3f5a;border-radius:12px;padding:20px;margin:12px 0}
.ratio-bar{height:32px;border-radius:10px;overflow:hidden;display:flex;margin:10px 0}
.seg{height:100%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:rgba(0,0,0,0.8);white-space:nowrap;overflow:hidden}
.seg-aq{background:#00d4ff}.seg-al{background:#f5c842}.seg-fl{background:#ff6b35}.seg-neu{background:#8fa8c8}
.brand-chip{display:inline-block;padding:4px 11px;border-radius:20px;font-size:12px;font-weight:600;margin:3px}
.chip-aq{background:rgba(0,212,255,0.18);color:#5ee8ff;border:1px solid rgba(0,212,255,0.4)}
.chip-al{background:rgba(245,200,66,0.18);color:#fdd835;border:1px solid rgba(245,200,66,0.4)}
.chip-fl{background:rgba(255,107,53,0.18);color:#ff8c5a;border:1px solid rgba(255,107,53,0.4)}
.ev-card{background:#0d1830;border:1px solid #2a3f5a;border-radius:10px;padding:14px;margin:6px 0}
.ev-title{font-size:11px;color:#7a9fc0;margin-bottom:6px;font-weight:600}
.rec-box{background:#0d1830;border:1px solid #2a3f5a;border-radius:12px;padding:18px;margin:12px 0}
.section-label{font-family:'Syne',sans-serif;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#00d4ff;margin:20px 0 10px}
</style>
""", unsafe_allow_html=True)

# ── Márkaadatbázis ───────────────────────────────────────────────────
BRAND_DB = {
    "aquashop": {
        "label":"Aquashop","color":"#00d4ff","chip":"chip-aq",
        "brands":["Fairland","InverPro","Inver-X","WarriorX","Maytronics","Dolphin","Liberty",
                  "Saci","Gemas","Microdos","BSV","BSV Touch","Sopremapool","Flagpool",
                  "Hidroten","Nature Works","Aquajet"]
    },
    "aqualing": {
        "label":"Aqualing","color":"#f5c842","chip":"chip-al",
        "brands":["Pontaqua","PoolTrend","Dekortrend","Bestway","Intex","Kokido",
                  "Hydro Force","HydroForce","Gladiator","Gladiator SUP","Wellis",
                  "VitalSpa","Azton","Wattsup"]
    },
    "fluidra": {
        "label":"Fluidra-Kerex","color":"#ff6b35","chip":"chip-fl",
        "brands":["Astralpool","AstralPool","Astral","Zodiac","Bayrol","GRE","Pahlen",
                  "Speck","ZDS","Kripsol","Fluidra","Kerex","iAquaLink","Omniflex"]
    }
}

TIER_CONFIG = {
    "PLATINUM":{"emoji":"🥇","color":"#00d4ff","label":"PLATINUM Partner"},
    "GOLD":    {"emoji":"🥈","color":"#f5c842","label":"GOLD Partner"},
    "SILVER":  {"emoji":"🥉","color":"#8fa8c8","label":"SILVER Partner"},
    "BASIC":   {"emoji":"⚠️","color":"#ff8c38","label":"BASIC Partner"},
    "INAKTÍV": {"emoji":"🔴","color":"#ff4455","label":"INAKTÍV"},
}
DIM_DEFS = [
    ("exkluziv_termekek","Aquashop exkluzív termékek",40),
    ("kinalat_teljessege","Kínálat teljessége",25),
    ("tartalmi_minoseg","Tartalmi minőség",20),
    ("webshop_aktivitas","Aktivitás & frissesség",10),
    ("seo_elkotelezettsege","SEO elkötelezettsége",5),
]

if "history" not in st.session_state:
    st.session_state.history = []

# Cache a főoldalak fingerprintjéhez
_homepage_fp = {}

# ── API kulcs ────────────────────────────────────────────────────────
def get_api_key():
    try:
        return st.secrets["OPENROUTER_API_KEY"]
    except:
        import os
        return os.environ.get("OPENROUTER_API_KEY","")

# ── Webshop letöltés ────────────────────────────────────────────────
HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def get_text(url, max_chars=3000):
    try:
        r = requests.get(url, headers=HEADERS, timeout=7)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script","style","nav","footer","header"]):
            t.decompose()
        return re.sub(r'\s+', ' ', soup.get_text(separator=" ", strip=True))[:max_chars]
    except:
        return ""

def get_sitemap_text(base):
    """Sitemap URL-ek összefűzve – tartalmazzák a márkaneveket."""
    for path in ["/sitemap.xml","/sitemap_index.xml"]:
        try:
            r = requests.get(base+path, headers=HEADERS, timeout=6)
            if r.status_code != 200:
                continue
            locs = re.findall(r'<loc>(.*?)</loc>', r.text)
            # Ha sitemap index, egy szinttel mélyebb
            if not locs:
                continue
            sub = [l for l in locs if "sitemap" in l.lower()]
            if sub:
                all_locs = []
                for s in sub[:4]:
                    try:
                        sr = requests.get(s, headers=HEADERS, timeout=5)
                        all_locs += re.findall(r'<loc>(.*?)</loc>', sr.text)
                    except:
                        pass
                locs = all_locs or locs
            return " ".join(locs[:500])
        except:
            pass
    return ""

def get_homepage_fingerprint(base):
    """Főoldal szöveg hash - a keresési oldal és főoldal megkülönböztetéséhez"""
    try:
        r = requests.get(base, headers=HEADERS, timeout=7)
        soup = BeautifulSoup(r.text, "html.parser")
        # Csak a body tartalmát nézzük
        body = soup.find('body')
        if body:
            for t in body(["nav", "footer", "header", "script", "style"]):
                t.decompose()
            text = body.get_text()[:500]
        else:
            for t in soup(["nav", "footer", "header", "script", "style"]):
                t.decompose()
            text = soup.get_text()[:500]
        return hash(text)
    except:
        return None

def check_one_brand(base, brand):
    """
    Márka keresése a webshopban - LAZA ELLENŐRZÉS
    Visszatér True-val ha a márka jelen van
    """
    b = brand.lower()
    b_slug = b.replace(" ", "-")
    b_nospace = b.replace(" ", "")
    
    # Főoldal fingerprint (cache)
    if base not in _homepage_fp:
        _homepage_fp[base] = get_homepage_fingerprint(base)
    home_fp = _homepage_fp[base]
    
    no_result_phrases = ["nincs találat", "no results", "0 termék", "nem található",
                         "0 találat", "nincsenek termékek", "nincs ilyen termék"]
    
    # 1. Keresés a márka aloldalon (ez a legvalószínűbb)
    for direct_url in [
        f"{base}/marka/{b_slug}",
        f"{base}/marka/{b}",
        f"{base}/termekek/marka/{b_slug}",
        f"{base}/brand/{b_slug}",
        f"{base}/márka/{b_slug}",
        f"{base}/termekek/{b_slug}",
        f"{base}/kategoria/{b_slug}",
        f"{base}/c/{b_slug}",
        f"{base}/{b_slug}",
        f"{base}/gyarto/{b_slug}",
        f"{base}/gyártó/{b_slug}",
    ]:
        try:
            r = requests.get(direct_url, headers=HEADERS, timeout=5)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for t in soup(["nav", "footer", "header", "script", "style"]):
                    t.decompose()
                page = soup.get_text()
                
                # Ne legyen ugyanaz mint a főoldal
                if home_fp and hash(page[:500]) == home_fp:
                    continue
                
                page_lower = page.lower()
                # Ha a márka szerepel a szövegben, valószínűleg jó
                if b in page_lower or b_slug in page_lower:
                    return True
        except:
            pass
    
    # 2. Belső kereső - LAZA ELLENŐRZÉS (elég ha szerepel a márka)
    for search_url in [
        f"{base}/?s={quote(brand)}",
        f"{base}/?search={quote(brand)}",
        f"{base}/search?q={quote(brand)}",
        f"{base}/?q={quote(brand)}",
        f"{base}/kereses/?q={quote(brand)}",
        f"{base}/termekek/?search={quote(brand)}",
        f"{base}/search/{quote(brand)}",
        f"{base}/keresés/{quote(brand)}",
    ]:
        try:
            r = requests.get(search_url, headers=HEADERS, timeout=7)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for t in soup(["nav", "footer", "header", "script", "style"]):
                t.decompose()
            page = soup.get_text()
            
            # Ha a keresési oldal ugyanolyan mint a főoldal  a webshop nem tud keresni
            page_fp = hash(page[:500])
            if home_fp and page_fp == home_fp:
                continue
            
            page_lower = page.lower()
            
            # "Nincs találat" kizárása
            if any(x in page_lower for x in no_result_phrases):
                continue
            
            # Márkanév előfordulás - elég egyszer is
            if b in page_lower or b_slug in page_lower or b_nospace in page_lower:
                return True
        except:
            pass
    
    # 3. URL direkt ellenőrzés - linkekben keresés
    try:
        r = requests.get(base, headers=HEADERS, timeout=7)
        if r.status_code == 200:
            # Linkek keresése a főoldalon
            links = re.findall(r'href=["\']([^"\']+)["\']', r.text)
            for link in links:
                if b_slug in link.lower() or b_nospace in link.lower() or b in link.lower():
                    # Ne legyen "no result" oldal
                    if "noresult" not in link.lower() and "notfound" not in link.lower():
                        return True
    except:
        pass
    
    return False


def detect_brands(base, progress_cb=None):
    """
    Teljes márkadetekció minden ismert márkára.
    """
    # Nagyobb corpus a jobb gyorsellenőrzéshez
    corpus = get_text(base, 15000)
    corpus += " " + get_sitemap_text(base)
    
    # Több oldal letöltése a corpus bővítéséhez
    important_paths = [
        "/termekek", "/kategoriak", "/medence", "/spa", "/szivattyu",
        "/hoszivattyu", "/robot", "/vegyszer", "/pumpa", "/markak",
        "/marka", "/brands", "/márkák", "/gyártók", "/gyartok",
        "/markaink", "/partnereink", "/termekek/marka"
    ]
    
    for path in important_paths:
        corpus += " " + get_text(base+path, 2000)
    
    corpus_lower = corpus.lower()
    
    found = {"aquashop": [], "aqualing": [], "fluidra": []}
    
    # Összes márka listája kategóriával
    all_brands = []
    for src in ["aquashop", "aqualing", "fluidra"]:
        for brand in BRAND_DB[src]["brands"]:
            all_brands.append((src, brand))
    
    total = len(all_brands)
    found_count = 0
    
    # Márkák ellenőrzése
    for i, (src, brand) in enumerate(all_brands):
        if progress_cb:
            progress_cb(i, total, brand)
        
        b = brand.lower()
        b_slug = b.replace(" ", "-")
        b_nospace = b.replace(" ", "")
        
        # Gyors ellenőrzés a corpusban
        if b in corpus_lower or b_slug in corpus_lower or b_nospace in corpus_lower:
            found[src].append(brand)
            found_count += 1
            continue
        
        # Pontos ellenőrzés a webshopban
        if check_one_brand(base, brand):
            found[src].append(brand)
            found_count += 1
    
    if progress_cb:
        progress_cb(total, total, f"kész - Találatok: {found_count}/{total}")
    
    return found, corpus[:15000]

# ── OpenRouter hívás ─────────────────────────────────────────────────
MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-4-scout:free",
    "deepseek/deepseek-chat:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-27b-it:free",
]

def ai_call(api_key, prompt):
    import time
    last_err = ""
    for model in MODELS:
        for attempt in range(2):
            try:
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json",
                             "HTTP-Referer":"https://aquashop-scoring.streamlit.app"},
                    json={"model":model,"messages":[{"role":"user","content":prompt}],
                          "temperature":0.1,"max_tokens":1500},
                    timeout=45
                )
                data = r.json()
                if "error" in data:
                    err = str(data["error"].get("message",""))
                    last_err = f"{model}: {err}"
                    if any(x in err for x in ["No endpoints","not found","404"]):
                        break
                    if attempt == 0:
                        time.sleep(5)
                        continue
                    break
                return data["choices"][0]["message"]["content"], model
            except Exception as e:
                last_err = str(e)
                if attempt == 0:
                    time.sleep(4)
    raise Exception(f"Minden modell elérhetetlen: {last_err}")

# ── Header ───────────────────────────────────────────────────────────
st.markdown("""<div style='display:flex;align-items:center;gap:12px;padding:8px 0 24px'>
  <div style='width:36px;height:36px;background:linear-gradient(135deg,#00d4ff,#0055ff);border-radius:8px;display:flex;align-items:center;justify-content:center;font-family:Syne;font-weight:800;font-size:16px;color:#fff'>A</div>
  <span style='font-family:Syne;font-weight:700;font-size:18px;color:#dce8f5'>Aquashop <span style='color:#4a6080;font-weight:400'>/ Partner Scoring</span></span>
  <div style='margin-left:auto;font-size:10px;letter-spacing:1px;color:#f5c842;background:rgba(245,200,66,0.08);border:1px solid rgba(245,200,66,0.2);border-radius:4px;padding:3px 8px'>AI · OPENROUTER</div>
</div>""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 OpenRouter API kulcs")
    st.markdown("""Ingyenes kulcs (EU-ban működik):
1. [openrouter.ai](https://openrouter.ai) → Sign up
2. [openrouter.ai/keys](https://openrouter.ai/keys) → Create Key
3. Streamlit → Settings → Secrets:
```
OPENROUTER_API_KEY = "sk-or-..."
```""")
    st.divider()
    st.markdown("### 📋 Márkaadatbázis")
    for src, data in BRAND_DB.items():
        with st.expander(f"{data['label']} ({len(data['brands'])} márka)"):
            st.write(", ".join(data["brands"]))

# ── Fő tartalom ──────────────────────────────────────────────────────
st.markdown("<h1 style='font-family:Syne;font-size:32px;font-weight:800;color:#dce8f5;margin-bottom:4px'>Domain  Márkaösszetétel</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#7a9fc0;margin-bottom:24px'>Add meg a webshop domain nevét.</p>", unsafe_allow_html=True)

col1, col2 = st.columns([4,1])
with col1:
    domain_input = st.text_input("", placeholder="pl. aquashop.hu", label_visibility="collapsed")
with col2:
    scan_btn = st.button("Elemzés ", type="primary", use_container_width=True)

# ── Elemzés ──────────────────────────────────────────────────────────
if scan_btn and domain_input:
    api_key = get_api_key()
    if not api_key:
        st.error("⚠️ OpenRouter API kulcs hiányzik! Streamlit Settings  Secrets OPENROUTER_API_KEY")
        st.stop()

    raw = domain_input.strip()
    if not raw.startswith("http"):
        raw = "https://" + raw
    domain = urlparse(raw).netloc.replace("www.","") or raw
    base = f"https://{domain}"

    with st.status(f"🤖 Elemzés: {domain}...", expanded=True) as status:

        # 1. Márkadetekció
        st.write("🔍 Webshop letöltése és márkafelismerés...")
        prog_bar = st.progress(0)
        prog_text = st.empty()

        def on_progress(current, total, brand_name):
            pct = current / total if total > 0 else 0
            prog_bar.progress(pct)
            if "kész" in brand_name:
                prog_text.markdown(f"<span style='color:#00d4ff;font-size:13px'>✓ {brand_name}</span>", unsafe_allow_html=True)
            else:
                prog_text.markdown(f"<span style='color:#7a9fc0;font-size:12px'>🔎 Ellenőrzés: **{brand_name}** ({current}/{total})</span>", unsafe_allow_html=True)

        found, corpus = detect_brands(base, progress_cb=on_progress)
        found_aq = found["aquashop"]
        found_al = found["aqualing"]
        found_fl = found["fluidra"]
        prog_bar.empty()
        prog_text.empty()
        st.write(f"✓ Aquashop: {len(found_aq)} | Aqualing: {len(found_al)} | Fluidra: {len(found_fl)}")
        
        # Ha kevés Aquashop márkát találtunk, kiírjuk figyelmeztetést
        if len(found_aq) < 3 and "aquashop" in domain:
            st.warning(f"⚠️ Csak {len(found_aq)} Aquashop márkát találtam. Lehet, hogy a webshop speciális URL struktúrát használ.")

        # 2. Exkluzív pont (Aquashop márkák száma alapján)
        aq_score = 0
        if len(found_aq) >= 8:
            aq_score = 40
        elif len(found_aq) >= 5:
            aq_score = 30
        elif len(found_aq) >= 3:
            aq_score = 20
        elif len(found_aq) >= 1:
            aq_score = 10

        # 3. AI pontozás
        st.write("🤖 AI minőségi pontozás...")
        
        # Márkák listázása a promptban
        aq_list = ", ".join(found_aq[:15]) if found_aq else "nincs"
        al_list = ", ".join(found_al[:15]) if found_al else "nincs"
        fl_list = ", ".join(found_fl[:15]) if found_fl else "nincs"
        
        prompt = f"""Magyar medence/spa webshop elemzése: {domain}

WEBSHOP TARTALOM:
{corpus[:4000]}

MÁR AZONOSÍTOTT MÁRKÁK (NE VÁLTOZTASD):
- Aquashop ({len(found_aq)}): {aq_list}
- Aqualing ({len(found_al)}): {al_list}
- Fluidra ({len(found_fl)}): {fl_list}

PONTOZÁS (csak ezeket töltsd ki, a márkákat ne módosítsd):
- exkluziv_termekek: PONTOSAN {aq_score} (ne változtasd!)
- kinalat_teljessege max 25: termékkör szélessége, választék
- tartalmi_minoseg max 20: termékleírások, képek minősége
- webshop_aktivitas max 10: friss árak, készletinfo, akciók
- seo_elkotelezettsege max 5: SEO elemek, kulcsszavak

Válasz CSAK valid JSON, semmi más:
{{"partner_neve":"string","osszefoglalo":"2-3 mondat magyarul","scores":{{"exkluziv_termekek":{aq_score},"kinalat_teljessege":0,"tartalmi_minoseg":0,"webshop_aktivitas":0,"seo_elkotelezettsege":0}},"bizonyitekok":{{"talalt_termekek":"string","kinalat_szelessege":"string","tartalom_minosege":"string","aktivitas_frissesseg":"string"}},"javasolt_teendok":"string"}}"""

        try:
            raw_text, used_model = ai_call(api_key, prompt)
            st.write(f"✓ Modell: {used_model.split('/')[-1]}")
        except Exception as e:
            status.update(label="❌ Hiba", state="error")
            st.error(str(e))
            st.stop()

        # JSON parse
        clean = re.sub(r'```json|```', '', raw_text).strip()
        bs = clean.find('{')
        be = clean.rfind('}')
        if bs == -1:
            status.update(label="❌ JSON hiba", state="error")
            st.error("Érvénytelen AI válasz. Próbáld újra!")
            st.stop()
        try:
            ai_data = json.loads(clean[bs:be+1])
        except:
            status.update(label="❌ JSON parse hiba", state="error")
            st.error("Hibás JSON. Próbáld újra!")
            st.stop()

        # Eredmény összerakása
        scores = ai_data.get("scores", {})
        scores["exkluziv_termekek"] = aq_score
        calc_total = sum(int(v) for v in scores.values())

        if calc_total >= 85:
            tier_key = "PLATINUM"
        elif calc_total >= 65:
            tier_key = "GOLD"
        elif calc_total >= 40:
            tier_key = "SILVER"
        elif calc_total >= 20:
            tier_key = "BASIC"
        else:
            tier_key = "INAKTÍV"

        result = {
            "domain": domain,
            "partner_neve": ai_data.get("partner_neve", domain),
            "osszefoglalo": ai_data.get("osszefoglalo", ""),
            "scores": scores,
            "total": min(100, calc_total),
            "tier": tier_key,
            "markak": {"aquashop": found_aq, "aqualing": found_al, "fluidra": found_fl, "egyeb": []},
            "markaok_szama": {"aquashop": len(found_aq), "aqualing": len(found_al), "fluidra": len(found_fl), "egyeb": 0},
            "bizonyitekok": ai_data.get("bizonyitekok", {}),
            "javasolt_teendok": ai_data.get("javasolt_teendok", ""),
        }
        st.session_state.last_result = result
        status.update(label="✅ Elemzés kész!", state="complete")

    # ── Eredmény megjelenítés ─────────────────────────────────────────
    result = st.session_state.get("last_result")
    if not result:
        st.stop()
    total = result["total"]
    tier = TIER_CONFIG.get(result["tier"], TIER_CONFIG["INAKTÍV"])

    st.markdown(f"""<div class="score-hero">
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
        <div class="score-big">{total}</div>
        <div>
          <div class="tier-badge" style="color:{tier['color']}">{tier['emoji']} {tier['label']}</div>
          <div style="font-size:12px;color:#7a9fc0;font-family:monospace">{result['partner_neve']} / {domain}</div>
          <div style="font-size:13px;color:#c8d8f0;margin-top:6px;max-width:480px">{result['osszefoglalo']}</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # Márka arány
    st.markdown('<div class="section-label">▸ Márkaösszetétel & versenytárs arány</div>', unsafe_allow_html=True)
    mc = result["markaok_szama"]
    aq = mc["aquashop"]
    al = mc["aqualing"]
    fl = mc["fluidra"]
    tb = max(aq + al + fl, 1)
    aq_pct = round(aq / tb * 100)
    al_pct = round(al / tb * 100)
    fl_pct = 100 - aq_pct - al_pct

    def seg(pct, cls):
        if pct <= 0:
            return ''
        return f'<div class="seg {cls}" style="width:{pct}%">{str(pct)+"%" if pct>7 else ""}</div>'

    st.markdown(f"""<div class="ratio-bar-container">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:10px;font-size:13px">
        <span style="color:#5ee8ff;font-weight:700">Aquashop {aq_pct}% ({aq})</span>
        <span style="color:#fdd835;font-weight:700">Aqualing {al_pct}% ({al})</span>
        <span style="color:#ff8c5a;font-weight:700">Fluidra-Kerex {fl_pct}% ({fl})</span>
      </div>
      <div class="ratio-bar">{seg(aq_pct,'seg-aq')}{seg(al_pct,'seg-al')}{seg(fl_pct,'seg-fl')}</div>
    </div>, unsafe_allow_html=True)

    # Márkák chip-ekben
    chips = ""
    for src, cls in [("aquashop","chip-aq"),("aqualing","chip-al"),("fluidra","chip-fl")]:
        for b in result["markak"].get(src,[]):
            chips += f'<span class="brand-chip {cls}">{b}</span>'
    if chips:
        st.markdown(f'<div style="margin:10px 0"><div style="font-size:11px;color:#7a9fc0;margin-bottom:6px;letter-spacing:1px">AZONOSÍTOTT MÁRKÁK</div>{chips}</div>', unsafe_allow_html=True)

    # Dimenzió bontás
    st.markdown('<div class="section-label">▸ Dimenzió bontás</div>', unsafe_allow_html=True)
    for key, label, max_pts in DIM_DEFS:
        pts = int(result["scores"].get(key, 0))
        c1, c2 = st.columns([4,1])
        with c1:
            st.markdown(f"<div style='font-size:13px;color:#e0eeff;margin-bottom:4px;font-weight:500'>{label}</div>", unsafe_allow_html=True)
            st.progress(pts/max_pts)
        with c2:
            color = "#00d4ff" if pts > 0 else "#666"
            st.markdown(f"<div style='font-size:14px;font-weight:700;color:{color};text-align:right;padding-top:4px'>{pts}/{max_pts}</div>", unsafe_allow_html=True)

    # Bizonyítékok
    biz = result.get("bizonyitekok", {})
    if any(biz.values()):
        st.markdown('<div class="section-label">▸ Elemzési bizonyítékok</div>', unsafe_allow_html=True)
        items = [("Talált termékek", biz.get("talalt_termekek","")),
                 ("Kínálat szélessége", biz.get("kinalat_szelessege","")),
                 ("Tartalom minősége", biz.get("tartalom_minosege","")),
                 ("Aktivitás & frissesség", biz.get("aktivitas_frissesseg",""))]
        c1, c2 = st.columns(2)
        for i, (t, v) in enumerate(items):
            if v:
                with (c1 if i%2==0 else c2):
                    st.markdown(f'<div class="ev-card"><div class="ev-title">{t}</div><div style="font-size:12px;color:#e0eeff;line-height:1.6">{v}</div></div>', unsafe_allow_html=True)

    # Javaslatok
    st.markdown('<div class="section-label">▸ Javasolt teendők</div>', unsafe_allow_html=True)
    jav = result.get("javasolt_teendok","")
    if jav and not jav.strip().startswith(("{","```")):
        st.markdown(f'<div class="rec-box"><div style="font-size:13px;color:#e0eeff;line-height:1.8">{jav.replace(chr(10),"<br>")}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="rec-box"><div style="color:#7a9fc0">Nem érkezett javaslat.</div></div>', unsafe_allow_html=True)

    # History mentés
    st.session_state.history.insert(0, {
        "domain": domain, "partner": result["partner_neve"],
        "total": total, "tier": result["tier"],
        "aq_pct": aq_pct, "date": datetime.now().strftime("%Y.%m.%d"),
    })

# ── Előzmények ───────────────────────────────────────────────────────
if st.session_state.history:
    st.markdown('<div class="section-label">▸ Korábbi értékelések</div>', unsafe_allow_html=True)
    colors = {"PLATINUM":"#00d4ff","GOLD":"#f5c842","SILVER":"#8fa8c8","BASIC":"#ff8c38","INAKTÍV":"#ff4455"}
    for h in st.session_state.history[:10]:
        c1,c2,c3,c4 = st.columns([3,1,1,1])
        with c1: st.markdown(f"<span style='font-size:13px;color:#c8d8f0'>{h['partner']} · {h['domain']}</span>", unsafe_allow_html=True)
        with c2: st.markdown(f"<span style='color:#5ee8ff;font-size:12px'>AQ: {h['aq_pct']}%</span>", unsafe_allow_html=True)
        with c3:
            tc = colors.get(h["tier"],"#fff")
            st.markdown(f"<span style='color:{tc};font-weight:700'>{h['total']} pt</span>", unsafe_allow_html=True)
        with c4: st.markdown(f"<span style='color:#7a9fc0;font-size:11px'>{h['date']}</span>", unsafe_allow_html=True)
