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

# --- YENİ VERİ YÜKLEME (GARANTİLİ YÖNTEM) ---
def veri_yukle():
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    
    # get_all_records yerine get_all_values kullanıyoruz.
    # Bu sayede veriler ham string (metin) olarak gelir, Pandas yorum katamaz.
    tum_veriler = worksheet.get_all_values()
    
    if not tum_veriler or len(tum_veriler) < 2:
        return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
    
    # İlk satırı başlık yap
    header = tum_veriler[0]
    rows = tum_veriler[1:]
    
    df = pd.DataFrame(rows, columns=header)
    
    # TEMİZLEME FONKSİYONU (HATA ÖNLEYİCİ)
    def temizle(x):
        try:
            # Önce metne çevir ve boşlukları/sembolleri at
            x_str = str(x).strip().replace("₺", "").replace("TL", "").strip()
            
            # Eğer boşsa 0 dön
            if not x_str:
                return 0.0
            
            # Eğer veri zaten "1963,33" gibiyse (Virgül var)
            if "," in x_str:
                # Noktaları (binlik) sil: 1.000,50 -> 1000,50
                x_str = x_str.replace(".", "")
                # Virgülü noktaya çevir: 1000,50 -> 1000.50
                x_str = x_str.replace(",", ".")
                return float(x_str)
            
            # Eğer veri "1963.33" gibiyse (Sadece nokta var)
            elif "." in x_str:
                # Burası kritik: Eğer noktadan sonra 1 veya 2 basamak varsa ondalıktır.
                # Örn: 1963.33 -> Sayıdır.
                # Örn: 1.000 -> Binliktir.
                # Ama riske girmemek için Python mantığıyla direkt çevirmeyi deneriz.
                try:
                    return float(x_str)
                except:
                    # Çevrilemiyorsa binlik noktasıdır, silip deneriz
                    return float(x_str.replace(".", ""))
            
            # Hiçbiri yoksa direkt çevir
            return float(x_str)
            
        except:
            return 0.0

    if not df.empty and "Tutar" in df.columns:
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
    
    # Yeniden yükle ve sil
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
        # Virgül/Nokta temizliği
        gold_str = str(data_dict.get('gram_altin', 6400)).replace(",", ".")
        saved_gold = float(gold_str)
        
        silver_str = str(data_dict.get('gram_gumus', 80)).replace(",", ".")
        saved_silver = float(silver_str)
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
    st.info("Güncel piyasa fiyatlarını giriniz.")
    
    try:
        kayitli_altin, kayitli_gumus = piyasa_fiyatlarini_getir_veya_olustur()
    except:
        kayitli_altin, kayitli_gumus = 6400.00, 80.00
    
    gold_val = st.number_input("Gr Altın (₺)", value=kayitli_altin, step=10.0, format="%.2f")
    silver_val = st.number_input("Gr Gümüş (₺)", value=kayitli_gumus, step=1.0, format="%.2f")
    
    if st.button("Fiyatları Sabitle 💾"):
        with st.spinner("Ayarlar kaydediliyor..."):
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
        is_taksit = st.checkbox("Taksitli mi?")
        if is_taksit:
            taksit_sayisi = st.slider("Taksit Sayısı", 2, 12, 3)
            st.caption(f"ℹ️ Tutar {taksit_sayisi} aya bölünecek.")
    
    miktar_bilgisi = ""
    if tur_giris == "Gider":
        kategoriler = ["Kredi Kartı", "Mutfak", "Fatura", "Kira", "Ulaşım", "Market", "Sağlık", "Giyim", "Eğitim", "Diğer"]
    elif tur_giris == "Gelir":
        kategoriler = ["Maaş", "Ek Gelir", "Prim", "Borç Alacak"]
    else: # YATIRIM
        kategoriler = ["Altın", "Gümüş", "Döviz", "Borsa", "Fon", "Bitcoin", "Bes"]
        miktar = st.text_input("Miktar (Örn: 5 Gram)")
        if miktar: miktar_bilgisi = f"[{miktar}] "

    kategori_giris = st.selectbox("Kategori", kategoriler)
    aciklama_giris = st.text_input("Açıklama")
    
    # --- TUTAR GİRİŞİ (TEXT INPUT İLE KONTROL) ---
    tutar_text = st.text_input("Toplam Tutar (₺)", placeholder="Örn: 5890,00")
    
    def parse_tutar_manual(x):
        try:
            x = x.replace("₺", "").replace("TL", "").strip()
            x = x.replace(".", "").replace(",", ".")
            return float(x)
        except:
            return 0.0

    tutar_float = parse_tutar_manual(tutar_text) if tutar_text else 0.0
    
    # HESAPLAMA VE GÖNDERİM LİSTESİ HAZIRLIĞI
    rows_to_send = [] 
    
    if tutar_float > 0:
        ay_map = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                  7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}
        
        # Gönderirken "1963,33" formatına çeviriyoruz (TR Standardı)
        if taksit_sayisi > 1:
            raw_aylik = tutar_float / taksit_sayisi
            tutar_str_tr = "{:.2f}".format(raw_aylik).replace(".", ",")
            
            for i in range(taksit_sayisi):
                gelecek_tarih = tarih_giris + relativedelta(months=i)
                yeni_aciklama = f"{aciklama_giris} ({i+1}/{taksit_sayisi}. Taksit)"
                
                rows_to_send.append([
                    str(gelecek_tarih.strftime("%Y-%m-%d")),
                    ay_map[gelecek_tarih.month],
                    gelecek_tarih.year,
                    kategori_giris,
                    yeni_aciklama,
                    tutar_str_tr,
                    tur_giris
                ])
        else:
            final_aciklama = miktar_bilgisi + aciklama_giris if aciklama_giris else miktar_bilgisi + tur_giris
            tutar_str_tr = "{:.2f}".format(tutar_float).replace(".", ",")
            
            rows_to_send.append([
                str(tarih_giris.strftime("%Y-%m-%d")),
                ay_map[tarih_giris.month],
                tarih_giris.year,
                kategori_giris,
                final_aciklama,
                tutar_str_tr,
                tur_giris
            ])

        st.caption("📝 **Kayıt Önizlemesi**")
        st.info(f"Girilen: {tutar_float:,.2f} TL -> Kaydedilecek: **{rows_to_send[0][5]} TL**")
        
    if st.button("Kaydet 💾", type="primary"):
        if tutar_float > 0 and rows_to_send:
            with st.spinner('Google Sheets\'e yazılıyor...'):
                veri_kaydet_liste(rows_to_send)
            st.success(f"{len(rows_to_send)} adet kayıt başarıyla eklendi!")
            st.rerun()
        elif tutar_float == 0:
            st.error("Lütfen geçerli bir tutar girin.")

    # --- HATA AYIKLAMA MODU (GİZLİ) ---
    # Burayı açarak Drive'dan verinin NASIL geldiğini görebilirsin.
    with st.expander("🛠️ Hata Ayıklama (Drive'dan Gelen Ham Veri)"):
        st.write("Veritabanından okunan ilk 5 satırın 'Tutar' sütunu:")
        if not df.empty:
            st.write(df[["Tarih", "Aciklama", "Tutar"]].head())
        else:
            st.write("Veri yok.")

    # --- SİLME ---
    st.divider()
    if not df.empty:
        with st.expander("🗑️ Kayıt Sil (Akıllı)"):
            df_gosterim = df.reset_index().sort_index(ascending=False)
            secenekler = df_gosterim.apply(lambda x: f"NO: {x['index']} | {x['Tarih']} | {x['Aciklama']} | {x['Tutar']:,.2f} ₺", axis=1)
            sil_secim = st.selectbox("Silinecek Kayıt:", secenekler)
            
            if st.button("Seçiliyi Sil"):
                if sil_secim:
                    idx = int(sil_secim.split("|")[0].replace("NO:", "").strip())
                    row_data = df.loc[idx]
                    aciklama = str(row_data["Aciklama"])
                    tutar = row_data["Tutar"]
                    
                    match = re.search(r"(.*?) \((\d+)/(\d+)\. Taksit\)", aciklama)
                    silinecekler = [idx]
                    
                    if match:
                        urun = match.group(1)
                        toplam_taksit = match.group(3)
                        benzerler = df[
                            (df["Aciklama"].str.contains(re.escape(urun), na=False)) &
                            (df["Aciklama"].str.contains(f"/{toplam_taksit}. Taksit", na=False)) &
                            (df["Tutar"] == tutar)
                        ]
                        if not benzerler.empty:
                            silinecekler = benzerler.index.tolist()
                            st.info(f"Tüm taksit grubu siliniyor... ({len(silinecekler)} kayıt)")

                    toplu_sil(silinecekler)
                    st.success("Silindi!")
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
    if sec_ay != "Tümü":
        df_f = df_f[df_f["Ay"] == sec_ay]

    top_gelir = df_f[df_f["Tur"] == "Gelir"]["Tutar"].sum()
    top_gider = df_f[df_f["Tur"] == "Gider"]["Tutar"].sum()
    top_yatirim_maliyet = df_f[df_f["Tur"] == "Yatırım"]["Tutar"].sum()
    kalan_nakit = top_gelir - (top_gider + top_yatirim_maliyet)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Gelir", f"{top_gelir:,.2f} ₺")
    c2.metric("Giderler", f"{top_gider:,.2f} ₺", delta_color="inverse")
    c3.metric("Yatırım (Maliyet)", f"{top_yatirim_maliyet:,.2f} ₺")
    c4.metric("Kalan Nakit", f"{kalan_nakit:,.2f} ₺")
    
    st.divider()
    
    # GRAFİKLER
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
        df_y = df[df["Tur"] == "Yatırım"].copy()
        if not df_y.empty:
            guncel_gold = st.session_state.get('piyasa_gold', 0)
            guncel_silver = st.session_state.get('piyasa_silver', 0)
            
            def calculate_current(row):
                desc = str(row["Aciklama"])
                cat = str(row["Kategori"]).lower()
                import re
                match = re.search(r'\[([\d\.,]+)', desc)
                if match:
                    qty_str = match.group(1).replace(".", "").replace(",", ".")
                    try: qty = float(qty_str)
                    except: return 0
                    
                    if "altın" in cat: return qty * guncel_gold
                    if "gümüş" in cat: return qty * guncel_silver
                return row["Tutar"]

            df_y["Guncel"] = df_y.apply(calculate_current, axis=1)
            df_y["Fark"] = df_y["Guncel"] - df_y["Tutar"]
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Maliyet", f"{df_y['Tutar'].sum():,.2f} ₺")
            k2.metric("Piyasa Değeri", f"{df_y['Guncel'].sum():,.2f} ₺")
            k3.metric("Kâr/Zarar", f"{df_y['Fark'].sum():,.2f} ₺")
            
            st.dataframe(df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Guncel", "Fark"]], use_container_width=True)
        else:
            st.info("Yatırım kaydı yok.")

    st.divider()
    st.subheader("📋 Tüm İşlemler")
    st.dataframe(df_f.sort_values("Tarih", ascending=False), use_container_width=True)
else:
    st.info("Veri yok.")
