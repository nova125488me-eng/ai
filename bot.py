import os
from groq import Groq

print("--- در حال بررسی مدل‌های در دسترس اکانت شما ---")
try:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    models = client.models.list()
    for model in models.data:
        print(f"MODEL_ID: {model.id}")
except Exception as e:
    print(f"Error fetching models: {e}")
print("---------------------------------------------")
