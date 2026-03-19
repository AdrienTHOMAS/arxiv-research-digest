/* ArXiv Research Digest — Client-side JS */

(function () {
    "use strict";

    // ── Theme toggle with localStorage ──────────────────────
    var THEME_KEY = "arxiv-digest-theme";

    function getStoredTheme() {
        try {
            return localStorage.getItem(THEME_KEY);
        } catch (_e) {
            return null;
        }
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        var icon = document.querySelector(".theme-icon");
        if (icon) {
            icon.textContent = theme === "dark" ? "\u263E" : "\u2600";
        }
    }

    function initTheme() {
        var stored = getStoredTheme();
        var theme = stored || "dark";
        applyTheme(theme);

        var toggle = document.getElementById("theme-toggle");
        if (toggle) {
            toggle.addEventListener("click", function () {
                var current = document.documentElement.getAttribute("data-theme") || "dark";
                var next = current === "dark" ? "light" : "dark";
                applyTheme(next);
                try {
                    localStorage.setItem(THEME_KEY, next);
                } catch (_e) {
                    // localStorage unavailable
                }
            });
        }
    }

    // ── Markdown rendering (digest summary) ─────────────────
    // Uses marked.js for parsing and DOMPurify for XSS protection
    function renderMarkdown() {
        var el = document.getElementById("summary-content");
        if (!el || typeof marked === "undefined") return;

        var raw = el.getAttribute("data-markdown");
        if (raw) {
            var rendered = marked.parse(raw);
            if (typeof DOMPurify !== "undefined") {
                rendered = DOMPurify.sanitize(rendered);
            }
            // Safe: content is sanitized by DOMPurify before insertion
            el.textContent = "";
            var wrapper = document.createElement("div");
            wrapper.className = "markdown-rendered";
            // Use DOMParser to safely insert sanitized HTML
            var parser = new DOMParser();
            var doc = parser.parseFromString(rendered, "text/html");
            while (doc.body.firstChild) {
                wrapper.appendChild(doc.body.firstChild);
            }
            el.appendChild(wrapper);
        }
    }

    // ── Paper filter form (progressive enhancement) ─────────
    function initFilters() {
        var form = document.getElementById("paper-filters");
        if (!form) return;

        form.addEventListener("submit", function (e) {
            e.preventDefault();

            var params = new URLSearchParams();
            var topic = document.getElementById("filter-topic").value;
            var minScore = document.getElementById("filter-min-score").value;
            var pageSize = document.getElementById("filter-page-size").value;

            if (topic) params.set("topic_id", topic);
            if (minScore) params.set("min_score", minScore);
            if (pageSize) params.set("page_size", pageSize);
            params.set("page", "1");

            window.location.href = "/papers?" + params.toString();
        });
    }

    // ── Init ────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", function () {
        initTheme();
        renderMarkdown();
        initFilters();
    });
})();
