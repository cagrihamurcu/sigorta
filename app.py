import streamlit as st
import numpy as np
import pandas as pd
from typing import Optional

st.set_page_config(page_title="Sigorta Temel Mantık Oyunu (Ders Modu)", layout="wide")

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
        st.session_state.step = 0  # 0: intro, 1-5: wizard

    if "capital0" not in st.session_state:
        st.session_state.capital0 = 1_000_000.0
        st.session_state.capital = st.session_state.capital0

    if "t" not in st.session_state:
        st.session_state.t = 0

    if "history" not in st.session_state:
        st.session_state.history = []

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

    # Quiz geçiş kontrolü
    if "quiz_ok" not in st.session_state:
        st.session_state.quiz_ok = {
            "intro": False,
            1: False,
            2: False,
            3: False,
            4: False,
        }

init_state()

# -----------------------------
# Senaryolar
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
# Başlık
# -----------------------------
st.title("🎮 Sigortacılığın Temel Mantığı (Adım Adım + Mini Soru)")

# Üst pano (oyun hissi)
colA, colB, colC, colD = st.columns(4)
colA.metric("Dönem", f"{st.session_state.t} / 12")
colB.metric("Sermaye", fmt_tl(st.session_state.capital))
colC.metric("Önerilen brüt prim", fmt_tl(suggested_gross))
colD.metric("Senin primin", fmt_tl(premium_choice))

# -----------------------------
# Navigasyon
# -----------------------------
def go_next():
    # intro -> 1, 1->2 ...
    if st.session_state.step == 0:
        st.session_state.step = 1
    else:
        st.session_state.step = min(5, st.session_state.step + 1)

def go_prev():
    if st.session_state.step == 1:
        st.session_state.step = 0
    else:
        st.session_state.step = max(0, st.session_state.step - 1)

# -----------------------------
# Sol panel: Oyun sıfırla
# -----------------------------
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

# -----------------------------
# INTRO (Amaç + Mantık + mini soru)
# -----------------------------
if st.session_state.step == 0:
    st.subheader("🚦 Başlangıç: Amaç ve Mantık (10 saniye)")
    st.markdown(
        """
**Bu oyunda ne yapıyorsun?**  
Her tur (dönem) için **prim** belirliyorsun. Prim → müşteri (poliçe) sayısını etkiliyor. Sonra hasarlar geliyor.  
Amaç: **12 dönem sonunda sermayeyi korumak ve mümkünse artırmak.**

**Sigortacılık mantığı (tek cümle):**  
> **Prim = beklenen hasar + gider + güvenlik/kâr payı**  
Beklenen hasar ise: **p × ortalama hasar**.

**Nasıl oynanır?**  
1) Risk senaryosunu seç  
2) Yüklemeleri belirle  
3) Primini seç  
4) Piyasa talebini ayarla  
5) Özetle ve 1 dönem oynat
        """
    )

    st.divider()
    st.write("✅ Mini Soru (devam etmek için):")
    ans = st.radio(
        "Beklenen hasar / poliçe hangi iki şeyin çarpımıdır?",
        ["ortalama hasar × gider", "hasar olasılığı (p) × ortalama hasar", "prim × müşteri sayısı"],
        index=0
    )

    if ans == "hasar olasılığı (p) × ortalama hasar":
        st.session_state.quiz_ok["intro"] = True
        st.success("Doğru! Beklenen hasar = p × ortalama hasar.")
    else:
        st.session_state.quiz_ok["intro"] = False
        st.warning("Tekrar dene. İpucu: p, hasar olasılığıdır.")

    st.button("İleri ➜", on_click=go_next, disabled=(not st.session_state.quiz_ok["intro"]), use_container_width=True)

# -----------------------------
# Wizard adımları başlıkları
# -----------------------------
steps_title = {
    1: "1) Risk Senaryosu",
    2: "2) Yüklemeler (Gider + Güvenlik/Kâr)",
    3: "3) Prim Kararı",
    4: "4) Piyasa (Talep)",
    5: "5) Özet & Oynat",
}

if st.session_state.step in [1, 2, 3, 4, 5]:
    st.subheader(f"🧭 {steps_title[st.session_state.step]}")
    st.progress((st.session_state.step) / 5)

# -----------------------------
# 1) Risk
# -----------------------------
if st.session_state.step == 1:
    st.markdown(
        """
Bu adımda riskin yapısını seçiyorsun.  
- **p:** hasar olasılığı  
- **Ortalama hasar:** hasar olursa tipik tutar
        """
    )

    st.session_state.scenario = st.radio(
        "Senaryo seç",
        list(SCENARIOS.keys()),
        index=list(SCENARIOS.keys()).index(st.session_state.scenario),
        horizontal=True
    )

    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss

    st.info(f"Seçimin: p = **{p_claim:.2f}**, ortalama hasar = **{fmt_tl(mean_loss)}**, beklenen hasar/poliçe = **{fmt_tl(expected_loss_per_policy)}**")

    st.divider()
    st.write("✅ Mini Soru (devam etmek için):")
    ans = st.radio(
        "Risk yükselirse (p ve/veya ortalama hasar artarsa) teknik prim ne olur?",
        ["Azalır", "Artar", "Değişmez"],
        index=0,
        key="q1"
    )
    st.session_state.quiz_ok[1] = (ans == "Artar")
    if st.session_state.quiz_ok[1]:
        st.success("Doğru. Risk maliyeti artınca teknik prim de artar.")
    else:
        st.warning("Tekrar dene. İpucu: Teknik prim = beklenen hasar.")

    nav1, nav2 = st.columns(2)
    nav1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    nav2.button("İleri ➜", on_click=go_next, disabled=(not st.session_state.quiz_ok[1]), use_container_width=True)

# -----------------------------
# 2) Yüklemeler
# -----------------------------
elif st.session_state.step == 2:
    st.markdown(
        """
**Teknik prim** sadece beklenen hasarı karşılar.  
Şirketin ayrıca **giderleri** ve **belirsizlik tamponu** vardır.
        """
    )

    st.session_state.expense_loading = st.slider("Gider yüklemesi (%)", 0, 50, int(st.session_state.expense_loading * 100), 1) / 100
    st.session_state.profit_loading = st.slider("Güvenlik/Kâr payı (%)", 0, 50, int(st.session_state.profit_loading * 100), 1) / 100

    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)

    st.success(
        f"Teknik prim (beklenen hasar): **{fmt_tl(expected_loss_per_policy)}**  \n"
        f"Önerilen brüt prim: **{fmt_tl(suggested_gross)}**"
    )

    st.divider()
    st.write("✅ Mini Soru (devam etmek için):")
    ans = st.radio(
        "Gider yüklemesini artırırsan brüt prim ne olur?",
        ["Azalır", "Artar", "Değişmez"],
        index=0,
        key="q2"
    )
    st.session_state.quiz_ok[2] = (ans == "Artar")
    if st.session_state.quiz_ok[2]:
        st.success("Doğru. Gider yüklemesi artarsa brüt prim artar.")
    else:
        st.warning("Tekrar dene. Brüt prim, teknik primin üstüne yüklemeler eklenerek oluşur.")

    nav1, nav2 = st.columns(2)
    nav1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    nav2.button("İleri ➜", on_click=go_next, disabled=(not st.session_state.quiz_ok[2]), use_container_width=True)

# -----------------------------
# 3) Prim kararı
# -----------------------------
elif st.session_state.step == 3:
    st.markdown(
        """
Şimdi “satış fiyatını” seçiyorsun: Önerilen brüt prime göre % kaç?  
- Düşük fiyat → daha çok müşteri, ama zarar riski  
- Yüksek fiyat → daha az müşteri, ama zarar riski azalabilir
        """
    )

    st.session_state.premium_factor = st.slider("Prim düzeyi (önerilenin %’si)", 60, 160, int(st.session_state.premium_factor), 5)

    # güncelle
    p_claim = SCENARIOS[st.session_state.scenario]["p_claim"]
    mean_loss = SCENARIOS[st.session_state.scenario]["mean_loss"]
    expected_loss_per_policy = p_claim * mean_loss
    suggested_gross = expected_loss_per_policy * (1 + st.session_state.expense_loading + st.session_state.profit_loading)
    premium_choice = suggested_gross * (st.session_state.premium_factor / 100.0)

    st.info(f"Senin primin: **{fmt_tl(premium_choice)}** (önerilen: {fmt_tl(suggested_gross)})")

    st.divider()
    st.write("✅ Mini Soru (devam etmek için):")
    ans = st.radio(
        "Prim çok düşerse en olası etki nedir?",
        ["Müşteri artar ama zarar riski artar", "Müşteri azalır ve zarar riski azalır", "Hiçbir şey değişmez"],
        index=0,
        key="q3"
    )
    st.session_state.quiz_ok[3] = (ans == "Müşteri artar ama zarar riski artar")
    if st.session_state.quiz_ok[3]:
        st.success("Doğru. Ucuz fiyat talebi artırabilir ama beklenmeyen hasarlar sermayeyi eritebilir.")
    else:
        st.warning("Tekrar dene. İpucu: fiyat ↓ → talep ↑, ama prim yetersiz kalabilir.")

    nav1, nav2 = st.columns(2)
    nav1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    nav2.button("İleri ➜", on_click=go_next, disabled=(not st.session_state.quiz_ok[3]), use_container_width=True)

# -----------------------------
# 4) Piyasa
# -----------------------------
elif st.session_state.step == 4:
    st.markdown(
        """
Piyasa ayarı: Bu fiyata kaç müşteri gelir?  
- **Pazar büyüklüğü:** Prim makulse geleceğini düşündüğümüz poliçe sayısı  
- **Fiyata duyarlılık:** Prim artınca müşterinin kaçma derecesi
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
    st.write("✅ Mini Soru (devam etmek için):")
    ans = st.radio(
        "Fiyata duyarlılık çok yüksekse (örn. 3), prim artınca ne olur?",
        ["Talep daha hızlı düşer", "Talep artar", "Talep değişmez"],
        index=0,
        key="q4"
    )
    st.session_state.quiz_ok[4] = (ans == "Talep daha hızlı düşer")
    if st.session_state.quiz_ok[4]:
        st.success("Doğru. Duyarlılık yüksekse küçük fiyat artışı bile müşteri kaybettirir.")
    else:
        st.warning("Tekrar dene. İpucu: duyarlılık ↑ → fiyat artışına tepki ↑")

    nav1, nav2 = st.columns(2)
    nav1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    nav2.button("İleri ➜", on_click=go_next, disabled=(not st.session_state.quiz_ok[4]), use_container_width=True)

# -----------------------------
# 5) Özet & Oynat
# -----------------------------
elif st.session_state.step == 5:
    st.markdown("Seçimlerini gör ve **1 dönem oynat**. Sonuçlar altta tablo ve grafiklerde görünecek.")

    st.session_state.seed = int(st.number_input("Rastgelelik (seed) (opsiyonel)", min_value=0, value=int(st.session_state.seed), step=1))

    summary = {
        "Senaryo": st.session_state.scenario,
        "p": p_claim,
        "Ortalama hasar": fmt_tl(mean_loss),
        "Beklenen hasar/poliçe": fmt_tl(expected_loss_per_policy),
        "Gider (%)": f"{int(st.session_state.expense_loading*100)}",
        "Kâr/Güvenlik (%)": f"{int(st.session_state.profit_loading*100)}",
        "Önerilen brüt prim": fmt_tl(suggested_gross),
        "Senin primin": fmt_tl(premium_choice),
        "Pazar büyüklüğü": f"{st.session_state.base_policies:,}",
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

        if premium_income == 0:
            comment = "Prim çok yüksek → talep düştü → poliçe yok. Öğrenme için primini düşürmeyi dene."
        elif combined_ratio < 1.0:
            comment = "✅ Teknik kâr: Combined Ratio < 1. (Prim/hasar dengesi bu tur iyi.)"
        else:
            comment = "⚠️ Teknik zarar: Combined Ratio > 1. (Prim yetersiz kaldı ya da hasar yüksek geldi.)"

        st.session_state.last_commentary = comment

        st.session_state.history.append({
            "Dönem": st.session_state.t,
            "Poliçe": n_policies,
            "Hasar Adedi": n_claims,
            "Prim Geliri": premium_income,
            "Toplam Hasar": total_loss,
            "Gider": expense,
            "UW Sonucu": uw_result,
            "Combined Ratio": combined_ratio,
            "Sermaye": st.session_state.capital
        })

    nav1, nav2 = st.columns(2)
    nav1.button("⬅ Geri", on_click=go_prev, use_container_width=True)
    nav2.button("▶️ 1 Dönem Oynat", on_click=play_one_period, use_container_width=True)

# -----------------------------
# Sonuçlar her zaman görünür
# -----------------------------
st.divider()

if st.session_state.last_commentary:
    st.success(st.session_state.last_commentary)

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)

    st.subheader("📊 Sonuç Tablosu")
    st.dataframe(df, use_container_width=True)

    st.subheader("📈 Grafikler")
    st.line_chart(df.set_index("Dönem")[["Prim Geliri", "Toplam Hasar"]])
    st.line_chart(df.set_index("Dönem")[["Combined Ratio"]])
    st.line_chart(df.set_index("Dönem")[["Sermaye"]])
else:
    st.info("Oyuna başlamak için üstteki adımları takip et. Her adımın sonunda mini soru var; doğru cevapla ilerleyebilirsin.")
