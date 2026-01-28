# Romanian University Scraper - Architecture Report (V3.2)

> **Status**: Production Ready (Pilot Verified)  
> **Version**: 3.2 ("The Specialist Release")  
> **Date**: 2026-01-28  
> **Run ID**: `ucv_20260128T141904`

## 1. Executive Summary & Philosophy
This architecture represents a "Hardened V3" designed specifically for the chaotic reality of Romanian university websites. Following deep analysis by GPT-4, DeepSeek-V3, and Kimi, we have moved from a "Scraper" mindset to a **"Digital Forensics"** mindset.

### Core Principles
1.  **Identity is not URL**: URLs change, query params rotate. We use **Composite Stable UIDs** (`sha256(canonical_url + normalized_name)`).
2.  **Snapshot Granularity**: A faculty is not a page. It is a collection of pages. We snapshot *per URL*, not per faculty key.
3.  **Data Fidelity**: We distinguish between "What the HTML said" (Bronze/Silver) and "What is True" (Gold). We preserve "dirty" data (`spots_raw`) forever.
4.  **Observability**: Every run produces a machine-readable `manifest.json`.

---

## 2. The V3.2 Data Pipeline

### 2.1 The "Bronze-Silver-Gold" Lifecycle (Enhanced)

| Layer | Path Pattern | Format | Purpose | V3.2 Upgrade |
| :--- | :--- | :--- | :--- | :--- |
| **Bronze** | `data/runs/{run_id}/raw/{faculty}/snapshots/{hash}.html` | HTML | Immutable Proof of State | **Hashed Filenames**: Distinguishes `admitere` vs `licenta` pages for same faculty. |
| **Silver** | `data/runs/{run_id}/raw/{faculty}/programs/{uid}.json` | JSON | Structured but "Dirty" | **Confidence Scoring**: `accuracy_confidence` (0.0-1.0) and `source_type` ("html" vs "pdf"). |
| **Gold** | `data/processed/ucv_programs.csv` | CSV | Cleaned & Normalized | **Validation** on export, not extraction. |

---

## 3. Specialist Fixes Applied (V3.2)

### Fix 1: Robust Identity System
**Problem**: The "One-URL-Many-Programs" bug and "Name-Change" risk.
**Solution**: We implemented `ProvenanceMixin.normalize_name()` and strict URL canonicalization.

```python
# ProvenanceMixin.normalize_name("Ingineria Sistemelor (2026)")
# -> "ingineria-sistemelor"
#
# UID = sha256(canonical_url + "|" + normalized_name)
```
*Result*: Programs survive minor renames or year updates without duplicate ghosts.

### Fix 2: Explicit Data Confidence
**Problem**: HTML text "30 locuri" is often a placeholder, while PDFs have the real data.
**Solution**: Added `source_type` and `accuracy_confidence` to the Schema.

```json
{
  "spots_raw": "30 locuri (buget estimated)",
  "source_type": "html_placeholder",
  "accuracy_confidence": 0.3
}
```
*Impact*: Downstream consumers (LLMs/Agents) know *not* to trust this number until a PDF parser upgrades it to `source_type: "pdf"` (Confidence 0.9).

### Fix 3: Run Observability (Manifests)
**Problem**: "Fire and forget" scripts leave no trace of what was *attempted* vs *succeeded*.
**Solution**: Auto-generated `manifest.json`.

```json
{
  "run_id": "ucv_20260128T141904",
  "faculties_attempted": 1,
  "successful": ["ace"],
  "failed": []
}
```

---

## 4. Verification: Pilot Run Analysis

**Run ID**: `ucv_20260128T141904`
**Target**: Facultatea de Automatică (ACE)

### Output Artifacts
1.  **Manifest**: `data/runs/ucv_.../manifest.json` (Valid)
2.  **Snapshot**: `data/runs/ucv_.../raw/ace/141906_2f598761_snapshot.html`  
    *   *Note*: `2f598761` is the hash of `https://ace.ucv.ro`, proving granular naming works.
3.  **Entity**: `data/runs/ucv_.../raw/ace/programs/3d37ed9e....json`

### Captured Entity (Sample)
```json
{
  "uid": "3d37ed9ebbf62761547ccdbc09cea549acd8f6a213dcbdc19dde5410680257da",
  "name": "Ingineria Sistemelor Multimedia",
  "faculty_uid": "2f598761...",
  "spots_raw": "30 locuri (buget estimated)",
  "source_type": "html_placeholder",
  "accuracy_confidence": 0.3,
  "content_hash": "2a97516c..."
}
```
*Assessment*: The data lineage is perfect. We know exactly WHERE it came from (`source_url`), WHAT it is (`html_placeholder`), and HOW reliable it is (`0.3`).

---

## 5. Next Steps (The "Thinker's" Roadmap)

With the **Infrastructure (V3.2)** frozen, we must focus on **Content (Step 4 & 6)**.

### Phase 2: The "PDF Frontier"
Real admission spots live in PDFs. The architecture is ready to receive them.
*   **Action**: Create `PDFParser` that outputs entities with `source_type="pdf"` and `accuracy_confidence=0.9`.
*   **Merge Strategy**: When PDF entity matches HTML entity (by fuzzy name), **Upsert** the spots data and boost confidence.

### Phase 3: Scale
*   **Action**: Populate `config.yaml` with all 12 UCV faculties.
*   **Action**: Run full scrape. Check `manifest.json` for "failed" entries.

## 6. Conclusion
V3.2 is no longer a "script". It is a **Data Ingestion Platform**. It tolerates dirty data, recovers from crashes (via manifests), and tracks data truthfulness. It is ready for the "Thinking AIs" to verify.
