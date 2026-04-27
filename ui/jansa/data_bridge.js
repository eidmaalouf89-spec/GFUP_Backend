/**
 * JANSA Data Bridge — replaces static data.js with live backend calls.
 *
 * Populates window.OVERVIEW, window.CONSULTANTS, window.CONTRACTORS,
 * window.CONTRACTORS_LIST, window.FICHE_DATA via pywebview API.
 *
 * Falls back to placeholder data if the backend is unavailable
 * (e.g. when opened directly in a browser without pywebview).
 */
(function () {
  "use strict";

  // ── Wait for pywebview API to be available ─────────────────────
  function waitForApi(timeout) {
    return new Promise(function (resolve, reject) {
      if (window.pywebview && window.pywebview.api) {
        return resolve(window.pywebview.api);
      }
      var elapsed = 0;
      var interval = setInterval(function () {
        elapsed += 50;
        if (window.pywebview && window.pywebview.api) {
          clearInterval(interval);
          resolve(window.pywebview.api);
        } else if (elapsed >= timeout) {
          clearInterval(interval);
          reject(new Error("pywebview API not available after " + timeout + "ms"));
        }
      }, 50);
    });
  }

  // ── Placeholder data (shown when backend is unavailable) ───────
  function _placeholderOverview() {
    return {
      week_num: 0, data_date_str: "— / — / —", run_number: 0, total_runs: 0,
      total_docs: 0, total_docs_delta: null,
      pending_blocking: 0, pending_blocking_delta: null,
      refus_rate: 0, refus_rate_delta: null,
      best_consultant: { name: "Not yet connected", slug: "", pass_rate: 0, delta: null },
      best_contractor: { code: "—", name: "Not yet connected", pass_rate: 0, delta: null },
      visa_flow: { submitted: 0, answered: 0, vso: 0, vao: 0, ref: 0, hm: 0, pending: 0, on_time: 0, late: 0 },
      weekly: [],
      focus: { focused: 0, p1_overdue: 0, p2_urgent: 0, p3_soon: 0, p4_ok: 0,
               total_dernier: 0, excluded: 0, stale: 0, resolved: 0, by_consultant: [] },
    };
  }

  function _placeholderConsultants() {
    return [];
  }

  // ── Bridge object ──────────────────────────────────────────────
  var bridge = {
    api: null,
    ready: false,
    error: null,
    _loadGen: 0,  // generation counter — prevents stale responses from overwriting globals

    /**
     * Initialize: wait for pywebview, load overview + consultants + contractors.
     * Populates window.OVERVIEW, window.CONSULTANTS, window.CONTRACTORS,
     * window.CONTRACTORS_LIST.
     * @param {boolean} focusMode
     * @param {number}  staleDays  stale-threshold in days (default 90)
     */
    init: async function (focusMode, staleDays) {
      try {
        bridge.api = await waitForApi(5000);
      } catch (e) {
        console.warn("[data_bridge] No pywebview API — using placeholders.", e.message);
        window.OVERVIEW = _placeholderOverview();
        window.CONSULTANTS = _placeholderConsultants();
        window.CONTRACTORS = {};
        window.CONTRACTORS_LIST = [];
        window.FICHE_DATA = null;
        bridge.error = "Backend not connected. Running in preview mode.";
        bridge.ready = true;
        return;
      }

      await bridge._loadCoreData(!!focusMode, staleDays != null ? staleDays : 90);
      bridge.ready = true;
    },

    /**
     * Reload core data when focus mode or stale threshold changes.
     * Returns only after window globals are updated (or skipped if superseded).
     * @param {boolean} focusMode
     * @param {number}  staleDays  stale-threshold in days (default 90)
     */
    refreshForFocus: async function (focusMode, staleDays) {
      if (!bridge.api) return;
      await bridge._loadCoreData(!!focusMode, staleDays != null ? staleDays : 90);
    },

    /**
     * Load fiche data for a specific consultant.
     * Populates window.FICHE_DATA.
     * @param {string}  consultantName
     * @param {boolean} focusMode
     * @param {number}  staleDays  stale-threshold in days (default 90)
     */
    loadFiche: async function (consultantName, focusMode, staleDays) {
      if (!bridge.api) {
        window.FICHE_DATA = null;
        return;
      }
      try {
        var result = await bridge.api.get_fiche_for_ui(consultantName, !!focusMode, staleDays != null ? staleDays : 90);
        if (result && !result.error) {
          window.FICHE_DATA = result;
        } else {
          console.error("[data_bridge] Fiche load error:", result && result.error);
          window.FICHE_DATA = null;
        }
      } catch (e) {
        console.error("[data_bridge] Fiche load exception:", e);
        window.FICHE_DATA = null;
      }
    },

    // ── Internal ──────────────────────────────────────────────────

    _loadCoreData: async function (focus, staleDays) {
      var api = bridge.api;
      var stale = staleDays != null ? staleDays : 90;
      var gen = ++bridge._loadGen;  // claim a generation number

      // Fire all three requests in parallel
      var results = await Promise.allSettled([
        api.get_overview_for_ui(focus, stale),
        api.get_consultants_for_ui(focus, stale),
        api.get_contractors_for_ui(focus, stale),
      ]);

      // If a newer _loadCoreData was launched while we were waiting, discard this result
      if (gen !== bridge._loadGen) {
        console.warn("[data_bridge] Discarding stale response (gen " + gen + ", current " + bridge._loadGen + ")");
        return;
      }

      // Overview
      var ov = results[0];
      if (ov.status === "fulfilled" && ov.value && !ov.value.error) {
        window.OVERVIEW = ov.value;
      } else {
        console.error("[data_bridge] Overview load failed:", ov.reason || (ov.value && ov.value.error));
        window.OVERVIEW = _placeholderOverview();
      }

      // Consultants
      var cs = results[1];
      if (cs.status === "fulfilled" && cs.value && !cs.value.error) {
        window.CONSULTANTS = Array.isArray(cs.value) ? cs.value : [];
      } else {
        console.error("[data_bridge] Consultants load failed:", cs.reason || (cs.value && cs.value.error));
        window.CONSULTANTS = _placeholderConsultants();
      }

      // Contractors
      var ct = results[2];
      if (ct.status === "fulfilled" && ct.value && !ct.value.error) {
        window.CONTRACTORS = ct.value.lookup || {};
        window.CONTRACTORS_LIST = ct.value.list || [];
      } else {
        console.error("[data_bridge] Contractors load failed:", ct.reason || (ct.value && ct.value.error));
        window.CONTRACTORS = {};
        window.CONTRACTORS_LIST = [];
      }
    },
  };

  window.jansaBridge = bridge;
})();
