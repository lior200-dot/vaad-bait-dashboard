import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- הגדרות עמוד ---
st.set_page_config(page_title="דשבורד ועד בית", layout="wide")
st.title("🏠 דשבורד ניהול כספי - ועד בית")

# --- אתחול Session State ---
if 'merge_map' not in st.session_state:
    st.session_state['merge_map'] = {}
if 'manual_tags' not in st.session_state:
    st.session_state['manual_tags'] = {}  # מילון לשמירת שיוך ידני של צ'קים: {index: new_name}

# --- פונקציית טעינת נתונים ---
def load_data(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, skiprows=4)
        cols = df.columns.tolist()
        
        if len(cols) < 9:
            st.error("קובץ האקסל לא תואם למבנה המצופה.")
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
        
        # יצירת אינדקס ייחודי וקבוע לשורות (חשוב לשיוך הידני)
        df['OriginalIndex'] = df.index
        
        return df
    except Exception as e:
        st.error(f"שגיאה בטעינת הנתונים: {e}")
        return pd.DataFrame()

# --- פונקציית עזר לקטגוריזציה ---
def categorize_expense(row):
    text = (str(row['Action']) + " " + str(row['Details'])).lower()
    if any(x in text for x in ['עמלה', 'ע.מפעולות']): return 'עמלות בנק'
    if 'גז' in text: return 'גז'
    if 'חשמל' in text: return 'חשמל'
    if 'גינון' in text: return 'גינון'
    if 'מעלית' in text: return 'מעלית'
    return 'אחר'

# --- ממשק צד (Sidebar) ---
st.sidebar.header("העלאת נתונים")
uploaded_file = st.sidebar.file_uploader("בחר קובץ אקסל מהבנק", type=['xlsx', 'xls'])

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    if not df.empty:
        
        # ==========================================
        # 1. מנגנון שיוך צ'קים ומזומן (ידני)
        # ==========================================
        st.sidebar.markdown("---")
        with st.sidebar.expander("✍️ שיוך צ'קים/מזומן לדיירים", expanded=False):
            st.caption("כאן ניתן לשייך הפקדות ללא שם (כמו צ'קים) למשפחה ספציפית.")
            
            # סינון שורות שהן הכנסות (Credit > 0)
            income_rows = df[df['Credit'] > 0].copy()
            income_rows['Label'] = income_rows.apply(
                lambda x: f"{x['Date'].strftime('%d/%m')} | {x['Credit']}₪ | {x['Details']} | {x['Beneficiary']}", axis=1
            )
            
            # בחירת השורה הבעייתית
            selected_row_label = st.selectbox("בחר תנועה לשיוך:", income_rows['Label'].tolist())
            
            # חילוץ האינדקס של השורה שנבחרה
            if selected_row_label:
                selected_idx = income_rows[income_rows['Label'] == selected_row_label]['OriginalIndex'].values[0]
                
                # רשימת דיירים קיימת + אפשרות להוסיף חדש
                existing_names = sorted(df[df['Credit'] > 0]['Beneficiary'].unique())
                target_family = st.selectbox("שייך למשפחה:", existing_names + ["אחר..."])
                
                if target_family == "אחר...":
                    target_family = st.text_input("הזן שם משפחה חדש:")
                
                if st.button("בצע שיוך"):
                    if target_family:
                        st.session_state['manual_tags'][selected_idx] = target_family
                        st.success("השיוך בוצע בהצלחה! (הגרפים יתעדכנו מיד)")
                        st.rerun()

        # החלת השיוכים הידניים על הדאטה-פריים
        for idx, new_name in st.session_state['manual_tags'].items():
            df.loc[df['OriginalIndex'] == idx, 'Beneficiary'] = new_name

        # ==========================================
        # 2. מנגנון איחוד משפחות (הקוד הקודם)
        # ==========================================
        with st.sidebar.expander("🔗 איחוד שמות ומשפחות", expanded=False):
            # ... (אותו קוד כמו קודם) ...
            all_beneficiaries = sorted(df[df['Credit'] > 0]['Beneficiary'].unique())
            available_beneficiaries = [name for name in all_beneficiaries if name not in st.session_state['merge_map']]
            
            with st.form("merge_form", clear_on_submit=True):
                new_group_name = st.text_input("שם מאוחד")
                selected_names = st.multiselect("בחר שמות:", available_beneficiaries)
                if st.form_submit_button("שמור"):
                    for name in selected_names: st.session_state['merge_map'][name] = new_group_name
                    st.rerun()
            
            if st.session_state['merge_map']:
                st.write("**איחודים פעילים:**")
                if st.button("אפס איחודים"):
                    st.session_state['merge_map'] = {}
                    st.rerun()

        # החלת האיחוד
        if st.session_state['merge_map']:
            df['Beneficiary'] = df['Beneficiary'].replace(st.session_state['merge_map'])

        # ==========================================
        # סינון תאריכים
        # ==========================================
        st.sidebar.markdown("---")
        min_date = df['Date'].min().date()
        max_date = df['Date'].max().date()
        start_date = st.sidebar.date_input("תאריך התחלה", min_date)
        end_date = st.sidebar.date_input("תאריך סיום", max_date)
        mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
        df_filtered = df.loc[mask]

        # ==========================================
        # מפת חום חכמה (מצטברת)
        # ==========================================
        st.subheader("🌡️ מפת גבייה ומצב חוב (מצטבר)")
        
        # 1. קלט סכום ועד חודשי
        monthly_fee = st.number_input("הכנס סכום ועד בית חודשי למשפחה (בש\"ח):", min_value=0, value=250, step=10)
        
        if monthly_fee > 0:
            # 2. יצירת ציר זמן מלא
            normalized_start = start_date.replace(day=1)
            full_date_range = pd.date_range(start=normalized_start, end=end_date, freq='MS')
            
            heatmap_data = []
            
            # רשימת כל המשפחות המשלמות (אחרי איחוד ושיוך)
            families = sorted(df_filtered[df_filtered['Credit'] > 0]['Beneficiary'].unique())
            
            for family in families:
                # סינון תשלומים למשפחה זו
                family_payments = df_filtered[
                    (df_filtered['Beneficiary'] == family) & 
                    (df_filtered['Credit'] > 0)
                ].copy()
                
                cumulative_paid = 0
                cumulative_expected = 0
                
                for i, date_point in enumerate(full_date_range):
                    month_str = date_point.strftime('%m/%Y')
                    
                    # כמה צריך היה לשלם עד החודש הזה (כולל)?
                    cumulative_expected += monthly_fee
                    
                    # כמה שילמו בחודש הספציפי הזה?
                    payment_in_month = family_payments[family_payments['Month'] == month_str]['Credit'].sum()
                    cumulative_paid += payment_in_month
                    
                    # חישוב היתרה המצטברת (האם שילמו מספיק כדי לכסות עד עכשיו?)
                    balance = cumulative_paid - cumulative_expected
                    
                    # סטטוס לצביעה
                    # אם היתרה חיובית או אפס - הכל בסדר (שילמו מראש או בזמן)
                    # אם היתרה שלילית - הם בחוב
                    status_val = balance 
                    
                    heatmap_data.append({
                        'Family': family,
                        'Month': month_str,
                        'Balance': balance,
                        'PaidThisMonth': payment_in_month
                    })

            if heatmap_data:
                hm_df = pd.DataFrame(heatmap_data)
                
                # המרה לפורמט מטריצה (Pivot) עבור מפת החום
                hm_pivot = hm_df.pivot(index='Family', columns='Month', values='Balance')
                
                # סידור העמודות לפי סדר כרונולוגי
                sorted_columns = [d.strftime('%m/%Y') for d in full_date_range]
                # סינון רק לעמודות שקיימות ב-pivot (למניעת שגיאות בקצוות)
                valid_columns = [c for c in sorted_columns if c in hm_pivot.columns]
                hm_pivot = hm_pivot[valid_columns]
                
                # יצירת מפת חום עם Plotly
                # צבע אדום למינוס (חוב), ירוק לפלוס (שולם/יתרה), לבן לאפס
                fig_heat = px.imshow(
                    hm_pivot,
                    labels=dict(x="חודש", y="משפחה", color="יתרה מצטברת"),
                    x=valid_columns,
                    y=hm_pivot.index,
                    color_continuous_scale=['red', 'white', 'green'],
                    color_continuous_midpoint=0, # האפס הוא המרכז (לבן)
                    text_auto=False,
                    aspect="auto"
                )
                
                # הוספת טקסט מותאם אישית (להציג יתרה בתוך הריבועים)
                fig_heat.update_traces(
                    text=hm_pivot.values,
                    texttemplate="%{text:.0f}",
                    hovertemplate="משפחה: %{y}<br>חודש: %{x}<br>יתרה מצטברת: %{z:,.0f}₪<extra></extra>"
                )
                
                fig_heat.update_layout(height=max(400, len(families) * 40)) # גובה דינמי
                st.plotly_chart(fig_heat, use_container_width=True)
                
                st.info("💡 **הסבר:** מפה זו מציגה יתרה מצטברת. **ירוק** = שולם בזמן או מראש (פלוס). **אדום** = חוב מצטבר. גם אם דייר שילם בתחילת השנה, החודשים הבאים יהיו ירוקים כי היתרה שלו מכסה אותם.")

        else:
            st.warning("נא להזין סכום ועד חודשי כדי לחשב את מפת החובות.")

        # ==========================================
        # המשך הגרפים הרגילים (פירוט משפחה וכו')
        # ==========================================
        # ... (כאן יבואו שאר הגרפים מהקוד הקודם שלך) ...
        # שים לב: הגרפים האחרים ישתמשו ב-df שיש בו כבר את השמות המעודכנים!

else:
    st.info("אנא העלה קובץ אקסל כדי להתחיל.")
