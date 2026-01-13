import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="Akıllı Bütçe v2", layout="wide", page_icon="💰")

# Karanlık Mod Uyumlu Dinamik Tasarım
st.markdown("""
    <style>
    /* Metrik Kartları */
    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.08);
        padding: 20px !important;
        border-radius: 20px !important;
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    /* Butonlar */
    .stButton>button {
        width: 100%;
        border-radius: 12px !important;
        height: 3em;
        font-weight: bold;
        background: linear-gradient(135deg, #007bff, #0056b3);
        color: white !important;
    }
    /* Sidebar yumuşatma */
    [data-testid="stSidebar"] {
        background-color: rgba(128, 128, 128, 0.02);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. GOOGLE SHEETS BAĞLANTISI ---
@st.cache_resource
def get_gspread_client():
    try:
        # Streamlit Cloud'da secrets.toml, yerelde credentials.json kullanır
        if "service_account" in st.secrets:
            creds_info = dict(st.secrets["service_account"])
        else:
            import json
            with open("credentials.json") as f:
                creds_info = json.load(f)
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ Google Sheets Bağlantı Hatası: {e}")
        return None

def veri_cek():
    client = get_gspread_client()
    if not client: return pd.DataFrame()
    try:
        sh = client.open("Butce_Veritabanı") # Tablo adın
        worksheet = sh.get_worksheet(0) # İlk sayfa
        data = worksheet.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        df = pd.DataFrame(data[1:], columns=data[0])
        # Tutar temizleme
        df["Tutar"] = df["Tutar"].str.replace('.', '').str.replace(',', '.').astype(float)
        return df
    except: return pd.DataFrame()

# --- 3. PİYASA FİYATLARI (SIDEBAR) ---
with st.sidebar:
    st.header("💰 Piyasa Fiyatları")
    # Ayarlar sayfasından veya manuel girişten fiyatları alalım
    gold_price = st.number_input("Gr Altın (₺)", value=6400.0, step=10.0)
    silver_price = st.number_input("Gr Gümüş (₺)", value=80.0, step=1.0)
    st.divider()

    # --- YENİ İŞLEM EKLE ---
    st.header("💸 İşlem Ekle")
    with st.form("ekle_form", clear_on_submit=True):
        tarih_giris = st.date_input("Tarih", datetime.today())
        tur_giris = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"])
        
        # Dinamik kategoriler
        if tur_giris == "Gider": kats = ["Mutfak", "Market", "Fatura", "Kira", "Ulaşım", "Sağlık", "Diğer"]
        elif tur_giris == "Gelir": kats = ["Maaş", "Ek Gelir", "Prim", "Borç Alacak"]
        else: kats = ["Altın", "Gümüş", "Döviz", "Borsa", "Fon", "Bitcoin"]
        
        kategori_giris = st.selectbox("Kategori", kats)
        
        miktar_notu = ""
        if tur_giris == "Yatırım":
            miktar = st.text_input("Miktar (Örn: 5 Gram)")
            if miktar: miktar_notu = f"[{miktar}] "
            
        aciklama_giris = st.text_input("Açıklama")
        tutar_giris = st.number_input("Tutar (₺)", min_value=0.0)
        
        is_taksit = st.checkbox("Taksitli mi? (Sadece Gider)")
        taksit_sayisi = st.slider("Taksit Sayısı", 2, 12, 3) if is_taksit else 1
        
        submit = st.form_submit_button("KAYDET")
        
        if submit and tutar_giris > 0:
            client = get_gspread_client()
            sh = client.open("Butce_Veritabanı").get_worksheet(0)
            
            payload = []
            ay_map = {1:"Ocak", 2:"Şubat", 3:"Mart", 4:"Nisan", 5:"Mayıs", 6:"Haziran", 
                      7:"Temmuz", 8:"Ağustos", 9:"Eylül", 10:"Ekim", 11:"Kasım", 12:"Aralık"}
            
            if is_taksit and tur_giris == "Gider":
                t_tutar = tutar_giris / taksit_sayisi
                for i in range(taksit_sayisi):
                    y_tarih = tarih_giris + relativedelta(months=i)
                    payload.append([str(y_tarih.strftime("%Y-%m-%d")), ay_map[y_tarih.month], str(y_tarih.year), 
                                    kategori_giris, f"{aciklama_giris} ({i+1}/{taksit_sayisi} Taksit)", 
                                    f"{t_tutar:.2f}".replace('.', ','), tur_giris])
            else:
                final_desc = miktar_notu + aciklama_giris
                payload.append([str(tarih_giris), ay_map[tarih_giris.month], str(tarih_giris.year), 
                                kategori_giris, final_desc, f"{tutar_giris:.2f}".replace('.', ','), tur_giris])
            
            sh.append_rows(payload)
            st.success("İşlem başarıyla kaydedildi!")
            st.rerun()

# --- 4. DASHBOARD ANA EKRAN ---
df = veri_cek()

if not df.empty:
    # Üst Filtreler
    c_f1, c_f2 = st.columns(2)
    yillar = sorted(df["Yıl"].unique().tolist(), reverse=True)
    aylar = ["Tümü"] + list(df["Ay"].unique())
    sec_yil = c_f1.selectbox("Yıl Seçin", yillar)
    sec_ay = c_f2.selectbox("Ay Seçin", aylar)
    
    df_f = df[df["Yıl"] == str(sec_yil)]
    if sec_ay != "Tümü": df_f = df_f[df_f["Ay"] == sec_ay]

    # --- MATEMATİKSEL HESAPLAMALAR ---
    top_gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    top_gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    
    # Yatırım Maliyet vs Güncel Değer
    df_yatirim = df_f[df_f["Tur"] == "Yatırım"].copy()
    yatirim_maliyet = df_yatirim["Tutar"].sum()
    
    def guncel_deger_hesapla(row):
        desc = str(row["Aciklama"])
        kat = str(row["Kategori"]).lower()
        match = re.search(r'\[([\d\.,]+)', desc)
        if match:
            qty = float(match.group(1).replace(',', '.'))
            if "altın" in kat: return qty * gold_price
            if "gümüş" in kat: return qty * silver_price
        return row["Tutar"]

    if not df_yatirim.empty:
        df_yatirim["Guncel"] = df_yatirim.apply(guncel_deger_hesapla, axis=1)
        yatirim_guncel_toplam = df_yatirim["Guncel"].sum()
    else:
        yatirim_guncel_toplam = 0

    kalan_nakit = top_gelir - (top_gider + yatirim_maliyet)

    # Özet Kartları
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Toplam Gelir", f"{top_gelir:,.2f} ₺")
    m2.metric("Toplam Gider", f"{top_gider:,.2f} ₺", delta_color="inverse")
    m3.metric("Yatırım Değeri", f"{yatirim_guncel_toplam:,.2f} ₺", delta=f"{yatirim_guncel_toplam-yatirim_maliyet:,.2f} ₺")
    m4.metric("Kalan Nakit", f"{kalan_nakit:,.2f} ₺")

    st.divider()

    # Grafikler
    t1, t2 = st.tabs(["📊 Analizler", "📋 Kayıt Listesi"])
    with t1:
        g1, g2 = st.columns(2)
        with g1:
            if not df_f[df_f["Tur"] == "Gider"].empty:
                fig_pie = px.pie(df_f[df_f["Tur"] == "Gider"], values="Tutar", names="Kategori", hole=0.4, title="Harcama Dağılımı")
                st.plotly_chart(fig_pie, use_container_width=True)
        with g2:
            fig_bar = px.bar(df_f.groupby("Tur")["Tutar"].sum().reset_index(), x="Tur", y="Tutar", color="Tur", title="Gelir/Gider Dengesi")
            st.plotly_chart(fig_bar, use_container_width=True)
    
    with t2:
        st.dataframe(df_f.sort_values("Tarih", ascending=False), use_container_width=True)

else:
    st.info("Henüz veri bulunamadı veya tablo bağlantısı kuruluyor...")
