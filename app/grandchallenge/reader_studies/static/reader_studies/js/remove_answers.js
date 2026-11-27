document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("warningModal");
    const proceedButton = document.getElementById("proceed");

    modal.addEventListener("show.bs.modal", event => {
        const button = event.relatedTarget;
        modal.querySelector(".warning-text").textContent =
            button.dataset.warning;
        modal.querySelector(".modal-action").textContent =
            button.dataset.action;
        modal.querySelector("#warningModalLabel").textContent =
            button.dataset.title;
        proceedButton.dataset.user = button.dataset.user;
    });

    proceedButton.addEventListener("click", () => {
        const { baseurl, csrf, user } = proceedButton.dataset;

        htmx.ajax("POST", `${baseurl}remove-answers/${user}/`, {
            values: { csrfmiddlewaretoken: csrf },
            headers: {
                "X-CSRFToken": csrf,
                "Content-Type": "application/json",
            },
        });
    });
});
