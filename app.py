import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- AYARLAR ---
SHEET_ADI = "Butce_Veritabanı"  # Google Sheet dosyanın tam adı
st.set_page_config(page_title="Bulut Bütçe", layout="wide", page_icon="💰")

# --- GİRİŞ KONTROLÜ (ŞİFRE) ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True
    
    # Secrets içinde şifre yoksa direkt geç (Hata vermesin diye)
    if "LOGIN_SIFRE" not in st.secrets:
        return True

    st.text_input("Lütfen Şifrenizi Girin", type="password", key="password_input", on_change=password_entered)
    return False

def password_entered():
    if st.session_state["password_input"] == st.secrets["LOGIN_SIFRE"]:
        st.session_state["password_correct"] = True
        del st.session_state["password_input"]
    else:
        st.error("😕 Şifre Yanlış")

if not check_password():
    st.stop()

# --- GOOGLE SHEETS BAĞLANTISI ---
def get_gspread_client():
    creds_dict = dict(st.secrets["service_account"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def veri_yukle():
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    data = worksheet.get_all_records()
    
    if not data:
        return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
        
    df = pd.DataFrame(data)
    if not df.empty and "Tutar" in df.columns:
        # Sayısal dönüşüm hatalarını önle
        df["Tutar"] = df["Tutar"].astype(str).str.replace(" TL", "").str.replace(".", "").str.replace(",", ".").astype(float)
    return df

def veri_kaydet(yeni_satir_df):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    yeni_satir_df["Tarih"] = yeni_satir_df["Tarih"].astype(str)
    liste = yeni_satir_df.values.tolist()
    for row in liste:
        worksheet.append_row(row)

def kayit_sil(satir_no):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    worksheet.delete_rows(satir_no + 2)

# --- ANA VERİYİ ÇEK ---
try:
    df = veri_yukle()
except Exception as e:
    st.error(f"Google Sheets Bağlantı Hatası: {e}")
    st.stop()

# --- SOL MENÜ (GELİŞMİŞ) ---
with st.sidebar:
    st.header("💸 İşlem Ekle")
    
    tarih_giris = st.date_input("Tarih", datetime.today())
    # BURASI GÜNCELLENDİ: ARTIK YATIRIM DA VAR
    tur_giris = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"])
    
    miktar_bilgisi = "" # Yatırım miktarını tutacak değişken
    
    if tur_giris == "Gider":
        kategoriler = ["Kredi Kartı", "Mutfak", "Fatura", "Kira", "Ulaşım", "Market", "Sağlık", "Giyim", "Diğer"]
    elif tur_giris == "Gelir":
        kategoriler = ["Maaş", "Ek Gelir", "Prim", "Borç Alacak"]
    else: # YATIRIM SEÇİLDİYSE
        kategoriler = ["Altın", "Gümüş", "Döviz (Dolar/Euro)", "Borsa (Hisse)", "Fon", "Bitcoin/Kripto", "Bes"]
        st.info("👇 Ne kadar aldığını aşağıya yaz")
        miktar = st.text_input("Miktar (Örn: 5 Gram, 100 Lot, 50 Dolar)")
        if miktar:
            miktar_bilgisi = f"[{miktar}] " # Açıklamanın başına ekleyeceğiz

    kategori_giris = st.selectbox("Kategori", kategoriler)
    aciklama_giris = st.text_input("Açıklama (Opsiyonel)")
    tutar_giris = st.number_input("Toplam Tutar (TL)", min_value=0.0, format="%.2f")
    
    if st.button("Kaydet 💾", type="primary"):
        if tutar_giris > 0:
            ay_map = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                      7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}
            
            # Yatırım ise açıklamayı güncelle: "[5 Gram] - Açıklama"
            final_aciklama = miktar_bilgisi + aciklama_giris if aciklama_giris else miktar_bilgisi + "Yatırım Alımı"
            
            yeni_veri = pd.DataFrame({
                "Tarih": [tarih_giris],
                "Ay": [ay_map[tarih_giris.month]],
                "Yıl": [tarih_giris.year],
                "Kategori": [kategori_giris],
                "Aciklama": [final_aciklama],
                "Tutar": [tutar_giris],
                "Tur": [tur_giris]
            })
            
            with st.spinner('Kaydediliyor...'):
                veri_kaydet(yeni_veri)
            st.success("İşlem Başarılı!")
            st.rerun()

    # SİLME BÖLÜMÜ
    st.divider()
    if not df.empty:
        with st.expander("🗑️ Hatalı Kayıt Sil"):
            df_gosterim = df.reset_index().sort_index(ascending=False)
            secenekler = df_gosterim.apply(lambda x: f"NO: {x['index']} | {x['Tur']} | {x['Kategori']} | {x['Tutar']} TL", axis=1)
            sil_secim = st.selectbox("Silinecek Kayıt:", secenekler)
            
            if st.button("Seçiliyi Sil"):
                silinecek_index = int(sil_secim.split("|")[0].replace("NO:", "").strip())
                with st.spinner('Siliniyor...'):
                    kayit_sil(silinecek_index)
                st.success("Silindi!")
                st.rerun()

# --- DASHBOARD (GELİŞMİŞ) ---
st.title("📊 Varlık ve Bütçe Yönetimi")

if not df.empty:
    # FİLTRELEME
    col_f1, col_f2 = st.columns(2)
    yillar = sorted(df["Yıl"].unique().tolist(), reverse=True)
    aylar = ["Tümü"] + list(df["Ay"].unique())
    
    sec_yil = col_f1.selectbox("Yıl Seçin", yillar)
    sec_ay = col_f2.selectbox("Ay Seçin", aylar)
    
    df_f = df[df["Yıl"] == sec_yil]
    if sec_ay != "Tümü":
        df_f = df_f[df_f["Ay"] == sec_ay]

    # --- HESAPLAMALAR ---
    # Gelirler
    top_gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    
    # Giderler (Sadece harcamalar)
    top_gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    
    # Yatırımlar (Varlıklar)
    top_yatirim = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()
    
    # Kalan Nakit = Gelir - (Gider + Yatırım) -> Çünkü yatırım için de para harcadın
    kalan_nakit = top_gelir - (top_gider + top_yatirim)
    
    # --- KARTLAR (METRICS) ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Gelir", f"{top_gelir:,.0f} ₺", help="Maaş ve Ek Gelirler")
    c2.metric("Harcamalar (Gider)", f"{top_gider:,.0f} ₺", delta_color="inverse", help="Çöpe giden paralar (Faturalar, Market vs)")
    c3.metric("Yatırımlar", f"{top_yatirim:,.0f} ₺", delta_color="normal", help="Altın, Döviz, Borsa birikimleri")
    c4.metric("Kalan Nakit", f"{kalan_nakit:,.0f} ₺", delta=f"{kalan_nakit:,.0f} ₺", help="Cebinde kalan harcanabilir para")
    
    st.divider()
    
    # --- GRAFİKLER ---
    tab1, tab2 = st.tabs(["📉 Gider Analizi", "💰 Yatırım Sepetim"])
    
    with tab1:
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Para Nereye Gitti?")
            df_g = df_f[df_f["Tur"] == "Gider"]
            if not df_g.empty:
                fig = px.pie(df_g, values="Tutar", names="Kategori", hole=0.4, title="Harcama Dağılımı")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Bu dönemde hiç gider yok.")
        with g2:
            st.subheader("Gelir vs Gider vs Yatırım")
            ozet_data = pd.DataFrame({
                "Tip": ["Gelir", "Gider", "Yatırım"],
                "Tutar": [top_gelir, top_gider, top_yatirim]
            })
            fig2 = px.bar(ozet_data, x="Tip", y="Tutar", color="Tip", 
                          color_discrete_map={"Gelir": "#00CC96", "Gider": "#EF553B", "Yatırım": "#636EFA"})
            st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.subheader("Yatırım Portföyüm (Ne Kadar Birikti?)")
        df_y = df_f[df_f["Tur"] == "Yatırım"]
        
        if not df_y.empty:
            col_y1, col_y2 = st.columns([2, 1])
            with col_y1:
                # Yatırım türüne göre dağılım
                fig_y = px.sunburst(df_y, path=['Kategori', 'Aciklama'], values='Tutar', title="Yatırım Detayları")
                st.plotly_chart(fig_y, use_container_width=True)
            with col_y2:
                # Liste halinde göster
                st.write("📋 **Yatırım Listesi**")
                st.dataframe(df_y[["Tarih", "Aciklama", "Tutar"]], hide_index=True)
        else:
            st.warning("Bu dönemde henüz bir yatırım yapmadınız.")

    # --- TÜM LİSTE ---
    st.divider()
    st.subheader("📋 Tüm İşlem Dökümü")
    st.dataframe(df_f.sort_values(by="Tarih", ascending=False), use_container_width=True)

else:
    st.info("Veritabanı boş. Menüden ilk kaydını ekle!")
