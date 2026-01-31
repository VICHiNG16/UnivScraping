import asyncio
import time
import os
import shutil
from pathlib import Path

# Try to import aiofiles, handled in main if missing
try:
    import aiofiles
except ImportError:
    aiofiles = None

DATA_DIR = Path("benchmark_data")
NUM_FILES = 1000
CONTENT = '{"id": 1, "name": "Test Program", "description": "Benchmark content"}' * 10

def setup():
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir()

def cleanup():
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)

def sync_write():
    start = time.time()
    for i in range(NUM_FILES):
        with open(DATA_DIR / f"sync_{i}.json", "w", encoding="utf-8") as f:
            f.write(CONTENT)
    return time.time() - start

async def async_write_aiofiles():
    if not aiofiles:
        return 0
    start = time.time()
    tasks = []
    for i in range(NUM_FILES):
        tasks.append(_write_one(i))
    await asyncio.gather(*tasks)
    return time.time() - start

async def _write_one(i):
    async with aiofiles.open(DATA_DIR / f"async_{i}.json", "w", encoding="utf-8") as f:
        await f.write(CONTENT)

async def main():
    if not aiofiles:
        print("aiofiles not installed. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "aiofiles"])
        print("Please rerun benchmark.")
        return

    print(f"Benchmarking write of {NUM_FILES} files...")
    
    setup()
    t_sync = sync_write()
    print(f"Sync Write: {t_sync:.4f}s")
    
    setup()
    t_async = await async_write_aiofiles()
    print(f"Async Write: {t_async:.4f}s")
    
    if t_async > 0:
        print(f"Speedup: {t_sync/t_async:.2f}x")
    
    cleanup()

if __name__ == "__main__":
    asyncio.run(main())
