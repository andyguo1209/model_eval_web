// 全局变量
let currentStep = 1;
let uploadedFile = null;
let fileInfo = null;
let availableModels = [];
let currentTaskId = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// 初始化应用
function initializeApp() {
    setupFileUpload();
    loadAvailableModels();
    updateStepDisplay();
}

// 设置文件上传功能
function setupFileUpload() {
    const fileInput = document.getElementById('file-input');
    const uploadArea = document.getElementById('file-upload-area');

    // 文件输入变化
    fileInput.addEventListener('change', handleFileSelect);

    // 拖拽功能
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileSelect();
        }
    });

    // 点击上传区域
    uploadArea.addEventListener('click', function() {
        fileInput.click();
    });
}

// 处理文件选择
function handleFileSelect() {
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];
    
    if (!file) return;

    // 检查文件格式
    const allowedTypes = ['.xlsx', '.xls', '.csv'];
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    
    if (!allowedTypes.includes(fileExtension)) {
        showError('不支持的文件格式，请上传 .xlsx、.xls 或 .csv 文件');
        return;
    }

    uploadedFile = file;
    uploadFile(file);
}

// 上传文件
async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    showLoading('正在上传文件...');

    try {
        const response = await fetch('/upload_file', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            fileInfo = result;
            displayFileInfo(result);
            showSuccess('文件上传成功！');
        } else {
            showError(result.error || '文件上传失败');
        }
    } catch (error) {
        showError('网络错误：' + error.message);
    } finally {
        hideLoading();
    }
}

// 显示文件信息
function displayFileInfo(info) {
    const fileInfoDiv = document.getElementById('file-info');
    const previewDiv = document.getElementById('file-preview');

    let modeText = info.mode === 'objective' ? '客观题评测' : '主观题评测';
    let modeIcon = info.mode === 'objective' ? 'fa-check-circle' : 'fa-question-circle';

    let typeCountsHtml = '';
    if (Object.keys(info.type_counts).length > 0) {
        typeCountsHtml = '<h4>题目类型分布：</h4><ul>';
        for (const [type, count] of Object.entries(info.type_counts)) {
            typeCountsHtml += `<li>${type}: ${count}题</li>`;
        }
        typeCountsHtml += '</ul>';
    }

    let previewHtml = '';
    if (info.preview && info.preview.length > 0) {
        previewHtml = '<h4>数据预览：</h4><div class="preview-table"><table><thead><tr>';
        
        // 表头
        const columns = Object.keys(info.preview[0]);
        columns.forEach(col => {
            previewHtml += `<th>${col}</th>`;
        });
        previewHtml += '</tr></thead><tbody>';
        
        // 数据行
        info.preview.forEach(row => {
            previewHtml += '<tr>';
            columns.forEach(col => {
                const value = row[col] || '';
                const displayValue = String(value).length > 50 ? String(value).substring(0, 50) + '...' : value;
                previewHtml += `<td title="${value}">${displayValue}</td>`;
            });
            previewHtml += '</tr>';
        });
        
        previewHtml += '</tbody></table></div>';
    }

    previewDiv.innerHTML = `
        <div class="file-info-grid">
            <div class="info-item">
                <strong><i class="fas fa-file"></i> 文件名：</strong>
                <span>${info.filename}</span>
            </div>
            <div class="info-item">
                <strong><i class="fas ${modeIcon}"></i> 评测模式：</strong>
                <span class="mode-badge ${info.mode}">${modeText}</span>
            </div>
            <div class="info-item">
                <strong><i class="fas fa-list-ol"></i> 总题数：</strong>
                <span>${info.total_count}</span>
            </div>
            <div class="info-item">
                <strong><i class="fas fa-columns"></i> 包含列：</strong>
                <span>
                    ${info.has_answer ? '<span class="badge success">answer</span>' : ''}
                    ${info.has_type ? '<span class="badge info">type</span>' : ''}
                    <span class="badge primary">query</span>
                </span>
            </div>
        </div>
        ${typeCountsHtml}
        ${previewHtml}
    `;

    fileInfoDiv.style.display = 'block';
}

// 加载可用模型
async function loadAvailableModels() {
    try {
        const response = await fetch('/get_available_models');
        const result = await response.json();
        
        availableModels = result.models;
        displayModelList(result.models);
        
        // 检查Gemini可用性
        if (!result.gemini_available) {
            showError('未配置GOOGLE_API_KEY环境变量，无法进行评测');
        }
    } catch (error) {
        showError('获取模型列表失败：' + error.message);
    }
}

// 显示模型列表
function displayModelList(models) {
    const modelList = document.getElementById('model-list');
    
    modelList.innerHTML = models.map(model => `
        <div class="model-item ${model.available ? '' : 'disabled'}" 
             data-model="${model.name}" 
             onclick="${model.available ? `toggleModel('${model.name}')` : ''}">
            <div class="model-name">${model.name}</div>
            <div class="model-status ${model.available ? 'available' : 'unavailable'}">
                <i class="fas ${model.available ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                ${model.available ? '可用' : '不可用'}
            </div>
            ${!model.available ? `<div class="model-env-hint">需配置 ${model.token_env}</div>` : ''}
        </div>
    `).join('');
    
    updateStartButton();
}

// 切换模型选择
function toggleModel(modelName) {
    const modelItem = document.querySelector(`[data-model="${modelName}"]`);
    if (!modelItem || modelItem.classList.contains('disabled')) return;
    
    modelItem.classList.toggle('selected');
    updateStartButton();
}

// 更新开始按钮状态
function updateStartButton() {
    const selectedModels = document.querySelectorAll('.model-card.selected');
    const startBtn = document.getElementById('start-btn');
    
    startBtn.disabled = selectedModels.length === 0;
}

// 切换模型选择状态
function toggleModelSelection(modelName, modelCard) {
    // 切换选中状态
    modelCard.classList.toggle('selected');
    
    // 更新按钮状态
    updateStartButton();
}

// 步骤导航
function nextStep() {
    if (currentStep < 4) {
        currentStep++;
        updateStepDisplay();
    }
}

function prevStep() {
    if (currentStep > 1) {
        currentStep--;
        updateStepDisplay();
    }
}

// 更新步骤显示
function updateStepDisplay() {
    // 更新步骤指示器
    document.querySelectorAll('.step').forEach((step, index) => {
        const stepNum = index + 1;
        step.classList.remove('active', 'completed');
        
        if (stepNum < currentStep) {
            step.classList.add('completed');
        } else if (stepNum === currentStep) {
            step.classList.add('active');
        }
    });

    // 显示对应的内容区域
    document.querySelectorAll('.section').forEach((section, index) => {
        section.classList.remove('active');
        if (index + 1 === currentStep) {
            section.classList.add('active');
        }
    });
}

// 开始评测
async function startEvaluation() {
    const selectedModels = Array.from(document.querySelectorAll('.model-card.selected'))
        .map(item => item.dataset.model);
    
    const evalMode = document.querySelector('input[name="eval-mode"]:checked').value;
    
    if (selectedModels.length === 0) {
        showError('请至少选择一个模型');
        return;
    }

    if (!fileInfo) {
        showError('请先上传文件');
        return;
    }

    const requestData = {
        filename: fileInfo.filename,
        selected_models: selectedModels,
        force_mode: evalMode
    };

    try {
        const response = await fetch('/start_evaluation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        const result = await response.json();

        if (result.success) {
            currentTaskId = result.task_id;
            nextStep(); // 进入进度页面
            startProgressMonitoring();
            showSuccess('评测任务已启动');
        } else {
            showError(result.error || '启动评测失败');
        }
    } catch (error) {
        showError('网络错误：' + error.message);
    }
}

// 开始进度监控
function startProgressMonitoring() {
    if (!currentTaskId) return;

    const interval = setInterval(async () => {
        try {
            const response = await fetch(`/task_status/${currentTaskId}`);
            const status = await response.json();

            if (response.ok) {
                updateProgressDisplay(status);

                if (status.status === '完成') {
                    clearInterval(interval);
                    onEvaluationComplete(status);
                } else if (status.status === '失败') {
                    clearInterval(interval);
                    onEvaluationFailed(status);
                }
            } else {
                clearInterval(interval);
                showError('获取任务状态失败');
            }
        } catch (error) {
            clearInterval(interval);
            showError('网络错误：' + error.message);
        }
    }, 2000);
}

// 更新进度显示
function updateProgressDisplay(status) {
    const progressFill = document.getElementById('progress-fill');
    const progressPercent = document.getElementById('progress-percent');
    const progressDetail = document.getElementById('progress-detail');
    const currentStatus = document.getElementById('current-status');
    const elapsedTime = document.getElementById('elapsed-time');
    const evalModeDisplay = document.getElementById('eval-mode-display');
    const selectedModelsDisplay = document.getElementById('selected-models-display');

    const percentage = status.total > 0 ? Math.round((status.progress / status.total) * 100) : 0;
    
    progressFill.style.width = percentage + '%';
    progressPercent.textContent = percentage + '%';
    progressDetail.textContent = status.current_step;
    currentStatus.textContent = status.status;
    elapsedTime.textContent = status.elapsed_time;
    evalModeDisplay.textContent = status.evaluation_mode === 'objective' ? '客观题评测' : '主观题评测';
    selectedModelsDisplay.textContent = status.selected_models.join(', ');

    // 添加到日志
    addToLog(`[${new Date().toLocaleTimeString()}] ${status.current_step}`);
}

// 添加到日志
function addToLog(message) {
    const logContent = document.getElementById('log-content');
    logContent.innerHTML += message + '\n';
    logContent.scrollTop = logContent.scrollHeight;
}

// 评测完成
function onEvaluationComplete(status) {
    nextStep(); // 进入结果页面
    
    const resultsSummary = document.getElementById('results-summary');
    const downloadBtn = document.getElementById('download-btn');
    const viewBtn = document.getElementById('view-btn');
    
    resultsSummary.innerHTML = `
        <div class="completion-message">
            <i class="fas fa-check-circle" style="color: #28a745; font-size: 48px; margin-bottom: 15px;"></i>
            <h3>评测完成！</h3>
            <p>耗时：${status.elapsed_time}</p>
            <p>结果文件：${status.result_file}</p>
        </div>
    `;
    
    downloadBtn.onclick = () => downloadResults(status.result_file);
    viewBtn.onclick = () => viewResults(status.result_file);
    
    showSuccess('评测完成！');
}

// 评测失败
function onEvaluationFailed(status) {
    showError('评测失败：' + status.error_message);
    addToLog(`[${new Date().toLocaleTimeString()}] 评测失败：${status.error_message}`);
}

// 下载结果
function downloadResults(filename) {
    if (filename) {
        window.open(`/download/${filename}`, '_blank');
    } else {
        showError('没有可下载的文件');
    }
}

// 查看结果
function viewResults(filename) {
    if (filename) {
        window.open(`/view_results/${filename}`, '_blank');
    } else {
        showError('没有可查看的文件');
    }
}

// 重置表单
function resetForm() {
    currentStep = 1;
    uploadedFile = null;
    fileInfo = null;
    currentTaskId = null;
    
    // 重置文件输入
    document.getElementById('file-input').value = '';
    document.getElementById('file-info').style.display = 'none';
    
    // 清除模型选择
    document.querySelectorAll('.model-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    // 重置评测模式
    document.querySelector('input[name="eval-mode"][value="auto"]').checked = true;
    
    // 重置进度
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-percent').textContent = '0%';
    document.getElementById('log-content').innerHTML = '';
    
    updateStepDisplay();
    updateStartButton();
}

// 通知函数
function showError(message) {
    showNotification('error', message);
}

function showSuccess(message) {
    showNotification('success', message);
}

function showNotification(type, message) {
    const notification = document.getElementById(`${type}-notification`);
    const messageElement = document.getElementById(`${type}-message`);
    
    messageElement.textContent = message;
    notification.style.display = 'flex';
    
    // 3秒后自动隐藏
    setTimeout(() => {
        hideNotification(type);
    }, 5000);
}

function hideNotification(type) {
    const notification = document.getElementById(`${type}-notification`);
    notification.style.display = 'none';
}

// 加载和隐藏指示器
function showLoading(message) {
    // 可以在这里添加加载指示器
    console.log('Loading:', message);
}

function hideLoading() {
    // 隐藏加载指示器
    console.log('Loading finished');
}

// 添加CSS样式到页面
const additionalCSS = `
.file-info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 15px;
    margin-bottom: 20px;
}

.info-item {
    display: flex;
    align-items: center;
    padding: 10px;
    background: #f8f9fa;
    border-radius: 6px;
    border-left: 4px solid #4CAF50;
}

.info-item strong {
    margin-right: 10px;
    color: #333;
}

.mode-badge {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
}

.mode-badge.objective {
    background: #d4edda;
    color: #155724;
}

.mode-badge.subjective {
    background: #fff3cd;
    color: #856404;
}

.badge {
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: bold;
    margin-right: 5px;
}

.badge.primary { background: #007bff; color: white; }
.badge.success { background: #28a745; color: white; }
.badge.info { background: #17a2b8; color: white; }

.preview-table {
    max-height: 300px;
    overflow: auto;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    margin-top: 10px;
}

.preview-table table {
    width: 100%;
    border-collapse: collapse;
}

.preview-table th,
.preview-table td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid #dee2e6;
    font-size: 14px;
}

.preview-table th {
    background: #f8f9fa;
    font-weight: bold;
    position: sticky;
    top: 0;
}

.completion-message {
    text-align: center;
    padding: 30px;
}

.completion-message h3 {
    color: #28a745;
    margin-bottom: 15px;
}

.completion-message p {
    color: #666;
    margin-bottom: 10px;
}
`;

// 添加CSS到页面
const style = document.createElement('style');
style.textContent = additionalCSS;
document.head.appendChild(style);

// API配置相关功能
function openApiConfig() {
    const modal = document.getElementById('api-config-modal');
    const backdrop = document.getElementById('api-config-backdrop');
    
    // 显示弹窗
    modal.style.display = 'flex';
    backdrop.style.display = 'block';
    
    // 添加动画效果
    setTimeout(() => {
        modal.style.opacity = '1';
        backdrop.style.opacity = '1';
    }, 10);
    
    // 设置表单提交事件
    const form = document.getElementById('api-config-form');
    form.onsubmit = handleApiConfigSubmit;
}

function closeApiConfig() {
    const modal = document.getElementById('api-config-modal');
    const backdrop = document.getElementById('api-config-backdrop');
    
    // 隐藏弹窗
    modal.style.opacity = '0';
    backdrop.style.opacity = '0';
    
    setTimeout(() => {
        modal.style.display = 'none';
        backdrop.style.display = 'none';
    }, 300);
}

function handleApiConfigSubmit(e) {
    e.preventDefault();
    
    const googleKey = document.getElementById('google-api-key').value;
    const hkgaiV1Key = document.getElementById('hkgai-v1-key').value;
    const hkgaiV2Key = document.getElementById('hkgai-v2-key').value;
    
    // 保存到sessionStorage (仅在当前会话有效)
    if (googleKey) {
        sessionStorage.setItem('GOOGLE_API_KEY', googleKey);
    }
    if (hkgaiV1Key) {
        sessionStorage.setItem('ARK_API_KEY_HKGAI_V1', hkgaiV1Key);
    }
    if (hkgaiV2Key) {
        sessionStorage.setItem('ARK_API_KEY_HKGAI_V2', hkgaiV2Key);
    }
    
    // 显示成功消息
    showNotification('success', 'API密钥配置已保存！请注意密钥仅在当前会话有效。');
    
    // 关闭弹窗
    closeApiConfig();
    
    // 重新加载模型状态
    loadAvailableModels();
    
    // 清空表单
    document.getElementById('api-config-form').reset();
}

// 修改loadAvailableModels函数以支持会话存储的API密钥
function loadAvailableModels() {
    // 添加会话存储的API密钥到请求头
    const headers = {
        'Content-Type': 'application/json'
    };
    
    // 从sessionStorage获取API密钥
    const googleKey = sessionStorage.getItem('GOOGLE_API_KEY');
    const hkgaiV1Key = sessionStorage.getItem('ARK_API_KEY_HKGAI_V1');
    const hkgaiV2Key = sessionStorage.getItem('ARK_API_KEY_HKGAI_V2');
    
    if (googleKey) headers['X-Google-API-Key'] = googleKey;
    if (hkgaiV1Key) headers['X-HKGAI-V1-Key'] = hkgaiV1Key;
    if (hkgaiV2Key) headers['X-HKGAI-V2-Key'] = hkgaiV2Key;
    
    fetch('/get_available_models', { headers })
        .then(response => response.json())
        .then(data => {
            availableModels = data.models || [];
            updateModelDisplay(data);
        })
        .catch(error => {
            console.error('获取模型列表失败:', error);
            showNotification('error', '获取模型列表失败，请检查网络连接');
        });
}

function updateModelDisplay(data) {
    const modelList = document.getElementById('model-list');
    const apiStatus = document.getElementById('api-status');
    
    // 检查是否有不可用的模型
    const hasUnavailableModels = data.models.some(model => !model.available) || !data.gemini_available;
    
    // 显示或隐藏API状态提示
    if (hasUnavailableModels) {
        apiStatus.style.display = 'block';
    } else {
        apiStatus.style.display = 'none';
    }
    
    // 生成模型卡片
    modelList.innerHTML = '';
    
    data.models.forEach(model => {
        const modelCard = document.createElement('div');
        modelCard.className = `model-card ${model.available ? 'available' : 'unavailable'}`;
        modelCard.dataset.model = model.name; // 添加数据属性
        
        const statusIcon = model.available ? 
            '<i class="fas fa-check-circle status-icon available"></i>' :
            '<i class="fas fa-times-circle status-icon unavailable"></i>';
        
        const statusText = model.available ? '可用' : '不可用';
        const requirementText = model.available ? '' : 
            `<div class="requirement">需配置 ${model.token_env}</div>`;
        
        modelCard.innerHTML = `
            <div class="model-header">
                <h4>${model.name}</h4>
                ${statusIcon}
            </div>
            <div class="model-status">${statusText}</div>
            ${requirementText}
        `;
        
        if (model.available) {
            modelCard.style.cursor = 'pointer';
            modelCard.addEventListener('click', () => toggleModelSelection(model.name, modelCard));
        }
        
        modelList.appendChild(modelCard);
    });
    
    // 添加Gemini状态
    const geminiCard = document.createElement('div');
    geminiCard.className = `model-card ${data.gemini_available ? 'available' : 'unavailable'}`;
    
    const geminiStatusIcon = data.gemini_available ? 
        '<i class="fas fa-check-circle status-icon available"></i>' :
        '<i class="fas fa-times-circle status-icon unavailable"></i>';
    
    const geminiStatusText = data.gemini_available ? '可用' : '不可用';
    const geminiRequirementText = data.gemini_available ? '' : 
        '<div class="requirement">需配置 GOOGLE_API_KEY</div>';
    
    geminiCard.innerHTML = `
        <div class="model-header">
            <h4>Google Gemini</h4>
            ${geminiStatusIcon}
        </div>
        <div class="model-status">${geminiStatusText}</div>
        ${geminiRequirementText}
        <div class="model-note">用于AI评分</div>
    `;
    
    modelList.appendChild(geminiCard);
    
    updateStartButton();
}
