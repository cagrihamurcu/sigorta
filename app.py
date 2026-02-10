import streamlit as st
import numpy as np
import pandas as pd

st.set_page_config(page_title="Sigorta Fiyatlama Simülasyonu", layout="wide")

# =========================================================
# YARDIMCILAR
# =========================================================

def fmt_tl(x):
    return f"{x:,.0f} TL"

def fmt_pct(x):
    return f"{x*100:.1f}%"

def simulate_period(n_policies, p_claim, mean_loss):
    rng = np.random.default_rng()
    claim_occurs = rng.random(n_policies) < p_claim
    n_claims = int(claim_occurs.sum())
    losses = rng.exponential(scale=mean_loss, size=n_claims) if n_claims > 0 else np.array([])
    return n_claims, float(losses.sum())

def demand_from_premium(premium, base_policies, reference_premium, sensitivity):
    ratio = premium / reference_premium if reference_premium > 0 else 1
    demand_factor = np.exp(-sensitivity * (ratio - 1))
    return max(0, int(round(base_policies * demand_factor)))

# =========================================================
# STATE
# =========================================================

if "step" not in st.session_state:
    st.session_state.step = 0

if "capital" not in st.session_state:
    st.session_state.capital = 1_000_000

if "capital0" not in st.session_state:
    st.session_state.capital0 = 1_000_000

if "period" not in st.session_state:
    st.session_state.period = 0

if "history" not in st.session_state:
    st.session_state.history = []

if "quiz_ok" not in st.session_state:
    st.session_state.quiz_ok = {}

# =========================================================
# PİYASA KOŞULLARI
# =========================================================

SCENARIOS = {
    "Düşük Hasar Seviyesi": {"p": 0.05, "mean": 20000},
    "Orta Hasar Seviyesi": {"p": 0.08, "mean": 25000},
    "Yüksek Hasar Seviyesi": {"p": 0.12, "mean": 32000},
}

if "scenario" not in st.session_state:
    st.session_state.scenario = "Orta Hasar Seviyesi"

if "expense" not in st.session_state:
    st.session_state.expense = 0.20

if "profit" not in st.session_state:
    st.session_state.profit = 0.10

if "premium_factor" not in st.session_state:
    st.session_state.premium_factor = 100

if "base_policies" not in st.session_state:
    st.session_state.base_policies = 2000

if "sensitivity" not in st.session_state:
    st.session_state.sensitivity = 1.2

# =========================================================
# NAVIGATION
# =========================================================

def next_step():
    st.session_state.step += 1
    st.rerun()

def prev_step():
    st.session_state.step -= 1
    st.rerun()

def reset_all():
    st.session_state.step = 0
    st.session_state.period = 0
    st.session_state.capital = st.session_state.capital0
    st.session_state.history = []
    st.session_state.quiz_ok = {}
    st.rerun()

# =========================================================
# BAŞLIK
# =========================================================

st.title("📊 Sigorta Fiyatlama Simülasyonu")
st.caption("Prim → Satış → Hasar → Teknik Sonuç → Sermaye")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Fiyatlama Dönemi", st.session_state.period)
c2.metric("Sermaye", fmt_tl(st.session_state.capital))

with st.sidebar:
    if st.button("🔄 Baştan Başlat"):
        reset_all()

# =========================================================
# ADIM 0 – TEMEL KAVRAM
# =========================================================

if st.session_state.step == 0:

    st.subheader("Beklenen Hasar / Poliçe Nedir?")

    st.markdown("""
Bir poliçenin bir fiyatlama döneminde ortalama ne kadar hasar maliyeti üretmesini beklediğimiz değerdir.

**Formül:**

Beklenen Hasar = Hasar Olasılığı (p) × Ortalama Hasar
    """)

    answer = st.radio(
        "Beklenen hasar hangi iki değerin çarpımıdır?",
        [
            "Hasar olasılığı × Ortalama hasar",
            "Prim × Poliçe sayısı",
            "Gider × Hasar"
        ]
    )

    if st.button("Cevabı Gönder"):
        st.session_state.quiz_ok[0] = (answer == "Hasar olasılığı × Ortalama hasar")

    if 0 in st.session_state.quiz_ok:
        if st.session_state.quiz_ok[0]:
            st.success("Doğru.")
        else:
            st.warning("Yanlış. Beklenen hasar = p × ortalama hasar.")

    if st.button("İleri ➜", disabled=not st.session_state.quiz_ok.get(0, False)):
        next_step()

# =========================================================
# ADIM 1 – PİYASA KOŞULU
# =========================================================

elif st.session_state.step == 1:

    st.subheader("Piyasa Hasar Seviyesi")

    st.markdown("""
Bu seçim, piyasadaki hasar sıklığını ve ortalama hasar büyüklüğünü belirler.
    """)

    scenario = st.radio("Koşul Seç", list(SCENARIOS.keys()))
    st.session_state.scenario = scenario

    p = SCENARIOS[scenario]["p"]
    mean = SCENARIOS[scenario]["mean"]
    expected = p * mean

    st.info(f"p = {p:.2f}  |  Ortalama Hasar = {fmt_tl(mean)}")
    st.success(f"Beklenen Hasar / Poliçe = {fmt_tl(expected)}")

    if st.button("⬅ Geri"):
        prev_step()

    if st.button("İleri ➜"):
        next_step()

# =========================================================
# ADIM 2 – PRİM BİLEŞENLERİ
# =========================================================

elif st.session_state.step == 2:

    st.subheader("Prim Bileşenleri")

    st.session_state.expense = st.slider("Gider Oranı (%)", 0, 50, 20) / 100
    st.session_state.profit = st.slider("Tampon / Kâr Oranı (%)", 0, 50, 10) / 100

    p = SCENARIOS[st.session_state.scenario]["p"]
    mean = SCENARIOS[st.session_state.scenario]["mean"]
    expected = p * mean

    suggested = expected * (1 + st.session_state.expense + st.session_state.profit)

    st.success(f"Önerilen Brüt Prim = {fmt_tl(suggested)}")

    if st.button("⬅ Geri"):
        prev_step()

    if st.button("İleri ➜"):
        next_step()

# =========================================================
# ADIM 3 – PRİM SEÇİMİ
# =========================================================

elif st.session_state.step == 3:

    st.subheader("Prim Düzeyi")

    st.session_state.premium_factor = st.slider("Önerilen brüt primin % kaçı?", 60, 160, 100)

    p = SCENARIOS[st.session_state.scenario]["p"]
    mean = SCENARIOS[st.session_state.scenario]["mean"]
    expected = p * mean
    suggested = expected * (1 + st.session_state.expense + st.session_state.profit)
    premium = suggested * (st.session_state.premium_factor / 100)

    st.success(f"Seçilen Prim = {fmt_tl(premium)}")

    if st.button("⬅ Geri"):
        prev_step()

    if st.button("İleri ➜"):
        next_step()

# =========================================================
# ADIM 4 – TALEP
# =========================================================

elif st.session_state.step == 4:

    st.subheader("Satış Varsayımı")

    st.session_state.base_policies = st.slider("Referans Satış (poliçe)", 500, 10000, 2000)
    st.session_state.sensitivity = st.slider("Fiyata Duyarlılık", 0.0, 3.0, 1.2)

    if st.button("⬅ Geri"):
        prev_step()

    if st.button("İleri ➜"):
        next_step()

# =========================================================
# ADIM 5 – SİMÜLASYON
# =========================================================

elif st.session_state.step == 5:

    st.subheader("Simülasyon")

    p = SCENARIOS[st.session_state.scenario]["p"]
    mean = SCENARIOS[st.session_state.scenario]["mean"]
    expected = p * mean
    suggested = expected * (1 + st.session_state.expense + st.session_state.profit)
    premium = suggested * (st.session_state.premium_factor / 100)

    if st.button("Bu primle piyasaya çık"):
        n_policies = demand_from_premium(
            premium,
            st.session_state.base_policies,
            suggested,
            st.session_state.sensitivity
        )

        st.session_state.period += 1

        n_claims, total_loss = simulate_period(n_policies, p, mean)

        premium_income = n_policies * premium
        expense = premium_income * st.session_state.expense
        result = premium_income - total_loss - expense

        st.session_state.capital += result

        cr = (total_loss + expense) / premium_income if premium_income > 0 else 0

        st.session_state.history.append({
            "Dönem": st.session_state.period,
            "Poliçe": n_policies,
            "Prim Geliri": premium_income,
            "Toplam Hasar": total_loss,
            "Gider": expense,
            "UW Sonucu": result,
            "Combined Ratio": cr,
            "Sermaye": st.session_state.capital
        })

        st.rerun()

# =========================================================
# SONUÇLAR
# =========================================================

if st.session_state.history:

    df = pd.DataFrame(st.session_state.history)

    st.subheader("Sonuç Tablosu")
    st.dataframe(df, use_container_width=True)

    last = df.iloc[-1]

    st.subheader("🧠 Koç: Bu dönem ne oldu, bir sonraki adım ne olmalı?")

    if last["Combined Ratio"] < 1:
        st.success("Teknik kâr oluştu. Küçük fiyat indirimleri ile satış artırılabilir.")
    else:
        st.warning("Teknik zarar oluştu. Prim artırılmalı veya gider kontrolü yapılmalı.")

    st.line_chart(df.set_index("Dönem")[["Sermaye"]])
