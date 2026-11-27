// Bootstrap tooltips are opt-in
// Set attribute 'data-bs-toggle' to "tooltip" on elements that should have a tooltip
// For example:
//   <div data-bs-toggle="tooltip" title="Tooltip content"></div>

const tooltipTriggerList = document.querySelectorAll(
    '[data-bs-toggle="tooltip"]',
);
const tooltipList = [...tooltipTriggerList].map(
    tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl),
);
