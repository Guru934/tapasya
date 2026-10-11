// Tapasya Tab Reporter (MV3). Sends ONLY {domain, title, shorts, audible} to the local daemon.
// Never sends full URLs, page contents, or anything from incognito windows.
const API = "http://127.0.0.1:8765/v1/tab";

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

async function report() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab || tab.incognito || !tab.url) {
    return send({ domain: "", title: "", shorts: false });
  }
  let u;
  try { u = new URL(tab.url); } catch { return send({ domain: "", title: "", shorts: false }); }
  if (u.protocol !== "http:" && u.protocol !== "https:") {
    return send({ domain: "", title: "", shorts: false }); // brave://, new tab, etc.
  }
  const shorts = u.hostname.endsWith("youtube.com") && u.pathname.startsWith("/shorts");
  return send({ domain: u.hostname, title: tab.title || "", shorts, audible: !!tab.audible });
}

chrome.tabs.onActivated.addListener(report);
chrome.tabs.onUpdated.addListener((_id, info) => {
  if (info.status === "complete" || info.title || info.audible !== undefined) report();
});
chrome.windows.onFocusChanged.addListener(report);
chrome.runtime.onStartup.addListener(report);
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("heartbeat", { periodInMinutes: 0.5 });
  report();
});
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "heartbeat") report(); });
