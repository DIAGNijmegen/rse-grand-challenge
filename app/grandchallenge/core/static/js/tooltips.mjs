// Bootstrap tooltips are opt-in
// Set attribute 'data-bs-toggle' to "tooltip" on elements that should have a tooltip
// For example:
//   <div data-bs-toggle="tooltip" title="Tooltip content"></div>

document
    .querySelectorAll('[data-bs-toggle="tooltip"]')
    .forEach(el => bootstrap.Tooltip.getOrCreateInstance(el));
