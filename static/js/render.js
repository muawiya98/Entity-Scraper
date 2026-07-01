

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function badge(label, count) {
  const has = count > 0 ? "has" : "";
  return `<span class="badge ${has}">${esc(label)}: ${count}</span>`;
}

function detailList(items, isLink, linkPrefix) {
  if (!items || !items.length) return `<span class="muted">—</span>`;
  return `<ul>${items
    .map((i) => {
      if (isLink) {
        const href = (linkPrefix || "") + i;
        return `<li><a href="${esc(href)}">${esc(i)}</a></li>`;
      }
      return `<li>${esc(i)}</li>`;
    })
    .join("")}</ul>`;
}

function peopleTable(people) {
  if (!people || !people.length) return `<span class="muted">—</span>`;
  const rows = people
    .map((p) => {
      const contact = [p.email, p.phone].filter(Boolean).map(esc).join("<br>");
      const name = p.profile_url
        ? `<a href="${esc(p.profile_url)}" target="_blank" rel="noopener">${esc(p.name)}</a>`
        : esc(p.name);
      return `<tr><td><strong>${name}</strong></td><td>${esc(p.position) || "—"}</td><td>${contact || "—"}</td></tr>`;
    })
    .join("");
  return `<table class="people-table">
    <thead><tr><th>${t("col_name")}</th><th>${t("position")}</th><th>${t("col_contact")}</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

function socialLinks(social) {
  const keys = social ? Object.keys(social) : [];
  if (!keys.length) return `<span class="muted">—</span>`;
  return `<div class="social-links">${keys
    .map((k) => `<a href="${esc(social[k])}" target="_blank" rel="noopener">${esc(k)}</a>`)
    .join("")}</div>`;
}

function entityCard(entity, index) {
  const phones = entity.phones || [];
  const emails = entity.emails || [];
  const people = entity.people || [];
  const desc = entity.description ? `<p class="entity-desc">${esc(entity.description)}</p>` : "";

  return `
  <div class="entity" data-entity>
    <div class="entity-head" data-toggle>
      <div class="entity-rank">${index}</div>
      <div class="entity-main">
        <p class="entity-name">${esc(entity.name) || esc(entity.domain)}</p>
        <a class="entity-domain" href="${esc(entity.website)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${esc(entity.website)}</a>
        ${desc}
        <div class="entity-badges">
          ${badge(t("phones"), phones.length)}
          ${badge(t("emails"), emails.length)}
          ${badge(t("people"), people.length)}
        </div>
      </div>
      <div class="chevron">›</div>
    </div>
    <div class="entity-body">
      <div class="detail-grid">
        <div class="detail-block">
          <h4>${t("phones")}</h4>
          ${detailList(phones, true, "tel:")}
        </div>
        <div class="detail-block">
          <h4>${t("emails")}</h4>
          ${detailList(emails, true, "mailto:")}
        </div>
        <div class="detail-block">
          <h4>${t("address")}</h4>
          ${entity.address ? esc(entity.address) : '<span class="muted">—</span>'}
        </div>
        <div class="detail-block">
          <h4>${t("social")}</h4>
          ${socialLinks(entity.social)}
        </div>
      </div>
      <div class="detail-block" style="margin-top:18px">
        <h4>${t("people")}</h4>
        ${peopleTable(people)}
      </div>
    </div>
  </div>`;
}

function renderResults(container, entities, opts) {
  opts = opts || {};
  if (!entities || !entities.length) {
    container.innerHTML = `<div class="card"><div class="empty">${t("no_results")}</div></div>`;
    return;
  }
  const exportBtn = opts.searchId
    ? `<a class="btn btn-ghost btn-sm" href="/api/search/${opts.searchId}/export">${t("btn_export")}</a>`
    : "";
  const cards = entities.map((e, i) => entityCard(e, i + 1)).join("");
  container.innerHTML = `
    <div class="card">
      <div class="results-head">
        <h2>${t("results_title")} (${entities.length})</h2>
        ${exportBtn}
      </div>
      ${cards}
    </div>`;

  container.querySelectorAll("[data-toggle]").forEach((head) => {
    head.addEventListener("click", () => head.closest("[data-entity]").classList.toggle("open"));
  });
}
