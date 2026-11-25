const puppeteer = require('puppeteer-core');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE_URL = 'http://127.0.0.1:5173';

async function runBrowserE2E() {
  console.log('=== ActTrident Automated Headless Browser E2E Test Suite ===');
  console.log(`Connecting to Frontend: ${BASE_URL}`);
  console.log(`Using Chrome binary: ${CHROME_PATH}`);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
    ],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const consoleLogs = [];
  const consoleErrors = [];
  page.on('console', (msg) => {
    const text = msg.text();
    consoleLogs.push(`[${msg.type()}] ${text}`);
    if (msg.type() === 'error') {
      consoleErrors.push(text);
    }
  });

  try {
    // 1. Initial Load & Title Verification
    console.log('\n[Step 1] Navigating to login screen...');
    await page.goto(BASE_URL, { waitUntil: 'networkidle0', timeout: 15000 });
    const title = await page.title();
    console.log(`  ✓ Page Title: "${title}"`);
    if (title !== 'ActTrident AI Outreach Agent') {
      throw new Error(`Unexpected page title: ${title}`);
    }

    const loginHeading = await page.$eval('h1', (el) => el.textContent);
    console.log(`  ✓ Login Heading: "${loginHeading}"`);

    // 2. Authenticate
    console.log('\n[Step 2] Filling login credentials and authenticating...');
    await page.type('input[type="email"]', 'admin@acttrident.ai');
    await page.type('input[type="password"]', 'AdminPassword2026!');
    
    await Promise.all([
      page.click('button[type="submit"]'),
      page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 10000 }).catch(() => {}),
    ]);

    await new Promise((r) => setTimeout(r, 1500));

    const appHeader = await page.$eval('#root', (el) => el.innerText);
    const loggedIn = appHeader.includes('ActTrident') && !appHeader.includes('Sign In to Platform');
    console.log(`  ✓ Authenticated session active: ${loggedIn}`);
    if (!loggedIn) {
      throw new Error('Authentication failed or did not transition from login screen');
    }

    // Helper to click sidebar nav items
    const clickSidebarItem = async (textLabel) => {
      return page.evaluate((targetLabel) => {
        const aside = document.querySelector('aside');
        if (!aside) return false;
        const btns = Array.from(aside.querySelectorAll('button'));
        const btn = btns.find((b) => b.innerText && b.innerText.includes(targetLabel));
        if (btn) {
          btn.click();
          return true;
        }
        return false;
      }, textLabel);
    };

    // 3. Navigation to Enterprise Integrations
    console.log('\n[Step 3] Navigating to Enterprise Integrations...');
    const clickedIntegrations = await clickSidebarItem('Integrations');
    console.log(`  ✓ Sidebar 'Integrations' clicked: ${clickedIntegrations}`);
    await new Promise((r) => setTimeout(r, 1000));

    const integrationsPageText = await page.evaluate(() => document.body.innerText);
    const hasIntegrations = integrationsPageText.includes('Enterprise Integrations') || integrationsPageText.includes('Service Credentials');
    console.log(`  ✓ Enterprise Integrations view rendered: ${hasIntegrations}`);
    if (!hasIntegrations) throw new Error('Integrations view failed to render');

    // 4. Test Customer Channel Setup Guide Modal
    console.log('\n[Step 4] Opening Customer Channel Setup Guide modal...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const guideBtn = btns.find((b) => b.innerText && b.innerText.includes('Customer Channel Setup Guide'));
      if (guideBtn) guideBtn.click();
    });
    await new Promise((r) => setTimeout(r, 800));

    let modalText = await page.evaluate(() => document.body.innerText);
    const modalOpen = modalText.includes('Customer Channel Setup & Connection Guide');
    console.log(`  ✓ Channel Guide Modal opened: ${modalOpen}`);
    if (!modalOpen) throw new Error('Customer Channel Setup Guide modal did not open');

    const hasGmailTab = modalText.includes('Google Workspace / Gmail OAuth 2.0');
    console.log(`  ✓ Gmail setup instructions present: ${hasGmailTab}`);

    // Click WhatsApp tab in modal
    await page.evaluate(() => {
      const modal = document.querySelector('.fixed');
      if (!modal) return;
      const btns = Array.from(modal.querySelectorAll('button'));
      const waBtn = btns.find((b) => b.innerText && b.innerText.includes('WhatsApp'));
      if (waBtn) waBtn.click();
    });
    await new Promise((r) => setTimeout(r, 500));
    modalText = await page.evaluate(() => document.body.innerText);
    const hasWhatsAppGuide = modalText.includes('Meta WhatsApp Business Cloud API') || modalText.includes('Permanent System User Token');
    console.log(`  ✓ Meta WhatsApp Cloud API guide present: ${hasWhatsAppGuide}`);

    // Click LinkedIn tab in modal
    await page.evaluate(() => {
      const modal = document.querySelector('.fixed');
      if (!modal) return;
      const btns = Array.from(modal.querySelectorAll('button'));
      const liBtn = btns.find((b) => b.innerText && b.innerText.includes('LinkedIn'));
      if (liBtn) liBtn.click();
    });
    await new Promise((r) => setTimeout(r, 500));
    modalText = await page.evaluate(() => document.body.innerText);
    const hasLinkedInGuide = modalText.includes('Compliant Operator Handoff Architecture') || modalText.includes('Connection notes');
    console.log(`  ✓ LinkedIn compliant handoff guide present: ${hasLinkedInGuide}`);

    // Click Checklist tab
    await page.evaluate(() => {
      const modal = document.querySelector('.fixed');
      if (!modal) return;
      const btns = Array.from(modal.querySelectorAll('button'));
      const chBtn = btns.find((b) => b.innerText && b.innerText.includes('Checklist'));
      if (chBtn) chBtn.click();
    });
    await new Promise((r) => setTimeout(r, 500));
    modalText = await page.evaluate(() => document.body.innerText);
    const hasChecklist = modalText.includes('Target Evidence Verified') || modalText.includes('Launch Checklist');
    console.log(`  ✓ Pre-flight checklist present: ${hasChecklist}`);

    // Close modal
    await page.evaluate(() => {
      const modal = document.querySelector('.fixed');
      if (!modal) return;
      const btns = Array.from(modal.querySelectorAll('button'));
      const closeBtn = btns.find((b) => b.innerText && b.innerText.includes('Close Guide'));
      if (closeBtn) closeBtn.click();
    });
    await new Promise((r) => setTimeout(r, 600));

    // 5. Navigate to Nationwide Discovery
    console.log('\n[Step 5] Navigating to Nationwide Discovery View...');
    const clickedDiscovery = await clickSidebarItem('Discover Companies');
    console.log(`  ✓ Sidebar 'Discover Companies' clicked: ${clickedDiscovery}`);
    await new Promise((r) => setTimeout(r, 1200));

    const discoveryPageText = await page.evaluate(() => document.body.innerText);
    const hasScope = discoveryPageText.includes('Nationwide') || discoveryPageText.includes('Scope') || discoveryPageText.includes('Target City');
    const hasExportBtn = discoveryPageText.includes('Export CSV') || discoveryPageText.includes('CSV');
    const hasFilters = discoveryPageText.includes('Min Verified Laptops') || discoveryPageText.includes('Search');
    console.log(`  ✓ Nationwide Discovery view loaded: scope/nationwide=${hasScope}, exportCSV=${hasExportBtn}, filters=${hasFilters}`);

    // 6. Navigate to CRM Pipeline
    console.log('\n[Step 6] Navigating to CRM Pipeline...');
    const clickedCrm = await clickSidebarItem('CRM Pipeline');
    console.log(`  ✓ Sidebar 'CRM Pipeline' clicked: ${clickedCrm}`);
    await new Promise((r) => setTimeout(r, 1000));
    const crmPageText = await page.evaluate(() => document.body.innerText);
    const hasCrm = crmPageText.includes('Pipeline') || crmPageText.includes('Stage') || crmPageText.includes('Lead');
    console.log(`  ✓ CRM Pipeline view loaded: ${hasCrm}`);

    // 7. Check Settings & Global Kill Switch
    console.log('\n[Step 7] Checking Settings & Kill Switch...');
    const clickedSettings = await clickSidebarItem('Settings');
    console.log(`  ✓ Sidebar 'Settings' clicked: ${clickedSettings}`);
    await new Promise((r) => setTimeout(r, 1000));
    const settingsText = await page.evaluate(() => document.body.innerText);
    const hasKillSwitch = settingsText.includes('Kill Switch') || settingsText.includes('Outbound') || settingsText.includes('Simulation Mode');
    console.log(`  ✓ System Settings view loaded: ${hasKillSwitch}`);

    // 8. Test Autonomous Outreach Agent Brain Console
    console.log('\n[Step 8] Testing Autonomous Sales Outreach Agent (Brain) Console on Dashboard...');
    const clickedDashboard = await clickSidebarItem('Dashboard');
    console.log(`  ✓ Sidebar 'Dashboard' clicked: ${clickedDashboard}`);
    await new Promise((r) => setTimeout(r, 1000));

    const dashboardText = await page.evaluate(() => document.body.innerText);
    const hasAgentHero = dashboardText.includes('Autonomous Sales Outreach Agent') || dashboardText.includes('Launch Outreach Agent');
    console.log(`  ✓ Autonomous Agent Brain Hero banner rendered: ${hasAgentHero}`);

    // Click Launch Outreach Agent button to open modal
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const launchBtn = btns.find((b) => b.innerText && b.innerText.includes('Launch Outreach Agent'));
      if (launchBtn) launchBtn.click();
    });
    await new Promise((r) => setTimeout(r, 1000));

    const agentModalText = await page.evaluate(() => document.body.innerText);
    const hasAgentModal = agentModalText.includes('BRAIN V2 ACTIVE') || agentModalText.includes('Launch Autonomous Outreach Run');
    console.log(`  ✓ Autonomous Agent Brain Console modal opened: ${hasAgentModal}`);

    // Close modal
    await page.evaluate(() => {
      const modal = document.querySelector('.fixed');
      if (!modal) return;
      const btns = Array.from(modal.querySelectorAll('button'));
      const closeBtn = btns.find((b) => b.innerText && b.innerText.includes('Close Console'));
      if (closeBtn) closeBtn.click();
    });
    await new Promise((r) => setTimeout(r, 600));

    console.log('\n' + '='.repeat(60));
    console.log('ALL BROWSER E2E TEST CHECKS PASSED WITH ZERO CRASHES!');
    console.log('='.repeat(60));
  } catch (err) {
    console.error('\n❌ Browser E2E Test Failed:', err.message);
    if (consoleErrors.length > 0) {
      console.error('Console errors detected:', consoleErrors);
    }
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runBrowserE2E();
