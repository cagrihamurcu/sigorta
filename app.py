import streamlit as st
import numpy as np
import pandas as pd
from typing import Optional

st.set_page_config(page_title="Sigorta Temel Mantık Simülasyonu (Eğitici + Koç)", layout="wide")

# =============================
# Yardımcılar
# =============================
def fmt_tl(x: float) -> str:
    return f"{x:,.0f} TL"

def fmt_pct(x: float) -> str:
    return f"{x*100:.1f}%"

def simulate_period(n_policies: int, p_claim: float, mean_loss: float, seed: Optional[int] = None):
    rng = np.random.default_rng(seed)
    claim_occurs = rng.random(n_policies) < p_claim
    n_claims = int(claim_occurs.sum())
    losses = rng.exponential(scale=mean_loss, size=n_claims) if n_claims > 0 else np.array([])
    return n_claims, float(losses.sum())

def demand_from_premium(premium: float, base_policies: int, reference_premium: float, sensitivity: float):
    ratio = premium / reference_premium if reference_premium > 0 else 1.0
    demand_factor = np.exp(-sensitivity * (ratio - 1.0))
    return max(0, int(round(base_policies * demand_factor)))

def compute_last_insights(df: pd.DataFrame, suggested_gross: float, premium_choice: float):
    last = df.iloc[-1].to_dict()

    premium_income = float(last["Prim Geliri"])
    cr = float(last["Combined Ratio"])
    n_pol = int(last["Poliçe"])

    base_market = int(last.get("Referans Satış (poliçe)", 0)) or 1
    demand_ratio = n_pol / base_market

    price_gap = premium_choice / max(1.0, suggested_gross)  # >1 pahalı, <1 ucuz

    diagnosis, actions, roadmap = [], [], []

    # CR yorumu
    if premium_income == 0:
        diagnosis.append("Talep neredeyse sıfır: fiyat/prim çok yüksek olduğu için poliçe gelmedi.")
        actions.append("Prim düzeyini düşür (ör. önerilen brüt primin %90–%110 bandına gel).")
    else:
        if cr < 1.0:
            diagnosis.append(f"Bu fiyatlama döneminde **teknik kâr** var: Combined Ratio = {cr:.2f} (< 1).")
            actions.append("Fiyatı koru veya kontrollü büyüme için çok küçük indirim dene (örn. -%5).")
        elif 1.0 <= cr < 1.10:
            diagnosis.append(f"Bu dönemde **hafif teknik zarar**: Combined Ratio = {cr:.2f} (1’e yakın).")
            actions.append("Prim düzeyini bir kademe artır (örn. +%5–%10) veya gider oranını azaltmayı dene.")
        else:
            diagnosis.append(f"Bu dönemde **belirgin teknik zarar**: Combined Ratio = {cr:.2f} (>> 1).")
            actions.append("Prim düzeyini artır (+%10–%20) ve portföy/risk seçimini (risk senaryosu) gözden geçir.")

    # Prim seviyesi yorumu
    if price_gap < 0.9:
        diagnosis.append("Prim, önerilen brüt primin belirgin altında: talep artabilir ama prim yetersizliği sermayeyi eritebilir.")
        actions.append("CR>1 ise önce prim seviyesini önerilen banda yaklaştır.")
    elif price_gap > 1.1:
        diagnosis.append("Prim, önerilen brüt primin üstünde: zarar riski azalabilir ama rekabetçi talep düşebilir.")
        actions.append("Talep çok düştüyse prim seviyesini biraz geri çek (örn. -%5).")
    else:
        diagnosis.append("Prim, önerilen brüt prime yakın: fiyatlama açısından dengeli bir bölgede deneme yapıyorsun.")

    # Talep yorumu
    if demand_ratio < 0.6:
        diagnosis.append("Talep zayıf (satış düşük): ya fiyat pahalı kaldı ya da piyasa fiyata çok hassas.")
        actions.append("Talebi artırmak için prim düzeyini düşür veya fiyata duyarlılığı azalt (piyasa daha az hassas varsayımı).")
    elif demand_ratio > 1.2:
        diagnosis.append("Talep güçlü (satış yüksek): genişleyen risk havuzu sonuçları beklenene yaklaştırma eğilimindedir.")
        actions.append("CR kötü ise satış artışı zararı büyütebilir → prim artır. CR iyi ise büyümeyi sürdür.")

    # Yol haritası
    roadmap.append("1) Öncelik: Combined Ratio’yu 1’in altına çek (kârlılık).")
    roadmap.append("2) Sonra: CR<1 olduktan sonra küçük fiyat indirimleriyle talebi test et (kontrollü).")
    roadmap.append("3) Piyasa çok hassassa: küçük prim artışı satışları hızla düşürür; ayarı küçük adımlarla yap.")
    roadmap.append("4) Risk seçimi: ‘yüksek riskli portföy’ (Daha Riskli) seçildiyse, fiyatın da buna uygun yükselmesi gerekir.")

    return diagnosis, actions, roadmap

# =============================
# State
# =============================
def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 0  # 0 intro, 1-5

    if "quiz_ok" not in st.session_state:
        st.session_state.quiz_ok = {"intro": False, 1: False, 2: False, 3: False, 4: False}

    if "quiz_submitted" not in st.session_state:
        st.session_state.quiz_submitted = {"intro": False, 1: False, 2: False, 3: False, 4: False}

    if "capital0" not in st.session_state:
        st.session_state.capital0 = 1_000_000.0
        st.session_state.capital = st.session_state.capital0

    if "period" not in st.session_state:
        st.session_state.period = 0  # fiyatlama dönemi sayacı

    if "history" not in st.session_state:
        st.session_state.history = []

    # kararlar
    if "scenario" not in st.session_state:
        st.session_state.scenario = "Dengeli Piyasa"
    if "expense_loading" not in st.session_state:
        st.session_state.expense_loading = 0.20
    if "profit_loading" not in st.session_state:
        st.session_state.profit_loading = 0.10
    if "premium_factor" not in st.session_state:
        st.session_state.premium_factor = 100
    if "base_policies" not in st.session_state:
        st.session_state.base_policies = 2000
    if "sensitivity" not in st.session_state:
        st.session_state.sensitivity = 1.2
    if "seed" not in st.session_state:
        st.session_state.seed = 0
    if "last_commentary" not in st.session_state:
        st.session_state.last_commentary = ""

init_state()

# =============================
# Risk senaryoları (piyasa dinamiklerine göre)
# =============================
SCENARIOS = {
    "Korunaklı Piyasa (Seçici Portföy)": {
        "p_claim": 0.05,
        "mean_loss": 20_000,
        "label": "Seçici underwriting / daha iyi risk seçimi",
        "market_logic": (
            "• Risk seçimi sıkı, poliçe kabul kriterleri güçlü\n"
            "• Daha düşük hasar frekansı ve/veya daha düşük hasar şiddeti\n"
            "• Genelde: yüksek rekabet baskısı olmayan veya güçlü risk seçimi olan yapılar"
        )
    },
    "Dengeli Piyasa": {
        "p_claim": 0.08,
        "mean_loss": 25_000,
        "label": "Ortalama portföy / tipik piyasa dengesi",
        "market_logic": (
            "• Standart underwriting, portföy karışık\n"
            "• Ortalama risk profili\n"
            "• Genelde: fiyat–talep–kârlılık dengesini en iyi gösteren referans durum"
        )
    },
    "Zorlu Piyasa (Adverse Selection Riski)": {
        "p_claim": 0.12,
        "mean_loss": 32_000,
        "label": "Daha riskli portföy / adverse selection olasılığı yüksek",
        "market_logic": (
            "• Rekabet yüksek, fiyat kırma eğilimi var\n"
            "• Daha riskli müşteri profili şirkete gelebilir (adverse selection)\n"
            "• Hasarlar daha sık ve/veya daha yüksek olabilir → fiyatlama disiplinine ihtiyaç artar"
        )
    },
}

# =============================
# Navigation (on_click yok)
# =============================
def go_next():
    if st.session_state.step == 0:
        st.session_state.step = 1
    else:
        st.session_state.step = min(5, st.session_state.step + 1)

def go_prev():
    if st.session_state.step == 1:
        st.session_state.step = 0
    else:
        st.session_state.step = max(0, st.session_state.step - 1)

def hard_reset():
    st.session_state.step = 0
    st.session_state.period = 0
    st.session_state.capital = st.session_state.capital0
    st.session_state.history = []
    st.session_state.last_commentary = ""
    st.session_state.quiz_ok = {"intro": False, 1: False, 2: False, 3: False, 4: False}
    st.session_state.quiz_submitted = {"intro": False, 1: False, 2: False, 3: False, 4: False}

# =============================
# Üst hesaplar
# =============================
p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]

expected_loss_per_policy = p_claim * mean_loss
suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)
premium_choice = suggested_gross * (st.session_state.premium_factor / 100.0)

# =============================
# Başlık + pano
# =============================
st.title("📊 Sigortacılığın Temel Mantığı — Fiyatlama Simülasyonu (Eğitici + Koç)")
st.caption("Amaç: Her fiyatlama döneminde prim–talep–hasar–gider dengesini görerek sermayeyi korumak ve geliştirmek.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Fiyatlama Dönemi", f"{st.session_state.period} / 12")
c2.metric("Sermaye", fmt_tl(st.session_state.capital))
c3.metric("Önerilen brüt prim", fmt_tl(suggested_gross))
c4.metric("Seçilen prim", fmt_tl(premium_choice))

# =============================
# Sidebar
# =============================
with st.sidebar:
    st.header("⚙️ Kontrol")
    if st.button("🔄 Baştan Başlat", use_container_width=True):
        hard_reset()
        st.rerun()

# =============================
# INTRO
# =============================
if st.session_state.step == 0:
    st.subheader("🚦 Başlangıç: 3 cümlede sistem")
    st.markdown(
        """
**1) Prim belirliyorsun (fiyatlama).**  
**2) Prim talebi etkiliyor (kaç poliçe satıldığı).**  
**3) Hasarlar ve giderler oluşuyor → sonuç sermayeye yansıyor.**

### “Beklenen hasar/poliçe” çok net ne demek?
Bir poliçenin, bir fiyatlama döneminde ortalama ne kadar hasar maliyeti üretmesini **beklediğimiz** değerdir.  
Basitçe:
- Hasar olma ihtimali **p**
- Hasar olursa ortalama tutar **ortalama hasar**
- **Beklenen hasar/poliçe = p × ortalama hasar**

Örnek: p=0.10 ve ortalama hasar=10.000 TL ise → beklenen hasar/poliçe = 1.000 TL.
        """
    )

    st.divider()
    st.write("✅ Mini Soru (cevabı gönderince değerlendirilir):")
    ans = st.radio(
        "Beklenen hasar/poliçe hangi iki şeyin çarpımıdır?",
        ["ortalama hasar × gider", "hasar olasılığı (p) × ortalama hasar", "prim × poliçe sayısı"],
        index=0,
        key="q_intro"
    )

    if st.button("Cevabı Gönder", use_container_width=True):
        st.session_state.quiz_submitted["intro"] = True
        st.session_state.quiz_ok["intro"] = (ans == "hasar olasılığı (p) × ortalama hasar")
        st.rerun()

    if st.session_state.quiz_submitted["intro"]:
        if st.session_state.quiz_ok["intro"]:
            st.success("Doğru.")
        else:
            st.warning("Yanlış. İpucu: p hasar olasılığıdır; beklenen hasar = p × ortalama hasar.")

    if st.button("İleri ➜", disabled=not st.session_state.quiz_ok["intro"], use_container_width=True):
        go_next()
        st.rerun()

# =============================
# Wizard başlıkları
# =============================
steps_title = {
    1: "1) Piyasa/Risk Profili Seçimi",
    2: "2) Prim Bileşenleri (Teknik + Gider + Tampon)",
    3: "3) Prim Düzeyi (Fiyatlama Kararı)",
    4: "4) Piyasa Talebi Varsayımı",
    5: "5) Özet & Simülasyon",
}
if st.session_state.step in [1, 2, 3, 4, 5]:
    st.subheader(f"🧭 {steps_title[st.session_state.step]}")
    st.progress(st.session_state.step / 5)

# =============================
# 1) Risk senaryosu: piyasa dinamiklerine göre
# =============================
if st.session_state.step == 1:
    st.markdown(
        """
### Bu adım neyi temsil ediyor?
Burada seçtiğin seçenek “oyuncu deneyimi” değil, **piyasadaki portföy/risk profilini** temsil eder:
- Underwriting seçiciliği
- Rekabet baskısı
- Adverse selection riski

Seçim, hasar olasılığını (p) ve ortalama hasar tutarını değiştirir.
        """
    )

    scenario = st.radio(
        "Piyasa/Risk profili seç",
        list(SCENARIOS.keys()),
        index=list(SCENARIOS.keys()).index(st.session_state.scenario),
        horizontal=True,
        key="scenario_pick"
    )
    st.session_state.scenario = scenario

    p_claim = SCENARIOS[scenario]["p_claim"]
    mean_loss = SCENARIOS[scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss

    st.success(f"**Seçilen profil:** {SCENARIOS[scenario]['label']}")
    st.info(SCENARIOS[scenario]["market_logic"])

    st.markdown(
        f"""
**Bu profilde sayılar:**  
- Hasar olasılığı (p) = **{p_claim:.2f}**  
- Ortalama hasar = **{fmt_tl(mean_loss)}**  
- Beklenen hasar/poliçe = **{fmt_tl(expected_loss_per_policy)}**
        """
    )

    st.divider()
    st.write("✅ Mini Soru (cevabı gönderince değerlendirilir):")
    ans = st.radio(
        "Riskli portföy/profil seçilirse (p ve/veya ortalama hasar artarsa) teknik prim ne olur?",
        ["Azalır", "Artar", "Değişmez"],
        index=0,
        key="q1"
    )

    if st.button("Cevabı Gönder", use_container_width=True):
        st.session_state.quiz_submitted[1] = True
        st.session_state.quiz_ok[1] = (ans == "Artar")
        st.rerun()

    if st.session_state.quiz_submitted[1]:
        if st.session_state.quiz_ok[1]:
            st.success("Doğru: Teknik prim (risk maliyeti) beklenen hasarla birlikte artar.")
        else:
            st.warning("Yanlış. İpucu: Teknik prim = beklenen hasar/poliçe.")

    b1, b2 = st.columns(2)
    if b1.button("⬅ Geri", use_container_width=True):
        go_prev(); st.rerun()
    if b2.button("İleri ➜", disabled=not st.session_state.quiz_ok[1], use_container_width=True):
        go_next(); st.rerun()

# =============================
# 2) Teknik prim / gider / tampon (daha sade ve net)
# =============================
elif st.session_state.step == 2:
    st.markdown(
        """
### Prim neden sadece “hasar” değil?
**Teknik prim (risk maliyeti)**: Hasarları ödemek için gereken ortalama tutar  
- Teknik prim = **beklenen hasar/poliçe**

**Gider yüklemesi**: Şirketin poliçe üretmek ve işletmek için yaptığı masraflar  
- Komisyon, personel, operasyon, IT vb.

**Belirsizlik tamponu (güvenlik/kâr payı)**: “Beklenenden kötü” bir dönem olursa ayakta kalmak için pay  
- Hasarlar bazen beklenenden yüksek gelir → tampon bu şoku karşılamak içindir.

> Bu üçünün toplamı **brüt prim** fikrini verir.
        """
    )

    st.session_state.expense_loading = st.slider("Gider oranı (%)", 0, 50, int(st.session_state.expense_loading * 100), 1) / 100
    st.session_state.profit_loading = st.slider("Belirsizlik tamponu / güvenlik–kâr (%)", 0, 50, int(st.session_state.profit_loading * 100), 1) / 100

    # güncelle
    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)

    st.success(
        f"Teknik prim (beklenen hasar/poliçe): **{fmt_tl(expected_loss_per_policy)}**\n\n"
        f"Gider oranı: **{fmt_pct(st.session_state.expense_loading)}**\n"
        f"Tampon/Kâr oranı: **{fmt_pct(st.session_state.profit_loading)}**\n\n"
        f"→ Önerilen brüt prim/poliçe: **{fmt_tl(suggested_gross)}**"
    )

    st.divider()
    st.write("✅ Mini Soru (cevabı gönderince değerlendirilir):")
    ans = st.radio(
        "Gider oranı artarsa önerilen brüt prim ne olur?",
        ["Azalır", "Artar", "Değişmez"],
        index=0,
        key="q2"
    )

    if st.button("Cevabı Gönder", use_container_width=True):
        st.session_state.quiz_submitted[2] = True
        st.session_state.quiz_ok[2] = (ans == "Artar")
        st.rerun()

    if st.session_state.quiz_submitted[2]:
        if st.session_state.quiz_ok[2]:
            st.success("Doğru: Gider oranı artarsa brüt prim artar.")
        else:
            st.warning("Yanlış. İpucu: Brüt prim = teknik prim + (gider + tampon).")

    b1, b2 = st.columns(2)
    if b1.button("⬅ Geri", use_container_width=True):
        go_prev(); st.rerun()
    if b2.button("İleri ➜", disabled=not st.session_state.quiz_ok[2], use_container_width=True):
        go_next(); st.rerun()

# =============================
# 3) Prim düzeyi
# =============================
elif st.session_state.step == 3:
    st.markdown(
        """
### Fiyatlama kararı (prim düzeyi)
Önerilen brüt prim “referans”tır. Sen bunun üstünde/altında fiyatlayabilirsin.

- Çok düşük prim → satış artabilir ama teknik zarar riski yükselir
- Çok yüksek prim → zarar riski azalabilir ama rekabetçi satış düşebilir
        """
    )

    st.session_state.premium_factor = st.slider("Prim düzeyi (önerilen brüt primin %’si)", 60, 160, int(st.session_state.premium_factor), 5)

    # güncelle
    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)
    premium_choice = suggested_gross * (st.session_state.premium_factor / 100.0)

    if st.session_state.premium_factor < 90:
        st.warning(f"Seçim: **agresif fiyat (ucuz)** → {fmt_tl(premium_choice)} (talep artabilir, zarar riski artar)")
    elif st.session_state.premium_factor > 110:
        st.info(f"Seçim: **korumacı fiyat (pahalı)** → {fmt_tl(premium_choice)} (zarar riski azalabilir, talep düşebilir)")
    else:
        st.success(f"Seçim: **denge bandı** → {fmt_tl(premium_choice)}")

    st.divider()
    st.write("✅ Mini Soru (cevabı gönderince değerlendirilir):")
    ans = st.radio(
        "Prim çok düşerse en olası etki hangisidir?",
        ["Satış artar ama zarar riski artar", "Satış azalır ve zarar riski azalır", "Hiçbir şey değişmez"],
        index=0,
        key="q3"
    )

    if st.button("Cevabı Gönder", use_container_width=True):
        st.session_state.quiz_submitted[3] = True
        st.session_state.quiz_ok[3] = (ans == "Satış artar ama zarar riski artar")
        st.rerun()

    if st.session_state.quiz_submitted[3]:
        if st.session_state.quiz_ok[3]:
            st.success("Doğru.")
        else:
            st.warning("Yanlış. İpucu: fiyat ↓ → satış ↑ olabilir ama prim yetersiz kalabilir.")

    b1, b2 = st.columns(2)
    if b1.button("⬅ Geri", use_container_width=True):
        go_prev(); st.rerun()
    if b2.button("İleri ➜", disabled=not st.session_state.quiz_ok[3], use_container_width=True):
        go_next(); st.rerun()

# =============================
# 4) Talep varsayımı (referans satış hacmi daha açık)
# =============================
elif st.session_state.step == 4:
    st.markdown(
        """
### Talep (satış) varsayımı
Burada “piyasanın büyüklüğünü” daha açık şekilde tanımlıyoruz:

**Referans satış hacmi (rekabetçi fiyatla beklenen poliçe adedi)**  
- Prim “makul/rekabetçi” ise, yaklaşık kaç poliçe satılmasını beklersin?

**Fiyata duyarlılık**  
- Prim biraz artınca satışlar ne kadar hızlı düşer?
        """
    )

    st.session_state.base_policies = st.slider(
        "Referans satış hacmi (rekabetçi fiyatla beklenen poliçe adedi)",
        200, 10000, int(st.session_state.base_policies), 100
    )
    st.session_state.sensitivity = st.slider("Fiyata duyarlılık (0–3)", 0.0, 3.0, float(st.session_state.sensitivity), 0.1)

    n_est = demand_from_premium(
        premium=premium_choice,
        base_policies=st.session_state.base_policies,
        reference_premium=suggested_gross if suggested_gross > 0 else 1.0,
        sensitivity=st.session_state.sensitivity
    )
    st.info(f"Bu prim düzeyinde tahmini satış (poliçe): **{n_est:,}**")

    st.divider()
    st.write("✅ Mini Soru (cevabı gönderince değerlendirilir):")
    ans = st.radio(
        "Fiyata duyarlılık çok yüksekse (3), prim artınca ne olur?",
        ["Satış daha hızlı düşer", "Satış artar", "Satış değişmez"],
        index=0,
        key="q4"
    )

    if st.button("Cevabı Gönder", use_container_width=True):
        st.session_state.quiz_submitted[4] = True
        st.session_state.quiz_ok[4] = (ans == "Satış daha hızlı düşer")
        st.rerun()

    if st.session_state.quiz_submitted[4]:
        if st.session_state.quiz_ok[4]:
            st.success("Doğru.")
        else:
            st.warning("Yanlış. İpucu: duyarlılık ↑ → fiyat artışına tepki ↑")

    b1, b2 = st.columns(2)
    if b1.button("⬅ Geri", use_container_width=True):
        go_prev(); st.rerun()
    if b2.button("İleri ➜", disabled=not st.session_state.quiz_ok[4], use_container_width=True):
        go_next(); st.rerun()

# =============================
# 5) Özet & Simülasyon
# =============================
elif st.session_state.step == 5:
    st.markdown(
        """
Seçimlerini kontrol et ve **bu fiyatla piyasaya çık**:  
(1 fiyatlama dönemi simüle edilir: satış → hasar → gider → sermaye)
        """
    )

    st.session_state.seed = int(st.number_input("Rastgelelik (seed) (opsiyonel)", min_value=0, value=int(st.session_state.seed), step=1))

    summary = {
        "Piyasa/Risk profili": st.session_state.scenario,
        "p": p_claim,
        "Ortalama hasar": fmt_tl(mean_loss),
        "Beklenen hasar/poliçe": fmt_tl(expected_loss_per_policy),
        "Gider oranı": fmt_pct(st.session_state.expense_loading),
        "Tampon/Kâr oranı": fmt_pct(st.session_state.profit_loading),
        "Önerilen brüt prim": fmt_tl(suggested_gross),
        "Seçilen prim": fmt_tl(premium_choice),
        "Referans satış (poliçe)": f"{st.session_state.base_policies:,}",
        "Fiyata duyarlılık": st.session_state.sensitivity,
    }
    st.dataframe(pd.DataFrame([summary]), use_container_width=True)

    b1, b2 = st.columns(2)
    if b1.button("⬅ Geri", use_container_width=True):
        go_prev(); st.rerun()

    def simulate_one_pricing_period():
        n_policies = demand_from_premium(
            premium=premium_choice,
            base_policies=st.session_state.base_policies,
            reference_premium=suggested_gross if suggested_gross > 0 else 1.0,
            sensitivity=st.session_state.sensitivity
        )

        st.session_state.period += 1
        n_claims, total_loss = simulate_period(
            n_policies=n_policies,
            p_claim=p_claim,
            mean_loss=mean_loss,
            seed=(st.session_state.seed + st.session_state.period) if st.session_state.seed != 0 else None
        )

        premium_income = float(n_policies) * float(premium_choice)
        expense = premium_income * st.session_state.expense_loading
        uw_result = premium_income - total_loss - expense
        st.session_state.capital += uw_result
        combined_ratio = (total_loss + expense) / premium_income if premium_income > 0 else 0.0

        if premium_income == 0:
            comment = "Satış yok: prim çok yüksek → rekabetçi talep sıfırlandı. (Fiyatı düşürmeyi dene.)"
        else:
            if combined_ratio < 1.0:
                comment = "✅ Teknik kâr: Combined Ratio < 1. (Prim/hasar/gider dengesi iyi.)"
            else:
                comment = "⚠️ Teknik zarar: Combined Ratio > 1. (Prim yetersiz kaldı veya hasar şoku yüksek.)"

        st.session_state.last_commentary = comment

        st.session_state.history.append({
            "Fiyatlama Dönemi": st.session_state.period,
            "Poliçe": n_policies,
            "Referans Satış (poliçe)": st.session_state.base_policies,
            "Prim/poliçe": premium_choice,
            "Prim Geliri": premium_income,
            "Hasar Adedi": n_claims,
            "Toplam Hasar": total_loss,
            "Gider": expense,
            "UW Sonucu": uw_result,
            "Combined Ratio": combined_ratio,
            "Sermaye": st.session_state.capital
        })

    if b2.button("📣 Bu fiyatla piyasaya çık (1 dönem simüle et)", use_container_width=True):
        simulate_one_pricing_period()
        st.rerun()

# =============================
# Sonuçlar + Koç
# =============================
st.divider()

if st.session_state.last_commentary:
    st.success(st.session_state.last_commentary)

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)

    with st.expander("📘 Sonuç tablosundaki kalemler (kısa açıklama)", expanded=False):
        st.markdown(
            """
- **Poliçe:** Bu fiyatla gerçekleşen satış (satılan poliçe adedi).  
- **Referans Satış (poliçe):** Fiyat rekabetçi olsaydı beklenen satış hacmi (piyasa varsayımı).  
- **Prim/poliçe:** Uygulanan satış primi.  
- **Prim Geliri:** Poliçe × Prim/poliçe.  
- **Hasar Adedi / Toplam Hasar:** Gerçekleşen hasar sayısı ve toplam tutar (rastgele).  
- **Gider:** Prim gelirinin gider oranı kadar kısmı (işletme maliyeti).  
- **UW Sonucu:** Prim Geliri − Toplam Hasar − Gider. (+) kâr, (−) zarar.  
- **Combined Ratio:** (Toplam Hasar + Gider) / Prim Geliri. **<1 kâr**, **>1 zarar**.  
- **Sermaye:** Birikimli sonuç (şirketin tampon gücü).
            """
        )

    st.subheader("📊 Sonuç Tablosu")
    st.dataframe(df, use_container_width=True)

    st.subheader("📈 Trendler")
    st.line_chart(df.set_index("Fiyatlama Dönemi")[["Prim Geliri", "Toplam Hasar"]])
    st.line_chart(df.set_index("Fiyatlama Dönemi")[["Combined Ratio"]])
    st.line_chart(df.set_index("Fiyatlama Dönemi")[["Sermaye"]])

    st.subheader("🧠 Koç: Bu dönem ne oldu, bir sonraki adım ne olmalı?")
    diagnosis, actions, roadmap = compute_last_insights(df, suggested_gross, premium_choice)

    cl, cr = st.columns([1, 1])
    with cl:
        st.markdown("### 📌 Yorum")
        for d in diagnosis:
            st.write("•", d)
    with cr:
        st.markdown("### ✅ Öneri")
        for a in actions[:10]:
            st.write("•", a)

    st.markdown("### 🧭 Yol haritası (strateji için)")
    for r in roadmap:
        st.write("•", r)

    if st.session_state.period >= 12:
        if st.session_state.capital > st.session_state.capital0:
            st.balloons()
            st.success("🎉 12 fiyatlama dönemi bitti: Sermayeyi büyüttün!")
        else:
            st.error("12 fiyatlama dönemi bitti: Sermaye düştü. (Ders: fiyatlama + belirsizlik + talep dengesi)")
else:
    st.info("Adım adım ilerle: her adımda açıklama var. Mini soruda ‘Cevabı Gönder’ deyip doğrulamayı görerek devam edebilirsin.")
