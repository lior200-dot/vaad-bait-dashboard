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
        df['OriginalIndex'] = df.index # מזהה ייחודי לשיוך ידני
        
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
        # 1. שיוך תשלומים ידני (לפני הכל)
        # ==========================================
        st.sidebar.markdown("---")
        with st.sidebar.expander("✍️ שיוך תשלומים ידני", expanded=False):
            st.caption("שיוך הפקדות ללא שם למשפחה ספציפית.")
            income_rows = df[df['Credit'] > 0].copy()
            # יצירת תווית בחירה
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

        # החלת שיוכים ידניים על ה-DF המקורי
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

        # החלת איחוד משפחות על ה-DF המקורי
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
            # Fallback למקרה שאין ספרייה
            pass

        st.success(f"מציג נתונים בין {start_date} ל-{end_date}")

        # ========================================================
        #  דוח משפחות טעונות בדיקה (שנתי מלא + מרווח 10 ימים)
        # ========================================================
        with st.expander("⚠️ דוח חריגים שנתי (בדיקת תשלום מלא לשנה)", expanded=True):
            st.caption("כאן בודקים האם משפחה שילמה את מלוא דמי הועד לשנה קלנדרית, כולל בדיקת תשלומים שבוצעו בסמוך לתחילת/סוף השנה.")
            
            # זיהוי השנים הקיימות בדאטה לבחירה
            available_years = sorted(df['Date'].dt.year.unique(), reverse=True)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                selected_year = st.selectbox("בחר שנה לבדיקה:", available_years)
            with c2:
                monthly_fee = st.number_input("סכום ועד חודשי (₪):", value=250, step=10)
            with c3:
                tolerance = st.number_input("להתעלם מחוב קטן מ- (₪):", value=50)

            # חישוב התאריכים: 1 בינואר עד 31 בדצמבר של השנה הנבחרת
            year_start = datetime(selected_year, 1, 1)
            year_end = datetime(selected_year, 12, 31)
            
            # חישוב טווח החיפוש (שנה קלנדרית +/- 10 ימים)
            search_start = year_start - timedelta(days=10)
            search_end = year_end + timedelta(days=10)
            
            # חישוב הצפי השנתי המלא
            expected_total = 12 * monthly_fee
            
            st.info(f"🔎 בודק תשלומים עבור שנת **{selected_year}** (בין {search_start.strftime('%d/%m/%Y')} ל-{search_end.strftime('%d/%m/%Y')}).\n💰 יעד גבייה שנתי: **{expected_total:,.0f} ₪**")

            # שליפת הנתונים מה-DF המלא (לא המסונן) לפי טווח החיפוש המורחב
            audit_mask = (df['Date'] >= search_start) & (df['Date'] <= search_end)
            audit_df = df.loc[audit_mask]
            
            if not audit_df.empty:
                # סיכום הכנסות לכל משפחה בטווח הזה
                audit_income = audit_df[audit_df['Credit'] > 0].groupby('Beneficiary')['Credit'].sum().reset_index()
                
                # חישוב חוב
                audit_income['Expected'] = expected_total
                audit_income['Gap'] = audit_income['Expected'] - audit_income['Credit']
                
                # סינון: רק מי שחייב יותר מהסובלנות
                flagged = audit_income[audit_income['Gap'] > tolerance].sort_values('Gap', ascending=False)
                
                if not flagged.empty:
                    st.error(f"נמצאו {len(flagged)} משפחות שלא השלימו את התשלום השנתי המלא!")
                    
                    flagged = flagged.rename(columns={
                        'Beneficiary': 'משפחה', 
                        'Credit': 'שולם בפועל', 
                        'Expected': 'יעד שנתי', 
                        'Gap': 'חוב'
                    })
                    
                    # הצגת הטבלה ללא עיצוב מורכב למניעת שגיאות
                    st.dataframe(
                        flagged[['משפחה', 'שולם בפועל', 'יעד שנתי', 'חוב']],
                        use_container_width=True
                    )
                else:
                    st.success(f"✅ כל המשפחות שילמו את מלוא הסכום לשנת {selected_year}!")
            else:
                st.warning(f"לא נמצאו נתונים רלוונטיים לשנת {selected_year}.")

        # ========================================================
        #  הגרפים (על ה-df_filtered לפי בחירת המשתמש בסרגל)
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
