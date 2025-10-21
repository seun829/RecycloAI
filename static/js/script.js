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
  // <label><input id="attr-soft_bag" type="checkbox"> Film plastic (soft bag)</label>
  // <label><input id="attr-foam" type="checkbox"> Foam / EPS</label>
  // <label><input id="attr-paper_cup" type="checkbox"> Paper cup</label>
  // <label><input id="attr-carton" type="checkbox"> Carton (milk/juice)</label>
  // <label><input id="attr-greasy_or_wet" type="checkbox"> Food-soiled / wet</label>
  // <label><input id="attr-hazard" type="checkbox"> Hazard</label>
  const cityInput = document.getElementById("city-input");
  const attrIds = [
    "soft_bag",
    "foam",
    "paper_cup",
    "carton",
    "greasy_or_wet",
    // "hazard" is optional to send; include if you want:
    "hazard",
  ];
  const attrEls = Object.fromEntries(
    attrIds.map((id) => [id, document.getElementById(`attr-${id}`)])
  );

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
    startBtn && (startBtn.textContent = "Camera On");
    startBtn && (startBtn.disabled = true);

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

  // Resize & convert any image File to a JPEG data URL
  async function fileToJpegDataURL(file, { maxDim = 1600, quality = 0.85 } = {}) {
    // Prefer createImageBitmap for speed & orientation handling where supported
    let bitmap;
    try {
      bitmap = await createImageBitmap(file);
    } catch {
      // Fallback: load via <img>
      const url = URL.createObjectURL(file);
      try {
        bitmap = await new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve(img);
          img.onerror = reject;
          img.src = url;
        });
      } finally {
        URL.revokeObjectURL(url);
      }
    }

    const { width: w0, height: h0 } = bitmap;
    const scale = Math.min(1, maxDim / Math.max(w0, h0));
    const w = Math.round(w0 * scale);
    const h = Math.round(h0 * scale);

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(bitmap, 0, 0, w, h);

    // Produce JPEG; keeps payload small and avoids HEIC/PNG backend issues
    return canvas.toDataURL("image/jpeg", quality);
  }

  // POST JSON and surface non-JSON errors (like 413/415) nicely
  async function postJson(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });

    const status = res.status;
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { error: text || res.statusText || "Unknown error" }; }

    if (!res.ok) {
      let hint = "";
      if (status === 413) hint = " (image too large — try a smaller photo)";
      if (status === 415) hint = " (unsupported format — JPEG should fix)";
      if (!data.error) data.error = `HTTP ${status}${hint}`;
      else data.error += hint;
    }
    return data;
  }

  async function sendImagePayload(imageData) {
    const { city, attrs } = collectContext();
    return postJson("/process_image", { image_data: imageData, city, attrs });
  }

  async function sendCanvas(canvas) {
    const imageData = canvas.toDataURL("image/jpeg", 0.85);
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
      } else if (data) {
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

  // Upload fallback (resize + JPEG convert + friendly errors)
  photoInput?.addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const prev = analyzeBtn.textContent;
    analyzeBtn.textContent = "Uploading…";
    analyzeBtn.disabled = true;

    try {
      const dataUrl = await fileToJpegDataURL(file, { maxDim: 1600, quality: 0.85 });
      const data = await sendImagePayload(dataUrl);
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
      analyzeBtn.textContent = prev;
      analyzeBtn.disabled = false;
    }
  });

  uploadBtn?.addEventListener("click", () => photoInput?.click());
});

/* --- Classification logging (local + server) ---------------------------------

Call after you compute a result to persist it locally and to your backend:

saveClassification({
  label: result.label,            // "Recyclable" | "Compost" | "Landfill" | "Other"
  confidence: result.confidence,  // optional number (0..1 or 0..100; either is accepted)
  city: document.getElementById("city-input")?.value || "default"
});

----------------------------------------------------------------------------- */

// Unified saveClassification: append to localStorage and POST to /api/logs
async function saveClassification({ label, confidence, city }) {
  // Normalize confidence
  const confNum = (typeof confidence === "number" ? confidence : Number(confidence));
  const normalized = Number.isFinite(confNum) ? confNum : null;

  // LocalStorage log (keeps last 10k)
  const LS_KEY = "recycloai_logs";
  function load(){ try { return JSON.parse(localStorage.getItem(LS_KEY)||"[]"); } catch { return []; } }
  function save(arr){ localStorage.setItem(LS_KEY, JSON.stringify(arr)); }
  try {
    const logs = load();
    logs.push({
      ts: Date.now(),
      label,                                  // e.g., "Recyclable" / "Compost" / "Landfill" / "Other"
      confidence: normalized,                 // 0..1 or 0..100
      city: city || document.getElementById("city-input")?.value || ""
    });
    if (logs.length > 10000) logs.splice(0, logs.length - 10000);
    save(logs);
  } catch (e) {
    console.warn("local log save failed", e);
  }

  // Remote log (silent failure OK)
  try {
    await fetch("/api/logs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        label,
        confidence: normalized,
        city: city || document.getElementById("city-input")?.value || ""
      })
    });
  } catch (e) {
    console.warn("remote log save failed", e);
  }
}

// --- Persist <details> open/close state for Tips ---
(function(){
  const details = document.querySelector('details#tips-container[data-pref]');
  if (!details) return;

  const key = 'recycloai:' + details.dataset.pref;

  // Restore
  try {
    const saved = localStorage.getItem(key);
    if (saved === 'open') details.setAttribute('open', '');
    if (saved === 'closed') details.removeAttribute('open');
  } catch(e){ /* storage may be blocked; ignore */ }

  // Save on toggle
  details.addEventListener('toggle', () => {
    try {
      localStorage.setItem(key, details.open ? 'open' : 'closed');
    } catch(e){ /* ignore */ }
  });
})();
