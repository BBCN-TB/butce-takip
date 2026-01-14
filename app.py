# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re
import requests 

# --- MODERN MOBİL & WEB TASARIMI (CSS) ---
st.markdown("""
    <style>
    /* 1. Genel Arka Plan ve Yazı Tipleri */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* 2. Metrik Kutularını (Özet Kartlarını) Güzelleştir */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 20px;
        border-radius: 20px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        border-left: 5px solid #007bff;
        transition: transform 0.3s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
    }
    
    /* 3. Butonları Daha Modern Yap */
    .stButton>button {
        border-radius: 12px;
        background: linear-gradient(to right, #007bff, #0056b3);
        color: white;
        font-weight: bold;
        border: none;
        padding: 0.6rem 1rem;
        width: 100%;
    }
    
    /* 4. Veri Tablosunu ve Sidebar'ı Yumuşat */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
    }
    .stDataFrame {
        border-radius: 15px;
        overflow: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

# --- AYARLAR ---
st.set_page_config(page_title="Akıllı Bütçe", layout="wide", page_icon="📈")
API_URL = "http://127.0.0.1:8000"

# --- BASİT ŞİFRE SİSTEMİ (DÜZELTİLEN KISIM) ---
# Bilgisayarında secrets dosyası olmadığı için şifreyi buraya yazıyoruz.
SABIT_SIFRE = "7855" 

def check_password():
    """Giriş kontrolünü yapar."""
    if st.session_state.get("password_correct", False):
        return True
    
    # Şifre giriş kutusu
    st.text_input("Lütfen Şifrenizi Girin", type="password", key="password_input", on_change=password_entered)
    return False

def password_entered():
    """Girilen şifreyi kontrol eder."""
    if st.session_state["password_input"] == SABIT_SIFRE:
        st.session_state["password_correct"] = True
        del st.session_state["password_input"] # Şifreyi hafızadan sil
    else:
        st.error("😕 Şifre Yanlış")

# Eğer şifre doğru girilmediyse dur.
if not check_password():
    st.stop()

# --- API İLE İLETİŞİM FONKSİYONLARI ---
def api_veri_cek():
    try:
        response = requests.get(f"{API_URL}/veriler")
        if response.status_code == 200:
            raw_data = response.json()["data"]
            if not raw_data or len(raw_data) < 2:
                return pd.DataFrame(columns=["Tarih", "Ay", "Yıl", "Kategori", "Aciklama", "Tutar", "Tur"])
            header = raw_data[0]
            rows = raw_data[1:]
            df = pd.DataFrame(rows, columns=header)
            
            # Temizleme
            def temizle(x):
                try:
                    if isinstance(x, (int, float)): return float(x)
                    x_str = str(x).strip().replace("₺", "").replace("TL", "").strip()
                    if not x_str: return 0.0
                    if "," in x_str:
                        x_str = x_str.replace(".", "").replace(",", ".")
                    elif "." in x_str:
                         try: return float(x_str)
                         except: return float(x_str.replace(".", ""))
                    return float(x_str)
                except: return 0.0
            
            if not df.empty and "Tutar" in df.columns:
                df["Tutar"] = df["Tutar"].apply(temizle)
            return df
        else:
            st.error("API Veri Çekemedi (Mutfak Kapalı Olabilir)")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"API Bağlantı Hatası: {e}. 'uvicorn' çalışıyor mu?")
        return pd.DataFrame()

def api_veri_ekle(veri_listesi):
    try:
        response = requests.post(f"{API_URL}/ekle", json=veri_listesi)
        return response.status_code == 200
    except: return False

def api_veri_sil(index_listesi):
    try:
        response = requests.post(f"{API_URL}/sil", json=index_listesi)
        return response.status_code == 200
    except: return False

def api_ayarlari_getir():
    try:
        res = requests.get(f"{API_URL}/ayarlar")
        if res.status_code == 200:
            return res.json()["altin"], res.json()["gumus"]
    except: pass
    return 6400.00, 80.00

def api_ayarlari_guncelle(altin, gumus):
    try:
        requests.post(f"{API_URL}/ayarlar/guncelle", json={"altin": altin, "gumus": gumus})
    except: pass

# --- ANA PROGRAM ---
df = api_veri_cek()

# --- SOL MENÜ ---
with st.sidebar:
    st.header("💰 Piyasa Fiyatları")
    st.info("Güncel piyasa fiyatlarını giriniz.")
    
    kayitli_altin, kayitli_gumus = api_ayarlari_getir()
    
    gold_val = st.number_input("Gr Altın (₺)", value=kayitli_altin, step=10.0, format="%.2f")
    silver_val = st.number_input("Gr Gümüş (₺)", value=kayitli_gumus, step=1.0, format="%.2f")
    
    if st.button("Fiyatları Sabitle 💾"):
        with st.spinner("Ayarlar güncelleniyor..."):
            api_ayarlari_guncelle(gold_val, silver_val)
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
    
    tutar_text = st.text_input("Toplam Tutar (₺)", placeholder="Örn: 5890,00")
    
    def parse_tutar_manual(x):
        try:
            x = x.replace("₺", "").replace("TL", "").strip()
            x = x.replace(".", "").replace(",", ".")
            return float(x)
        except:
            return 0.0

    tutar_float = parse_tutar_manual(tutar_text) if tutar_text else 0.0
    
    payload_list = [] 
    
    if tutar_float > 0:
        ay_map = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                  7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}
        
        if taksit_sayisi > 1:
            raw_aylik = tutar_float / taksit_sayisi
            for i in range(taksit_sayisi):
                gelecek_tarih = tarih_giris + relativedelta(months=i)
                yeni_aciklama = f"{aciklama_giris} ({i+1}/{taksit_sayisi}. Taksit)"
                
                payload_list.append({
                    "tarih": str(gelecek_tarih.strftime("%Y-%m-%d")),
                    "ay": ay_map[gelecek_tarih.month],
                    "yil": gelecek_tarih.year,
                    "kategori": kategori_giris,
                    "aciklama": yeni_aciklama,
                    "tutar_raw": raw_aylik,
                    "tur": tur_giris
                })
        else:
            final_aciklama = miktar_bilgisi + aciklama_giris if aciklama_giris else miktar_bilgisi + tur_giris
            payload_list.append({
                "tarih": str(tarih_giris.strftime("%Y-%m-%d")),
                "ay": ay_map[tarih_giris.month],
                "yil": tarih_giris.year,
                "kategori": kategori_giris,
                "aciklama": final_aciklama,
                "tutar_raw": float(tutar_float),
                "tur": tur_giris
            })

        st.caption("📝 **Kayıt Önizlemesi**")
        st.info(f"Girilen: {tutar_float:,.2f} ₺")
        
    if st.button("Kaydet 💾", type="primary"):
        if tutar_float > 0 and payload_list:
            with st.spinner('API üzerinden kaydediliyor...'):
                basarili = api_veri_ekle(payload_list)
            if basarili:
                st.success("Kayıt Başarılı!")
                st.rerun()
            else:
                st.error("API Hatası! (Mutfak kapalı olabilir)")
        elif tutar_float == 0:
            st.error("Lütfen geçerli bir tutar girin.")

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
                    tutar = row_data["Tutar"]
                    
                    match = re.search(r"(.*?) \((\d+)/(\d+)\. Taksit\)", str(row_data["Aciklama"]))
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

                    if api_veri_sil(silinecekler):
                        st.success("Silindi!")
                        st.rerun()
                    else:
                        st.error("Silme başarısız!")

# --- DASHBOARD ---
st.title("📊 Akıllı Bütçe (API Modu)")

if not df.empty:
    col_f1, col_f2 = st.columns(2)
    yillar = sorted(df["Yıl"].unique().tolist(), reverse=True)
    aylar = ["Tümü"] + list(df["Ay"].unique())
    sec_yil = col_f1.selectbox("Yıl", yillar)
    sec_ay = col_f2.selectbox("Ay", aylar)
    
    df_f = df[df["Yıl"] == str(sec_yil)]
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
            
            st.dataframe(
                df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Guncel", "Fark"]].style.format({
                    "Tutar": "{:,.2f} ₺",
                    "Guncel": "{:,.2f} ₺",
                    "Fark": "{:,.2f} ₺"
                }), 
                use_container_width=True
            )
        else:
            st.info("Yatırım kaydı yok.")

    st.divider()
    st.subheader("📋 Tüm İşlemler")
    st.dataframe(df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}), use_container_width=True)
else:
    st.info("Veri yok veya API (Mutfak) çalışmıyor.")
