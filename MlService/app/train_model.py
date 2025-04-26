import pandas as pd
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score

# Ścieżki
DATASET_PATH = 'MlService/data/dataset.csv'
MODEL_PATH = 'MlService/data/model/model.pkl'
REPORT_PATH = 'MlService/data/training_report/training_report.txt'

def load_dataset():
    print("🔵 Loading dataset...")
    df = pd.read_csv(DATASET_PATH)
    return df

def preprocess_data(df):
    print("🛠 Preprocessing data...")

    # Target
    y = df['home_win']

    # Features
    X = df.drop(columns=['home_win', 'league'], errors='ignore')  # Wywalamy home_win + ligę jeśli istnieje

    # Dodatkowe sanity check
    if X.isnull().values.any():
        print("⚠️ Warning: Missing values found in features. Dropping NA...")
        X = X.dropna()

    return X, y

def train_model(X_train, y_train):
    print("⚙️ Training model...")
    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=12,
        random_state=42,
        n_jobs=-1  # Wykorzystaj wszystkie rdzenie
    )
    model.fit(X_train, y_train)
    return model

def evaluate_model(model, X_test, y_test):
    print("📈 Evaluating model...")
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_prob)

    return accuracy, roc_auc

def save_model(model):
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    print(f"🟢 Model saved to {MODEL_PATH}")

def save_report(accuracy, roc_auc):
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, 'w') as f:
        f.write(f"Model Training Report\n")
        f.write(f"Accuracy: {accuracy:.4f}\n")
        f.write(f"ROC AUC: {roc_auc:.4f}\n")
    print(f"📝 Report saved to {REPORT_PATH}")

def pipeline():
    df = load_dataset()
    X, y = preprocess_data(df)

    # Jeśli X i y się nie zgadzają po czyszczeniu
    if len(X) != len(y):
        print("❌ Error: X and y lengths do not match after preprocessing.")
        return

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = train_model(X_train, y_train)

    accuracy, roc_auc = evaluate_model(model, X_test, y_test)

    save_model(model)
    save_report(accuracy, roc_auc)

    print(f"✅ Training complete! Accuracy: {accuracy:.4f}, ROC AUC: {roc_auc:.4f}")

if __name__ == "__main__":
    pipeline()
