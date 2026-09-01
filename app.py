import streamlit as st
import requests
from PIL import Image
import datetime
import json
import google.generativeai as genai

st.set_page_config(page_title="ระบบบันทึกสลิปออนไลน์", page_icon="🧾", layout="centered")

# === นำลิงก์ Web App URL จาก Google Sheets มาวางในเครื่องหมายคำพูดด้านล่างนี้ ===
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxoj88M6eoGT5ck0yUtPcDDNZAIBSazAVzJwHt5sqpvVl34irUkqZ_RAr2xQ69nHV3yJA/exec"

def analyze_slip_with_ai(image_file, api_key):
    genai.configure(api_key=api_key)
    target_model = "gemini-3.6-flash"
    model = genai.GenerativeModel(target_model)
    img = Image.open(image_file)
    prompt = """
    อ่านข้อมูลสลิปโอนเงินนี้ ส่งกลับมาเป็น JSON เท่านั้น
    {
      "transfer_date": "วันที่โอน (DD/MM/YYYY หรือ YYYY-MM-DD)",
      "transfer_time": "เวลาโอน (HH:MM)",
      "sender_name": "ชื่อผู้โอน",
      "receiver_name": "ชื่อผู้รับโอน",
      "bank": "ชื่อธนาคาร",
      "amount": "ยอดเงินตัวเลขเท่านั้น"
    }
    """
    response = model.generate_content([prompt, img])
    result_text = response.text.strip()
    
    if result_text.startswith('```json'): result_text = result_text[7:]
    elif result_text.startswith('```'): result_text = result_text[3:]
    if result_text.endswith('```'): result_text = result_text[:-3]
        
    return json.loads(result_text.strip())

st.title("📱 ระบบบันทึกสลิป (เชื่อมต่อ Google Sheets)")
st.markdown("เวอร์ชันออนไลน์ ข้อมูลจะถูกบันทึกขึ้น Google Sheets ทันที")

if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''

with st.expander("⚙️ ตั้งค่ารหัส Gemini API Key", expanded=(st.session_state['api_key'] == '')):
    api_input = st.text_input("ใส่ API Key ของคุณ:", type="password", value=st.session_state['api_key'])
    if st.button("บันทึกรหัสชั่วคราว"):
        st.session_state['api_key'] = api_input
        st.success("บันทึกเรียบร้อย! สามารถเริ่มสแกนได้เลย")
        st.rerun()

st.markdown("---")
slip_type = st.radio("ประเภทของสลิปใบนี้:", ["โอนเข้า (รับเงิน)", "โอนออก (จ่ายเงิน)"], horizontal=True)

with st.container():
    uploaded_file = st.file_uploader("ถ่ายรูป หรืออัปโหลดสลิป", type=["jpg", "jpeg", "png"])
    note = st.text_input("หมายเหตุ / ชื่อคอร์ส:", placeholder="เช่น ด.ช.สมชาย คอร์สวิทย์")

    if uploaded_file is not None:
        st.image(Image.open(uploaded_file), caption="สลิปที่กำลังตรวจสอบ", use_container_width=True)

        if st.button("สแกนและบันทึกลง Google Sheets", type="primary", use_container_width=True):
            if not st.session_state['api_key']:
                st.error("กรุณาใส่ API Key ด้านบนก่อนครับ")
            elif WEBHOOK_URL == "วาง_URL_ของ_Google_Apps_Script_ที่นี่":
                st.error("คุณยังไม่ได้นำลิงก์จาก Google Sheets มาใส่ในโค้ดบรรทัดที่ 11 ครับ")
            else:
                with st.spinner("🤖 กำลังสแกนและส่งข้อมูลขึ้นคลาวด์..."):
                    try:
                        ai_data = analyze_slip_with_ai(uploaded_file, st.session_state['api_key'])
                        
                        payload = {
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "slip_type": slip_type,
                            "transfer_date": ai_data.get("transfer_date", "-"),
                            "transfer_time": ai_data.get("transfer_time", "-"),
                            "sender_name": ai_data.get("sender_name", "-"),
                            "receiver_name": ai_data.get("receiver_name", "-"),
                            "bank": ai_data.get("bank", "-"),
                            "amount": float(ai_data.get("amount", 0.0)),
                            "note": note
                        }
                        
                        response = requests.post(WEBHOOK_URL, json=payload)
                        
                        if response.text == "Success":
                            st.success(f"✅ บันทึกยอดเงิน {payload['amount']} บาท ลง Google Sheets เรียบร้อย!")
                            st.json(ai_data)
                        else:
                            st.error(f"บันทึกข้อมูลไม่สำเร็จ: {response.text}")
                            
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")
