document
    .getElementById("InfoModal")
    .addEventListener("show.bs.modal", event => {
        const button = event.relatedTarget;
        const modal = event.target;
        modal.querySelector(".modal-title").textContent = button.dataset.title;
        modal.querySelector(".modal-description").textContent =
            button.dataset.description;

        const url = modal.querySelector(".modal-url");
        url.setAttribute("href", button.dataset.absoluteUrl);
        url.textContent = button.dataset.absoluteUrl;
    });
