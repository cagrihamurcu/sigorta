import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Sigortacılık Temel Simülasyon", layout="wide")
st.title("🧠 Sigortacılığın Temel Mantığı: Risk Havuzu + Prim + Hasar")

st.caption(
    "Bu uygulama; primin beklenen hasara göre belirlenmesini, risk havuzlamayı ve gerçekleşen sonuçların belirsizliğini gösterir."
)

# -----------------------------
# Yardımcı fonksiyonlar
# -----------------------------
def simulate_period(n_policies: int, p_claim: float, mean_loss: float, seed: int | None = None):
    rng = np.random.default_rng(seed)
    # Her poliçe için hasar var/yok (Bernoulli)
    claim_occurs = rng.random(n_policies) < p_claim
    n_claims = int(claim_occurs.sum())

    # Hasar tutarı (basit): hasar varsa exponential dağılım (pozitif, sağ kuyruklu)
    losses = rng.exponential(scale=mean_loss, size=n_claims) if n_claims > 0 else np.array([])
    total_loss = float(losses.sum())
    return n_claims, total_loss


def demand_from_premium(premium: float, base_policies: int, reference_premium: float, sensitivity: float):
    """
    Basit talep modeli:
    - premium reference'a yaklaştıkça talep base'e yakın
    - premium artınca talep azalır, düşünce artar
    """
    # Oransal fark
    ratio = premium / reference_premium if reference_premium > 0 else 1.0
    # Logaritmik tepki: ratio ↑ -> talep ↓
    demand_factor = np.exp(-sensitivity * (ratio - 1.0))
    n = int(round(base_policies * demand_factor))
    return max(0, n)


# -----------------------------
# Varsayılanlar / state
# -----------------------------
if "t" not in st.session_state:
    st.session_state.t = 0
    st.session_state.capital = 1_000_000.0
    st.session_state.history = []

# -----------------------------
# Sol panel: Parametreler
# -----------------------------
with st.sidebar:
    st.header("1) Risk Parametreleri")
    p_claim = st.slider("Hasar olasılığı (p)", 0.01, 0.30, 0.08, 0.01)
    mean_loss = st.number_input("Ortalama hasar tutarı (TL)", min_value=1_000, max_value=200_000, value=25_000, step=1000)

    st.divider()
    st.header("2) Prim ve Yüklemeler")

    expense_loading = st.slider("Gider yüklemesi (%)", 0, 50, 20, 1) / 100
    profit_loading = st.slider("Kâr / güvenlik yüklemesi (%)", 0, 50, 10, 1) / 100

    # Beklenen hasar = p * mean_loss
    expected_loss_per_policy = p_claim * mean_loss
    technical_premium = expected_loss_per_policy
    gross_premium = technical_premium * (1 + expense_loading + profit_loading)

    st.write("**Beklenen hasar / poliçe (teknik prim):**", f"{technical_premium:,.0f} TL")
    st.write("**Önerilen brüt prim / poliçe:**", f"{gross_premium:,.0f} TL")

    st.divider()
    st.header("3) Talep (Basit)")
    base_policies = st.slider("Referans poliçe sayısı", 100, 10000, 2000, 100)
    sensitivity = st.slider("Fiyata duyarlılık (0=duyarsız)", 0.0, 3.0, 1.2, 0.1)

    st.divider()
    st.header("4) Senin prim kararın")
    premium_choice = st.number_input("Belirlediğin prim (TL / poliçe)", min_value=0, value=int(round(gross_premium)), step=250)

    st.divider()
    seed = st.number_input("Rastgelelik (seed) (istersen sabitle)", min_value=0, value=0, step=1)

    run = st.button("▶️ 1 Dönem Simüle Et")
    reset = st.button("🔄 Sıfırla")

# Reset
if reset:
    st.session_state.t = 0
    st.session_state.capital = 1_000_000.0
    st.session_state.history = []
    st.rerun()

# -----------------------------
# Simülasyon çalıştır
# -----------------------------
if run:
    st.session_state.t += 1

    # Talep: seçilen prime göre poliçe sayısını belirle
    n_policies = demand_from_premium(
        premium=premium_choice,
        base_policies=base_policies,
        reference_premium=gross_premium if gross_premium > 0 else 1.0,
        sensitivity=sensitivity,
    )

    n_claims, total_loss = simulate_period(
        n_policies=n_policies,
        p_claim=p_claim,
        mean_loss=mean_loss,
        seed=(seed + st.session_state.t) if seed != 0 else None
    )

    premium_income = float(n_policies) * float(premium_choice)
    expense = premium_income * expense_loading
    underwriting_result = premium_income - total_loss - expense

    # Sermaye güncelle
    st.session_state.capital += underwriting_result

    loss_ratio = (total_loss / premium_income) if premium_income > 0 else 0.0
    expense_ratio = (expense / premium_income) if premium_income > 0 else 0.0
    combined_ratio = loss_ratio + expense_ratio

    st.session_state.history.append({
        "Dönem": st.session_state.t,
        "Poliçe": n_policies,
        "Hasar Adedi": n_claims,
        "Prim Geliri": premium_income,
        "Toplam Hasar": total_loss,
        "Gider": expense,
        "UW Sonucu": underwriting_result,
        "Loss Ratio": loss_ratio,
        "Expense Ratio": expense_ratio,
        "Combined Ratio": combined_ratio,
        "Sermaye": st.session_state.capital
    })

# -----------------------------
# Gösterim
# -----------------------------
left, right = st.columns([1, 1])

with left:
    st.subheader("📌 Temel mesaj")
    st.markdown(
        """
- **Teknik prim** = Beklenen hasar = *p × ortalama hasar*
- **Brüt prim** = Teknik prim + **gider** + **kâr/güvenlik payı**
- Havuz büyüdükçe (poliçe sayısı arttıkça) gerçekleşen sonuçlar beklenene yaklaşır.
        """
    )

with right:
    st.subheader("💰 Sermaye Durumu")
    st.metric("Başlangıç sermayesi", f"{1_000_000:,.0f} TL")
    st.metric("Güncel sermaye", f"{st.session_state.capital:,.0f} TL")

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)

    st.subheader("📊 Sonuçlar Tablosu")
    st.dataframe(df, use_container_width=True)

    st.subheader("📈 Grafikler")

    # 1) Prim geliri vs hasar
    fig1 = plt.figure()
    plt.plot(df["Dönem"], df["Prim Geliri"], marker="o")
    plt.plot(df["Dönem"], df["Toplam Hasar"], marker="o")
    plt.xlabel("Dönem")
    plt.ylabel("TL")
    plt.title("Prim Geliri ve Toplam Hasar")
    st.pyplot(fig1, clear_figure=True)

    # 2) Combined Ratio
    fig2 = plt.figure()
    plt.plot(df["Dönem"], df["Combined Ratio"], marker="o")
    plt.axhline(1.0, linestyle="--")
    plt.xlabel("Dönem")
    plt.ylabel("Oran")
    plt.title("Combined Ratio (1'in altı teknik kâr)")
    st.pyplot(fig2, clear_figure=True)

    # 3) Sermaye
    fig3 = plt.figure()
    plt.plot(df["Dönem"], df["Sermaye"], marker="o")
    plt.xlabel("Dönem")
    plt.ylabel("TL")
    plt.title("Sermaye (Kümülatif)")
    st.pyplot(fig3, clear_figure=True)
else:
    st.info("Sol panelden parametreleri seçip **1 Dönem Simüle Et** diyerek başlayın.")
