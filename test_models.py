import os
from groq import Groq

# کلید خودت رو اینجا بگذار یا بگذار از متغیرهای محیطی بخونه
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

try:
    models = client.models.list()
    print("✅ مدل‌های در دسترس برای اکانت شما:")
    for model in models.data:
        print(f"- {model.id}")
except Exception as e:
    print(f"❌ خطا: {e}")
