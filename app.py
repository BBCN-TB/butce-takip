import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

# --- 1. AYARLAR VE TASARIM (CSS) ---
SHEET_ADI = "Butce_Veritabanı"
AYARLAR_TAB_ADI = "Ayarlar"

st.set_page_config(page_title="Finans Pro", layout="wide", page_icon="💰")

st.markdown("""
<style>
/* Genel Arka Plan */
.stApp {
    background: linear-gradient(135deg, #f5f7fa 0%, #e4ecf7 100%);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* Metrik Kartları (Dashboard) */
div[data-testid="stMetric"] {
    background: white;
    padding: 18px;
    border-radius: 18px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.06);
    text-align: center;
    border: 1px solid #eef2f6;
}

/* Tablar (Sekmeler) Tasarımı */
.stTabs [data-baseweb="tab-list"] {
    gap: 24px;
}
.stTabs [data-baseweb="tab"] {
    height: 50px;
    white-space: pre-wrap;
    background-color: transparent;
    border-radius: 4px;
    font-weight: 600;
}

/* Butonlar */
.stButton > button {
    border-radius: 14px;
    padding: 0.6rem 1rem;
    font-weight: 600;
    background: linear-gradient(to right, #4facfe, #00f2fe);
    color: white;
    border: none;
    transition: all 0.3s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
}

/* Kenar Çubuğu (Sidebar) */
section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #eee;
}

/* Mobil uyum iyileştirmeleri */
@media (max-width: 768px) {
    .block-container {
        padding: 1rem !important;
    }
    div[data-testid="stMetric"] {
        margin-bottom: 10px;
    }
}
</style>
""", unsafe_allow_html=True)

# --- 2. GİRİŞ VE GOOGLE BAĞLANTISI ---
def check_password():
    if st.session_state.get("password_correct", False): return True
    if "LOGIN_SIFRE" not in st.secrets: return True
    st.text_input("Şifre", type="password", key="password_input", on_change=password_entered)
    return False

def password_entered():
    if st.session_state["password_input"] == st.secrets["LOGIN_SIFRE"]:
        st.session_state["password_correct"] = True
    else: st.error("😕 Hatalı Şifre")

if not check_password(): st.stop()

@st.cache_resource
def get_client():
    creds_dict = dict(st.secrets["service_account"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def veri_yukle():
    try:
        sh = get_client().open(SHEET_ADI).sheet1
        data = sh.get_all_values()
        if len(data) < 2: return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
        df = pd.DataFrame(data[1:], columns=data[0])
        def temizle(x):
            try:
                x_str = str(x).replace("₺", "").replace("TL", "").replace(".", "").replace(",", ".").strip()
                return float(x_str) if x_str else 0.0
            except: return 0.0
        df["Tutar"] = df["Tutar"].apply(temizle)
        return df
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return pd.DataFrame()

# --- 3. ANA MANTIK VE PİYASA VERİSİ ---
df = veri_yukle()

def piyasa_cek():
    try:
        sh = get_client().open(SHEET_ADI).worksheet(AYARLAR_TAB_ADI)
        recs = sh.get_all_records()
        d = {row['Parametre']: row['Deger'] for row in recs}
        return float(str(d.get('gram_altin', 6400)).replace(",", ".")), float(str(d.get('gram_gumus', 80)).replace(",", "."))
    except: return 6400.0, 80.0

g_altin, g_gumus = piyasa_cek()

# --- 4. KENAR ÇUBUĞU (İŞLEM EKLEME) ---
with st.sidebar:
    st.title("➕ Yeni İşlem")
    with st.form("ekle_form", clear_on_submit=True):
        tarih = st.date_input("Tarih", datetime.today())
        tur = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"])
        
        if tur == "Gider": kats = ["Mutfak", "Kredi Kartı", "Kira", "Fatura", "Pazar", "Ulaşım", "Eğitim", "Diğer"]
        elif tur == "Gelir": kats = ["Maaş", "Ek Gelir", "Borç Alacak"]
        else: kats = ["Altın", "Gümüş", "Döviz", "Borsa", "Bitcoin"]
        
        kat = st.selectbox("Kategori", kats)
        miktar = st.text_input("Miktar (Yatırım ise: 5.5)") if tur == "Yatırım" else ""
        aciklama = st.text_input("Açıklama")
        tutar_input = st.text_input("Tutar (1500,50)")
        
        taksitli = False
        t_sayi = 1
        if tur == "Gider":
            taksitli = st.checkbox("Taksitli mi?")
            if taksitli: t_sayi = st.slider("Taksit", 2, 12, 3)

        if st.form_submit_button("KAYDET"):
            tutar_f = float(tutar_input.replace(".", "").replace(",", "."))
            ay_map = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}
            
            rows = []
            if taksitli:
                pay = tutar_f / t_sayi
                for i in range(t_sayi):
                    d = tarih + relativedelta(months=i)
                    rows.append([str(d), ay_map[d.month], d.year, kat, f"{aciklama} ({i+1}/{t_sayi}.Tks)", str(pay).replace(".", ","), tur])
            else:
                desc = f"[{miktar}] {aciklama}" if miktar else aciklama
                rows.append([str(tarih), ay_map[tarih.month], tarih.year, kat, desc, str(tutar_f).replace(".", ","), tur])
            
            get_client().open(SHEET_ADI).sheet1.append_rows(rows, value_input_option='USER_ENTERED')
            st.success("İşlem Başarılı!")
            st.rerun()

# --- 5. DASHBOARD VE ANALİZ ---
st.header("💎 Finansal Kontrol Paneli")

if not df.empty:
    # Filtreler (Mobil uyumlu yan yana)
    f1, f2 = st.columns(2)
    s_yil = f1.selectbox("Yıl", sorted(df["Yıl"].unique(), reverse=True))
    s_ay = f2.selectbox("Ay", ["Tümü"] + list(df["Ay"].unique()))
    
    df_f = df[df["Yıl"] == s_yil]
    if s_ay != "Tümü": df_f = df_f[df_f["Ay"] == s_ay]

    # Metrik Kartları
    gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    yatirim = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()
    kalan = gelir - gider - yatirim

    m1, m2, m3, m4 = st.columns([1,1,1,1])
    m1.metric("Toplam Gelir", f"{gelir:,.2f} ₺")
    m2.metric("Toplam Gider", f"{gider:,.2f} ₺")
    m3.metric("Yatırım Maliyeti", f"{yatirim:,.2f} ₺")
    m4.metric("Kalan Nakit", f"{kalan:,.2f} ₺")

    st.divider()

    # --- TABLAR: ANALİZ VE PORTFÖY ---
    tab1, tab2 = st.tabs(["📉 Harcama Dağılımı", "💰 Yatırım Portföyü (Kâr/Zarar)"])

    with tab1:
        if not df_f[df_f["Tur"] != "Gelir"].empty:
            fig = px.pie(df_f[df_f["Tur"] != "Gelir"], values="Tutar", names="Kategori", hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Bu ay için harcama verisi yok.")

    with tab2:
        df_y = df[df["Tur"] == "Yatırım"].copy()
        if not df_y.empty:
            def portfoy_hesap(row):
                d, c = str(row["Aciklama"]), str(row["Kategori"]).lower()
                res = re.search(r'\[([\d\.,]+)\]', d)
                if res:
                    q = float(res.group(1).replace(",", "."))
                    if "altın" in c: return q * g_altin
                    if "gümüş" in c: return q * g_gumus
                return row["Tutar"]
            
            df_y["Güncel Değer"] = df_y.apply(portfoy_hesap, axis=1)
            df_y["Net Kâr/Zarar"] = df_y["Güncel Değer"] - df_y["Tutar"]
            
            k1, k2 = st.columns(2)
            k1.metric("Portföy Güncel Değer", f"{df_y['Güncel Değer'].sum():,.2f} ₺")
            k2.metric("Toplam Kâr/Zarar", f"{df_y['Net Kâr/Zarar'].sum():,.2f} ₺", delta=f"{df_y['Net Kâr/Zarar'].sum():,.2f}")
            
            st.dataframe(df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Güncel Değer", "Net Kâr/Zarar"]].style.format("{:,.2f} ₺"), use_container_width=True)
        else: st.info("Yatırım kaydı bulunamadı.")

    # --- 6. TÜM İŞLEMLER (EN ALTTA, BAĞIMSIZ) ---
    st.divider()
    st.subheader("📋 Tüm İşlem Geçmişi")
    st.dataframe(df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}), use_container_width=True)

else:
    st.info("Veritabanında henüz işlem bulunmuyor.")
