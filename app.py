import streamlit as st
import requests
from PIL import Image
import datetime
import json
import google.generativeai as genai

st.set_page_config(page_title="ระบบบันทึกสลิปออนไลน์", page_icon="🧾", layout="centered")

# === วาง URL ของ Google Apps Script ที่นี่ ===
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbw5OpwLNxub-721GJGiWiBFFHFRgL7TXcY7y8BXcDlkza2H0Mpk6-XHIbvkk64-jyodBw/exec"

def analyze_slip_with_ai(img, api_key):
    genai.configure(api_key=api_key)
    target_model = "gemini-3.6-flash"
    model = genai.GenerativeModel(target_model)
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

st.title("📱 ระบบบันทึกสลิปอัตโนมัติ")
st.markdown("สแกนสลิป ดึงยอดเงิน และบันทึกลง Google Sheets ทันที")

if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''

with st.expander("⚙️ ตั้งค่ารหัส Gemini API Key", expanded=(st.session_state['api_key'] == '')):
    api_input = st.text_input("ใส่ API Key ของคุณ:", type="password", value=st.session_state['api_key'])
    if st.button("บันทึกรหัสชั่วคราว"):
        st.session_state['api_key'] = api_input
        st.success("บันทึกเรียบร้อย!")
        st.rerun()

st.markdown("---")
slip_type = st.radio("ประเภทของสลิปใบนี้:", ["โอนเข้า (รับเงิน)", "โอนออก (จ่ายเงิน)"], horizontal=True)

with st.container():
    uploaded_file = st.file_uploader("ถ่ายรูป หรืออัปโหลดสลิป", type=["jpg", "jpeg", "png"])
    note = st.text_input("หมายเหตุ / ชื่อคอร์ส:", placeholder="เช่น ด.ช.สมชาย คอร์สวิทย์")

    if uploaded_file is not None:
        img = Image.open(uploaded_file)
        img.thumbnail((800, 800))
        st.image(img, caption="สลิปที่กำลังตรวจสอบ", use_container_width=True)

        if st.button("สแกนและบันทึกข้อมูล", type="primary", use_container_width=True):
            if not st.session_state['api_key']:
                st.error("กรุณาใส่ API Key ด้านบนก่อนครับ")
            elif WEBHOOK_URL == "วาง_URL_ของ_Google_Apps_Script_ที่นี่":
                st.error("อย่าลืมนำลิงก์มาใส่ในโค้ดบรรทัดที่ 11 ครับ")
            else:
              with st.spinner("🤖 กำลังอ่านสลิปและบันทึกข้อมูล..."):
                  try:
                      ai_data = analyze_slip_with_ai(img, st.session_state['api_key'])

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
                          st.success(f"✅ บันทึกยอดเงิน {payload['amount']} บาท เรียบร้อย!")
                          st.json(ai_data)
                      else:
                          st.error(f"บันทึกข้อมูลไม่สำเร็จ: {response.text}")

                  except Exception as e:
                      st.error(f"เกิดข้อผิดพลาด: {str(e)}")
