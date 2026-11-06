const SERVER = "http://127.0.0.1:8000";
let pageUrl = "";

// This function runs INSIDE the job page, not in the popup.
// Each site has its own selectors. When a site changes its layout, update them here.
function readJobFromPage() {
  const SITES = [
    {
      match: /linkedin\.com\/jobs/,
      title: [".job-details-jobs-unified-top-card__job-title h1", ".t-24.t-bold", "h1"],
      company: [".job-details-jobs-unified-top-card__company-name a",
                ".job-details-jobs-unified-top-card__company-name"],
    },
    {
      match: /indeed\.com/,
      title: ["[data-testid='jobsearch-JobInfoHeader-title']", "h1"],
      company: ["[data-testid='inlineHeader-companyName']"],
    },
  ];

  function firstText(selectors) {
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element && element.textContent.trim()) {
        return element.textContent.trim().replace(/\s+/g, " ");
      }
    }
    return "";
  }

  const site = SITES.find(s => s.match.test(location.href));
  let title = site ? firstText(site.title) : "";
  let company = site ? firstText(site.company) : "";

  // Tab title looks like "(2) Title | Company | LinkedIn"
  const tabTitle = document.title.replace(/^\(\d+\)\s*/, "");  // remove "(2) " notification count
  const parts = tabTitle.split(" | ");

  // Fallbacks: use the tab title when the page selectors don't find anything
  if (!title) title = parts[0];
  if (!company && parts.length >= 3) company = parts[1];

  title = title.split(" | ")[0].trim();
  company = company.trim();

  // One clean link per LinkedIn job, so duplicates are caught
  const match = location.href.match(/currentJobId=(\d+)/) || location.href.match(/jobs\/view\/(\d+)/);
  const url = match ? `https://www.linkedin.com/jobs/view/${match[1]}/` : location.href;

  return { title, company, url };
}

function showStatus(text, color = "#1d2330") {
  const el = document.getElementById("status");
  el.textContent = text;
  el.style.color = color;
}

async function start() {
  const { apiKey } = await chrome.storage.local.get("apiKey");
  if (!apiKey) {
    document.getElementById("settings").style.display = "block";
    showStatus("Add your API key in Settings first.", "#dc2626");
  }

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: readJobFromPage,
    });
    document.getElementById("title").value = result.title;
    document.getElementById("company").value = result.company;
    pageUrl = result.url;
  } catch {
    showStatus("Can't read this page. Type the details in.", "#dc2626");
  }
}

document.getElementById("save").addEventListener("click", async () => {
  const { apiKey } = await chrome.storage.local.get("apiKey");
  showStatus("Saving…");
  try {
    const response = await fetch(`${SERVER}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": apiKey || "" },
      body: JSON.stringify({
        title: document.getElementById("title").value.trim(),
        company: document.getElementById("company").value.trim(),
        url: pageUrl,
      }),
    });
    if (response.status === 201) showStatus("Saved ✓", "#059669");
    else if (response.status === 200) showStatus("Already tracked ✓", "#059669");
    else if (response.status === 401) showStatus("Wrong API key. Check Settings.", "#dc2626");
    else if (response.status === 422) showStatus("Title and company are required.", "#dc2626");
    else showStatus("Error " + response.status, "#dc2626");
  } catch {
    showStatus("Can't reach the server. Is uvicorn running?", "#dc2626");
  }
});

document.getElementById("toggle-settings").addEventListener("click", () => {
  const box = document.getElementById("settings");
  box.style.display = box.style.display === "block" ? "none" : "block";
});

document.getElementById("save-settings").addEventListener("click", async () => {
  await chrome.storage.local.set({ apiKey: document.getElementById("api-key").value.trim() });
  showStatus("Key saved ✓", "#059669");
});

start();