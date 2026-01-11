import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

# --- AYARLAR ---
DOSYA_ADI = "butce.csv"
st.set_page_config(page_title="Kişisel Bütçe Takip", layout="wide", page_icon="💰")

# --- FONKSİYONLAR ---
def veri_yukle():
    if not os.path.exists(DOSYA_ADI):
        df = pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
        df.to_csv(DOSYA_ADI, index=False)
        return df
    else:
        return pd.read_csv(DOSYA_ADI)

def veri_kaydet(yeni_df):
    yeni_df.to_csv(DOSYA_ADI, index=False)

# --- ANA VERİYİ YÜKLE ---
df = veri_yukle()

# --- SOL MENÜ (VERİ GİRİŞİ & SİLME) ---
with st.sidebar:
    st.header("💸 Veri Girişi")
    
    # Ekleme Formu
    tarih_giris = st.date_input("Tarih", datetime.today())
    tur_giris = st.selectbox("İşlem Türü", ["Gider", "Gelir"])
    
    if tur_giris == "Gider":
        kategoriler = ["Kredi Kartı", "Mutfak", "Fatura", "Kira", "Ulaşım", "Eğlence", "Sağlık", "Diğer"]
    else:
        kategoriler = ["Maaş", "Ek Gelir", "Yatırım Getirisi", "Borç Alacak"]
        
    kategori_giris = st.selectbox("Kategori", kategoriler)
    aciklama_giris = st.text_input("Açıklama (Opsiyonel)")
    tutar_giris = st.number_input("Tutar (TL)", min_value=0.0, format="%.2f")
    
    if st.button("Kaydet ✅", type="primary"):
        if tutar_giris > 0:
            # Tarih dönüşümleri
            ay_isimleri = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                           7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}
            
            yeni_satir = pd.DataFrame({
                "Tarih": [tarih_giris],
                "Ay": [ay_isimleri[tarih_giris.month]],
                "Yıl": [tarih_giris.year],
                "Kategori": [kategori_giris],
                "Aciklama": [aciklama_giris],
                "Tutar": [tutar_giris],
                "Tur": [tur_giris]
            })
            
            df = pd.concat([df, yeni_satir], ignore_index=True)
            veri_kaydet(df)
            st.success("Kaydedildi!")
            st.rerun() # Sayfayı yenile
        else:
            st.warning("Tutar 0 olamaz.")

    # --- SİLME BÖLÜMÜ ---
    st.divider()
    st.header("🗑️ Kayıt Sil")
    
    if not df.empty:
        # Silinecek kaydı seçtiren kutu (Ters sıralı ki en son eklenen en üstte olsun)
        # Format: Index No - Tarih - Kategori - Tutar
        df_gosterim = df.copy()
        df_gosterim = df_gosterim.sort_index(ascending=False)
        
        secenekler = df_gosterim.apply(lambda x: f"ID: {x.name} | {x['Tarih']} | {x['Kategori']} | {x['Tutar']} TL", axis=1)
        
        silinecek_id_str = st.selectbox("Silinecek İşlemi Seçin:", secenekler)
        
        if st.button("Seçili Kaydı Sil 🚨"):
            # ID'yi metinden ayıkla (Örn: "ID: 5 | ..." -> 5'i al)
            silinecek_index = int(silinecek_id_str.split("|")[0].replace("ID:", "").strip())
            
            # Veriyi sil ve kaydet
            df = df.drop(silinecek_index)
            veri_kaydet(df)
            st.success("Kayıt silindi!")
            st.rerun()
    else:
        st.info("Silinecek veri yok.")

# --- ANA EKRAN (DASHBOARD) ---
st.title("📊 Kişisel Bütçe Dashboard")

if not df.empty:
    # FİLTRELEME
    col1, col2 = st.columns(2)
    mevcut_yillar = sorted(df["Yıl"].unique().tolist(), reverse=True)
    mevcut_aylar = ["Tümü"] + list(df["Ay"].unique())
    
    secilen_yil = col1.selectbox("Yıl", mevcut_yillar)
    secilen_ay = col2.selectbox("Ay", mevcut_aylar)
    
    df_filter = df[df["Yıl"] == secilen_yil]
    if secilen_ay != "Tümü":
        df_filter = df_filter[df_filter["Ay"] == secilen_ay]

    # KARTLAR
    top_gelir = df_filter[df_filter["Tur"] == "Gelir"]["Tutar"].sum()
    top_gider = df_filter[df_filter["Tur"] == "Gider"]["Tutar"].sum()
    kalan = top_gelir - top_gider
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Gelir", f"{top_gelir:,.2f} ₺")
    k2.metric("Gider", f"{top_gider:,.2f} ₺", delta_color="inverse")
    k3.metric("Kalan", f"{kalan:,.2f} ₺", delta=f"{kalan:,.2f} ₺")

    st.divider()

    # GRAFİKLER
    g1, g2 = st.columns(2)
    
    with g1:
        st.subheader("Gider Dağılımı")
        df_gider = df_filter[df_filter["Tur"] == "Gider"]
        if not df_gider.empty:
            fig = px.pie(df_gider, values="Tutar", names="Kategori", hole=0.5)
            st.plotly_chart(fig, use_container_width=True)
            
    with g2:
        st.subheader("Gelir vs Gider")
        df_ozet = df_filter.groupby("Tur")["Tutar"].sum().reset_index()
        if not df_ozet.empty:
            fig2 = px.bar(df_ozet, x="Tur", y="Tutar", color="Tur", 
                          color_discrete_map={"Gelir": "#00CC96", "Gider": "#EF553B"})
            st.plotly_chart(fig2, use_container_width=True)

    # TABLO
    st.subheader("📋 Kayıtlar")
    st.dataframe(df_filter.sort_index(ascending=False), use_container_width=True)

else:
    st.info("Veri girişi bekleniyor...")