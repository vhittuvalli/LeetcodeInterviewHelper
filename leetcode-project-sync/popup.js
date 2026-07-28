const tokenInput = document.getElementById("tokenInput");
const saveBtn = document.getElementById("saveBtn");
const statusEl = document.getElementById("status");

function showStatus(hasToken) {
  if (hasToken) {
    statusEl.textContent = "Sync token saved -- syncing to your account.";
    statusEl.className = "active";
  } else {
    statusEl.textContent = "No sync token set yet.";
    statusEl.className = "";
  }
}

// Load whatever's already saved so re-opening the popup doesn't look empty
// if it's already configured -- doesn't show the token itself back in the
// input (same "never displayed after generation" rule the Account page
// follows), just whether one is present.
chrome.storage.local.get(["syncToken"], (result) => {
  showStatus(!!result.syncToken);
});

saveBtn.addEventListener("click", () => {
  const value = tokenInput.value.trim();
  if (!value) return;

  saveBtn.disabled = true;
  chrome.storage.local.set({ syncToken: value }, () => {
    // background.js is listening for this via chrome.storage.onChanged
    // and will trigger a sync immediately -- nothing to do here beyond
    // saving.
    tokenInput.value = "";
    statusEl.textContent = "Saved! Syncing now...";
    statusEl.className = "saved";
    saveBtn.disabled = false;
  });
});