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
                        st.success("השיוך בוצע!")
                        st.rerun()

            if st.session_state['manual_tags']:
                st.write(f"**שוייכו {len(st.session_state['manual_tags'])} תשלומים.**")
                if st.button("בטל שיוכים ידניים"):
                    st.session_state['manual_tags'] = {}
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
                new_group_name = st.text_input("שם מאוחד (למשל: משפחת פולק)")
                selected_names = st.multiselect("בחר שמות לאיחוד:", available_beneficiaries)
                if st.form_submit_button("שמור והוסף"):
                    if new_group_name and selected_names:
                        for name in selected_names:
                            st.session_state['merge_map'][name] = new_group_name
                        st.rerun()

            if st.session_state['merge_map']:
                st.write("📋 **קבוצות פעילות:**")
                grouped_view = {}
                for original_name, new_name in st.session_state['merge_map'].items():
                    grouped_view.setdefault(new_name, []).append(original_name)
                
                group_to_delete = st.selectbox("מחק קבוצה", ["- בחר -"] + list(grouped_view.keys()))
                if group_to_delete != "- בחר -" and st.button("מחק"):
                     keys_to_remove = [k for k, v in st.session_state['merge_map'].items() if v == group_to_delete]
                     for k in keys_to_remove: del st.session_state['merge_map'][k]
                     st.rerun()
                
                if st.button("אפס איחודים"):
                    st.session_state['merge_map'] = {}
                    st.rerun()

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
        
        mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
        df_filtered = df.loc[mask]
        
        # ==========================================
        # 4. ייצוא לאקסל
        # ==========================================
        st.sidebar.markdown("---")
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_filtered.to_excel(writer, index=False, sheet_name='Data')
            st.sidebar.download_button("📥 הורד נתונים מעובדים", buffer, "processed_data.xlsx")
        except Exception:
            pass

        st.success(f"מציג נתונים בגרפים בין {start_date} ל-{end_date}")

        # ========================================================
        #  ⚠️ דוח משפחות טעונות בדיקה (כולל אפס תשלומים)
        # ========================================================
        with st.expander("⚠️ דוח חריגים שנתי (בדיקת תשלום חכם)", expanded=True):
            st.caption("בדיקת חובות לשנה נבחרת. כולל משפחות שלא שילמו כלל בתקופה זו.")
            
            last_data_date = df['Date'].max()
            last_data_year = last_data_date.year
            years = df['Date'].dt.year.dropna().unique()
            available_years = sorted(years.astype(int), reverse=True)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                selected_year = st.selectbox("בחר שנה לבדיקה:", available_years)
            with c2:
                monthly_fee = st.number_input("סכום ועד חודשי (₪):", value=250, step=10)
            with c3:
                tolerance = st.number_input("להתעלם מחוב קטן מ- (₪):", value=50)

            if selected_year:
                year_start = datetime(selected_year, 1, 1)
                
                if selected_year == last_data_year:
                    year_end = last_data_date
                    limit_msg = f"עד התאריך האחרון ({year_end.strftime('%d/%m/%Y')})"
                else:
                    year_end = datetime(selected_year, 12, 31)
                    limit_msg = "שנה מלאה"

                search_start = year_start - timedelta(days=10)
                search_end = year_end + timedelta(days=10)
                
                months_count = (year_end.year - year_start.year) * 12 + (year_end.month - year_start.month) + 1
                expected_total = months_count * monthly_fee
                
                st.info(f"🔎 בדיקה לשנת **{selected_year}** ({limit_msg}). יעד: **{expected_total:,.0f} ₪**")

                # 1. יצירת רשימת כל המשפחות הפעילות (ששילמו אי פעם)
                # זה מבטיח שגם מי שלא שילם השנה יופיע ברשימה
                all_ever_payers = df[df['Credit'] > 0]['Beneficiary'].unique()
                all_families_df = pd.DataFrame({'Beneficiary': all_ever_payers})

                # 2. סיכום תשלומים לשנה הנבחרת
                audit_mask = (df['Date'] >= search_start) & (df['Date'] <= search_end)
                audit_df = df.loc[audit_mask]
                
                # קיבוץ לפי משפחה רק עבור השנה הזו
                yearly_payments = audit_df[audit_df['Credit'] > 0].groupby('Beneficiary')['Credit'].sum().reset_index()
                
                # 3. מיזוג (Left Join) - כך שכל המשפחות יופיעו, גם אם לא שילמו השנה
                merged_audit = pd.merge(all_families_df, yearly_payments, on='Beneficiary', how='left')
                
                # מילוי אפסים למי שלא שילם כלום השנה
                merged_audit['Credit'] = merged_audit['Credit'].fillna(0)
                
                # חישוב הפער
                merged_audit['Expected'] = expected_total
                merged_audit['Gap'] = merged_audit['Expected'] - merged_audit['Credit']
                
                # סינון חריגים
                flagged = merged_audit[merged_audit['Gap'] > tolerance].sort_values('Gap', ascending=False)
                
                if not flagged.empty:
                    st.error(f"נמצאו {len(flagged)} משפחות עם חוסר בתשלום!")
                    flagged = flagged.rename(columns={'Beneficiary': 'משפחה', 'Credit': 'שולם בפועל', 'Expected': 'צפי', 'Gap': 'חוב'})
                    st.dataframe(flagged[['משפחה', 'שולם בפועל', 'צפי', 'חוב']], use_container_width=True)
                else:
                    st.success(f"✅ כל המשפחות עמדו ביעד לשנת {selected_year}.")

        # ========================================================
        #  הגרפים הראשיים
        # ========================================================
        col_top1, col_top2 = st.columns(2)
        with col_top1:
            st.subheader("⚖️ הכנסות מול הוצאות")
            if not df_filtered.empty:
                ms = df_filtered.copy()
                ms['MonthDate'] = ms['Date'].dt.to_period('M')
                gr = ms.groupby('MonthDate')[['Credit', 'Debit']].sum().reset_index()
                gr['MonthStr'] = gr['MonthDate'].dt.strftime('%m/%Y')
                mlt = gr.melt(id_vars='MonthStr', value_vars=['Credit', 'Debit'], var_name='Type', value_name='Amount')
                mlt['Type'] = mlt['Type'].replace({'Credit': 'הכנסות', 'Debit': 'הוצאות'})
                fig = px.bar(mlt, x='MonthStr', y='Amount', color='Type', barmode='group', text='Amount', 
                             color_discrete_map={'הכנסות': '#2ecc71', 'הוצאות': '#e74c3c'})
                fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)

        with col_top2:
            st.subheader("💰 מגמת יתרה")
            df_srt = df_filtered.sort_values('Date')
            fig = px.line(df_srt, x='Date', y='Balance', color_discrete_sequence=['purple'])
            fig.update_layout(yaxis=dict(tickformat=",.0f"))
            st.plotly_chart(fig, use_container_width=True)

        col_mid1, col_mid2 = st.columns(2)
        with col_mid1:
            st.subheader("⚡ הוצאות חשמל")
            is_elec = df_filtered['Action'].str.contains('חשמל', na=False) | df_filtered['Details'].str.contains('חשמל', na=False) | df_filtered['Beneficiary'].str.contains('חשמל', na=False)
            el_df = df_filtered[is_elec & (df_filtered['Debit'] > 0)]
            if not el_df.empty:
                mel = el_df.groupby('Month')['Debit'].sum().reset_index()
                mel['SortDate'] = pd.to_datetime(mel['Month'], format='%m/%Y')
                mel = mel.sort_values('SortDate')
                fig = px.bar(mel, x='Month', y='Debit', text='Debit', color_discrete_sequence=['orange'])
                fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("אין הוצאות חשמל.")

        with col_mid2:
            st.subheader("🏆 סיכום תשלומים")
            inc_df = df_filtered[df_filtered['Credit'] > 0]
            if not inc_df.empty:
                tpf = inc_df.groupby('Beneficiary')['Credit'].sum().reset_index().sort_values('Beneficiary')
                fig = px.bar(tpf, x='Beneficiary', y='Credit', text='Credit', color_discrete_sequence=['teal'])
                fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("אין הכנסות.")

        # ========================================================
        #  פילוח הוצאות
        # ========================================================
        st.markdown("---")
        st.subheader("🍰 פילוח הוצאות (כללי)")
        expense_df = df_filtered[df_filtered['Debit'] > 0].copy()
        
        if not expense_df.empty:
            expense_df['Category'] = expense_df.apply(categorize_expense, axis=1)
            cat_summary = expense_df.groupby('Category')['Debit'].sum().reset_index()
            
            p_col1, p_col2 = st.columns(2)
            
            with p_col1:
                st.caption("כלל ההוצאות")
                fig_p1 = px.pie(cat_summary, values='Debit', names='Category', hole=0.3)
                fig_p1.update_traces(textposition='inside', textinfo='percent+label')
                fig_p1.update_layout(showlegend=True, legend=dict(orientation="h"))
                st.plotly_chart(fig_p1, use_container_width=True)
            
            with p_col2:
                st.caption("הוצאות ללא גז")
                no_gas_df = cat_summary[cat_summary['Category'] != 'גז ניהול מבנים']
                if not no_gas_df.empty:
                    fig_p2 = px.pie(no_gas_df, values='Debit', names='Category', hole=0.3,
                                    color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_p2.update_traces(textposition='inside', textinfo='percent+label')
                    fig_p2.update_layout(showlegend=True, legend=dict(orientation="h"))
                    st.plotly_chart(fig_p2, use_container_width=True)
                else:
                    st.info("אין הוצאות נוספות מלבד גז.")

        # ========================================================
        #  פירוט חודשי
        # ========================================================
        st.markdown("---")
        st.subheader("📅 פירוט חודשי ממוקד")
        
        unique_periods = df_filtered['Date'].dt.to_period('M').unique()
        sorted_periods = sorted(unique_periods, reverse=True)
        available_months = [p.strftime('%m/%Y') for p in sorted_periods]
        
        if len(available_months) > 0:
            selected_month = st.selectbox("בחר חודש לצפייה בפירוט:", available_months)
            month_data = df_filtered[df_filtered['Month'] == selected_month]
            
            m_col1, m_col2 = st.columns(2)
            
            with m_col1:
                st.caption(f"הכנסות - {selected_month}")
                month_income = month_data[month_data['Credit'] > 0]
                if not month_income.empty:
                    income_pie = month_income.groupby('Beneficiary')['Credit'].sum().reset_index()
                    fig_m_inc = px.pie(income_pie, values='Credit', names='Beneficiary', hole=0.3,
                                       color_discrete_sequence=px.colors.qualitative.Set3)
                    fig_m_inc.update_traces(textposition='inside', textinfo='percent+label')
                    fig_m_inc.update_layout(showlegend=False)
                    st.plotly_chart(fig_m_inc, use_container_width=True)
                    st.write(f"סה\"כ הכנסות: {month_income['Credit'].sum():,.0f} ש\"ח")
                else:
                    st.info("אין הכנסות בחודש זה.")
            
            with m_col2:
                st.caption(f"הוצאות - {selected_month}")
                month_expense = month_data[month_data['Debit'] > 0].copy()
                if not month_expense.empty:
                    month_expense['Category'] = month_expense.apply(categorize_expense, axis=1)
                    expense_pie = month_expense.groupby('Category')['Debit'].sum().reset_index()
                    fig_m_exp = px.pie(expense_pie, values='Debit', names='Category', hole=0.3,
                                       color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_m_exp.update_traces(textposition='inside', textinfo='percent+label')
                    fig_m_exp.update_layout(showlegend=True, legend=dict(orientation="h"))
                    st.plotly_chart(fig_m_exp, use_container_width=True)
                    st.write(f"סה\"כ הוצאות: {month_expense['Debit'].sum():,.0f} ש\"ח")
                else:
                    st.info("אין הוצאות בחודש זה.")

        # ========================================================
        #  פירוט למשפחה
        # ========================================================
        st.markdown("---")
        st.subheader("🔎 פירוט תשלומים למשפחה")
        pf = sorted(df_filtered[df_filtered['Credit'] > 0]['Beneficiary'].unique())
        if pf:
            c1, c2 = st.columns([3, 1])
            with c1: sel_fam = st.selectbox("בחר משפחה:", pf)
            with c2: show_miss = st.checkbox("הצג חודשים ללא תשלום בגרף", value=False)
            
            ap = df_filtered[(df_filtered['Beneficiary'] == sel_fam) & (df_filtered['Credit'] > 0)].sort_values('Date')
            gdata = []
            
            if show_miss:
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
                for _, r in ap.iterrows():
                    gdata.append({'Date': r['Date'], 'Month': r['Month'], 'Credit': r['Credit'], 'Details': r['Details']})
            
            gdf = pd.DataFrame(gdata)
            if not gdf.empty:
                gdf['RowID'] = range(len(gdf))
                mc = gdf['Credit'].max() if not gdf.empty else 100
                fig = px.bar(gdf, x='RowID', y='Credit', text='Credit', color='Month', title=f'היסטוריה - {sel_fam}')
                fig.update_layout(xaxis=dict(tickmode='array', tickvals=gdf['RowID'], ticktext=gdf['Month']), yaxis=dict(range=[0, mc*1.2]), showlegend=False, bargap=0.3)
                fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside', cliponaxis=False)
                if show_miss: fig.for_each_trace(lambda t: t.update(text=[v if v>0 else "" for v in t.y]))
                st.plotly_chart(fig, use_container_width=True)
            
            tdf = ap[['Date', 'Credit', 'Details', 'Action']].copy()
            tdf['Date'] = tdf['Date'].dt.strftime('%d/%m/%Y')
            st.dataframe(tdf, use_container_width=True, hide_index=True)
            st.write(f"**סה\"כ שולם:** {ap['Credit'].sum():,.0f} ₪")

else:
    st.info("אנא העלה קובץ אקסל.")
