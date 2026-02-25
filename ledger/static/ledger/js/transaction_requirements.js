
(function () {
  const form = document.getElementById("transaction-form");
  if (!form) return;

  const urlTemplate = form.dataset.requirementsUrlTemplate; // ends with /0/requirements/
  const subSel = document.getElementById("id_subcategory");
  const transportSel = document.getElementById("id_transport_type");
  const vehicleSel = document.getElementById("id_vehicle");
  const contactSel = document.getElementById("id_contact");
  const invoiceInput = document.getElementById("id_invoice_number");
  const clearInvoiceBtn = document.getElementById("clearInvoiceBtn");

  const badge = document.getElementById("requirementsBadge");
  const list = document.getElementById("requirementsList");
  const hintsEl = document.getElementById("requirementsHints");

  const transportWrap = document.getElementById("transportWrap");
  const vehicleWrap = document.getElementById("vehicleWrap");
  const contactWrap = document.getElementById("contactWrap");

  const transportReq = document.getElementById("transportReq");
  const vehicleReq = document.getElementById("vehicleReq");
  const contactReq = document.getElementById("contactReq");

  let currentRules = null;

  function buildUrl(pk) {
    // Replace "/0/" with "/<pk>/"
    return urlTemplate.replace("/0/", `/${pk}/`);
  }

  function setBadge(text, tone) {
    badge.textContent = text;
    badge.className = "badge";
    if (tone === "ok") badge.classList.add("bg-success");
    else if (tone === "warn") badge.classList.add("bg-warning", "text-dark");
    else badge.classList.add("bg-secondary");
  }

  function liFor(key) {
    return list ? list.querySelector(`li[data-key="${key}"]`) : null;
  }

  function markRequired(key, required) {
    const li = liFor(key);
    if (!li) return;
    li.style.display = required ? "" : "none";
  }

  function isFilled(el) {
    if (!el) return false;
    const v = (el.value || "").trim();
    return !!v;
  }

  function renderHints(hints) {
    if (!hintsEl) return;
    if (!hints || !hints.length) {
      hintsEl.textContent = "";
      return;
    }
    hintsEl.innerHTML = hints.map(h => `<div>• ${escapeHtml(h)}</div>`).join("");
  }

  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function applyVisibility() {
    if (!currentRules) {
      // Hide conditional wrappers until subcategory selected
      transportWrap && (transportWrap.style.display = "none");
      vehicleWrap && (vehicleWrap.style.display = "none");
      contactWrap && (contactWrap.style.display = "none");
      return;
    }

    const requires = currentRules.requires || {};
    const vehicleRule = currentRules.vehicle_rule || "none";

    // Contact
    if (contactWrap) contactWrap.style.display = requires.contact ? "" : "none";
    if (contactReq) contactReq.classList.toggle("d-none", !requires.contact);

    // Transport
    if (transportWrap) transportWrap.style.display = requires.transport ? "" : "none";
    if (transportReq) transportReq.classList.toggle("d-none", !requires.transport);

    // Vehicle
    const t = (transportSel?.value || "").trim();
    let showVehicle = false;
    if (vehicleRule === "business_vehicle") showVehicle = (t === "business_vehicle");
    if (vehicleRule === "always") showVehicle = true;

    if (vehicleWrap) vehicleWrap.style.display = showVehicle ? "" : "none";
    if (vehicleReq) {
      const req = (vehicleRule === "always") || (vehicleRule === "business_vehicle" && t === "business_vehicle");
      vehicleReq.classList.toggle("d-none", !req);
    }

    // If we hid vehicle, clear it to prevent invalid combos
    if (!showVehicle && vehicleSel) vehicleSel.value = "";
  }

  function updateChecklistAndBadge() {
    if (!currentRules) {
      setBadge("Select a Sub-Category", "neutral");
      return;
    }

    const requires = currentRules.requires || {};
    // Show/hide items
    markRequired("description", true);
    markRequired("amount", true);
    markRequired("date", true);
    markRequired("contact", !!requires.contact);
    markRequired("transport", !!requires.transport);

    // Vehicle checklist item should appear if rule is always OR transport is business_vehicle
    const vehicleRule = currentRules.vehicle_rule || "none";
    const t = (transportSel?.value || "").trim();
    const vehicleReqNow = (vehicleRule === "always") || (vehicleRule === "business_vehicle" && t === "business_vehicle");
    markRequired("vehicle", vehicleReqNow);

    // Determine missing count (best-effort UI, server remains source of truth)
    let missing = 0;
    // description
    const desc = document.getElementById("id_description");
    if (!isFilled(desc)) missing++;
    const amt = document.getElementById("id_amount");
    if (!isFilled(amt)) missing++;
    const date = document.getElementById("id_date");
    if (!isFilled(date)) missing++;

    if (requires.contact && !isFilled(contactSel)) missing++;
    if (requires.transport && !isFilled(transportSel)) missing++;
    if (vehicleReqNow && !isFilled(vehicleSel)) missing++;

    if (missing === 0) setBadge("All set", "ok");
    else setBadge(`${missing} missing`, "warn");
  }

  async function fetchRules(pk) {
    const url = buildUrl(pk);
    const resp = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!resp.ok) throw new Error(`Failed: ${resp.status}`);
    return await resp.json();
  }

  async function onSubcategoryChange() {
    const pk = (subSel?.value || "").trim();
    currentRules = null;

    if (!pk) {
      applyVisibility();
      updateChecklistAndBadge();
      renderHints([]);
      return;
    }

    try {
      currentRules = await fetchRules(pk);
      // extend checklist with keys if needed
      // add list items dynamically if missing (contact/transport/vehicle)
      if (list) {
        ["contact", "transport", "vehicle"].forEach((k) => {
          if (!liFor(k)) {
            const li = document.createElement("li");
            li.dataset.key = k;
            li.textContent = k.charAt(0).toUpperCase() + k.slice(1);
            list.appendChild(li);
          }
        });
      }

      renderHints(currentRules.hints || []);
      applyVisibility();
      updateChecklistAndBadge();
    } catch (e) {
      setBadge("Helper unavailable", "neutral");
      renderHints(["Could not load requirements. You can still save; server-side validation will guide you."]);
      // fall back: show transport so user can proceed
      if (transportWrap) transportWrap.style.display = "";
    }
  }

  function onTransportChange() {
    applyVisibility();
    updateChecklistAndBadge();
  }

  function onAnyInputChange() {
    updateChecklistAndBadge();
  }

  if (subSel) subSel.addEventListener("change", onSubcategoryChange);
  if (transportSel) transportSel.addEventListener("change", onTransportChange);

  // update badge as user types
  ["id_description", "id_amount", "id_date"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", onAnyInputChange);
  });
  if (contactSel) contactSel.addEventListener("change", onAnyInputChange);
  if (vehicleSel) vehicleSel.addEventListener("change", onAnyInputChange);

  // Clear invoice button
  if (clearInvoiceBtn && invoiceInput) {
    const syncClearState = () => {
      const has = (invoiceInput.value || "").trim().length > 0;
      clearInvoiceBtn.disabled = !has;
    };
    clearInvoiceBtn.addEventListener("click", () => {
      invoiceInput.value = "";
      invoiceInput.focus();
      syncClearState();
    });
    invoiceInput.addEventListener("input", syncClearState);
    syncClearState();
  }

  // Initial load
  onSubcategoryChange();
  onTransportChange();
  onAnyInputChange();
})();
