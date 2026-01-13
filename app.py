import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
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

# --- VERİ YÜKLEME VE SENİN TEMİZLEME FONKSİYONUN ---
def veri_yukle():
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    data = worksheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
    df = pd.DataFrame(data)
    
    if not df.empty and "Tutar" in df.columns:
        # SENİN GÖNDERDİĞİN SAĞLAM TEMİZLEME KODU
        def temizle(x):
            try:
                if isinstance(x, (int, float)):
                    return float(x)

                x = str(x).strip()
                x = x.replace("₺", "").replace("TL", "").strip()

                # Eğer hem nokta hem virgül varsa → Türkçe format (Örn: 1.250,50)
                if "," in x and "." in x:
                    x = x.replace(".", "").replace(",", ".")
                # Sadece virgül varsa → Türkçe ondalık (Örn: 1250,50)
                elif "," in x:
                    x = x.replace(",", ".")
                
                # Sadece nokta varsa (Python standardı) zaten float(x) onu halleder.
                return float(x)
            except:
                return 0.0

        df["Tutar"] = df["Tutar"].apply(temizle)
        
    return df

# --- VERİ KAYDETME (RAW MODU - HATA ÖNLEYİCİ) ---
def veri_kaydet(yeni_satir_df):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    
    # Tarihi string yapıyoruz
    yeni_satir_df["Tarih"] = yeni_satir_df["Tarih"].astype(str)
    
    liste = yeni_satir_df.values.tolist()
    for row in liste:
        # RAW modu: Sayıları metne çevirmeden, matematiksel değer olarak gönderir.
        # Böylece Google Sheets nokta/virgül yorumu yapmaz, direkt sayıyı hücreye yazar.
        worksheet.append_row(row, value_input_option='RAW')

# --- AYARLAR SEKME FONKSİYONLARI ---
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
        # Buradaki okuma işlemi için de senin mantığını kullanabiliriz basitçe
        gold_raw = str(data_dict.get('gram_altin', 6400)).replace(",", ".")
        saved_gold = float(gold_raw)
        
        silver_raw = str(data_dict.get('gram_gumus', 80)).replace(",", ".")
        saved_silver = float(silver_raw)
    except:
        saved_gold, saved_silver = 6400.00, 80.00
    return saved_gold, saved_silver

def piyasa_fiyatlarini_guncelle(yeni_altin, yeni_gumus):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    ws = sh.worksheet(AYARLAR_TAB_ADI)
    # Fiyatları da RAW olarak sayı formatında gönderelim
    ws.update_acell('B2', new_val=yeni_altin)
    ws.update_acell('B3', new_val=yeni_gumus)

# --- TOPLU SİLME ---
def toplu_sil(silinecek_indexler):
    client = get_gspread_client()
    sh = client.open(SHEET_ADI)
    worksheet = sh.sheet1
    data = worksheet.get_all_records()
    df_mevcut = pd.DataFrame(data)
    df_yeni = df_mevcut.drop(index=silinecek_indexler)
    worksheet.clear()
    worksheet.append_row(df_mevcut.columns.tolist())
    if not df_yeni.empty:
        # Geri yüklerken tarihlerin string olduğundan emin olalım
        # ve RAW modunda gönderelim
        values = df_yeni.values.tolist()
        for i in range(len(values)):
            values[i][0] = str(values[i][0]) # Tarih sütunu
        worksheet.append_rows(values, value_input_option='RAW')

# --- ANA VERİYİ ÇEK ---
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
    except Exception as e:
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
    st.session_state['piyasa_usd'] = 0
    st.session_state['piyasa_eur'] = 0

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
                
                # --- HESAPLAMA VE KAYIT (RAW MODUNA UYGUN) ---
                # Burada string formatlama yapmıyoruz. Direkt float (sayı) gönderiyoruz.
                # veri_kaydet fonksiyonundaki 'RAW' ayarı bunu Sheets'e doğru aktaracak.
                
                if taksit_sayisi > 1:
                    raw_tutar = round(tutar_giris / taksit_sayisi, 2)
                    
                    for i in range(taksit_sayisi):
                        gelecek_tarih = tarih_giris + relativedelta(months=i)
                        yeni_aciklama = f"{aciklama_giris} ({i+1}/{taksit_sayisi}. Taksit)"
                        
                        rows_to_add.append({
                            "Tarih": gelecek_tarih.strftime("%Y-%m-%d"),
                            "Ay": ay_map[gelecek_tarih.month],
                            "Yıl": gelecek_tarih.year,
                            "Kategori": kategori_giris,
                            "Aciklama": yeni_aciklama,
                            "Tutar": raw_tutar, # Direkt Sayı (Float)
                            "Tur": tur_giris
                        })
                else:
                    final_aciklama = miktar_bilgisi + aciklama_giris if aciklama_giris else miktar_bilgisi + tur_giris
                    
                    rows_to_add.append({
                        "Tarih": tarih_giris.strftime("%Y-%m-%d"),
                        "Ay": ay_map[tarih_giris.month],
                        "Yıl": tarih_giris.year,
                        "Kategori": kategori_giris,
                        "Aciklama": final_aciklama,
                        "Tutar": float(tutar_giris), # Direkt Sayı (Float)
                        "Tur": tur_giris
                    })
                
                yeni_veri = pd.DataFrame(rows_to_add)
                veri_kaydet(yeni_veri)
                
            st.success(f"{len(rows_to_add)} adet kayıt eklendi!")
            st.rerun()

    # --- SİLME BÖLÜMÜ ---
    st.divider()
    if not df.empty:
        with st.expander("🗑️ Kayıt Sil (Akıllı)"):
            st.info("Bir taksiti seçerseniz, sistem o taksit grubunun tamamını silmeyi teklif eder.")
            df_gosterim = df.reset_index().sort_index(ascending=False)
            
            secenekler = df_gosterim.apply(lambda x: f"NO: {x['index']} | {x['Tarih']} | {x['Aciklama']} | {x['Tutar']:,.2f} ₺", axis=1)
            sil_secim = st.selectbox("Silinecek Kayıt:", secenekler)
            
            if sil_secim:
                secilen_index = int(sil_secim.split("|")[0].replace("NO:", "").strip())
                secilen_satir = df.loc[secilen_index]
                aciklama = secilen_satir["Aciklama"]
                tutar = secilen_satir["Tutar"]
                match = re.search(r"(.*?) \((\d+)/(\d+)\. Taksit\)", str(aciklama))
                
                silinecek_liste = [secilen_index]
                buton_metni = "Sadece Bu Kaydı Sil"
                is_toplu = False
                
                if match:
                    urun_adi = match.group(1) 
                    toplam_taksit = match.group(3)
                    
                    benzerler = df[
                        (df["Aciklama"].str.contains(re.escape(urun_adi), na=False)) & 
                        (df["Aciklama"].str.contains(f"/{toplam_taksit}. Taksit", na=False)) &
                        (df["Tutar"] == tutar)
                    ]
                    
                    if not benzerler.empty:
                        silinecek_liste = benzerler.index.tolist()
                        is_toplu = True
                        st.warning(f"⚠️ Bu bir taksitli işlem! ({urun_adi})")
                        st.write(f"Bu gruba ait toplam **{len(silinecek_liste)}** adet taksit bulundu.")
                        buton_metni = f"🔴 Tüm Taksit Grubunu Sil ({len(silinecek_liste)} Kayıt)"
                
                if st.button(buton_metni):
                    with st.spinner('Kayıtlar veritabanından siliniyor...'):
                        toplu_sil(silinecek_liste)
                    msg = "Tüm taksitler başarıyla silindi!" if is_toplu else "Kayıt silindi!"
                    st.success(msg)
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
            guncel_gold = st.session_state.get('piyasa_gold', 0)
            guncel_silver = st.session_state.get('piyasa_silver', 0)
            guncel_usd = 0 
            guncel_eur = 0
            
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
                    elif "gümüş" in kategori:
                        return miktar * guncel_silver
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
