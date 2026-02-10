import streamlit as st
import streamlit.components.v1 as components
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

    if premium_income == 0:
        diagnosis.append("Satış yok: prim rekabetçi seviyenin çok üzerinde kalmış görünüyor.")
        actions.append("Prim düzeyini düşür (ör. önerilen brüt primin %90–%110 bandına yaklaş).")
    else:
        if cr < 1.0:
            diagnosis.append(f"Teknik sonuç olumlu: Combined Ratio = {cr:.2f} (< 1).")
            actions.append("Fiyatı koru veya kontrollü büyüme için küçük indirim dene (örn. -%5).")
        elif 1.0 <= cr < 1.10:
            diagnosis.append(f"Teknik sonuç sınıra yakın: Combined Ratio = {cr:.2f} (1’e yakın).")
            actions.append("Prim düzeyini bir kademe artır (örn. +%5–%10) veya gider oranını düşürmeyi dene.")
        else:
            diagnosis.append(f"Teknik sonuç olumsuz: Combined Ratio = {cr:.2f} (>> 1).")
            actions.append("Prim düzeyini artır (+%10–%20) ve fiyat disiplinini güçlendir.")

    if price_gap < 0.9:
        diagnosis.append("Prim, önerilen brüt primin belirgin altında: satış artabilir ama prim yetersizliği sermayeyi zorlayabilir.")
        actions.append("CR>1 ise önce prim seviyesini önerilen banda yaklaştır.")
    elif price_gap > 1.1:
        diagnosis.append("Prim, önerilen brüt primin üstünde: zarar riski azalabilir ama rekabetçi satış düşebilir.")
        actions.append("Satış çok düştüyse prim seviyesini biraz geri çek (örn. -%5).")
    else:
        diagnosis.append("Prim, önerilen brüt prime yakın: fiyatlama açısından dengeli bir bölgede ilerliyorsun.")

    if demand_ratio < 0.6:
        diagnosis.append("Satış zayıf: fiyat pahalı kalmış olabilir veya piyasa fiyata çok hassastır.")
        actions.append("Satış hedefleniyorsa prim düzeyini düşür veya fiyata duyarlılığı daha düşük bir piyasa varsayımıyla test et.")
    elif demand_ratio > 1.2:
        diagnosis.append("Satış güçlü: genişleyen risk havuzu sonuçları beklenen değere yaklaştırma eğilimindedir.")
        actions.append("CR kötü ise satış artışı zararı büyütebilir → prim artır. CR iyi ise büyümeyi sürdür.")

    roadmap.append("1) Öncelik: Combined Ratio’yu 1’in altına çek (teknik denge).")
    roadmap.append("2) Sonra: CR<1 iken küçük fiyat indirimleriyle satış hacmini test et (kontrollü).")
    roadmap.append("3) Piyasa çok hassassa: prim ayarını küçük adımlarla yap; küçük artış satışları hızlı düşürebilir.")
    roadmap.append("4) Rekabet baskısı yüksekse, primin daha disiplinli olması gerekir.")

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
        st.session_state.period = 0  # fiyatlama dönemi

    if "history" not in st.session_state:
        st.session_state.history = []

    # kararlar
    if "scenario" not in st.session_state:
        st.session_state.scenario = "Standart Piyasa"
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

    # scroll flag
    if "_do_scroll" not in st.session_state:
        st.session_state._do_scroll = False

init_state()

# =============================
# Scroll-to-top (en üstte çalışır)
# =============================
if st.session_state.get("_do_scroll", False):
    components.html(
        """
        <script>
          try { window.parent.scrollTo({top: 0, left: 0, behavior: 'instant'}); }
          catch (e) { window.parent.scrollTo(0,0); }
        </script>
        """,
        height=0,
        width=0,
    )
    st.session_state._do_scroll = False

# =============================
# Piyasa/Risk Profili (terminoloji sadeleştirildi)
# =============================
SCENARIOS = {
    "Seçici Risk Kabul (Daha İyi Portföy)": {
        "p_claim": 0.05,
        "mean_loss": 20_000,
        "label": "Daha düşük hasar olasılığı ve daha düşük ortalama hasar",
        "market_logic": (
            "**Ne demek?**\n"
            "- Şirket daha düşük riskli poliçeler satıyor varsayılır.\n"
            "- Bu yüzden hasar daha seyrek ve/veya daha düşük tutarda gelir.\n"
            "- Rekabet baskısı görece düşüktür (fiyat kırma daha azdır)."
        )
    },
    "Standart Piyasa": {
        "p_claim": 0.08,
        "mean_loss": 25_000,
        "label": "Ortalama risk karışımı; tipik piyasa dengesi",
        "market_logic": (
            "**Ne demek?**\n"
            "- Piyasa ortalamasına yakın bir risk düzeyi varsayılır.\n"
            "- Rekabet baskısı orta düzeydedir.\n"
            "- Hasar olasılığı ve ortalama hasar ‘referans’ seviyededir."
        )
    },
    "Yoğun Rekabet (Zayıf Fiyat Disiplini)": {
        "p_claim": 0.12,
        "mean_loss": 32_000,
        "label": "Hasar olasılığı ve ortalama hasar daha yüksek (daha zorlu koşul)",
        "market_logic": (
            "**Ne demek?**\n"
            "- Rekabet baskısı yüksektir: fiyat kırma eğilimi artar.\n"
            "- Daha riskli poliçelerin portföye gelmesi olasıdır.\n"
            "- Bu nedenle hasar daha sık ve/veya daha yüksek tutarda gerçekleşebilir."
        )
    },
}

# =============================
# Navigation (scroll flag eklendi)
# =============================
def go_next():
    st.session_state.step = 1 if st.session_state.step == 0 else min(5, st.session_state.step + 1)
    st.session_state._do_scroll = True

def go_prev():
    st.session_state.step = 0 if st.session_state.step == 1 else max(0, st.session_state.step - 1)
    st.session_state._do_scroll = True

def hard_reset():
    st.session_state.step = 0
    st.session_state.period = 0
    st.session_state.capital = st.session_state.capital0
    st.session_state.history = []
    st.session_state.last_commentary = ""
    st.session_state.quiz_ok = {"intro": False, 1: False, 2: False, 3: False, 4: False}
    st.session_state.quiz_submitted = {"intro": False, 1: False, 2: False, 3: False, 4: False}
    st.session_state._do_scroll = True

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
st.title("📊 Sigortacılığın Temel Mantığı — Fiyatlama Simülasyonu")
st.caption("Prim (fiyat) → satış hacmi → hasar + gider → teknik sonuç → sermaye")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Fiyatlama Dönemi", f"{st.session_state.period} / 12")
c2.metric("Sermaye", fmt_tl(st.session_state.capital))
c3.metric("Önerilen brüt prim", fmt_tl(suggested_gross))
c4.metric("Seçilen prim", fmt_tl(premium_choice))

with st.sidebar:
    st.header("⚙️ Kontrol")
    if st.button("🔄 Baştan Başlat", use_container_width=True):
        hard_reset()
        st.rerun()

# =============================
# INTRO
# =============================
if st.session_state.step == 0:
    st.subheader("🚦 Başlangıç: temel kavram")
    st.markdown(
        """
### “Beklenen hasar/poliçe” nedir?
Bir poliçenin, bir fiyatlama döneminde ortalama ne kadar hasar maliyeti üretmesini beklediğimiz değerdir.

- Hasar olma ihtimali: **p**
- Hasar olursa ortalama tutar: **ortalama hasar**
- **Beklenen hasar/poliçe = p × ortalama hasar**

Örnek: p=0.10 ve ortalama hasar=10.000 TL ise → beklenen hasar/poliçe = 1.000 TL.
        """
    )

    st.divider()
    st.write("Mini Soru:")
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
            st.warning("Yanlış. İpucu: beklenen hasar = p × ortalama hasar.")

    if st.button("İleri ➜", disabled=not st.session_state.quiz_ok["intro"], use_container_width=True):
        go_next()
        st.rerun()

# =============================
# Wizard başlıkları
# =============================
steps_title = {
    1: "1) Piyasa Koşulu (Hasar Seviyesi)",
    2: "2) Prim Bileşenleri",
    3: "3) Prim Düzeyi (Fiyatlama)",
    4: "4) Talep Varsayımı",
    5: "5) Özet & Simülasyon",
}
if st.session_state.step in [1, 2, 3, 4, 5]:
    st.subheader(f"🧭 {steps_title[st.session_state.step]}")
    st.progress(st.session_state.step / 5)

# =============================
# 1) Profil
# =============================
if st.session_state.step == 1:
    st.markdown(
        """
Bu adımda **piyasanın hasar seviyesini** seçiyorsun.  
Seçim iki şeyi belirler:
- **Hasar olasılığı (p)**: Bu dönemde bir poliçenin hasara dönme ihtimali
- **Ortalama hasar**: Hasar olursa ortalama ne kadar ödeme çıkacağı
        """
    )

    scenario = st.radio(
        "Piyasa koşulu seç",
        list(SCENARIOS.keys()),
        index=list(SCENARIOS.keys()).index(st.session_state.scenario),
        horizontal=True,
        key="scenario_pick"
    )
    st.session_state.scenario = scenario

    p_claim = SCENARIOS[scenario]["p_claim"]
    mean_loss = SCENARIOS[scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss

    st.success(f"**Koşul:** {SCENARIOS[scenario]['label']}")
    st.info(SCENARIOS[scenario]["market_logic"])

    st.markdown(
        f"""
**Bu koşulda sayılar:**  
- p = **{p_claim:.2f}**  
- Ortalama hasar = **{fmt_tl(mean_loss)}**  
- Beklenen hasar/poliçe = **{fmt_tl(expected_loss_per_policy)}**
        """
    )

    st.divider()
    st.write("Mini Soru:")
    ans = st.radio(
        "Hasar olasılığı (p) artarsa, beklenen hasar/poliçe için en doğru ifade hangisidir?",
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
            st.success("Doğru.")
        else:
            st.warning("Yanlış. İpucu: beklenen hasar = p × ortalama hasar.")

    b1, b2 = st.columns(2)
    if b1.button("⬅ Geri", use_container_width=True):
        go_prev(); st.rerun()
    if b2.button("İleri ➜", disabled=not st.session_state.quiz_ok[1], use_container_width=True):
        go_next(); st.rerun()

# =============================
# 2) Prim bileşenleri
# =============================
elif st.session_state.step == 2:
    st.markdown(
        """
### Brüt primin üç parçası
**1) Teknik prim:** Hasarları ödemek için gereken ortalama tutar (beklenen hasar/poliçe)  
**2) Gider payı:** İşletme maliyetleri (komisyon, operasyon, IT vb.)  
**3) Tampon/Kâr payı:** Beklenenden kötü dönemlere karşı güvenlik payı
        """
    )

    st.session_state.expense_loading = st.slider("Gider oranı (%)", 0, 50, int(st.session_state.expense_loading * 100), 1) / 100
    st.session_state.profit_loading = st.slider("Tampon/Kâr oranı (%)", 0, 50, int(st.session_state.profit_loading * 100), 1) / 100

    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)

    st.success(
        f"Teknik prim: **{fmt_tl(expected_loss_per_policy)}**\n\n"
        f"Gider oranı: **{fmt_pct(st.session_state.expense_loading)}**\n"
        f"Tampon/Kâr oranı: **{fmt_pct(st.session_state.profit_loading)}**\n\n"
        f"Önerilen brüt prim/poliçe: **{fmt_tl(suggested_gross)}**"
    )

    st.divider()
    st.write("Mini Soru:")
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
            st.success("Doğru.")
        else:
            st.warning("Yanlış. İpucu: brüt prim; teknik prim + yüklemelerden oluşur.")

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
Önerilen brüt prim referanstır. Bu adımda satış primini belirliyorsun.

- Düşük prim → satış artabilir ama teknik zarar riski artar
- Yüksek prim → satış düşebilir ama zarar riski azalabilir
        """
    )

    st.session_state.premium_factor = st.slider("Prim düzeyi (önerilen brüt primin %’si)", 60, 160, int(st.session_state.premium_factor), 5)

    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)
    premium_choice = suggested_gross * (st.session_state.premium_factor / 100.0)

    if st.session_state.premium_factor < 90:
        st.warning(f"Agresif fiyat: {fmt_tl(premium_choice)} (satış artabilir, zarar riski artar)")
    elif st.session_state.premium_factor > 110:
        st.info(f"Korumacı fiyat: {fmt_tl(premium_choice)} (zarar riski azalabilir, satış düşebilir)")
    else:
        st.success(f"Denge bandı: {fmt_tl(premium_choice)}")

    st.divider()
    st.write("Mini Soru:")
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
# 4) Talep varsayımı
# =============================
elif st.session_state.step == 4:
    st.markdown(
        """
### Referans satış (poliçe) ne demek?
Prim “rekabetçi/makul” seviyedeyken, bu fiyatlama döneminde satılmasını beklediğin poliçe adedidir.
        """
    )

    st.session_state.base_policies = st.slider(
        "Referans satış (rekabetçi fiyatla beklenen poliçe adedi)",
        200, 10000, int(st.session_state.base_policies), 100
    )
    st.session_state.sensitivity = st.slider("Fiyata duyarlılık (0–3)", 0.0, 3.0, float(st.session_state.sensitivity), 0.1)

    n_est = demand_from_premium(
        premium=premium_choice,
        base_policies=st.session_state.base_policies,
        reference_premium=suggested_gross if suggested_gross > 0 else 1.0,
        sensitivity=st.session_state.sensitivity
    )
    st.info(f"Bu prim düzeyinde tahmini satış: **{n_est:,} poliçe**")

    st.divider()
    st.write("Mini Soru:")
    ans = st.radio(
        "Fiyata duyarlılık yükselirse prim artınca satış nasıl değişir?",
        ["Daha hızlı düşer", "Artar", "Değişmez"],
        index=0,
        key="q4"
    )

    if st.button("Cevabı Gönder", use_container_width=True):
        st.session_state.quiz_submitted[4] = True
        st.session_state.quiz_ok[4] = (ans == "Daha hızlı düşer")
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
    st.markdown("Seçimlerini kontrol et ve **bu primle piyasaya çık** (1 fiyatlama dönemi simülasyonu).")

    summary = {
        "Piyasa koşulu": st.session_state.scenario,
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
            seed=None
        )

        premium_income = float(n_policies) * float(premium_choice)
        expense = premium_income * st.session_state.expense_loading
        uw_result = premium_income - total_loss - expense
        st.session_state.capital += uw_result
        combined_ratio = (total_loss + expense) / premium_income if premium_income > 0 else 0.0

        if premium_income == 0:
            comment = "Satış yok: prim rekabetçi seviyenin çok üzerinde kalmış görünüyor."
        else:
            if combined_ratio < 1.0:
                comment = "✅ Teknik kâr: Combined Ratio < 1."
            else:
                comment = "⚠️ Teknik zarar: Combined Ratio > 1."

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

    if b2.button("📣 Bu primle piyasaya çık (1 dönem simüle et)", use_container_width=True):
        simulate_one_pricing_period()
        st.session_state._do_scroll = True  # simülasyon sonrası da yukarı al
        st.rerun()

# =============================
# Sonuçlar + Koç
# =============================
st.divider()

if st.session_state.last_commentary:
    st.success(st.session_state.last_commentary)

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)

    with st.expander("📘 Sonuç kalemleri (kısa açıklama)", expanded=False):
        st.markdown(
            """
- **Poliçe:** Bu primle gerçekleşen satış (satılan poliçe adedi).  
- **Referans Satış (poliçe):** Prim rekabetçi olsaydı beklenen satış hacmi (varsayım).  
- **Prim/poliçe:** Uygulanan satış primi.  
- **Prim Geliri:** Poliçe × Prim/poliçe.  
- **Hasar Adedi / Toplam Hasar:** Gerçekleşen hasar sayısı ve toplam tutar.  
- **Gider:** Prim gelirinin gider oranı kadar kısmı.  
- **UW Sonucu:** Prim Geliri − Toplam Hasar − Gider.  
- **Combined Ratio:** (Toplam Hasar + Gider) / Prim Geliri. **<1 kâr**, **>1 zarar**.  
- **Sermaye:** Birikimli sonuç.
            """
        )

    st.subheader("📊 Sonuç Tablosu")
    st.dataframe(df, use_container_width=True)

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

    st.markdown("### 🧭 Yol haritası")
    for r in roadmap:
        st.write("•", r)

    st.subheader("📈 Trendler")
    st.line_chart(df.set_index("Fiyatlama Dönemi")[["Prim Geliri", "Toplam Hasar"]])
    st.line_chart(df.set_index("Fiyatlama Dönemi")[["Combined Ratio"]])
    st.line_chart(df.set_index("Fiyatlama Dönemi")[["Sermaye"]])

    if st.session_state.period >= 12:
        if st.session_state.capital > st.session_state.capital0:
            st.balloons()
            st.success("🎉 12 fiyatlama dönemi bitti: Sermayeyi büyüttün!")
        else:
            st.error("12 fiyatlama dönemi bitti: Sermaye düştü.")
else:
    st.info("Adım adım ilerle: mini sorularla ilerleyip en sonda simülasyon çalıştırınca sonuçlar ve koç yorumları görünür.")
