import re
import time
import timeit

URLS = [
    "https://ace.ucv.ro/admitere",
    "https://feaa.ucv.ro/admitere",
    "https://litere.ucv.ro/admitere",
    "http://drept.ucv.ro/admitere",
    "https://mec.ucv.ro/admitere",
] * 1000  # 5000 URLs

def loop_re_compile():
    count = 0
    for url in URLS:
        m = re.search(r'https?://([^.]+)\.ucv\.ro', url)
        if m: count += 1
    return count

FACULTY_URL_PATTERN = re.compile(r'https?://([^.]+)\.ucv\.ro')

def pre_compiled():
    count = 0
    for url in URLS:
        m = FACULTY_URL_PATTERN.search(url)
        if m: count += 1
    return count

if __name__ == "__main__":
    print("Benchmarking Regex Optimization...")
    
    t1 = timeit.timeit(loop_re_compile, number=10)
    print(f"Inside Loop: {t1:.4f}s")
    
    t2 = timeit.timeit(pre_compiled, number=10)
    print(f"Pre-compiled: {t2:.4f}s")
    
    print(f"Speedup: {t1/t2:.2f}x")
