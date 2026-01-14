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
.stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e4ecf7 100%); font-family: sans-serif; }
div[data-testid="stMetric"] { background: white; padding: 18px; border-radius: 18px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); text-align: center; }
.stButton > button { border-radius: 14px; padding: 0.6rem 1rem; font-weight: 600; background: linear-gradient(to right, #4facfe, #00f2fe); color: white; border: none; }
section[data-testid="stSidebar"] { background: #ffffff; }
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
        # Yıl kolonunu sayıya çevir
        df["Yıl"] = pd.to_numeric(df["Yıl"], errors='coerce')
        return df
    except: return pd.DataFrame()

df = veri_yukle()

# --- 3. PİYASA VERİSİ ---
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
    
    tarih = st.date_input("Tarih", datetime.today())
    tur = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"], key="main_tur")
    
    # Kategori Listesini Dinamikleştirme
    if tur == "Gider": 
        kats = ["Mutfak", "Kredi Kartı", "Kira", "Fatura", "Pazar", "Ulaşım", "Eğitim", "Diğer"]
    elif tur == "Gelir": 
        kats = ["Maaş", "Ek Gelir", "Borç Alacak"]
    else: 
        kats = ["Altın", "Gümüş", "Döviz", "Borsa", "Bitcoin"]
    
    # HATA DÜZELTME: Tür değişince kategoriyi sıfırlamak için key'e 'tur' ekledik
    kat = st.selectbox("Kategori", kats, key=f"kat_select_{tur}")
    
    miktar = st.text_input("Miktar (Örn: 5.5 Gram)") if tur == "Yatırım" else ""
    aciklama = st.text_input("Açıklama")
    tutar_input = st.text_input("Tutar (Örn: 1500,50)")
    
    taksitli = False
    t_sayi = 1
    if tur == "Gider":
        taksitli = st.checkbox("Taksitli mi?")
        if taksitli: t_sayi = st.slider("Taksit", 2, 12, 3)

    if st.button("KAYDET 💾"):
        if not tutar_input:
            st.error("Lütfen bir tutar girin!")
        else:
            tutar_f = float(tutar_input.replace(".", "").replace(",", "."))
            ay_map = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}
            
            rows = []
            if taksitli:
                pay = tutar_f / t_sayi
                for i in range(t_sayi):
                    d = tarih + relativedelta(months=i)
                    rows.append([str(d.strftime("%Y-%m-%d")), ay_map[d.month], d.year, kat, f"{aciklama} ({i+1}/{t_sayi}.Tks)", str(round(pay,2)).replace(".", ","), tur])
            else:
                desc = f"[{miktar}] {aciklama}" if miktar else aciklama
                rows.append([str(tarih.strftime("%Y-%m-%d")), ay_map[tarih.month], tarih.year, kat, desc, str(tutar_f).replace(".", ","), tur])
            
            get_client().open(SHEET_ADI).sheet1.append_rows(rows, value_input_option='USER_ENTERED')
            st.success("Kaydedildi!")
            st.rerun()

# --- 5. DASHBOARD ---
st.title("📊 Finansal Kontrol Paneli")

if not df.empty:
    f1, f2 = st.columns(2)
    yil_listesi = sorted(df["Yıl"].dropna().unique().astype(int), reverse=True)
    s_yil = f1.selectbox("Yıl", yil_listesi)
    s_ay = f2.selectbox("Ay", ["Tümü"] + list(df["Ay"].unique()))
    
    df_f = df[df["Yıl"] == s_yil]
    if s_ay != "Tümü": df_f = df_f[df_f["Ay"] == s_ay]

    # Metrikler
    gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    yatirim = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gelir", f"{gelir:,.2f} ₺")
    m2.metric("Gider", f"{gider:,.2f} ₺")
    m3.metric("Yatırım", f"{yatirim:,.2f} ₺")
    m4.metric("Kalan", f"{(gelir - gider - yatirim):,.2f} ₺")

    st.divider()

    # --- TABLAR ---
    tab1, tab2 = st.tabs(["📉 Harcama Grafikleri", "💰 Portföy Kâr/Zarar"])

    with tab1:
        c_g1, c_g2 = st.columns(2)
        # Sadece Gider ve Yatırım içeren pasta grafiği
        df_pie = df_f[df_f["Tur"].isin(["Gider", "Yatırım"])]
        if not df_pie.empty:
            fig1 = px.pie(df_pie, values="Tutar", names="Kategori", hole=0.4, title="Harcama Dağılımı")
            c_g1.plotly_chart(fig1, use_container_width=True)
            
            # Tür bazlı bar grafiği
            df_bar = df_f.groupby("Tur")["Tutar"].sum().reset_index()
            fig2 = px.bar(df_bar, x="Tur", y="Tutar", color="Tur", title="Bütçe Dengesi")
            c_g2.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Gösterilecek grafik verisi yok.")

    with tab2:
        # SADECE YATIRIMLARI FİLTRELE
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
            df_y["Kâr/Zarar"] = df_y["Güncel Değer"] - df_y["Tutar"]
            
            st.write("### 💎 Yatırım Durumu")
            st.dataframe(df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Güncel Değer", "Kâr/Zarar"]].style.format("{:,.2f} ₺"), use_container_width=True)
        else:
            st.info("Henüz yatırım kaydı yok.")

    # --- TÜM İŞLEMLER ---
    st.divider()
    st.subheader("📋 Tüm İşlem Geçmişi")
    st.dataframe(df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}), use_container_width=True)

else:
    st.info("Veri yok.")
