import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

# --------------------------------------------------
# SAYFA AYARLARI
# --------------------------------------------------
st.set_page_config(
    page_title="Akıllı Bütçe",
    layout="wide",
    page_icon="📊"
)

# --------------------------------------------------
# MOBİL & MODERN UI CSS
# --------------------------------------------------
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #f5f7fa 0%, #e6ecf5 100%);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

h1, h2, h3 {
    font-weight: 600;
}

div[data-testid="stMetric"] {
    background: white;
    padding: 20px;
    border-radius: 18px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.08);
    text-align: center;
}

.stButton > button {
    width: 100%;
    border-radius: 14px;
    padding: 0.75rem;
    font-weight: 600;
    background: linear-gradient(to right, #4facfe, #00f2fe);
    color: white;
    border: none;
}

section[data-testid="stSidebar"] {
    background: #ffffff;
}

@media (max-width: 768px) {
    .block-container {
        padding: 1rem;
    }
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# AYARLAR
# --------------------------------------------------
SHEET_ADI = "Butce_Veritabanı"
AYARLAR_TAB_ADI = "Ayarlar"

# --------------------------------------------------
# GİRİŞ KONTROLÜ
# --------------------------------------------------
def check_password():
    if st.session_state.get("password_correct", False):
        return True
    if "LOGIN_SIFRE" not in st.secrets:
        return True
    st.text_input("🔐 Şifre", type="password", key="password_input", on_change=password_entered)
    return False

def password_entered():
    if st.session_state["password_input"] == st.secrets["LOGIN_SIFRE"]:
        st.session_state["password_correct"] = True
        del st.session_state["password_input"]
    else:
        st.error("Şifre yanlış")

if not check_password():
    st.stop()

# --------------------------------------------------
# GOOGLE SHEETS BAĞLANTISI
# --------------------------------------------------
def get_gspread_client():
    creds_dict = dict(st.secrets["service_account"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# --------------------------------------------------
# VERİ YÜKLE
# --------------------------------------------------
def veri_yukle():
    sh = get_gspread_client().open(SHEET_ADI)
    ws = sh.sheet1
    data = ws.get_all_values()

    if len(data) < 2:
        return pd.DataFrame(columns=["Tarih","Ay","Yıl","Kategori","Aciklama","Tutar","Tur"])

    df = pd.DataFrame(data[1:], columns=data[0])

    def temizle(x):
        try:
            return float(str(x).replace("₺","").replace("TL","").replace(".","").replace(",","."))
        except:
            return 0.0

    df["Tutar"] = df["Tutar"].apply(temizle)
    df["Yıl"] = df["Yıl"].astype(int)
    return df

df = veri_yukle()

AY_MAP = {
    1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",
    7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"
}

# --------------------------------------------------
# SIDEBAR – İŞLEM EKLEME
# --------------------------------------------------
with st.sidebar:
    st.header("➕ İşlem Ekle")

    tarih = st.date_input("Tarih", datetime.today())
    tur = st.selectbox("Tür", ["Gider","Gelir","Yatırım"])

    taksit = 1
    if tur == "Gider" and st.checkbox("Taksitli mi?"):
        taksit = st.slider("Taksit Sayısı", 2, 12, 3)

    if tur == "Gider":
        kategoriler = ["Kredi Kartı","Market","Fatura","Kira","Ulaşım","Sağlık","Diğer"]
    elif tur == "Gelir":
        kategoriler = ["Maaş","Ek Gelir","Prim"]
    else:
        kategoriler = ["Altın","Gümüş","Döviz","Borsa","Fon"]

    kategori = st.selectbox("Kategori", kategoriler)
    aciklama = st.text_input("Açıklama")
    tutar_text = st.text_input("Tutar (₺)", placeholder="5890,00")

    def parse_tutar(x):
        try:
            return float(x.replace(".","").replace(",","."))
        except:
            return 0.0

    tutar = parse_tutar(tutar_text)

    if st.button("Kaydet"):
        if tutar > 0:
            rows = []
            if taksit > 1:
                aylik = round(tutar / taksit, 2)
                for i in range(taksit):
                    d = tarih + relativedelta(months=i)
                    rows.append([
                        d.strftime("%Y-%m-%d"),
                        AY_MAP[d.month],
                        d.year,
                        kategori,
                        f"{aciklama} ({i+1}/{taksit}. Taksit)",
                        aylik,
                        tur
                    ])
            else:
                rows.append([
                    tarih.strftime("%Y-%m-%d"),
                    AY_MAP[tarih.month],
                    tarih.year,
                    kategori,
                    aciklama,
                    tutar,
                    tur
                ])

            ws = get_gspread_client().open(SHEET_ADI).sheet1
            ws.append_rows(rows, value_input_option="RAW")
            st.success("Kaydedildi")
            st.rerun()

# --------------------------------------------------
# ANA EKRAN – DASHBOARD
# --------------------------------------------------
st.title("📊 Akıllı Bütçe")

yillar = sorted(df["Yıl"].unique(), reverse=True)
aylar = ["Tümü"] + list(df["Ay"].unique())

c1, c2 = st.columns(2)
sec_yil = c1.selectbox("Yıl", yillar)
sec_ay = c2.selectbox("Ay", aylar)

df_f = df[df["Yıl"] == sec_yil]
if sec_ay != "Tümü":
    df_f = df_f[df_f["Ay"] == sec_ay]

gelir = df_f[df_f["Tur"]=="Gelir"]["Tutar"].sum()
gider = df_f[df_f["Tur"]=="Gider"]["Tutar"].sum()
yatirim = df_f[df_f["Tur"]=="Yatırım"]["Tutar"].sum()
kalan = gelir - (gider + yatirim)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Gelir", f"{gelir:,.2f} ₺")
m2.metric("Gider", f"{gider:,.2f} ₺")
m3.metric("Yatırım", f"{yatirim:,.2f} ₺")
m4.metric("Kalan", f"{kalan:,.2f} ₺")

st.divider()

fig = px.pie(
    df_f[df_f["Tur"]!="Gelir"],
    values="Tutar",
    names="Kategori",
    hole=0.4
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("📋 Tüm İşlemler")
st.dataframe(
    df_f.sort_values("Tarih", ascending=False)
    .style.format({"Tutar":"{:,.2f} ₺"}),
    use_container_width=True
)
