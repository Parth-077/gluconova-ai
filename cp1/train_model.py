import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import pickle
import warnings
warnings.filterwarnings('ignore')
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("⚠️  XGBoost not installed. Using Random Forest only.")
    print("💡 For best accuracy, install: pip install xgboost")
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
def create_synthetic_pima_data():
    np.random.seed(42)
    n_samples = 1000
    data = {
        'Age': np.random.randint(21, 81, n_samples),
        'BMI': np.random.normal(32, 7, n_samples),
        'Glucose': np.random.normal(120, 30, n_samples),
        'HbA1c': np.random.normal(5.7, 1.2, n_samples),
        'Lifestyle': np.random.randint(0, 3, n_samples)  # 0=sedentary, 1=moderate, 2=active
    }
    df = pd.DataFrame(data)
    df['BMI'] = df['BMI'].clip(15, 60)
    df['Glucose'] = df['Glucose'].clip(50, 200)
    df['HbA1c'] = df['HbA1c'].clip(4.0, 12.0)
    df['Diabetes'] = 0
    df.loc[(df['Glucose'] > 126) | (df['HbA1c'] >= 6.5), 'Diabetes'] = 1
    df.loc[(df['BMI'] > 35) & (df['Glucose'] > 110), 'Diabetes'] = 1
    df.loc[(df['Age'] > 60) & (df['HbA1c'] > 6.0), 'Diabetes'] = 1
    medium_risk = (df['Glucose'] > 100) & (df['Glucose'] <= 126) & (df['HbA1c'] > 5.7) & (df['HbA1c'] < 6.5)
    df.loc[medium_risk & (np.random.random(n_samples) > 0.6), 'Diabetes'] = 1
    lifestyle_mask = (df['Lifestyle'] == 0) & (df['BMI'] > 30)
    lifestyle_indices = df[lifestyle_mask].index
    df.loc[lifestyle_indices, 'Diabetes'] = (np.random.random(len(lifestyle_indices)) > 0.7).astype(int)
    return df
def train_ensemble_model():
    print("=" * 70)
    print("🏥 GlucoNova AI - Model Training")
    print("=" * 70)
    print("\n📊 Loading dataset...")
    df = create_synthetic_pima_data()
    print(f"✅ Dataset loaded: {len(df)} samples")
    print(f"   Diabetes cases: {df['Diabetes'].sum()} ({df['Diabetes'].mean()*100:.1f}%)")
    print(f"   Healthy cases: {(1-df['Diabetes']).sum()} ({(1-df['Diabetes'].mean())*100:.1f}%)")
    X = df[['Age', 'BMI', 'Glucose', 'HbA1c', 'Lifestyle']]
    y = df['Diabetes']
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print("\n⚙️  Preprocessing data...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    print("\n🤖 Training ensemble model...")
    models = []
    lr = LogisticRegression(random_state=42, max_iter=1000)
    models.append(('lr', lr))
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )
    models.append(('rf', rf))
    if XGBOOST_AVAILABLE:
        xgb = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            eval_metric='logloss'
        )
        models.append(('xgb', xgb))
    ensemble = VotingClassifier(
        estimators=models,
        voting='soft'
    )
    ensemble.fit(X_train_scaled, y_train)
    print("\n📈 Evaluating model...")
    y_pred = ensemble.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n{'='*70}")
    print(f"🎯 Model Performance")
    print(f"{'='*70}")
    print(f"Accuracy: {accuracy*100:.2f}%")
    print(f"\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Healthy', 'Diabetes']))
    print(f"\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"                Predicted")
    print(f"              Healthy  Diabetes")
    print(f"Actual Healthy    {cm[0][0]:3d}      {cm[0][1]:3d}")
    print(f"       Diabetes   {cm[1][0]:3d}      {cm[1][1]:3d}")
    print(f"\n🔄 Cross-validation (5-fold)...")
    cv_scores = cross_val_score(ensemble, X_train_scaled, y_train, cv=5)
    print(f"CV Accuracy: {cv_scores.mean()*100:.2f}% (+/- {cv_scores.std()*100:.2f}%)")
    pipeline = ModelPipeline(scaler, ensemble)
    print(f"\n💾 Saving model...")
    with open('diabetes_model.pkl', 'wb') as f:
        pickle.dump(pipeline, f)
    print(f"✅ Model saved as 'diabetes_model.pkl'")
    print(f"\n{'='*70}")
    print(f"🎉 Training complete! You can now run: python app.py")
    print(f"{'='*70}\n")
    return pipeline, accuracy
if __name__ == '__main__':
    model, accuracy = train_ensemble_model()
    print("\n🧪 Testing prediction...")
    test_data = np.array([[45, 28.5, 95, 5.4, 1]])  # Healthy profile
    prediction = model.predict(test_data)
    probability = model.predict_proba(test_data)
    print(f"Test input: Age=45, BMI=28.5, Glucose=95, HbA1c=5.4, Lifestyle=Moderate")
    print(f"Prediction: {'Diabetes' if prediction[0] == 1 else 'Healthy'}")
    print(f"Confidence: {max(probability[0])*100:.1f}%")
