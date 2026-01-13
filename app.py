import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

# --- 1. SAYFA AYARLARI VE TASARIM ---
st.set_page_config(page_title="Bütçe Yönetimi", layout="wide", page_icon="📈")

# Modern Arayüz İçin Özel CSS (Karanlık Mod Uyumlu)
st.markdown("""
    <style>
    /* Ana Konteynırı Yumuşat */
    .main { background-color: transparent; }
    
    /* Metrik Kartlarını (Özet) Güzelleştir */
    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 15px !important;
        border-radius: 20px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        transition: 0.3s;
    }
    div[data-testid="stMetric"]:hover { transform: translateY(-3px); }

    /* Butonları Modernleştir */
    .stButton>button {
        width: 100%;
        border-radius: 12px !important;
        height: 3em;
        background: linear-gradient(135deg, #007bff, #0056b3);
        color: white !important;
        font-weight: bold;
        border: none;
    }
    
    /* Sidebar'ı düzenle */
    [data-testid="stSidebar"] { padding: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. GÜVENLİK (Giriş Sistemi) ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True
    
    col_a, col_b, col_c = st.columns([1,2,1])
    with col_b:
        st.title("🔒 Giriş Gerekli")
        pwd = st.text_input("Şifrenizi Girin", type="password")
        if st.button("Giriş Yap"):
            # Şifreyi Streamlit Cloud Secrets'tan (L_SIFRE) veya manuel kontrol et
            if pwd == st.secrets.get("LOGIN_SIFRE", "1234"): 
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("😕 Yanlış Şifre")
    return False

if not check_password():
    st.stop()

# --- 3. GOOGLE SHEETS BAĞLANTISI ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Streamlit Cloud üzerinde Secrets -> [service_account] altına JSON bilgilerini eklemelisin
    creds_dict = dict(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# Verileri Çek
def veri_yukle():
    try:
        client = get_gspread_client()
        sheet = client.open("Butce_Veritabanı").sheet1 # Dosya adını kontrol et
        data = sheet.get_all_values()
        if not data:
            return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
        df = pd.DataFrame(data[1:], columns=data[0])
        df["Tutar"] = pd.to_numeric(df["Tutar"].str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return pd.DataFrame()

# --- 4. ANA EKRAN (Dashboard) ---
df = veri_yukle()

st.title("💰 Akıllı Bütçe Dashboard")

if not df.empty:
    # Filtreleme (Yıl ve Ay)
    yillar = sorted(df["Yıl"].unique().tolist(), reverse=True)
    aylar = ["Tümü"] + list(df["Ay"].unique())
    
    col_f1, col_f2 = st.columns(2)
    sec_yil = col_f1.selectbox("Yıl", yillar)
    sec_ay = col_f2.selectbox("Ay", aylar)
    
    df_f = df[df["Yıl"] == sec_yil]
    if sec_ay != "Tümü":
        df_f = df_f[df_f["Ay"] == sec_ay]

    # Özet Kartları
    top_gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    top_gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    kalan = top_gelir - top_gider

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Gelir", f"{top_gelir:,.2f} ₺")
    c2.metric("Giderler", f"{top_gider:,.2f} ₺", delta=f"-{top_gider:,.2f}", delta_color="inverse")
    c3.metric("Kalan Nakit", f"{kalan:,.2f} ₺")

    st.divider()

    # Grafikler
    tab1, tab2 = st.tabs(["📉 Harcama Dağılımı", "📋 Son İşlemler"])
    
    with tab1:
        if not df_f[df_f["Tur"] == "Gider"].empty:
            fig = px.pie(df_f[df_f["Tur"] == "Gider"], values="Tutar", names="Kategori", 
                         hole=0.5, title="Kategori Bazlı Giderler",
                         color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Bu dönemde gider kaydı bulunamadı.")

    with tab2:
        st.dataframe(df_f.sort_values("Tarih", ascending=False), use_container_width=True)

# --- 5. İŞLEM EKLEME (Sidebar) ---
with st.sidebar:
    st.header("➕ Yeni İşlem")
    with st.form("ekleme_formu", clear_on_submit=True):
        tarih = st.date_input("Tarih", datetime.today())
        tur = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"])
        kategori = st.selectbox("Kategori", ["Mutfak", "Market", "Maaş", "Fatura", "Kira", "Ulaşım", "Eğitim", "Diğer"])
        aciklama = st.text_input("Açıklama")
        tutar = st.number_input("Tutar (₺)", min_value=0.0, format="%.2f")
        
        submit = st.form_submit_button("KAYDET")
        
        if submit:
            if tutar > 0:
                client = get_gspread_client()
                sheet = client.open("Butce_Veritabanı").sheet1
                yeni_satir = [
                    str(tarih), 
                    tarih.strftime("%B"), # Ay ismi (İngilizce ise manuel sözlük eklenebilir)
                    str(tarih.year), 
                    kategori, 
                    aciklama, 
                    str(tutar).replace('.', ','), 
                    tur
                ]
                sheet.append_row(yeni_satir)
                st.success("Kayıt Başarılı!")
                st.rerun()
            else:
                st.warning("Lütfen tutar girin!")
