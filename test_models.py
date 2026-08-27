from groq import Groq
import os

# direct ga key pettachu testing kosam
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

models = client.models.list()

for m in models.data:
    print(m.id)