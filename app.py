import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

# --- AYARLAR ---
SHEET_ADI = "Butce_Veritabanı"
AYARLAR_TAB_ADI = "Ayarlar"
st.set_page_config(page_title="Akıllı Bütçe", layout="wide", page_icon="📈")

# --- GİRİŞ KONTROLÜ ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True
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

# --- VERİ YÜKLEME ---
def veri_yukle():
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    tum_veriler = worksheet.get_all_values()
    
    if not tum_veriler or len(tum_veriler) < 2:
        return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
    
    header = tum_veriler[0]
    rows = tum_veriler[1:]
    df = pd.DataFrame(rows, columns=header)
    
    if not df.empty and "Tutar" in df.columns:
        def temizle(x):
            try:
                if isinstance(x, (int, float)): return float(x)
                x_str = str(x).strip().replace("₺", "").replace("TL", "").strip()
                if not x_str: return 0.0
                if "," in x_str:
                    x_str = x_str.replace(".", "").replace(",", ".")
                    return float(x_str)
                elif "." in x_str:
                    try: return float(x_str)
                    except: return float(x_str.replace(".", ""))
                return float(x_str)
            except:
                return 0.0
        df["Tutar"] = df["Tutar"].apply(temizle)
    return df

# --- VERİ KAYDETME ---
def veri_kaydet_liste(satirlar_listesi):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    worksheet.append_rows(satirlar_listesi, value_input_option='USER_ENTERED')

# --- TOPLU SİLME ---
def toplu_sil(silinecek_indexler):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    tum_veriler = worksheet.get_all_values()
    header = tum_veriler[0]
    rows = tum_veriler[1:]
    df_mevcut = pd.DataFrame(rows, columns=header)
    df_yeni = df_mevcut.drop(index=silinecek_indexler)
    worksheet.clear()
    worksheet.append_row(header)
    if not df_yeni.empty:
        values = df_yeni.astype(str).values.tolist()
        worksheet.append_rows(values, value_input_option='USER_ENTERED')

# --- AYARLAR ---
def piyasa_fiyatlarini_getir_veya_olustur():
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
        saved_gold = float(str(data_dict.get('gram_altin', 6400)).replace(",", "."))
        saved_silver = float(str(data_dict.get('gram_gumus', 80)).replace(",", "."))
    except:
        saved_gold, saved_silver = 6400.00, 80.00
    return saved_gold, saved_silver

def piyasa_fiyatlarini_guncelle(yeni_altin, yeni_gumus):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    ws = sh.worksheet(AYARLAR_TAB_ADI)
    ws.update_acell('B2', yeni_altin)
    ws.update_acell('B3', yeni_gumus)

# --- ANA PROGRAM ---
try:
    df = veri_yukle()
except Exception as e:
    st.error(f"Google Sheets Bağlantı Hatası: {e}")
    st.stop()

# --- SOL MENÜ ---
with st.sidebar:
    st.header("💰 Piyasa Fiyatları")
    kayitli_altin, kayitli_gumus = piyasa_fiyatlarini_getir_veya_olustur()
    gold_val = st.number_input("Gr Altın (₺)", value=kayitli_altin, format="%.2f")
    silver_val = st.number_input("Gr Gümüş (₺)", value=kayitli_gumus, format="%.2f")
    
    if st.button("Fiyatları Sabitle 💾"):
        piyasa_fiyatlarini_guncelle(gold_val, silver_val)
        st.success("Fiyatlar güncellendi!")
        st.rerun()

    st.session_state['piyasa_gold'] = gold_val
    st.session_state['piyasa_silver'] = silver_val
    st.divider()

    # --- İŞLEM EKLEME ---
    st.header("💸 İşlem Ekle")
    tarih_giris = st.date_input("Tarih", datetime.today())
    tur_giris = st.selectbox("Tür", ["Gider", "Gelir", "Yatırım"])
    
    taksit_sayisi = 1
    if tur_giris == "Gider":
        if st.checkbox("Taksitli mi?"):
            taksit_sayisi = st.slider("Taksit Sayısı", 2, 12, 3)

    if tur_giris == "Gider":
        kategoriler = ["Kredi Kartı", "Mutfak", "Fatura", "Kira", "Ulaşım", "Market", "Sağlık", "Giyim", "Eğitim", "Diğer"]
    elif tur_giris == "Gelir":
        kategoriler = ["Maaş", "Ek Gelir", "Prim", "Borç Alacak"]
    else:
        kategoriler = ["Altın", "Gümüş", "Döviz", "Borsa", "Fon", "Bitcoin", "Bes"]
        miktar = st.text_input("Miktar (Örn: 5 Gram)")
        miktar_bilgisi = f"[{miktar}] " if miktar else ""

    kategori_giris = st.selectbox("Kategori", kategoriler)
    aciklama_giris = st.text_input("Açıklama")
    tutar_text = st.text_input("Toplam Tutar (₺)", placeholder="Örn: 5890,00")
    
    def parse_tutar_manual(x):
        try:
            return float(x.replace("₺", "").replace("TL", "").replace(".", "").replace(",", ".").strip())
        except: return 0.0

    tutar_float = parse_tutar_manual(tutar_text) if tutar_text else 0.0
    
    if st.button("Kaydet 💾", type="primary"):
        if tutar_float > 0:
            ay_map = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}
            rows_to_send = []
            if taksit_sayisi > 1:
                aylik = tutar_float / taksit_sayisi
                for i in range(taksit_sayisi):
                    d = tarih_giris + relativedelta(months=i)
                    rows_to_send.append([d.strftime("%Y-%m-%d"), ay_map[d.month], d.year, kategori_giris, f"{aciklama_giris} ({i+1}/{taksit_sayisi}. Taksit)", "{:.2f}".format(aylik).replace(".", ","), tur_giris])
            else:
                desc = (miktar_bilgisi + aciklama_giris) if tur_giris == "Yatırım" else aciklama_giris
                rows_to_send.append([tarih_giris.strftime("%Y-%m-%d"), ay_map[tarih_giris.month], tarih_giris.year, kategori_giris, desc, "{:.2f}".format(tutar_float).replace(".", ","), tur_giris])
            
            veri_kaydet_liste(rows_to_send)
            st.success("Kaydedildi!")
            st.rerun()

# --- DASHBOARD ---
st.title("📊 Akıllı Bütçe Yönetimi")

if not df.empty:
    col_f1, col_f2 = st.columns(2)
    yillar = sorted(df["Yıl"].unique().tolist(), reverse=True)
    aylar = ["Tümü"] + list(df["Ay"].unique())
    sec_yil = col_f1.selectbox("Yıl", yillar)
    sec_ay = col_f2.selectbox("Ay", aylar)
    
    df_f = df[df["Yıl"] == sec_yil]
    if sec_ay != "Tümü": df_f = df_f[df_f["Ay"] == sec_ay]

    top_gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    top_gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    top_yatirim_maliyet = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()
    kalan_nakit = top_gelir - (top_gider + top_yatirim_maliyet)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Gelir", f"{top_gelir:,.2f} ₺")
    c2.metric("Giderler", f"{top_gider:,.2f} ₺")
    c3.metric("Yatırım (Maliyet)", f"{top_yatirim_maliyet:,.2f} ₺")
    c4.metric("Kalan Nakit", f"{kalan_nakit:,.2f} ₺")
    
    st.divider()
    
    tab1, tab2 = st.tabs(["📉 Gider Analizi", "💰 Portföy Kâr/Zarar"])
    
    with tab1:
        g1, g2 = st.columns(2)
        with g1:
            df_pie = df_f[df_f["Tur"].isin(["Gider", "Yatırım"])]
            if not df_pie.empty:
                fig = px.pie(df_pie, values="Tutar", names="Kategori", hole=0.4, title="Harcama Dağılımı")
                st.plotly_chart(fig, use_container_width=True)
        with g2:
            ozet = df_f.groupby("Tur")["Tutar"].sum().reset_index()
            fig2 = px.bar(ozet, x="Tur", y="Tutar", color="Tur", title="Bütçe Dengesi")
            st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        # --- DÜZELTME BURADA: Sadece 'Yatırım' türündeki verileri alıyoruz ---
        df_y = df[df["Tur"] == "Yatırım"].copy()
        
        if not df_y.empty:
            guncel_gold = st.session_state.get('piyasa_gold', 0)
            guncel_silver = st.session_state.get('piyasa_silver', 0)
            
            def calculate_current(row):
                desc = str(row["Aciklama"])
                cat = str(row["Kategori"]).lower()
                match = re.search(r'\[([\d\.,]+)', desc)
                if match:
                    qty_str = match.group(1).replace(".", "").replace(",", ".")
                    try:
                        qty = float(qty_str)
                        if "altın" in cat: return qty * guncel_gold
                        if "gümüş" in cat: return qty * guncel_silver
                    except: return row["Tutar"]
                return row["Tutar"]

            df_y["Guncel"] = df_y.apply(calculate_current, axis=1)
            df_y["Fark"] = df_y["Guncel"] - df_y["Tutar"]
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Toplam Maliyet", f"{df_y['Tutar'].sum():,.2f} ₺")
            k2.metric("Güncel Değer", f"{df_y['Guncel'].sum():,.2f} ₺")
            k3.metric("Toplam Kâr/Zarar", f"{df_y['Fark'].sum():,.2f} ₺")
            
            st.dataframe(
                df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Guncel", "Fark"]].style.format({
                    "Tutar": "{:,.2f} ₺", "Guncel": "{:,.2f} ₺", "Fark": "{:,.2f} ₺"
                }), use_container_width=True
            )
        else:
            st.info("Henüz yatırım kaydı bulunmuyor.")

    st.divider()
    st.subheader("📋 Filtrelenmiş İşlemler")
    st.dataframe(df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}), use_container_width=True)
else:
    st.info("Henüz veri girişi yapılmamış.")
