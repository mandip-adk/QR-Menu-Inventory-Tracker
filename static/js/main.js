/**
 * Sajilo Pasal – Main JavaScript
 * Day 1 baseline. Feature modules are added on their respective days.
 */

"use strict";

/* ── CSRF helper (needed for HTMX / fetch POST requests) ── */
function getCsrfToken() {
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith("csrftoken="))
    ?.split("=")[1];
}

/* ── Auto-dismiss flash messages after 4 s ── */
document.addEventListener("DOMContentLoaded", () => {
  const alerts = document.querySelectorAll(".alert.alert-dismissible");
  alerts.forEach((el) => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    }, 4000);
  });
});

