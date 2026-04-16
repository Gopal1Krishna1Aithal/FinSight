import os
from dotenv import load_dotenv
from groq import Groq

def test_connection():
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY NOT FOUND in .env")
        return

    print(f"Testing Groq with key: {api_key[:10]}...")
    client = Groq(api_key=api_key)
    
    # Try multiple common models
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-8b-8192", "mixtral-8x7b-32768"]
    
    for model in models:
        try:
            print(f"--- Trying model: {model} ---")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10
            )
            print(f"✅ Success with {model}: {resp.choices[0].message.content}")
            return model
        except Exception as e:
            print(f"❌ Failed with {model}: {str(e)}")
            
    return None

if __name__ == "__main__":
    test_connection()
