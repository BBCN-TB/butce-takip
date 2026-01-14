import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

# --- 1. AYARLAR VE MODERN TASARIM (CSS) ---
SHEET_ADI = "Butce_Veritabanı"
AYARLAR_TAB_ADI = "Ayarlar"

st.set_page_config(page_title="Finans Pro", layout="wide", page_icon="💰")

st.markdown("""
<style>
/* Genel Arka Plan ve Yazı Tipi */
.stApp {
    background: linear-gradient(135deg, #f5f7fa 0%, #e4ecf7 100%);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
/* Metrik Kartları */
div[data-testid="stMetric"] {
    background: white;
    padding: 18px;
    border-radius: 18px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.06);
    text-align: center;
    border: 1px solid #eef2f6;
}
/* Butonlar */
.stButton > button {
    border-radius: 14px;
    padding: 0.6rem 1rem;
    font-weight: 600;
    background: linear-gradient(to right, #4facfe, #00f2fe);
    color: white;
    border: none;
    width: 100%;
}
/* Sidebar */
section[data-testid="stSidebar"] {
    background: #ffffff;
}
</style>
""", unsafe_allow_html=True)

# --- 2. GİRİŞ VE GOOGLE BAĞLANTISI ---
def check_password():
    if st.session_state.get("password_correct", False): return True
    if "LOGIN_SIFRE" not in st.secrets: return True
    st.text_input("Lütfen Şifrenizi Girin", type="password", key="password_input", on_change=password_entered)
    return False

def password_entered():
    if st.session_state["password_input"] == st.secrets["LOGIN_SIFRE"]:
        st.session_state["password_correct"] = True
        del st.session_state["password_input"]
    else: st.error("😕 Şifre Yanlış")

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

df = veri_yukle()
return df
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

# --- 3. PİYASA FİYATLARI ---
def piyasa_cek():
    try:
        sh = get_client().open(SHEET_ADI).worksheet(AYARLAR_TAB_ADI)
        recs = sh.get_all_records()
        d = {row['Parametre']: row['Deger'] for row in recs}
        return float(str(d.get('gram_altin', 6400)).replace(",", ".")), float(str(d.get('gram_gumus', 80)).replace(",", "."))
    except: return 6400.0, 80.0

g_altin, g_gumus = piyasa_cek()

# --- VERİ SİLME FONKSİYONU ---
def veri_sil_toplu(indexler):
    try:
        # Mevcut veriyi tekrar çek (en güncel hali için)
        sh = get_client().open(SHEET_ADI).sheet1
        tum_veriler = sh.get_all_values()
        header = tum_veriler[0]
        df_mevcut = pd.DataFrame(tum_veriler[1:], columns=header)
        
        # Seçilen satırları index numarasına göre uçur
        df_yeni = df_mevcut.drop(index=indexler)
        
        # Sayfayı komple temizle ve başlıkla birlikte yeni listeyi yaz
        sh.clear()
        sh.append_row(header)
        if not df_yeni.empty:
            sh.append_rows(df_yeni.values.tolist(), value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Silme işlemi sırasında hata oluştu: {e}")
        return False

# --- 4. KENAR ÇUBUĞU (İŞLEM EKLEME) ---
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

    if st.button("KAYDET 💾"):
        if tutar_input:
            tutar_f = float(tutar_input.replace(".", "").replace(",", "."))
            ay_map = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}
            desc = f"[{miktar}] {aciklama}" if miktar else aciklama
            row = [str(tarih.strftime("%Y-%m-%d")), ay_map[tarih.month], tarih.year, kat, desc, str(tutar_f).replace(".", ","), tur]
            get_client().open(SHEET_ADI).sheet1.append_row(row, value_input_option='USER_ENTERED')
            st.success("Kaydedildi!")
            st.rerun()
if st.form_submit_button("KAYDET"): # veya st.button("KAYDET 💾")
    t.divider()
    st.header("🗑️ İşlem Silme")

    if not df_f.empty:
        df_sil = df_f.copy()
        df_sil["Gosterim"] = df_sil["Tarih"] + " | " + df_sil["Kategori"] + " | " + df_sil["Tutar"].astype(str) + "₺"
        secilen_islem = st.selectbox("Silinecek İşlemi Seçin", ["Seçiniz..."] + df_sil["Gosterim"].tolist())

        if secilen_islem != "Seçiniz...":
            idx = df_sil[df_sil["Gosterim"] == secilen_islem].index
            btn_col1, btn_col2 = st.columns(2)
            
            if btn_col1.button("Tekil Sil", use_container_width=True):
                if veri_sil_toplu(idx):
                    st.success("Silindi!")
                    st.rerun()
            
            if btn_col2.button("Tüm Seri Sil", use_container_width=True):
                aciklama = df.loc[idx[0], "Aciklama"]
                match = re.search(r"(.+?)\s\(\d+/\d+\.Tks\)", str(aciklama))
                if match:
                    temel_isim = match.group(1).strip()
                    taksit_idx = df[df["Aciklama"].str.contains(re.escape(temel_isim), na=False)].index
                    if veri_sil_toplu(taksit_idx):
                        st.success("Tüm seri silindi!")
                        st.rerun()
                else:
                    st.warning("Bu işlem taksitli değil!")
    # --- 5. DASHBOARD ---
st.title("📊 Akıllı Bütçe Yönetimi")

if not df.empty:
    f1, f2 = st.columns(2)
    yil_listesi = sorted(df["Yıl"].dropna().unique().astype(int), reverse=True)
    s_yil = f1.selectbox("Yıl", yil_listesi)
    s_ay = f2.selectbox("Ay", ["Tümü"] + list(df["Ay"].unique()))
    
    # Ana Filtreleme
    df_f = df[df["Yıl"] == s_yil]
    if s_ay != "Tümü": 
        df_f = df_f[df_f["Ay"] == s_ay]

    # Metrikler
    m1, m2, m3, m4 = st.columns(4)
    gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    yatirim = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()
    m1.metric("Gelir", f"{gelir:,.2f} ₺")
    m2.metric("Gider", f"{gider:,.2f} ₺")
    m3.metric("Yatırım", f"{yatirim:,.2f} ₺")
    m4.metric("Kalan", f"{(gelir - gider - yatirim):,.2f} ₺")

    st.divider()

    tab1, tab2 = st.tabs(["📉 Grafikler", "💰 Yatırım Durumu"])

    with tab1:
        c_g1, c_g2 = st.columns(2)
        df_pie = df_f[df_f["Tur"].isin(["Gider", "Yatırım"])]
        if not df_pie.empty:
            fig1 = px.pie(df_pie, values="Tutar", names="Kategori", hole=0.4, title="Harcama Dağılımı")
            c_g1.plotly_chart(fig1, use_container_width=True)
            df_bar = df_f.groupby("Tur")["Tutar"].sum().reset_index()
            fig2 = px.bar(df_bar, x="Tur", y="Tutar", color="Tur", title="Bütçe Dengesi")
            c_g2.plotly_chart(fig2, use_container_width=True)

    with tab2:
        # ÖNEMLİ: Sadece seçili yıl ve aydaki yatırımları getirir
        df_y = df_f[df_f["Tur"] == "Yatırım"].copy()
        
        if not df_y.empty:
            def portfoy_hesap(row):
                d, c = str(row["Aciklama"]), str(row["Kategori"]).lower()
                match = re.search(r'\[([\d\.,]+)', d)
                if match:
                    try:
                        q = float(match.group(1).replace(",", "."))
                        if "altın" in c: return q * g_altin
                        if "gümüş" in c: return q * g_gumus
                    except: return row["Tutar"]
                return row["Tutar"]
            
            df_y["Güncel Değer"] = df_y.apply(portfoy_hesap, axis=1).fillna(0)
            df_y["Kâr/Zarar"] = (df_y["Güncel Değer"] - df_y["Tutar"]).fillna(0)
            
            st.write(f"### 💎 {s_ay} {s_yil} Yatırımları")
            df_display = df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Güncel Değer", "Kâr/Zarar"]]
            st.dataframe(df_display.style.format({
                "Tutar": "{:,.2f} ₺", "Güncel Değer": "{:,.2f} ₺", "Kâr/Zarar": "{:,.2f} ₺"
            }), use_container_width=True)
        else:
            st.info(f"{s_ay} {s_yil} döneminde yatırım kaydı bulunamadı.")

    st.divider()
    st.subheader("📋 İşlem Geçmişi")
    # --- 6. TÜM İŞLEMLER VE SİLME PANELİ ---
    st.divider()
    st.subheader("📋 İşlem Geçmişi")
    st.info("💡 Silmek istediğiniz satırları tablonun solundaki kutucuklardan seçebilirsiniz.")

    # Veriyi tarihe göre sıralı göster
    df_gecmis = df_f.sort_values("Tarih", ascending=False)
    
    # SEÇİLEBİLİR TABLO
    # Bu tablo üzerinden satır seçtiğinde 'secilen_satirlar' değişkeni dolacak
    secilen_satirlar = st.dataframe(
        df_gecmis.style.format({"Tutar": "{:,.2f} ₺"}), 
        use_container_width=True,
        on_select="rerun",           # Seçim yapınca sayfayı tetikle
        selection_mode="multi-row"    # Çoklu satır seçimine izin ver
    )

    # Eğer en az bir satır seçildiyse Silme Butonlarını göster
    if len(secilen_satirlar.selection.rows) > 0:
        st.warning(f"⚠️ {len(secilen_satirlar.selection.rows)} işlem seçildi. Ne yapmak istersiniz?")
        
        col_sil1, col_sil2 = st.columns(2)
        
        # SADECE SEÇİLENLERİ SİL
        if col_sil1.button("Seçilen Satırları Sil 🗑️", type="primary"):
            # Orijinal dataframe indexlerini alıyoruz
            secilen_indexler = df_gecmis.iloc[secilen_satirlar.selection.rows].index
            if veri_sil_toplu(secilen_indexler):
                st.success("İşlemler başarıyla silindi!")
                st.rerun()

        # TÜM TAKSİT GRUBUNU SİL
        if col_sil2.button("Seçilenin Tüm Taksitlerini Sil 🔄"):
            secilen_veriler = df_gecmis.iloc[secilen_satirlar.selection.rows]
            silinecek_ek_indexler = []
            
            for _, row in secilen_veriler.iterrows():
                aciklama = str(row["Aciklama"])
                # Regex ile taksit ibaresini (Örn: " (1/3.Tks)") temizleyip ana ismi bulur
                match = re.search(r"(.+?)\s\(\d+/\d+\.Tks\)", aciklama)
                if match:
                    temel_isim = match.group(1).strip()
                    # Veritabanında bu ismi içeren tüm satırları bul
                    taksit_indexleri = df[df["Aciklama"].str.contains(re.escape(temel_isim), na=False)].index
                    silinecek_ek_indexler.extend(taksit_indexleri)
            
            # Tekrar eden indexleri temizle
            toplam_silinecek = list(set(silinecek_ek_indexler))
            
            if toplam_silinecek:
                if veri_sil_toplu(toplam_silinecek):
                    st.success(f"Taksit serisine ait {len(toplam_silinecek)} kayıt silindi!")
                    st.rerun()
            else:
                st.error("Seçtiğiniz işlem taksitli bir seri gibi görünmüyor.")
    st.info("Veri yok.")


