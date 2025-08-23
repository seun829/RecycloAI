// Mobile-friendly camera control + analyze-on-click + upload fallback
document.addEventListener("DOMContentLoaded", () => {
  const video = document.getElementById("camera-feed");
  const startBtn = document.getElementById("start-camera");
  const analyzeBtn = document.getElementById("analyze-button");
  const uploadBtn = document.getElementById("upload-photo");
  const photoInput = document.getElementById("photo-input");
  const contextList = document.getElementById("context-list");

  // avoid duplicate bindings
  if (analyzeBtn.dataset.bound === "true") return;
  analyzeBtn.dataset.bound = "true";

  let stream = null;
  let inFlight = false;
  const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

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

  startBtn.addEventListener("click", async () => {
    try {
      // HTTPS required on mobile (localhost is OK)
      await startCamera();
    } catch (e) {
      console.error("Camera error:", e);
      alert("Couldn’t open the camera. You can upload a photo instead.");
      uploadBtn.focus();
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

  async function sendCanvas(canvas) {
    const imageData = canvas.toDataURL("image/jpeg");
    const res = await fetch("/process_image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_data: imageData })
    });
    return res.json();
  }

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

  // NEW: prefer backend-provided confidence_text; fallback to formatted percent certain
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
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="result-label">${esc(data.label ?? "Unknown")}</span>
      <span class="result-confidence"> - ${esc(confidenceText(data))}</span>
      ${data.tip ? `<span class="result-tip">Tip: ${esc(data.tip)}</span>` : ``}
    `;
    contextList.appendChild(li);
  }

  analyzeBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    if (inFlight) return;
    inFlight = true;
    try {
      if (!stream) { photoInput.click(); return; }
      if (video.readyState < 2) {
        await new Promise(r => video.addEventListener("loadeddata", r, { once: true }));
      }
      const canvas = grabFrameCanvas();
      const data = await sendCanvas(canvas);
      if (data?.error) { console.error(data.error); return; }
      renderResult(data);
    } catch (err) {
      console.error("Analyze error:", err);
    } finally {
      inFlight = false;
    }
  });

  // upload fallback
  uploadBtn.addEventListener("click", () => photoInput.click());
  photoInput.addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const res = await fetch("/process_image", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_data: reader.result })
        });
        const data = await res.json();
        if (data?.error) { console.error(data.error); return; }
        renderResult(data);
      } catch (err) {
        console.error("Upload processing error:", err);
      } finally {
        photoInput.value = ""; // allow same file later
      }
    };
    reader.onerror = (err) => console.error("File read error:", err);
    reader.readAsDataURL(file);
  });
});
