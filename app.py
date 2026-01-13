import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

# --- 1. AYARLAR VE TASARIM ---
SHEET_ADI = "Butce_Veritabanı"
AYARLAR_TAB_ADI = "Ayarlar"
st.set_page_config(page_title="Akıllı Bütçe v2", layout="wide", page_icon="💰")

# Karanlık Mod Uyumlu Modern Tasarım
st.markdown("""
    <style>
    /* Metrik Kartları */
    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.08);
        padding: 15px !important;
        border-radius: 15px !important;
        border: 1px solid rgba(128, 128, 128, 0.2);
        transition: 0.3s;
    }
    div[data-testid="stMetric"]:hover { transform: translateY(-3px); }
    
    /* Butonlar */
    .stButton>button {
        width: 100%;
        border-radius: 12px !important;
        height: 3em;
        font-weight: bold;
        background: linear-gradient(135deg, #007bff, #0056b3);
        color: white !important;
        border: none;
    }
    
    /* Sidebar yumuşatma */
    [data-testid="stSidebar"] { background-color: rgba(128, 128, 128, 0.02); }
    
    /* Tablo genişliği */
    .stDataFrame { width: 100% !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. GİRİŞ KONTROLÜ ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True
    if "LOGIN_SIFRE" not in st.secrets:
        return True # Eğer secret tanımlanmamışsa açık bırak
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Giriş")
        st.text_input("Şifre", type="password", key="password_input")
        if st.button("Giriş Yap"):
            if st.session_state["password_input"] == st.secrets["LOGIN_SIFRE"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("😕 Şifre Yanlış")
    return False

if not check_password():
    st.stop()

# --- 3. GOOGLE SHEETS BAĞLANTISI ---
@st.cache_resource
def get_gspread_client():
    creds_dict = dict(st.secrets["service_account"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def veri_yukle():
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    tum_veriler = worksheet.get_all_values()
    
    if not tum_veriler or len(tum_veriler) < 2:
        return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
    
    df = pd.DataFrame(tum_veriler[1:], columns=tum_veriler[0])
    
    def temizle(x):
        try:
            x_str = str(x).strip().replace("₺", "").replace("TL", "").strip()
            if not x_str: return 0.0
            if "," in x_str:
                x_str = x_str.replace(".", "").replace(",", ".")
            return float(x_str)
        except: return 0.0
        
    df["Tutar"] = df["Tutar"].apply(temizle)
    df["Yıl"] = df["Yıl"].astype(str)
    return df

# --- 4. AYARLAR (ALTIN/GÜMÜŞ) ---
def piyasa_fiyatlarini_getir():
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    try:
        ws = sh.worksheet(AYARLAR_TAB_ADI)
    except:
        ws = sh.add_worksheet(title=AYARLAR_TAB_ADI, rows=10, cols=5)
        ws.update('A1', [['Parametre', 'Deger'], ['gram_altin', 6400.00], ['gram_gumus', 80.00]])
        return 6400.00, 80.00
    
    records = ws.get_all_records()
    data_dict = {row['Parametre']: row['Deger'] for row in records}
    
    try:
        gold = float(str(data_dict.get('gram_altin', 6400)).replace(",", "."))
        silver = float(str(data_dict.get('gram_gumus', 80)).replace(",", "."))
    except:
        gold, silver = 6400.00, 80.00
    return gold, silver

def piyasa_fiyatlarini_guncelle(altin, gumus):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    ws = sh.worksheet(AYARLAR_TAB_ADI)
    ws.update('B2', altin)
    ws.update('B3', gumus)

# --- 5. ANA PROGRAM ---
df = veri_yukle()

# --- SOL MENÜ (INPUTS) ---
with st.sidebar:
    st.header("💰 Piyasa Fiyatları")
    k_altin, k_gumus = piyasa_fiyatlarini_getir()
    gold_val = st.number_input("Gr Altın (₺)", value=k_altin, step=10.0)
    silver_val = st.number_input("Gr Gümüş (₺)", value=k_gumus, step=1.0)
    
    if st.button("Fiyatları Sabitle 💾"):
        piyasa_fiyatlarini_guncelle(gold_val, silver_val)
        st.success("Güncellendi!")
        st.rerun()

    st.session_state['piyasa_gold'] = gold_val
    st.session_state['piyasa_silver'] = silver_val

    st.divider()
    st.header("💸 İşlem Ekle")
    tarih_giris = st.date_input("Tarih", datetime.today())
    tur_giris = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"])
    
    taksit_sayisi = 1
    if tur_giris == "Gider":
        is_taksit = st.checkbox("Taksitli mi?")
        if is_taksit:
            taksit_sayisi = st.slider("Taksit Sayısı", 2, 12, 3)
    
    if tur_giris == "Gider": kats = ["Kredi Kartı", "Mutfak", "Fatura", "Kira", "Ulaşım", "Market", "Sağlık", "Diğer"]
    elif tur_giris == "Gelir": kats = ["Maaş", "Ek Gelir", "Prim", "Borç Alacak"]
    else: # Yatırım
        kats = ["Altın", "Gümüş", "Döviz", "Borsa", "Fon", "Bitcoin", "Bes"]
        miktar = st.text_input("Miktar (Örn: 5 Gram)")
        miktar_bilgisi = f"[{miktar}] " if miktar else ""

    kategori_giris = st.selectbox("Kategori", kats)
    aciklama_giris = st.text_input("Açıklama")
    tutar_text = st.text_input("Tutar (₺)", placeholder="Örn: 500,00")

    if st.button("Kaydet 💾", type="primary"):
        try:
            t_float = float(tutar_text.replace(".", "").replace(",", "."))
            if t_float > 0:
                client = get_gspread_client()
                ws = client.open(SHEET_ADI).sheet1
                ay_map = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}
                rows = []
                
                if taksit_sayisi > 1:
                    aylik = t_float / taksit_sayisi
                    for i in range(taksit_sayisi):
                        d = tarih_giris + relativedelta(months=i)
                        rows.append([str(d), ay_map[d.month], d.year, kategori_giris, f"{aciklama_giris} ({i+1}/{taksit_sayisi}. Taksit)", str(aylik).replace(".", ","), tur_giris])
                else:
                    rows.append([str(tarih_giris), ay_map[tarih_giris.month], tarih_giris.year, kategori_giris, miktar_bilgisi+aciklama_giris, str(t_float).replace(".", ","), tur_giris])
                
                ws.append_rows(rows, value_input_option='USER_ENTERED')
                st.success("Başarıyla kaydedildi!")
                st.rerun()
        except: st.error("Geçerli bir tutar girin!")

    # SİLME
    st.divider()
    if not df.empty:
        with st.expander("🗑️ Kayıt Sil"):
            df_s = df.reset_index().sort_index(ascending=False)
            sec = st.selectbox("Seç:", df_s.apply(lambda x: f"{x['index']} | {x['Tarih']} | {x['Aciklama']} | {x['Tutar']}", axis=1))
            if st.button("Seçiliyi Sil"):
                idx = int(sec.split("|")[0].strip())
                client = get_gspread_client()
                ws = client.open(SHEET_ADI).sheet1
                # Basit silme: Tüm veriyi çek, satırı sil, geri yaz (Küçük tablolar için en güvenli yol)
                all_vals = ws.get_all_values()
                del all_vals[idx + 1]
                ws.clear()
                ws.append_rows(all_vals, value_input_option='USER_ENTERED')
                st.rerun()

# --- 6. DASHBOARD (MAIN) ---
st.title("📊 Akıllı Bütçe Dashboard")

if not df.empty:
    yillar = sorted(df["Yıl"].unique().tolist(), reverse=True)
    aylar = ["Tümü"] + list(df["Ay"].unique())
    c1, c2 = st.columns(2)
    s_yil = c1.selectbox("Yıl", yillar)
    s_ay = c2.selectbox("Ay", aylar)
    
    df_f = df[df["Yıl"] == s_yil]
    if s_ay != "Tümü": df_f = df_f[df_f["Ay"] == s_ay]

    # Özet Kartları
    t_gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    t_gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    t_yatirim = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()
    kalan = t_gelir - (t_gider + t_yatirim)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gelir", f"{t_gelir:,.2f} ₺")
    m2.metric("Gider", f"{t_gider:,.2f} ₺", delta_color="inverse")
    m3.metric("Yatırım", f"{t_yatirim:,.2f} ₺")
    m4.metric("Kalan", f"{kalan:,.2f} ₺")

    st.divider()
    tab1, tab2 = st.tabs(["📉 Analiz", "💰 Portföy"])
    
    with tab1:
        g1, g2 = st.columns(2)
        with g1:
            fig1 = px.pie(df_f[df_f["Tur"] != "Gelir"], values="Tutar", names="Kategori", hole=0.4, title="Harcama Dağılımı")
            st.plotly_chart(fig1, use_container_width=True)
        with g2:
            fig2 = px.bar(df_f.groupby("Tur")["Tutar"].sum().reset_index(), x="Tur", y="Tutar", color="Tur", title="Genel Durum")
            st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        df_y = df[df["Tur"] == "Yatırım"].copy()
        if not df_y.empty:
            g_gold = st.session_state.get('piyasa_gold', 0)
            g_silver = st.session_state.get('piyasa_silver', 0)
            
            def calc(row):
                d, c = str(row["Aciklama"]), str(row["Kategori"]).lower()
                m = re.search(r'\[([\d\.,]+)', d)
                if m:
                    q = float(m.group(1).replace(",", "."))
                    if "altın" in c: return q * g_gold
                    if "gümüş" in c: return q * g_silver
                return row["Tutar"]

            df_y["Guncel"] = df_y.apply(calc, axis=1)
            df_y["Fark"] = df_y["Guncel"] - df_y["Tutar"]
            
            st.dataframe(df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Guncel", "Fark"]].style.format("{:,.2f} ₺"), use_container_width=True)
        else: st.info("Yatırım kaydı yok.")

    st.subheader("📋 Tüm İşlemler")
    st.dataframe(df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}), use_container_width=True)
else:
    st.info("Henüz veri yok.")
