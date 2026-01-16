
# 🌊 Project Lifeline: Lagos Command Center

![Project Status](https://img.shields.io/badge/Status-Operational-success)
![Gemini AI](https://img.shields.io/badge/Powered%20By-Google%20Gemini%202.0-blue)
![License](https://img.shields.io/badge/License-MIT-green)

**Project Lifeline** is an autonomous, AI-driven flood response system designed for the Lagos State Government. It transforms fragmented, real-time video surveillance into actionable intelligence, allowing decision-makers to track rising water levels, assess infrastructure risks, and dispatch assets with precision.

---

## 🚨 The Challenge
Lagos, a coastal megacity, faces perennial flooding that paralyzes transit and endangers lives. Emergency response is often reactive, relying on delayed reports rather than real-time data. 
**The missing link?** A system that *sees*, *understands*, and *recommends* action instantly.

## 🧠 The Solution
**Project Lifeline** acts as a central neural nervous system for flood management:
1.  **See**: Aggregates live feeds from traffic cameras, drones, and crowdsourced mobile uploads.
2.  **Think**: Uses **Google Gemini 2.0 Flash** (Vision Agent) to analyze water depth, identify submerged assets, and infer flood trends.
3.  **Act**: Automatically recommends the correct asset (Truck, Okada, or Canoe) and visualizes the crisis on a geospatial heatmap.

## ✨ Key Features
-   **inspector Mode**: Click any zone to verify AI reasoning with real-time video playback.
-   **Smart Asset Dispatch**: Knows when to send a truck vs. a canoe based on water depth (e.g., >60cm = Canoe).
-   **Temporal Analysis**: Detects if water is "RISING RAPIDLY" or "RECEDING" by analyzing rain intensity and source.
-   **Lagos-First Design**: Custom-built for the unique geography of Lekki, VI, Ikoyi, and Third Mainland Bridge.

---

## 🛠️ Technology Stack
-   **AI Core**: Google Gemini 2.0 Flash (Multimodal Vision Analysis)
-   **Backend**: Python (Flask) for API and Agent Orchestration
-   **Frontend**: HTML5, CSS3, JavaScript (Vanilla), Leaflet.js
-   **Video Processing**: yt-dlp, FFmpeg

## 🚀 Quick Start (For Judges)

### Prerequisites
- Python 3.8+
- [Google Gemini API Key](https://aistudio.google.com/) (free tier works)

### Step 1: Clone & Install
```bash
git clone https://github.com/Amethyst001/Project-Lifeline.git
cd Project-Lifeline
pip install -r requirements.txt
```

### Step 2: Set Your API Key
Copy the example environment file and add your key:
```bash
cp .env.example .env
```
Then edit `.env` and replace `your_api_key_here` with your actual key.

**Or set it directly:**
```powershell
# Windows (PowerShell)
$env:GOOGLE_API_KEY="your_api_key_here"
```
```bash
# Mac/Linux
export GOOGLE_API_KEY="your_api_key_here"
```

### Step 3: Run
```bash
python api_server.py
```
Then open `index.html` in your browser (double-click or drag into Chrome).

### Step 4: Test It!
1. Click any **zone marker** on the map (e.g., Lekki, VI)
2. The Inspector opens with a **real flood video** from that area
3. Click **"Live Analysis"** → Watch the AI analyze the video in real-time
4. See the stats update: Water Level, Asset Recommendation, Road Status
5. Try **"Override AI"** → Click status boxes to toggle manually

---

## 📁 Included Demo Videos
The `test_videos_merged/` folder contains real Lagos flood footage for each zone:
| Zone | Videos |
|------|--------|
| **Lekki** | `lekki_vgc_flood.mp4`, `lekki_downpour_flood.mp4`, `lekki_vi_houses_destroyed.mp4`, `ajah_flood.mp4` |
| **Victoria Island** | `vi_ahmadu_bello_way.mp4`, `vi_canoes_after_rain.mp4`, `vi_flooded_island_brt.mp4` |
| **Ikoyi** | `banana_island_drone.mp4`, `ikoyi_bourdillon_flood.mp4` |
| **Third Mainland** | `third_mainland_bridge_inspection.mp4`, `third_mainland_oworo_flooded.mp4`, `third_mainland_water_rises.mp4` |

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*"Built for Lagos, Scalable for the World."*
