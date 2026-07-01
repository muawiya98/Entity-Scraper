
(function () {
  const form = document.getElementById("search-form");
  if (!form) return;

  const submitBtn = document.getElementById("submit-btn");
  const submitLabel = submitBtn.querySelector("[data-i18n]");
  const maxRange = document.getElementById("max_results");
  const maxVal = document.getElementById("max_val");
  const progressCard = document.getElementById("progress-card");
  const progressFill = document.getElementById("progress-fill");
  const progressText = document.getElementById("progress-text");
  const resultsArea = document.getElementById("results-area");

  let currentEntities = [];
  let currentSearchId = null;
  let polling = null;

  maxRange.addEventListener("input", () => (maxVal.textContent = maxRange.value));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      query: document.getElementById("query").value.trim(),
      location: document.getElementById("location").value.trim(),
      entity_type: document.getElementById("entity_type").value.trim(),
      max_results: parseInt(maxRange.value, 10),
    };
    if (!payload.query) return;

    setBusy(true);
    resultsArea.innerHTML = "";
    progressCard.classList.add("show");
    setProgress(2, t("btn_searching"));

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");
      currentSearchId = data.search_id;
      poll(currentSearchId);
    } catch (err) {
      setProgress(0, "⚠ " + err.message);
      setBusy(false);
    }
  });

  function poll(id) {
    if (polling) clearInterval(polling);
    polling = setInterval(async () => {
      try {
        const res = await fetch(`/api/search/${id}/status`);
        const s = await res.json();
        setProgress(s.progress, s.message || t("status_" + s.status));
        if (s.status === "completed" || s.status === "failed") {
          clearInterval(polling);
          polling = null;
          setBusy(false);
          await loadResults(id);
        }
      } catch (err) {
        clearInterval(polling);
        polling = null;
        setBusy(false);
      }
    }, 1200);
  }

  async function loadResults(id) {
    const res = await fetch(`/api/search/${id}/results`);
    const data = await res.json();
    currentEntities = data.entities || [];
    renderResults(resultsArea, currentEntities, { searchId: id });
    if (currentEntities.length) {
      progressFill.style.width = "100%";
    }
  }

  function setProgress(pct, msg) {
    progressFill.style.width = Math.max(2, pct) + "%";
    progressText.textContent = msg || "";
  }

  function setBusy(busy) {
    submitBtn.disabled = busy;
    submitLabel.textContent = busy ? t("btn_searching") : t("btn_search");
    const spinner = document.querySelector("#progress-msg .spinner");
    if (spinner) spinner.style.display = busy ? "inline-block" : "none";
  }

  
  document.addEventListener("langchange", () => {
    if (currentEntities.length) {
      renderResults(resultsArea, currentEntities, { searchId: currentSearchId });
    }
  });
})();
