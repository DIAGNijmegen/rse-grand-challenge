/**
 * @description
 * Lightweight, JavaScript-based bot challenge for the contact form.
 *
 * The form renders three hidden fields:
 *   - c0, c1: prefilled by the server with random tokens.
 *   - c2: empty; must be filled in by this script to equal `c1 + c0`
 *     (the second token followed by the first token).
 *
 * The value of c2 is built up by two delayed actions:
 *   - after ~1 second: c2 := c1
 *   - after ~2 seconds: c2 := c2 + c0
 *
 * The server only accepts the submission when c2 === c1 + c0. A bot that
 * submits the raw HTML without executing JavaScript leaves c2 empty and is
 * rejected.
 *
 * Anti-tamper: a naive bot might overwrite `setTimeout` so that callbacks run
 * immediately instead of after the delay. To detect this, each scheduled
 * action records the wall-clock time at scheduling and verifies that enough
 * real time has actually elapsed when it runs. If a callback fires too early
 * (e.g. because setTimeout was patched to be synchronous), it refuses to write
 * to c2, so the challenge cannot be solved by short-circuiting the timers.
 *
 * Note on ordering: the later (2s) action is scheduled first, then the earlier
 * (1s) action, so that the append step is registered before the step it
 * depends on.
 */

const FIRST_DELAY_MS = 1000;
const SECOND_DELAY_MS = 2000;

function getField(name) {
    return document.querySelector(`input[name="${name}"]`);
}

function elapsedIsPlausible(scheduledAt, delayMs) {
    const elapsed = Date.now() - scheduledAt;
    return elapsed >= delayMs;
}

function initContactChallenge() {
    const c0 = getField("c0");
    const c1 = getField("c1");
    const c2 = getField("c2");

    if (!c0 || !c1 || !c2) {
        // Not the contact form; nothing to do.
        return;
    }

    const scheduledAt = Date.now();

    // Second (later) action: append c0 to c2.
    setTimeout(() => {
        if (!elapsedIsPlausible(scheduledAt, SECOND_DELAY_MS)) {
            // Timers were tampered with; abort silently.
            return;
        }
        // Only append if the first action has already set c2 to c1.
        if (c2.value === c1.value) {
            c2.value = c2.value + c0.value;
        }
    }, SECOND_DELAY_MS);

    // First (earlier) action: set c2 to c1.
    setTimeout(() => {
        if (!elapsedIsPlausible(scheduledAt, FIRST_DELAY_MS)) {
            // Timers were tampered with; abort silently.
            return;
        }
        c2.value = c1.value;
    }, FIRST_DELAY_MS);
}

document.addEventListener("DOMContentLoaded", initContactChallenge);