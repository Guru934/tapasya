// Tapasya Tab Reporter (MV3). Sends ONLY {domain, title, shorts, audible} to the local daemon.
// Never sends full URLs, page contents, or anything from incognito windows.
const API = "http://127.0.0.1:8765/v1/tab";

// Version counter to prevent race conditions: only the latest report() call sends its payload.
let reportVersion = 0;
// Track the currently focused window ID to ignore events from unfocused windows.
let focusedWindowId = chrome.windows.WINDOW_ID_NONE;

async function send(payload) {
  try {
    await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    // daemon not running: ignore silently
  }
}

// Ensure the heartbeat alarm exists. Creates it only if missing.
async function ensureHeartbeat() {
  const existing = await chrome.alarms.get("heartbeat");
  if (!existing) {
    await chrome.alarms.create("heartbeat", { periodInMinutes: 0.5 });
  }
}

// Build payload from a tab. Returns an object with eligible flag.
function buildPayload(tab) {
  if (!tab || tab.incognito || !tab.url) {
    return { domain: "", title: "", shorts: false, audible: false, eligible: false };
  }
  let u;
  try { u = new URL(tab.url); } catch { return { domain: "", title: "", shorts: false, audible: false, eligible: false }; }
  if (u.protocol !== "http:" && u.protocol !== "https:") {
    return { domain: "", title: "", shorts: false, audible: false, eligible: false }; // brave://, new tab, etc.
  }
  const shorts = u.hostname.endsWith("youtube.com") && u.pathname.startsWith("/shorts");
  return { domain: u.hostname, title: tab.title || "", shorts, audible: !!tab.audible, eligible: true };
}

// Core reporting logic with version-based race prevention.
async function doReport(version, tab) {
  const payload = buildPayload(tab);
  // Only send if this is still the latest report version.
  if (version !== reportVersion) return;
  await send(payload);
}

// Public report entry point: increments version, captures tab, and sends if still latest.
async function report(tabOrWindowId) {
  const version = ++reportVersion;
  let tab = null;

  if (typeof tabOrWindowId === "number") {
    // Called from windows.onFocusChanged with a window ID.
    if (tabOrWindowId === chrome.windows.WINDOW_ID_NONE) {
      focusedWindowId = chrome.windows.WINDOW_ID_NONE;
      // Don't send a report on focus loss - just update the tracked window ID.
      // The last valid tab state should persist until a new valid tab is focused.
      return;
    }
    focusedWindowId = tabOrWindowId;
    // Query the active tab in the newly focused window.
    const tabs = await chrome.tabs.query({ active: true, windowId: focusedWindowId });
    tab = tabs[0] || null;
  } else if (tabOrWindowId && typeof tabOrWindowId === "object" && tabOrWindowId.id) {
    // Called from tabs.onActivated or tabs.onUpdated with a tab object or activeInfo.
    // Only report if this tab belongs to the currently focused window.
    if (focusedWindowId !== chrome.windows.WINDOW_ID_NONE && tabOrWindowId.windowId === focusedWindowId) {
      tab = tabOrWindowId;
    } else {
      // Tab event from an unfocused window - ignore to avoid stale reports.
      return;
    }
  } else {
    // Fallback: query active tab in focused window (used by alarms, startup).
    if (focusedWindowId !== chrome.windows.WINDOW_ID_NONE) {
      const tabs = await chrome.tabs.query({ active: true, windowId: focusedWindowId });
      tab = tabs[0] || null;
    }
  }

  await doReport(version, tab);
}

// Initialize on service worker startup.
(async () => {
  await ensureHeartbeat();
  // Determine initial focused window.
  const windows = await chrome.windows.getAll({ populate: false });
  const focused = windows.find(w => w.focused);
  focusedWindowId = focused ? focused.id : chrome.windows.WINDOW_ID_NONE;
  await report();
})();

chrome.tabs.onActivated.addListener((activeInfo) => report(activeInfo));
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" || changeInfo.title || changeInfo.audible !== undefined) {
    report(tab);
  }
});
chrome.windows.onFocusChanged.addListener((windowId) => report(windowId));
chrome.runtime.onStartup.addListener(async () => {
  await ensureHeartbeat();
  await report();
});
chrome.runtime.onInstalled.addListener(async () => {
  await ensureHeartbeat();
  await report();
});
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "heartbeat") report(); });
