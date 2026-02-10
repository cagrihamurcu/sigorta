import streamlit as st
import numpy as np
import pandas as pd
from typing import Optional

st.set_page_config(page_title="Sigorta Temel Mantık Oyunu (Adım Adım)", layout="wide")

# -----------------------------
# Yardımcılar
# -----------------------------
def fmt_tl(x: float) -> str:
    return f"{x:,.0f} TL"

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

def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 1

    if "capital0" not in st.session_state:
        st.session_state.capital0 = 1_000_000.0
        st.session_state.capital = st.session_state.capital0

    if "t" not in st.session_state:
        st.session_state.t = 0

    if "history" not in st.session_state:
        st.session_state.history = []

    # Oyuncu seçimleri (wizard boyunca doldurulacak)
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

# -----------------------------
# Senaryo parametreleri
# -----------------------------
SCENARIOS = {
    "Daha Az Riskli": {"p_claim": 0.05, "mean_loss": 20_000},
    "Normal": {"p_claim": 0.08, "mean_loss": 25_000},
    "Daha Riskli": {"p_claim": 0.12, "mean_loss": 32_000},
}

p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]

expected_loss_per_policy = p_claim * mean_loss
suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)
premium_choice = suggested_gross * (st.session_state.premium_factor / 100.0)

# -----------------------------
# Oyun başlığı + ilerleme
# -----------------------------
st.title("🎮 Sigortacılığın Temel Mantığı (Adım Adım)")
st.caption("Öğrenciye tek seferde her şeyi yüklemek yerine 5 adımda ilerliyoruz: Risk → Yüklemeler → Prim → Piyasa → Oynat.")

progress = (st.session_state.step - 1) / 5
st.progress(progress)

steps_title = {
    1: "1) Risk Senaryosu",
    2: "2) Yüklemeler (Gider + Güvenlik/Kâr)",
    3: "3) Prim Kararı",
    4: "4) Piyasa (Talep)",
    5: "5) Özet & Oynat",
}
st.subheader(f"🧭 {steps_title.get(st.session_state.step, '')}")

# Üstte küçük skor panosu (oyun hissi)
colA, colB, colC, colD = st.columns(4)
colA.metric("Dönem", f"{st.session_state.t} / 12")
colB.metric("Sermaye", fmt_tl(st.session_state.capital))
colC.metric("Önerilen brüt prim", fmt_tl(suggested_gross))
colD.metric("Senin primin", fmt_tl(premium_choice))

# -----------------------------
# Navigasyon butonları
# -----------------------------
def go_prev():
    st.session_state.step = max(1, st.session_state.step - 1)

def go_next():
    st.session_state.step = min(5, st.session_state.step + 1)

# -----------------------------
# 1) Risk Senaryosu
# -----------------------------
if st.session_state.step == 1:
    st.markdown(
        """
Bu adımda sadece **riskin yapısını** seçiyorsun.

- **Hasar olasılığı (p):** Bir poliçede dönem içinde hasar olma ihtimali  
- **Ortalama hasar:** Hasar olursa ortalama tutar

Amaç: Risk artınca primin neden artması gerektiğini görmek.
        """
    )

    scenario = st.radio(
        "Senaryo seç",
        list(SCENARIOS.keys()),
        index=list(SCENARIOS.keys()).index(st.session_state.scenario),
        horizontal=True
    )
    st.session_state.scenario = scenario

    p_claim = SCENARIOS[scenario]["p_claim"]
    mean_loss = SCENARIOS[scenario]["mean_loss"]

    st.info(f"Bu senaryoda: p = **{p_claim:.2f}**, ortalama hasar = **{fmt_tl(mean_loss)}**")

    nav1, nav2 = st.columns([1, 1])
    with nav2:
        st.button("İleri ➜", on_click=go_next, use_container_width=True)

# -----------------------------
# 2) Yüklemeler
# -----------------------------
elif st.session_state.step == 2:
    st.markdown(
        """
Sigortada prim sadece hasarı ödemek için değildir.

**Teknik prim (beklenen hasar)**:
- Beklenen hasar / poliçe = **p × ortalama hasar**

**Brüt prim**:
- Teknik prim + **gider yüklemesi** + **güvenlik/kâr payı**
        """
    )

    st.session_state.expense_loading = st.slider(
        "Gider yüklemesi (%) (komisyon, personel, IT, genel gider vb.)",
        0, 50, int(st.session_state.expense_loading * 100), 1
    ) / 100

    st.session_state.profit_loading = st.slider(
        "Güvenlik/Kâr payı (%) (belirsizlik için tampon + kâr)",
        0, 50, int(st.session_state.profit_loading * 100), 1
    ) / 100

    # Güncel hesapları göster
    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)

    st.success(
        f"Beklenen hasar / poliçe (teknik prim): **{fmt_tl(expected_loss_per_policy)}**  \n"
        f"Önerilen brüt prim / poliçe: **{fmt_tl(suggested_gross)}**"
    )

    nav1, nav2 = st.columns([1, 1])
    with nav1:
        st.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    with nav2:
        st.button("İleri ➜", on_click=go_next, use_container_width=True)

# -----------------------------
# 3) Prim Kararı
# -----------------------------
elif st.session_state.step == 3:
    st.markdown(
        """
Şimdi “satış fiyatını” seçiyorsun.

- **Önerilen brüt prim** denge noktası gibi düşün.
- Daha düşük fiyat → daha çok müşteri, ama **zarar riski** artabilir.
- Daha yüksek fiyat → müşteri azalabilir, ama **kârlılık** ihtimali artar.
        """
    )

    st.session_state.premium_factor = st.slider(
        "Prim düzeyi (önerilen brüt primin %’si)",
        60, 160, int(st.session_state.premium_factor), 5
    )

    # Güncel premium hesap
    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)
    premium_choice = suggested_gross * (st.session_state.premium_factor / 100.0)

    if st.session_state.premium_factor < 90:
        st.warning(f"Prim düşük: **{fmt_tl(premium_choice)}** → müşteri artabilir ama sermaye eriyebilir.")
    elif st.session_state.premium_factor > 110:
        st.info(f"Prim yüksek: **{fmt_tl(premium_choice)}** → zarar riski azalabilir ama müşteri kaybı olabilir.")
    else:
        st.success(f"Dengeli prim: **{fmt_tl(premium_choice)}**")

    nav1, nav2 = st.columns([1, 1])
    with nav1:
        st.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    with nav2:
        st.button("İleri ➜", on_click=go_next, use_container_width=True)

# -----------------------------
# 4) Piyasa (Talep)
# -----------------------------
elif st.session_state.step == 4:
    st.markdown(
        """
Sigorta sadece matematik değildir; **piyasa davranışı** da vardır.

- Pazar büyüklüğü (referans poliçe): Prim “makul” ise yaklaşık bu kadar müşteri gelir.
- Fiyata duyarlılık: Prim artınca müşterinin kaçma derecesi.
        """
    )

    st.session_state.base_policies = st.slider(
        "Pazar büyüklüğü (referans poliçe)",
        200, 10000, int(st.session_state.base_policies), 100
    )

    st.session_state.sensitivity = st.slider(
        "Fiyata duyarlılık (0=duyarsız, 3=çok hassas)",
        0.0, 3.0, float(st.session_state.sensitivity), 0.1
    )

    # Tahmini talep göster
    n_est = demand_from_premium(
        premium=premium_choice,
        base_policies=st.session_state.base_policies,
        reference_premium=suggested_gross if suggested_gross > 0 else 1.0,
        sensitivity=st.session_state.sensitivity
    )

    st.info(f"Bu fiyatta tahmini müşteri (poliçe) sayısı: **{n_est:,}**")

    nav1, nav2 = st.columns([1, 1])
    with nav1:
        st.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    with nav2:
        st.button("İleri ➜", on_click=go_next, use_container_width=True)

# -----------------------------
# 5) Özet & Oynat
# -----------------------------
elif st.session_state.step == 5:
    st.markdown(
        """
Son adım: Seçimlerini özetle ve **1 dönem oynat**.

Bu turda:
- Talep (poliçe sayısı) oluşur
- Hasarlar gelir
- Gider düşülür
- **Sermaye** güncellenir
        """
    )

    st.session_state.seed = int(st.number_input("Rastgelelik (seed) (opsiyonel)", min_value=0, value=int(st.session_state.seed), step=1))

    # Özet kartı
    summary = {
        "Senaryo": st.session_state.scenario,
        "Hasar olasılığı (p)": p_claim,
        "Ortalama hasar": fmt_tl(mean_loss),
        "Beklenen hasar / poliçe": fmt_tl(expected_loss_per_policy),
        "Gider yüklemesi": f"{int(st.session_state.expense_loading*100)}%",
        "Güvenlik/Kâr payı": f"{int(st.session_state.profit_loading*100)}%",
        "Önerilen brüt prim": fmt_tl(suggested_gross),
        "Senin primin": fmt_tl(premium_choice),
        "Pazar büyüklüğü": f"{st.session_state.base_policies:,}",
        "Fiyata duyarlılık": st.session_state.sensitivity,
    }
    st.dataframe(pd.DataFrame([summary]), use_container_width=True)

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.button("⬅ Geri", on_click=go_prev, use_container_width=True)

    def play_one_period():
        # Talep
        n_policies = demand_from_premium(
            premium=premium_choice,
            base_policies=st.session_state.base_policies,
            reference_premium=suggested_gross if suggested_gross > 0 else 1.0,
            sensitivity=st.session_state.sensitivity
        )

        # Hasar
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

        # Öğretici yorum
        if premium_income == 0:
            comment = "Prim çok yüksek olduğu için talep neredeyse sıfırlandı. Poliçe olmayınca hasar da yok; ama oyun öğrenme açısından kilitlenir."
        elif combined_ratio < 1.0:
            comment = "✅ Teknik kâr (Combined Ratio < 1). Bu tur prim ve gerçekleşen hasar dengesi lehine oldu."
        else:
            comment = "⚠️ Teknik zarar (Combined Ratio > 1). Ya prim düşük kaldı ya da hasar gerçekleşmesi yüksek geldi."

        st.session_state.last_commentary = comment

        st.session_state.history.append({
            "Dönem": st.session_state.t,
            "Poliçe": n_policies,
            "Hasar Adedi": n_claims,
            "Prim (poliçe)": premium_choice,
            "Prim Geliri": premium_income,
            "Toplam Hasar": total_loss,
            "Gider": expense,
            "UW Sonucu": uw_result,
            "Combined Ratio": combined_ratio,
            "Sermaye": st.session_state.capital
        })

    with col2:
        st.button("▶️ 1 Dönem Oynat", on_click=play_one_period, use_container_width=True)

    with col3:
        if st.button("🔄 Oyunu Sıfırla", use_container_width=True):
            st.session_state.t = 0
            st.session_state.capital = st.session_state.capital0
            st.session_state.history = []
            st.session_state.last_commentary = ""
            st.session_state.step = 1
            st.rerun()

# -----------------------------
# Alt bölüm: Sonuçlar (her adımda görünür)
# -----------------------------
st.divider()

if st.session_state.last_commentary:
    st.success(st.session_state.last_commentary)

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)

    st.subheader("📊 Oyun Sonuçları (Dönem Dönem)")
    st.dataframe(df, use_container_width=True)

    st.subheader("📈 Trendler")
    st.line_chart(df.set_index("Dönem")[["Prim Geliri", "Toplam Hasar"]])
    st.line_chart(df.set_index("Dönem")[["Combined Ratio"]])
    st.line_chart(df.set_index("Dönem")[["Sermaye"]])

    if st.session_state.t >= 12:
        if st.session_state.capital > st.session_state.capital0:
            st.balloons()
            st.success("🎉 12 dönem bitti: Sermayeyi büyüttün!")
        else:
            st.error("12 dönem bitti: Sermaye düştü. (Ders: fiyatlama + belirsizlik)")

else:
    st.info("Adım adım ilerlemek için yukarıdaki yönlendirmeleri takip et. En sonda ‘▶️ 1 Dönem Oynat’ ile sonuçları göreceksin.")
