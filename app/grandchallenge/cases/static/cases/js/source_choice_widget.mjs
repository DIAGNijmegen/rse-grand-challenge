const initChoiceWidgets = () => {
    const elements = document.querySelectorAll(
        "[id^='id___INTERFACE_FIELD__'][id$='__widget_choice']",
    );
    for (const el of elements) {
        const prefixedSocketSlug = el.id.replace(/__widget_choice$/, "");
        const searchWidget = document.getElementById(
            `div_${prefixedSocketSlug}__search`,
        );
        const uploadWidget = document.getElementById(
            `div_${prefixedSocketSlug}__upload`,
        );

        if (!searchWidget || !uploadWidget) {
            return;
        }

        searchWidget.classList.toggle("d-none", el.value !== "IMAGE_SEARCH");
        uploadWidget.classList.toggle("d-none", el.value !== "IMAGE_UPLOAD");

        if (!el.dataset.eventListenerAdded) {
            el.addEventListener("change", function () {
                searchWidget.classList.toggle(
                    "d-none",
                    this.value !== "IMAGE_SEARCH",
                );
                uploadWidget.classList.toggle(
                    "d-none",
                    this.value !== "IMAGE_UPLOAD",
                );
            });
            el.dataset.eventListenerAdded = "1";
        }
    }
};

// Run on DOM changes (needed for re-rendered forms)
new MutationObserver(initChoiceWidgets).observe(document.body, {
    childList: true,
    subtree: true,
});
