import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from urllib.parse import urlparse

st.set_page_config(page_title="Aquashop · Partner Scoring (OpenRouter)", page_icon="💧", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: #e8f0fe; }
[data-testid="stAppViewContainer"] { background: #060912; color: #e8f0fe; }
[data-testid="stHeader"] { background: #060912; border-bottom: 1px solid #1c2a42; }
[data-testid="stSidebar"] { background: #0d1424; }
[data-testid="stSidebar"] * { color: #c8d8f0 !important; }
p, span, div, label { color: #c8d8f0; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; color: #ffffff; }
input, textarea { background: #121d30 !important; color: #e8f0fe !important; border-color: #243350 !important; }
.score-hero { background: linear-gradient(135deg,#0d1424,#121d30); border: 1px solid #2a3f5a; border-radius: 16px; padding: 28px; margin: 16px 0; position: relative; overflow: hidden; }
.score-hero::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg,#0055ff,#00d4ff,#00ffb3); }
.score-big { font-family:'Syne',sans-serif; font-weight:800; font-size:56px; line-height:1; background:linear-gradient(135deg,#00d4ff,#0055ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.tier-badge { font-family:'Syne',sans-serif; font-weight:800; font-size:26px; margin-bottom:4px; }
.ratio-bar-container { background:#0d1830; border:1px solid #2a3f5a; border-radius:12px; padding:20px; margin:12px 0; }
.ratio-bar { height:32px; border-radius:10px; overflow:hidden; display:flex; margin:10px 0; }
.seg { height:100%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:12px; color:rgba(0,0,0,0.8); white-space:nowrap; overflow:hidden; }
.seg-aq{background:#00d4ff} .seg-al{background:#f5c842} .seg-fl{background:#ff6b35} .seg-neu{background:#8fa8c8}
.brand-chip { display:inline-block; padding:4px 11px; border-radius:20px; font-size:12px; font-weight:600; margin:3px; }
.chip-aq{background:rgba(0,212,255,0.18);color:#5ee8ff;border:1px solid rgba(0,212,255,0.4)}
.chip-al{background:rgba(245,200,66,0.18);color:#fdd835;border:1px solid rgba(245,200,66,0.4)}
.chip-fl{background:rgba(255,107,53,0.18);color:#ff8c5a;border:1px solid rgba(255,107,53,0.4)}
.chip-neu{background:rgba(180,200,230,0.15);color:#b4c8e6;border:1px solid rgba(180,200,230,0.3)}
.ev-card{background:#0d1830;border:1px solid #2a3f5a;border-radius:10px;padding:14px;margin:6px 0}
.ev-title{font-size:11px;color:#7a9fc0;margin-bottom:6px;font-weight:600}
.rec-box{background:#0d1830;border:1px solid #2a3f5a;border-radius:12px;padding:18px;margin:12px 0}
.section-label{font-family:'Syne',sans-serif;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#00d4ff;margin:20px 0 10px}
</style>
""", unsafe_allow_html=True)

# ── Márkaadatbázis ───────────────────────────────────────────────────
BRAND_DB = {
    "aquashop": {
        "label": "Aquashop", "color": "#00d4ff", "chip": "chip-aq",
        "brands": ["Fairland","InverPro","Inver-X","WarriorX","Maytronics","Dolphin","Liberty","Saci","Gemas","Microdos","BSV","BSV Touch","Sopremapool","Flagpool","Hidroten","Nature Works","Aquajet"]
    },
    "aqualing": {
        "label": "Aqualing", "color": "#f5c842", "chip": "chip-al",
        "brands": ["Pontaqua","PoolTrend","Dekortrend","Bestway","Intex","Kokido","Hydro Force","HydroForce","Gladiator","Gladiator SUP","Wellis","VitalSpa","Azton","Wattsup"]
    },
    "fluidra": {
        "label": "Fluidra-Kerex", "color": "#ff6b35", "chip": "chip-fl",
        "brands": ["Astralpool","AstralPool","Astral","Zodiac","Bayrol","GRE","Pahlen","Speck","ZDS","Kripsol","Fluidra","Kerex","iAquaLink","Omniflex"]
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
    ("exkluziv_termekek","Aquashop exkluzív termékek",40),
    ("kinalat_teljessege","Kínálat teljessége",25),
    ("tartalmi_minoseg","Tartalmi minőség",20),
    ("webshop_aktivitas","Aktivitás & frissesség",10),
    ("seo_elkotelezettsege","SEO elkötelezettsége",5),
]

if "history" not in st.session_state:
    st.session_state.history = []

# ── API kulcs ────────────────────────────────────────────────────────
def get_api_key():
    try:
        return st.secrets["OPENROUTER_API_KEY"]
    except:
        import os
        return os.environ.get("OPENROUTER_API_KEY", "")

if "api_key" not in st.session_state:
    st.session_state.api_key = get_api_key()

# ── Webshop tartalom letöltése ───────────────────────────────────────
def fetch_webshop(url, max_chars=12000):
    """Letölti a webshop szövegét több oldalról."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    texts = []
    pages_to_try = [url, url.rstrip("/") + "/termekek", url.rstrip("/") + "/kategoriak",
                    url.rstrip("/") + "/medence", url.rstrip("/") + "/spa"]
    for page_url in pages_to_try[:3]:
        try:
            r = requests.get(page_url, headers=headers, timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script","style","nav","footer","header"]):
                    tag.decompose()
                text = soup.get_text(separator=" ", strip=True)
                text = re.sub(r'\s+', ' ', text)
                texts.append(f"[{page_url}]\n{text[:4000]}")
        except:
            pass
    combined = "\n\n".join(texts)
    return combined[:max_chars] if combined else ""

# ── OpenRouter API hívás ─────────────────────────────────────────────
OPENROUTER_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-27b-it:free",
    "microsoft/phi-4-reasoning:free",
]

def openrouter_call(api_key, prompt, retries=2):
    import time
    last_error = ""
    for model in OPENROUTER_MODELS:
        for attempt in range(retries):
            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://aquashop-scoring.streamlit.app",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 2000,
                    },
                    timeout=60
                )
                data = resp.json()
                if "error" in data:
                    err = data["error"].get("message","")
                    last_error = f"{model}: {err}"
                    if "rate" in err.lower() or "quota" in err.lower():
                        break
                    if attempt == 0:
                        time.sleep(5)
                        continue
                    break
                return data["choices"][0]["message"]["content"], model
            except Exception as e:
                last_error = str(e)
                if attempt == 0:
                    time.sleep(5)
    raise Exception(f"OpenRouter hiba: {last_error}")

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
st.markdown("<h1 style='font-family:Syne;font-size:32px;font-weight:800;color:#dce8f5;margin-bottom:4px'>Domain → Márkaösszetétel</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#7a9fc0;margin-bottom:24px'>Add meg a webshop címét – az app letölti a tartalmat, azonosítja a márkákat és elkészíti a scorecard-ot.</p>", unsafe_allow_html=True)

col1, col2 = st.columns([4,1])
with col1:
    domain_input = st.text_input("", placeholder="pl. medencefutar.hu", label_visibility="collapsed")
with col2:
    scan_btn = st.button("Elemzés →", type="primary", use_container_width=True)

# ── Elemzés ──────────────────────────────────────────────────────────
if scan_btn and domain_input:
    api_key = st.session_state.get("api_key","")
    if not api_key:
        st.error("⚠️ OpenRouter API kulcs hiányzik! Streamlit → Settings → Secrets → OPENROUTER_API_KEY")
        st.stop()

    raw = domain_input.strip()
    if not raw.startswith("http"):
        raw = "https://" + raw
    domain = urlparse(raw).netloc.replace("www.","") or raw

    with st.status(f"🤖 Elemzés: {domain}...", expanded=True) as status:
        # 1. Webshop letöltése
        st.write("🌐 Webshop tartalom letöltése...")
        webshop_text = fetch_webshop(raw)
        if not webshop_text:
            st.warning("⚠️ Nem sikerült letölteni a webshopot – az AI a domain alapján dolgozik.")
            webshop_text = f"Webshop domain: {domain}"
        else:
            st.write(f"✓ {len(webshop_text)} karakter letöltve")

        # 2. Python gyors ellenőrzés a letöltött szövegben
        st.write("🔍 Márkafelismerés folyamatban...")
        found_in_text = {"aquashop":[], "aqualing":[], "fluidra":[]}
        text_lower = webshop_text.lower()
        for src in ["aquashop","aqualing","fluidra"]:
            for brand in BRAND_DB[src]["brands"]:
                if brand.lower() in text_lower:
                    found_in_text[src].append(brand)

        # 3. AI márkafelismerés + pontozás (az AI látja a webshopot)
        st.write("🤖 AI elemzés és márkafelismerés...")

        aq_brands_list = ", ".join(BRAND_DB["aquashop"]["brands"])
        al_brands_list = ", ".join(BRAND_DB["aqualing"]["brands"])
        fl_brands_list = ", ".join(BRAND_DB["fluidra"]["brands"])

        prompt = f"""Elemezd ezt a magyar medence/spa webshopot: {raw}

WEBSHOP TARTALOM (amit sikerült letölteni):
{webshop_text[:5000]}

FELADATOD:
1. A fenti szövegből és a webshop ismeretéből azonosítsd a márkákat
2. Ellenőrizd melyik márka szerepel a következő listákból:

AQUASHOP márkák (keresd ezeket): {aq_brands_list}
AQUALING márkák (keresd ezeket): {al_brands_list}  
FLUIDRA márkák (keresd ezeket): {fl_brands_list}

PONTOZÁSI SZABÁLYOK:
- exkluziv_termekek (max 40): 0 AQ márka=0p, 1-2=10p, 3-4=20p, 5-7=30p, 8+=40p
- kinalat_teljessege (max 25): medence/spa termékkör szélessége
- tartalmi_minoseg (max 20): leírások, képek, műszaki adatok minősége
- webshop_aktivitas (max 10): naprakész árak, készletjelzés
- seo_elkotelezettsege (max 5): kulcsszó-optimalizáltság

Válaszolj KIZÁRÓLAG valid JSON-ban, semmi más:
{{"partner_neve":"string","osszefoglalo":"2-3 mondatos magyar összefoglaló","markak_lista":{{"aquashop":["talált AQ márkák"],"aqualing":["talált AL márkák"],"fluidra":["talált FL márkák"],"egyeb":["egyéb márkák"]}},"scores":{{"exkluziv_termekek":0,"kinalat_teljessege":0,"tartalmi_minoseg":0,"webshop_aktivitas":0,"seo_elkotelezettsege":0}},"bizonyitekok":{{"talalt_termekek":"konkrét márkák és termékek","kinalat_szelessege":"kategóriák","tartalom_minosege":"leírások minősége","aktivitas_frissesseg":"árak és frissesség"}},"javasolt_teendok":"konkrét fejlesztési javaslatok"}}"""

        try:
            raw_text, used_model = openrouter_call(api_key, prompt)
            st.write(f"✓ Modell: {used_model.split('/')[-1]}")
        except Exception as e:
            status.update(label="❌ Hiba", state="error")
            st.error(str(e))
            st.stop()

        # JSON kinyerés
        clean = re.sub(r'```json|```','',raw_text).strip()
        bs = clean.find('{'); be = clean.rfind('}')
        if bs == -1:
            status.update(label="❌ JSON hiba", state="error")
            st.error("Az AI nem adott vissza JSON választ. Próbáld újra!")
            st.stop()
        try:
            ai_data = json.loads(clean[bs:be+1])
        except:
            status.update(label="❌ JSON parse hiba", state="error")
            st.error("Hibás JSON válasz. Próbáld újra!")
            st.stop()

        # AI által talált márkák + Python ellenőrzés összevonása
        ai_markak = ai_data.get("markak_lista", {})
        
        def merge_brands(ai_list, py_list):
            """AI és Python találatok összevonása, duplikátumok nélkül."""
            combined = list(ai_list) if ai_list else []
            for b in py_list:
                if b not in combined:
                    combined.append(b)
            return combined

        found_aq = merge_brands(ai_markak.get("aquashop",[]), found_in_text["aquashop"])
        found_al = merge_brands(ai_markak.get("aqualing",[]), found_in_text["aqualing"])
        found_fl = merge_brands(ai_markak.get("fluidra",[]), found_in_text["fluidra"])
        found_neu = ai_markak.get("egyeb", [])

        st.write(f"✓ Talált márkák – Aquashop: {len(found_aq)} | Aqualing: {len(found_al)} | Fluidra: {len(found_fl)}")

        # Exkluzív termékek pontja Python számolja
        aq_score = 0 if len(found_aq)==0 else 10 if len(found_aq)<=2 else 20 if len(found_aq)<=4 else 30 if len(found_aq)<=7 else 40
        scores = ai_data.get("scores", {})
        scores["exkluziv_termekek"] = aq_score

        calc_total = sum(int(v) for v in scores.values())
        if calc_total >= 85:   tier_key = "PLATINUM"
        elif calc_total >= 65: tier_key = "GOLD"
        elif calc_total >= 40: tier_key = "SILVER"
        elif calc_total >= 20: tier_key = "BASIC"
        else:                  tier_key = "INAKTÍV"

        result = {
            "domain": domain,
            "partner_neve": ai_data.get("partner_neve", domain),
            "osszefoglalo": ai_data.get("osszefoglalo",""),
            "scores": scores,
            "total": min(100, calc_total),
            "tier": tier_key,
            "markak": {"aquashop": found_aq, "aqualing": found_al,
                       "fluidra": found_fl, "egyeb": found_neu},
            "markaok_szama": {"aquashop": len(found_aq), "aqualing": len(found_al),
                              "fluidra": len(found_fl), "egyeb": len(found_neu)},
            "bizonyitekok": ai_data.get("bizonyitekok",{}),
            "javasolt_teendok": ai_data.get("javasolt_teendok",""),
        }
        status.update(label="✅ Elemzés kész!", state="complete")

    # ── Eredmény megjelenítése ────────────────────────────────────────
    total = result["total"]
    tier = TIER_CONFIG.get(result["tier"], TIER_CONFIG["INAKTÍV"])

    st.markdown(f"""<div class="score-hero">
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
        <div class="score-big">{total}</div>
        <div>
          <div class="tier-badge" style="color:{tier['color']}">{tier['emoji']} {tier['label']}</div>
          <div style="font-size:12px;color:#7a9fc0;font-family:monospace">{result['partner_neve']} · {domain}</div>
          <div style="font-size:13px;color:#c8d8f0;margin-top:6px;max-width:480px">{result['osszefoglalo']}</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # Márka arány
    st.markdown('<div class="section-label">▸ Márkaösszetétel & versenytárs arány</div>', unsafe_allow_html=True)
    mc = result["markaok_szama"]
    aq=mc["aquashop"]; al=mc["aqualing"]; fl=mc["fluidra"]; neu=mc["egyeb"]
    tb=max(aq+al+fl+neu,1)
    aq_pct=round(aq/tb*100); al_pct=round(al/tb*100); fl_pct=round(fl/tb*100); neu_pct=100-aq_pct-al_pct-fl_pct

    def seg(pct,cls):
        if pct<=0: return ''
        return f'<div class="seg {cls}" style="width:{pct}%">{""+str(pct)+"%" if pct>7 else ""}</div>'

    st.markdown(f"""<div class="ratio-bar-container">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:10px;font-size:13px">
        <span style="color:#5ee8ff;font-weight:700">Aquashop {aq_pct}% ({aq})</span>
        <span style="color:#fdd835;font-weight:700">Aqualing {al_pct}% ({al})</span>
        <span style="color:#ff8c5a;font-weight:700">Fluidra-Kerex {fl_pct}% ({fl})</span>
        <span style="color:#b4c8e6;font-weight:700">Egyéb {neu_pct}% ({neu})</span>
      </div>
      <div class="ratio-bar">{seg(aq_pct,'seg-aq')}{seg(al_pct,'seg-al')}{seg(fl_pct,'seg-fl')}{seg(neu_pct,'seg-neu')}</div>
    </div>""", unsafe_allow_html=True)

    chips=""
    for src,cls in [("aquashop","chip-aq"),("aqualing","chip-al"),("fluidra","chip-fl"),("egyeb","chip-neu")]:
        for b in result["markak"].get(src,[]):
            chips+=f'<span class="brand-chip {cls}">{b}</span>'
    if chips:
        st.markdown(f'<div style="margin:10px 0"><div style="font-size:11px;color:#7a9fc0;margin-bottom:6px;letter-spacing:1px">AZONOSÍTOTT MÁRKÁK</div>{chips}</div>', unsafe_allow_html=True)

    # Dimenzió bontás
    st.markdown('<div class="section-label">▸ Dimenzió bontás</div>', unsafe_allow_html=True)
    for key,label,max_pts in DIM_DEFS:
        pts=int(result["scores"].get(key,0))
        c1,c2=st.columns([4,1])
        with c1:
            st.markdown(f"<div style='font-size:13px;color:#e0eeff;margin-bottom:4px;font-weight:500'>{label}</div>", unsafe_allow_html=True)
            st.progress(pts/max_pts)
        with c2:
            color="#00d4ff" if pts>0 else "#666"
            st.markdown(f"<div style='font-size:14px;font-weight:700;color:{color};text-align:right;padding-top:4px'>{pts}/{max_pts}</div>", unsafe_allow_html=True)

    # Bizonyítékok
    biz=result.get("bizonyitekok",{})
    if any(biz.values()):
        st.markdown('<div class="section-label">▸ Elemzési bizonyítékok</div>', unsafe_allow_html=True)
        items=[("Talált termékek",biz.get("talalt_termekek","")),("Kínálat szélessége",biz.get("kinalat_szelessege","")),
               ("Tartalom minősége",biz.get("tartalom_minosege","")),("Aktivitás & frissesség",biz.get("aktivitas_frissesseg",""))]
        c1,c2=st.columns(2)
        for i,(t,v) in enumerate(items):
            if v:
                with (c1 if i%2==0 else c2):
                    st.markdown(f'<div class="ev-card"><div class="ev-title">{t}</div><div style="font-size:12px;color:#e0eeff;line-height:1.6">{v}</div></div>', unsafe_allow_html=True)

    # Javaslatok
    st.markdown('<div class="section-label">▸ Javasolt teendők</div>', unsafe_allow_html=True)
    jav=result.get("javasolt_teendok","")
    if jav and not jav.strip().startswith(("{","```")):
        st.markdown(f'<div class="rec-box"><div style="font-size:13px;color:#e0eeff;line-height:1.8">{jav.replace(chr(10),"<br>")}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="rec-box"><div style="color:#7a9fc0">Nem érkezett javaslat.</div></div>', unsafe_allow_html=True)

    # History
    st.session_state.history.insert(0,{"domain":domain,"partner":result["partner_neve"],
        "total":total,"tier":result["tier"],"aq_pct":aq_pct,
        "date":datetime.now().strftime("%Y.%m.%d"),"result":result})

# ── Előzmények ───────────────────────────────────────────────────────
if st.session_state.history:
    st.markdown('<div class="section-label">▸ Korábbi értékelések</div>', unsafe_allow_html=True)
    colors={"PLATINUM":"#00d4ff","GOLD":"#f5c842","SILVER":"#8fa8c8","BASIC":"#ff8c38","INAKTÍV":"#ff4455"}
    for h in st.session_state.history[:10]:
        c1,c2,c3,c4=st.columns([3,1,1,1])
        with c1: st.markdown(f"<span style='font-size:13px;color:#c8d8f0'>{h['partner']} · {h['domain']}</span>", unsafe_allow_html=True)
        with c2: st.markdown(f"<span style='color:#5ee8ff;font-size:12px'>AQ: {h['aq_pct']}%</span>", unsafe_allow_html=True)
        with c3:
            tier_color = colors.get(h["tier"], "#fff")
            st.markdown(f"<span style='color:{tier_color};font-weight:700'>{h['total']} pt</span>", unsafe_allow_html=True)
        with c4: st.markdown(f"<span style='color:#7a9fc0;font-size:11px'>{h['date']}</span>", unsafe_allow_html=True)
