// Elementos de Navegação/Dashboard
const dashboard = document.getElementById('dashboard');
const moduleOracle = document.getElementById('module-oracle');
const moduleConverter = document.getElementById('module-converter');
const moduleGenerator = document.getElementById('module-generator');

const btnGotoOracle = document.getElementById('btn-goto-oracle');
const btnGotoConverter = document.getElementById('btn-goto-converter');
const btnGotoGenerator = document.getElementById('btn-goto-generator');
const btnBackNodes = document.querySelectorAll('.btn-back');

// Elementos do Módulo A: Oráculo
const jsonUpload = document.getElementById('jsonUpload');
const errorOverlay = document.getElementById('error-overlay');
const errorMessage = document.getElementById('error-message');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatFile = document.getElementById('chat-file');
const attachmentPreview = document.getElementById('attachment-preview');
const attachmentName = document.getElementById('attachment-name');
const btnRemoveAttachment = document.getElementById('btn-remove-attachment');
const btnExportPdf = document.getElementById('btn-export-pdf');
const btnClearChat = document.getElementById('btn-clear-chat');

// Elementos de Métricas e Status do Arquivo
const loadedFilename = document.getElementById('loaded-filename');
const loadedStatus = document.getElementById('loaded-status');
const statNodes = document.getElementById('stat-nodes');
const statGateways = document.getElementById('stat-gateways');
const statEdges = document.getElementById('stat-edges');
const statScripts = document.getElementById('stat-scripts');
const statApis = document.getElementById('stat-apis');

// Elementos do Módulo B: Conversor (Ocultado visualmente por enquanto)
const dropzone = document.getElementById('dropzone');
const drawioUpload = document.getElementById('drawioUpload');
const converterLoading = document.getElementById('converter-loading');
const downloadBox = document.getElementById('download-box');
const btnDownload = document.getElementById('btn-download');

// Elementos do Módulo C: Gerador Inteligente BPMN
const generatorText = document.getElementById('generator-text');
const generatorDropzone = document.getElementById('generator-dropzone');
const generatorDropzoneLabel = document.getElementById('generator-dropzone-label');
const generatorMediaUpload = document.getElementById('generator-media-upload');
const btnGenerateFlow = document.getElementById('btn-generate-flow');
const generatorLoading = document.getElementById('generator-loading');
const generatorDownloadBox = document.getElementById('generator-download-box');
const btnGeneratorDownload = document.getElementById('btn-generator-download');
const btnExportSvg = document.getElementById('btn-export-svg');
const refineInput = document.getElementById('refine-input');
const btnRefine = document.getElementById('btn-refine');
const refineLoading = document.getElementById('refine-loading');

// Estado Global da Aplicação
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://localhost:5000' 
    : `http://${window.location.hostname}:5000`;

let currentFlowData = null;
let currentAttachedFile = null;
let rawJsonFlow = null;
let selectedModel = 'gemini:gemini-3.5-flash'; // Padrão

let chatHistory = []; // Armazena mensagens da sessão atual (Oráculo)
let bpmnViewer = null; // Instância global do bpmn-js
let lastGeneratedFlow = null; // Guarda o JSON do fluxo gerado pela IA no módulo C
let lastGeneratedXml = null; // Guarda o XML do BPMN gerado

// Helper para obter headers de autorização caso o token exista no localStorage
function getAuthHeaders(headers = {}) {
    const token = localStorage.getItem('nexus_flow_token');
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

// Controle de bloqueio e status dos modelos de IA (Quota/Rate Limit)
const modelQuotaBlocks = {}; 

function handleModelQuotaExceeded(modelName, retryAfter, quotaType) {
    // Reconstrói a chave padrão
    const modelKey = modelName.startsWith('gemini:') || modelName.startsWith('ollama:') || modelName.startsWith('foundry:') 
        ? modelName 
        : `gemini:${modelName}`;
        
    const blockDuration = quotaType === 'day' ? 86400 : retryAfter; // Se for diário, bloqueia por 24h (86400s)
    modelQuotaBlocks[modelKey] = {
        blockedUntil: Date.now() + (blockDuration * 1000),
        quotaType: quotaType
    };
    
    // Atualizar labels imediatamente
    updateModelSelectorLabels();
}

function updateModelSelectorLabels() {
    const selectors = document.querySelectorAll('.model-selector');
    const now = Date.now();
    
    selectors.forEach(select => {
        const options = select.querySelectorAll('option');
        options.forEach(opt => {
            const modelVal = opt.value;
            const block = modelQuotaBlocks[modelVal];
            
            // Texto original base (limpar labels antigas de bloqueio)
            let baseText = opt.textContent;
            if (baseText.includes(' (Indisponível - ')) {
                baseText = baseText.split(' (Indisponível - ')[0];
            }
            
            if (block && block.blockedUntil > now) {
                opt.disabled = true;
                if (block.quotaType === 'day') {
                    opt.textContent = `${baseText} (Indisponível - Esgotado hoje)`;
                } else {
                    const secondsLeft = Math.ceil((block.blockedUntil - now) / 1000);
                    opt.textContent = `${baseText} (Indisponível - Aguardar ${secondsLeft}s)`;
                }
            } else {
                opt.disabled = false;
                opt.textContent = baseText;
                if (block) {
                    delete modelQuotaBlocks[modelVal];
                }
            }
        });
    });
}

// Roda a verificação de status a cada 1 segundo
setInterval(updateModelSelectorLabels, 1000);

// Verifica o status de todas as IAs Gemini ao inicializar a página
async function checkAllModelsStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/check-models`, {
            method: 'GET',
            headers: getAuthHeaders()
        });
        if (!response.ok) return;
        
        const data = await response.json();
        
        for (const [modelName, status] of Object.entries(data)) {
            if (!status.available && status.error === "Cota excedida") {
                handleModelQuotaExceeded(modelName, status.retry_after, status.quota_type);
            }
        }
    } catch (e) {
        console.warn("Erro ao checar status inicial dos modelos:", e);
    }
}

// Executa o check inicial e agenda polling a cada 60 segundos
document.addEventListener('DOMContentLoaded', () => {
    checkAllModelsStatus();
});
setInterval(checkAllModelsStatus, 60000);

// ==========================================
// 1. LÓGICA DE NAVEGAÇÃO E TRANSIÇÕES (SPA)
// ==========================================

function showSection(sectionShow) {
    // Esconder todos
    dashboard.classList.add('hidden');
    dashboard.classList.remove('flex');
    moduleOracle.classList.add('hidden');
    moduleConverter.classList.add('hidden');
    moduleGenerator.classList.add('hidden');
    
    // Reset de opacidade para efeito fade-in
    sectionShow.classList.remove('opacity-0');
    sectionShow.classList.add('opacity-100');
    
    if (sectionShow === dashboard) {
        dashboard.classList.add('flex');
        dashboard.classList.remove('hidden');
    } else {
        sectionShow.classList.remove('hidden');
    }
}

btnGotoOracle.addEventListener('click', () => showSection(moduleOracle));
// Módulo de conversão desabilitado visualmente, mas mapeado por compatibilidade
if (btnGotoConverter) {
    btnGotoConverter.addEventListener('click', () => showSection(moduleConverter));
}
btnGotoGenerator.addEventListener('click', () => showSection(moduleGenerator));

btnBackNodes.forEach(btn => {
    btn.addEventListener('click', () => showSection(dashboard));
});

// Sincronizar seletores de modelo de IA
const modelSelectors = document.querySelectorAll('.model-selector');
modelSelectors.forEach(select => {
    select.addEventListener('change', (e) => {
        selectedModel = e.target.value;
        // Mantém todos os seletores com o mesmo valor ativo
        modelSelectors.forEach(s => s.value = selectedModel);
    });
});

// ==========================================
// 2. MÓDULO A: ORÁCULO DE MANUTENÇÃO
// ==========================================

function showError(message) {
    console.error("Erro detectado:", message);
    errorMessage.textContent = message;
    errorOverlay.classList.remove('hidden');
    errorOverlay.classList.add('flex');
    
    setTimeout(() => {
        errorOverlay.classList.add('hidden');
        errorOverlay.classList.remove('flex');
    }, 5000);
}

// Ativar/Desativar inputs do Chat
function enableChat() {
    chatInput.removeAttribute('disabled');
    chatSend.removeAttribute('disabled');
    chatFile.removeAttribute('disabled');
    chatInput.placeholder = "Pergunte ao Oráculo sobre o fluxo...";
}

function disableChat() {
    chatInput.setAttribute('disabled', 'true');
    chatSend.setAttribute('disabled', 'true');
    chatFile.setAttribute('disabled', 'true');
    chatInput.placeholder = "Carregue um chatbot JSON primeiro...";
    currentFlowData = null;
    rawJsonFlow = null;
    chatHistory = [];
    btnExportPdf.classList.add('hidden');
    btnClearChat.classList.add('hidden');
    
    // Reset de Métricas
    loadedFilename.textContent = "Nenhum arquivo";
    loadedStatus.textContent = "Aguardando JSON...";
    statNodes.textContent = "-";
    statGateways.textContent = "-";
    statEdges.textContent = "-";
    statScripts.textContent = "-";
    statApis.textContent = "-";
}

// Salvar e carregar histórico de conversas via LocalStorage (Melhoria 3)
function saveChatHistory(fileName, history) {
    localStorage.setItem(`chat_history_${fileName}`, JSON.stringify(history));
}

function loadChatHistory(fileName) {
    const historyRaw = localStorage.getItem(`chat_history_${fileName}`);
    if (historyRaw) {
        try {
            chatHistory = JSON.parse(historyRaw);
            chatMessages.innerHTML = ''; // Limpa aviso padrão
            chatHistory.forEach(msg => {
                addMessage(msg.sender, msg.text);
            });
            btnExportPdf.classList.remove('hidden');
            btnClearChat.classList.remove('hidden');
        } catch (e) {
            console.error("Erro ao ler histórico:", e);
            chatHistory = [];
            btnExportPdf.classList.add('hidden');
            btnClearChat.classList.add('hidden');
        }
    } else {
        chatHistory = [];
        btnExportPdf.classList.add('hidden');
        btnClearChat.classList.add('hidden');
        chatMessages.innerHTML = `
            <div class="bg-slate-800/40 border border-slate-800/60 rounded-xl p-6 text-center text-xs text-slate-400 italic max-w-md mx-auto my-auto shadow-inner">
                Faça o upload do fluxo em JSON para liberar o Oráculo. Faça perguntas sobre a lógica do robô ou anexe PDFs/Áudios para suporte completo.
            </div>
        `;
    }
}

// Mensagem no chat
function addMessage(sender, text) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);
    
    // Ajuste de layout baseado no remetente (Tailwind styles)
    if (sender === 'user') {
        messageDiv.className = 'message user bg-blue-600 text-white max-w-[85%] px-4 py-2.5 rounded-xl rounded-br-none self-end text-sm leading-relaxed shadow-md animate-fade-in';
        messageDiv.textContent = text;
    } else if (sender === 'ai') {
        messageDiv.className = 'message ai bg-slate-800 text-slate-100 max-w-[85%] px-4 py-2.5 rounded-xl rounded-bl-none self-start text-sm leading-relaxed border border-slate-700/50 shadow-md animate-fade-in';
        
        // Renderizar Markdown
        messageDiv.innerHTML = marked.parse(text);
        
        // Aplicar classes do Tailwind nos elementos gerados pelo Markdown para manter a interface Premium
        const lists = messageDiv.querySelectorAll('ul');
        lists.forEach(ul => ul.className = 'list-disc pl-5 my-2 flex flex-col gap-1 text-slate-300');
        
        const orderedLists = messageDiv.querySelectorAll('ol');
        orderedLists.forEach(ol => ol.className = 'list-decimal pl-5 my-2 flex flex-col gap-1 text-slate-300');
        
        const headings = messageDiv.querySelectorAll('h1, h2, h3, h4');
        headings.forEach(h => h.className = 'font-semibold text-blue-400 mt-3 mb-1 text-sm border-b border-slate-700/30 pb-0.5');
        
        const paragraphs = messageDiv.querySelectorAll('p');
        paragraphs.forEach((p, idx) => {
            if (idx > 0) p.className = 'mt-2';
        });

        const codeBlocks = messageDiv.querySelectorAll('pre');
        codeBlocks.forEach(pre => {
            pre.className = 'bg-slate-950 p-3 rounded-lg overflow-x-auto font-mono text-xs text-sky-400 border border-slate-800 my-2';
        });

        const inlineCode = messageDiv.querySelectorAll('code:not(pre code)');
        inlineCode.forEach(c => {
            c.className = 'bg-slate-900 px-1.5 py-0.5 rounded font-mono text-pink-400 text-xs';
        });
    } else {
        messageDiv.className = 'message system text-slate-500 text-xs italic self-center text-center my-1 animate-fade-in';
        messageDiv.textContent = text;
    }
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageDiv;
}

// Calcular estatísticas lógicas do JSON do chatbot
function computeFlowStats(flow) {
    let nodesCount = 0;
    let gatewaysCount = 0;
    let edgesCount = 0;
    let scriptsCount = 0;
    let apisCount = 0;

    flow.forEach(item => {
        const isEdge = item.edge === 1 || 'source' in item;
        const cod = item.cod_componente;

        if (isEdge) {
            edgesCount++;
        } else {
            nodesCount++;
            // Identificar Decisões/Gateways pelo código ou palavra chave
            if (cod === 15 || cod === 8 || (item.value && item.value.toLowerCase().includes('gateway')) || (item.data && item.data.identifier && item.data.identifier.startsWith('dec'))) {
                gatewaysCount++;
            } else if (cod === 19) {
                scriptsCount++;
            } else if (cod === 9) {
                apisCount++;
            }
        }
    });

    statNodes.textContent = nodesCount;
    statGateways.textContent = gatewaysCount;
    statEdges.textContent = edgesCount;
    statScripts.textContent = scriptsCount;
    statApis.textContent = apisCount;
}

// Upload do JSON do chatbot
jsonUpload.addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    try {
        const fileContent = await file.text();
        let jsonData;
        
        try {
            jsonData = JSON.parse(fileContent);
        } catch (e) {
            showError("O arquivo selecionado não é um JSON válido.");
            return;
        }

        if (jsonData && Array.isArray(jsonData.flow)) {
            currentFlowData = jsonData.flow;
            rawJsonFlow = jsonData; // Armazena o JSON original completo
            enableChat();
            
            // Atualizar UI com informações do arquivo
            loadedFilename.textContent = file.name;
            loadedStatus.textContent = "Pronto para análise";
            
            // Computar estatísticas do fluxo
            computeFlowStats(jsonData.flow);
            
            // Carregar histórico de conversa persistido
            loadChatHistory(file.name);
            
            // Se o histórico local estiver vazio, exibe saudação do sistema
            if (!chatHistory.length) {
                addMessage("system", `Fluxo "${file.name}" carregado com sucesso! Pergunte algo para depurar o chatbot.`);
            }
        } else {
            throw new Error("Estrutura JSON inválida: Chave 'flow' não encontrada.");
        }

    } catch (error) {
        showError(error.message);
        disableChat();
    } finally {
        jsonUpload.value = '';
    }
});

// Gerenciamento de Arquivos no Chat (Mídia / Documento)
chatFile.addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (!file) return;

    currentAttachedFile = file;
    attachmentName.textContent = file.name;
    attachmentPreview.classList.remove('hidden');
    attachmentPreview.classList.add('flex');
});

btnRemoveAttachment.addEventListener('click', () => {
    currentAttachedFile = null;
    chatFile.value = '';
    attachmentPreview.classList.add('hidden');
    attachmentPreview.classList.remove('flex');
});

// Envio de pergunta ao Oráculo com suporte a Streaming (Melhoria 2)
async function sendChatMessage() {
    const question = chatInput.value.trim();
    if (!question || !currentFlowData) return;

    let userMsgText = question;
    if (currentAttachedFile) {
        userMsgText += ` (Anexo: ${currentAttachedFile.name})`;
    }
    
    addMessage('user', userMsgText);
    chatHistory.push({ sender: 'user', text: userMsgText });
    saveChatHistory(loadedFilename.textContent, chatHistory);
    
    chatInput.value = '';

    // Adiciona o typing indicator
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message ai bg-slate-800 text-slate-100 max-w-[85%] px-4 py-2.5 rounded-xl rounded-bl-none self-start text-sm leading-relaxed border border-slate-700/50 shadow-md animate-fade-in flex gap-1 items-center';
    loadingDiv.innerHTML = `
        <div class="flex gap-1 py-1">
            <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style="animation-delay: -0.3s"></span>
            <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style="animation-delay: -0.15s"></span>
            <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"></span>
        </div>
    `;
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Bloqueia campos
    chatInput.disabled = true;
    chatSend.disabled = true;
    const previousAttachedFile = currentAttachedFile;
    
    // Limpar anexo da UI imediatamente
    currentAttachedFile = null;
    chatFile.value = '';
    attachmentPreview.classList.add('hidden');

    try {
        const formData = new FormData();
        formData.append('question', question);
        formData.append('flow_data', JSON.stringify(currentFlowData));
        
        if (previousAttachedFile) {
            formData.append('file', previousAttachedFile);
        }

        // Requisição para a rota de streaming /chat-stream
        const response = await fetch(`${API_BASE_URL}/chat-stream`, {
            method: 'POST',
            headers: getAuthHeaders({
                'X-Provider-Model': selectedModel
            }),
            body: formData
        });

        if (loadingDiv.parentNode) {
            chatMessages.removeChild(loadingDiv);
        }

        if (!response.ok) {
            let errorMsg = "Erro de resposta da IA.";
            let retryAfter = null;
            let quotaType = null;
            let errModel = null;
            try {
                const errorData = await response.json();
                if (errorData.error) errorMsg = errorData.error;
                if (errorData.retry_after) retryAfter = errorData.retry_after;
                if (errorData.quota_type) quotaType = errorData.quota_type;
                if (errorData.model) errModel = errorData.model;
            } catch(e) {}
            
            if (response.status === 429 && errModel) {
                handleModelQuotaExceeded(errModel, retryAfter, quotaType);
            }
            throw new Error(errorMsg);
        }

        // Ler a resposta do Server-Sent Events progressivamente
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let partialText = '';
        
        // Adiciona um container de mensagem de IA vazio que será preenchido
        const aiMessageDiv = addMessage('ai', '');
        btnExportPdf.classList.remove('hidden');
        btnClearChat.classList.remove('hidden');

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const parsedData = JSON.parse(line.substring(6));
                        
                        if (parsedData.error) {
                            if (parsedData.retry_after && parsedData.model) {
                                handleModelQuotaExceeded(parsedData.model, parsedData.retry_after, parsedData.quota_type);
                            }
                            throw new Error(parsedData.error);
                        }
                        
                        if (parsedData.token) {
                            partialText += parsedData.token;
                            aiMessageDiv.innerHTML = marked.parse(partialText);
                            
                            // Re-aplicar classes do Tailwind nos elementos Markdown dinâmicos
                            aiMessageDiv.querySelectorAll('ul').forEach(ul => ul.className = 'list-disc pl-5 my-2 flex flex-col gap-1 text-slate-300');
                            aiMessageDiv.querySelectorAll('ol').forEach(ol => ol.className = 'list-decimal pl-5 my-2 flex flex-col gap-1 text-slate-300');
                            aiMessageDiv.querySelectorAll('h1, h2, h3, h4').forEach(h => h.className = 'font-semibold text-blue-400 mt-3 mb-1 text-sm border-b border-slate-700/30 pb-0.5');
                            aiMessageDiv.querySelectorAll('pre').forEach(pre => pre.className = 'bg-slate-950 p-3 rounded-lg overflow-x-auto font-mono text-xs text-sky-400 border border-slate-800 my-2');
                            aiMessageDiv.querySelectorAll('code:not(pre code)').forEach(c => c.className = 'bg-slate-900 px-1.5 py-0.5 rounded font-mono text-pink-400 text-xs');
                            
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        }
                    } catch (e) {
                        console.warn("Parse parcial falhou:", e);
                    }
                }
            }
        }

        // Salvar a resposta final gerada no histórico
        if (partialText) {
            chatHistory.push({ sender: 'ai', text: partialText });
            saveChatHistory(loadedFilename.textContent, chatHistory);
        }

    } catch (error) {
        if (loadingDiv.parentNode) {
            chatMessages.removeChild(loadingDiv);
        }
        addMessage('ai', `⚠️ Erro ao consultar o Oráculo: ${error.message}`);
    } finally {
        chatInput.disabled = false;
        chatSend.disabled = false;
        chatInput.focus();
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

chatSend.addEventListener('click', sendChatMessage);
chatInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        sendChatMessage();
    }
});

// Exportação do Chat do Oráculo para PDF usando jsPDF (Melhoria 9)
btnExportPdf.addEventListener('click', () => {
    if (!chatHistory.length) return;
    
    try {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        
        doc.setFillColor(15, 23, 42); // Cor escura igual ao background (slate-950)
        doc.rect(0, 0, 220, 20, "F");
        
        doc.setTextColor(255, 255, 255);
        doc.setFont("Helvetica", "bold");
        doc.setFontSize(14);
        doc.text("RELATÓRIO DE ANÁLISE - ORÁCULO DE MANUTENÇÃO", 14, 13);
        
        doc.setTextColor(51, 65, 85);
        doc.setFont("Helvetica", "normal");
        doc.setFontSize(9);
        doc.text(`Arquivo do Fluxo: ${loadedFilename.textContent}`, 14, 28);
        doc.text(`Data de Geração: ${new Date().toLocaleString()}`, 14, 33);
        doc.line(14, 36, 196, 36);
        
        let y = 44;
        const pageHeight = doc.internal.pageSize.height;
        
        chatHistory.forEach(msg => {
            const isUser = msg.sender === 'user';
            
            // Desenhar caixa de remetente
            doc.setFont("Helvetica", "bold");
            doc.setFontSize(9);
            doc.setTextColor(isUser ? 37 : 71, isUser ? 99 : 85, isUser ? 235 : 105);
            doc.text(isUser ? "USUÁRIO" : "ORÁCULO (IA)", 14, y);
            y += 5;
            
            // Texto da mensagem
            doc.setTextColor(15, 23, 42);
            doc.setFont("Helvetica", "normal");
            doc.setFontSize(9.5);
            
            const lines = doc.splitTextToSize(msg.text, 182);
            lines.forEach(line => {
                if (y > pageHeight - 15) {
                    doc.addPage();
                    y = 20;
                }
                doc.text(line, 14, y);
                y += 5.2;
            });
            y += 4.5; // Espaço extra entre balões de mensagens
        });
        
        doc.save(`analise_${loadedFilename.textContent.replace('.json', '')}.pdf`);
    } catch (e) {
        showError("Erro ao exportar PDF: " + e.message);
    }
});

// Limpar histórico do Chat no Oráculo (Melhoria requisitada)
btnClearChat.addEventListener('click', () => {
    const fileName = loadedFilename.textContent;
    if (!fileName || fileName === "Nenhum arquivo") return;

    if (confirm(`Deseja realmente limpar todo o histórico de conversas do fluxo "${fileName}"?`)) {
        chatHistory = [];
        localStorage.removeItem(`chat_history_${fileName}`);
        
        // Limpa mensagens e restaura o aviso inicial padrão
        chatMessages.innerHTML = `
            <div class="bg-slate-800/40 border border-slate-800/60 rounded-xl p-6 text-center text-xs text-slate-400 italic max-w-md mx-auto my-auto shadow-inner">
                Faça o upload do fluxo em JSON para liberar o Oráculo. Faça perguntas sobre a lógica do robô ou anexe PDFs/Áudios para suporte completo.
            </div>
        `;
        
        btnExportPdf.classList.add('hidden');
        btnClearChat.classList.add('hidden');
    }
});

// ==========================================
// 3. MÓDULO B: CONVERSOR DRAW.IO (DESABILITADO VISUALMENTE)
// ==========================================
if (dropzone) {
    dropzone.addEventListener('click', () => {
        drawioUpload.click();
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('border-indigo-500', 'bg-indigo-950/20');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('border-indigo-500', 'bg-indigo-950/20');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('border-indigo-500', 'bg-indigo-950/20');
        if (e.dataTransfer.files.length > 0) {
            handleDrawioFile(e.dataTransfer.files[0]);
        }
    });

    drawioUpload.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleDrawioFile(e.target.files[0]);
        }
    });
}

async function handleDrawioFile(file) {
    if (!file.name.endsWith('.drawio') && !file.name.endsWith('.xml')) {
        alert("Por favor, selecione apenas arquivos do formato .drawio ou .xml");
        return;
    }

    downloadBox.classList.add('hidden');
    converterLoading.classList.remove('hidden');
    dropzone.classList.add('opacity-55', 'pointer-events-none');

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/convert-drawio`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: formData
        });

        if (!response.ok) {
            let errorMsg = "Erro na conversão do arquivo.";
            try {
                const errData = await response.json();
                if (errData.error) errorMsg = errData.error;
            } catch(e) {}
            throw new Error(errorMsg);
        }

        const convertedJson = await response.json();
        const blob = new Blob([JSON.stringify(convertedJson, null, 4)], { type: 'application/json' });
        const downloadUrl = URL.createObjectURL(blob);
        
        btnDownload.href = downloadUrl;
        downloadBox.classList.remove('hidden');

    } catch (err) {
        alert("Erro na conversão: " + err.message);
    } finally {
        converterLoading.classList.add('hidden');
        dropzone.classList.remove('opacity-55', 'pointer-events-none');
        drawioUpload.value = '';
    }
}

// ==========================================
// 4. MÓDULO C: GERADOR INTELIGENTE BPMN
// ==========================================

let selectedGeneratorFile = null;

// Inicializa e renderiza o diagrama BPMN no Canvas (Melhoria 1)
function renderBPMN(xmlString) {
    const container = document.getElementById('bpmn-canvas');
    if (!bpmnViewer) {
        // Usa o BpmnJS carregado pela CDN no index.html
        bpmnViewer = new BpmnJS({ container: container });
    }
    
    bpmnViewer.importXML(xmlString).then(() => {
        const canvas = bpmnViewer.get('canvas');
        canvas.zoom('fit-viewport');
    }).catch(err => {
        console.error("Erro ao renderizar diagrama BPMN:", err);
    });
}

// Click na dropzone aciona o input file
generatorDropzone.addEventListener('click', () => {
    generatorMediaUpload.click();
});

// Drag and drop events
generatorDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    generatorDropzone.classList.add('border-emerald-500', 'bg-emerald-950/20');
});

generatorDropzone.addEventListener('dragleave', () => {
    generatorDropzone.classList.remove('border-emerald-500', 'bg-emerald-950/20');
});

generatorDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    generatorDropzone.classList.remove('border-emerald-500', 'bg-emerald-950/20');
    if (e.dataTransfer.files.length > 0) {
        handleGeneratorFile(e.dataTransfer.files[0]);
    }
});

generatorMediaUpload.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleGeneratorFile(e.target.files[0]);
    }
});

function handleGeneratorFile(file) {
    selectedGeneratorFile = file;
    generatorDropzoneLabel.textContent = `Arquivo selecionado: ${file.name}`;
}

btnGenerateFlow.addEventListener('click', async () => {
    const textDescription = generatorText.value.trim();
    
    if (!textDescription && !selectedGeneratorFile) {
        alert("Por favor, digite uma descrição em texto ou selecione um arquivo (Áudio, Imagem ou PDF).");
        return;
    }

    // Ocultar resultados anteriores e mostrar loading
    generatorDownloadBox.classList.add('hidden');
    generatorLoading.classList.remove('hidden');
    btnGenerateFlow.classList.add('opacity-55', 'pointer-events-none');
    generatorDropzone.classList.add('opacity-55', 'pointer-events-none');
    generatorText.classList.add('opacity-55', 'pointer-events-none');

    try {
        const formData = new FormData();
        if (textDescription) {
            formData.append('description', textDescription);
        }
        if (selectedGeneratorFile) {
            formData.append('file', selectedGeneratorFile);
        }

        const response = await fetch(`${API_BASE_URL}/generate-multimodal`, {
            method: 'POST',
            headers: getAuthHeaders({
                'X-Provider-Model': selectedModel
            }),
            body: formData
        });

        if (!response.ok) {
            let errorMsg = "Erro ao gerar o diagrama BPMN.";
            let retryAfter = null;
            let quotaType = null;
            let errModel = null;
            try {
                const errData = await response.json();
                if (errData.error) errorMsg = errData.error;
                if (errData.retry_after) retryAfter = errData.retry_after;
                if (errData.quota_type) quotaType = errData.quota_type;
                if (errData.model) errModel = errData.model;
            } catch(e) {}
            
            if (response.status === 429 && errModel) {
                handleModelQuotaExceeded(errModel, retryAfter, quotaType);
            }
            throw new Error(errorMsg);
        }

        // Captura o XML bruto do BPMN
        const xmlText = await response.text();
        lastGeneratedXml = xmlText;

        // Captura o JSON do fluxo retornado via Header de resposta exposto (Melhoria 4)
        const flowHeader = response.headers.get('X-Flow-JSON');
        if (flowHeader) {
            lastGeneratedFlow = JSON.parse(flowHeader);
        }

        // Criar link de download para baixar o arquivo .bpmn
        const blob = new Blob([xmlText], { type: 'application/xml' });
        const downloadUrl = URL.createObjectURL(blob);
        btnGeneratorDownload.href = downloadUrl;
        
        // Exibir download box
        generatorDownloadBox.classList.remove('hidden');

        // Renderizar o BPMN graficamente na tela
        setTimeout(() => {
            renderBPMN(xmlText);
        }, 100);

    } catch (err) {
        alert("Erro na geração inteligente: " + err.message);
    } finally {
        generatorLoading.classList.add('hidden');
        btnGenerateFlow.classList.remove('opacity-55', 'pointer-events-none');
        generatorDropzone.classList.remove('opacity-55', 'pointer-events-none');
        generatorText.classList.remove('opacity-55', 'pointer-events-none');
    }
});

// Exportar Diagrama BPMN como Imagem SVG (Melhoria 9)
btnExportSvg.addEventListener('click', () => {
    if (!bpmnViewer) return;
    
    bpmnViewer.saveSVG().then(({ svg }) => {
        const blob = new Blob([svg], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'fluxo_bpmn.svg';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }).catch(err => {
        alert("Erro ao exportar SVG: " + err);
    });
});

// Refinamento Iterativo de Fluxo via Prompts (Melhoria 4)
btnRefine.addEventListener('click', async () => {
    const instruction = refineInput.value.trim();
    if (!instruction) {
        alert("Digite o que deseja ajustar no fluxo gerado.");
        return;
    }
    if (!lastGeneratedFlow) {
        alert("Não há nenhum fluxo gerado disponível para refinamento.");
        return;
    }

    refineLoading.classList.remove('hidden');
    btnRefine.classList.add('opacity-55', 'pointer-events-none');
    refineInput.disabled = true;

    try {
        const response = await fetch(`${API_BASE_URL}/refine-flow`, {
            method: 'POST',
            headers: getAuthHeaders({
                'Content-Type': 'application/json',
                'X-Provider-Model': selectedModel
            }),
            body: JSON.stringify({
                flow: lastGeneratedFlow,
                instruction: instruction
            })
        });

        if (!response.ok) {
            let errorMsg = "Erro ao refinar o fluxo.";
            let retryAfter = null;
            let quotaType = null;
            let errModel = null;
            try {
                const errData = await response.json();
                if (errData.error) errorMsg = errData.error;
                if (errData.retry_after) retryAfter = errData.retry_after;
                if (errData.quota_type) quotaType = errData.quota_type;
                if (errData.model) errModel = errData.model;
            } catch(e) {}
            
            if (response.status === 429 && errModel) {
                handleModelQuotaExceeded(errModel, retryAfter, quotaType);
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();
        
        // Atualiza o estado local do fluxo e XML
        lastGeneratedFlow = data.flow;
        lastGeneratedXml = data.bpmn_xml;

        // Atualiza o link de download
        const blob = new Blob([data.bpmn_xml], { type: 'application/xml' });
        const downloadUrl = URL.createObjectURL(blob);
        btnGeneratorDownload.href = downloadUrl;

        // Renderiza o novo BPMN modificado
        renderBPMN(data.bpmn_xml);
        refineInput.value = '';

    } catch (err) {
        alert("Erro ao refinar fluxo: " + err.message);
    } finally {
        refineLoading.classList.add('hidden');
        btnRefine.classList.remove('opacity-55', 'pointer-events-none');
        refineInput.disabled = false;
    }
});
