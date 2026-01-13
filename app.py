# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import plotly.express as px
import os
import re

# --------------------------------------------------
# SAYFA AYARLARI
# --------------------------------------------------
st.set_page_config(
    page_title="Akıllı Bütçe",
    page_icon="📊",
    layout="wide"
)

# --------------------------------------------------
# DOSYA AYARLARI
# --------------------------------------------------
DATA_FILE = "veriler.csv"
SABIT_SIFRE = "7855"

# --------------------------------------------------
# YARDIMCI FONKSİYONLAR
# --------------------------------------------------
def parse_tutar(text: str) -> float:
    """
    Kullanıcıdan gelen tutarı güvenli şekilde float'a çevirir
    5890,00 -> 5890.00
    """
    try:
        x = text.replace("₺", "").replace("TL", "").strip()
        x = x.replace(".", "").replace(",", ".")
        return float(x)
    except:
        return 0.0


def veri_cek() -> pd.DataFrame:
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=[
            "Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"
        ])
    df = pd.read_csv(DATA_FILE)
    df["Tutar"] = df["Tutar"].astype(float)
    return df


def veri_kaydet(df: pd.DataFrame):
    df.to_csv(DATA_FILE, index=False)


# --------------------------------------------------
# ŞİFRE KONTROLÜ
# --------------------------------------------------
def sifre_kontrol():
    if st.session_state.get("auth", False):
        return True

    st.title("🔐 Giriş")
    sifre = st.text_input("Şifre", type="password")
    if st.button("Giriş"):
        if sifre == SABIT_SIFRE:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Şifre yanlış")
    return False


if not sifre_kontrol():
    st.stop()

# --------------------------------------------------
# VERİ YÜKLE
# --------------------------------------------------
df = veri_cek()

AY_MAP = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
    5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
    9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
}

# --------------------------------------------------
# SIDEBAR - KAYIT EKLE
# --------------------------------------------------
with st.sidebar:
    st.header("➕ İşlem Ekle")

    tarih = st.date_input("Tarih", datetime.today())
    tur = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"])

    if tur == "Gider":
        kategoriler = ["Kredi Kartı", "Kira", "Fatura", "Market", "Ulaşım", "Sağlık", "Diğer"]
    elif tur == "Gelir":
        kategoriler = ["Maaş", "Ek Gelir", "Prim"]
    else:
        kategoriler = ["Altın", "Gümüş", "Döviz", "Borsa", "Fon"]

    kategori = st.selectbox("Kategori", kategoriler)
    aciklama = st.text_input("Açıklama")

    taksit_sayisi = 1
    if tur == "Gider":
        if st.checkbox("Taksitli mi?"):
            taksit_sayisi = st.slider("Taksit Sayısı", 2, 12, 3)

    tutar_text = st.text_input("Toplam Tutar (₺)", placeholder="Örn: 5890,00")
    tutar = parse_tutar(tutar_text)

    if st.button("Kaydet 💾"):
        if tutar <= 0:
            st.error("Geçerli bir tutar girin")
        else:
            yeni_kayitlar = []

            if taksit_sayisi > 1:
                aylik = round(tutar / taksit_sayisi, 2)

                for i in range(taksit_sayisi):
                    t = tarih + relativedelta(months=i)
                    yeni_kayitlar.append({
                        "Tarih": t.strftime("%Y-%m-%d"),
                        "Ay": AY_MAP[t.month],
                        "Yıl": t.year,
                        "Kategori": kategori,
                        "Aciklama": f"{aciklama} ({i+1}/{taksit_sayisi}. Taksit)",
                        "Tutar": aylik,
                        "Tur": tur
                    })
            else:
                yeni_kayitlar.append({
                    "Tarih": tarih.strftime("%Y-%m-%d"),
                    "Ay": AY_MAP[tarih.month],
                    "Yıl": tarih.year,
                    "Kategori": kategori,
                    "Aciklama": aciklama,
                    "Tutar": float(tutar),
                    "Tur": tur
                })

            df = pd.concat([df, pd.DataFrame(yeni_kayitlar)], ignore_index=True)
            veri_kaydet(df)
            st.success("Kayıt eklendi")
            st.rerun()

# --------------------------------------------------
# ANA EKRAN
# --------------------------------------------------
st.title("📊 Akıllı Bütçe")

if df.empty:
    st.info("Henüz kayıt yok")
    st.stop()

yillar = sorted(df["Yıl"].unique(), reverse=True)
aylar = ["Tümü"] + list(df["Ay"].unique())

c1, c2 = st.columns(2)
sec_yil = c1.selectbox("Yıl", yillar)
sec_ay = c2.selectbox("Ay", aylar)

df_f = df[df["Yıl"] == sec_yil]
if sec_ay != "Tümü":
    df_f = df_f[df_f["Ay"] == sec_ay]

top_gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
top_gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
top_yatirim = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()
kalan = top_gelir - (top_gider + top_yatirim)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Gelir", f"{top_gelir:,.2f} ₺")
m2.metric("Gider", f"{top_gider:,.2f} ₺")
m3.metric("Yatırım", f"{top_yatirim:,.2f} ₺")
m4.metric("Kalan", f"{kalan:,.2f} ₺")

st.divider()

fig = px.pie(
    df_f[df_f["Tur"] != "Gelir"],
    values="Tutar",
    names="Kategori",
    title="Harcama Dağılımı",
    hole=0.4
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("📋 Tüm Kayıtlar")
st.dataframe(
    df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}),
    use_container_width=True
)
