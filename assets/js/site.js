/* ============================================================
   Hassium — theme toggle and image lightbox
   ============================================================ */

(function () {
    "use strict";

    var root = document.documentElement;
    var toggle = document.querySelector("[data-theme-toggle]");
    var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

    function currentTheme() {
        return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
    }

    function syncToggle() {
        if (!toggle) return;
        var dark = currentTheme() === "dark";
        toggle.setAttribute("aria-pressed", String(dark));
        toggle.setAttribute(
            "aria-label",
            dark ? "Switch to light theme" : "Switch to dark theme"
        );
        toggle.title = dark ? "Switch to light theme" : "Switch to dark theme";
    }

    if (toggle) {
        syncToggle();
        toggle.addEventListener("click", function () {
            var next = currentTheme() === "dark" ? "light" : "dark";
            root.setAttribute("data-theme", next);
            try {
                localStorage.setItem("hassium-theme", next);
            } catch (error) {
                /* Private mode: the choice simply will not persist. */
            }
            syncToggle();
        });
    }

    if (media) {
        var onSchemeChange = function (event) {
            var stored = null;
            try {
                stored = localStorage.getItem("hassium-theme");
            } catch (error) {
                stored = null;
            }
            if (stored === "light" || stored === "dark") return;
            root.setAttribute("data-theme", event.matches ? "dark" : "light");
            syncToggle();
        };

        if (typeof media.addEventListener === "function") {
            media.addEventListener("change", onSchemeChange);
        } else if (typeof media.addListener === "function") {
            media.addListener(onSchemeChange);
        }
    }

    /* ---------- Lightbox ---------- */

    var triggers = Array.prototype.slice.call(document.querySelectorAll("[data-lightbox]"));
    var dialog = null;
    var dialogImage = null;
    var dialogCaption = null;
    var lastTrigger = null;

    function buildDialog() {
        dialog = document.createElement("dialog");
        dialog.className = "lightbox";
        dialog.setAttribute("aria-label", "Enlarged image");

        var inner = document.createElement("div");
        inner.className = "lightbox-inner";

        var bar = document.createElement("div");
        bar.className = "lightbox-bar";

        dialogCaption = document.createElement("span");
        dialogCaption.className = "lightbox-caption";

        var close = document.createElement("button");
        close.type = "button";
        close.className = "lightbox-close";
        close.setAttribute("aria-label", "Close image");
        close.innerHTML =
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';

        bar.appendChild(dialogCaption);
        bar.appendChild(close);

        dialogImage = document.createElement("img");
        dialogImage.alt = "";

        inner.appendChild(bar);
        inner.appendChild(dialogImage);
        dialog.appendChild(inner);
        document.body.appendChild(dialog);

        close.addEventListener("click", function () {
            dialog.close();
        });

        dialog.addEventListener("click", function (event) {
            if (event.target === dialog) dialog.close();
        });

        dialog.addEventListener("close", function () {
            if (lastTrigger) lastTrigger.focus();
            lastTrigger = null;
        });
    }

    if (triggers.length && typeof HTMLDialogElement !== "undefined") {
        triggers.forEach(function (trigger) {
            trigger.addEventListener("click", function (event) {
                var src = trigger.getAttribute("href");
                var caption = trigger.getAttribute("data-caption") || "";
                if (!src) return;

                event.preventDefault();
                if (!dialog) buildDialog();

                dialogImage.src = src;
                dialogImage.alt = caption;
                dialogCaption.textContent = caption;
                lastTrigger = trigger;

                if (typeof dialog.showModal === "function") {
                    dialog.showModal();
                } else {
                    dialog.setAttribute("open", "");
                }
            });
        });
    }

    /* ---------- Current year ---------- */

    var year = document.querySelector("[data-year]");
    if (year) year.textContent = String(new Date().getFullYear());
})();
