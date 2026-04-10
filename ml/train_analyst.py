import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
import joblib

# Load data
df = pd.read_csv("data/errors.csv")

# Convert text to features
vectorizer = CountVectorizer()
X = vectorizer.fit_transform(df["error_message"])

# Encode labels
le = LabelEncoder()
y = le.fit_transform(df["root_cause"])

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
model = XGBClassifier(use_label_encoder=False, eval_metric='mlogloss')
model.fit(X_train, y_train)

# Save model, vectorizer, and label encoder
joblib.dump(model, "ml/analyst_model.pkl")
joblib.dump(vectorizer, "ml/vectorizer.pkl")
joblib.dump(le, "ml/label_encoder.pkl")

print("Model trained and saved.")