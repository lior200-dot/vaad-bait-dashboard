import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- הגדרות עמוד ---
st.set_page_config(page_title="דשבורד ועד בית", layout="wide")
st.title("🏠 דשבורד ניהול כספי - ועד בית")

# --- פונקציית טעינת נתונים ---
def load_data(uploaded_file):
    # מדלגים על 4 שורות ראשונות כמו במטלאב
    df = pd.read_excel(uploaded_file, skiprows=4)
    
    # שינוי שמות עמודות (לפי המיקום)
    cols = df.columns.tolist()
    if len(cols) >= 9:
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
    
    # ניקוי נתונים
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
    df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
    df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce').fillna(0)
    
    # המרת שדות טקסט למחרוזות
    df['Details'] = df['Details'].fillna('').astype(str)
    df['Action'] = df['Action'].fillna('').astype(str)
    df['Beneficiary'] = df['Beneficiary'].fillna('').astype(str)
    
    df['Month'] = df['Date'].dt.to_period('M').astype(str)
    
    return df

# --- ממשק צד (Sidebar) ---
st.sidebar.header("העלאת נתונים")
uploaded_file = st.sidebar.file_uploader("בחר קובץ אקסל מהבנק", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        df = load_data(uploaded_file)
        
        # --- בחירת טווח תאריכים ---
        st.sidebar.header("סינון תאריכים")
        min_date = df['Date'].min().date()
        max_date = df['Date'].max().date()
        
        start_date = st.sidebar.date_input("תאריך התחלה", min_date)
        end_date = st.sidebar.date_input("תאריך סיום", max_date)
        
        # סינון הדאטה
        mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
        df_filtered = df.loc[mask]
        
        st.success(f"מציג נתונים בין {start_date} ל-{end_date}")
        
        # ========================================================
        # שורה 1: גרפים כלליים (Figure 3 + Balance)
        # ========================================================
        col_top1, col_top2 = st.columns(2)
        
        # --- Figure 3: הכנסות מול הוצאות (חדש!) ---
        with col_top1:
            st.subheader("⚖️ הכנסות מול הוצאות (חודשי)")
            if not df_filtered.empty:
                # סיכום לפי חודש
                monthly_summary = df_filtered.groupby('Month')[['Credit', 'Debit']].sum().reset_index()
                
                # המרה למבנה שנוח לגרף (Melting)
                monthly_melt = monthly_summary.melt(id_vars='Month', value_vars=['Credit', 'Debit'], 
                                                    var_name='Type', value_name='Amount')
                
                # שינוי שמות לעברית
                monthly_melt['Type'] = monthly_melt['Type'].replace({'Credit': 'הכנסות', 'Debit': 'הוצאות'})
                
                fig_inc_exp = px.bar(monthly_melt, x='Month', y='Amount', color='Type', barmode='group',
                                     text='Amount',
                                     color_discrete_map={'הכנסות': '#2ecc71', 'הוצאות': '#e74c3c'},
                                     labels={'Amount': 'סכום (ש"ח)', 'Month': 'חודש', 'Type': 'סוג'})
                
                fig_inc_exp.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
                st.plotly_chart(fig_inc_exp, use_container_width=True)
            else:
                st.info("אין נתונים להצגה.")

        # --- Figure 6: מגמת יתרה ---
        with col_top2:
            st.subheader("💰 מגמת יתרה בחשבון")
            df_sorted = df_filtered.sort_values('Date')
            fig_bal = px.line(df_sorted, x='Date', y='Balance',
                              labels={'Balance': 'יתרה', 'Date': 'תאריך'},
                              color_discrete_sequence=['purple'])
            # פירמוט ציר Y עם פסיקים
            fig_bal.update_layout(yaxis=dict(tickformat=",.0f"))
            st.plotly_chart(fig_bal, use_container_width=True)

        # ========================================================
        # שורה 2: חשמל ותשלומים
        # ========================================================
        col_mid1, col_mid2 = st.columns(2)

        # --- Figure 1: חשמל ---
        with col_mid1:
            st.subheader("⚡ הוצאות חשמל")
            is_electric = df_filtered['Action'].str.contains('חשמל', na=False) | \
                          df_filtered['Details'].str.contains('חשמל', na=False) | \
                          df_filtered['Beneficiary'].str.contains('חשמל', na=False)
            
            electric_df = df_filtered[is_electric & (df_filtered['Debit'] > 0)]
            if not electric_df.empty:
                monthly_electric = electric_df.groupby('Month')['Debit'].sum().reset_index()
                fig_elec = px.bar(monthly_electric, x='Month', y='Debit', text='Debit',
                                  labels={'Debit': 'סכום (ש"ח)', 'Month': 'חודש'},
                                  color_discrete_sequence=['orange'])
                fig_elec.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                st.plotly_chart(fig_elec, use_container_width=True)
            else:
                st.info("לא נמצאו הוצאות חשמל בטווח זה.")

        # --- Figure 5: סיכום תשלומים ---
        with col_mid2:
            st.subheader("🏆 סיכום תשלומים לפי משפחה")
            income_df = df_filtered[df_filtered['Credit'] > 0]
            if not income_df.empty:
                total_per_family = income_df.groupby('Beneficiary')['Credit'].sum().reset_index().sort_values('Credit', ascending=False)
                fig_pay = px.bar(total_per_family, x='Beneficiary', y='Credit', text='Credit',
                                 labels={'Credit': 'סה"כ שולם', 'Beneficiary': 'משפחה'},
                                 color_discrete_sequence=['teal'])
                fig_pay.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                st.plotly_chart(fig_pay, use_container_width=True)
            else:
                st.info("אין הכנסות בטווח שנבחר.")

        # ========================================================
        # שורה 3: פילוח הוצאות (Pie Charts)
        # ========================================================
        st.subheader("🍰 פילוח הוצאות")
        expense_df = df_filtered[df_filtered['Debit'] > 0].copy()
        
        if not expense_df.empty:
            # קטגוריזציה
            def categorize(row):
                text = (str(row['Action']) + " " + str(row['Details'])).lower()
                if 'ע.מפעולות-ישיר' in text or 'ע. מפעולות ישיר' in text or 'ע. מסלול בסיסי' in text or 'ע.מפעולות-פקיד' in text:
                    return 'עמלות בנק'
                if 'גז ניהול מבנים' in text:
                    return 'גז ניהול מבנים'
                # ברירת מחדל: פרטים, ואם אין אז פעולה
                return row['Details'] if row['Details'] else row['Action']

            expense_df['Category'] = expense_df.apply(categorize, axis=1)
            
            # קיבוץ
            cat_summary = expense_df.groupby('Category')['Debit'].sum().reset_index()
            
            p_col1, p_col2 = st.columns(2)
            
            with p_col1:
                st.caption("כלל ההוצאות")
                fig_p1 = px.pie(cat_summary, values='Debit', names='Category', hole=0.3)
                # הסתרת אחוזים קטנים (פחות מ-2%)
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

    except Exception as e:
        st.error(f"שגיאה בעיבוד הקובץ: {e}")
        st.write("נא לוודא שקובץ האקסל הוא בפורמט התקין מהבנק.")

else:
    st.info("אנא העלה קובץ אקסל כדי להתחיל.")
