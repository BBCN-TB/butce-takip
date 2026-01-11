import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import random  # <-- YENİ EKLENDİ (Önbelleği kırmak için)

# --- AYARLAR ---
SHEET_ADI = "Butce_Veritabanı"
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

def veri_yukle():
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    data = worksheet.get_all_records()
    
    if not data:
        return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
        
    df = pd.DataFrame(data)
    if not df.empty and "Tutar" in df.columns:
        df["Tutar"] = df["Tutar"].astype(str).str.replace(" TL", "").str.replace(" ₺", "").str.replace(".", "").str.replace(",", ".").astype(float)
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

# --- ÖZELLİK 1: CANLI PİYASA VERİLERİ (GÜNCELLENMİŞ CACHE-BUSTER) ---
def piyasa_verileri_getir():
    # 1. YÖNTEM: TRUNCGIL API (Önbellek Kırıcı Eklendi)
    try:
        # URL'nin sonuna rastgele sayı ekliyoruz (?v=0.123123) ki sistem eski veriyi getirmesin.
        url = f"https://finans.truncgil.com/today.json?v={random.random()}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # timeout süresini kısalttık ki takılmasın
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            usd = float(data['USD']['satis'].replace(",", "."))
            eur = float(data['EUR']['satis'].replace(",", "."))
            gold = float(data['gram-altin']['satis'].replace(",", "."))
            return usd, eur, gold
    except:
        pass 

    # 2. YÖNTEM: GLOBAL API
    try:
        r_usd = requests.get(f"https://api.frankfurter.app/latest?from=USD&to=TRY&v={random.random()}", timeout=3).json()
        usd = r_usd["rates"]["TRY"]
        r_eur = requests.get(f"https://api.frankfurter.app/latest?from=EUR&to=TRY&v={random.random()}", timeout=3).json()
        eur = r_eur["rates"]["TRY"]
        gold_ons = 2650 
        ham_gold = (gold_ons / 31.1035) * usd
        gold = ham_gold * 1.75 
        return usd, eur, gold
    except:
        pass 

    # 3. YÖNTEM: VARSAYILAN
    return 36.50, 38.20, 6370.00

# --- ANA VERİYİ ÇEK ---
try:
    df = veri_yukle()
except Exception as e:
    st.error(f"Google Sheets Bağlantı Hatası: {e}")
    st.stop()

# --- SOL MENÜ ---
with st.sidebar:
    st.header("🌍 Canlı Piyasa")
    
    # GÜNCELLEME BUTONU (YENİ)
    if st.button("🔄 Piyasayı Güncelle"):
        st.cache_data.clear() # Varsa önbelleği temizle
        st.rerun() # Sayfayı yenile

    # Verileri Çek
    usd_val, eur_val, gold_val = piyasa_verileri_getir()
    
    # Ekrana Yazdır
    c1, c2 = st.columns(2)
    c1.metric("Dolar", f"{usd_val:.2f} ₺")
    c2.metric("Euro", f"{eur_val:.2f} ₺")
    
    st.metric("Gr Altın (24K)", f"{gold_val:,.2f} ₺")
    st.caption(f"Son Kontrol: {datetime.now().strftime('%H:%M:%S')}") # Saati gösterelim ki emin ol
    
    # Hafızaya at
    st.session_state['piyasa_usd'] = usd_val
    st.session_state['piyasa_eur'] = eur_val
    st.session_state['piyasa_gold'] = gold_val
    
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
    tutar_giris = st.number_input("Toplam Tutar (₺)", min_value=0.0, format="%.2f")
    
    if st.button("Kaydet 💾", type="primary"):
        if tutar_giris > 0:
            with st.spinner('İşleniyor...'):
                ay_map = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                          7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}
                
                rows_to_add = []
                
                if taksit_sayisi > 1:
                    aylik_tutar = tutar_giris / taksit_sayisi
                    for i in range(taksit_sayisi):
                        gelecek_tarih = tarih_giris + relativedelta(months=i)
                        yeni_aciklama = f"{aciklama_giris} ({i+1}/{taksit_sayisi}. Taksit)"
                        
                        rows_to_add.append({
                            "Tarih": gelecek_tarih,
                            "Ay": ay_map[gelecek_tarih.month],
                            "Yıl": gelecek_tarih.year,
                            "Kategori": kategori_giris,
                            "Aciklama": yeni_aciklama,
                            "Tutar": aylik_tutar,
                            "Tur": tur_giris
                        })
                else:
                    final_aciklama = miktar_bilgisi + aciklama_giris if aciklama_giris else miktar_bilgisi + tur_giris
                    rows_to_add.append({
                        "Tarih": tarih_giris,
                        "Ay": ay_map[tarih_giris.month],
                        "Yıl": tarih_giris.year,
                        "Kategori": kategori_giris,
                        "Aciklama": final_aciklama,
                        "Tutar": tutar_giris,
                        "Tur": tur_giris
                    })
                
                yeni_veri = pd.DataFrame(rows_to_add)
                veri_kaydet(yeni_veri)
                
            st.success(f"{len(rows_to_add)} adet kayıt eklendi!")
            st.rerun()

    # --- SABİT GİDER KOPYALAMA ---
    st.divider()
    with st.expander("🔄 Geçen Ayın Sabitlerini Kopyala"):
        if st.button("Kopyala ve Ekle"):
            if not df.empty:
                bugun = datetime.today()
                gecen_ay_tarih = bugun - relativedelta(months=1)
                gecen_ay_isim = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                                 7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}[gecen_ay_tarih.month]
                
                sabit_kategoriler = ["Kira", "Fatura", "Aidat", "Eğitim", "İnternet"]
                
                kopya_df = df[
                    (df["Ay"] == gecen_ay_isim) & 
                    (df["Yıl"] == gecen_ay_tarih.year) & 
                    (df["Kategori"].isin(sabit_kategoriler))
                ].copy()
                
                if not kopya_df.empty:
                    kopya_df["Tarih"] = bugun.strftime("%Y-%m-%d")
                    kopya_df["Ay"] = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                          7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}[bugun.month]
                    kopya_df["Yıl"] = bugun.year
                    kopya_df["Aciklama"] = kopya_df["Aciklama"] + " (Kopya)"
                    
                    with st.spinner('Kopyalanıyor...'):
                        veri_kaydet(kopya_df)
                    st.success(f"{len(kopya_df)} adet sabit gider kopyalandı!")
                    st.rerun()
                else:
                    st.warning("Geçen ay uygun sabit gider bulunamadı.")

    # SİLME BÖLÜMÜ
    st.divider()
    if not df.empty:
        with st.expander("🗑️ Kayıt Sil"):
            df_gosterim = df.reset_index().sort_index(ascending=False)
            secenekler = df_gosterim.apply(lambda x: f"NO: {x['index']} | {x['Tur']} | {x['Kategori']} | {x['Tutar']:,.2f} ₺", axis=1)
            sil_secim = st.selectbox("Silinecek Kayıt:", secenekler)
            if st.button("Seçiliyi Sil"):
                silinecek_index = int(sil_secim.split("|")[0].replace("NO:", "").strip())
                kayit_sil(silinecek_index)
                st.success("Silindi!")
                st.rerun()

# --- DASHBOARD (AKILLI KAR/ZARAR HESAPLAMALI) ---
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
    c3.metric("Yatırım (Maliyet)", f"{top_yatirim_maliyet:,.2f} ₺", help="Cebinden çıkan nakit para")
    c4.metric("Kalan Nakit", f"{kalan_nakit:,.2f} ₺", delta=f"{kalan_nakit:,.2f} ₺")
    
    st.divider()
    
    tab1, tab2 = st.tabs(["📉 Gider Analizi", "💰 Portföy Kâr/Zarar"])
    
    with tab1:
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Para Çıkış Dağılımı")
            df_pie = df_f[df_f["Tur"].isin(["Gider", "Yatırım"])]
            if not df_pie.empty:
                fig = px.pie(df_pie, values="Tutar", names="Kategori", hole=0.4)
                fig.update_traces(textinfo='percent+label', texttemplate='%{label}<br>%{value:,.0f} ₺')
                st.plotly_chart(fig, use_container_width=True)
        with g2:
            st.subheader("Bütçe Dengesi")
            ozet_data = pd.DataFrame({"Tip": ["Gelir", "Gider", "Yatırım"], "Tutar": [top_gelir, top_gider, top_yatirim_maliyet]})
            fig2 = px.bar(ozet_data, x="Tip", y="Tutar", color="Tip", text="Tutar",
                          color_discrete_map={"Gelir": "#00CC96", "Gider": "#EF553B", "Yatırım": "#636EFA"})
            fig2.update_traces(texttemplate='%{text:,.0f} ₺', textposition='outside')
            st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.subheader("Yatırım Portföyüm ve Canlı Durum")
        
        df_y = df[df["Tur"] == "Yatırım"].copy() 
        
        if not df_y.empty:
            guncel_usd = st.session_state.get('piyasa_usd', 0)
            guncel_eur = st.session_state.get('piyasa_eur', 0)
            guncel_gold = st.session_state.get('piyasa_gold', 0)
            
            def guncel_deger_hesapla(row):
                kategori = str(row["Kategori"]).lower()
                aciklama = str(row["Aciklama"])
                import re
                match = re.search(r'\[([\d\.,]+)', aciklama)
                
                if match:
                    miktar_str = match.group(1).replace(",", ".")
                    try:
                        miktar = float(miktar_str)
                    except:
                        return 0
                    
                    if "altın" in kategori:
                        return miktar * guncel_gold
                    elif "dolar" in kategori or "döviz" in kategori:
                        if "euro" in aciklama.lower():
                            return miktar * guncel_eur
                        return miktar * guncel_usd
                    elif "euro" in kategori:
                        return miktar * guncel_eur
                    else:
                        return row["Tutar"]
                else:
                    return row["Tutar"]

            df_y["Güncel Değer (₺)"] = df_y.apply(guncel_deger_hesapla, axis=1)
            df_y["Fark (₺)"] = df_y["Güncel Değer (₺)"] - df_y["Tutar"]
            
            toplam_maliyet = df_y["Tutar"].sum()
            toplam_guncel = df_y["Güncel Değer (₺)"].sum()
            toplam_fark = toplam_guncel - toplam_maliyet
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Toplam Yatırım Maliyeti", f"{toplam_maliyet:,.2f} ₺")
            k2.metric("Şu Anki Piyasa Değeri", f"{toplam_guncel:,.2f} ₺")
            k3.metric("Net Kâr/Zarar", f"{toplam_fark:,.2f} ₺", delta=f"{toplam_fark:,.2f} ₺")
            
            st.divider()
            
            st.write("📋 **Varlık Bazlı Detaylar**")
            df_goster = df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Güncel Değer (₺)", "Fark (₺)"]].sort_values(by="Tarih", ascending=False)
            
            st.dataframe(
                df_goster.style.format({
                    "Tutar": "{:,.2f} ₺",
                    "Güncel Değer (₺)": "{:,.2f} ₺",
                    "Fark (₺)": "{:,.2f} ₺"
                }).applymap(lambda v: 'color: red;' if v < 0 else 'color: green;', subset=['Fark (₺)']),
                use_container_width=True
            )
            
        else:
            st.info("Henüz portföyünde yatırım yok.")

    st.divider()
    st.subheader("📋 Tüm İşlemler")
    df_all = df_f.sort_values(by="Tarih", ascending=False).copy()
    df_all["Tutar"] = df_all["Tutar"].apply(lambda x: f"{x:,.2f} ₺")
    st.dataframe(df_all, use_container_width=True)

else:
    st.info("Veritabanı boş.")
