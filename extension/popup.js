const SERVER = "https://ca-itrackjobs.purplecliff-58dc9ef2.eastus2.azurecontainerapps.io";
let pageUrl = "";


function readJobFromPage() {
  
  function fromStructuredData() {
    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const data = JSON.parse(script.textContent);
        const items = Array.isArray(data) ? data : (data["@graph"] || [data]);
        for (const item of items) {
          const type = item["@type"];
          const isJob = type === "JobPosting" || (Array.isArray(type) && type.includes("JobPosting"));
          if (!isJob) continue;
          const org = item.hiringOrganization;
          const company = typeof org === "string" ? org : (org && org.name) || "";
          return { title: item.title || "", company };
        }
      } catch {
        
      }
    }
    return { title: "", company: "" };
  }

  
  const SITES = [
    {
      match: /linkedin\.com\/jobs/,
      title: [".job-details-jobs-unified-top-card__job-title h1", ".t-24.t-bold"],
      company: [".job-details-jobs-unified-top-card__company-name a",
                ".job-details-jobs-unified-top-card__company-name"],
    },
    {
      match: /indeed\.com/,
      title: [
        "[data-testid='jobsearch-JobInfoHeader-title']",
        ".jobsearch-JobInfoHeader-title",
      ],
      company: [
        "[data-testid='inlineHeader-companyName']",
        "[data-company-name='true']",
        "[data-testid='jobsearch-CompanyInfoContainer'] a",
      ],
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

  const structured = fromStructuredData();
  const site = SITES.find(s => s.match.test(location.href));
  let title = structured.title || (site ? firstText(site.title) : "");
  let company = structured.company || (site ? firstText(site.company) : "");

  
  const tabTitle = document.title.replace(/^\(\d+\)\s*/, "");
  const parts = tabTitle.split(" | ");
  if (!title) title = parts[0];
  if (!company && parts.length >= 3) company = parts[1];

 
  title = title.split(" | ")[0].trim();
  title = title.replace(/\s*-\s*job post$/i, "").trim();
  if (/indeed\.com/.test(location.href)) title = title.replace(/\s+-\s+[^-]+,\s*[A-Z]{2}\b.*$/, "").trim();
  company = company.replace(/\s+/g, " ").trim();
  if (/^(job search|jobs?|indeed|linkedin)$/i.test(title)) title = "";

  
  const linkedIn = location.href.match(/currentJobId=(\d+)/) || location.href.match(/jobs\/view\/(\d+)/);
  const indeed = location.href.match(/[?&](?:vjk|jk)=([a-f0-9]+)/i);
  let url = location.href;
  if (linkedIn) url = `https://www.linkedin.com/jobs/view/${linkedIn[1]}/`;
  else if (indeed) url = `https://www.indeed.com/viewjob?jk=${indeed[1]}`;

  return { title, company, url };
}

function showStatus(text, color = "#1d2330") {
  const el = document.getElementById("status");
  el.textContent = text;
  el.style.color = color;
}

async function start() {
  const { apiKey } = await chrome.storage.local.get("apiKey");
  const { autoLog = true } = await chrome.storage.local.get("autoLog");
  document.getElementById("auto-log").checked = autoLog;

  if (!apiKey) {
    document.getElementById("settings").style.display = "block";
    showStatus("Add your API key in Settings first.", "#dc2626");
  }

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    
    const JOB_PAGE_RULES = [
      { site: /linkedin\.com/, page: /currentJobId=\d+|\/jobs\/view\/\d+/ },
      { site: /indeed\.com/, page: /viewjob|vjk=/ },
    ];
    const rule = JOB_PAGE_RULES.find(r => r.site.test(tab.url || ""));
    if (rule && !rule.page.test(tab.url)) {
      showStatus("Open a specific job posting first, then click iTrackJobs.", "#dc2626");
      document.getElementById("save").disabled = true;
      return;
    }

    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: readJobFromPage,
    });

    
    const NOT_A_JOB = /can.?t find this page|page not found|404|(doesn.?t|does not) exist/i;
    if (NOT_A_JOB.test(result.title)) {
      showStatus("This doesn't look like a job posting. Open the job's own page.", "#dc2626");
      document.getElementById("save").disabled = true;
      return;
    }

    document.getElementById("title").value = result.title;
    document.getElementById("company").value = result.company;
    pageUrl = result.url;

    if (!result.title || !result.company) {
      showStatus("Couldn't find everything. Please fill in the empty box.", "#d97706");
    }
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
    showStatus("Can't reach the server. Try again in a few seconds.", "#dc2626");
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

document.getElementById("auto-log").addEventListener("change", async (event) => {
  await chrome.storage.local.set({ autoLog: event.target.checked });
  showStatus(event.target.checked ? "Auto-log on ✓" : "Auto-log off", "#059669");
});

start();