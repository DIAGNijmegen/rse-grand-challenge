let user;

document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("warningModal");

    modal.addEventListener("show.bs.modal", event => {
        const button = event.relatedTarget;
        modal.querySelector(".warning-text").textContent =
            button.dataset.warning;
        modal.querySelector(".modal-action").textContent =
            button.dataset.action;
        document.getElementById("warningModalLabel").textContent =
            button.dataset.title;
        user = button.dataset.user;
    });

    document.getElementById("proceed").addEventListener("click", event => {
        const target = event.currentTarget;
        htmx.ajax("POST", `${target.dataset.baseurl}remove-answers/${user}/`, {
            values: { csrfmiddlewaretoken: target.dataset.csrf },
            headers: {
                "X-CSRFToken": target.dataset.csrf,
                "Content-Type": "application/json",
            },
        });
    });
});
