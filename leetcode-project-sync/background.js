const BACKEND_URL = "https://leetcodeinterviewhelper.onrender.com/api/credentials";

async function getAllLeetCodeCookies() {
  return new Promise((resolve) => {
    chrome.cookies.getAll({ domain: "leetcode.com" }, (cookies) => resolve(cookies));
  });
}

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
    console.error("LeetCode sync: could not reach backend", err);
  }
}

chrome.runtime.onInstalled.addListener(syncCredentialsToBackend);
chrome.runtime.onStartup.addListener(syncCredentialsToBackend);

chrome.cookies.onChanged.addListener((changeInfo) => {
  const { cookie } = changeInfo;

  if (!cookie.domain.includes("leetcode.com")) {
    return;
  }

  if (cookie.name === "LEETCODE_SESSION" || cookie.name === "csrftoken") {
    syncCredentialsToBackend();
  }
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.syncToken) {
    syncCredentialsToBackend();
  }
});