import streamlit as st
import numpy as np
import pandas as pd
from typing import Optional

st.set_page_config(page_title="Sigorta Temel Simülasyon Oyunu", layout="wide")

# -----------------------------
# Oyun mantığı (çok basit)
# -----------------------------
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

def fmt_tl(x: float) -> str:
    return f"{x:,.0f} TL"

# -----------------------------
# State
# -----------------------------
if "initialized" not in st.session_state:
    st.session_state.initialized = False

if "t" not in st.session_state:
    st.session_state.t = 0
    st.session_state.capital0 = 1_000_000.0
    st.session_state.capital = st.session_state.capital0
    st.session_state.history = []

if "last_commentary" not in st.session_state:
    st.session_state.last_commentary = ""

# -----------------------------
# Başlık + Oyun açıklaması (oyuncu yönlendirmesi)
# -----------------------------
st.title("🎮 Sigortacılık Mantığı Oyunu: Prim–Hasar–Sermaye")
st.caption("Amaç: 12 dönem boyunca şirketi batırmadan sermayeyi büyütmek. Her dönem prim belirle, müşteri (poliçe) sayısı oluşsun, hasarlar gelsin, sonucu gör.")

with st.expander("📌 Nasıl oynanır? (30 saniye)", expanded=True):
    st.markdown(
        """
**1) Soldan prim kararını ver:**  
- “Önerilen brüt prim” sana referans.  
- Daha düşük prim → daha çok müşteri ama zarar riski.  
- Daha yüksek prim → daha az müşteri ama kârlılık ihtimali.

**2) “▶️ 1 Dönem Oynat” butonuna bas.**  
Her basış 1 dönem ilerletir.

**3) Sonuçları oku:**  
- **Combined Ratio < 1** ise teknik kâr, **> 1** ise teknik zarar.  
- Sermaye düşerse batarsın (ders: fiyatlama + havuz mantığı).
        """
    )

# -----------------------------
# Sol panel: Oyun kontrol paneli (minimum, anlaşılır)
# -----------------------------
with st.sidebar:
    st.header("🎛 Oyun Kontrol Paneli")

    # Basit risk parametreleri
    st.subheader("1) Risk (Senaryo)")
    scenario = st.selectbox(
        "Senaryo seç",
        ["Normal", "Daha Riskli", "Daha Az Riskli"],
        index=0
    )

    if scenario == "Normal":
        p_claim = 0.08
        mean_loss = 25_000
    elif scenario == "Daha Riskli":
        p_claim = 0.12
        mean_loss = 32_000
    else:
        p_claim = 0.05
        mean_loss = 20_000

    st.write(f"Hasar olasılığı (p): **{p_claim:.2f}**")
    st.write(f"Ortalama hasar: **{fmt_tl(mean_loss)}**")

    st.subheader("2) Yüklemeler")
    expense_loading = st.slider("Gider yüklemesi (%)", 0, 50, 20, 1) / 100
    profit_loading = st.slider("Güvenlik/Kâr payı (%)", 0, 50, 10, 1) / 100

    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + expense_loading + profit_loading)

    st.divider()
    st.subheader("3) Prim Kararın")
    st.info(f"Önerilen brüt prim: **{fmt_tl(suggested_gross)} / poliçe**")

    # Oyuncuya kolaylık: prim “önerilenin % kaçı?”
    premium_factor = st.slider("Prim düzeyi (önerilenin %’si)", 60, 160, 100, 5)
    premium_choice = float(suggested_gross) * (premium_factor / 100)

    st.write("Senin primin:", f"**{fmt_tl(premium_choice)} / poliçe**")

    st.divider()
    st.subheader("4) Piyasa (Talep)")
    base_policies = st.slider("Piyasa büyüklüğü (referans poliçe)", 200, 10000, 2000, 100)
    sensitivity = st.slider("Fiyata duyarlılık", 0.0, 3.0, 1.2, 0.1)

    st.divider()
    st.subheader("5) Oynat / Sıfırla")
    seed = st.number_input("Rastgelelik (seed) (opsiyonel)", min_value=0, value=0, step=1)

    play_one = st.button("▶️ 1 Dönem Oynat", use_container_width=True)
    auto_demo = st.checkbox("Açılışta 1 örnek tur otomatik oynat", value=True)

    reset = st.button("🔄 Oyunu Sıfırla", use_container_width=True)

# Reset
if reset:
    st.session_state.t = 0
    st.session_state.capital = st.session_state.capital0
    st.session_state.history = []
    st.session_state.last_commentary = ""
    st.session_state.initialized = False
    st.rerun()

# -----------------------------
# Oynatma fonksiyonu (tek yerden)
# -----------------------------
def run_one_period(premium_choice: float, p_claim: float, mean_loss: float,
                   expense_loading: float, base_policies: int, sensitivity: float,
                   suggested_gross: float, seed: int):

    st.session_state.t += 1

    n_policies = demand_from_premium(
        premium=premium_choice,
        base_policies=base_policies,
        reference_premium=suggested_gross if suggested_gross > 0 else 1.0,
        sensitivity=sensitivity
    )

    n_claims, total_loss = simulate_period(
        n_policies=n_policies,
        p_claim=p_claim,
        mean_loss=mean_loss,
        seed=(seed + st.session_state.t) if seed != 0 else None
    )

    premium_income = float(n_policies) * float(premium_choice)
    expense = premium_income * expense_loading
    uw_result = premium_income - total_loss - expense

    st.session_state.capital += uw_result

    loss_ratio = (total_loss / premium_income) if premium_income > 0 else 0.0
    expense_ratio = (expense / premium_income) if premium_income > 0 else 0.0
    combined_ratio = loss_ratio + expense_ratio

    # Kısa yorum (oyuncu neyi anlasın?)
    if premium_income == 0:
        comment = "Prim çok yüksek olduğu için talep sıfıra yakınladı. Poliçe yoksa hasar da yok, ama oyun ilerlemiyor."
    else:
        if combined_ratio < 1.0:
            comment = "Bu tur teknik kâr ettin (Combined Ratio < 1). Prim seviyesi ve risk gerçekleşmesi bu tur lehine oldu."
        else:
            comment = "Bu tur teknik zarar ettin (Combined Ratio > 1). Ya prim düşük kaldı ya da hasar gerçekleşmesi yüksek geldi."

    # Öğretici bir cümle daha:
    if premium_choice < suggested_gross * 0.9:
        comment += " Prim, önerilen seviyenin epey altında: müşteri artar ama sermaye erime riski yükselir."
    elif premium_choice > suggested_gross * 1.1:
        comment += " Prim, önerilen seviyenin üstünde: zarar riski azalır ama müşteri kaybı yaşayabilirsin."
    else:
        comment += " Prim, önerilen seviyeye yakın: beklenen dengeyi hedefliyorsun."

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

# -----------------------------
# Açılışta otomatik 1 tur (oyuncu “kendini oynatıyor” hissi)
# -----------------------------
if (not st.session_state.initialized) and auto_demo:
    st.session_state.initialized = True
    # Açılış turu: önerilen primin %100'ü ile oynat
    run_one_period(
        premium_choice=premium_choice,
        p_claim=p_claim,
        mean_loss=mean_loss,
        expense_loading=expense_loading,
        base_policies=base_policies,
        sensitivity=sensitivity,
        suggested_gross=suggested_gross,
        seed=int(seed)
    )

# Butonla oynatma
if play_one:
    run_one_period(
        premium_choice=premium_choice,
        p_claim=p_claim,
        mean_loss=mean_loss,
        expense_loading=expense_loading,
        base_policies=base_policies,
        sensitivity=sensitivity,
        suggested_gross=suggested_gross,
        seed=int(seed)
    )

# -----------------------------
# Ana ekran: skorlar ve “ne yapacağını söyle”
# -----------------------------
colA, colB, colC, colD = st.columns(4)
colA.metric("Dönem", f"{st.session_state.t} / 12")
colB.metric("Sermaye", fmt_tl(st.session_state.capital))
colC.metric("Hedef", "Sermayeyi artır")
if st.session_state.t >= 1:
    last_cr = st.session_state.history[-1]["Combined Ratio"]
    colD.metric("Son Combined Ratio", f"{last_cr:.2f}")
else:
    colD.metric("Son Combined Ratio", "-")

if st.session_state.last_commentary:
    st.success(st.session_state.last_commentary)

# Oyuncuya “şimdi ne yapayım?” mesajı
if st.session_state.t == 0:
    st.warning("Başlamak için soldan prim düzeyini seç ve **▶️ 1 Dönem Oynat** butonuna bas.")
elif st.session_state.t < 12:
    st.info("Bir sonraki tur için prim düzeyini değiştirip tekrar **▶️ 1 Dönem Oynat** yap. Amaç: Combined Ratio’yu 1’in altında tutarak sermayeyi büyütmek.")
else:
    if st.session_state.capital > st.session_state.capital0:
        st.balloons()
        st.success("🎉 Oyun bitti: Sermayeyi büyüttün! (Temel ders: doğru prim + havuz etkisi)")
    else:
        st.error("Oyun bitti: Sermaye düştü. (Temel ders: düşük prim / kötü şans birleşince şirket zarar eder)")

# -----------------------------
# Sonuç tablosu + grafikler
# -----------------------------
if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)

    st.subheader("📊 Dönem Sonuçları")
    st.dataframe(df, use_container_width=True)

    st.subheader("📈 Trendler")
    st.line_chart(df.set_index("Dönem")[["Prim Geliri", "Toplam Hasar"]])
    st.line_chart(df.set_index("Dönem")[["Combined Ratio"]])
    st.line_chart(df.set_index("Dönem")[["Sermaye"]])
