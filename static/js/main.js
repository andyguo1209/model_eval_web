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
    loadHistoryFiles();
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
async function uploadFile(file, overwrite = false) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('overwrite', overwrite.toString());

    showLoading('正在上传文件...');

    try {
        const response = await fetch('/upload_file', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            console.log('📤 上传成功，调用displayFileInfo');
            displayFileInfo(result);
            showSuccess('文件上传成功！');
            loadHistoryFiles(); // 刷新历史文件列表
        } else if (result.error === 'file_exists') {
            // 文件已存在，询问是否覆盖
            showFileExistsDialog(result.filename, file);
        } else {
            console.error('❌ 文件上传失败:', result.error);
            showError(result.error || '文件上传失败');
        }
    } catch (error) {
        showError('网络错误：' + error.message);
    } finally {
        hideLoading();
    }
}

// 显示文件存在对话框
function showFileExistsDialog(filename, file) {
    const dialogHtml = `
        <div class="custom-alert">
            <div class="custom-alert-content">
                <div class="custom-alert-header">
                    <i class="fas fa-exclamation-triangle text-warning"></i>
                    <h4>文件已存在</h4>
                </div>
                <div class="custom-alert-body">
                    <p>文件 "<strong>${filename}</strong>" 已存在，您要如何处理？</p>
                </div>
                <div class="custom-alert-footer">
                    <button class="btn btn-secondary" onclick="closeCustomAlert()">取消</button>
                    <button class="btn btn-primary" onclick="overwriteFile('${filename}')">覆盖文件</button>
                </div>
            </div>
        </div>
    `;
    
    const alertContainer = document.createElement('div');
    alertContainer.innerHTML = dialogHtml;
    alertContainer.id = 'custom-alert-container';
    document.body.appendChild(alertContainer);
    
    // 存储文件对象以便覆盖时使用
    window.pendingFile = file;
}

// 覆盖文件
async function overwriteFile(filename) {
    closeCustomAlert();
    if (window.pendingFile) {
        await uploadFile(window.pendingFile, true);
        window.pendingFile = null;
    }
}

// 显示文件信息
function displayFileInfo(info) {
    // 确保全局变量设置
    fileInfo = info;
    console.log('✅ displayFileInfo 调用，文件信息已更新:', fileInfo);
    
    const fileInfoDiv = document.getElementById('file-info');
    const previewDiv = document.getElementById('file-preview');

    let modeText = info.mode === 'objective' ? '客观题评测' : '主观题评测';
    let modeIcon = info.mode === 'objective' ? 'fa-check-circle' : 'fa-question-circle';
    
    // 根据检测结果自动设置评测模式
    const modeRadio = document.querySelector(`input[name="eval-mode"][value="${info.mode}"]`);
    if (modeRadio) {
        modeRadio.checked = true;
        console.log('✅ 评测模式已自动设置为:', info.mode);
    }

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
    
    // 重新检查按钮状态
    console.log('🔄 文件信息显示完成，更新按钮状态');
    updateStartButton();
    
    // 自动进入下一步
    nextStep();
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
    
    console.log('🔧 生成模型列表，模型数量:', models.length);
    
    modelList.innerHTML = models.map(model => {
        console.log(`📋 处理模型: ${model.name}, 可用: ${model.available}`);
        return `
        <div class="model-card ${model.available ? 'available' : 'disabled'}" 
             data-model="${model.name}" 
             onclick="${model.available ? `toggleModel('${model.name}')` : ''}">
            <div class="model-name">${model.name}</div>
            <div class="model-status ${model.available ? 'available' : 'unavailable'}">
                <i class="fas ${model.available ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                ${model.available ? '可用' : '不可用'}
            </div>
            ${!model.available ? `<div class="model-env-hint">需配置 ${model.token_env}</div>` : ''}
        </div>
        `;
    }).join('');
    
    console.log('✅ 模型列表已生成，调用updateStartButton');
    updateStartButton();
}

// 切换模型选择
function toggleModel(modelName) {
    const modelCard = document.querySelector(`[data-model="${modelName}"]`);
    if (!modelCard || modelCard.classList.contains('disabled')) return;
    
    console.log('🎯 切换模型选择:', modelName);
    modelCard.classList.toggle('selected');
    console.log('📋 模型选中状态:', modelCard.classList.contains('selected') ? '已选中' : '未选中');
    updateStartButton();
}

// 更新开始按钮状态
function updateStartButton() {
    const selectedModels = document.querySelectorAll('.model-card.selected');
    const availableModels = document.querySelectorAll('.model-card.available');
    const startBtn = document.getElementById('start-btn');
    
    // 检查各种条件
    const hasSelection = selectedModels.length > 0;
    const hasAvailableModels = availableModels.length > 0;
    const hasFileUploaded = fileInfo !== null;
    
    // 确定按钮是否应该禁用
    const shouldDisable = !hasSelection || !hasAvailableModels || !hasFileUploaded;
    startBtn.disabled = shouldDisable;
    
    // 移除所有现有的事件监听器，重新绑定
    startBtn.onclick = null;
    
    // 为按钮添加点击事件
    if (shouldDisable) {
        startBtn.onclick = function(e) {
            e.preventDefault();
            console.log('🚫 按钮被禁用，显示原因');
            showStartButtonDisabledReason(hasFileUploaded, hasAvailableModels, hasSelection);
        };
    } else {
        startBtn.onclick = function(e) {
            e.preventDefault();
            console.log('✅ 按钮可用，调用评测函数');
            startEvaluation();
        };
    }
    
    // 调试信息
    console.log('🔍 按钮状态更新:');
    console.log('  - 文件已上传:', hasFileUploaded);
    console.log('  - 选中模型数量:', selectedModels.length);
    console.log('  - 可用模型数量:', availableModels.length);
    console.log('  - 按钮状态:', startBtn.disabled ? '禁用' : '启用');
    console.log('  - 按钮onclick函数:', startBtn.onclick ? '已绑定' : '未绑定');
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

// 显示开始按钮禁用原因
function showStartButtonDisabledReason(hasFileUploaded, hasAvailableModels, hasSelection) {
    let reasons = [];
    
    if (!hasFileUploaded) {
        reasons.push('<li><i class="fas fa-upload text-warning"></i> 请先上传评测文件</li>');
    }
    
    if (!hasAvailableModels) {
        reasons.push('<li><i class="fas fa-key text-danger"></i> 没有可用的模型，请先配置API密钥</li>');
    }
    
    if (!hasSelection) {
        reasons.push('<li><i class="fas fa-robot text-info"></i> 请至少选择一个模型进行评测</li>');
    }
    
    const reasonHtml = `
        <div class="custom-alert">
            <div class="custom-alert-content">
                <div class="custom-alert-header">
                    <i class="fas fa-exclamation-triangle text-warning"></i>
                    <h4>无法开始评测</h4>
                </div>
                <div class="custom-alert-body">
                    <p>请解决以下问题后再试：</p>
                    <ul>${reasons.join('')}</ul>
                </div>
                <div class="custom-alert-footer">
                    <button class="btn btn-primary" onclick="closeCustomAlert()">我知道了</button>
                </div>
            </div>
        </div>
    `;
    
    // 添加弹窗到页面
    const alertContainer = document.createElement('div');
    alertContainer.innerHTML = reasonHtml;
    alertContainer.id = 'custom-alert-container';
    document.body.appendChild(alertContainer);
    
    // 添加点击背景关闭功能
    alertContainer.addEventListener('click', function(e) {
        if (e.target === alertContainer) {
            closeCustomAlert();
        }
    });
}

// 关闭自定义弹窗
function closeCustomAlert() {
    const alertContainer = document.getElementById('custom-alert-container');
    if (alertContainer) {
        alertContainer.remove();
    }
}

// 切换上传选项卡
function switchUploadTab(tabName) {
    // 更新选项卡按钮状态
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    
    // 找到点击的按钮并激活
    const clickedBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => 
        btn.textContent.includes(tabName === 'new' ? '上传新文件' : '选择历史文件')
    );
    if (clickedBtn) {
        clickedBtn.classList.add('active');
    }
    
    // 显示对应的内容
    document.querySelectorAll('.upload-tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabName}-upload-tab`).classList.add('active');
    
    // 如果切换到历史文件，加载文件列表
    if (tabName === 'history') {
        loadHistoryFiles();
    }
}

// 加载历史文件列表
async function loadHistoryFiles() {
    const historyList = document.getElementById('history-files-list');
    
    try {
        const response = await fetch('/get_uploaded_files');
        const result = await response.json();
        
        if (result.success) {
            displayHistoryFiles(result.files);
        } else {
            historyList.innerHTML = '<div class="no-files">获取文件列表失败</div>';
        }
    } catch (error) {
        historyList.innerHTML = '<div class="no-files">网络错误</div>';
    }
}

// 显示历史文件列表
function displayHistoryFiles(files) {
    const historyList = document.getElementById('history-files-list');
    
    if (files.length === 0) {
        historyList.innerHTML = `
            <div class="no-files">
                <i class="fas fa-folder-open"></i>
                <p>暂无历史文件</p>
                <small>上传文件后将显示在这里</small>
            </div>
        `;
        return;
    }
    
    const filesHtml = files.map(file => `
        <div class="history-file-item" data-filename="${file.filename}">
            <div class="file-info">
                <div class="file-icon">
                    <i class="fas ${getFileIcon(file.filename)}"></i>
                </div>
                <div class="file-details">
                    <div class="file-name" title="${file.filename}">${file.filename}</div>
                    <div class="file-meta">
                        <span><i class="fas fa-clock"></i> ${file.upload_time}</span>
                        <span><i class="fas fa-hdd"></i> ${file.size_formatted}</span>
                    </div>
                </div>
            </div>
            <div class="file-actions">
                <button class="btn btn-sm btn-primary" onclick="selectHistoryFile('${file.filename}')" 
                        title="选择此文件">
                    <i class="fas fa-check"></i>
                </button>
                <button class="btn btn-sm btn-info" onclick="editFilePrompt('${file.filename}')" 
                        title="编辑提示词">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-sm btn-secondary" onclick="downloadHistoryFile('${file.filename}')" 
                        title="下载文件">
                    <i class="fas fa-download"></i>
                </button>
                <button class="btn btn-sm btn-danger" onclick="deleteHistoryFile('${file.filename}')" 
                        title="删除文件">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
    
    historyList.innerHTML = filesHtml;
}

// 获取文件图标
function getFileIcon(filename) {
    const ext = filename.toLowerCase().split('.').pop();
    switch (ext) {
        case 'xlsx':
        case 'xls':
            return 'fa-file-excel';
        case 'csv':
            return 'fa-file-csv';
        default:
            return 'fa-file';
    }
}

// 选择历史文件
async function selectHistoryFile(filename) {
    showLoading('正在加载文件...');
    
    try {
        // 构造一个虚拟的file对象，直接调用后端API分析文件
        const response = await fetch('/upload_file', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                existing_file: filename
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('✅ 历史文件加载成功，调用displayFileInfo');
            displayFileInfo(result);
            showSuccess(`已选择文件: ${filename}`);
            
            // 切换回文件上传选项卡显示结果
            switchUploadTab('new');
        } else {
            console.error('❌ 历史文件加载失败:', result.error);
            showError(result.error || '选择文件失败');
        }
    } catch (error) {
        showError('网络错误：' + error.message);
    } finally {
        hideLoading();
    }
}

// 下载历史文件
function downloadHistoryFile(filename) {
    window.open(`/download_uploaded_file/${encodeURIComponent(filename)}`, '_blank');
}

// 删除历史文件
async function deleteHistoryFile(filename) {
    if (!confirm(`确定要删除文件 "${filename}" 吗？\n此操作不可撤销。`)) {
        return;
    }
    
    try {
        const response = await fetch(`/delete_file/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess(result.message);
            loadHistoryFiles(); // 刷新文件列表
            
            // 如果删除的是当前选中的文件，清除文件信息
            if (fileInfo && fileInfo.filename === filename) {
                fileInfo = null;
                document.getElementById('file-info').style.display = 'none';
            }
        } else {
            showError(result.error || '删除文件失败');
        }
    } catch (error) {
        showError('网络错误：' + error.message);
    }
}

// 刷新历史文件
function refreshHistoryFiles() {
    loadHistoryFiles();
}

// 开始评测
async function startEvaluation() {
    console.log('🚀 开始评测');
    
    const selectedModels = Array.from(document.querySelectorAll('.model-card.selected'))
        .map(item => item.dataset.model);
    
    const evalMode = document.querySelector('input[name="eval-mode"]:checked').value;
    
    // 验证必要条件
    if (!fileInfo) {
        showError('请先选择文件');
        return;
    }
    
    if (selectedModels.length === 0) {
        showError('请至少选择一个模型');
        return;
    }

    const requestData = {
        filename: fileInfo.filename,
        selected_models: selectedModels,
        force_mode: evalMode
    };

    console.log('📤 发送请求数据:', requestData);

    try {
        console.log('🌐 发起网络请求...');
        const response = await fetch('/start_evaluation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        console.log('📥 收到响应，状态码:', response.status);
        const result = await response.json();
        console.log('📋 响应结果:', result);

        if (result.success) {
            currentTaskId = result.task_id;
            console.log('✅ 评测任务创建成功，任务ID:', currentTaskId);
            nextStep(); // 进入进度页面
            startProgressMonitoring();
            showSuccess('评测任务已启动');
        } else {
            console.error('❌ 评测启动失败:', result.error);
            showError(result.error || '启动评测失败');
        }
    } catch (error) {
        console.error('💥 网络请求异常:', error);
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
    document.querySelectorAll('.model-card').forEach(item => {
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
async function openApiConfig() {
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
    
    // 加载环境状态
    await updateEnvStatus();
}

// 更新环境状态显示
async function updateEnvStatus() {
    try {
        const response = await fetch('/get_env_status');
        const data = await response.json();
        
        const statusDiv = document.getElementById('env-status');
        if (!statusDiv) return;
        
        if (data.error) {
            statusDiv.innerHTML = `<span style="color: #e74c3c;">获取状态失败: ${data.error}</span>`;
            return;
        }
        
        const { env_file_exists, saved_keys, total_saved } = data;
        
        if (!env_file_exists || total_saved === 0) {
            statusDiv.innerHTML = '<span style="color: #95a5a6;">📁 暂未保存任何密钥到本地文件</span>';
        } else {
            const keyList = saved_keys.map(key => {
                const displayName = key.replace('ARK_API_KEY_', '').replace('GOOGLE_API_KEY', 'Google Gemini');
                return `<span style="color: #27ae60;">✓ ${displayName}</span>`;
            }).join(', ');
            
            statusDiv.innerHTML = `<span style="color: #27ae60;">💾 已保存 ${total_saved} 个密钥: ${keyList}</span>`;
        }
    } catch (error) {
        console.error('获取环境状态失败:', error);
        const statusDiv = document.getElementById('env-status');
        if (statusDiv) {
            statusDiv.innerHTML = '<span style="color: #e74c3c;">❌ 获取状态失败</span>';
        }
    }
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

async function handleApiConfigSubmit(e) {
    e.preventDefault();
    
    const googleKey = document.getElementById('google-api-key').value;
    const hkgaiV1Key = document.getElementById('hkgai-v1-key').value;
    const hkgaiV2Key = document.getElementById('hkgai-v2-key').value;
    const saveToFile = document.getElementById('save-to-file').checked;
    
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
    
    let successMessage = 'API密钥配置已保存到当前会话！';
    
    // 如果选择保存到文件，则调用后端API
    if (saveToFile && (googleKey || hkgaiV1Key || hkgaiV2Key)) {
        try {
            const response = await fetch('/save_api_keys', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    google_api_key: googleKey,
                    hkgai_v1_key: hkgaiV1Key,
                    hkgai_v2_key: hkgaiV2Key
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                successMessage = `✅ ${result.message}（重启后仍然有效）`;
                updateEnvStatus(); // 刷新环境状态
            } else {
                showNotification('error', `保存到文件失败: ${result.message}`);
                return;
            }
        } catch (error) {
            showNotification('error', `保存到文件时发生错误: ${error.message}`);
            return;
        }
    }
    
    // 显示成功消息
    showNotification('success', successMessage);
    
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
    
    // 调试信息
    console.log('模型数据:', data);
    
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
    
    // 添加Gemini状态（注意：Gemini仅用于评分，不参与模型选择）
    const geminiCard = document.createElement('div');
    geminiCard.className = `model-card ${data.gemini_available ? 'available' : 'unavailable'} gemini-card`;
    
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

// ===== 用户认证相关功能 =====

// 页面加载时检查用户登录状态
document.addEventListener('DOMContentLoaded', function() {
    checkUserLoginStatus();
});

// 检查用户登录状态
function checkUserLoginStatus() {
    // 这里可以通过检查session或者调用API来确定用户状态
    // 由于是服务端渲染，我们可以在页面模板中设置用户信息
}

// 退出登录
async function logout() {
    if (confirm('确定要退出登录吗？')) {
        try {
            const response = await fetch('/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                // 清除客户端状态
                hideUserInfo();
                showAlert('已退出登录', 'success');
                // 重定向到登录页面
                setTimeout(() => {
                    window.location.href = result.redirect || '/login';
                }, 1000);
            } else {
                showAlert('退出登录失败', 'error');
            }
        } catch (error) {
            console.error('退出登录错误:', error);
            showAlert('退出登录时发生错误', 'error');
        }
    }
}

// 显示用户信息
function showUserInfo(user) {
    document.getElementById('loginLink').style.display = 'none';
    document.getElementById('userInfo').style.display = 'inline-block';
    document.getElementById('displayName').textContent = user.display_name || user.username;
    
    // 如果是管理员，显示用户管理链接
    if (user.role === 'admin') {
        document.getElementById('adminLink').style.display = 'inline-block';
    }
}

// 隐藏用户信息
function hideUserInfo() {
    document.getElementById('loginLink').style.display = 'inline-block';
    document.getElementById('userInfo').style.display = 'none';
    document.getElementById('adminLink').style.display = 'none';
}

// 显示评分标准
async function showScoringCriteria() {
    try {
        const response = await fetch('/api/scoring-criteria');
        if (!response.ok) {
            showAlert('获取评分标准失败', 'error');
            return;
        }
        
        const data = await response.json();
        const criteria = data.criteria;
        
        if (!criteria || criteria.length === 0) {
            showAlert('暂无可用的评分标准', 'info');
            return;
        }
        
        // 创建模态框显示评分标准
        const modalHtml = `
            <div id="scoring-criteria-modal" style="
                position: fixed; 
                top: 0; left: 0; 
                width: 100%; height: 100%; 
                background: rgba(0,0,0,0.5); 
                z-index: 1000; 
                display: flex; 
                align-items: center; 
                justify-content: center;
            ">
                <div style="
                    background: white; 
                    border-radius: 20px; 
                    max-width: 800px; 
                    max-height: 80vh; 
                    width: 90%; 
                    overflow: hidden; 
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                ">
                    <div style="
                        background: linear-gradient(135deg, #28a745 0%, #20c997 100%); 
                        color: white; 
                        padding: 25px 30px; 
                        display: flex; 
                        justify-content: space-between; 
                        align-items: center;
                    ">
                        <h3 style="margin: 0; font-size: 20px; font-weight: 600;">
                            <i class="fas fa-star"></i> 评分标准
                        </h3>
                        <button onclick="closeScoringCriteriaModal()" style="
                            background: rgba(255,255,255,0.2); 
                            border: none; 
                            color: white; 
                            width: 35px; height: 35px; 
                            border-radius: 50%; 
                            cursor: pointer; 
                            font-size: 20px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                        ">&times;</button>
                    </div>
                    <div style="padding: 30px; max-height: 60vh; overflow-y: auto;">
                        ${criteria.map(criterion => `
                            <div style="
                                background: #f8f9fa; 
                                border: 1px solid #e9ecef; 
                                border-radius: 12px; 
                                padding: 20px; 
                                margin-bottom: 20px;
                            ">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px;">
                                    <div>
                                        <h4 style="margin: 0 0 8px 0; color: #495057; font-size: 18px;">${criterion.name}</h4>
                                        <span style="
                                            background: ${criterion.criteria_type === 'subjective' ? '#e3f2fd' : '#e8f5e8'}; 
                                            color: ${criterion.criteria_type === 'subjective' ? '#1976d2' : '#2e7d32'}; 
                                            padding: 3px 8px; 
                                            border-radius: 12px; 
                                            font-size: 11px; 
                                            font-weight: 500; 
                                            text-transform: uppercase;
                                        ">${criterion.criteria_type}</span>
                                        ${criterion.is_default ? '<span style="background: #28a745; color: white; padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 500; margin-left: 8px;">默认</span>' : ''}
                                    </div>
                                </div>
                                
                                <p style="color: #6c757d; margin-bottom: 15px; line-height: 1.4;">
                                    ${criterion.description || '无描述'}
                                </p>
                                
                                <div style="background: white; border: 1px solid #dee2e6; border-radius: 8px; padding: 15px;">
                                    <h5 style="margin: 0 0 10px 0; color: #495057;">评分维度:</h5>
                                    ${(criterion.criteria_config.dimensions || []).map(dim => `
                                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
                                            <div>
                                                <strong>${dim.display_name || dim.name}</strong>
                                                <br><small style="color: #6c757d;">${dim.description || ''}</small>
                                            </div>
                                            <div style="text-align: right;">
                                                <div style="background: #e9ecef; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-bottom: 2px;">
                                                    权重: ${dim.weight || 1.0}
                                                </div>
                                                ${dim.scale ? `<div style="color: #6c757d; font-size: 11px;">范围: ${dim.scale[0]} - ${dim.scale[dim.scale.length - 1]}</div>` : ''}
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                                
                                <div style="margin-top: 15px; font-size: 12px; color: #868e96;">
                                    <span><i class="fas fa-user"></i> 创建者: ${criterion.created_by}</span>
                                    <span style="margin-left: 15px;"><i class="fas fa-clock"></i> 创建时间: ${new Date(criterion.created_at).toLocaleString('zh-CN')}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        
        // 添加模态框到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
    } catch (error) {
        console.error('获取评分标准错误:', error);
        showAlert('获取评分标准时发生错误', 'error');
    }
}

// 关闭评分标准模态框
function closeScoringCriteriaModal() {
    const modal = document.getElementById('scoring-criteria-modal');
    if (modal) {
        modal.remove();
    }
}

// 点击模态框外部关闭
document.addEventListener('click', function(event) {
    const modal = document.getElementById('scoring-criteria-modal');
    if (modal && event.target === modal) {
        closeScoringCriteriaModal();
    }
    
    // 处理文件提示词编辑模态框
    const promptModal = document.getElementById('file-prompt-modal');
    if (promptModal && event.target === promptModal) {
        closeFilePromptModal();
    }
});

// ========== 文件提示词管理功能 ==========

// 编辑文件提示词
async function editFilePrompt(filename) {
    try {
        // 获取当前提示词
        const response = await fetch(`/api/file-prompt/${encodeURIComponent(filename)}`);
        if (!response.ok) {
            throw new Error('获取提示词失败');
        }
        
        const data = await response.json();
        
        // 创建编辑模态框
        const modalHtml = `
            <div id="file-prompt-modal" style="
                position: fixed; 
                top: 0; left: 0; 
                width: 100%; height: 100%; 
                background: rgba(0,0,0,0.5); 
                z-index: 1000; 
                display: flex; 
                align-items: center; 
                justify-content: center;
            ">
                <div style="
                    background: white; 
                    border-radius: 20px; 
                    max-width: 800px; 
                    max-height: 80vh; 
                    width: 90%; 
                    overflow: hidden; 
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                ">
                    <div style="
                        background: linear-gradient(135deg, #17a2b8 0%, #138496 100%); 
                        color: white; 
                        padding: 25px 30px; 
                        display: flex; 
                        justify-content: space-between; 
                        align-items: center;
                    ">
                        <h3 style="margin: 0; font-size: 20px; font-weight: 600;">
                            <i class="fas fa-edit"></i> 编辑提示词
                        </h3>
                        <button onclick="closeFilePromptModal()" style="
                            background: rgba(255,255,255,0.2); 
                            border: none; 
                            color: white; 
                            width: 35px; height: 35px; 
                            border-radius: 50%; 
                            cursor: pointer; 
                            font-size: 20px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                        ">&times;</button>
                    </div>
                    <div style="padding: 30px;">
                        <div style="margin-bottom: 20px;">
                            <div style="
                                background: #f8f9fa; 
                                border: 1px solid #e9ecef; 
                                border-radius: 8px; 
                                padding: 15px; 
                                margin-bottom: 15px;
                            ">
                                <h4 style="margin: 0 0 8px 0; color: #495057;">
                                    <i class="fas fa-file"></i> 文件: ${filename}
                                </h4>
                                <small style="color: #6c757d;">
                                    最后更新: ${new Date(data.updated_at).toLocaleString('zh-CN')} 
                                    (${data.updated_by})
                                </small>
                            </div>
                            
                            <label style="
                                display: block; 
                                margin-bottom: 8px; 
                                color: #333; 
                                font-weight: 600;
                            ">自定义提示词:</label>
                            <textarea id="prompt-editor" style="
                                width: 100%; 
                                height: 300px; 
                                padding: 15px; 
                                border: 2px solid #e1e5e9; 
                                border-radius: 10px; 
                                font-size: 14px; 
                                font-family: 'Courier New', monospace;
                                resize: vertical;
                                box-sizing: border-box;
                            " placeholder="输入自定义提示词...">${data.custom_prompt}</textarea>
                            
                            <div style="margin-top: 15px; padding: 10px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px;">
                                <small style="color: #856404;">
                                    <i class="fas fa-info-circle"></i> 
                                    提示词将在评测时替换默认的评分标准。支持任意文本内容，无需特殊格式。
                                </small>
                            </div>
                        </div>
                        
                        <div style="text-align: right; margin-top: 20px;">
                            <button onclick="closeFilePromptModal()" style="
                                background: #6c757d; 
                                color: white; 
                                border: none; 
                                padding: 10px 20px; 
                                border-radius: 5px; 
                                cursor: pointer; 
                                margin-right: 10px;
                            ">取消</button>
                            <button onclick="saveFilePrompt('${filename}')" style="
                                background: #17a2b8; 
                                color: white; 
                                border: none; 
                                padding: 10px 20px; 
                                border-radius: 5px; 
                                cursor: pointer;
                            ">
                                <i class="fas fa-save"></i> 保存
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 添加模态框到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
    } catch (error) {
        console.error('编辑提示词错误:', error);
        showAlert('获取提示词失败: ' + error.message, 'error');
    }
}

// 保存文件提示词
async function saveFilePrompt(filename) {
    try {
        const promptText = document.getElementById('prompt-editor').value.trim();
        
        if (!promptText) {
            showAlert('提示词不能为空', 'error');
            return;
        }
        
        const response = await fetch(`/api/file-prompt/${encodeURIComponent(filename)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                custom_prompt: promptText
            })
        });
        
        if (!response.ok) {
            throw new Error('保存失败');
        }
        
        const result = await response.json();
        
        if (result.success) {
            showAlert('提示词保存成功', 'success');
            closeFilePromptModal();
            // 刷新文件列表
            loadHistoryFiles();
        } else {
            throw new Error(result.error || '保存失败');
        }
        
    } catch (error) {
        console.error('保存提示词错误:', error);
        showAlert('保存提示词失败: ' + error.message, 'error');
    }
}

// 关闭文件提示词编辑模态框
function closeFilePromptModal() {
    const modal = document.getElementById('file-prompt-modal');
    if (modal) {
        modal.remove();
    }
}
