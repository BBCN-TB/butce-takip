import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

# ======================================================
# SAYFA AYARLARI
# ======================================================
st.set_page_config(page_title="Akıllı Bütçe", layout="wide", page_icon="📊")

SHEET_ADI = "Butce_Veritabanı"
AYARLAR_TAB_ADI = "Ayarlar"

# ======================================================
# SESSION DEFAULTS
# ======================================================
if "tema" not in st.session_state:
    st.session_state.tema = "Açık"

if "gold" not in st.session_state:
    st.session_state.gold = 6400.0

if "silver" not in st.session_state:
    st.session_state.silver = 80.0

# ======================================================
# TEMA CSS
# ======================================================
if st.session_state.tema == "Koyu":
    BG = "#0e1117"
    CARD = "#1c1f26"
    TXT = "#ffffff"
else:
    BG = "#f5f7fa"
    CARD = "#ffffff"
    TXT = "#000000"

st.markdown(f"""
<style>
.stApp {{
    background: {BG};
    color: {TXT};
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}

div[data-testid="stMetric"] {{
    background: {CARD};
    padding: 18px;
    border-radius: 18px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.12);
}}

.stButton>button {{
    border-radius: 14px;
    padding: 0.7rem;
    width: 100%;
    font-weight: 600;
    background: linear-gradient(to right, #4facfe, #00f2fe);
    color: white;
    border: none;
}}

section[data-testid="stSidebar"] {{
    background: {CARD};
}}

@media (max-width: 768px) {{
    .block-container {{
        padding: 1rem;
    }}
}}
</style>
""", unsafe_allow_html=True)

# ======================================================
# ŞİFRE
# ======================================================
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

# ======================================================
# GOOGLE SHEETS
# ======================================================
def get_client():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["service_account"]),
        ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

def load_data():
    ws = get_client().open(SHEET_ADI).sheet1
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

df = load_data()

AY_MAP = {
    1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",
    7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"
}

# ======================================================
# SIDEBAR
# ======================================================
with st.sidebar:
    st.header("🎨 Tema")
    st.session_state.tema = st.radio("", ["Açık","Koyu"],
        index=0 if st.session_state.tema=="Açık" else 1)

    st.divider()

    st.header("💰 Piyasalar")
    st.session_state.gold = st.number_input("Gram Altın (₺)", value=st.session_state.gold, step=10.0)
    st.session_state.silver = st.number_input("Gram Gümüş (₺)", value=st.session_state.silver, step=1.0)

    st.divider()

    st.header("➕ İşlem Ekle")
    tarih = st.date_input("Tarih", datetime.today())
    tur = st.selectbox("Tür", ["Gider","Gelir","Yatırım"])

    taksit = 1
    if tur=="Gider" and st.checkbox("Taksitli mi?"):
        taksit = st.slider("Taksit Sayısı", 2, 12, 3)

    if tur=="Gider":
        kategoriler = ["Market","Kira","Fatura","Ulaşım","Sağlık","Diğer"]
    elif tur=="Gelir":
        kategoriler = ["Maaş","Ek Gelir","Prim"]
    else:
        kategoriler = ["Altın","Gümüş","Döviz","Fon","Borsa"]

    kategori = st.selectbox("Kategori", kategoriler)
    aciklama = st.text_input("Açıklama")
    tutar_txt = st.text_input("Tutar", placeholder="5890,00")

    def parse_tutar(x):
        try:
            return float(x.replace(".","").replace(",","."))
        except:
            return 0.0

    tutar = parse_tutar(tutar_txt)

    if st.button("Kaydet"):
        if tutar>0:
            rows=[]
            if taksit>1:
                aylik = round(tutar/taksit,2)
                for i in range(taksit):
                    d = tarih + relativedelta(months=i)
                    rows.append([
                        d.strftime("%Y-%m-%d"), AY_MAP[d.month], d.year,
                        kategori, f"{aciklama} ({i+1}/{taksit}. Taksit)",
                        aylik, tur
                    ])
            else:
                rows.append([
                    tarih.strftime("%Y-%m-%d"), AY_MAP[tarih.month], tarih.year,
                    kategori, aciklama, tutar, tur
                ])
            get_client().open(SHEET_ADI).sheet1.append_rows(rows, value_input_option="RAW")
            st.success("Kaydedildi")
            st.rerun()

# ======================================================
# DASHBOARD
# ======================================================
st.title("📊 Akıllı Bütçe")

yillar = sorted(df["Yıl"].unique(), reverse=True)
aylar = ["Tümü"] + list(df["Ay"].unique())

c1,c2 = st.columns(2)
sec_yil = c1.selectbox("Yıl", yillar)
sec_ay = c2.selectbox("Ay", aylar)

df_f = df[df["Yıl"]==sec_yil]
if sec_ay!="Tümü":
    df_f = df_f[df_f["Ay"]==sec_ay]

gelir = df_f[df_f["Tur"]=="Gelir"]["Tutar"].sum()
gider = df_f[df_f["Tur"]=="Gider"]["Tutar"].sum()
yatirim = df_f[df_f["Tur"]=="Yatırım"]["Tutar"].sum()
kalan = gelir-(gider+yatirim)

m1,m2,m3,m4 = st.columns(4)
m1.metric("Gelir", f"{gelir:,.2f} ₺")
m2.metric("Gider", f"{gider:,.2f} ₺")
m3.metric("Yatırım", f"{yatirim:,.2f} ₺")
m4.metric("Kalan", f"{kalan:,.2f} ₺")

st.divider()

# ======================================================
# PORTFÖY
# ======================================================
st.subheader("💼 Portföyüm")
df_y = df[df["Tur"]=="Yatırım"].copy()

def current_value(row):
    m = re.search(r'\[([\d\.,]+)', str(row["Aciklama"]))
    if m:
        miktar = float(m.group(1).replace(".","").replace(",","."))
        if "altın" in row["Kategori"].lower():
            return miktar * st.session_state.gold
        if "gümüş" in row["Kategori"].lower():
            return miktar * st.session_state.silver
    return row["Tutar"]

if not df_y.empty:
    df_y["Güncel"] = df_y.apply(current_value, axis=1)
    df_y["Fark"] = df_y["Güncel"] - df_y["Tutar"]

    p1,p2,p3 = st.columns(3)
    p1.metric("Maliyet", f"{df_y['Tutar'].sum():,.2f} ₺")
    p2.metric("Güncel Değer", f"{df_y['Güncel'].sum():,.2f} ₺")
    p3.metric("Kâr/Zarar", f"{df_y['Fark'].sum():,.2f} ₺", delta=f"{df_y['Fark'].sum():,.2f} ₺")

    st.dataframe(
        df_y[["Tarih","Kategori","Aciklama","Tutar","Güncel","Fark"]]
        .style.format({"Tutar":"{:,.2f} ₺","Güncel":"{:,.2f} ₺","Fark":"{:,.2f} ₺"}),
        use_container_width=True
    )

st.divider()

# ======================================================
# SİLME (TAKSİT DESTEKLİ)
# ======================================================
st.subheader("🗑️ Kayıt Sil")

df_disp = df.reset_index()
sec = st.selectbox(
    "Silinecek kayıt",
    df_disp.apply(lambda x: f"{x['index']} | {x['Tarih']} | {x['Aciklama']} | {x['Tutar']:,.2f} ₺", axis=1)
)

if st.button("Sil"):
    idx = int(sec.split("|")[0].strip())
    aciklama = df.loc[idx,"Aciklama"]
    tutar = df.loc[idx,"Tutar"]

    match = re.search(r"(.*?) \((\d+)/(\d+)\. Taksit\)", aciklama)
    indices=[idx]

    if match:
        ana = match.group(1)
        toplam = match.group(3)
        benzer = df[
            (df["Aciklama"].str.contains(ana, na=False)) &
            (df["Aciklama"].str.contains(f"/{toplam}. Taksit")) &
            (df["Tutar"]==tutar)
        ]
        if not benzer.empty:
            if st.checkbox("Tüm taksitleri sil"):
                indices = benzer.index.tolist()

    ws = get_client().open(SHEET_ADI).sheet1
    data = ws.get_all_values()
    header, rows = data[0], data[1:]
    new = pd.DataFrame(rows, columns=header).drop(index=indices)
    ws.clear()
    ws.append_row(header)
    ws.append_rows(new.astype(str).values.tolist(), value_input_option="RAW")
    st.success("Silindi")
    st.rerun()
