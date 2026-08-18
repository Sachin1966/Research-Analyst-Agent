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

const synthesizerSection = document.getElementById('synthesizer-section');
const finalReportContent = document.getElementById('final-report-content');
const copyBtn = document.getElementById('copy-btn');
const downloadBtn = document.getElementById('download-btn');
const historyList = document.getElementById('history-list');

// State Variables
let timerInterval = null;
let startTime = 0;
let eventSource = null;
let activeSubQuestions = [];
let sessionHistory = [];
let activeReportText = ""; // Keep raw Markdown for copying/downloading

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchConfig();
    fetchModels();
    
    runBtn.addEventListener('click', startResearchPipeline);
    copyBtn.addEventListener('click', copyReportToClipboard);
    downloadBtn.addEventListener('click', downloadReportMarkdown);
    
    // Allow pressing Enter key to run query
    queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            startResearchPipeline();
        }
    });
});

// Fetch system configurations and set statuses
async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) throw new Error("Config endpoint returned error");
        const config = await response.json();
        
        // Update badges
        if (config.llm_demo_mode) {
            ollamaStatus.textContent = "Offline (Demo)";
            ollamaStatus.className = "status-badge demo";
        } else {
            ollamaStatus.textContent = "Online";
            ollamaStatus.className = "status-badge live";
        }

        if (config.tavily_key_configured) {
            tavilyStatus.textContent = "Live Search";
            tavilyStatus.className = "status-badge live";
        } else {
            tavilyStatus.textContent = "Canned Search";
            tavilyStatus.className = "status-badge demo";
        }

        if (config.llm_demo_mode) {
            modeStatus.textContent = "DEMO MODE";
            modeStatus.className = "status-badge demo";
        } else {
            modeStatus.textContent = "LIVE MODE";
            modeStatus.className = "status-badge live";
        }
    } catch (error) {
        console.error("Error fetching config:", error);
        ollamaStatus.textContent = "Error";
        ollamaStatus.className = "status-badge offline";
        tavilyStatus.textContent = "Error";
        tavilyStatus.className = "status-badge offline";
        modeStatus.textContent = "Offline";
        modeStatus.className = "status-badge offline";
    }
}

// Fetch available Ollama models
async function fetchModels() {
    try {
        const response = await fetch('/api/models');
        if (!response.ok) throw new Error("Models endpoint error");
        const data = await response.json();
        
        modelSelect.innerHTML = '';
        
        if (data.models && data.models.length > 0) {
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                // Preselect llama3 if it is present, otherwise preselect first model
                if (model.startsWith('llama3')) {
                    option.selected = true;
                }
                modelSelect.appendChild(option);
            });
            // Re-fetch config to check statuses again
            fetchConfig();
        } else {
            const option = document.createElement('option');
            option.value = "";
            option.textContent = "No models found (Using Demo)";
            modelSelect.appendChild(option);
        }
    } catch (error) {
        console.error("Error fetching models:", error);
        modelSelect.innerHTML = '<option value="">Offline (Demo Fallback)</option>';
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
    
    // Get timestamp
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');
    
    entry.innerHTML = `<span style="color: var(--text-muted)">[${timeStr}]</span> ${text}`;
    
    // Remove 'active' state from previous logs
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
    runBtn.querySelector('span').textContent = "Researching...";
    runBtn.style.opacity = "0.7";
    
    dashboardResults.classList.remove('hidden');
    
    // Status indicators
    statusPulse.className = "pulse-indicator blue";
    pipelineStatusText.textContent = "Initializing...";
    pipelineProgress.style.width = "5%";
    
    statusLogs.innerHTML = "";
    logMessage("Initiating multi-agent research network pipeline...", 'info');
    
    orchestratorSection.classList.add('hidden');
    subQuestionsContainer.innerHTML = "";
    
    workersSection.classList.add('hidden');
    workersGrid.innerHTML = "";
    
    synthesizerSection.classList.add('hidden');
    finalReportContent.innerHTML = "";
    activeReportText = "";
    
    startTimer();
    activeSubQuestions = [];

    // 2. Open Server-Sent Events (SSE) Stream
    const encodedQuery = encodeURIComponent(query);
    const modelParam = selectedModel ? `&model=${encodeURIComponent(selectedModel)}` : '';
    const sseUrl = `/api/research/stream?query=${encodedQuery}${modelParam}`;
    
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
        logMessage("SSE Stream connection encountered an unexpected interruption or finished.", 'warning');
        
        // Check if finished or actual error
        if (pipelineStatusText.textContent !== "Research Completed" && pipelineStatusText.textContent !== "Failed") {
            logMessage("Pipeline connection closed abruptly. Terminating runner.", 'error');
            terminatePipelineRun("Failed", "Connection closed prematurely", "red");
        }
        
        eventSource.close();
    };
}

// Event Router for SSE
function handlePipelineEvent(event) {
    switch (event.status) {
        case "decomposing":
            pipelineStatusText.textContent = "Orchestrating Task";
            statusPulse.className = "pulse-indicator blue";
            pipelineProgress.style.width = "15%";
            logMessage(event.message, 'active');
            break;
            
        case "sub_questions":
            activeSubQuestions = event.sub_questions;
            pipelineStatusText.textContent = "Task Decomposed";
            pipelineProgress.style.width = "30%";
            logMessage(`Orchestrator successfully decomposed query into ${activeSubQuestions.length} sub-tasks.`, 'success');
            
            // Show Orchestrator Card
            orchestratorSection.classList.remove('hidden');
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
            pipelineStatusText.textContent = "Concurrent Researching";
            statusPulse.className = "pulse-indicator amber";
            pipelineProgress.style.width = "45%";
            logMessage(`Initializing ${event.count} specialized Worker Agents. Booting search interfaces...`, 'active');
            
            // Show Workers Card & Initialize grids with 'Searching' placeholders
            workersSection.classList.remove('hidden');
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
            
        case "synthesizing":
            pipelineStatusText.textContent = "Synthesizing Report";
            statusPulse.className = "pulse-indicator blue";
            pipelineProgress.style.width = "75%";
            logMessage(event.message, 'active');
            break;

        case "synthesizing_chunk":
            pipelineStatusText.textContent = "Synthesizing Report";
            statusPulse.className = "pulse-indicator blue";
            pipelineProgress.style.width = "80%";
            if (synthesizerSection.classList.contains('hidden')) {
                synthesizerSection.classList.remove('hidden');
                setTimeout(() => {
                    synthesizerSection.scrollIntoView({ behavior: 'smooth', block: 'end' });
                }, 100);
            }
            activeReportText += event.chunk;
            finalReportContent.innerHTML = marked.parse(activeReportText);
            break;

        case "synthesizing_reset":
            activeReportText = "";
            finalReportContent.innerHTML = "";
            logMessage("Draft reset. Redrafting report...", 'info');
            break;

        case "critic_reviewing":
            pipelineStatusText.textContent = "Critic Reviewing";
            statusPulse.className = "pulse-indicator purple";
            pipelineProgress.style.width = "90%";
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
            logMessage("Synthesizer successfully merged all worker results and drafted final report.", 'success');
            activeReportText = event.final_report;
            
            // Render Markdown
            finalReportContent.innerHTML = marked.parse(activeReportText);
            synthesizerSection.classList.remove('hidden');
            
            // Scroll to synthesizer report slowly
            setTimeout(() => {
                synthesizerSection.scrollIntoView({ behavior: 'smooth' });
            }, 300);
            
            // Terminate run
            terminatePipelineRun("Research Completed", "Network process completed successfully.", "green");
            
            // Save to Session History
            addToHistory(queryInput.value, activeReportText, event.worker_results);
            break;
            
        case "error":
            logMessage(`Pipeline Process Error: ${event.message}`, 'error');
            terminatePipelineRun("Failed", `Error: ${event.message}`, "red");
            break;
    }
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
            link.title = `${src.title}\n(${src.url})`;
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
    logMessage("Pipeline execution finalized. Agent thread closed.", 'info');
    
    runBtn.disabled = false;
    runBtn.querySelector('span').textContent = "Execute Pipeline";
    runBtn.style.opacity = "1";
    
    if (eventSource) {
        eventSource.close();
    }
}

// Session History Management
function addToHistory(query, report, workers) {
    const historyItem = {
        query: query,
        report: report,
        workers: workers,
        time: elapsedTimer.textContent,
        date: new Date().toLocaleTimeString()
    };
    
    sessionHistory.push(historyItem);
    renderHistory();
}

function renderHistory() {
    if (sessionHistory.length === 0) {
        historyList.innerHTML = '<p class="empty-history">No previous runs in this session.</p>';
        return;
    }
    
    historyList.innerHTML = "";
    sessionHistory.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = "history-item";
        div.textContent = `${item.date} - ${item.query}`;
        div.addEventListener('click', () => loadHistoryItem(index));
        historyList.appendChild(div);
    });
}

function loadHistoryItem(index) {
    const item = sessionHistory[index];
    
    // Restore states
    queryInput.value = item.query;
    activeReportText = item.report;
    elapsedTimer.textContent = item.time;
    
    dashboardResults.classList.remove('hidden');
    pipelineStatusText.textContent = "Restored from History";
    statusPulse.className = "pulse-indicator green";
    pipelineProgress.style.width = "100%";
    
    statusLogs.innerHTML = `<div class="log-entry success">Restored report run from session history (Run time: ${item.time})</div>`;
    
    // Hide details cards that we didn't store fully, or show reconstructed worker results
    orchestratorSection.classList.add('hidden');
    workersSection.classList.remove('hidden');
    workersGrid.innerHTML = "";
    
    item.workers.forEach((w, wIdx) => {
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
        w.sources.forEach(src => {
            const link = document.createElement('a');
            link.className = "source-link";
            link.href = src.url;
            link.target = "_blank";
            link.textContent = src.title || src.url;
            sourcesList.appendChild(link);
        });
    });

    // Render report markdown
    finalReportContent.innerHTML = marked.parse(activeReportText);
    synthesizerSection.classList.remove('hidden');
    synthesizerSection.scrollIntoView({ behavior: 'smooth' });
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
    
    // Generate clean filename
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

