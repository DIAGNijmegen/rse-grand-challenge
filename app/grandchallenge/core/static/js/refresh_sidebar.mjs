document.addEventListener("DOMContentLoaded", () => {
    const tabSelectors = [...document.querySelectorAll("#v-pills-tab a")];

    const allowedHashes = new Set(
        tabSelectors
            .map(tab => tab.getAttribute("href"))
            .filter(href => href !== null && href.startsWith("#")),
    );

    function isValidHash(hash) {
        return allowedHashes.has(hash);
    }

    function showTab(tab) {
        if (!tab) return;
        for (const sibling of tab.parentElement.children) {
            if (sibling !== tab) sibling.classList.remove("active");
        }
        bootstrap.Tab.getOrCreateInstance(tab).show();
    }

    function activateLocation() {
        const hash = window.location.hash;
        if (isValidHash(hash)) {
            showTab(
                tabSelectors.find(tab => tab.getAttribute("href") === hash),
            );
        } else {
            // Fallback to a default tab if the hash is not valid
            showTab(
                document.querySelector('#v-pills-tab a[href="#information"]'),
            );
        }
    }

    for (const tab of tabSelectors) {
        tab.addEventListener("click", () => {
            const hash = tab.getAttribute("href");
            if (isValidHash(hash)) {
                history.pushState(null, null, hash);
                activateLocation();
            }
        });
    }

    window.addEventListener("popstate", activateLocation);
    window.addEventListener("pageshow", activateLocation);

    activateLocation();
});
