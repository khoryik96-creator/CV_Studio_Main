(() => {
  "use strict";

  const app = document.getElementById("salaryApp");
  const notice = document.getElementById("globalNotice");
  const calculateButton = document.getElementById("calculateButton");
  const resetButton = document.getElementById("resetButton");
  const rulesButton = document.getElementById("rulesButton");
  const exportPdfButton = document.getElementById("exportPdfButton");
  const exportWordButton = document.getElementById("exportWordButton");
  const rulesModal = document.getElementById("rulesModal");
  const previewRuleButton = document.getElementById("previewRuleButton");
  const publishRuleButton = document.getElementById("publishRuleButton");
  const ruleNotice = document.getElementById("ruleNotice");
  const proposal = document.getElementById("ruleProposal");
  const proposalJson = document.getElementById("ruleProposalJson");
  const ruleUsage = document.getElementById("ruleUsage");
  let config = null;
  let pendingRule = null;
  let calculationTimer = null;
  let calculationSequence = 0;
  let calculationController = null;

  const apiUrl = (path) => new URL(path, window.location.href).toString();
  const el = (id) => document.getElementById(id);

  function setNotice(message, type = "error") {
    notice.textContent = message;
    notice.className = `notice${type === "success" ? " success" : ""}`;
    notice.hidden = !message;
  }

  function setRuleNotice(message, type = "error") {
    ruleNotice.textContent = message;
    ruleNotice.className = `notice${type === "success" ? " success" : ""}`;
    ruleNotice.hidden = !message;
  }

  async function requestJson(path, options = {}) {
    const response = await fetch(apiUrl(path), {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || body.detail || `Request failed (${response.status})`);
    return body;
  }

  function filenameFromDisposition(response, fallback) {
    const disposition = response.headers.get("Content-Disposition") || "";
    const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8) return decodeURIComponent(utf8[1].replace(/["']/g, ""));
    const plain = disposition.match(/filename="?([^";]+)"?/i);
    return plain ? plain[1] : fallback;
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function countryCurrency(country) {
    return config?.countries.find((item) => item.country === country)?.currency || "";
  }

  function setOptions(select, items, selected) {
    select.innerHTML = "";
    for (const item of items) {
      const option = document.createElement("option");
      const value = typeof item === "string" || typeof item === "number" ? item : item.value;
      const label = typeof item === "string" || typeof item === "number" ? item : item.label;
      option.value = String(value);
      option.textContent = String(label);
      if (String(value) === String(selected)) option.selected = true;
      select.appendChild(option);
    }
  }

  function populateYear(prefix, preferred) {
    const country = el(`${prefix}_country`).value;
    const known = config.years_by_country[country] || [];
    const current = new Date().getFullYear();
    const years = [...new Set([...known, current, current - 1, current + 1])].sort((a, b) => b - a);
    const target = years.includes(Number(preferred)) ? preferred : known[0] || current;
    setOptions(el(`${prefix}_tax_year`), years, target);
  }

  function updateLocalCurrency(prefix) {
    const currency = countryCurrency(el(`${prefix}_country`).value);
    el(`${prefix}_local_currency`).textContent = currency || "No mapping";
  }

  function initializeSelectors() {
    const countryNames = config.countries.map((item) => item.country);
    const currencies = [...new Set(config.countries.map((item) => item.currency))].sort();
    for (const prefix of ["a", "b"]) {
      setOptions(el(`${prefix}_country`), countryNames, prefix === "a" ? "Malaysia" : "Singapore");
      setOptions(el(`${prefix}_residency`), config.residency_profiles, "Resident");
      setOptions(el(`${prefix}_reporting_currency`), currencies, "MYR");
      populateYear(prefix, 2025);
      updateLocalCurrency(prefix);
    }
    setOptions(el("rule_country"), countryNames, "Malaysia");
  }

  function numberValue(id, scale = 1) {
    const raw = el(id).value.trim();
    if (raw === "") return null;
    const value = Number(raw) * scale;
    if (!Number.isFinite(value)) throw new Error(`Enter a valid finite number for ${id.replaceAll("_", " ")}.`);
    return value;
  }

  function scenarioPayload(prefix) {
    return {
      name: el(`${prefix}_name`).value.trim(),
      country: el(`${prefix}_country`).value,
      tax_year: Number(el(`${prefix}_tax_year`).value),
      residency: el(`${prefix}_residency`).value,
      monthly_base: numberValue(`${prefix}_monthly_base`) ?? 0,
      monthly_fixed_allowance: numberValue(`${prefix}_monthly_fixed_allowance`) ?? 0,
      guaranteed_bonus_months: numberValue(`${prefix}_guaranteed_bonus_months`) ?? 0,
      sign_on_bonus: numberValue(`${prefix}_sign_on_bonus`) ?? 0,
      variable_bonus_mode: el(`${prefix}_variable_bonus_mode`).value,
      variable_bonus_pct: el(`${prefix}_variable_bonus_mode`).value === "percentage"
        ? (numberValue(`${prefix}_variable_bonus_value`, 0.01) ?? 0)
        : 0,
      variable_bonus_months: el(`${prefix}_variable_bonus_mode`).value === "months"
        ? (numberValue(`${prefix}_variable_bonus_value`) ?? 0)
        : 0,
      other_taxable_income: numberValue(`${prefix}_other_taxable_income`) ?? 0,
      personal_tax_reliefs: numberValue(`${prefix}_personal_tax_reliefs`) ?? 0,
      employee_contribution_rate_override: numberValue(`${prefix}_employee_contribution_rate_override`, 0.01),
      employer_contribution_rate_override: numberValue(`${prefix}_employer_contribution_rate_override`, 0.01),
      contribution_cap_override: numberValue(`${prefix}_contribution_cap_override`),
      include_bonus_in_contribution_base: el(`${prefix}_include_bonus_in_contribution_base`).value === "true",
      other_after_tax_deductions: numberValue(`${prefix}_other_after_tax_deductions`) ?? 0,
      reporting_currency: el(`${prefix}_reporting_currency`).value,
      fx_rate_override: numberValue(`${prefix}_fx_rate_override`),
    };
  }

  function formatMoney(value, currency) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency,
        maximumFractionDigits: currency === "IDR" || currency === "VND" || currency === "JPY" ? 0 : 2,
      }).format(Number(value));
    } catch {
      return `${currency} ${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    }
  }

  function formatRate(value) {
    return `${(Number(value || 0) * 100).toFixed(1)}%`;
  }

  function renderScenario(prefix, result, fxMeta) {
    const container = el(`${prefix}_results`);
    container.querySelectorAll("[data-key]").forEach((node) => {
      const value = result[node.dataset.key];
      node.textContent = node.dataset.format === "rate"
        ? formatRate(value)
        : formatMoney(value, result.local_currency);
    });
    const status = el(`${prefix}_status`);
    const taxVerified = Boolean(result.rule_metadata.tax_brackets_verified);
    const contributionVerified = Boolean(result.rule_metadata.contribution_rule_verified);
    if (taxVerified && contributionVerified) {
      status.textContent = "Verified rule";
      status.className = "status-pill ready";
    } else if (taxVerified) {
      status.textContent = "Tax verified · contribution review";
      status.className = "status-pill neutral";
    } else {
      status.textContent = "Review rule";
      status.className = "status-pill neutral";
    }
    const source = fxMeta.source === "identity" ? "Same currency" : (fxMeta.cached ? "Cached reference rate" : "Reference rate");
    const stale = fxMeta.stale ? " · service unavailable; cached rate retained" : "";
    el(`${prefix}_fx_note`).textContent = `${source}: 1 ${result.local_currency} = ${result.fx_rate} ${result.reporting_currency}${stale}`;
  }

  function renderSummary(data) {
    const comparison = data.comparison;
    el("summaryCurrency").textContent = comparison.reporting_currency;
    el("summaryNetDifference").textContent = formatMoney(comparison.net_annual_difference, comparison.reporting_currency);
    el("summaryEmployerDifference").textContent = formatMoney(comparison.employer_cost_difference, comparison.reporting_currency);
    el("summaryUplift").textContent = formatRate(comparison.net_uplift_rate);
    el("analysisCurrency").textContent = comparison.reporting_currency;
    renderBars(data.scenario_a, data.scenario_b);
    el("analysisPanel").hidden = false;
  }

  function renderBars(a, b) {
    const metrics = [
      ["Gross annual cash", a.gross_annual_cash * a.fx_rate, b.gross_annual_cash * b.fx_rate],
      ["Net annual cash", a.net_annual_reporting, b.net_annual_reporting],
      ["Total Gross plus Employer EPF", a.employer_cost_reporting, b.employer_cost_reporting],
    ];
    const max = Math.max(1, ...metrics.flatMap(([, av, bv]) => [Math.abs(av), Math.abs(bv)]));
    const currency = a.reporting_currency;
    el("comparisonBars").innerHTML = metrics.map(([label, av, bv]) => `
      <div class="bar-group">
        <div class="bar-label">${label}</div>
        <div class="bar-lanes">
          <div class="bar-line a${av < 0 ? " negative" : ""}"><span>Scenario A</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(1, Math.abs(av) / max * 100)}%"></div></div><strong class="bar-value">${formatMoney(av, currency)}</strong></div>
          <div class="bar-line b${bv < 0 ? " negative" : ""}"><span>Scenario B</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(1, Math.abs(bv) / max * 100)}%"></div></div><strong class="bar-value">${formatMoney(bv, currency)}</strong></div>
        </div>
      </div>
    `).join("");
  }

  function clearCalculatedDisplay() {
    for (const prefix of ["a", "b"]) {
      const container = el(`${prefix}_results`);
      container.querySelectorAll("[data-key]").forEach((node) => { node.textContent = "—"; });
      el(`${prefix}_fx_note`).textContent = "Calculation unavailable until the issue above is fixed.";
      const status = el(`${prefix}_status`);
      status.textContent = "Needs attention";
      status.className = "status-pill error";
    }
    el("analysisPanel").hidden = true;
  }

  async function calculate() {
    const sequence = ++calculationSequence;
    if (calculationController) calculationController.abort();
    calculationController = new AbortController();
    setNotice("");
    const reportingA = el("a_reporting_currency").value;
    const reportingB = el("b_reporting_currency").value;
    if (reportingA !== reportingB) {
      el("b_reporting_currency").value = reportingA;
    }
    app.classList.add("loading");
    calculateButton.textContent = "Calculating…";
    try {
      const data = await requestJson("api/compare", {
        method: "POST",
        signal: calculationController.signal,
        body: JSON.stringify({ scenario_a: scenarioPayload("a"), scenario_b: scenarioPayload("b") }),
      });
      if (sequence !== calculationSequence) return;
      renderScenario("a", data.scenario_a, data.fx.scenario_a);
      renderScenario("b", data.scenario_b, data.fx.scenario_b);
      renderSummary(data);
    } catch (error) {
      if (error.name === "AbortError" || sequence !== calculationSequence) return;
      setNotice(error.message);
      clearCalculatedDisplay();
    } finally {
      if (sequence === calculationSequence) {
        calculationController = null;
        app.classList.remove("loading");
        calculateButton.textContent = "Calculate comparison";
      }
    }
  }

  async function exportReport(format) {
    setNotice("");
    const reportingA = el("a_reporting_currency").value;
    if (el("b_reporting_currency").value !== reportingA) {
      el("b_reporting_currency").value = reportingA;
    }
    const button = format === "pdf" ? exportPdfButton : exportWordButton;
    const originalText = button.textContent;
    exportPdfButton.disabled = true;
    exportWordButton.disabled = true;
    button.textContent = format === "pdf" ? "Preparing PDF…" : "Preparing Word…";
    try {
      const response = await fetch(apiUrl(`api/export/${format}`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_a: scenarioPayload("a"), scenario_b: scenarioPayload("b") }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || `Export failed (${response.status})`);
      }
      const extension = format === "pdf" ? "pdf" : "docx";
      const blob = await response.blob();
      const filename = filenameFromDisposition(response, `salary-comparison.${extension}`);
      downloadBlob(blob, filename);
      setNotice(`${format === "pdf" ? "PDF" : "Word"} report exported successfully.`, "success");
    } catch (error) {
      setNotice(error.message);
    } finally {
      exportPdfButton.disabled = false;
      exportWordButton.disabled = false;
      button.textContent = originalText;
    }
  }

  function updateVariableBonusControl(prefix, resetValue = false) {
    const mode = el(`${prefix}_variable_bonus_mode`).value;
    const input = el(`${prefix}_variable_bonus_value`);
    const suffix = el(`${prefix}_variable_bonus_suffix`);
    if (mode === "months") {
      suffix.textContent = "months";
      input.max = "24";
      input.step = "0.1";
      if (resetValue) input.value = "1";
    } else {
      suffix.textContent = "%";
      input.max = "100";
      input.step = "0.1";
      if (resetValue) input.value = "10";
    }
  }

  function scheduleCalculation() {
    clearTimeout(calculationTimer);
    calculationTimer = setTimeout(calculate, 650);
  }

  function bindScenario(prefix) {
    el(`${prefix}_variable_bonus_mode`).addEventListener("change", () => {
      updateVariableBonusControl(prefix, true);
      scheduleCalculation();
    });
    el(`${prefix}_country`).addEventListener("change", () => {
      updateLocalCurrency(prefix);
      populateYear(prefix);
      scheduleCalculation();
    });
    el(`${prefix}_reporting_currency`).addEventListener("change", () => {
      const other = prefix === "a" ? "b" : "a";
      el(`${other}_reporting_currency`).value = el(`${prefix}_reporting_currency`).value;
      scheduleCalculation();
    });
    document.querySelectorAll(`[id^="${prefix}_"]`).forEach((node) => {
      if (![`${prefix}_country`, `${prefix}_reporting_currency`].includes(node.id)) {
        node.addEventListener("input", scheduleCalculation);
        node.addEventListener("change", scheduleCalculation);
      }
    });
  }

  function resetSamples() {
    const sample = {
      a: { country: "Malaysia", base: 12000, allowance: 500, reliefs: 9000, name: "Current role" },
      b: { country: "Singapore", base: 9000, allowance: 600, reliefs: 0, name: "Overseas offer" },
    };
    for (const prefix of ["a", "b"]) {
      const values = sample[prefix];
      el(`${prefix}_name`).value = values.name;
      el(`${prefix}_country`).value = values.country;
      populateYear(prefix, 2025);
      el(`${prefix}_residency`).value = "Resident";
      el(`${prefix}_monthly_base`).value = values.base;
      el(`${prefix}_monthly_fixed_allowance`).value = values.allowance;
      el(`${prefix}_guaranteed_bonus_months`).value = 1;
      el(`${prefix}_sign_on_bonus`).value = 0;
      el(`${prefix}_variable_bonus_mode`).value = "percentage";
      el(`${prefix}_variable_bonus_value`).value = 10;
      updateVariableBonusControl(prefix);
      el(`${prefix}_other_taxable_income`).value = 0;
      el(`${prefix}_personal_tax_reliefs`).value = values.reliefs;
      el(`${prefix}_other_after_tax_deductions`).value = 0;
      el(`${prefix}_employee_contribution_rate_override`).value = "";
      el(`${prefix}_employer_contribution_rate_override`).value = "";
      el(`${prefix}_contribution_cap_override`).value = "";
      el(`${prefix}_include_bonus_in_contribution_base`).value = "true";
      el(`${prefix}_reporting_currency`).value = "MYR";
      el(`${prefix}_fx_rate_override`).value = "";
      updateLocalCurrency(prefix);
    }
    calculate();
  }

  function adminHeaders() {
    const token = el("rule_admin_token").value.trim();
    return token ? { "X-Salary-Admin-Token": token } : {};
  }

  async function previewRule() {
    setRuleNotice("");
    pendingRule = null;
    publishRuleButton.disabled = true;
    previewRuleButton.disabled = true;
    previewRuleButton.textContent = "Reading official sources…";
    try {
      const data = await requestJson("api/rules/preview", {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({
          provider: el("rule_provider").value,
          model: el("rule_model").value.trim(),
          api_key: el("rule_api_key").value.trim(),
          country: el("rule_country").value,
          tax_year: Number(el("rule_tax_year").value),
          residency: el("rule_residency").value,
          tax_url: el("rule_tax_url").value.trim(),
          contribution_url: el("rule_contribution_url").value.trim(),
        }),
      });
      pendingRule = data.rule;
      proposalJson.textContent = JSON.stringify(data.rule, null, 2);
      ruleUsage.textContent = `${data.provider} · ${data.model} · ${data.usage.input_tokens} input / ${data.usage.output_tokens} output tokens`;
      proposal.hidden = false;
      publishRuleButton.disabled = false;
      setRuleNotice("Proposal validated. Review every bracket and contribution assumption before publishing.", "success");
    } catch (error) {
      setRuleNotice(error.message);
    } finally {
      previewRuleButton.disabled = false;
      previewRuleButton.textContent = "Preview update";
      el("rule_api_key").value = "";
    }
  }

  async function publishRule() {
    if (!pendingRule) return;
    publishRuleButton.disabled = true;
    try {
      await requestJson("api/rules/publish", {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({ rule: pendingRule }),
      });
      setRuleNotice("Rule published. Reloading available tax years…", "success");
      config = await requestJson("api/config");
      for (const prefix of ["a", "b"]) populateYear(prefix, el(`${prefix}_tax_year`).value);
      pendingRule = null;
      publishRuleButton.disabled = true;
      setTimeout(() => rulesModal.close(), 800);
      calculate();
    } catch (error) {
      setRuleNotice(error.message);
      publishRuleButton.disabled = false;
    }
  }

  async function initialize() {
    try {
      config = await requestJson("api/config");
      initializeSelectors();
      bindScenario("a");
      bindScenario("b");
      updateVariableBonusControl("a");
      updateVariableBonusControl("b");
      calculateButton.addEventListener("click", calculate);
      resetButton.addEventListener("click", resetSamples);
      exportPdfButton.addEventListener("click", () => exportReport("pdf"));
      exportWordButton.addEventListener("click", () => exportReport("word"));
      rulesButton.addEventListener("click", () => rulesModal.showModal());
      previewRuleButton.addEventListener("click", previewRule);
      publishRuleButton.addEventListener("click", publishRule);
      calculate();
    } catch (error) {
      setNotice(`Unable to initialize Salary Comparison: ${error.message}`);
    }
  }

  initialize();
})();
