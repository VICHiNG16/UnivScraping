import re
import timeit

NAMES = [
    "Ingineria Sistemelor (vezi detalii)",
    "Calculatoare [2026]",
    "  Informatica   Aplicata  ",
    "Drept (aici)",
    "Litere [IF]",
    "Teologie (link )",
    "Matematica",
    "Fizica [B]"
] * 1000 # 8000 names

def clean_name_old(name: str) -> str:
    if not name: return "Unknown"
    # Remove (aici), (detalii), etc
    name = re.sub(r'\(\s*(aici|detalii|vezi|link)\s*\)', '', name, flags=re.IGNORECASE)
    # Remove [Metadata]
    name = re.sub(r'\[.*?\]', '', name)
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name

CLEAN_PARENS_PATTERN = re.compile(r'\(\s*(aici|detalii|vezi|link)\s*\)', flags=re.IGNORECASE)
CLEAN_BRACKETS_PATTERN = re.compile(r'\[.*?\]')
CLEAN_SPACES_PATTERN = re.compile(r'\s+')

def clean_name_new(name: str) -> str:
    if not name: return "Unknown"
    name = CLEAN_PARENS_PATTERN.sub('', name)
    name = CLEAN_BRACKETS_PATTERN.sub('', name)
    name = CLEAN_SPACES_PATTERN.sub(' ', name).strip()
    return name

if __name__ == "__main__":
    print("Benchmarking _clean_name Regex Optimization...")
    
    def run_old():
        for n in NAMES: clean_name_old(n)
        
    def run_new():
        for n in NAMES: clean_name_new(n)
    
    t1 = timeit.timeit(run_old, number=10)
    print(f"Inside Loop: {t1:.4f}s")
    
    t2 = timeit.timeit(run_new, number=10)
    print(f"Pre-compiled: {t2:.4f}s")
    
    print(f"Speedup: {t1/t2:.2f}x")
