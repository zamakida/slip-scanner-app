
import streamlit as st
import requests
from PIL import Image
import datetime
import json
import google.generativeai as genai
import base64
import io
import time
import re

# =========================================================
# ตั้งค่าหน้าเว็บ
# =========================================================
st.set_page_config(
    page_title="ระบบบันทึกสลิปออนไลน์",
    page_icon="🧾",
    layout="centered"
)

# =========================================================
# Google Apps Script Webhook
# =========================================================
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwCefdCFZp5RtEBBJjBD72CRJUlQmS3VYL3f-2F-iAI2n_vLyFDe-TG5c-1jXIS19KtXQ/exec"


# =========================================================
# ฟังก์ชันดึง JSON จากคำตอบ Gemini
# =========================================================
def extract_json(text):
    text = text.strip()

    # ลบ ```json ... ```
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # หา JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("Gemini ไม่ได้ส่งข้อมูล JSON กลับมา")

    return json.loads(match.group(0))


# =========================================================
# วิเคราะห์สลิปด้วย Gemini
# =========================================================
def analyze_slip_with_ai(img, api_key):

    genai.configure(api_key=api_key)

    # โมเดล Stable
    target_model = "gemini-3.6-flash"

    model = genai.GenerativeModel(target_model)

    prompt = """
คุณเป็นระบบ OCR สำหรับอ่านสลิปโอนเงินของประเทศไทย

อ่านข้อความจากสลิป แล้วส่งกลับมาเป็น JSON เท่านั้น
ห้ามใส่คำอธิบาย
ห้ามใส่ Markdown
ห้ามใส่ ```json

รูปแบบ JSON:

{
  "transfer_date": "วันที่โอน เช่น 02/09/2026",
  "transfer_time": "เวลา เช่น 10:30",
  "sender_name": "ชื่อผู้โอน",
  "receiver_name": "ชื่อผู้รับโอน",
  "bank": "ชื่อธนาคาร",
  "amount": 0
}

ข้อกำหนด:
- amount ต้องเป็นตัวเลขเท่านั้น
- ห้ามใส่คำว่า บาท
- ถ้าไม่พบข้อมูล ให้ใช้ "-"
- ห้ามเดาข้อมูลที่ไม่เห็นในสลิป
"""

    # =====================================================
    # Retry สูงสุด 3 ครั้ง
    # =====================================================
    max_retry = 3

    for attempt in range(max_retry):

        try:

            response = model.generate_content(
                [prompt, img]
            )

            result_text = response.text.strip()

            return extract_json(result_text)

        except Exception as e:

            error_text = str(e)

            # -------------------------------------------------
            # ตรวจว่าเป็น 429 / Quota
            # -------------------------------------------------
            if "429" in error_text or "quota" in error_text.lower():

                if attempt < max_retry - 1:

                    wait_time = 55

                    st.warning(
                        f"⏳ Gemini ใช้งานครบโควตาชั่วคราว "
                        f"กำลังลองใหม่ใน {wait_time} วินาที..."
                    )

                    time.sleep(wait_time)

                    continue

                else:

                    raise Exception(
                        "QUOTA_EXCEEDED"
                    )

            # -------------------------------------------------
            # Error อื่น
            # -------------------------------------------------
            raise e

    raise Exception("ไม่สามารถอ่านสลิปได้")


# =========================================================
# หัวเว็บ
# =========================================================
st.title("📱 ระบบบันทึกสลิป + เซฟรูปลงไดรฟ์")

st.markdown(
    """
    สแกนสลิป → อ่านข้อมูลอัตโนมัติ → บันทึกลง Google Sheets
    พร้อมเก็บรูปสลิปไว้ใน Google Drive
    """
)


# =========================================================
# API KEY
# =========================================================
if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""


with st.expander(
    "⚙️ ตั้งค่ารหัส Gemini API Key",
    expanded=(st.session_state["api_key"] == "")
):

    api_input = st.text_input(
        "ใส่ API Key ของคุณ:",
        type="password",
        value=st.session_state["api_key"]
    )

    if st.button("💾 บันทึกรหัสชั่วคราว"):

        st.session_state["api_key"] = api_input

        st.success("✅ บันทึก API Key เรียบร้อย")

        st.rerun()


# =========================================================
# ประเภทสลิป
# =========================================================
st.markdown("---")

slip_type = st.radio(
    "ประเภทของสลิปใบนี้:",
    [
        "โอนเข้า (รับเงิน)",
        "โอนออก (จ่ายเงิน)"
    ],
    horizontal=True
)


# =========================================================
# Upload
# =========================================================
with st.container():

    uploaded_file = st.file_uploader(
        "📷 ถ่ายรูป หรืออัปโหลดสลิป",
        type=["jpg", "jpeg", "png"]
    )

    note = st.text_input(
        "📝 หมายเหตุ / ชื่อคอร์ส:",
        placeholder="เช่น ด.ช.สมชาย คอร์สวิทย์"
    )


    # =====================================================
    # แสดงรูป
    # =====================================================
    if uploaded_file is not None:

        img = Image.open(uploaded_file)

        # ทำสำเนาเพื่อป้องกันการแก้ต้นฉบับ
        img = img.copy()

        img.thumbnail((1000, 1000))

        st.image(
            img,
            caption="🧾 สลิปที่กำลังตรวจสอบ",
            use_container_width=True
        )


        # =================================================
        # ปุ่มสแกน
        # =================================================
        if st.button(
            "🔍 สแกนและบันทึกข้อมูลพร้อมรูปภาพ",
            type="primary",
            use_container_width=True
        ):

            # ------------------------------------------------
            # ตรวจ API KEY
            # ------------------------------------------------
            if not st.session_state["api_key"]:

                st.error(
                    "❌ กรุณาใส่ Gemini API Key ด้านบนก่อนครับ"
                )

                st.stop()


            # ------------------------------------------------
            # ตรวจ Webhook
            # ------------------------------------------------
            if not WEBHOOK_URL.startswith("https://script.google.com"):

                st.error(
                    "❌ กรุณาตรวจสอบ WEBHOOK_URL"
                )

                st.stop()


            # =================================================
            # เริ่มทำงาน
            # =================================================
            with st.spinner(
                "🤖 กำลังอ่านสลิปและบันทึกข้อมูล..."
            ):

                try:

                    # =================================================
                    # 1. อ่านสลิป
                    # =================================================
                    ai_data = analyze_slip_with_ai(
                        img,
                        st.session_state["api_key"]
                    )


                    # =================================================
                    # 2. เตรียมรูป
                    # =================================================
                    buffered = io.BytesIO()

                    if img.mode != "RGB":
                        img = img.convert("RGB")

                    img.save(
                        buffered,
                        format="JPEG",
                        quality=90
                    )

                    image_base64 = base64.b64encode(
                        buffered.getvalue()
                    ).decode("utf-8")


                    # =================================================
                    # 3. แปลงยอดเงิน
                    # =================================================
                    try:

                        amount = float(
                            str(
                                ai_data.get(
                                    "amount",
                                    0
                                )
                            ).replace(",", "")
                        )

                    except:

                        amount = 0


                    # =================================================
                    # 4. เตรียมข้อมูลส่ง Google Apps Script
                    # =================================================
                    payload = {

                        "timestamp":
                            datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),

                        "slip_type":
                            slip_type,

                        "transfer_date":
                            ai_data.get(
                                "transfer_date",
                                "-"
                            ),

                        "transfer_time":
                            ai_data.get(
                                "transfer_time",
                                "-"
                            ),

                        "sender_name":
                            ai_data.get(
                                "sender_name",
                                "-"
                            ),

                        "receiver_name":
                            ai_data.get(
                                "receiver_name",
                                "-"
                            ),

                        "bank":
                            ai_data.get(
                                "bank",
                                "-"
                            ),

                        "amount":
                            amount,

                        "note":
                            note,

                        "image_base64":
                            image_base64
                    }


                    # =================================================
                    # 5. ส่งข้อมูลไป Google Apps Script
                    # =================================================
                    response = requests.post(
                        WEBHOOK_URL,
                        json=payload,
                        timeout=60
                    )


                    # =================================================
                    # 6. ตรวจผลลัพธ์
                    # =================================================
                    if response.text.strip() == "Success":

                        st.success(
                            f"🎉 บันทึกสำเร็จ!\n\n"
                            f"💰 ยอดเงิน: {amount:,.2f} บาท\n"
                            f"🧾 ประเภท: {slip_type}\n"
                            f"📁 รูปสลิปถูกเก็บใน Google Drive แล้ว"
                        )

                        st.markdown("### 🤖 ข้อมูลที่ AI อ่านได้")

                        st.json(ai_data)

                    else:

                        st.error(
                            "❌ Google Apps Script บันทึกข้อมูลไม่สำเร็จ"
                        )

                        st.code(
                            response.text
                        )


                # =====================================================
                # จัดการ Quota
                # =====================================================
                except Exception as e:

                    error_message = str(e)

                    if error_message == "QUOTA_EXCEEDED":

                        st.error(
                            """
                            🚨 Gemini API ใช้งานครบโควตาแล้ว

                            ขณะนี้ API Key ของคุณใช้คำขอครบตาม Free Tier
                            กรุณารอสักครู่แล้วลองใหม่

                            ⚠️ การเปลี่ยนโค้ดหรือกดปุ่มซ้ำหลายครั้ง
                            จะไม่ทำให้โควตาเพิ่มขึ้น
                            """
                        )

                        st.info(
                            "💡 หากต้องการใช้งานระบบบันทึกสลิปจำนวนมาก "
                            "ควรใช้ Gemini API แบบมี Billing/Quota ที่เหมาะกับงานจริง"
                        )

                    else:

                        st.error(
                            f"❌ เกิดข้อผิดพลาด: {error_message}"
                        )
