// Where your Flask backend is running. Change this if you deploy the
// backend somewhere other than your own machine.
const BACKEND_URL = "https://leetcodeinterviewhelper.onrender.com/api/credentials";

// Grab every cookie LeetCode has set, not just the two we care about --
// LeetCode's Cloudflare protection (cf_clearance) can reject requests that
// are missing cookies a real browser would normally send along, even if
// LEETCODE_SESSION and csrftoken are both technically present.
async function getAllLeetCodeCookies() {
  return new Promise((resolve) => {
    chrome.cookies.getAll({ domain: "leetcode.com" }, (cookies) => resolve(cookies));
  });
}

// The extension's own account-scoped bearer token, pasted into popup.html
// once (from the app's Account page) and stored locally. This is what
// tells the backend WHICH account to sync this cookie to -- deliberately
// not a login JWT (see auth.py's module docstring for why), and there's
// no fallback to a "default" account anymore: with nothing set here, the
// backend has no way to know whose data this is, so syncing is skipped
// entirely rather than guessing.
async function getSyncToken() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["syncToken"], (result) => resolve(result.syncToken || ""));
  });
}

async function syncCredentialsToBackend() {
  const syncToken = await getSyncToken();
  if (!syncToken) {
    console.log("LeetCode sync: no sync token configured yet -- open the extension popup and paste one in from the app's Account page.");
    return;
  }

  const cookies = await getAllLeetCodeCookies();
  const sessionCookie = cookies.find((c) => c.name === "LEETCODE_SESSION");
  const csrfCookie = cookies.find((c) => c.name === "csrftoken");

  if (!sessionCookie || !csrfCookie) {
    console.log("LeetCode sync: not logged in (missing session or csrf cookie), nothing to send.");
    return;
  }

  const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");

  try {
    const response = await fetch(BACKEND_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Sync-Token": syncToken,
      },
      body: JSON.stringify({ cookie: cookieHeader, csrf: csrfCookie.value }),
    });

    if (response.status === 401) {
      console.error("LeetCode sync: backend rejected the sync token -- it may have been revoked or regenerated. Get a fresh one from the app's Account page.");
      return;
    }

    if (!response.ok) {
      console.error("LeetCode sync: backend rejected the credentials", response.status);
      return;
    }

    console.log("LeetCode sync: credentials sent to backend successfully.");
  } catch (err) {
    // Backend not running / unreachable -- fine, we'll try again next time
    // a cookie changes. Nothing for the user to do here.
    console.error("LeetCode sync: could not reach backend", err);
  }
}

// Fires on install/update AND on browser startup -- covers the case where
// the user was already logged into LeetCode before installing the extension,
// so we don't just wait around for a future cookie change that may never come.
chrome.runtime.onInstalled.addListener(syncCredentialsToBackend);
chrome.runtime.onStartup.addListener(syncCredentialsToBackend);

// Fires any time a LeetCode cookie changes -- covers login, logout, and
// LeetCode silently renewing the session while the user browses.
chrome.cookies.onChanged.addListener((changeInfo) => {
  const { cookie } = changeInfo;

  if (!cookie.domain.includes("leetcode.com")) {
    return;
  }

  if (cookie.name === "LEETCODE_SESSION" || cookie.name === "csrftoken") {
    syncCredentialsToBackend();
  }
});

// Fires the moment the popup saves a new (or changed) sync token -- syncs
// immediately instead of waiting for the next cookie change, so pasting a
// token in and seeing it work feels instant.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.syncToken) {
    syncCredentialsToBackend();
  }
});