/* Minimal tab switching for the markdown editor in the Django admin */
document.addEventListener("click", function (event) {
    var tab = event.target.closest(".gc-md-tab");
    if (!tab) {
        return;
    }
    var root = tab.closest(".gc-md-admin");
    root.querySelectorAll(".gc-md-tab").forEach(function (t) {
        var active = t === tab;
        t.classList.toggle("gc-md-tab-active", active);
        t.setAttribute("aria-selected", active ? "true" : "false");
        document.getElementById(t.dataset.gcMdTarget).hidden = !active;
    });
});
