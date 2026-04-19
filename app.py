import os
import requests
import time
import sqlite3
from dotenv import load_dotenv
from tavily import TavilyClient
from init_db import setup_database  # Uvozimo tvoju funkciju za bazu

# --- CONFIGURATION ---
load_dotenv()
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")

tavily = TavilyClient(api_key=TAVILY_KEY)
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GOOGLE_KEY}"

def fetch_news(query):
    """Fetches news and filters out social media/video platforms."""
    print(f"🔍 Fetching textual sources for: {query}...")
    search = tavily.search(
        query=query, 
        search_depth="basic", 
        max_results=15, 
        exclude_domains=["youtube.com", "instagram.com", "reddit.com", "tiktok.com", "facebook.com", "vimeo.com", "twitter.com", "x.com"]
    )
    
    context = ""
    for r in search['results']:
        context += f"TITLE: {r['title']} | URL: {r['url']}\n"
    return context

def ask_gemini(news_content, query):
    """Filters and formats only high-quality textual links."""
    print("🧠 AI is filtering sources...")
    
    # Tražimo od AI-ja fiksni format 'Naslov | URL' kako bismo lakše spremili u bazu
    prompt_text = (
        f"You are a professional research librarian. Based on the data for '{query}':\n"
        f"1. Remove social media/videos.\n"
        f"2. Return ONLY a list of max 10 results.\n"
        f"3. FORMAT: Title | URL (use the pipe symbol to separate them).\n"
        f"No intros, no extra text.\n\nDATA:\n{news_content}"
    )
    
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
    response = requests.post(GEMINI_URL, json=payload)
    
    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    return f"AI Error: {response.status_code}"

def save_to_db(search_id, link_list_text):
    """Parsira tekst od Gemini-ja i sprema u SQLite bazu."""
    conn = sqlite3.connect("database/app.db")
    cursor = conn.cursor()
    
    lines = link_list_text.strip().split('\n')
    count = 0
    for line in lines:
        if "|" in line:
            # Čistimo od rednih brojeva ako ih AI doda (npr. "1. Title | URL")
            clean_line = line.split('.', 1)[-1] if '.' in line[:4] else line
            parts = clean_line.split("|")
            if len(parts) == 2:
                title = parts[0].strip()
                url = parts[1].strip()
                cursor.execute(
                    "INSERT INTO media_news (search_id, media_name, link) VALUES (?, ?, ?)",
                    (search_id, title, url)
                )
                count += 1
    
    conn.commit()
    conn.close()
    return count

def main():
    # Inicijalizacija baze pri pokretanju
    setup_database()
    
    user_query = input("Enter the topic for a text-only source list: ")
    
    # Generiramo isti ID za cijelu ovu pretragu
    current_search_id = int(time.time())
    
    try:
        news_data = fetch_news(user_query)
        if not news_data:
            print("No sources found.")
            return
            
        link_list = ask_gemini(news_data, user_query)
        
        # SPREMANJE U BAZU
        saved_count = save_to_db(current_search_id, link_list)
        
        print("\n" + "="*60)
        print(f" TEXT-ONLY SOURCES FOR: {user_query.upper()} (ID: {current_search_id}) ")
        print("="*60)
        print(link_list)
        print(f"\n✅ Successfully saved {saved_count} sources to database/app.db")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()