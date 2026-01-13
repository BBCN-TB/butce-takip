# ... (Önceki kodların devamı)
    
    st.divider()
    tab1, tab2 = st.tabs(["📉 Gider Analizi", "💰 Portföy & Yatırımlar"])
    
    with tab1:
        g1, g2 = st.columns(2)
        with g1:
            # Sadece Gider ve Yatırım maliyetlerini gösteren pasta grafiği
            df_pie = df_f[df_f["Tur"].isin(["Gider", "Yatırım"])]
            if not df_pie.empty:
                fig1 = px.pie(df_pie, values="Tutar", names="Kategori", hole=0.4, title="Harcama Dağılımı")
                st.plotly_chart(fig1, use_container_width=True)
        with g2:
            fig2 = px.bar(df_f.groupby("Tur")["Tutar"].sum().reset_index(), x="Tur", y="Tutar", color="Tur", title="Genel Bütçe Dengesi")
            st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        # ÖNEMLİ: Sadece 'Yatırım' türündeki verileri filtreliyoruz
        df_y = df_f[df_f["Tur"] == "Yatırım"].copy()
        
        if not df_y.empty:
            g_gold = st.session_state.get('piyasa_gold', 0)
            g_silver = st.session_state.get('piyasa_silver', 0)
            
            def calc_investment(row):
                desc, cat = str(row["Aciklama"]), str(row["Kategori"]).lower()
                # Açıklama içindeki [5] gibi miktarları ayıklar
                match = re.search(r'\[([\d\.,]+)', desc)
                if match:
                    qty = float(match.group(1).replace(",", "."))
                    if "altın" in cat: return qty * g_gold
                    if "gümüş" in cat: return qty * g_silver
                return row["Tutar"]

            df_y["Guncel Değer"] = df_y.apply(calc_investment, axis=1)
            df_y["Kâr/Zarar"] = df_y["Guncel Değer"] - df_y["Tutar"]
            
            # Portföy Özet Metrikleri
            k1, k2, k3 = st.columns(3)
            k1.metric("Yatırım Maliyeti", f"{df_y['Tutar'].sum():,.2f} ₺")
            k2.metric("Güncel Portföy", f"{df_y['Guncel Değer'].sum():,.2f} ₺")
            k3.metric("Net Kâr/Zarar", f"{df_y['Kâr/Zarar'].sum():,.2f} ₺")

            st.write("### 📋 Yatırım Detayları")
            # Sadece yatırım satırlarını gösteren tablo
            st.dataframe(
                df_y[["Tarih", "Kategori", "Aciklama", "Tutar", "Guncel Değer", "Kâr/Zarar"]].style.format("{:,.2f} ₺"), 
                use_container_width=True
            )
        else:
            st.info("Seçili dönemde herhangi bir yatırım kaydı bulunamadı.")

    # Tüm İşlemler Listesi (Tabların tamamen dışında, en altta)
    st.divider()
    with st.expander("🔍 Tüm İşlem Geçmişini Gör"):
        st.dataframe(
            df_f.sort_values("Tarih", ascending=False).style.format({"Tutar": "{:,.2f} ₺"}), 
            use_container_width=True
        )
