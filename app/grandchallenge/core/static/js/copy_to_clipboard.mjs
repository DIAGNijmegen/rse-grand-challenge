const activeTimers = {};
const originalTitles = {};

function showTooltip(btn, id, message) {
    const tooltip = bootstrap.Tooltip.getOrCreateInstance(btn);

    tooltip.setContent({ ".tooltip-inner": message });
    tooltip.show();

    activeTimers[id] = setTimeout(() => {
        tooltip.hide();
        tooltip.setContent({ ".tooltip-inner": originalTitles[id] });
    }, 2000);
}

document.addEventListener("click", e => {
    const btn = e.target.closest(".copy-btn");
    if (!btn) return;

    const id = btn.dataset.copy;

    if (!originalTitles[id]) {
        originalTitles[id] =
            btn.getAttribute("data-bs-original-title") || btn.title;
    }
    clearTimeout(activeTimers[id]);

    navigator.clipboard
        .writeText(id)
        .then(() => showTooltip(btn, id, "Copied to clipboard!"))
        .catch(() => showTooltip(btn, id, "Copy failed!"));
});
