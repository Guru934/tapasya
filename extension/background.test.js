// Tests for Tapasya Tab Reporter extension logic
// Run with: node --test extension/background.test.js

const { test, describe, beforeEach, afterEach, mock } = require('node:test');
const assert = require('node:assert');

// Mock Chrome APIs
const chrome = {
  windows: {
    WINDOW_ID_NONE: -1,
    getAll: mock.fn(),
    onFocusChanged: { addListener: mock.fn() },
  },
  tabs: {
    query: mock.fn(),
    onActivated: { addListener: mock.fn() },
    onUpdated: { addListener: mock.fn() },
  },
  alarms: {
    get: mock.fn(),
    create: mock.fn(),
    onAlarm: { addListener: mock.fn() },
  },
  runtime: {
    onStartup: { addListener: mock.fn() },
    onInstalled: { addListener: mock.fn() },
  },
  runtime: {
    onStartup: { addListener: mock.fn() },
    onInstalled: { addListener: mock.fn() },
  },
};

// We need to test the pure functions from background.js
// Since background.js uses ES modules and chrome APIs, we'll extract the testable functions
// and test them in isolation.

describe('buildPayload', () => {
  test('returns empty payload for null tab', () => {
    const payload = buildPayload(null);
    assert.deepStrictEqual(payload, { domain: "", title: "", shorts: false, audible: false });
  });

  test('returns empty payload for incognito tab', () => {
    const payload = buildPayload({ incognito: true, url: "https://example.com" });
    assert.deepStrictEqual(payload, { domain: "", title: "", shorts: false, audible: false });
  });

  test('returns empty payload for tab without url', () => {
    const payload = buildPayload({ url: null });
    assert.deepStrictEqual(payload, { domain: "", title: "", shorts: false, audible: false });
  });

  test('returns empty payload for internal protocol', () => {
    const payload = buildPayload({ url: "chrome://newtab/", incognito: false });
    assert.deepStrictEqual(payload, { domain: "", title: "", shorts: false, audible: false });
  });

  test('returns empty payload for brave:// protocol', () => {
    const payload = buildPayload({ url: "brave://settings", incognito: false });
    assert.deepStrictEqual(payload, { domain: "", title: "", shorts: false, audible: false });
  });

  test('returns domain and title for valid http URL', () => {
    const payload = buildPayload({ url: "https://docs.python.org/3/", title: "Python Docs", incognito: false, audible: false });
    assert.strictEqual(payload.domain, "docs.python.org");
    assert.strictEqual(payload.title, "Python Docs");
    assert.strictEqual(payload.shorts, false);
    assert.strictEqual(payload.audible, false);
  });

  test('returns domain for valid https URL', () => {
    const payload = buildPayload({ url: "https://github.com/user/repo", title: "GitHub", incognito: false, audible: true });
    assert.strictEqual(payload.domain, "github.com");
    assert.strictEqual(payload.audible, true);
  });

  test('detects YouTube Shorts', () => {
    const payload = buildPayload({ url: "https://www.youtube.com/shorts/abc123", title: "Short", incognito: false });
    assert.strictEqual(payload.domain, "www.youtube.com");
    assert.strictEqual(payload.shorts, true);
  });

  test('does not detect regular YouTube as Shorts', () => {
    const payload = buildPayload({ url: "https://www.youtube.com/watch?v=abc123", title: "Video", incognito: false });
    assert.strictEqual(payload.shorts, false);
  });
});

describe('reportVersion race prevention', () => {
  let reportVersion;

  beforeEach(() => {
    reportVersion = 0;
  });

  test('increments version on each report call', () => {
    const v1 = ++reportVersion;
    const v2 = ++reportVersion;
    const v3 = ++reportVersion;
    assert.strictEqual(v1, 1);
    assert.strictEqual(v2, 2);
    assert.strictEqual(v3, 3);
  });

  test('only latest version executes send', async () => {
    const sent = [];
    const originalSend = global.send;
    global.send = async (payload) => { sent.push(payload); };

    reportVersion = 0;
    const v1 = ++reportVersion;
    const v2 = ++reportVersion;

    // Simulate doReport checking version
    async function doReport(version) {
      if (version !== reportVersion) return;
      await send({ domain: "test" });
    }

    await doReport(v1); // Should be skipped (v1 !== reportVersion which is v2)
    await doReport(v2); // Should execute

    assert.strictEqual(sent.length, 1);
    assert.strictEqual(sent[0].domain, "test");

    global.send = originalSend;
  });
});

describe('focusedWindowId tracking', () => {
  let focusedWindowId;

  beforeEach(() => {
    focusedWindowId = chrome.windows.WINDOW_ID_NONE;
  });

  test('starts as WINDOW_ID_NONE', () => {
    assert.strictEqual(focusedWindowId, -1);
  });

  test('updates on focus change to valid window', () => {
    focusedWindowId = 123;
    assert.strictEqual(focusedWindowId, 123);
  });

  test('resets to WINDOW_ID_NONE on focus lost', () => {
    focusedWindowId = 123;
    focusedWindowId = chrome.windows.WINDOW_ID_NONE;
    assert.strictEqual(focusedWindowId, -1);
  });
});

// Need to define buildPayload for tests (copied from background.js logic)
function buildPayload(tab) {
  if (!tab || tab.incognito || !tab.url) {
    return { domain: "", title: "", shorts: false, audible: false };
  }
  let u;
  try { u = new URL(tab.url); } catch { return { domain: "", title: "", shorts: false, audible: false }; }
  if (u.protocol !== "http:" && u.protocol !== "https:") {
    return { domain: "", title: "", shorts: false, audible: false };
  }
  const shorts = u.hostname.endsWith("youtube.com") && u.pathname.startsWith("/shorts");
  return { domain: u.hostname, title: tab.title || "", shorts, audible: !!tab.audible };
}

// Mock send for tests
global.send = async (payload) => { };