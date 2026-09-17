import { jest } from "@jest/globals";

// The module attaches its logic on DOMContentLoaded. We (re)import it once;
// subsequent dispatches of DOMContentLoaded re-run the initialization.
import("../../../grandchallenge/contact/static/contact/js/contact_challenge.mjs");

const formHtml = `
<form>
  <input type="hidden" name="c0" id="id_c0" value="AAA">
  <input type="hidden" name="c1" id="id_c1" value="BBB">
  <input type="hidden" name="c2" id="id_c2" value="">
</form>`;

describe("contact_challenge module", () => {
    let c0;
    let c1;
    let c2;

    beforeEach(() => {
        jest.useFakeTimers();
        document.body.innerHTML = formHtml;
        document.dispatchEvent(new Event("DOMContentLoaded"));

        c0 = document.querySelector("#id_c0");
        c1 = document.querySelector("#id_c1");
        c2 = document.querySelector("#id_c2");
    });

    afterEach(() => {
        jest.useRealTimers();
    });

    test("Sanity: c2 is empty before any timer fires", () => {
        expect(c2.value).toBe("");
    });

    test("c2 equals c1 + c0 after both delays complete", () => {
        // Advance real time so the anti-tamper elapsed-time check passes.
        jest.setSystemTime(new Date(Date.now() + 5000));
        jest.advanceTimersByTime(2000);

        // Concatenation is second (c1) then first (c0).
        expect(c2.value).toBe("BBBAAA");
    });

    test("c2 stays empty when setTimeout is overwritten to run immediately: tamper attempt", () => {
        // Reset DOM and simulate a bot that patches setTimeout to fire the
        // callback synchronously with zero delay.
        document.body.innerHTML = formHtml;

        const immediateSetTimeout = (fn, _delay, ...args) => {
            fn(...args);
            return 0;
        };
        const originalSetTimeout = window.setTimeout;
        window.setTimeout = immediateSetTimeout;
        global.setTimeout = immediateSetTimeout;

        try {
            document.dispatchEvent(new Event("DOMContentLoaded"));
        } finally {
            window.setTimeout = originalSetTimeout;
            global.setTimeout = originalSetTimeout;
        }

        const c2After = document.querySelector("#id_c2");
        // Because no real time elapsed, the anti-tamper check must reject the
        // fill and leave c2 empty.
        expect(c2After.value).toBe("");
    });
});
