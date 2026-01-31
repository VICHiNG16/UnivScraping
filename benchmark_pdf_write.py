import asyncio
import time
import os
import shutil
from pathlib import Path

# Try to import aiofiles
try:
    import aiofiles
except ImportError:
    aiofiles = None

DATA_DIR = Path("benchmark_pdf_data")
NUM_FILES = 100
FILE_SIZE = 1024 * 1024 # 1MB dummy PDF

# Create a 1MB dummy buffer
DUMMY_PDF = b'%PDF-1.4\n' + (b'0' * (FILE_SIZE - 20)) + b'\n%%EOF'

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
        with open(DATA_DIR / f"sync_{i}.pdf", "wb") as f:
            f.write(DUMMY_PDF)
    return time.time() - start

async def async_write_aiofiles():
    if not aiofiles: return 0
    start = time.time()
    tasks = []
    for i in range(NUM_FILES):
        tasks.append(_write_one(i))
    await asyncio.gather(*tasks)
    return time.time() - start

async def _write_one(i):
    async with aiofiles.open(DATA_DIR / f"async_{i}.pdf", "wb") as f:
        await f.write(DUMMY_PDF)

async def main():
    if not aiofiles:
        print("aiofiles not installed.")
        return

    print(f"Benchmarking write of {NUM_FILES} files ({FILE_SIZE/1024/1024} MB each)...")
    
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
