import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- AYARLAR ---
SHEET_ADI = "Butce_Veritabanı"  # Google Sheet dosyanın tam adı
st.set_page_config(page_title="Bulut Bütçe", layout="wide", page_icon="☁️")
# --- GİRİŞ KONTROLÜ (BEKÇİ) ---
def check_password():
    """Giriş yapılmadıysa şifre sorar, doğruysa True döner."""
    
    # 1. Eğer zaten giriş yapıldıysa direkt geç
    if st.session_state.get("password_correct", False):
        return True

    # 2. Şifre giriş kutusunu göster
    st.text_input(
        "Lütfen Şifrenizi Girin", 
        type="password", 
        key="password_input", 
        on_change=password_entered
    )
    return False

def password_entered():
    """Girilen şifreyi kontrol eder."""
    # Secrets'tan şifreyi al ve kıyasla
    if st.session_state["password_input"] == st.secrets["LOGIN_SIFRE"]:
        st.session_state["password_correct"] = True
        del st.session_state["password_input"]  # Şifreyi hafızadan sil (Güvenlik)
    else:
        st.session_state["password_correct"] = False
        st.error("😕 Şifre Yanlış")

# --- ANA PROGRAM BAŞLANGICI ---
# Eğer şifre kontrolü False dönerse (yani giriş yapılmadıysa)
# Uygulamanın geri kalanını DURDUR (st.stop)
if not check_password():
    st.stop()

# BURADAN AŞAĞISI SENİN ESKİ KODLARIN DEVAM EDECEK...
# (def get_gspread_client()... vs diye devam eden kısım)
# --- GOOGLE SHEETS BAĞLANTISI ---
def get_gspread_client():
    # Streamlit Secrets'tan bilgileri al
    creds_dict = dict(st.secrets["service_account"])
    
    # Scope tanımla
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Kimlik doğrulama
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def veri_yukle():
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    
    # Tüm verileri al ve DataFrame'e çevir
    data = worksheet.get_all_records()
    if not data: # Eğer boşsa
        return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
        
    df = pd.DataFrame(data)
    # Sayısal dönüşüm (Google Sheet bazen string tutabilir)
    # Tutar sütununda virgül varsa noktaya çevir, TL işaretini kaldır
    if not df.empty and "Tutar" in df.columns:
        df["Tutar"] = df["Tutar"].astype(str).str.replace(" TL", "").str.replace(".", "").str.replace(",", ".").astype(float)
        
    return df

def veri_kaydet(yeni_satir_df):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    
    # DataFrame'i listeye çevir (Header hariç)
    # Tarih formatını string yapalım ki Sheet bozulmasın
    yeni_satir_df["Tarih"] = yeni_satir_df["Tarih"].astype(str)
    
    liste = yeni_satir_df.values.tolist()
    
    # En alta ekle
    for row in liste:
        worksheet.append_row(row)

def kayit_sil(satir_no):
    # Google Sheet'te satır numarası 1'den başlar. 1. satır başlıktır.
    # Pandas index 0 -> Sheet row 2 demektir.
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    worksheet.delete_rows(satir_no + 2) # +2 çünkü Pandas 0-indexli ve Header var

# --- ANA VERİYİ ÇEK ---
try:
    df = veri_yukle()
except Exception as e:
    st.error(f"Google Sheets Bağlantı Hatası: {e}")
    st.stop()

# --- SOL MENÜ ---
with st.sidebar:
    st.header("☁️ Bulut Veri Girişi")
    
    tarih_giris = st.date_input("Tarih", datetime.today())
    tur_giris = st.selectbox("Tür", ["Gider", "Gelir"])
    
    if tur_giris == "Gider":
        kategoriler = ["Kredi Kartı", "Mutfak", "Fatura", "Kira", "Ulaşım", "Market", "Sağlık", "Diğer"]
    else:
        kategoriler = ["Maaş", "Ek Gelir", "Yatırım", "Borç Alacak"]
        
    kategori_giris = st.selectbox("Kategori", kategoriler)
    aciklama_giris = st.text_input("Açıklama")
    tutar_giris = st.number_input("Tutar", min_value=0.0, format="%.2f")
    
    if st.button("Kaydet 💾", type="primary"):
        if tutar_giris > 0:
            ay_map = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                      7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}
            
            yeni_veri = pd.DataFrame({
                "Tarih": [tarih_giris],
                "Ay": [ay_map[tarih_giris.month]],
                "Yıl": [tarih_giris.year],
                "Kategori": [kategori_giris],
                "Aciklama": [aciklama_giris],
                "Tutar": [tutar_giris],
                "Tur": [tur_giris]
            })
            
            with st.spinner('Google Drive\'a yazılıyor...'):
                veri_kaydet(yeni_veri)
            st.success("Kaydedildi!")
            st.rerun()

    # SİLME BÖLÜMÜ
    st.divider()
    if not df.empty:
        df_gosterim = df.reset_index().sort_index(ascending=False) # Indexi koruyarak ters çevir
        secenekler = df_gosterim.apply(lambda x: f"NO: {x['index']} | {x['Tarih']} | {x['Kategori']} | {x['Tutar']}", axis=1)
        sil_secim = st.selectbox("Kayıt Sil:", secenekler)
        
        if st.button("Seçiliyi Sil 🗑️"):
            silinecek_index = int(sil_secim.split("|")[0].replace("NO:", "").strip())
            with st.spinner('Siliniyor...'):
                kayit_sil(silinecek_index)
            st.success("Silindi!")
            st.rerun()

# --- DASHBOARD ---
st.title("📊 Bulut Bütçe Takip")

if not df.empty:
    col1, col2 = st.columns(2)
    yillar = sorted(df["Yıl"].unique().tolist(), reverse=True)
    aylar = ["Tümü"] + list(df["Ay"].unique())
    
    sec_yil = col1.selectbox("Yıl", yillar)
    sec_ay = col2.selectbox("Ay", aylar)
    
    df_f = df[df["Yıl"] == sec_yil]
    if sec_ay != "Tümü":
        df_f = df_f[df_f["Ay"] == sec_ay]

    # Kartlar
    gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    kalan = gelir - gider
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Gelir", f"{gelir:,.2f}")
    c2.metric("Gider", f"{gider:,.2f}", delta_color="inverse")
    c3.metric("Kalan", f"{kalan:,.2f}", delta=f"{kalan:,.2f}")
    
    st.divider()
    
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Gider Dağılımı")
        df_g = df_f[df_f["Tur"] == "Gider"]
        if not df_g.empty:
            fig = px.pie(df_g, values="Tutar", names="Kategori", hole=0.5)
            st.plotly_chart(fig, use_container_width=True)
    with g2:
        st.subheader("Durum")
        ozet = df_f.groupby("Tur")["Tutar"].sum().reset_index()
        if not ozet.empty:
            fig2 = px.bar(ozet, x="Tur", y="Tutar", color="Tur")
            st.plotly_chart(fig2, use_container_width=True)
            
    st.dataframe(df_f, use_container_width=True)
else:
    st.info("Veritabanı boş. İlk kaydını ekle!")

