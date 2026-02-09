# 🌊 Project Lifeline: Lagos Command Center

**Project Lifeline** is an autonomous, AI-driven flood response system designed for the Lagos State Government. It transforms fragmented, real-time video surveillance into actionable intelligence, allowing decision-makers to track rising water levels, assess infrastructure risks, and dispatch assets with precision.

---

## 🚀 Live Demo
**Project Lifeline is deployed and ready for immediate review.**
Access the full command center here:
### [**👉 Launch Project Lifeline | Lagos Command Center**](https://project-lifeline-avhmahdserdre6df.southafricannorth-01.azurewebsites.net)

*(Note: The system is hosted on Azure. No installation required for judges.)*

---

## 🚨 The Challenge
Lagos, a coastal megacity, faces perennial flooding that paralyzes transit and endangers lives. Emergency response is often reactive, relying on delayed reports rather than real-time data. 

**The missing link?** A system that *sees*, *understands*, and *recommends* action instantly.

### The "Physics Hallucination" Gap
We tried building this with older models (Gemini 1.5 Pro, GPT-4), but they failed. They could identify "water," but they couldn't *measure* it. They would often hallucinate depth, guessing randomly between "wet road" and "flooded."
* **The Breakthrough:** Only **Gemini 3** had the spatial reasoning to use "Reference Objects" (like using a car tire as a ruler) to calculate accurate depth.

---

## 🧠 The Solution
Project Lifeline acts as a central neural nervous system for flood management:

* **See:** Aggregates live feeds from traffic cameras, drones, and crowdsourced mobile uploads.
* **Think:** Uses **Gemini 3 Flash's Spatial Reasoning** to calculate water depth based on physical reference objects (e.g., car tires), identify submerged assets, and infer flood trends.
* **Act:** Automatically recommends the correct asset (**Truck**, **Okada**, or **Canoe**) and visualizes the crisis on a geospatial heatmap.

---

## ✨ Key Features
* **Inspector Mode:** Click any zone to verify AI reasoning with real-time video playback.
* **Smart Asset Dispatch:** Knows when to send a truck vs. a canoe based on water depth logic (e.g., `depth > 60cm` = **Canoe**).
* **Temporal Analysis:** Detects if water is "RISING RAPIDLY" or "RECEDING" by analyzing rain intensity and source context.
* **Lagos-First Design:** Custom-built for the unique geography of Lekki, VI, Ikoyi, and Third Mainland Bridge.

---

## ⚙️ Configuration & Optimization

**Architecture Decision: Precision vs. Speed**
We tuned the Gemini 3 Flash agent to balance real-time performance with physical accuracy.

* **❌ Disabled `thinking_level="high"` (Deep Thinking):**
    * *Trade-off:* While powerful, the ~12-15s latency was unacceptable for emergency response.
    * *Result:* Maintained **sub-2s inference** times for instant feedback.

* **✅ Enabled High-Resolution Vision:**
    * *Trade-off:* We prioritized higher bandwidth video frames over raw speed.
    * *Why:* To execute **Physics-Based Logistics**, the model needs to see fine details—specifically the water line against a car's wheel arch or a pedestrian's knee.
    * *Result:* The agent can distinguish between "Wet Road" and "60cm Flood" without hallucinating, while still responding in real-time.

---

## 🛠️ Technology Stack
* **AI Core:** Google Gemini 3 Flash (Multimodal Vision + Reasoning)
* **Backend:** Python (Flask) for API and Agent Orchestration
* **Frontend:** HTML5, CSS3, JavaScript (Vanilla), Leaflet.js
* **Video Processing:** yt-dlp, FFmpeg
* **Deployment:** Microsoft Azure App Service

---

## 💻 Local Development (Optional)
If you wish to run the project locally for code inspection instead of using the Azure link:

### Prerequisites
* Python 3.8+
* Google Gemini API Key

### Step 1: Clone & Install
```bash
git clone https://github.com/Amethyst001/Project-Lifeline.git
cd Project-Lifeline
pip install -r requirements.txt
```

### Step 2: Set Your API Key

Copy the example environment file:

```bash
cp .env.example .env
```

Then edit `.env` and replace `your_api_key_here` with your actual key.

### Step 3: Run

```bash
python api_server.py
```

Then open `http://localhost:5000` in your browser.

---

## 📁 Included Demo Videos

The `test_videos_merged/` folder contains real Lagos flood footage for each zone:

* **Lekki:** `lekki_vgc_flood.mp4`, `lekki_downpour_flood.mp4`
* **Victoria Island:** `vi_ahmadu_bello_way.mp4`, `vi_flooded_island_brt.mp4`
* **Ikoyi:** `banana_island_drone.mp4`, `ikoyi_bourdillon_flood.mp4`
* **Third Mainland:** `third_mainland_bridge_inspection.mp4`, `third_mainland_water_rises.mp4`

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

> *"Built for Lagos, Scalable for the World."*
