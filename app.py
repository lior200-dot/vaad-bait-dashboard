import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- הגדרות עמוד ---
st.set_page_config(page_title="דשבורד ועד בית", layout="wide")
st.title("🏠 ניהול כספי - ועד בית אור החיים 5")

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
    
    # עמודת חודש לשימוש בגרפים - פורמט חודש/שנה
    df['Month'] = df['Date'].dt.strftime('%m/%Y')
    
    return df

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
            else:
                st.info("אין נתונים להצגה.")

        with col_top2:
            st.subheader("💰 מגמת יתרה בחשבון")
            df_sorted = df_filtered.sort_values('Date')
            fig_bal = px.line(df_sorted, x='Date', y='Balance',
                              labels={'Balance': 'יתרה', 'Date': 'תאריך'},
                              color_discrete_sequence=['purple'])
            fig_bal.update_layout(yaxis=dict(tickformat=",.0f"))
            st.plotly_chart(fig_bal, use_container_width=True)

        # ========================================================
        # שורה 2: חשמל ותשלומים
        # ========================================================
        col_mid1, col_mid2 = st.columns(2)

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

        with col_mid2:
            st.subheader("🏆 סיכום תשלומים לפי משפחה")
            income_df = df_filtered[df_filtered['Credit'] > 0]
            if not income_df.empty:
                # --- שינוי: מיון לפי שם (Beneficiary) במקום לפי סכום ---
                total_per_family = income_df.groupby('Beneficiary')['Credit'].sum().reset_index().sort_values('Beneficiary', ascending=True)
                
                fig_pay = px.bar(total_per_family, x='Beneficiary', y='Credit', text='Credit',
                                 labels={'Credit': 'סה"כ שולם', 'Beneficiary': 'משפחה'},
                                 color_discrete_sequence=['teal'])
                fig_pay.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                st.plotly_chart(fig_pay, use_container_width=True)
            else:
                st.info("אין הכנסות בטווח שנבחר.")

        # ========================================================
        # פירוט תשלומים למשפחה
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
                family_payments['RowID'] = range(len(family_payments))
                family_payments['FullDate'] = family_payments['Date'].dt.strftime('%d/%m/%Y')
                
                fig_family = px.bar(
                    family_payments, 
                    x='RowID', 
                    y='Credit', 
                    text='Credit',
                    color='Month',
                    hover_data={'FullDate': True, 'Month': False, 'RowID': False},
                    title=f'היסטוריית תשלומים - {selected_family}',
                    labels={'Credit': 'סכום (ש"ח)', 'FullDate': 'תאריך תשלום'}
                )
                
                fig_family.update_layout(
                    xaxis=dict(
                        tickmode='array',
                        tickvals=family_payments['RowID'],
                        ticktext=family_payments['Month'],
                        title_text="חודש ושנה"
                    ),
                    showlegend=False,
                    bargap=0.3
                )
                
                fig_family.update_traces(
                    texttemplate='%{text:,.0f}', 
                    textposition='outside',
                    textfont=dict(size=14, color='black'),
                    marker_line_width=1,
                    marker_line_color='black'
                )
                
                st.plotly_chart(fig_family, use_container_width=True)

            st.caption("פירוט בטבלה:")
            display_table = family_payments[['Date', 'Credit', 'Details', 'Action']].copy()
            display_table['Date'] = display_table['Date'].dt.strftime('%d/%m/%Y')
            display_table = display_table.rename(columns={'Date': 'תאריך', 'Credit': 'סכום (ש"ח)', 'Details': 'פרטים', 'Action': 'פעולה'})
            st.dataframe(display_table, use_container_width=True, hide_index=True)
            
            total_paid = family_payments['Credit'].sum()
            st.write(f"**סה\"כ שולם בתקופה זו:** {total_paid:,.0f} ש\"ח")

        else:
            st.info("אין נתוני תשלומים בטווח התאריכים שנבחר.")

        # ========================================================
        # פילוח הוצאות (כללי)
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
        # פירוט חודשי
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
        else:
            st.info("אין נתונים זמינים לבחירת חודשים.")

    except Exception as e:
        st.error(f"שגיאה בעיבוד הקובץ: {e}")
        st.write("נא לוודא שקובץ האקסל הוא בפורמט התקין מהבנק.")

else:
    st.info("אנא העלה קובץ אקסל כדי להתחיל.")

