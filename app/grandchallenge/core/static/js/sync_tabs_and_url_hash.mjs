const DEFAULT_HASH = "#information";

const tabLinks = [...document.querySelectorAll("#v-pills-tab a")];
const allowedHashes = new Set(tabLinks.map(tab => tab.getAttribute("href")));

function showTabFromLocation() {
    const hash = allowedHashes.has(window.location.hash)
        ? window.location.hash
        : DEFAULT_HASH;
    const tab = tabLinks.find(t => t.getAttribute("href") === hash);

    if (tab) {
        bootstrap.Tab.getOrCreateInstance(tab).show();
    }
}

// Bootstrap handles the click itself, we only keep the URL in sync
for (const tab of tabLinks) {
    tab.addEventListener("shown.bs.tab", () => {
        const hash = tab.getAttribute("href");

        if (window.location.hash === hash) return;

        if (allowedHashes.has(window.location.hash)) {
            history.pushState(null, "", hash);
        } else {
            // Default tab shown on load, don't add a history entry for it
            history.replaceState(null, "", hash);
        }
    });
}

window.addEventListener("popstate", showTabFromLocation);

showTabFromLocation();
