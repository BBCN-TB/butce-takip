import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re
import plotly.express as px

# --- 1. AYARLAR VE TASARIM ---
SHEET_ADI = "Butce_Veritabanı"
AYARLAR_TAB_ADI = "Ayarlar"

st.set_page_config(page_title="Finans Pro", layout="wide", page_icon="💰")

# Sidebar'a Toggle Butonu
theme_toggle = st.sidebar.toggle("🌙 Karanlık Mod", value=True)

if theme_toggle:
    # --- DARK MODE ---
    st.markdown("""
    <style>
    /* Ana Arka Plan */
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    
    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #262730; }
    
    /* METRİK KARTLARI */
    div[data-testid="stMetric"] {
        background-color: #1F2937;
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 15px;
    }
    div[data-testid="stMetricLabel"] p { color: #9CA3AF !important; font-size: 14px !important; }
    div[data-testid="stMetricValue"] div { color: #FFFFFF !important; font-size: 24px !important; font-weight: bold !important; }

    /* GRAFİK KUTULARI */
    div[data-testid="stPlotlyChart"] {
        background-color: #1F2937;
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 10px;
    }

    /* TABLOLAR */
    div[data-testid="stDataFrame"] {
        background-color: #1F2937;
        border: 1px solid #374151;
        border-radius: 8px;
    }
    div[data-testid="stDataFrame"] * { color: #E5E7EB !important; }

    /* Input Alanları */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        color: white !important;
        background-color: #374151 !important;
    }
    
    /* Genel Yazılar */
    h1, h2, h3, p { color: #E5E7EB !important; }
    
    /* Butonlar */
    .stButton > button {
        background: linear-gradient(to right, #374151, #111827);
        color: white;
        border: 1px solid #4B5563;
    }
    /* Sekme Başlıkları */
    .stTabs [data-baseweb="tab"] { color: #9CA3AF; }
    .stTabs [aria-selected="true"] { color: #FFFFFF !important; }
    </style>
    """, unsafe_allow_html=True)
else:
    # --- LIGHT MODE ---
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e4ecf7 100%); color: black; }
    div[data-testid="stMetric"] { 
        background: white; 
        padding: 18px; 
        border-radius: 18px; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); 
        text-align: center; 
        border: 1px solid #eef2f6; 
    }
    .stButton > button { 
        border-radius: 14px; 
        font-weight: 600; 
        background: linear-gradient(to right, #4facfe, #00f2fe); 
        color: white; 
        border: none; 
    }
    section[data-testid="stSidebar"] { background: #ffffff; }
    div[data-testid="stPlotlyChart"] {
        background: white;
        border-radius: 18px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        padding: 10px;
        border: 1px solid #eef2f6;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FONKSİYONLAR ---
def check_password():
    if st.session_state.get("password_correct", False): return True
    if "LOGIN_SIFRE" not in st.secrets: return True
    st.text_input("Şifre", type="password", key="password_input", on_change=password_entered)
    return False

def password_entered():
    if st.session_state["password_input"] == st.secrets["LOGIN_SIFRE"]:
        st.session_state["password_correct"] = True
        del st.session_state["password_input"]
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

def piyasa_cek():
    try:
        sh = get_client().open(SHEET_ADI).worksheet(AYARLAR_TAB_ADI)
        recs = sh.get_all_records()
        d = {row['Parametre']: row['Deger'] for row in recs}
        return float(str(d.get('gram_altin', 6400)).replace(",", ".")), float(str(d.get('gram_gumus', 80)).replace(",", "."))
    except: return 6400.0, 80.0

def piyasa_guncelle(yeni_altin, yeni_gumus):
    try:
        client = get_client()
        sh = client.open(SHEET_ADI)
        try:
            ws = sh.worksheet(AYARLAR_TAB_ADI)
        except:
            ws = sh.add_worksheet(title=AYARLAR_TAB_ADI, rows=10, cols=5)
            ws.append_row(['Parametre', 'Deger'])
            ws.append_row(['gram_altin', 6400])
            ws.append_row(['gram_gumus', 80])
        
        cell_gold = ws.find("gram_altin")
        ws.update_cell(cell_gold.row, cell_gold.col + 1, yeni_altin)
        cell_silver = ws.find("gram_gumus")
        ws.update_cell(cell_silver.row, cell_silver.col + 1, yeni_gumus)
        return True
    except Exception as e:
        st.error(f"Piyasa güncelleme hatası: {e}")
        return False

g_altin, g_gumus = piyasa_cek()

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("💰 Piyasalar")
    col_p1, col_p2 = st.columns(2)
    yeni_altin_val = col_p1.number_input("Gr Altın", value=g_altin, step=10.0)
    yeni_gumus_val = col_p2.number_input("Gr Gümüş", value=g_gumus, step=1.0)
    
    if st.button("Fiyatları Güncelle 🔄"):
        if piyasa_guncelle(yeni_altin_val, yeni_gumus_val):
            st.success("Güncellendi!")
            st.rerun()
    
    st.divider()

    st.subheader("➕ Yeni İşlem")
    tarih = st.date_input("Tarih", datetime.today())
    tur = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"], key="main_tur")
    
    if tur == "Gider": kats = ["Mutfak", "Kredi Kartı", "Kira", "Fatura", "Pazar", "Ulaşım", "Eğitim", "Diğer"]
    elif tur == "Gelir": kats = ["Maaş", "Ek Gelir", "Borç Alacak"]
    else: kats = ["Altın", "Gümüş", "Döviz", "Borsa", "Bitcoin"]
    
    kat = st.selectbox("Kategori", kats, key=f"kat_select_{tur}")
    miktar = st.text_input("Miktar (Yatırım ise: 5.5)") if tur == "Yatırım" else ""
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

    st.divider()
    st.subheader("🗑️ İşlem Silme")
    yil_options = sorted(df["Yıl"].dropna().unique().astype(int), reverse=True)
    f_yil = st.selectbox("Yıl Seç", yil_options, key="sil_yil")
    f_ay = st.selectbox("Ay Seç", list(df["Ay"].unique()), key="sil_ay")
    
    df_sil_f = df[(df["Yıl"] == f_yil) & (df["Ay"] == f_ay)].copy()

    if not df_sil_f.empty:
        df_sil_f["Gosterim"] = df_sil_f["Tarih"] + " | " + df_sil_f["Kategori"] + " | " + df_sil_f["Tutar"].astype(str) + "₺"
        secilen = st.selectbox("İşlem Seç", ["Seçiniz..."] + df_sil_f["Gosterim"].tolist())

        if secilen != "Seçiniz...":
            idx = df_sil_f[df_sil_f["Gosterim"] == secilen].index
            c1, c2 = st.columns(2)
            if c1.button("Tek Sil", key="btn_tek_sil"):
                if veri_sil_toplu(idx): st.rerun()
            if c2.button("Seri Sil", key="btn_seri_sil"):
                t_desc = str(df.loc[idx[0], "Aciklama"])
                match = re.search(r"(.+?)\s*\(\d+/\d+.*?\)", t_desc)
                if match:
                    base = match.group(1).strip()
                    t_idx = df[df["Aciklama"].str.contains(re.escape(base), na=False)].index
                    if veri_sil_toplu(t_idx): st.rerun()
                else:
                    base = t_desc.strip()
                    t_idx = df[df["Aciklama"] == base].index
                    if veri_sil_toplu(t_idx): st.rerun()

# --- 4. ANA EKRAN ---
st.title("📊 Akıllı Bütçe Yönetimi")

if not df.empty:
    col_f1, col_f2 = st.columns(2)
    yil_list = sorted(df["Yıl"].dropna().unique().astype(int), reverse=True)
    s_yil = col_f1.selectbox("Yıl Filtre", yil_list)
    s_ay = col_f2.selectbox("Ay Filtre", ["Tümü"] + list(df["Ay"].unique()))
    
    df_f = df[df["Yıl"] == s_yil]
    if s_ay != "Tümü": df_f = df_f[df_f["Ay"] == s_ay]

    gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    yatirim = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gelir", f"{gelir:,.2f} ₺")
    m2.metric("Gider", f"{gider:,.2f} ₺")
    m3.metric("Yatırım", f"{yatirim:,.2f} ₺")
    m4.metric("Kalan", f"{(gelir - gider - yatirim):,.2f} ₺")

    st.divider()

    tab1, tab2 = st.tabs(["📉 Grafikler", "💰 Portföy"])

    with tab1:
        c_g1, c_g2 = st.columns(2)
        
        # 1. HARCAMA ANALİZİ (Pasta Grafik)
        # Sadece Gider ve Yatırım olanları filtrele
        df_p = df_f[df_f["Tur"].isin(["Gider", "Yatırım"])]
        
        if not df_p.empty:
            fig1 = px.pie(df_p, values="Tutar", names="Kategori", hole=0.4, title="Harcama Analizi")
            fig1.update_traces(textposition='inside', textinfo='percent+label')
            
            # Ayarlar (Alt boşluk)
            fig1.update_layout(
                legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
                margin=dict(t=40, b=100, l=10, r=10) 
            )
            
            # Karanlık mod ayarı
            if theme_toggle:
                dark_layout = dict(
                    paper_bgcolor='rgba(0,0,0,0)', 
                    plot_bgcolor='rgba(0,0,0,0)',  
                    font=dict(color='#E5E7EB'),    
                    title_font=dict(color='#FAFAFA') 
                )
                fig1.update_layout(**dark_layout)
                
            c_g1.plotly_chart(fig1, use_container_width=True)
        else:
            c_g1.info("Harcama grafiği için veri yok.")

        # 2. NAKİT AKIŞ ANALİZİ (Sütun Grafik) - ÖZEL RENKLER
        if not df_f.empty:
            df_b = df_f.groupby("Tur")["Tutar"].sum().reset_index()
            
            # --- GÜNCELLENMİŞ RENK HARİTASI ---
            renk_haritasi = {
                "Gelir": "#008000",   # YEŞİL
                "Gider": "#B81414",   # KIRMIZI
                "Yatırım": "#00008b"  # MAVİ
            }
            
            fig2 = px.bar(
                df_b, 
                x="Tur", 
                y="Tutar", 
                color="Tur", 
                title="Nakit Akış Analizi", 
                text_auto='.2s',
                color_discrete_map=renk_haritasi  # Renkleri uygula
            )
            
            # Ayarlar (Alt boşluk ve Efsane konumu)
            fig2.update_layout(
                xaxis_title=None, 
                legend_title_text='', 
                legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
                margin=dict(t=40, b=100, l=10, r=10)
            )

            # Karanlık mod ayarı
            if theme_toggle:
                dark_layout = dict(
                    paper_bgcolor='rgba(0,0,0,0)', 
                    plot_bgcolor='rgba(0,0,0,0)',  
                    font=dict(color='#E5E7EB'),    
                    title_font=dict(color='#FAFAFA') 
                )
                fig2.update_layout(**dark_layout)

            c_g2.plotly_chart(fig2, use_container_width=True)
        else:
            c_g2.info("Akış grafiği için veri yok.")
            
    with tab2:
        df_y = df_f[df_f["Tur"] == "Yatırım"].copy()
        if not df_y.empty:
            def analyze_investment(row):
                desc = str(row["Aciklama"])
                cat = str(row["Kategori"]).lower()
                tutar = float(row["Tutar"]) if row["Tutar"] else 0.0
                
                qty = 0.0
                match = re.search(r'\[([\d\.,]+)', desc)
                if match:
                    try:
                        qty = float(match.group(1).replace(".", "").replace(",", "."))
                    except: qty = 0.0
                
                birim_maliyet = (tutar / qty) if qty > 0 else 0.0
                guncel_deger = tutar 
                if qty > 0:
                    if "altın" in cat: guncel_deger = qty * g_altin
                    elif "gümüş" in cat: guncel_deger = qty * g_gumus
                
                return pd.Series([birim_maliyet, guncel_deger])

            df_calc = df_y.apply(analyze_investment, axis=1)
            df_y["Birim Maliyet"] = df_calc[0]
            df_y["Güncel"] = df_calc[1]
            df_y["K/Z"] = df_y["Güncel"] - df_y["Tutar"]
            
            st.write(f"### 💎 {s_ay} {s_yil} Portföy Performansı")

            df_disp = df_y[["Tarih", "Kategori", "Aciklama", "Birim Maliyet", "Tutar", "Güncel", "K/Z"]]
            
            def kz_format(val):
                if pd.isna(val): return "-"
                prefix = "▲ " if val >= 0 else "▼ "
                return prefix + "{:,.2f} ₺".format(val)

            def kz_color(val):
                if pd.isna(val): return ""
                color = '#00CC96' if val >= 0 else '#EF553B' 
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                df_disp.style
                .format({
                    "Birim Maliyet": "{:,.2f} ₺",
                    "Tutar": "{:,.2f} ₺", 
                    "Güncel": "{:,.2f} ₺",
                    "K/Z": kz_format
                })
                .map(kz_color, subset=['K/Z']),
                use_container_width=True
            )
        else: 
            st.info("Veri yok.")

    st.divider()
    st.subheader("📋 İşlem Geçmişi")
    df_f["Tutar"] = pd.to_numeric(df_f["Tutar"], errors='coerce').fillna(0)
    st.dataframe(df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}), use_container_width=True)
else:
    st.info("Veri yok.")





