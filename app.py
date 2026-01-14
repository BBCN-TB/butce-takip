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

st.set_page_config(page_title="Finans Pro", layout="wide", page_icon="💰")

st.markdown("""
<style>
.stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e4ecf7 100%); font-family: sans-serif; }
div[data-testid="stMetric"] { background: white; padding: 18px; border-radius: 18px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); text-align: center; }
.stButton > button { border-radius: 14px; font-weight: 600; background: linear-gradient(to right, #4facfe, #00f2fe); color: white; border: none; }
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
        df["Yıl"] = pd.to_numeric(df["Yıl"], errors='coerce')
        return df
    except: return pd.DataFrame()

# --- SİLME FONKSİYONU ---
def veri_sil_toplu(indexler):
    try:
        client = get_client() 
        sh = client.open(SHEET_ADI).sheet1
        tum_veriler = sh.get_all_values()
        header = tum_veriler[0]
        df_mevcut = pd.DataFrame(tum_veriler[1:], columns=header)
        df_yeni = df_mevcut.drop(index=indexler)
        sh.clear()
        sh.append_row(header)
        if not df_yeni.empty:
            sh.append_rows(df_yeni.values.tolist(), value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Hata: {e}")
        return False

df = veri_yukle()

# --- 3. PİYASA FİYATLARI ---
def piyasa_cek():
    try:
        sh = get_client().open(SHEET_ADI).worksheet(AYARLAR_TAB_ADI)
        recs = sh.get_all_records()
        d = {row['Parametre']: row['Deger'] for row in recs}
        return float(str(d.get('gram_altin', 6400)).replace(",", ".")), float(str(d.get('gram_gumus', 80)).replace(",", "."))
    except: return 6400.0, 80.0

g_altin, g_gumus = piyasa_cek()

# --- 4. KENAR ÇUBUĞU (EKLEME VE SİLME) ---
with st.sidebar:
    st.title("➕ Yeni İşlem")
    tarih = st.date_input("Tarih", datetime.today())
    tur = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"], key="main_tur")
    
    if tur == "Gider": kats = ["Mutfak", "Kredi Kartı", "Kira", "Fatura", "Pazar", "Ulaşım", "Eğitim", "Diğer"]
    elif tur == "Gelir": kats = ["Maaş", "Ek Gelir", "Borç Alacak"]
    else: kats = ["Altın", "Gümüş", "Döviz", "Borsa", "Bitcoin"]
    
    kat = st.selectbox("Kategori", kats, key=f"kat_select_{tur}")
    miktar = st.text_input("Miktar (Örn: 5.5 Gram)") if tur == "Yatırım" else ""
    aciklama = st.text_input("Açıklama")
    tutar_input = st.text_input("Tutar (Örn: 1500,50)")
    
    taksitli = False
    t_sayi = 1
    if tur == "Gider":
        taksitli = st.checkbox("Taksitli mi?")
        if taksitli: t_sayi = st.slider("Taksit", 2, 12, 3)

    if st.button("KAYDET 💾", use_container_width=True):
        if tutar_input:
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

    # --- SİLME PANELİ (SİDEBAR İÇİNDE) ---
    st.divider()
    st.header("🗑️ İşlem Silme")

    yil_listesi = sorted(df["Yıl"].dropna().unique().astype(int), reverse=True)
    f_yil = st.selectbox("Yıl Seç", yil_listesi, key="sil_yil")
    f_ay = st.selectbox("Ay Seç", list(df["Ay"].unique()), key="sil_ay")
    
    df_filtre_sil = df[(df["Yıl"] == f_yil) & (df["Ay"] == f_ay)].copy()

    if not df_filtre_sil.empty:
        df_filtre_sil["Gosterim"] = df_filtre_sil["Tarih"] + " | " + df_filtre_sil["Kategori"] + " | " + df_filtre_sil["Tutar"].astype(str) + "₺"
        secilen_islem = st.selectbox("Silinecek İşlem", ["Seçiniz..."] + df_filtre_sil["Gosterim"].tolist())

        if secilen_islem != "Seçiniz...":
            idx = df_filtre_sil[df_filtre_sil["Gosterim"] == secilen_islem].index
            c1, c2 = st.columns(2)
            
            if c1.button("Tek Sil", use_container_width=True):
                if veri_sil_toplu(idx):
                    st.success("Silindi!")
                    st.rerun()
            
            if c2.button("Seri Sil", use_container_width=True):
                target_desc = df.loc[idx[0], "Aciklama"]
                match = re.search(r"(.+?)\s\(\d+/\d+\.Tks\)", str(target_desc))
                if match:
                    base_name = match.group(1).strip()
                    t_idx = df[df["Aciklama"].str.contains(re.escape(base_name), na=False)].index
                    if veri_sil_toplu(t_idx):
                        st.success("Tüm seri silindi!")
                        st.rerun()
                else:
                    st.warning("Taksitli değil!")
    else:
        st.write("Bu ayda kayıt yok.")

# --- 5. DASHBOARD ---
st.title("📊 Akıllı Bütçe Yönetimi")

if not df.empty:
    col_f1, col_f2 = st.columns(2)
    yil_options = sorted(df["Yıl"].dropna().unique().astype(int), reverse=True)
    s_yil = col_f1.selectbox("Filtre: Yıl", yil_options)
    s_ay = col_f2.selectbox("Filtre: Ay", ["Tümü"] + list(df["Ay"].unique()))
    
    df_f = df[df["Yıl"] == s_yil]
    if s_ay != "Tümü": df_f = df_f[df_f["Ay"] == s_ay]

    m1, m2, m3, m4 = st.columns(4)
    gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    yatirim = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()
    m1.metric("Gelir", f"{gelir:,.2f} ₺")
    m2.metric("Gider", f"{gider:,.2f} ₺")
    m3.metric("Yatırım", f"{yatirim:,.2f} ₺")
    m4.metric("Kalan", f"{(gelir - gider - yatirim):,.2f} ₺")

    st.divider()

    tab1, tab2 = st.tabs(["📉 Grafikler", "💰 Portföy"])

    with tab1:
        c_g1, c_g2 = st.columns(2)
        df_p = df_f[df_f["Tur"].isin(["Gider", "Yatırım"])]
        if not df_p.empty:
            fig1 = px.pie(df_p, values="Tutar", names="Kategori", hole=0.4, title="Harcama Dağılımı")
            c_g1.plotly_chart(fig1, use_container_width=True)
            df_b = df_f.groupby("Tur")["Tutar"].sum().reset_index()
            fig2 = px.bar(df_b, x="Tur", y="Tutar", color="Tur", title="Denge")
            c_g2.plotly_chart(fig2, use_container_width=True)

    with tab2:
        df_y = df_f[df_f["Tur"] == "Yatırım"].copy()
        if not df_y.empty:
            def calc(row):
                d, c = str(row["Aciklama"]), str(row["Kategori"]).lower()
                m = re.search(r'\[([\d\.,]+)', d)
                if m:
                    try:
                        q = float(m.group(1).replace(",", "."))
                        if "altın" in c: return q * g_altin
                        if "gümüş" in c: return q * g_gumus
                    except: return row["Tutar"]
                return row["Tutar"]
            df_y["Güncel"] = df_y.apply(calc, axis=1).fillna(0)
            df_y["K/Z"] = (df_y["Güncel"] - df_y["Tutar"]).fillna(0)
            st.dataframe(df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Güncel", "K/Z"]].style.format("{:,.2f} ₺"), use_container_width=True)
        else: st.info("Yatırım yok.")

    st.divider()
    st.subheader("📋 İşlem Geçmişi")
    st.dataframe(df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}), use_container_width=True)
else:
    st.info("Veri yok.")
