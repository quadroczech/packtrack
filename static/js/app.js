/* PackTrack – main JS */

// Auto-dismiss flash messages after 4 s
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".alert.alert-success").forEach(function (el) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    }, 4000);
  });
});

// Confirm before destructive actions
document.querySelectorAll("[data-confirm]").forEach(function (el) {
  el.addEventListener("click", function (e) {
    if (!confirm(this.dataset.confirm)) e.preventDefault();
  });
});
