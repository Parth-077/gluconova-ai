from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import pickle
import os
import re
import io
import sqlite3
from datetime import datetime
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
if os.name == 'nt':  # Windows
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    else:
        print("⚠️ Tesseract not found at default location. OCR may not work.")
        print("   Please install Tesseract or set the correct path.")
app = Flask(__name__)
# SECURITY: Restrict CORS to localhost only (change for production)
CORS(app, resources={r"/*": {"origins": ["http://localhost:8080", "http://127.0.0.1:8080"]}})
DB_NAME = 'gluconova.db'
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            patient_name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
init_db()
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
class ModelPipeline:
    def __init__(self, scaler, model):
        self.scaler = scaler
        self.model = model
    def predict(self, X):
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    def predict_proba(self, X):
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
MODEL_PATH = 'diabetes_model.pkl'
def load_model():
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, 'rb') as f:
            return pickle.load(f)
    else:
        print("⚠️ Model not found! Please run train_model.py first.")
        return None
model = load_model()
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "GlucoNova AI Backend is running",
        "version": "1.0",
        "model_loaded": model is not None,
        "ocr_enabled": True
    })
def extract_text_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        print(f"PDF extraction error: {str(e)}")
        return None
def extract_text_from_image(image_path):
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        print(f"OCR error: {str(e)}")
        return None
def parse_medical_data(text):
    data = {
        'age': None,
        'weight': None,
        'sugar': None,
        'hba1c': None
    }
    if not text:
        return data
    original_text = text
    text = text.lower()
    age_keywords = [
        'age', 'yrs', 'years', 'year', 'yr', 'y.o.', 'yo', 'pt age', 'patient age'
    ]
    age_candidates = []
    for match in re.finditer(r'\b(\d{1,3})\b', text):
        num = int(match.group(1))
        if 1 <= num <= 120:
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end]
            for keyword in age_keywords:
                if keyword in context:
                    age_candidates.append((num, match.start()))
                    break
    if age_candidates:
        data['age'] = age_candidates[0][0]
    weight_keywords = ['weight', 'wt', 'body weight', 'kg', 'kgs']
    weight_candidates = []
    for match in re.finditer(r'\b(\d{1,3}(?:\.\d{1,2})?)\b', text):
        num = float(match.group(1))
        if 20 <= num <= 300:
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end]
            for keyword in weight_keywords:
                if keyword in context:
                    weight_candidates.append((num, match.start()))
                    break
    if weight_candidates:
        data['weight'] = weight_candidates[0][0]
    glucose_keywords = [
        'fasting blood sugar', 'fasting blood glucose', 'fasting glucose', 'fasting sugar',
        'blood sugar fasting', 'blood glucose fasting', 'glucose fasting', 'sugar fasting',
        'fbs', 'fbg', 'fpg', 'fasting plasma glucose', 'plasma glucose fasting',
        'blood sugar', 'blood glucose', 'glucose', 'sugar', 'bs', 'glu', 'gluc',
        'random blood sugar', 'rbs', 'ppbs', 'post prandial'
    ]
    reference_words = [
        'normal', 'reference', 'range', 'limit', 'upto', 'up to', 'below', 'above',
        'less than', 'greater than', 'between', 'within', 'desirable', 'optimal',
        'normal range', 'ref range', 'biological reference'
    ]
    glucose_candidates = []
    for match in re.finditer(r'\b(\d{2,3})\b', text):
        num = int(match.group(1))
        if not (40 <= num <= 500):
            continue
        start = max(0, match.start() - 150)
        end = min(len(text), match.end() + 150)
        context = text[start:end]
        immediate_before = text[max(0, match.start()-10):match.start()]
        immediate_after = text[match.end():min(len(text), match.end()+10)]
        is_range = False
        if '-' in immediate_before or '-' in immediate_after:
            is_range = True
        if 'to' in immediate_before or 'to' in immediate_after:
            if re.search(r'\s+to\s+', immediate_before + immediate_after):
                is_range = True
        if '–' in immediate_before or '–' in immediate_after:  # en-dash
            is_range = True
        if '—' in immediate_before or '—' in immediate_after:  # em-dash
            is_range = True
        if is_range:
            continue
        has_glucose_keyword = False
        keyword_found = None
        for keyword in glucose_keywords:
            if keyword in context:
                has_glucose_keyword = True
                keyword_found = keyword
                break
        if not has_glucose_keyword:
            continue
        is_reference = False
        for ref_word in reference_words:
            if ref_word in context:
                is_reference = True
                break
        nearby = text[max(0, match.start()-5):min(len(text), match.end()+5)]
        if '<' in nearby or '>' in nearby or '≤' in nearby or '≥' in nearby:
            is_reference = True
        after_num = text[match.end():min(len(text), match.end()+20)]
        if '(' in immediate_before and ')' in immediate_after:
            is_reference = True
        has_units = False
        if 'mg/dl' in after_num or 'mg' in after_num or 'mgdl' in after_num:
            has_units = True
            if not is_reference:
                is_reference = False  # Definitely not reference
        if is_reference:
            continue
        score = 0
        fasting_keywords = [
            'fasting blood sugar', 'fasting blood glucose', 'fasting glucose', 
            'fasting sugar', 'blood sugar fasting', 'blood glucose fasting',
            'glucose fasting', 'sugar fasting', 'fbs', 'fbg', 'fpg',
            'fasting plasma glucose', 'plasma glucose fasting'
        ]
        has_fasting_keyword = False
        for keyword in fasting_keywords:
            if keyword in context:
                has_fasting_keyword = True
                keyword_pos = context.find(keyword)
                number_pos_in_context = match.start() - start
                distance = abs(keyword_pos - number_pos_in_context)
                score += max(0, 1500 - (distance * 10))  # 10x multiplier!
        if not has_fasting_keyword:
            other_keywords = ['blood sugar', 'blood glucose', 'glucose', 'sugar', 'bs', 'glu', 'gluc']
            for keyword in other_keywords:
                if keyword in context:
                    keyword_pos = context.find(keyword)
                    number_pos_in_context = match.start() - start
                    distance = abs(keyword_pos - number_pos_in_context)
                    score += max(0, 100 - distance)
        if has_units:
            score += 100
        if has_fasting_keyword and keyword_found:
            keyword_pos = context.find(keyword_found)
            number_pos_in_context = match.start() - start
            if abs(keyword_pos - number_pos_in_context) < 30:
                score += 2000  # Massive boost for close fasting keywords!
        glucose_candidates.append((num, score, match.start()))
    if glucose_candidates:
        glucose_candidates.sort(key=lambda x: x[1], reverse=True)
        data['sugar'] = glucose_candidates[0][0]
    hba1c_keywords = [
        'hba1c', 'hb a1c', 'a1c', 'glycated hemoglobin', 'glycated haemoglobin',
        'glycosylated hemoglobin', 'glycosylated haemoglobin', 'hemoglobin a1c',
        'haemoglobin a1c', 'glycohemoglobin'
    ]
    hba1c_candidates = []
    for match in re.finditer(r'\b(\d{1,2}(?:\.\d{1,2})?)\b', text):
        num = float(match.group(1))
        if not (3.0 <= num <= 15.0):
            continue
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end]
        for keyword in hba1c_keywords:
            if keyword in context:
                hba1c_candidates.append((num, match.start()))
                break
    if hba1c_candidates:
        data['hba1c'] = hba1c_candidates[0][0]
    return data
@app.route('/upload-report', methods=['POST'])
def upload_report():
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "No file uploaded"
            }), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "success": False,
                "error": "No file selected"
            }), 400
        
        # SECURITY: Sanitize filename to prevent path traversal
        import secrets
        filename = file.filename
        # Remove path components and dangerous characters
        filename = os.path.basename(filename)
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        # Add random prefix to prevent overwrites
        safe_filename = f"{secrets.token_hex(8)}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(filepath)
        extracted_text = None
        file_ext = filename.lower().split('.')[-1]
        if file_ext == 'pdf':
            extracted_text = extract_text_from_pdf(filepath)
        elif file_ext in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
            extracted_text = extract_text_from_image(filepath)
        else:
            os.remove(filepath)
            return jsonify({
                "success": False,
                "error": "Unsupported file format. Use PDF or image files."
            }), 400
        os.remove(filepath)
        if not extracted_text:
            return jsonify({
                "success": False,
                "error": "Could not extract text from file"
            }), 400
        parsed_data = parse_medical_data(extracted_text)
        extracted_count = sum(1 for v in parsed_data.values() if v is not None)
        return jsonify({
            "success": True,
            "extracted_data": parsed_data,
            "extracted_count": extracted_count,
            "raw_text": extracted_text[:1000],  # First 1000 chars for debugging
            "message": f"Successfully extracted {extracted_count} field(s) from report",
            "debug_info": {
                "text_length": len(extracted_text),
                "has_fasting": "fasting" in extracted_text.lower(),
                "has_glucose": "glucose" in extracted_text.lower(),
                "has_sugar": "sugar" in extracted_text.lower()
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
@app.route('/predict', methods=['POST'])
def predict():
    try:
        if model is None:
            return jsonify({
                "error": "Model not loaded. Please run train_model.py first."
            }), 500
        data = request.get_json()
        
        # SECURITY: Validate input ranges to prevent malicious data
        try:
            age = float(data.get('age', 0))
            weight = float(data.get('weight', 0))
            sugar = float(data.get('sugar', 0))
            hba1c = float(data.get('hba1c', 0))
            
            # Validate reasonable ranges
            if not (1 <= age <= 120):
                return jsonify({"success": False, "error": "Invalid age"}), 400
            if not (20 <= weight <= 300):
                return jsonify({"success": False, "error": "Invalid weight"}), 400
            if not (40 <= sugar <= 500):
                return jsonify({"success": False, "error": "Invalid blood sugar"}), 400
            if not (3.0 <= hba1c <= 15.0):
                return jsonify({"success": False, "error": "Invalid HbA1c"}), 400
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid input format"}), 400
            
        lifestyle = data.get('lifestyle', 'moderate')
        lifestyle_map = {'sedentary': 0, 'moderate': 1, 'active': 2}
        lifestyle_encoded = lifestyle_map.get(lifestyle, 1)
        height = 1.65  # meters (assumed average)
        bmi = weight / (height ** 2)
        features = np.array([[age, bmi, sugar, hba1c, lifestyle_encoded]])
        prediction = model.predict(features)[0]
        probability = model.predict_proba(features)[0]
        risk_score = int(probability[1] * 100)
        if risk_score < 20:
            risk_level = 'Low'
            color = 'teal'
            message = "Excellent! Your metabolic health is optimal."
        elif risk_score < 40:
            risk_level = 'Low-Medium'
            color = 'green'
            message = "Good health status with minor areas for improvement."
        elif risk_score < 60:
            risk_level = 'Medium'
            color = 'yellow'
            message = "Pre-diabetic range detected. Lifestyle intervention critical."
        elif risk_score < 80:
            risk_level = 'Medium-High'
            color = 'orange'
            message = "High risk. Medical consultation strongly recommended."
        else:
            risk_level = 'High'
            color = 'rose'
            message = "Critical risk level. Immediate medical attention required."
        suggestions = generate_ai_suggestions(age, bmi, sugar, hba1c, lifestyle, risk_score)
        return jsonify({
            "success": True,
            "prediction": int(prediction),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "color": color,
            "message": message,
            "suggestion": suggestions,
            "confidence": float(max(probability)),
            "model_type": "Ensemble (Random Forest + XGBoost)",
            "bmi": round(bmi, 1),
            "bmi_category": get_bmi_category(bmi)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
def generate_ai_suggestions(age, bmi, sugar, hba1c, lifestyle, risk_score):
    suggestions = []
    if sugar < 70:
        suggestions.append("🚨 URGENT: Low blood sugar detected. Consume 15g fast-acting carbs immediately (juice, glucose tablets). Recheck in 15 minutes.")
    elif sugar < 100:
        suggestions.append("✅ Excellent fasting glucose! Maintain current diet and exercise habits.")
    elif sugar < 126:
        suggestions.append("⚠️ Pre-diabetic glucose level. Reduce refined carbs, increase fiber intake, and add 30 minutes of daily walking.")
    else:
        suggestions.append("🔴 Diabetic range glucose. Schedule immediate doctor visit. Start monitoring blood sugar 2x daily. Eliminate sugary beverages.")
    if hba1c < 5.7:
        suggestions.append("✅ Healthy HbA1c! Your 3-month average is excellent.")
    elif hba1c < 6.5:
        suggestions.append("⚠️ Pre-diabetic HbA1c. Target 5-7% weight loss if overweight. Exercise 150 mins/week. Consider Mediterranean diet.")
    else:
        suggestions.append("🔴 Diabetic HbA1c. Endocrinologist consultation essential. Daily glucose monitoring required. Medication likely needed.")
    if bmi > 30:
        suggestions.append(f"⚖️ BMI {bmi:.1f} (Obese). Target: Lose 1-2 lbs/week through 500 cal/day deficit. High-protein meals. Avoid liquid calories.")
    elif bmi > 25:
        suggestions.append(f"⚖️ BMI {bmi:.1f} (Overweight). Aim for 5-10% weight reduction. Portion control and food tracking recommended.")
    elif bmi >= 18.5:
        suggestions.append(f"✅ BMI {bmi:.1f} (Normal). Maintain current weight through balanced nutrition.")
    else:
        suggestions.append(f"⚠️ BMI {bmi:.1f} (Underweight). Consult nutritionist for healthy weight gain strategies.")
    if lifestyle == 'sedentary':
        suggestions.append("🏃 Increase activity: Start with 10-min post-meal walks. Gradually build to 30 mins daily. Take stairs, park farther away.")
    elif lifestyle == 'moderate':
        suggestions.append("💪 Good activity level! Add 2 days of strength training. Try interval walking (fast/slow alternating).")
    else:
        suggestions.append("🏆 Excellent activity level! Ensure adequate recovery. Monitor for exercise-induced hypoglycemia.")
    if age > 60:
        suggestions.append("👴 Age 60+: Annual comprehensive metabolic panel recommended. Focus on balance exercises to prevent falls. Vitamin D supplementation.")
    elif age > 45:
        suggestions.append("👨 Age 45+: Increase screening frequency. Focus on cardiovascular health. Stress management crucial.")
    if risk_score > 70:
        suggestions.append("🏥 HIGH RISK: Schedule appointment with endocrinologist within 1 week. Bring glucose log. Discuss medication options.")
    elif risk_score > 50:
        suggestions.append("📋 MEDIUM RISK: See primary care physician within 2 weeks. Request A1C recheck in 3 months. Start food diary.")
    else:
        suggestions.append("📅 LOW RISK: Annual checkup sufficient. Continue healthy habits. Recheck glucose yearly.")
    suggestions.append("🥗 Diet: Focus on non-starchy vegetables, lean proteins, healthy fats. Limit carbs to 45-60g per meal. Avoid white bread, pasta, rice.")
    if risk_score > 60:
        suggestions.append("📊 Monitoring: Check fasting glucose daily. Keep log. Watch for symptoms: excessive thirst, frequent urination, fatigue.")
    else:
        suggestions.append("📊 Monitoring: Check fasting glucose weekly. Annual HbA1c test. Stay aware of diabetes symptoms.")
    return " | ".join(suggestions)
def get_bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal"
    elif bmi < 30:
        return "Overweight"
    else:
        return "Obese"
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "model_loaded": model is not None
    })
if __name__ == '__main__':
    print("=" * 60)
    print("🏥 GlucoNova AI Backend Server")
    print("=" * 60)
    if model is None:
        print("⚠️  WARNING: Model not loaded!")
        print("📝 Please run: python train_model.py")
        print("=" * 60)
    else:
        print("✅ Model loaded successfully")
        print("🚀 Server starting on http://localhost:5000")
        print("=" * 60)
    
    # SECURITY: Disable debug mode for production
    import os
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='127.0.0.1', port=5000)
