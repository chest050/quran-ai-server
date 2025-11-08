import json
import re
import difflib
import pytesseract

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# مسار Tesseract في ويندوز
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# تحميل نص الكتاب كاملاً
try:
    with open("quran_tafsir_text.txt", "r", encoding="utf-8") as f:
        KNOWLEDGE_BASE = f.read()
except FileNotFoundError:
    KNOWLEDGE_BASE = ""

# تجهيز الأسطر
LINES = [line.strip() for line in KNOWLEDGE_BASE.split("\n") if line.strip()]

app = FastAPI()

# السماح بالاتصال من الواجهة
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # عدّلها لاحقًا للدومين الخاص بك
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تنظيف نص عربي
def clean_text(text: str) -> str:
    text = re.sub(r"[^\u0600-\u06FF\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()

# البحث الذكي في الكتاب
def search_in_book(question: str):
    if not LINES:
        return None

    q = clean_text(question)
    if not q:
        return None

    q_words = [w for w in q.split() if len(w) > 2]
    if not q_words:
        return None

    best_score = 0.0
    best_index = -1

    for i, line in enumerate(LINES):
        line_clean = clean_text(line)
        if not line_clean:
            continue

        # نسبة تطابق الكلمات
        common = sum(1 for w in q_words if w in line_clean)
        word_score = common / max(1, len(q_words))

        # تشابه تقريبي عام
        sim = difflib.SequenceMatcher(None, q, line_clean).ratio()

        # مزيج من الاثنين
        score = (word_score * 0.7) + (sim * 0.3)

        if score > best_score:
            best_score = score
            best_index = i

    # إذا لم نصل لحد معقول، نرجع لا شيء
    if best_index == -1 or best_score < 0.30:
        return None

    # نرجع فقرة حول السطر الأفضل (3 قبل + 3 بعد)
    start = max(0, best_index - 2)
    end = min(len(LINES), best_index + 2)
    paragraph = "\n".join(LINES[start:end])
    return paragraph

def fallback_answer():
    return (
        "⚠️ لم يتم العثور على إجابة دقيقة في النص المتوفر.\n"
        "المرجع المعتمد: كتاب (القرآن الكريم وتفسيره - السنة الأولى المشتركة 1447هـ)."
    )

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    user_msg = data.get("message", "").strip()

    if not user_msg:
        return JSONResponse(content={"response": "🖊️ الرجاء كتابة سؤالك أولاً."}, status_code=400)

    answer = search_in_book(user_msg)
    if answer:
        return JSONResponse(content={"response": answer})
    else:
        return JSONResponse(content={"response": fallback_answer()})

@app.post("/api/ocr")
async def ocr_endpoint(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        with open("temp_img.jpg", "wb") as f:
            f.write(contents)

        extracted = pytesseract.image_to_string("temp_img.jpg", lang="ara")

        if not extracted.strip():
            return JSONResponse(content={"response": "❌ لم يتم التعرف على أي نص في الصورة."})

        answer = search_in_book(extracted)
        if answer:
            return JSONResponse(content={"response": answer})
        else:
            return JSONResponse(content={"response": fallback_answer()})
    except Exception as e:
        return JSONResponse(content={"response": f"حدث خطأ أثناء تحليل الصورة: {e}"})

# تقديم الملفات الثابتة
app.mount("/", StaticFiles(directory=".", html=True), name="static")
@app.get("/")
async def home():
    return FileResponse("index.html")
