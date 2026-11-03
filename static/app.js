
// Backend API Host configuration (supports Netlify proxy or direct external server)
function getApiBase() {
    const saved = localStorage.getItem('veritas_api_base');
    if (saved) return saved.trim().replace(/\/+$/, '');
    const urlParams = new URLSearchParams(window.location.search);
    const queryApi = urlParams.get('api');
    if (queryApi) return queryApi.trim().replace(/\/+$/, '');
    return '';
}

// DOM Elements
const modelSelect = document.getElementById('model-select');
const ollamaStatus = document.getElementById('ollama-status');
const tavilyStatus = document.getElementById('tavily-status');
const modeStatus = document.getElementById('mode-status');
const queryInput = document.getElementById('query-input');
const runBtn = document.getElementById('run-btn');
const elapsedTimer = document.getElementById('elapsed-timer');

const dashboardResults = document.getElementById('dashboard-results');
const statusPulse = document.getElementById('status-pulse');
const pipelineStatusText = document.getElementById('pipeline-status-text');
const pipelineProgress = document.getElementById('pipeline-progress');
const statusLogs = document.getElementById('status-logs');

const orchestratorSection = document.getElementById('orchestrator-section');
const subQuestionsContainer = document.getElementById('sub-questions-container');

const workersSection = document.getElementById('workers-section');
const workersGrid = document.getElementById('workers-grid');

// VeritasCore DOM Elements
const veritasPapersSection = document.getElementById('veritas-papers-section');
const papersGrid = document.getElementById('papers-grid');

const synthesizerSection = document.getElementById('synthesizer-section');
const finalReportContent = document.getElementById('final-report-content');
const copyBtn = document.getElementById('copy-btn');
const downloadBtn = document.getElementById('download-btn');
const historyList = document.getElementById('history-list');
const clearHistoryBtn = document.getElementById('clear-history-btn');

const veritasDnaSection = document.getElementById('veritas-dna-section');
const dnaContainer = document.getElementById('dna-container');

const veritasAuditSection = document.getElementById('veritas-audit-section');
const auditClaimsContainer = document.getElementById('audit-claims-container');
const auditIntegrityScore = document.getElementById('audit-integrity-score');
const auditSupportedCount = document.getElementById('audit-supported-count');
const auditUnsupportedCount = document.getElementById('audit-unsupported-count');
const auditContradictoryCount = document.getElementById('audit-contradictory-count');
const auditNeedsResearchCount = document.getElementById('audit-needs-research-count');

const countAllEl = document.getElementById('count-all');
const countSupportedEl = document.getElementById('count-supported');
const countUnsupportedEl = document.getElementById('count-unsupported');
const countContradictoryEl = document.getElementById('count-contradictory');
const countNeedsResearchEl = document.getElementById('count-needs-research');

// State Variables
let timerInterval = null;
let startTime = 0;
let eventSource = null;
let activeSubQuestions = [];
let sessionHistory = [];
let activeReportText = "";
let currentAuditClaims = [];
let currentFilter = "all";
let activeCapabilityTab = 'report';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const apiUrlInput = document.getElementById('api-url-input');
    if (apiUrlInput) {
        apiUrlInput.value = localStorage.getItem('veritas_api_base') || '';
        apiUrlInput.addEventListener('change', () => {
            const val = apiUrlInput.value.trim();
            if (val) {
                localStorage.setItem('veritas_api_base', val);
            } else {
                localStorage.removeItem('veritas_api_base');
            }
            fetchConfig();
            fetchModels();
            fetchHistory();
        });
    }

    fetchConfig();
    fetchModels();
    fetchHistory();
    
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', handleClearAllHistory);
    }
    
    runBtn.addEventListener('click', startResearchPipeline);
    copyBtn.addEventListener('click', copyReportToClipboard);
    downloadBtn.addEventListener('click', downloadReportMarkdown);
    
    // Allow pressing Enter key to run query
    queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            startResearchPipeline();
        }
    });

    // Setup Audit Filter Buttons and Navigation Tabs
    setupAuditFilters();
    setupCapabilityTabs();
});

// ---------------------------------------------------------------------------
// Multi-Navbar Capabilities Navigation
// ---------------------------------------------------------------------------

function setupCapabilityTabs() {
    const topTabBtns = document.querySelectorAll('.nav-tab-btn');
    const sideCapBtns = document.querySelectorAll('.sidebar-cap-btn');

    topTabBtns.forEach(btn => {
        btn.onclick = () => {
            const tabId = btn.getAttribute('data-tab');
            switchCapabilityTab(tabId);
        };
    });

    sideCapBtns.forEach(btn => {
        btn.onclick = () => {
            const tabId = btn.getAttribute('data-tab');
            dashboardResults.classList.remove('hidden');
            switchCapabilityTab(tabId);
        };
    });
}

function switchCapabilityTab(tabId) {
    if (!tabId) return;
    activeCapabilityTab = tabId;

    // 1. Sync Top Navbar
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        if (btn.getAttribute('data-tab') === tabId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // 2. Sync Sidebar Capabilities
    document.querySelectorAll('.sidebar-cap-btn').forEach(btn => {
        if (btn.getAttribute('data-tab') === tabId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // 3. Toggle View Panels
    document.querySelectorAll('.capability-view').forEach(view => {
        view.classList.remove('active');
    });

    const activeView = document.getElementById(`view-${tabId}`);
    if (activeView) {
        activeView.classList.add('active');
    }
}

function updateBadge(tabId, value) {
    const pill = document.getElementById(`pill-${tabId}`);
    const sidePill = document.getElementById(`side-pill-${tabId}`);
    if (pill) pill.textContent = value;
    if (sidePill) sidePill.textContent = value;
}

// Setup filter tabs for VeritasCore Claim Verification
function setupAuditFilters() {
    const filterBtns = document.querySelectorAll('.audit-filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-filter');
            applyClaimFilter();
        });
    });
}

function applyClaimFilter() {
    const claimCards = document.querySelectorAll('.claim-audit-card');
    claimCards.forEach(card => {
        const verdict = card.getAttribute('data-verdict');
        if (currentFilter === 'all' || verdict === currentFilter) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

// Fetch system configurations and set statuses
async function fetchConfig() {
    try {
        const response = await fetch(`${getApiBase()}/api/config`);
        if (!response.ok) throw new Error("Config endpoint returned error");
        const config = await response.json();
        
        // Update badges
        ollamaStatus.textContent = "Online (LLaMA-3)";
        ollamaStatus.className = "status-badge live";

        if (config.tavily_key_configured) {
            tavilyStatus.textContent = "Tavily + ArXiv";
            tavilyStatus.className = "status-badge live";
        } else {
            tavilyStatus.textContent = "Live ArXiv + DDG";
            tavilyStatus.className = "status-badge live";
        }

        modeStatus.textContent = "LIVE MODE";
        modeStatus.className = "status-badge live";
    } catch (error) {
        console.error("Error fetching config:", error);
        ollamaStatus.textContent = "Offline";
        ollamaStatus.className = "status-badge offline";
        tavilyStatus.textContent = "Offline";
        tavilyStatus.className = "status-badge offline";
        modeStatus.textContent = "Offline";
        modeStatus.className = "status-badge offline";
    }
}

// Fetch available Ollama models
async function fetchModels() {
    try {
        const response = await fetch(`${getApiBase()}/api/models`);
        if (!response.ok) throw new Error("Models endpoint error");
        const data = await response.json();
        
        modelSelect.innerHTML = '';
        
        if (data.models && data.models.length > 0) {
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                if (model.startsWith('llama3')) {
                    option.selected = true;
                }
                modelSelect.appendChild(option);
            });
            fetchConfig();
        } else {
            ["llama3:latest", "llama3:8b", "mistral:latest"].forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                if (m === 'llama3:latest') opt.selected = true;
                modelSelect.appendChild(opt);
            });
        }
    } catch (error) {
        console.error("Error fetching models:", error);
        modelSelect.innerHTML = '<option value="llama3:latest">llama3:latest (Production)</option>';
    }
}

// Timer Functions
function startTimer() {
    resetTimer();
    startTime = Date.now();
    timerInterval = setInterval(updateTimer, 100);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
    }
}

function resetTimer() {
    stopTimer();
    elapsedTimer.textContent = "00:00.0";
}

function updateTimer() {
    const elapsedMs = Date.now() - startTime;
    const minutes = Math.floor(elapsedMs / 60000);
    const seconds = Math.floor((elapsedMs % 60000) / 1000);
    const tenths = Math.floor((elapsedMs % 1000) / 100);
    
    const minStr = String(minutes).padStart(2, '0');
    const secStr = String(seconds).padStart(2, '0');
    
    elapsedTimer.textContent = `${minStr}:${secStr}.${tenths}`;
}

// Log Messages to UI console
function logMessage(text, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');
    
    entry.innerHTML = `<span style="color: var(--text-muted)">[${timeStr}]</span> ${text}`;
    
    Array.from(statusLogs.children).forEach(el => el.classList.remove('active'));
    
    entry.classList.add('active');
    statusLogs.appendChild(entry);
    statusLogs.scrollTop = statusLogs.scrollHeight;
}

// Core Execution: Server-Sent Events Research Stream
function startResearchPipeline() {
    const query = queryInput.value.trim();
    if (!query) {
        alert("Please enter a research question.");
        return;
    }

    const selectedModel = modelSelect.value;
    
    // 1. Reset UI States
    runBtn.disabled = true;
    runBtn.querySelector('span').textContent = "Investigating...";
    runBtn.style.opacity = "0.7";
    
    dashboardResults.classList.remove('hidden');
    
    statusPulse.className = "pulse-indicator blue";
    pipelineStatusText.textContent = "Initializing Pipeline...";
    pipelineProgress.style.width = "5%";
    
    statusLogs.innerHTML = "";
    logMessage("Initiating VeritasCore multi-agent research network...", 'info');
    
    // Initialize view contents with animated placeholders (NEVER leave blank!)
    subQuestionsContainer.innerHTML = '<div class="loading-state"><div class="mini-spinner"></div><span>Orchestrator decomposing query into sub-questions...</span></div>';
    workersGrid.innerHTML = '<div class="loading-state"><div class="mini-spinner"></div><span>Worker agents standing by for decomposed tasks...</span></div>';
    papersGrid.innerHTML = '<div class="loading-state"><div class="mini-spinner"></div><span>Querying ArXiv and academic repositories for scholarly research papers...</span></div>';
    finalReportContent.innerHTML = '<div class="loading-state"><div class="mini-spinner"></div><span>Report synthesis will begin once parallel research concludes...</span></div>';
    activeReportText = "";
    dnaContainer.innerHTML = '<div class="loading-state"><div class="mini-spinner"></div><span>Evidence DNA will trace claims to source passages after report drafting...</span></div>';
    auditClaimsContainer.innerHTML = '<div class="loading-state"><div class="mini-spinner"></div><span>Claim-level verification audit will evaluate evidence grounding upon completion...</span></div>';

    auditIntegrityScore.textContent = "100%";
    auditSupportedCount.textContent = "0";
    auditUnsupportedCount.textContent = "0";
    auditContradictoryCount.textContent = "0";
    auditNeedsResearchCount.textContent = "0";

    startTimer();
    activeSubQuestions = [];
    currentAuditClaims = [];

    // Reset capability badges and start on pipeline trace view
    updateBadge('report', 'Waiting');
    updateBadge('papers', '0');
    updateBadge('dna', '0');
    updateBadge('audit', '--');
    updateBadge('pipeline', 'Starting');
    switchCapabilityTab('pipeline');

    // 2. Open Server-Sent Events (SSE) Stream
    const encodedQuery = encodeURIComponent(query);
    const modelParam = selectedModel ? `&model=${encodeURIComponent(selectedModel)}` : '';
    const sseUrl = `${getApiBase()}/api/research/stream?query=${encodedQuery}${modelParam}`;
    
    logMessage(`Establishing connection to SSE stream endpoint...`, 'info');
    eventSource = new EventSource(sseUrl);

    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handlePipelineEvent(data);
        } catch (err) {
            console.error("Error parsing event data:", err);
            logMessage(`Error parsing stream event: ${err.message}`, 'error');
        }
    };

    eventSource.onerror = function(err) {
        console.error("SSE stream error:", err);
        if (pipelineStatusText.textContent !== "Research Completed" && pipelineStatusText.textContent !== "Failed") {
            logMessage("Pipeline connection interrupted.", 'error');
            terminatePipelineRun("Failed", "Connection closed prematurely", "red");
        }
        eventSource.close();
    };
}

// Event Router for SSE
function handlePipelineEvent(event) {
    switch (event.status) {
        case "guardrail_checking":
            pipelineStatusText.textContent = "Guardrail Security Check";
            statusPulse.className = "pulse-indicator blue";
            pipelineProgress.style.width = "10%";
            logMessage(event.message, 'active');
            break;

        case "guardrail_result":
            if (event.safe) {
                logMessage(`Security Guardrail: Clean (${event.message})`, 'success');
            } else {
                logMessage(`Security Guardrail Alert: ${event.message}`, 'error');
            }
            break;

        case "decomposing":
            pipelineStatusText.textContent = "Orchestrating Sub-questions";
            statusPulse.className = "pulse-indicator blue";
            pipelineProgress.style.width = "20%";
            logMessage(event.message, 'active');
            break;
            
        case "sub_questions":
            activeSubQuestions = event.sub_questions;
            pipelineStatusText.textContent = "Task Decomposed";
            pipelineProgress.style.width = "30%";
            logMessage(`Orchestrator successfully decomposed query into ${activeSubQuestions.length} sub-questions.`, 'success');
            updateBadge('pipeline', `${activeSubQuestions.length} Tasks`);
            
            subQuestionsContainer.innerHTML = "";
            activeSubQuestions.forEach((q, index) => {
                const chip = document.createElement('div');
                chip.className = "question-chip";
                chip.innerHTML = `
                    <span class="question-num">${index + 1}</span>
                    <span class="question-text">${escapeHtml(q)}</span>
                `;
                subQuestionsContainer.appendChild(chip);
            });
            break;
            
        case "workers_started":
            pipelineStatusText.textContent = "Concurrent Web & ArXiv Research";
            statusPulse.className = "pulse-indicator amber";
            pipelineProgress.style.width = "40%";
            logMessage(`Initializing ${event.count} specialized Worker Agents querying search & scholarly repositories...`, 'active');
            
            workersGrid.innerHTML = "";
            activeSubQuestions.forEach((q, index) => {
                const card = document.createElement('div');
                card.className = "worker-card searching";
                card.id = `worker-card-${index}`;
                card.innerHTML = `
                    <div class="worker-header">
                        <span class="worker-name">Worker Agent ${index + 1}</span>
                        <span class="worker-status searching">Searching...</span>
                    </div>
                    <p class="worker-question">${escapeHtml(q)}</p>
                    <div class="worker-summary">Querying web indices & reading content snippets...</div>
                    <div class="worker-sources hidden" id="worker-sources-${index}">
                        <div class="worker-sources-title">Referenced Sources</div>
                        <div class="sources-list" id="sources-list-${index}"></div>
                    </div>
                `;
                workersGrid.appendChild(card);
            });
            break;
            
        case "worker_completed":
            logMessage(`Worker Agent ${event.index + 1} completed research on: "${event.sub_question.substring(0, 40)}..."`, 'success');
            updateWorkerCard(event.index, 'completed', event.summary, event.sources);
            break;
            
        case "worker_failed":
            logMessage(`Worker Agent ${event.index + 1} failed: ${event.message}`, 'error');
            updateWorkerCard(event.index, 'failed', `Error: ${event.message}`, []);
            break;

        // Capability 1: VeritasCore Paper Intelligence
        case "veritas_paper_summarizing":
            pipelineStatusText.textContent = "Extracting Paper Intelligence";
            statusPulse.className = "pulse-indicator purple";
            pipelineProgress.style.width = "55%";
            logMessage(event.message, 'active');
            break;

        case "veritas_paper_summaries":
            pipelineProgress.style.width = "65%";
            logMessage(`VeritasCore extracted structured intelligence from ${event.summaries.length} research papers.`, 'success');
            updateBadge('papers', String(event.summaries.length));
            renderPaperSummaries(event.summaries);
            break;
            
        case "synthesizing":
            pipelineStatusText.textContent = "Synthesizing Cited Report";
            statusPulse.className = "pulse-indicator blue";
            pipelineProgress.style.width = "75%";
            updateBadge('report', 'Drafting...');
            switchCapabilityTab('report');
            logMessage(event.message, 'active');
            break;

        case "synthesizing_chunk":
            if (activeReportText === "") {
                finalReportContent.innerHTML = "";
            }
            activeReportText += event.chunk;
            finalReportContent.innerHTML = marked.parse(activeReportText);
            break;

        case "synthesizing_reset":
            activeReportText = "";
            finalReportContent.innerHTML = '<div class="loading-state"><div class="mini-spinner"></div><span>Draft reset. Revising report based on critique...</span></div>';
            logMessage("Draft reset for evidence re-alignment...", 'info');
            break;

        // Capability 2: Evidence DNA
        case "veritas_linking_dna":
            pipelineStatusText.textContent = "Tracing Evidence DNA";
            statusPulse.className = "pulse-indicator blue";
            pipelineProgress.style.width = "82%";
            logMessage(event.message, 'active');
            break;

        case "veritas_evidence_dna":
            pipelineProgress.style.width = "88%";
            logMessage(`VeritasCore mapped ${event.dna.length} claims to verbatim passages in the research papers.`, 'success');
            updateBadge('dna', String(event.dna.length));
            renderEvidenceDNA(event.dna);
            break;

        // Capability 3: Claim-Level Verification
        case "veritas_verifying_claims":
            pipelineStatusText.textContent = "Verifying Claims & Evidence Grounding";
            statusPulse.className = "pulse-indicator purple";
            pipelineProgress.style.width = "92%";
            logMessage(event.message, 'active');
            break;

        case "veritas_verification":
            pipelineProgress.style.width = "96%";
            logMessage(`VeritasCore claim audit finished. Evidence Integrity Score: ${event.audit.integrity_score}%.`, 'success');
            updateBadge('audit', `${event.audit.integrity_score}%`);
            renderClaimAudit(event.audit);
            break;

        case "critic_reviewing":
            pipelineStatusText.textContent = "Critic Reviewing Against Audit";
            statusPulse.className = "pulse-indicator purple";
            pipelineProgress.style.width = "98%";
            logMessage(event.message, 'active');
            break;

        case "critic_verdict":
            if (event.verdict === "revision_needed") {
                logMessage(`Critic Review Verdict: <strong>REVISION NEEDED</strong>. Feedback: <em>${escapeHtml(event.feedback)}</em>`, 'warning');
            } else {
                logMessage(`Critic Review Verdict: <strong>APPROVED</strong>. Feedback: <em>${escapeHtml(event.feedback)}</em>`, 'success');
            }
            break;
            
        case "completed":
            logMessage("Research Pipeline & VeritasCore Evidence Verification fully completed.", 'success');
            activeReportText = event.final_report;
            finalReportContent.innerHTML = marked.parse(activeReportText);

            if (event.veritas) {
                if (event.veritas.paper_summaries && event.veritas.paper_summaries.length > 0) {
                    updateBadge('papers', String(event.veritas.paper_summaries.length));
                    renderPaperSummaries(event.veritas.paper_summaries);
                }
                if (event.veritas.evidence_dna && event.veritas.evidence_dna.length > 0) {
                    updateBadge('dna', String(event.veritas.evidence_dna.length));
                    renderEvidenceDNA(event.veritas.evidence_dna);
                }
                if (event.veritas.audit_report) {
                    if (event.veritas.audit_report.integrity_score !== undefined) {
                        updateBadge('audit', `${event.veritas.audit_report.integrity_score}%`);
                    }
                    renderClaimAudit(event.veritas.audit_report);
                }
            }
            
            const dbMsg = event.session_id ? ` (Saved to Database as Session #${event.session_id})` : "";
            updateBadge('report', 'Complete');
            terminatePipelineRun("Research Completed", `VeritasCore intelligence and audit verified.${dbMsg}`, "green");
            fetchHistory();
            break;
            
        case "error":
            logMessage(`Pipeline Error: ${event.message}`, 'error');
            terminatePipelineRun("Failed", `Error: ${event.message}`, "red");
            break;
    }
}

// ---------------------------------------------------------------------------
// VeritasCore Renderers
// ---------------------------------------------------------------------------

// 1. Render Research Paper Summaries
function renderPaperSummaries(summaries) {
    if (!summaries || summaries.length === 0) {
        papersGrid.innerHTML = '<div class="loading-state"><span>No research papers summarized for this query.</span></div>';
        return;
    }
    papersGrid.innerHTML = "";

    summaries.forEach((paper, idx) => {
        const card = document.createElement('div');
        card.className = "paper-card";
        
        const findingsList = (paper.key_findings || []).map(f => `<li>${escapeHtml(f)}</li>`).join('');

        card.innerHTML = `
            <div class="paper-header">
                <div class="paper-title-line">
                    <span class="paper-badge">Paper ${idx + 1}</span>
                    <a href="${escapeHtml(paper.url)}" target="_blank" class="paper-title-link">
                        ${escapeHtml(paper.title)}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="ext-icon"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
                    </a>
                </div>
                <div class="paper-meta">
                    <span><strong>Authors/Venue:</strong> ${escapeHtml(paper.authors || 'Research Lab')}</span> • 
                    <span><strong>Year:</strong> ${escapeHtml(paper.year || '2024')}</span>
                </div>
            </div>
            <div class="paper-body">
                <div class="paper-block">
                    <span class="paper-block-title">🎯 Core Objective & Hypothesis</span>
                    <p>${escapeHtml(paper.objective)}</p>
                </div>
                <div class="paper-block">
                    <span class="paper-block-title">🔬 Methodology & Architecture</span>
                    <p>${escapeHtml(paper.methodology)}</p>
                </div>
                <div class="paper-block">
                    <span class="paper-block-title">📊 Key Quantitative Findings</span>
                    <ul class="paper-findings-list">${findingsList}</ul>
                </div>
                ${paper.limitations ? `
                <div class="paper-block limitations">
                    <span class="paper-block-title">⚠️ Identified Constraints & Limitations</span>
                    <p>${escapeHtml(paper.limitations)}</p>
                </div>` : ''}
            </div>
        `;
        papersGrid.appendChild(card);
    });
}

// 2. Render Evidence DNA
function renderEvidenceDNA(dnaItems) {
    if (!dnaItems || dnaItems.length === 0) {
        dnaContainer.innerHTML = '<div class="loading-state"><span>No Evidence DNA links generated for this query.</span></div>';
        return;
    }
    dnaContainer.innerHTML = "";

    dnaItems.forEach((dna, idx) => {
        const card = document.createElement('div');
        card.className = "dna-card";

        const alignClass = dna.grounding_alignment === "Direct Corroboration" ? "direct" : 
                          (dna.grounding_alignment === "Contextual Inference" ? "contextual" : "partial");
        const confPercent = Math.round((dna.confidence_score || 0.9) * 100);

        card.innerHTML = `
            <div class="dna-header">
                <div class="dna-tag-row">
                    <span class="dna-badge">Claim DNA #${idx + 1}</span>
                    <span class="alignment-pill ${alignClass}">${escapeHtml(dna.grounding_alignment || 'Direct Corroboration')}</span>
                </div>
                <div class="confidence-indicator" title="Grounding Confidence Score">
                    <span class="conf-label">Confidence:</span>
                    <div class="conf-bar-bg">
                        <div class="conf-bar-fill" style="width: ${confPercent}%"></div>
                    </div>
                    <span class="conf-text">${confPercent}%</span>
                </div>
            </div>

            <div class="dna-claim-text">
                <span class="quote-symbol">“</span>${escapeHtml(dna.claim_text)}<span class="quote-symbol">”</span>
            </div>

            <div class="dna-evidence-box">
                <div class="dna-source-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="source-icon"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15z"/></svg>
                    <span>Supporting Paper:</span>
                    <a href="${escapeHtml(dna.source_url)}" target="_blank">${escapeHtml(dna.source_title)}</a>
                </div>
                <div class="verbatim-passage">
                    <span class="passage-lbl">Verbatim Grounding Passage:</span>
                    <blockquote>"${escapeHtml(dna.verbatim_passage)}"</blockquote>
                </div>
            </div>
        `;
        dnaContainer.appendChild(card);
    });
}

// 3. Render Claim-Level Verification Audit
function renderClaimAudit(audit) {
    if (!audit || !audit.claims || audit.claims.length === 0) {
        auditClaimsContainer.innerHTML = '<div class="loading-state"><span>No claim verification audit items available.</span></div>';
        return;
    }
    auditClaimsContainer.innerHTML = "";

    // Set metrics
    auditIntegrityScore.textContent = `${audit.integrity_score || 100}%`;
    auditSupportedCount.textContent = audit.supported_claims || 0;
    auditUnsupportedCount.textContent = audit.unsupported_claims || 0;
    auditContradictoryCount.textContent = audit.contradictory_claims || 0;
    auditNeedsResearchCount.textContent = audit.needs_research_claims || 0;

    countAllEl.textContent = audit.total_claims || audit.claims.length;
    countSupportedEl.textContent = audit.supported_claims || 0;
    countUnsupportedEl.textContent = audit.unsupported_claims || 0;
    countContradictoryEl.textContent = audit.contradictory_claims || 0;
    countNeedsResearchEl.textContent = audit.needs_research_claims || 0;

    currentAuditClaims = audit.claims;

    audit.claims.forEach((item, idx) => {
        const card = document.createElement('div');
        const verdict = (item.verdict || "SUPPORTED").toUpperCase();
        card.className = `claim-audit-card ${verdict.toLowerCase().replace(/_/g, '-')}`;
        card.setAttribute('data-verdict', verdict);

        let verdictBadge = "";
        if (verdict === "SUPPORTED") {
            verdictBadge = '<span class="audit-verdict-badge supported">✅ SUPPORTED</span>';
        } else if (verdict === "UNSUPPORTED") {
            verdictBadge = '<span class="audit-verdict-badge unsupported">❌ UNSUPPORTED LEAP</span>';
        } else if (verdict === "CONTRADICTORY") {
            verdictBadge = '<span class="audit-verdict-badge contradictory">⚠️ CONTRADICTORY FINDINGS</span>';
        } else {
            verdictBadge = '<span class="audit-verdict-badge needs-research">🔍 NEEDS FURTHER RESEARCH</span>';
        }

        const sourcesList = (item.supporting_sources && item.supporting_sources.length > 0)
            ? item.supporting_sources.map(s => `<span class="claim-source-chip">${escapeHtml(s)}</span>`).join(' ')
            : '<span class="no-source">No supporting citations found</span>';

        card.innerHTML = `
            <div class="audit-card-header">
                <span class="claim-id-pill">Claim #${idx + 1}</span>
                ${verdictBadge}
            </div>

            <div class="audit-claim-content">
                <p class="audit-claim-text">${escapeHtml(item.claim_text)}</p>
                <p class="audit-verdict-expl"><strong>Verification Assessment:</strong> ${escapeHtml(item.verdict_explanation)}</p>
            </div>

            ${item.conflicting_evidence ? `
            <div class="audit-conflict-box">
                <span class="box-title">⚡ Contradictory Evidence in Literature:</span>
                <p>${escapeHtml(item.conflicting_evidence)}</p>
            </div>` : ''}

            ${item.open_questions ? `
            <div class="audit-research-box">
                <span class="box-title">🔬 Open Research Questions:</span>
                <p>${escapeHtml(item.open_questions)}</p>
            </div>` : ''}

            <div class="audit-supporting-row">
                <span class="row-label">Corroborating Sources:</span>
                <div class="sources-wrap">${sourcesList}</div>
            </div>
        `;

        auditClaimsContainer.appendChild(card);
    });

    applyClaimFilter();
}

// Update individual worker cards during research
function updateWorkerCard(index, status, summary, sources) {
    const card = document.getElementById(`worker-card-${index}`);
    if (!card) return;
    
    card.className = `worker-card ${status}`;
    
    const statusEl = card.querySelector('.worker-status');
    statusEl.textContent = status;
    statusEl.className = `worker-status ${status}`;
    
    const summaryEl = card.querySelector('.worker-summary');
    summaryEl.textContent = summary;
    
    if (status === 'completed' && sources && sources.length > 0) {
        const sourcesDiv = document.getElementById(`worker-sources-${index}`);
        const sourcesList = document.getElementById(`sources-list-${index}`);
        
        sourcesDiv.classList.remove('hidden');
        sourcesList.innerHTML = "";
        
        sources.forEach(src => {
            const link = document.createElement('a');
            link.className = "source-link";
            link.href = src.url;
            link.target = "_blank";
            link.textContent = src.title || src.url;
            link.title = `${src.title}
(${src.url})`;
            sourcesList.appendChild(link);
        });
    }
}

// Stop execution wrapper
function terminatePipelineRun(statusText, logText, pulseColor) {
    stopTimer();
    pipelineStatusText.textContent = statusText;
    statusPulse.className = `pulse-indicator ${pulseColor}`;
    pipelineProgress.style.width = "100%";
    
    logMessage(logText, pulseColor === "green" ? 'success' : 'error');
    logMessage("Pipeline execution finalized. VeritasCore inspection complete.", 'info');
    
    runBtn.disabled = false;
    runBtn.querySelector('span').textContent = "Execute Pipeline";
    runBtn.style.opacity = "1";
    
    if (eventSource) {
        eventSource.close();
    }
}

// ---------------------------------------------------------------------------
// Persistent SQLite History Management
// ---------------------------------------------------------------------------

async function fetchHistory() {
    try {
        const res = await fetch(`${getApiBase()}/api/history?limit=50`);
        if (!res.ok) throw new Error("Database request failed");
        const data = await res.json();
        sessionHistory = data.history || [];
        renderHistory();
    } catch (err) {
        console.error("Error fetching history from SQLite:", err);
        historyList.innerHTML = '<p class="empty-history">Could not connect to history database.</p>';
    }
}

function renderHistory() {
    if (!sessionHistory || sessionHistory.length === 0) {
        historyList.innerHTML = '<p class="empty-history">No saved research sessions yet.</p>';
        return;
    }

    historyList.innerHTML = "";
    sessionHistory.forEach(item => {
        const div = document.createElement('div');
        div.className = "history-item";
        div.setAttribute('data-id', item.id);

        let dateDisplay = item.created_at || "Recent";
        try {
            const d = new Date(item.created_at);
            if (!isNaN(d.getTime())) {
                dateDisplay = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ', ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
            }
        } catch (_) {}

        div.innerHTML = `
            <div class="history-item-top">
                <span class="history-time">${escapeHtml(dateDisplay)}</span>
                <div class="history-badges">
                    <span class="history-duration">${escapeHtml(item.duration || "00:00")}</span>
                    <button class="history-delete-btn" title="Delete session from database" data-id="${item.id}">✕</button>
                </div>
            </div>
            <div class="history-query" title="${escapeHtml(item.query)}">${escapeHtml(item.query)}</div>
        `;

        div.addEventListener('click', (e) => {
            if (e.target.classList.contains('history-delete-btn')) {
                e.stopPropagation();
                handleDeleteHistory(item.id);
                return;
            }
            document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
            div.classList.add('active');
            loadHistoryItem(item.id);
        });

        historyList.appendChild(div);
    });
}

async function loadHistoryItem(sessionId) {
    try {
        logMessage(`Loading session #${sessionId} from SQLite database...`, 'info');
        const res = await fetch(`${getApiBase()}/api/history/${sessionId}`);
        if (!res.ok) throw new Error("Failed to load session details");
        const data = await res.json();
        const item = data.session;

        queryInput.value = item.query;
        activeReportText = item.final_report;
        elapsedTimer.textContent = item.duration || "00:00.0";

        dashboardResults.classList.remove('hidden');
        pipelineStatusText.textContent = `Restored Session #${sessionId}`;
        statusPulse.className = "pulse-indicator green";
        pipelineProgress.style.width = "100%";

        statusLogs.innerHTML = `<div class="log-entry success">Restored session #${sessionId} from SQLite database (Created: ${item.created_at}, Duration: ${item.duration})</div>`;

        // Restore Orchestrator sub-questions
        if (item.sub_questions && item.sub_questions.length > 0) {
            subQuestionsContainer.innerHTML = "";
            item.sub_questions.forEach((q, index) => {
                const chip = document.createElement('div');
                chip.className = "question-chip";
                chip.innerHTML = `
                    <span class="question-num">${index + 1}</span>
                    <span class="question-text">${escapeHtml(q)}</span>
                `;
                subQuestionsContainer.appendChild(chip);
            });
        }

        // Restore Worker cards
        if (item.worker_results && item.worker_results.length > 0) {
            workersGrid.innerHTML = "";
            item.worker_results.forEach((w, wIdx) => {
                const card = document.createElement('div');
                card.className = "worker-card completed";
                card.innerHTML = `
                    <div class="worker-header">
                        <span class="worker-name">Worker Agent ${wIdx + 1}</span>
                        <span class="worker-status completed">completed</span>
                    </div>
                    <p class="worker-question">${escapeHtml(w.sub_question)}</p>
                    <div class="worker-summary">${escapeHtml(w.summary)}</div>
                    <div class="worker-sources" id="hist-sources-${wIdx}">
                        <div class="worker-sources-title">Referenced Sources</div>
                        <div class="sources-list" id="hist-sources-list-${wIdx}"></div>
                    </div>
                `;
                workersGrid.appendChild(card);

                const sourcesList = card.querySelector(`#hist-sources-list-${wIdx}`);
                if (w.sources) {
                    w.sources.forEach(src => {
                        const link = document.createElement('a');
                        link.className = "source-link";
                        link.href = src.url;
                        link.target = "_blank";
                        link.textContent = src.title || src.url;
                        sourcesList.appendChild(link);
                    });
                }
            });
        }

        // Restore VeritasCore Paper Intelligence
        renderPaperSummaries(item.paper_summaries || []);

        // Restore Final Synthesized Report
        finalReportContent.innerHTML = marked.parse(activeReportText);

        // Restore VeritasCore Evidence DNA
        renderEvidenceDNA(item.evidence_dna || []);

        // Restore VeritasCore Claim-Level Verification Audit
        renderClaimAudit(item.audit_report || {});

        // Update all badges for restored session
        updateBadge('report', 'Complete');
        updateBadge('papers', String((item.paper_summaries || []).length));
        updateBadge('dna', String((item.evidence_dna || []).length));
        const auditScore = (item.audit_report && item.audit_report.integrity_score !== undefined) ? `${item.audit_report.integrity_score}%` : '100%';
        updateBadge('audit', auditScore);
        updateBadge('pipeline', `${(item.sub_questions || []).length} Tasks`);
        
        switchCapabilityTab('report');
    } catch (err) {
        console.error("Error loading history session:", err);
        logMessage(`Error loading session #${sessionId}: ${err.message}`, 'error');
    }
}

async function handleDeleteHistory(sessionId) {
    if (!confirm(`Delete research session #${sessionId} from database?`)) return;
    try {
        const res = await fetch(`${getApiBase()}/api/history/${sessionId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error("Failed to delete");
        fetchHistory();
        logMessage(`Session #${sessionId} deleted from SQLite database.`, 'info');
    } catch (err) {
        alert("Failed to delete session: " + err.message);
    }
}

async function handleClearAllHistory() {
    if (!confirm("Are you sure you want to clear all research history from the SQLite database? This cannot be undone.")) return;
    try {
        const res = await fetch(`${getApiBase()}/api/history`, { method: 'DELETE' });
        if (!res.ok) throw new Error("Failed to clear history");
        fetchHistory();
        logMessage("All research history cleared from SQLite database.", 'info');
    } catch (err) {
        alert("Failed to clear history: " + err.message);
    }
}

// Copy to Clipboard
function copyReportToClipboard() {
    if (!activeReportText) return;
    navigator.clipboard.writeText(activeReportText).then(() => {
        const originalText = copyBtn.innerHTML;
        copyBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-small-icon"><polyline points="20 6 9 17 4 12"></polyline></svg>
            Copied!
        `;
        setTimeout(() => {
            copyBtn.innerHTML = originalText;
        }, 2000);
    }).catch(err => {
        console.error('Could not copy report:', err);
    });
}

// Download Markdown File
function downloadReportMarkdown() {
    if (!activeReportText) return;
    const blob = new Blob([activeReportText], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    
    const querySlug = queryInput.value.trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .substring(0, 30);
    link.setAttribute("download", `research_report_${querySlug || 'draft'}.md`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Escape HTML utility
function escapeHtml(unsafe) {
    if (unsafe === undefined || unsafe === null) return "";
    return String(unsafe)
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}
