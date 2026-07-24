const { chromium } = require("playwright");

const BASE = "http://127.0.0.1:8000";
const OUT = "docs/img";
const creds = JSON.stringify({ discord_token: "demo", guild_id: "", groq_key: "demo" });

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2 });

  // 1. Onboarding (no creds)
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  // open a couple of accordion steps for a fuller shot
  const steps = await page.$$(".step-head");
  if (steps[1]) await steps[1].click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/onboarding.png` });
  console.log("captured onboarding");

  // Inject creds so the app treats us as connected
  await page.addInitScript((c) => localStorage.setItem("punch_creds", c), creds);
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);

  // 2. Ask (chat empty state)
  await page.screenshot({ path: `${OUT}/ask.png` });
  console.log("captured ask");

  // 3. Timeline
  await page.click('button.nav-item:has-text("Timeline")');
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/timeline.png` });
  console.log("captured timeline");

  // 4. Messages
  await page.click('button.nav-item:has-text("Messages")');
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/messages.png` });
  console.log("captured messages");

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
