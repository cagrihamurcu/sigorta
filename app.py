import streamlit as st
import numpy as np
import pandas as pd
from typing import Optional

st.set_page_config(page_title="Sigorta Temel Mantık Oyunu (Eğitici + Koç)", layout="wide")

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

def compute_last_insights(df: pd.DataFrame, suggested_gross: float, premium_choice: float, premium_factor: int):
    """Son dönemi okuyup öğrenciye net öneriler döndürür."""
    last = df.iloc[-1].to_dict()

    premium_income = float(last["Prim Geliri"])
    claims = float(last["Toplam Hasar"])
    expense = float(last["Gider"])
    uw = float(last["UW Sonucu"])
    cr = float(last["Combined Ratio"])
    n_pol = int(last["Poliçe"])
    cap = float(last["Sermaye"])

    # Basit eşikler
    demand_ratio = n_pol / max(1, int(last["Pazar (referans)"]))
    price_gap = premium_choice / max(1.0, suggested_gross)  # >1 pahalı, <1 ucuz

    # Yorum blokları
    diagnosis = []
    actions = []
    roadmap = []

    # 1) CR yorumu
    if premium_income == 0:
        diagnosis.append("Talep neredeyse sıfır: prim çok yüksek olduğu için poliçe gelmedi.")
        actions.append("Prim düzeyini düşür (ör. önerilen brüt primin %90–%110 bandına gel).")
        actions.append("Fiyata duyarlılık yüksekse (2+), prim artışı talebi çok hızlı düşürür.")
    else:
        if cr < 1.0:
            diagnosis.append(f"Bu tur **teknik kâr** var: Combined Ratio = {cr:.2f} (< 1).")
            actions.append("Stratejiyi koru veya çok hafif ucuzlayarak (örn. -%5) büyümeyi test et.")
        elif 1.0 <= cr < 1.10:
            diagnosis.append(f"Bu tur **hafif teknik zarar**: Combined Ratio = {cr:.2f} (1’e yakın).")
            actions.append("Prim düzeyini bir kademe artır (örn. +%5–%10) veya gider yüklemesini azaltmayı dene.")
        else:
            diagnosis.append(f"Bu tur **belirgin teknik zarar**: Combined Ratio = {cr:.2f} (>> 1).")
            actions.append("Prim düzeyini artır (+%10–%20) VE/VEYA daha az riskli senaryoya geçmeyi dene (öğrenme için).")

    # 2) Prim seviyesi ve talep (piyasa) yorumu
    if price_gap < 0.9:
        diagnosis.append("Prim, önerilen brüt primin epey altında: müşteri artabilir ama hasar şoku sermayeyi eritebilir.")
        actions.append("Eğer CR>1 ise: önce prim seviyesini önerilen banda yaklaştır.")
    elif price_gap > 1.1:
        diagnosis.append("Prim, önerilen brüt primin üstünde: zarar riski azalır ama talep düşebilir.")
        actions.append("Talep çok düştüyse (poliçe az): prim seviyesini biraz geri çek (örn. -%5).")
    else:
        diagnosis.append("Prim, önerilen brüt prime yakın: fiyatlama açısından dengeli bir bölgede deneme yapıyorsun.")

    # 3) Talep yeterli mi?
    if demand_ratio < 0.6:
        diagnosis.append("Talep zayıf (poliçe az). Piyasa primine göre pahalı kalmış olabilirsin veya duyarlılık yüksek.")
        actions.append("Talebi artırmak için prim düzeyini düşür veya fiyata duyarlılığı azalt (piyasa daha az hassas).")
    elif demand_ratio > 1.2:
        diagnosis.append("Talep güçlü (poliçe yüksek). Havuz büyüdükçe sonuçlar beklenene yaklaşma eğilimindedir (risk havuzu etkisi).")
        actions.append("CR iyi ise büyümeyi sürdür; CR kötü ise talep artışı prim yetersizliğini büyütebilir (prim artır).")

    # 4) Sermaye trendi (basit)
    if len(df) >= 3:
        cap_change = df["Sermaye"].iloc[-1] - df["Sermaye"].iloc[-3]
        if cap_change < 0:
            roadmap.append("Son 3 dönemde sermaye düşüyor: önce **kârlılık stabilitesi** hedefle (CR<1).")
        else:
            roadmap.append("Son 3 dönemde sermaye artıyor: önce dengeyi koru, sonra kontrollü büyüme dene.")
    else:
        roadmap.append("Henüz az tur var: önce CR’yi 1’in altına çekmeye odaklan.")

    # Yol haritası: 3 adım
    roadmap.append("1) Risk: Senaryo ‘Daha Riskli’ ise öğrenme için önce ‘Normal’ ile denge kur, sonra riskliyi dene.")
    roadmap.append("2) Fiyat: Prim düzeyini %90–%110 bandında test et, CR’ye göre yukarı/aşağı ayarla.")
    roadmap.append("3) Piyasa: Duyarlılık yüksekse küçük fiyat artışı talebi hızlı düşürür; bunu bilerek hareket et.")

    return diagnosis, actions, roadmap


# =============================
# State
# =============================
def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 0  # 0 intro, 1-5 wizard

    if "quiz_ok" not in st.session_state:
        st.session_state.quiz_ok = {"intro": False, 1: False, 2: False, 3: False, 4: False}

    if "capital0" not in st.session_state:
        st.session_state.capital0 = 1_000_000.0
        st.session_state.capital = st.session_state.capital0

    if "t" not in st.session_state:
        st.session_state.t = 0

    if "history" not in st.session_state:
        st.session_state.history = []

    # seçimler
    if "scenario" not in st.session_state:
        st.session_state.scenario = "Normal"
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
# Senaryolar (risk tipi + rehber metin)
# =============================
SCENARIOS = {
    "Daha Az Riskli": {
        "p_claim": 0.05,
        "mean_loss": 20_000,
        "label": "Düşük frekans & daha düşük şiddet (daha stabil)",
        "when": "Yeni başlayanlar için dengeyi görmek ve prim mantığını hızlı kavramak için."
    },
    "Normal": {
        "p_claim": 0.08,
        "mean_loss": 25_000,
        "label": "Orta frekans & orta şiddet (referans)",
        "when": "Dersin temel modu: fiyatlama–talep–sonuç ilişkisini en gerçekçi şekilde görmek için."
    },
    "Daha Riskli": {
        "p_claim": 0.12,
        "mean_loss": 32_000,
        "label": "Yüksek frekans & daha yüksek şiddet (volatilite yüksek)",
        "when": "‘Prim yetersiz kalırsa sermaye nasıl erir?’ sorusunu göstermek için."
    },
}

p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
expected_loss_per_policy = p_claim * mean_loss
suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)
premium_choice = suggested_gross * (st.session_state.premium_factor / 100.0)

# =============================
# Başlık + üst pano
# =============================
st.title("🎮 Sigortacılığın Temel Mantığı (Adım Adım + Koç)")
st.caption("Amaç: 12 dönem sonunda sermayeyi korumak ve mümkünse artırmak. Mantık: Prim = beklenen hasar + gider + belirsizlik tamponu (güvenlik/kâr).")

colA, colB, colC, colD = st.columns(4)
colA.metric("Dönem", f"{st.session_state.t} / 12")
colB.metric("Sermaye", fmt_tl(st.session_state.capital))
colC.metric("Önerilen brüt prim", fmt_tl(suggested_gross))
colD.metric("Senin primin", fmt_tl(premium_choice))

# =============================
# Sidebar: reset
# =============================
with st.sidebar:
    st.header("⚙️ Oyun")
    if st.button("🔄 Baştan Başlat", use_container_width=True):
        st.session_state.step = 0
        st.session_state.t = 0
        st.session_state.capital = st.session_state.capital0
        st.session_state.history = []
        st.session_state.last_commentary = ""
        st.session_state.quiz_ok = {"intro": False, 1: False, 2: False, 3: False, 4: False}
        st.rerun()

# =============================
# Navigation
# =============================
def go_next():
    st.session_state.step = 1 if st.session_state.step == 0 else min(5, st.session_state.step + 1)

def go_prev():
    st.session_state.step = 0 if st.session_state.step == 1 else max(0, st.session_state.step - 1)

# =============================
# INTRO
# =============================
if st.session_state.step == 0:
    st.subheader("🚦 Başlangıç (çok kısa)")
    st.markdown(
        """
**Ne yapacaksın?** Her dönemde prim belirleyeceksin → prim talebi etkiler → hasarlar gelir → giderler düşülür → sermaye güncellenir.  
**Tek ana fikir:**  
- **Beklenen hasar/poliçe = p × ortalama hasar**  
- **Brüt prim = beklenen hasar + gider + belirsizlik tamponu (güvenlik/kâr payı)**

İlerlemek için 1 mini soru:
        """
    )
    ans = st.radio(
        "Beklenen hasar/poliçe hangi iki şeyin çarpımıdır?",
        ["ortalama hasar × gider", "hasar olasılığı (p) × ortalama hasar", "prim × poliçe sayısı"],
        index=0
    )
    ok = (ans == "hasar olasılığı (p) × ortalama hasar")
    st.session_state.quiz_ok["intro"] = ok
    st.success("Doğru!") if ok else st.warning("İpucu: p hasar olasılığıdır.")
    st.button("İleri ➜", on_click=go_next, disabled=not ok, use_container_width=True)

# =============================
# Wizard titles
# =============================
steps_title = {1:"1) Risk Senaryosu", 2:"2) Prim Bileşenleri", 3:"3) Prim Kararı", 4:"4) Piyasa (Talep)", 5:"5) Özet & Oynat"}
if st.session_state.step in [1,2,3,4,5]:
    st.subheader(f"🧭 {steps_title[st.session_state.step]}")
    st.progress(st.session_state.step/5)

# =============================
# 1) Risk (rehberli)
# =============================
if st.session_state.step == 1:
    st.markdown(
        """
### Bu adımda ne seçiyorsun?
**Risk tipi**, iki parçadan oluşur:
- **Hasar olasılığı (p)**: Dönemde hasar olur mu?
- **Ortalama hasar**: Hasar olursa ortalama ne kadar?

> Risk yükselirse beklenen hasar artar → **teknik prim** artmalıdır.
        """
    )

    st.info(
        "🧭 Seçim rehberi:  \n"
        "- İlk kez oynuyorsan: **Normal** (en öğretici denge)  \n"
        "- Mantığı hızla görmek istiyorsan: **Daha Az Riskli** (daha stabil sonuç)  \n"
        "- ‘Prim yetersiz kalırsa ne olur?’ görmek istiyorsan: **Daha Riskli** (volatilite)"
    )

    scenario = st.radio("Risk senaryosu seç", list(SCENARIOS.keys()),
                        index=list(SCENARIOS.keys()).index(st.session_state.scenario),
                        horizontal=True)
    st.session_state.scenario = scenario

    p_claim = SCENARIOS[scenario]["p_claim"]
    mean_loss = SCENARIOS[scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss

    st.success(f"**Risk tipi:** {SCENARIOS[scenario]['label']}")
    st.caption(f"Ne zaman seçilir? {SCENARIOS[scenario]['when']}")
    st.write(f"p = **{p_claim:.2f}**, ortalama hasar = **{fmt_tl(mean_loss)}**, beklenen hasar/poliçe = **{fmt_tl(expected_loss_per_policy)}**")

    st.divider()
    ans = st.radio("Mini Soru: Risk artarsa teknik prim ne olur?", ["Azalır", "Artar", "Değişmez"], index=0, key="q1")
    ok = (ans == "Artar")
    st.session_state.quiz_ok[1] = ok
    st.success("Doğru: Teknik prim = beklenen hasar.") if ok else st.warning("İpucu: Teknik prim beklenen hasardır.")
    c1,c2 = st.columns(2)
    c1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    c2.button("İleri ➜", on_click=go_next, disabled=not ok, use_container_width=True)

# =============================
# 2) Teknik prim + gider + tampon (çok net)
# =============================
elif st.session_state.step == 2:
    st.markdown(
        """
### Prim bileşenleri (çok net)
**1) Teknik prim (risk maliyeti)**  
- Poliçe başına beklenen hasar: **p × ortalama hasar**  
- Bu sadece “hasar ödeme” kısmıdır.

**2) Gider yüklemesi (işletme maliyeti)**  
- Komisyon, personel, operasyon, IT, genel gider…  
- Basit model: **Gider = Prim geliri × gider oranı**

**3) Belirsizlik tamponu / güvenlik–kâr payı**  
- Hasarlar her tur beklenenin üstüne çıkabilir (belirsizlik).  
- Bu pay, kötü senaryolara karşı “tampon” + kâr beklentisidir.

> Bu üçü birleşince **brüt prim** oluşur.
        """
    )

    st.session_state.expense_loading = st.slider("Gider yüklemesi (%)", 0, 50, int(st.session_state.expense_loading*100), 1) / 100
    st.session_state.profit_loading = st.slider("Belirsizlik tamponu / güvenlik–kâr (%)", 0, 50, int(st.session_state.profit_loading*100), 1) / 100

    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)

    st.success(
        f"Teknik prim (beklenen hasar/poliçe): **{fmt_tl(expected_loss_per_policy)}**  \n"
        f"Gider oranı: **{fmt_pct(st.session_state.expense_loading)}**, Tampon/Kâr: **{fmt_pct(st.session_state.profit_loading)}**  \n"
        f"Önerilen brüt prim/poliçe: **{fmt_tl(suggested_gross)}**"
    )

    st.divider()
    ans = st.radio("Mini Soru: Gider oranı artarsa brüt prim ne olur?", ["Azalır", "Artar", "Değişmez"], index=0, key="q2")
    ok = (ans == "Artar")
    st.session_state.quiz_ok[2] = ok
    st.success("Doğru: Yükleme artarsa brüt prim artar.") if ok else st.warning("İpucu: Brüt prim = teknik prim + yüklemeler.")
    c1,c2 = st.columns(2)
    c1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    c2.button("İleri ➜", on_click=go_next, disabled=not ok, use_container_width=True)

# =============================
# 3) Prim kararı (kavramsal)
# =============================
elif st.session_state.step == 3:
    st.markdown(
        """
### Bu adımda ne yapıyorsun?
Önerilen brüt primi referans alıp **satış primini** seçiyorsun.

- Prim düşük → talep artabilir → ama prim yetersizse **Combined Ratio** bozulabilir.
- Prim yüksek → talep düşebilir → ama zarar riski azalabilir.

> Burada asıl ders: **fiyatlama–talep–kârlılık dengesi**.
        """
    )

    st.session_state.premium_factor = st.slider("Prim düzeyi (önerilen brüt primin %’si)", 60, 160, int(st.session_state.premium_factor), 5)

    # güncel
    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)
    premium_choice = suggested_gross * (st.session_state.premium_factor / 100.0)

    if st.session_state.premium_factor < 90:
        st.warning(f"Seçim: **Ucuz prim** ({fmt_tl(premium_choice)}) → büyüme olabilir ama zarar riski artar.")
    elif st.session_state.premium_factor > 110:
        st.info(f"Seçim: **Pahalı prim** ({fmt_tl(premium_choice)}) → zarar riski azalabilir ama talep düşebilir.")
    else:
        st.success(f"Seçim: **Dengeli prim** ({fmt_tl(premium_choice)})")

    st.divider()
    ans = st.radio("Mini Soru: Prim çok düşerse en olası etki nedir?",
                   ["Müşteri artar ama zarar riski artar", "Müşteri azalır ve zarar riski azalır", "Hiçbir şey değişmez"],
                   index=0, key="q3")
    ok = (ans == "Müşteri artar ama zarar riski artar")
    st.session_state.quiz_ok[3] = ok
    st.success("Doğru.") if ok else st.warning("İpucu: fiyat ↓ → talep ↑, ama prim yetersiz kalabilir.")
    c1,c2 = st.columns(2)
    c1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    c2.button("İleri ➜", on_click=go_next, disabled=not ok, use_container_width=True)

# =============================
# 4) Piyasa (talep)
# =============================
elif st.session_state.step == 4:
    st.markdown(
        """
### Talep (poliçe sayısı) nasıl oluşuyor?
Bu modelde talep iki şeye bağlı:
- **Pazar büyüklüğü (referans poliçe):** fiyat makulse beklenen müşteri sayısı
- **Fiyata duyarlılık:** fiyat artınca müşterinin kaçma hızı

> Ders: Aynı prim kararı farklı piyasalarda farklı sonuç verir.
        """
    )

    st.session_state.base_policies = st.slider("Pazar büyüklüğü (referans poliçe)", 200, 10000, int(st.session_state.base_policies), 100)
    st.session_state.sensitivity = st.slider("Fiyata duyarlılık (0–3)", 0.0, 3.0, float(st.session_state.sensitivity), 0.1)

    n_est = demand_from_premium(
        premium=premium_choice,
        base_policies=st.session_state.base_policies,
        reference_premium=suggested_gross if suggested_gross > 0 else 1.0,
        sensitivity=st.session_state.sensitivity
    )
    st.info(f"Bu fiyatta tahmini poliçe sayısı: **{n_est:,}**")

    st.divider()
    ans = st.radio("Mini Soru: Duyarlılık çok yüksekse (3), prim artınca ne olur?",
                   ["Talep daha hızlı düşer", "Talep artar", "Talep değişmez"], index=0, key="q4")
    ok = (ans == "Talep daha hızlı düşer")
    st.session_state.quiz_ok[4] = ok
    st.success("Doğru.") if ok else st.warning("İpucu: duyarlılık ↑ → fiyat artışına tepki ↑")
    c1,c2 = st.columns(2)
    c1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    c2.button("İleri ➜", on_click=go_next, disabled=not ok, use_container_width=True)

# =============================
# 5) Özet & Oynat
# =============================
elif st.session_state.step == 5:
    st.markdown("Seçimlerini gör ve **1 dönem oynat**. Sonra koç paneli sana sonuçları açıklayıp öneri verecek.")

    st.session_state.seed = int(st.number_input("Rastgelelik (seed) (opsiyonel)", min_value=0, value=int(st.session_state.seed), step=1))

    summary = {
        "Senaryo": st.session_state.scenario,
        "p": p_claim,
        "Ortalama hasar": fmt_tl(mean_loss),
        "Beklenen hasar/poliçe": fmt_tl(expected_loss_per_policy),
        "Gider oranı": fmt_pct(st.session_state.expense_loading),
        "Tampon/Kâr oranı": fmt_pct(st.session_state.profit_loading),
        "Önerilen brüt prim": fmt_tl(suggested_gross),
        "Senin primin": fmt_tl(premium_choice),
        "Pazar (referans)": f"{st.session_state.base_policies:,}",
        "Duyarlılık": st.session_state.sensitivity,
    }
    st.dataframe(pd.DataFrame([summary]), use_container_width=True)

    def play_one_period():
        n_policies = demand_from_premium(
            premium=premium_choice,
            base_policies=st.session_state.base_policies,
            reference_premium=suggested_gross if suggested_gross > 0 else 1.0,
            sensitivity=st.session_state.sensitivity
        )

        st.session_state.t += 1
        n_claims, total_loss = simulate_period(
            n_policies=n_policies,
            p_claim=p_claim,
            mean_loss=mean_loss,
            seed=(st.session_state.seed + st.session_state.t) if st.session_state.seed != 0 else None
        )

        premium_income = float(n_policies) * float(premium_choice)
        expense = premium_income * st.session_state.expense_loading
        uw_result = premium_income - total_loss - expense
        st.session_state.capital += uw_result
        combined_ratio = (total_loss + expense) / premium_income if premium_income > 0 else 0.0

        # Kısa yorum
        if premium_income == 0:
            comment = "Prim çok yüksek → talep düştü → poliçe yok. Öğrenme için primini düşürmeyi dene."
        elif combined_ratio < 1.0:
            comment = "✅ Teknik kâr: Combined Ratio < 1. (Bu turda prim/hasar dengesi lehine.)"
        else:
            comment = "⚠️ Teknik zarar: Combined Ratio > 1. (Prim yetersiz veya hasar şoku yüksek.)"

        st.session_state.last_commentary = comment

        st.session_state.history.append({
            "Dönem": st.session_state.t,
            "Poliçe": n_policies,
            "Pazar (referans)": st.session_state.base_policies,
            "Prim/poliçe": premium_choice,
            "Prim Geliri": premium_income,
            "Hasar Adedi": n_claims,
            "Toplam Hasar": total_loss,
            "Gider": expense,
            "UW Sonucu": uw_result,
            "Combined Ratio": combined_ratio,
            "Sermaye": st.session_state.capital
        })

    c1,c2 = st.columns(2)
    c1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    c2.button("▶️ 1 Dönem Oynat", on_click=play_one_period, use_container_width=True)

# =============================
# Sonuçlar + Koç paneli
# =============================
st.divider()

if st.session_state.last_commentary:
    st.success(st.session_state.last_commentary)

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)

    # ---- Tablo kalem açıklamaları
    with st.expander("📘 Sonuç tablosundaki kalemler ne anlama geliyor?", expanded=False):
        st.markdown(
            """
- **Poliçe:** Bu tur satılan poliçe sayısı (talep sonucu).  
- **Pazar (referans):** “Fiyat makulse” beklenen poliçe büyüklüğü (piyasa varsayımı).  
- **Prim/poliçe:** Senin belirlediğin satış primi.  
- **Prim Geliri:** Poliçe × Prim/poliçe.  
- **Hasar Adedi:** Bu tur gerçekleşen hasar sayısı (rastgele).  
- **Toplam Hasar:** Hasarların toplam tutarı (rastgele).  
- **Gider:** Prim gelirinin gider oranı kadarı (işletme maliyeti).  
- **UW Sonucu (Underwriting):** Prim Geliri − Toplam Hasar − Gider. (+) kâr, (−) zarar.  
- **Combined Ratio:** (Toplam Hasar + Gider) / Prim Geliri. **<1 kâr**, **>1 zarar**.  
- **Sermaye:** Tüm dönemlerin birikimli sonucu (şirketin tampon gücü).
            """
        )

    st.subheader("📊 Sonuç Tablosu")
    st.dataframe(df, use_container_width=True)

    st.subheader("📈 Trendler")
    st.line_chart(df.set_index("Dönem")[["Prim Geliri", "Toplam Hasar"]])
    st.line_chart(df.set_index("Dönem")[["Combined Ratio"]])
    st.line_chart(df.set_index("Dönem")[["Sermaye"]])

    # ---- Koç: yorum + öneri + yol haritası
    st.subheader("🧠 Koç: Bu tur ne oldu, ne yapmalısın?")
    diagnosis, actions, roadmap = compute_last_insights(
        df=df,
        suggested_gross=suggested_gross,
        premium_choice=premium_choice,
        premium_factor=int(st.session_state.premium_factor)
    )

    cL, cR = st.columns([1,1])
    with cL:
        st.markdown("### 📌 Teşhis (yorum)")
        for d in diagnosis:
            st.write("•", d)

    with cR:
        st.markdown("### ✅ Öneri (bir sonraki tur için)")
        for a in actions[:6]:
            st.write("•", a)

    st.markdown("### 🧭 Yol haritası (strateji değiştirirken elinde dursun)")
    for r in roadmap:
        st.write("•", r)

    # Oyun sonu
    if st.session_state.t >= 12:
        if st.session_state.capital > st.session_state.capital0:
            st.balloons()
            st.success("🎉 12 dönem bitti: Sermayeyi büyüttün!")
        else:
            st.error("12 dönem bitti: Sermaye düştü. (Ders: fiyatlama + belirsizlik + talep dengesi)")
else:
    st.info("Adım adım ilerle: her adımda kısa açıklama + mini soru var. En sonda 1 dönem oynatınca koç yorumları başlayacak.")
