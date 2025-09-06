// Mobile-friendly camera control + analyze-on-click + upload fallback
document.addEventListener("DOMContentLoaded", () => {
  const video = document.getElementById("camera-feed");
  const startBtn = document.getElementById("start-camera");
  const analyzeBtn = document.getElementById("analyze-button");
  const uploadBtn = document.getElementById("upload-photo");
  const photoInput = document.getElementById("photo-input");
  const contextList = document.getElementById("context-list");

  // Optional inputs (add these to your HTML if you want):
  // <input id="city-input" placeholder="City (e.g., Austin, TX)">
  // <label><input id="attr-food_soiled" type="checkbox"> Food-soiled</label>
  // <label><input id="attr-film" type="checkbox"> Film plastic</label>
  // <label><input id="attr-rigid" type="checkbox" checked> Rigid plastic</label>
  // <label><input id="attr-black" type="checkbox"> Black plastic</label>
  // <label><input id="attr-wet" type="checkbox"> Wet</label>
  // <label><input id="attr-lined" type="checkbox"> Lined (e.g., paper cup)</label>
  // <label><input id="attr-foam" type="checkbox"> Foam / EPS</label>
  // <label><input id="attr-hazard" type="checkbox"> Hazard</label>
  const cityInput = document.getElementById("city-input");
  const attrIds = [
    "soft_bag",
    "foam",
    "paper_cup_or_carton",
    "greasy_or_wet",
    // "hazard" is optional to send; include if you want:
    "hazard"
  ];

  const attrEls = Object.fromEntries(attrIds.map(id => [id, document.getElementById(`attr-${id}`)]));

  // avoid duplicate bindings
  if (!analyzeBtn || analyzeBtn.dataset.bound === "true") return;
  analyzeBtn.dataset.bound = "true";

  let stream = null;
  let inFlight = false;
  const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

  function collectContext() {
    // city is case-insensitive; backend normalizes
    const city = cityInput?.value?.trim() || "default";
    const attrs = {};
    for (const [k, el] of Object.entries(attrEls)) {
      if (el && typeof el.checked === "boolean") attrs[k] = !!el.checked;
    }
    return { city, attrs };
  }

  async function startCamera() {
    const base = { width: { ideal: 1280 }, height: { ideal: 720 }, aspectRatio: { ideal: 16 / 9 } };
    const envStrict = { video: { facingMode: { exact: "environment" }, ...base } };
    const envLoose  = { video: { facingMode: "environment", ...base } };

    try {
      stream = await navigator.mediaDevices.getUserMedia(envStrict);
    } catch {
      try {
        stream = await navigator.mediaDevices.getUserMedia(envLoose);
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
      }
    }

    video.srcObject = stream;
    video.setAttribute("playsinline", "");
    video.muted = true;

    await new Promise((r) => {
      if (video.readyState >= 2) r();
      else video.addEventListener("loadedmetadata", r, { once: true });
    });
    try { await video.play(); } catch (_) {}

    analyzeBtn.disabled = false;
    startBtn.textContent = "Camera On";
    startBtn.disabled = true;

    window.addEventListener("beforeunload", () => stream?.getTracks().forEach(t => t.stop()));
  }

  startBtn?.addEventListener("click", async () => {
    try {
      await startCamera(); // HTTPS required on mobile (localhost is OK)
    } catch (e) {
      console.error("Camera error:", e);
      alert("Couldn’t open the camera. You can upload a photo instead.");
      uploadBtn?.focus();
    }
  });

  function grabFrameCanvas() {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    const track = stream?.getVideoTracks?.()[0];
    const s = track?.getSettings?.() || {};
    let w = s.width || video.videoWidth || 640;
    let h = s.height || video.videoHeight || 480;

    // portrait heuristic for phones
    const portraitScreen = isMobile && window.innerHeight > window.innerWidth;
    const needRotate = portraitScreen && w > h;

    if (needRotate) {
      canvas.width = h; canvas.height = w;
      ctx.save(); ctx.translate(h, 0); ctx.rotate(Math.PI / 2);
      ctx.drawImage(video, 0, 0, w, h); ctx.restore();
    } else {
      canvas.width = w; canvas.height = h;
      ctx.drawImage(video, 0, 0, w, h);
    }
    return canvas;
  }

  async function sendImagePayload(imageData) {
    const { city, attrs } = collectContext();
    const res = await fetch("/process_image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_data: imageData, city, attrs })
    });
    return res.json();
  }

  async function sendCanvas(canvas) {
    const imageData = canvas.toDataURL("image/jpeg");
    return sendImagePayload(imageData);
  }

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

  // Prefer backend-provided confidence_text; fallback to formatted percent
  function confidenceText(data) {
    if (data?.confidence_text) return data.confidence_text;
    const c = Number(data?.confidence);
    if (!Number.isNaN(c)) {
      const pct = c <= 1 ? c * 100 : c;
      return `${pct.toFixed(1)} % Confidence Score`;
    }
    return "—";
  }

  function renderResult(data) {
    // Support both old (label) and new (material/action) API fields
    const material = data.material ?? data.label ?? "Unknown";
    const action = data.action ?? "Unknown";
    const why = data.why ?? "";
    const tip = data.tip ?? "";
    const abstained = !!data.abstained;

    const li = document.createElement("li");
    li.className = `result-item ${abstained ? "result-item--abstained" : ""}`;
    li.innerHTML = `
      <div class="result-primary">
        <strong class="result-action">${esc(action)}</strong>
        <span class="dot">•</span>
        <span class="result-material">${esc(material)}</span>
      </div>
      <div class="result-meta">
        <span class="result-confidence">${esc(confidenceText(data))}</span>
      </div>
      ${why ? `<div class="result-why">${esc(why)}</div>` : ``}
      ${tip ? `<div class="result-tip">Tip: ${esc(tip)}</div>` : ``}
    `;
    contextList?.appendChild(li);
  }

  async function analyzeFromCamera() {
    if (!stream) { photoInput?.click(); return; }
    if (video.readyState < 2) {
      await new Promise(r => video.addEventListener("loadeddata", r, { once: true }));
    }
    const canvas = grabFrameCanvas();
    return sendCanvas(canvas);
  }

  // Button wire-up
  analyzeBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    if (inFlight) return;
    inFlight = true;
    const prev = analyzeBtn.textContent;
    analyzeBtn.textContent = "Analyzing…";
    analyzeBtn.disabled = true;

    try {
      const data = await analyzeFromCamera();
      if (data?.error) {
        console.error(data.error);
        alert("Error: " + data.error);
      } else {
        renderResult(data);
      }
    } catch (err) {
      console.error("Analyze error:", err);
      alert("Couldn’t analyze the image.");
    } finally {
      inFlight = false;
      analyzeBtn.textContent = prev;
      analyzeBtn.disabled = false;
    }
  });

  // Upload fallback
  uploadBtn?.addEventListener("click", () => photoInput?.click());
  photoInput?.addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const data = await sendImagePayload(reader.result);
        if (data?.error) {
          console.error(data.error);
          alert("Error: " + data.error);
        } else {
          renderResult(data);
        }
      } catch (err) {
        console.error("Upload processing error:", err);
        alert("Couldn’t process the uploaded photo.");
      } finally {
        photoInput.value = ""; // allow same file later
      }
    };
    reader.onerror = (err) => console.error("File read error:", err);
    reader.readAsDataURL(file);
  });
});

// Append a classification log to localStorage so Progress can read it
(function(){
  const LS_KEY = "recycloai_logs";
  function load(){ try { return JSON.parse(localStorage.getItem(LS_KEY)||"[]"); } catch { return []; } }
  function save(arr){ localStorage.setItem(LS_KEY, JSON.stringify(arr)); }

  window.saveClassification = function({ label, confidence, city }){
    const logs = load();
    logs.push({
      ts: Date.now(),
      label,                    // e.g., "Recyclable" / "Compost" / "Landfill" / "Other"
      confidence: Number(confidence) || null, // 0..1 or %
      city: city || document.getElementById("city-input")?.value || ""
    });
    // keep it tidy (last 10k)
    if (logs.length > 10000) logs.splice(0, logs.length - 10000);
    save(logs);
  };
})();

// Save a classification to the signed-in user's account
async function saveClassification({ label, confidence, city }) {
  try {
    await fetch("/api/logs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        label,
        confidence: (typeof confidence === "number" ? confidence : Number(confidence) || null),
        city: city || document.getElementById("city-input")?.value || ""
      })
    });
  } catch (e) {
    // Silently ignore if offline/not logged in
    console.warn("log save failed", e);
  }
}

/* Example: AFTER you compute a result, call:
saveClassification({
  label: result.label,           // "Recyclable" | "Compost" | "Landfill" | "Other"
  confidence: result.confidence, // optional number (0..1 or 0..100; we accept either)
  city: /* optional */ 



