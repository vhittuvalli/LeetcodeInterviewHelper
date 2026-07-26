// Where your Flask backend is running. Change this if you deploy the
// backend somewhere other than your own machine.
const BACKEND_URL = "http://localhost:5000/api/credentials";

// Grab every cookie LeetCode has set, not just the two we care about --
// LeetCode's Cloudflare protection (cf_clearance) can reject requests that
// are missing cookies a real browser would normally send along, even if
// LEETCODE_SESSION and csrftoken are both technically present.
async function getAllLeetCodeCookies() {
  return new Promise((resolve) => {
    chrome.cookies.getAll({ domain: "leetcode.com" }, (cookies) => resolve(cookies));
  });
}

async function syncCredentialsToBackend() {
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cookie: cookieHeader, csrf: csrfCookie.value }),
    });

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