import streamlit as st
import numpy as np
import pandas as pd
from typing import Optional

st.set_page_config(page_title="Sigortacılık Temel Simülasyon", layout="wide")
st.title("🧠 Sigortacılığın Temel Mantığı: Risk Havuzu + Prim + Hasar")

st.caption("Prim = beklenen hasar + gider + güvenlik/kâr payı. Havuz büyüdükçe sonuçlar beklenene yaklaşır.")

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

if "t" not in st.session_state:
    st.session_state.t = 0
    st.session_state.capital = 1_000_000.0
    st.session_state.history = []

with st.sidebar:
    st.header("1) Risk Parametreleri")
    p_claim = st.slider("Hasar olasılığı (p)", 0.01, 0.30, 0.08, 0.01)
    mean_loss = st.number_input("Ortalama hasar tutarı (TL)", min_value=1_000, max_value=200_000, value=25_000, step=1000)

    st.divider()
    st.header("2) Prim ve Yüklemeler")
    expense_loading = st.slider("Gider yüklemesi (%)", 0, 50, 20, 1) / 100
    profit_loading = st.slider("Güvenlik/Kâr yüklemesi (%)", 0, 50, 10, 1) / 100

    expected_loss_per_policy = p_claim * mean_loss
    gross_premium = expected_loss_per_policy * (1 + expense_loading + profit_loading)

    st.write("**Beklenen hasar / poliçe (teknik prim):**", f"{expected_loss_per_policy:,.0f} TL")
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

if reset:
    st.session_state.t = 0
    st.session_state.capital = 1_000_000.0
    st.session_state.history = []
    st.rerun()

if run:
    st.session_state.t += 1
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

st.subheader("💰 Sermaye")
st.metric("Güncel sermaye", f"{st.session_state.capital:,.0f} TL")

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)
    st.subheader("📊 Sonuçlar")
    st.dataframe(df, use_container_width=True)

    st.subheader("📈 Grafikler")
    st.line_chart(df.set_index("Dönem")[["Prim Geliri", "Toplam Hasar"]])
    st.line_chart(df.set_index("Dönem")[["Combined Ratio"]])
    st.line_chart(df.set_index("Dönem")[["Sermaye"]])
else:
    st.info("Sol panelden parametreleri seçip **1 Dönem Simüle Et** diyerek başlayın.")
