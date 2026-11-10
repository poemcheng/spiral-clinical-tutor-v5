# CareLab v2 — Multimodal Synthetic Care Teaching Lab

A **public, open-source, synthetic-data-only** educational application for an interprofessional healthcare workshop. **Not medical software, not a medical device, and not validated for diagnosis, treatment, screening, or clinical decision making.**

## Online demonstration

The static demonstration is published inside the existing public GitHub Pages website for `poemcheng/spiral-clinical-tutor-v5` at `/carelab-v2/`. It intentionally does not send user input to an external model and does not require an API key.

- [GitHub Pages (when deployment succeeds)](https://poemcheng.github.io/spiral-clinical-tutor-v5/carelab-v2/)
- [Static page source](../web_portal/carelab-v2/)

## What works on GitHub Pages

- Three.js procedural 3D character; animated walking, lean and sit/stand illustrations; optional local VRM file, with 2D fallback if CDN is unavailable.
- Synthetic ECG-style trace, simulated HR, SpO2, BP, gait speed, plantar-pressure illustration and seven-day activity history.
- Three cases: baseline, absent SpO2 modality, and conflicting modalities.
- Rule-based interview with clearly attributed synthetic responses.
- Editable SBAR draft, transparent keyword-coverage practice scoring, and client-side JSON export.

## Architecture and limits

`web_portal/carelab-v2/` is the **self-contained static demo**. It uses the local `carelab-api.js` adapter and does not call a clinical inference API. Three.js and three-vrm are optionally loaded from a CDN. Browser speech recognition may be implemented by the browser provider; avoid any real or identifiable patient data.

`carelab-v2/backend/` contains the original **FastAPI reference server** and pytest cases for a controlled local setup. This is **not hosted by GitHub Pages**. Ollama / Gemini connectors require a separately operated, secured backend and additional data-protection review. No API keys are ever placed in the public site.

**Do not** use this site to make health assessments or upload real patient data. The words "ECG," "muscle," "gait," or "SBAR" in this app describe illustrative teaching content only.

## Local backend (optional)

```bash
cd carelab-v2/backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
uvicorn server:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. External-model connectors have not been deployed publicly.

## License

MIT License, copyright (c) 2026 CareLab contributors. Third-party libraries are subject to their own licenses. The content contains no clinical data.

## v3 interface and avatar refinement (2026-11-11)

The public teaching interface now uses a refined clinical dashboard, a purpose-built 3D staging environment, front/side/three-quarter camera controls, and an articulated procedural older-adult figure with detailed facial features, clothing, hands, elbows, knees, and animated gait / chair transfer. When the 3D libraries cannot be loaded, a detailed animated 2D illustration is shown instead of a stick figure. A matching AI-generated fictional character portrait is included at `web_portal/carelab-v2/assets/lin-portrait.webp`.

The default character remains a **stylized visualization**, not a photorealistic digital human, and no clinical biomechanics, human pose estimation or gait classification is implied. Users may load a separately licensed VRM asset using the file chooser to increase visual fidelity; check that asset's licence before redistributing it. No real patient data or medical claims are embedded in the character.

The frontend remains static and uses deterministic synthetic API responses. No external medical model is connected to GitHub Pages. For the most realistic avatar experience, provide a legally licensed VRM 1.0 adult/senior model and validate its skeleton and animations individually.