import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finans Pro", layout="wide", page_icon="💰")

# --- MOBİL UYGULAMA GÖRÜNÜMÜ İÇİN CSS ---
st.markdown("""
    <style>
    /* Arka plan ve kartlar */
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] {
        background-color: #1e2129;
        border: 1px solid #30363d;
        padding: 15px !important;
        border-radius: 15px !important;
    }
    /* Mobilde butonları büyüt */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3.5em;
        background-color: #238636;
        color: white;
        font-weight: bold;
    }
    /* Tablo genişliği */
    .stDataFrame { width: 100% !important; }
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS BAĞLANTISI ---
@st.cache_resource
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["service_account"]), scope)
    return gspread.authorize(creds)

def veri_cek():
    client = get_client()
    sh = client.open("Butce_Veritabanı")
    # Ana Veri
    ws = sh.sheet1
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["Tutar"] = df["Tutar"].str.replace('.', '').str.replace(',', '.').astype(float)
    
    # Ayarlar (Altın/Gümüş)
    try:
        settings_ws = sh.worksheet("Ayarlar")
        settings_data = settings_ws.get_all_records()
        prices = {row['Parametre']: row['Deger'] for row in settings_data}
    except:
        prices = {"gram_altin": 6400, "gram_gumus": 80}
    
    return df, prices

# --- VERİLERİ YÜKLE ---
try:
    df, piyasa = veri_cek()
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

# --- SIDEBAR: İŞLEM EKLEME ---
with st.sidebar:
    st.title("➕ Yeni İşlem")
    with st.form("ekle_form", clear_on_submit=True):
        tarih = st.date_input("Tarih", datetime.today())
        tur = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"])
        
        if tur == "Gider": kats = ["Market", "Kira", "Fatura", "Ulaşım", "Eğitim", "Sağlık", "Diğer"]
        elif tur == "Gelir": kats = ["Maaş", "Ek Gelir", "Borç Alacak"]
        else: kats = ["Altın", "Gümüş", "Döviz", "Borsa", "Bitcoin"]
        
        kat = st.selectbox("Kategori", kats)
        aciklama = st.text_input("Açıklama")
        
        miktar = ""
        if tur == "Yatırım":
            miktar = st.text_input("Miktar (Örn: 5)")
        
        tutar_str = st.text_input("Tutar (Örn: 1500,50)")
        
        taksitli = False
        taksit_sayisi = 1
        if tur == "Gider":
            taksitli = st.checkbox("Taksitli İşlem")
            if taksitli:
                taksit_sayisi = st.slider("Taksit", 2, 12, 3)

        if st.form_submit_button("KAYDET"):
            tutar = float(tutar_str.replace('.', '').replace(',', '.'))
            client = get_client()
            ws = client.open("Butce_Veritabanı").sheet1
            ay_map = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}
            
            rows = []
            if taksitli:
                aylik = tutar / taksit_sayisi
                for i in range(taksit_sayisi):
                    d = tarih + relativedelta(months=i)
                    rows.append([str(d), ay_map[d.month], d.year, kat, f"{aciklama} ({i+1}/{taksit_sayisi})", str(aylik).replace('.', ','), tur])
            else:
                desc = f"[{miktar}] {aciklama}" if miktar else aciklama
                rows.append([str(tarih), ay_map[tarih.month], tarih.year, kat, desc, str(tutar).replace('.', ','), tur])
            
            ws.append_rows(rows, value_input_option='USER_ENTERED')
            st.success("Kaydedildi!")
            st.rerun()

# --- ANA EKRAN ---
st.title("📊 Finansal Özet")

# Filtreler
yillar = sorted(df["Yıl"].unique().tolist(), reverse=True)
aylar = ["Tümü"] + list(df["Ay"].unique())
c1, c2 = st.columns(2)
s_yil = c1.selectbox("Yıl", yillar)
s_ay = c2.selectbox("Ay", aylar)

df_f = df[df["Yıl"] == str(s_yil)]
if s_ay != "Tümü": df_f = df_f[df_f["Ay"] == s_ay]

# Hesaplamalar
gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
yatirim_maliyet = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()

# Metrikler
m1, m2, m3 = st.columns(3)
m1.metric("Gelir", f"{gelir:,.2f} ₺")
m2.metric("Gider", f"{gider:,.2f} ₺", delta=f"-{gider:,.2f}", delta_color="inverse")
m3.metric("Kalan", f"{(gelir - gider - yatirim_maliyet):,.2f} ₺")

# Grafikler
st.divider()
fig = px.pie(df_f[df_f["Tur"] != "Gelir"], values="Tutar", names="Kategori", hole=0.5, title="Harcama Dağılımı")
st.plotly_chart(fig, use_container_width=True)

# Portföy Hesaplama
st.subheader("💰 Yatırım Portföyü")
df_y = df[df["Tur"] == "Yatırım"].copy()
if not df_y.empty:
    def hesapla(row):
        d = str(row["Aciklama"])
        k = str(row["Kategori"]).lower()
        res = re.search(r'\[([\d\.,]+)\]', d)
        if res:
            q = float(res.group(1).replace(',', '.'))
            if "altın" in k: return q * float(piyasa.get("gram_altin", 0))
            if "gümüş" in k: return q * float(piyasa.get("gram_gumus", 0))
        return row["Tutar"]
    
    df_y["Güncel"] = df_y.apply(hesapla, axis=1)
    df_y["Kâr/Zarar"] = df_y["Güncel"] - df_y["Tutar"]
    st.dataframe(df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Güncel", "Kâr/Zarar"]].style.format("{:,.2f} ₺"), use_container_width=True)

# İşlemler
st.subheader("📋 Son İşlemler")
st.dataframe(df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}), use_container_width=True)
