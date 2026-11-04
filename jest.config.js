const path = require("node:path");

// Vendored frontend assets (installed by amass, see [tool.amass] in
// pyproject.toml) live outside the source tree. VENDORED_STATIC_ROOT points at
// that directory and must match the value used by Django and the Dockerfile.
// It defaults to the repo-external .vendored directory used for native
// development. Tests import the vendored bundles via the "vendored/" alias so
// they do not depend on the physical install location.
const vendoredStaticRoot = path.resolve(
    __dirname,
    process.env.VENDORED_STATIC_ROOT || ".vendored",
);

module.exports = {
    testEnvironment: "jsdom",

    // A list of paths to modules that run some code to configure or set up the testing framework before each test
    setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],

    // The glob patterns Jest uses to detect test files
    testMatch: ["<rootDir>/app/tests/*/js/*.test.@(js|mjs)"],

    // Resolve `vendored/...` imports to the amass-installed assets directory.
    moduleNameMapper: {
        "^vendored/(.*)$": path.join(vendoredStaticRoot, "$1"),
    },
};
