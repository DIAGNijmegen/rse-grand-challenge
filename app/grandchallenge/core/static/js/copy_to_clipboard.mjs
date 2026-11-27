const TOOLTIP_DURATION_MS = 2000;

const activeTimers = new WeakMap();
const originalTitles = new WeakMap();

function showTooltip(btn, message) {
    const tooltip = bootstrap.Tooltip.getOrCreateInstance(btn);

    clearTimeout(activeTimers.get(btn));
    tooltip.setContent({ ".tooltip-inner": message });
    tooltip.show();

    activeTimers.set(
        btn,
        setTimeout(() => {
            tooltip.hide();
            tooltip.setContent({ ".tooltip-inner": originalTitles.get(btn) });
        }, TOOLTIP_DURATION_MS),
    );
}

document.addEventListener("click", async e => {
    const btn = e.target.closest(".copy-btn");
    if (!btn) return;

    if (!originalTitles.has(btn)) {
        originalTitles.set(
            btn,
            btn.getAttribute("data-bs-original-title") || btn.title,
        );
    }

    navigator.clipboard.writeText(btn.dataset.copy).then(
        () => showTooltip(btn, "Copied to clipboard!"),
        () => showTooltip(btn, "Copy failed!"),
    );
});
