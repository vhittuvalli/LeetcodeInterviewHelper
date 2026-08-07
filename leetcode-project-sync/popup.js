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

chrome.storage.local.get(["syncToken"], (result) => {
  showStatus(!!result.syncToken);
});

saveBtn.addEventListener("click", () => {
  const value = tokenInput.value.trim();
  if (!value) return;

  saveBtn.disabled = true;
  chrome.storage.local.set({ syncToken: value }, () => {
    tokenInput.value = "";
    statusEl.textContent = "Saved! Syncing now...";
    statusEl.className = "saved";
    saveBtn.disabled = false;
  });
});