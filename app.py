import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import io

# --- הגדרות עמוד ---
st.set_page_config(page_title="דשבורד ועד בית", layout="wide")
st.title("🏠 דשבורד ניהול כספי - ועד בית")

# --- אתחול Session State ---
if 'merge_map' not in st.session_state:
    st.session_state['merge_map'] = {}
if 'manual_tags' not in st.session_state:
    st.session_state['manual_tags'] = {} 

# --- פונקציית טעינת נתונים ---
def load_data(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, skiprows=4)
        cols = df.columns.tolist()
        
        if len(cols) < 9:
            st.error("קובץ האקסל לא תואם למבנה המצופה (חסרות עמודות).")
            return pd.DataFrame()

        mapping = {
            cols[0]: 'Date',
            cols[1]: 'Action',
            cols[2]: 'Details',
            cols[4]: 'Debit',
            cols[5]: 'Credit',
            cols[6]: 'Balance',
            cols[8]: 'Beneficiary'
        }
        df = df.rename(columns=mapping)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
        df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
        df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce').fillna(0)
        
        df['Details'] = df['Details'].fillna('').astype(str)
        df['Action'] = df['Action'].fillna('').astype(str)
        df['Beneficiary'] = df['Beneficiary'].fillna('').astype(str)
        
        df['Month'] = df['Date'].dt.strftime('%m/%Y')
        df['OriginalIndex'] = df.index 
        
        return df
    except Exception as e:
        st.error(f"שגיאה בטעינת הנתונים: {e}")
        return pd.DataFrame()

# --- פונקציית עזר לקטגוריזציה ---
def categorize_expense(row):
    text = (str(row['Action']) + " " + str(row['Details'])).lower()
    if 'ע.מפעולות-ישיר' in text or 'ע. מפעולות ישיר' in text or 'ע. מסלול בסיסי' in text or 'ע.מפעולות-פקיד' in text:
        return 'עמלות בנק'
    if 'גז ניהול מבנים' in text:
        return 'גז ניהול מבנים'
    return row['Details'] if row['Details'] else row['Action']

# --- פונקציה להצגת היסטוריית משפחה ---
def display_family_history(family_name, df_full, start_date, end_date, hide_missing_months):
    st.markdown(f"#### 🏠 {family_name}")
    
    # חיפוש תשלומים בתוך כל הדאטה
    ap = df_full[(df_full['Beneficiary'] == family_name) & (df_full['Credit'] > 0)].sort_values('Date')
    gdata = []
    
    if not hide_missing_months:
        # ברירת המחדל: הצגת כל החודשים בטווח
        norm_st = start_date.replace(day=1)
        dr = pd.date_range(start=norm_st, end=end_date, freq='MS')
        for dp in dr:
            mstr = dp.strftime('%m/%Y')
            pim = ap[ap['Month'] == mstr]
            if not pim.empty:
                for _, r in pim.iterrows():
                    gdata.append({'Date': r['Date'], 'Month': mstr, 'Credit': r['Credit'], 'Details': r['Details']})
            else:
                gdata.append({'Date': dp, 'Month': mstr, 'Credit': 0, 'Details': '❌ לא שולם'})
    else:
        # הצגת תשלומים בלבד
        for _, r in ap.iterrows():
            gdata.append({'Date': r['Date'], 'Month': r['Month'], 'Credit': r['Credit'], 'Details': r['Details']})
    
    gdf = pd.DataFrame(gdata)
    if not gdf.empty:
        gdf['RowID'] = range(len(gdf))
        mc = gdf['Credit'].max() if not gdf.empty else 100
        fig = px.bar(gdf, x='RowID', y='Credit', text='Credit', color='Month')
        fig.update_layout(xaxis=dict(tickmode='array', tickvals=gdf['RowID'], ticktext=gdf['Month']), 
                          yaxis=dict(range=[0, mc*1.2]), showlegend=False, bargap=0.3, height=350)
        fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside', cliponaxis=False)
        if not hide_missing_months:
            fig.for_each_trace(lambda t: t.update(text=[v if v>0 else "" for v in t.y]))
        
        # --- התיקון כאן: תוספת מזהה ייחודי key ---
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{family_name}")
    else:
        st.info("אין תשלומים להצגה בטווח זה.")
    
    tdf = ap[['Date', 'Credit', 'Details', 'Action']].copy()
    tdf['Date'] = tdf['Date'].dt.strftime('%d/%m/%Y')
    
    # --- התיקון כאן: תוספת מזהה ייחודי key ---
    st.dataframe(tdf, use_container_width=True, hide_index=True, key=f"table_{family_name}")
    
    st.write(f"**סה\"כ שולם ע\"י {family_name}:** {ap['Credit'].sum():,.0f} ₪")
    st.markdown("---")

# --- ממשק צד (Sidebar) ---
st.sidebar.header("העלאת נתונים")
uploaded_file = st.sidebar.file_uploader("בחר קובץ אקסל מהבנק", type=['xlsx', 'xls'])

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    if not df.empty:
        # ==========================================
        # 1. שיוך תשלומים ידני
        # ==========================================
        st.sidebar.markdown("---")
        with st.sidebar.expander("✍️ שיוך תשלומים ידני", expanded=False):
            st.caption("שיוך הפקדות ללא שם למשפחה ספציפית.")
            income_rows = df[df['Credit'] > 0].copy()
            income_rows['Label'] = income_rows.apply(
                lambda x: f"{x['Date'].strftime('%d/%m/%y')} | {x['Credit']}₪ | {x['Details']} | {x['Beneficiary']}", axis=1
            )
            selected_row_label = st.selectbox("בחר תנועה:", income_rows['Label'].tolist())
            if selected_row_label:
                selected_idx = income_rows[income_rows['Label'] == selected_row_label]['OriginalIndex'].values[0]
                current_families = sorted(df[df['Credit'] > 0]['Beneficiary'].unique())
                target_family = st.selectbox("שייך למשפחה:", ["- בחר -"] + current_families + ["משפחה חדשה..."])
                if target_family == "משפחה חדשה...":
                    target_family = st.text_input("הזן שם משפחה:")
                if st.button("בצע שיוך"):
                    if target_family and target_family != "- בחר -":
                        st.session_state['manual_tags'][selected_idx] = target_family
                        st.rerun()

        for idx, new_name in st.session_state['manual_tags'].items():
            df.loc[df['OriginalIndex'] == idx, 'Beneficiary'] = new_name

        # ==========================================
        # 2. איחוד משפחות
        # ==========================================
        st.sidebar.markdown("---")
        with st.sidebar.expander("🔗 איחוד שמות ומשפחות", expanded=False):
            all_beneficiaries = sorted(df[df['Credit'] > 0]['Beneficiary'].unique())
            available_beneficiaries = [name for name in all_beneficiaries if name not in st.session_state['merge_map']]
            with st.form("merge_form", clear_on_submit=True):
                new_group_name = st.text_input("שם מאוחד")
                selected_names = st.multiselect("בחר שמות:", available_beneficiaries)
                if st.form_submit_button("שמור"):
                    if new_group_name and selected_names:
                        for name in selected_names: st.session_state['merge_map'][name] = new_group_name
                        st.rerun()
            if st.session_state['merge_map']:
                if st.button("אפס איחודים"): st.session_state['merge_map'] = {}; st.rerun()

        if st.session_state['merge_map']:
            df['Beneficiary'] = df['Beneficiary'].replace(st.session_state['merge_map'])

        # ==========================================
        # 3. סינון תאריכים
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("סינון תאריכים לגרפים")
        min_date = df['Date'].min().date()
        max_date = df['Date'].max().date()
        start_date = st.sidebar.date_input("תאריך התחלה", min_date)
        end_date = st.sidebar.date_input("תאריך סיום", max_date)
        df_filtered = df.loc[(df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)]

        # ==========================================
        # 4. ייצוא לאקסל
        # ==========================================
        st.sidebar.markdown("---")
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df_filtered.to_excel(writer, index=False)
            st.sidebar.download_button("📥 הורד אקסל מעובד", buffer, "vaad_data.xlsx")
        except: pass

        st.success(f"מציג נתונים בגרפים בין {start_date} ל-{end_date}")

        # ========================================================
        #  חלק א': מבט על - הוצאות והכנסות
        # ========================================================
        st.subheader("📊 מבט על: הוצאות והכנסות")
        c_r1_1, c_r1_2 = st.columns(2)
        with c_r1_1:
            st.subheader("הכנסות מול הוצאות")
            if not df_filtered.empty:
                ms = df_filtered.copy(); ms['MonthDate'] = ms['Date'].dt.to_period('M')
                gr = ms.groupby('MonthDate')[['Credit', 'Debit']].sum().reset_index()
                gr['MonthStr'] = gr['MonthDate'].dt.strftime('%m/%Y')
                mlt = gr.melt(id_vars='MonthStr', value_vars=['Credit', 'Debit'], var_name='Type', value_name='Amount')
                mlt['Type'] = mlt['Type'].replace({'Credit': 'הכנסות', 'Debit': 'הוצאות'})
                fig = px.bar(mlt, x='MonthStr', y='Amount', color='Type', barmode='group', text='Amount', color_discrete_map={'הכנסות': '#2ecc71', 'הוצאות': '#e74c3c'})
                fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside'); st.plotly_chart(fig, use_container_width=True)
        with c_r1_2:
            st.subheader("מגמת יתרה מצטברת")
            fig = px.line(df_filtered.sort_values('Date'), x='Date', y='Balance', color_discrete_sequence=['purple'])
            fig.update_layout(yaxis=dict(tickformat=",.0f")); st.plotly_chart(fig, use_container_width=True)

        # ========================================================
        #  חלק ב': ניתוח חודשי וחשמל
        # ========================================================
        c_r2_1, c_r2_2 = st.columns(2)
        with c_r2_1:
            st.subheader("פירוט חודשי ממוקד (הוצאות)")
            avail_months = [p.strftime('%m/%Y') for p in sorted(df_filtered['Date'].dt.to_period('M').unique(), reverse=True)]
            if avail_months:
                sel_m = st.selectbox("בחר חודש:", avail_months, label_visibility="collapsed")
                m_data = df_filtered[df_filtered['Month'] == sel_m]
                me = m_data[m_data['Debit'] > 0].copy()
                if not me.empty:
                    me['Category'] = me.apply(categorize_expense, axis=1)
                    ep = me.groupby('Category')['Debit'].sum().reset_index()
                    fig = px.pie(ep, values='Debit', names='Category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig.update_layout(showlegend=True, legend=dict(orientation="h"), height=300); st.plotly_chart(fig, use_container_width=True)
                    st.metric("סה\"כ הוצאות לחודש זה:", f"{ep['Debit'].sum():,.0f} ₪")
                else: st.info("אין הוצאות בחודש זה.")
        with c_r2_2:
            st.subheader("הוצאות חשמל")
            is_elec = df_filtered['Action'].str.contains('חשמל', na=False) | df_filtered['Details'].str.contains('חשמל', na=False)
            el_df = df_filtered[is_elec & (df_filtered['Debit'] > 0)]
            if not el_df.empty:
                mel = el_df.groupby('Month')['Debit'].sum().reset_index()
                mel['SortDate'] = pd.to_datetime(mel['Month'], format='%m/%Y')
                mel = mel.sort_values('SortDate')
                fig = px.bar(mel, x='Month', y='Debit', text='Debit', color_discrete_sequence=['orange'])
                fig.update_traces(texttemplate='%{text:.0f}', textposition='outside'); st.plotly_chart(fig, use_container_width=True)
            else: st.info("אין הוצאות חשמל בתקופה זו.")

        # ========================================================
        #  חלק ג': פילוח קטגוריות
        # ========================================================
        st.markdown("---")
        st.subheader("🍰 פילוח הוצאות לפי קטגוריות")
        c_p1, c_p2 = st.columns(2)
        exp_df = df_filtered[df_filtered['Debit'] > 0].copy()
        if not exp_df.empty:
            exp_df['Category'] = exp_df.apply(categorize_expense, axis=1)
            cat_sum = exp_df.groupby('Category')['Debit'].sum().reset_index()
            with c_p1:
                st.subheader("כלל ההוצאות")
                fig = px.pie(cat_sum, values='Debit', names='Category', hole=0.3)
                fig.update_layout(showlegend=True, legend=dict(orientation="h")); st.plotly_chart(fig, use_container_width=True)
                st.metric("סה\"כ הוצאות:", f"{cat_sum['Debit'].sum():,.0f} ₪")
            with c_p2:
                st.subheader("הוצאות ללא גז")
                no_g = cat_sum[cat_sum['Category'] != 'גז ניהול מבנים']
                if not no_g.empty:
                    fig = px.pie(no_g, values='Debit', names='Category', hole=0.3, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig.update_layout(showlegend=True, legend=dict(orientation="h")); st.plotly_chart(fig, use_container_width=True)
                    st.metric("סה\"כ (ללא גז):", f"{no_g['Debit'].sum():,.0f} ₪")
                else: st.info("אין הוצאות נוספות מלבד גז.")

        # ========================================================
        #  חלק ד': דוחות מפורטים וחריגים
        # ========================================================
        st.markdown("---")
        st.header("📋 דוחות מפורטים וחריגים")

        flagged_family_names = []
        with st.expander("⚠️ דוח חריגים שנתי (בדיקת תשלום חכם)", expanded=True):
            last_date_val = df['Date'].max(); last_year_val = last_date_val.year
            avail_years = sorted(df['Date'].dt.year.dropna().unique().astype(int), reverse=True)
            c1, c2, c3 = st.columns(3)
            with c1: sel_y = st.selectbox("שנה לבדיקה:", avail_years)
            with c2: m_fee = st.number_input("ועד חודשי:", value=250)
            with c3: tol = st.number_input("סובלנות חוב:", value=50)
            
            st.markdown("---")
            st.write("🛠️ **הרחבת טווח חיפוש תשלומים:**")
            d1, d2 = st.columns(2)
            with d1: d_bef = st.number_input("ימים לפני:", value=0)
            with d2: d_aft = st.number_input("ימים אחרי:", value=0)
            
            y_st = datetime(sel_y, 1, 1); y_en = last_date_val if sel_y == last_year_val else datetime(sel_y, 12, 31)
            s_st = y_st - timedelta(days=d_bef); s_en = y_en + timedelta(days=d_aft)
            m_count = (y_en.year - y_st.year) * 12 + (y_en.month - y_st.month) + 1
            exp_total = m_count * m_fee
            
            st.info(f"🔎 בדיקה לשנת **{sel_y}** | צפי לחיוב: **{m_count}** חודשים | סכום יעד: **{exp_total:,.0f} ₪**\n🛡️ מחפש בפועל תשלומים שבוצעו בין **{s_st.strftime('%d/%m/%y')}** ל-**{s_en.strftime('%d/%m/%y')}**.")

            audit_mask = (df['Date'] >= s_st) & (df['Date'] <= s_en)
            audit_df = df.loc[audit_mask]
            all_p = pd.DataFrame({'Beneficiary': df[df['Credit'] > 0]['Beneficiary'].unique()})
            y_p = audit_df[audit_df['Credit'] > 0].groupby('Beneficiary')['Credit'].sum().reset_index()
            m_audit = pd.merge(all_p, y_p, on='Beneficiary', how='left').fillna(0)
            m_audit['Gap'] = exp_total - m_audit['Credit']
            flagged = m_audit[m_audit['Gap'] > tol].sort_values('Gap', ascending=False)
            
            if not flagged.empty: 
                st.error(f"נמצאו {len(flagged)} משפחות עם חוסר בתשלום!")
                st.dataframe(flagged.rename(columns={'Beneficiary': 'משפחה', 'Credit': 'שולם בפועל', 'Expected': 'צפי', 'Gap': 'חוב'}), use_container_width=True)
                flagged_family_names = flagged['Beneficiary'].tolist()
            else: 
                st.success("הכל תקין!")

        # --- חלק ה': פירוט תשלומים למשפחה ---
        st.subheader("🔎 פירוט תשלומים למשפחה")
        
        all_paying_families = sorted(df[df['Credit'] > 0]['Beneficiary'].unique())
        
        if all_paying_families:
            col_ui1, col_ui2 = st.columns([1, 1])
            with col_ui1:
                bulk_view_flagged = st.checkbox("⚠️ תצוגה מורחבת של החריגים בלבד", value=False)
            with col_ui2:
                hide_miss = st.checkbox("הצג חודשים עם תשלום בלבד", value=False)

            if bulk_view_flagged:
                if flagged_family_names:
                    st.warning(f"מציג היסטוריה עבור {len(flagged_family_names)} משפחות חריגות:")
                    for family in flagged_family_names:
                        display_family_history(family, df, start_date, end_date, hide_miss)
                else:
                    st.info("לא נמצאו חריגים להצגה.")
            else:
                selected_family = st.selectbox("בחר משפחה לצפייה:", all_paying_families)
                display_family_history(selected_family, df, start_date, end_date, hide_miss)

else:
    st.info("אנא העלה קובץ אקסל.")
            
