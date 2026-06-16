

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

// Elementos de Métricas e Status do Arquivo
const loadedFilename = document.getElementById('loaded-filename');
const loadedStatus = document.getElementById('loaded-status');
const statNodes = document.getElementById('stat-nodes');
const statGateways = document.getElementById('stat-gateways');
const statEdges = document.getElementById('stat-edges');
const statScripts = document.getElementById('stat-scripts');
const statApis = document.getElementById('stat-apis');

// Elementos do Módulo B: Conversor
const dropzone = document.getElementById('dropzone');
const drawioUpload = document.getElementById('drawioUpload');
const converterLoading = document.getElementById('converter-loading');
const downloadBox = document.getElementById('download-box');
const btnDownload = document.getElementById('btn-download');

// Estado Global da Aplicação
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://localhost:5000' 
    : `http://${window.location.hostname}:5000`;

let currentFlowData = null;
let currentAttachedFile = null;
let rawJsonFlow = null;
let selectedModel = 'gemini:gemini-3.5-flash'; // Padrão

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
btnGotoConverter.addEventListener('click', () => showSection(moduleConverter));
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
    
    // Reset de Métricas
    loadedFilename.textContent = "Nenhum arquivo";
    loadedStatus.textContent = "Aguardando JSON...";
    statNodes.textContent = "-";
    statGateways.textContent = "-";
    statEdges.textContent = "-";
    statScripts.textContent = "-";
    statApis.textContent = "-";
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
            
            addMessage("system", `Fluxo "${file.name}" carregado com sucesso! Pergunte algo para depurar o chatbot.`);
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

// Envio de pergunta ao Oráculo
async function sendChatMessage() {
    const question = chatInput.value.trim();
    if (!question || !currentFlowData) return;

    let userMsgText = question;
    if (currentAttachedFile) {
        userMsgText += ` (Anexo: ${currentAttachedFile.name})`;
    }
    
    addMessage('user', userMsgText);
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
        // Envia via FormData para suportar binários
        const formData = new FormData();
        formData.append('question', question);
        formData.append('flow_data', JSON.stringify(currentFlowData));
        
        if (previousAttachedFile) {
            formData.append('file', previousAttachedFile);
        }

        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'X-Provider-Model': selectedModel
            },
            body: formData
        });

        if (loadingDiv.parentNode) {
            chatMessages.removeChild(loadingDiv);
        }

        if (!response.ok) {
            let errorMsg = "Erro de resposta da IA.";
            try {
                const errorData = await response.json();
                if (errorData.error) errorMsg = errorData.error;
            } catch(e) {}
            throw new Error(errorMsg);
        }

        const data = await response.json();
        addMessage('ai', data.response);

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

// ==========================================
// 3. MÓDULO B: CONVERSOR DRAW.IO
// ==========================================

// Click na dropzone aciona o input file
dropzone.addEventListener('click', () => {
    drawioUpload.click();
});

// Drag and drop events
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

// Processar arquivo do Draw.io
async function handleDrawioFile(file) {
    if (!file.name.endsWith('.drawio') && !file.name.endsWith('.xml')) {
        alert("Por favor, selecione apenas arquivos do formato .drawio ou .xml");
        return;
    }

    // Ocultar resultados anteriores
    downloadBox.classList.add('hidden');
    
    // Mostrar animação de processamento
    converterLoading.classList.remove('hidden');
    dropzone.classList.add('opacity-55', 'pointer-events-none');

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/convert-drawio`, {
            method: 'POST',
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

        // Criar link para baixar o JSON
        const blob = new Blob([JSON.stringify(convertedJson, null, 4)], { type: 'application/json' });
        const downloadUrl = URL.createObjectURL(blob);
        
        btnDownload.href = downloadUrl;
        
        // Exibir download box
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

const generatorText = document.getElementById('generator-text');
const generatorDropzone = document.getElementById('generator-dropzone');
const generatorDropzoneLabel = document.getElementById('generator-dropzone-label');
const generatorMediaUpload = document.getElementById('generator-media-upload');
const btnGenerateFlow = document.getElementById('btn-generate-flow');
const generatorLoading = document.getElementById('generator-loading');
const generatorDownloadBox = document.getElementById('generator-download-box');
const btnGeneratorDownload = document.getElementById('btn-generator-download');

let selectedGeneratorFile = null;

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
            headers: {
                'X-Provider-Model': selectedModel
            },
            body: formData
        });

        if (!response.ok) {
            let errorMsg = "Erro ao gerar o diagrama BPMN.";
            try {
                const errData = await response.json();
                if (errData.error) errorMsg = errData.error;
            } catch(e) {}
            throw new Error(errorMsg);
        }

        // Recebe o XML do BPMN como texto
        const xmlText = await response.text();

        // Criar link para baixar o arquivo BPMN (.bpmn)
        const blob = new Blob([xmlText], { type: 'application/xml' });
        const downloadUrl = URL.createObjectURL(blob);
        
        btnGeneratorDownload.href = downloadUrl;
        
        // Exibir download box
        generatorDownloadBox.classList.remove('hidden');

    } catch (err) {
        alert("Erro na geração inteligente: " + err.message);
    } finally {
        generatorLoading.classList.add('hidden');
        btnGenerateFlow.classList.remove('opacity-55', 'pointer-events-none');
        generatorDropzone.classList.remove('opacity-55', 'pointer-events-none');
        generatorText.classList.remove('opacity-55', 'pointer-events-none');
    }
});
