
import os
from bs4 import BeautifulSoup

def main():
    if not os.path.exists('data/runs'):
        print("No runs found.")
        return

    runs = sorted(os.listdir('data/runs'))
    latest = runs[-1]
    ace_dir = f'data/runs/{latest}/raw/ace'
    
    html_files = [f for f in os.listdir(ace_dir) if f.endswith('.html')]
    if not html_files:
        print(f"No HTML found in {ace_dir}")
        return
        
    html_file = html_files[0]
    print(f"Analyzing: {html_file}")
    
    content = open(os.path.join(ace_dir, html_file), 'r', encoding='utf-8').read()
    soup = BeautifulSoup(content, 'html.parser')
    
    print("\n--- Links Found ---")
    for a in soup.find_all('a'):
        href = a.get('href')
        text = a.text.strip()
        if href and (text or 'img' in str(a)):
            print(f"[{text}] -> {href}")

if __name__ == "__main__":
    main()
