import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- הגדרות עמוד ---
st.set_page_config(page_title="דשבורד ועד בית", layout="wide")
st.title("🏠 דשבורד ניהול כספי - ועד בית")

# --- פונקציית טעינת נתונים ---
def load_data(uploaded_file):
    df = pd.read_excel(uploaded_file, skiprows=4)
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
    
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
    df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
    df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce').fillna(0)
    
    df['Details'] = df['Details'].fillna('').astype(str)
    df['Action'] = df['Action'].fillna('').astype(str)
    df['Beneficiary'] = df['Beneficiary'].fillna('').astype(str)
    
    # עמודת חודש לשימוש בגרפים
    df['Month'] = df['Date'].dt.strftime('%m/%Y')
    
    return df

# --- פונקציית עזר לקטגוריזציה ---
def categorize_expense(row):
    text = (str(row['Action']) + " " + str(row['Details'])).lower()
    if any(x in text for x in ['ע.מפעולות', 'ע. מפעולות', 'ע. מסלול', 'עמלות']):
        return 'עמלות בנק'
    if 'גז ניהול מבנים' in text:
        return 'גז ניהול מבנים'
    return row['Details'] if row['Details'] else row['Action']

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
        
        mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
        df_filtered = df.loc[mask]
        
        st.success(f"מציג נתונים בין {start_date} ל-{end_date}")
        
        # ========================================================
        # שורה 1: גרפים כלליים
        # ========================================================
        col_top1, col_top2 = st.columns(2)
        
        with col_top1:
            st.subheader("⚖️ הכנסות מול הוצאות (חודשי)")
            if not df_filtered.empty:
                monthly_summary = df_filtered.copy()
                monthly_summary['MonthDate'] = monthly_summary['Date'].dt.to_period('M')
                grouped = monthly_summary.groupby('MonthDate')[['Credit', 'Debit']].sum().reset_index()
                grouped['MonthStr'] = grouped['MonthDate'].dt.strftime('%m/%Y')
                
                monthly_melt = grouped.melt(id_vars='MonthStr', value_vars=['Credit', 'Debit'], 
                                            var_name='Type', value_name='Amount')
                monthly_melt['Type'] = monthly_melt['Type'].replace({'Credit': 'הכנסות', 'Debit': 'הוצאות'})
                
                fig_inc_exp = px.bar(monthly_melt, x='MonthStr', y='Amount', color='Type', barmode='group',
                                     text='Amount',
                                     color_discrete_map={'הכנסות': '#2ecc71', 'הוצאות': '#e74c3c'},
                                     labels={'Amount': 'סכום (ש"ח)', 'MonthStr': 'חודש', 'Type': 'סוג'})
                fig_inc_exp.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
                st.plotly_chart(fig_inc_exp, use_container_width=True)

        with col_top2:
            st.subheader("💰 מגמת יתרה בחשבון")
            df_sorted = df_filtered.sort_values('Date')
            fig_bal = px.line(df_sorted, x='Date', y='Balance',
                              labels={'Balance': 'יתרה', 'Date': 'תאריך'},
                              color_discrete_sequence=['purple'])
            st.plotly_chart(fig_bal, use_container_width=True)

        # ========================================================
        # פירוט תשלומים למשפחה - הגרף המשופר
        # ========================================================
        st.markdown("---")
        st.subheader("🔎 פירוט תשלומים למשפחה")
        
        paying_families = sorted(df_filtered[df_filtered['Credit'] > 0]['Beneficiary'].unique())
        
        if len(paying_families) > 0:
            selected_family = st.selectbox("בחר משפחה להצגת פירוט:", paying_families)
            
            family_payments = df_filtered[
                (df_filtered['Beneficiary'] == selected_family) & 
                (df_filtered['Credit'] > 0)
            ].copy().sort_values('Date')
            
            if not family_payments.empty:
                # יצירת מפתח ייחודי לכל שורה כדי למנוע כפילויות/איחוד ברים
                family_payments['RowID'] = range(len(family_payments))
                family_payments['FullDate'] = family_payments['Date'].dt.strftime('%d/%m/%Y')

                # יצירת הגרף - משתמשים ב-RowID כציר X כדי שכל תשלום יקבל בר נפרד
                fig_family = px.bar(
                    family_payments, 
                    x='RowID', 
                    y='Credit',
                    text='Credit',
                    color='Month', # צבע לפי חודש
                    hover_data={'FullDate': True, 'Month': False, 'RowID': False},
                    labels={'Credit': 'סכום (ש"ח)', 'FullDate': 'תאריך תשלום'}
                )

                # עדכון תוויות ציר ה-X שיראו את החודש במקום את ה-ID
                fig_family.update_layout(
                    xaxis=dict(
                        tickmode='array',
                        tickvals=family_payments['RowID'],
                        ticktext=family_payments['Month'],
                        title_text="חודש ושנה"
                    ),
                    showlegend=False,
                    bargap=0.3 # שולט על עובי הברים (ככל שקטן הבר עבה יותר)
                )

                # עיצוב הטקסט מעל הברים - גדול ובולט
                fig_family.update_traces(
                    texttemplate='%{text:,.0f}',
                    textposition='outside',
                    textfont=dict(size=14, color='black'),
                    marker_line_width=1,
                    marker_line_color='black'
                )
                
                # התאמת גובה הגרף
                fig_family.update_layout(height=450, margin=dict(t=50, b=50, l=50, r=50))
                
                st.plotly_chart(fig_family, use_container_width=True)

                # טבלת פירוט
                st.caption("פירוט בטבלה:")
                display_table = family_payments[['Date', 'Credit', 'Details', 'Action']].copy()
                display_table['Date'] = display_table['Date'].dt.strftime('%d/%m/%Y')
                st.dataframe(display_table.rename(columns={'Date': 'תאריך', 'Credit': 'סכום', 'Details': 'פרטים', 'Action': 'פעולה'}), 
                             use_container_width=True, hide_index=True)
                
                st.metric("סה\"כ שולם בתקופה", f"{family_payments['Credit'].sum():,.0f} ש\"ח")

        # ========================================================
        # פילוח הוצאות ופירוט חודשי (שאר הקוד)
        # ========================================================
        st.markdown("---")
        # ... (שאר הקוד שלך ללא שינוי מהותי) ...
        st.subheader("🍰 פילוח הוצאות כללי")
        expense_df = df_filtered[df_filtered['Debit'] > 0].copy()
        if not expense_df.empty:
            expense_df['Category'] = expense_df.apply(categorize_expense, axis=1)
            cat_summary = expense_df.groupby('Category')['Debit'].sum().reset_index()
            fig_p1 = px.pie(cat_summary, values='Debit', names='Category', hole=0.4)
            st.plotly_chart(fig_p1, use_container_width=True)

    except Exception as e:
        st.error(f"שגיאה: {e}")
else:
    st.info("אנא העלה קובץ אקסל כדי להתחיל.")
