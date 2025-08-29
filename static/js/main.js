// 全局变量
let currentStep = 1;
let uploadedFile = null;
let fileInfo = null;
let availableModels = [];
let currentTaskId = null;

// 显示提示信息
function showAlert(message, type = 'info') {
    // 移除已存在的提示
    const existingAlert = document.getElementById('custom-alert');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    // 创建提示元素
    const alert = document.createElement('div');
    alert.id = 'custom-alert';
    alert.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        max-width: 400px;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transition: all 0.3s ease;
    `;
    
    // 根据类型设置样式
    switch(type) {
        case 'success':
            alert.style.background = 'linear-gradient(135deg, #28a745, #20c997)';
            alert.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
            break;
        case 'error':
            alert.style.background = 'linear-gradient(135deg, #dc3545, #e74c3c)';
            alert.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
            break;
        case 'warning':
            alert.style.background = 'linear-gradient(135deg, #ffc107, #ff9800)';
            alert.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
            break;
        default:
            alert.style.background = 'linear-gradient(135deg, #007bff, #0056b3)';
            alert.innerHTML = `<i class="fas fa-info-circle"></i> ${message}`;
    }
    
    // 添加到页面
    document.body.appendChild(alert);
    
    // 3秒后自动消失
    setTimeout(() => {
        if (alert && alert.parentNode) {
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (alert && alert.parentNode) {
                    alert.remove();
                }
            }, 300);
        }
    }, 3000);
    
    console.log(`🔔 [提示] ${type.toUpperCase()}: ${message}`);
}

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
async function uploadFile(file, overwrite = false, retryCount = 0) {
    const maxRetries = 2;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('overwrite', overwrite.toString());

    // 显示适当的加载消息
    const loadingMessage = retryCount > 0 
        ? `正在重试上传文件... (${retryCount}/${maxRetries})` 
        : '正在上传文件...';
    showLoading(loadingMessage);

    try {
        const response = await fetch('/upload_file', {
            method: 'POST',
            body: formData
        });

        // 检查响应状态
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        if (result.success) {
            console.log('📤 上传成功，调用displayFileInfo');
            displayFileInfo(result);
            showSuccess('文件上传成功！');
            loadHistoryFiles(); // 刷新测试集列表
        } else if (result.error === 'file_exists') {
            // 文件已存在，询问是否覆盖
            showFileExistsDialog(result.filename, file);
        } else {
            console.error('❌ 文件上传失败:', result.error);
            
            // 如果是网络错误且还有重试次数，则重试
            if (retryCount < maxRetries && (
                result.error.includes('网络') || 
                result.error.includes('超时') || 
                result.error.includes('连接')
            )) {
                console.log(`🔄 准备重试上传 (${retryCount + 1}/${maxRetries})`);
                hideLoading();
                await new Promise(resolve => setTimeout(resolve, 1000)); // 等待1秒后重试
                return uploadFile(file, overwrite, retryCount + 1);
            }
            
            showError(result.error || '文件上传失败');
        }
    } catch (error) {
        console.error('❌ 上传过程中发生错误:', error);
        
        // 网络错误重试机制
        if (retryCount < maxRetries) {
            console.log(`🔄 网络错误，准备重试 (${retryCount + 1}/${maxRetries})`);
            hideLoading();
            await new Promise(resolve => setTimeout(resolve, 1000)); // 等待1秒后重试
            return uploadFile(file, overwrite, retryCount + 1);
        }
        
        showError(`上传失败：${error.message}`);
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
        
        <div class="file-actions-section" style="margin-top: 20px; padding: 20px; background: #f8f9fa; border-radius: 10px;">
            <h4 style="margin: 0 0 15px 0; color: #495057;">
                <i class="fas fa-cogs"></i> 配置测评参数
            </h4>
            <div class="action-buttons" style="display: flex; gap: 15px; flex-wrap: wrap; justify-content: center; margin-bottom: 20px;">
                <button class="btn btn-info btn-lg" onclick="editFilePrompt('${info.filename}')" style="flex: 1; min-width: 250px; max-width: 350px; padding: 12px 20px;">
                    <i class="fas fa-edit"></i> 查看/编辑评测提示词
                </button>
                <button class="btn btn-primary btn-lg" onclick="nextStep()" style="flex: 1; min-width: 250px; max-width: 350px; padding: 12px 20px;">
                    <i class="fas fa-cogs"></i> 配置模型和开始评测
                </button>
            </div>
            <div style="background: #f8f9fa; border-left: 4px solid #28a745; padding: 15px; border-radius: 8px; margin-top: 10px;">
                <p style="margin: 0 0 8px 0; color: #28a745; font-size: 14px; font-weight: 600;">
                    💡 个性化评测提示
                </p>
                <p style="margin: 0; color: #6c757d; font-size: 13px; line-height: 1.4;">
                    点击"查看/编辑评测提示词"可以自定义评分标准、权重和详细要求，<br>
                    获得更贴近您需求的专业评测结果
                </p>
            </div>
        </div>
    `;

    fileInfoDiv.style.display = 'block';
    
    // 重新检查按钮状态
    console.log('🔄 文件信息显示完成，更新按钮状态');
    updateStartButton();
    
    // 不再自动进入下一步，让用户手动选择
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
        btn.textContent.includes(tabName === 'new' ? '上传新文件' : '选择测试集')
    );
    if (clickedBtn) {
        clickedBtn.classList.add('active');
    }
    
    // 显示对应的内容
    document.querySelectorAll('.upload-tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabName}-upload-tab`).classList.add('active');
    
    // 如果切换到测试集，加载文件列表
    if (tabName === 'history') {
        loadHistoryFiles();
    }
}

// 加载测试集列表
async function loadHistoryFiles() {
    const historyList = document.getElementById('history-files-list');
    
    // 显示加载状态
    historyList.innerHTML = '<div class="loading-placeholder"><i class="fas fa-spinner fa-spin"></i> 加载测试集列表中...</div>';
    
    try {
        console.log('🔄 开始加载测试集列表...');
        const response = await fetch('/get_uploaded_files');
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log('📋 收到测试集列表响应:', result);
        
        if (result.success) {
            console.log(`✅ 成功加载 ${result.files.length} 个测试集文件`);
            // 检查文件名编码
            result.files.forEach((file, index) => {
                console.log(`📄 文件 ${index + 1}: "${file.filename}" (${typeof file.filename})`);
                // 检查是否包含中文字符
                if (/[\u4e00-\u9fa5]/.test(file.filename)) {
                    console.log(`🔤 文件 "${file.filename}" 包含中文字符`);
                }
            });
            displayHistoryFiles(result.files);
        } else {
            console.error('❌ 获取文件列表失败:', result.error);
            historyList.innerHTML = `<div class="no-files">获取文件列表失败: ${result.error || '未知错误'}</div>`;
        }
    } catch (error) {
        console.error('❌ 加载测试集列表网络错误:', error);
        historyList.innerHTML = `<div class="no-files">网络错误: ${error.message}</div>`;
    }
}

// 安全的HTML转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 安全的属性值转义函数
function escapeAttr(text) {
    return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// 显示测试集列表
function displayHistoryFiles(files) {
    const historyList = document.getElementById('history-files-list');
    
    if (files.length === 0) {
        historyList.innerHTML = `
            <div class="no-files">
                <i class="fas fa-folder-open"></i>
                <p>暂无测试集</p>
                <small>上传文件后将显示在这里</small>
            </div>
        `;
        return;
    }
    
    // 清空容器
    historyList.innerHTML = '';
    
    // 为每个文件创建DOM元素
    files.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'history-file-item';
        fileItem.setAttribute('data-filename', file.filename);
        
        // 创建文件信息区域
        const fileInfo = document.createElement('div');
        fileInfo.className = 'file-info';
        
        const fileIcon = document.createElement('div');
        fileIcon.className = 'file-icon';
        fileIcon.innerHTML = `<i class="fas ${getFileIcon(file.filename)}"></i>`;
        
        const fileDetails = document.createElement('div');
        fileDetails.className = 'file-details';
        
        const fileName = document.createElement('div');
        fileName.className = 'file-name';
        fileName.title = file.filename;
        fileName.textContent = file.filename; // 使用textContent自动处理中文
        
        const fileMeta = document.createElement('div');
        fileMeta.className = 'file-meta';
        fileMeta.innerHTML = `
            <span><i class="fas fa-clock"></i> ${file.upload_time}</span>
            <span><i class="fas fa-hdd"></i> ${file.size_formatted}</span>
        `;
        
        fileDetails.appendChild(fileName);
        fileDetails.appendChild(fileMeta);
        fileInfo.appendChild(fileIcon);
        fileInfo.appendChild(fileDetails);
        
        // 创建操作按钮区域
        const fileActions = document.createElement('div');
        fileActions.className = 'file-actions';
        
        // 选择按钮
        const selectBtn = document.createElement('button');
        selectBtn.className = 'btn btn-sm btn-primary';
        selectBtn.title = '选择此文件';
        selectBtn.innerHTML = '<i class="fas fa-check"></i>';
        selectBtn.onclick = () => selectHistoryFile(file.filename);
        
        // 重命名按钮
        const renameBtn = document.createElement('button');
        renameBtn.className = 'btn btn-sm btn-warning';
        renameBtn.title = '重命名文件';
        renameBtn.innerHTML = '<i class="fas fa-tag"></i>';
        renameBtn.onclick = () => renameDatasetFile(file.filename);
        
        // 编辑提示词按钮
        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-sm btn-info';
        editBtn.title = '编辑提示词';
        editBtn.innerHTML = '<i class="fas fa-edit"></i>';
        editBtn.onclick = () => editFilePrompt(file.filename);
        
        // 下载按钮
        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'btn btn-sm btn-secondary';
        downloadBtn.title = '下载文件';
        downloadBtn.innerHTML = '<i class="fas fa-download"></i>';
        downloadBtn.onclick = () => downloadHistoryFile(file.filename);
        
        // 删除按钮
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-sm btn-danger';
        deleteBtn.title = '删除文件';
        deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
        deleteBtn.onclick = () => deleteHistoryFile(file.filename);
        
        fileActions.appendChild(selectBtn);
        fileActions.appendChild(renameBtn);
        fileActions.appendChild(editBtn);
        fileActions.appendChild(downloadBtn);
        fileActions.appendChild(deleteBtn);
        
        // 组装完整的文件项
        fileItem.appendChild(fileInfo);
        fileItem.appendChild(fileActions);
        
        // 添加到列表
        historyList.appendChild(fileItem);
        
        console.log(`✅ 显示测试集文件 ${index + 1}/${files.length}: ${file.filename}`);
    });
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

// 选择测试集文件
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
            console.log('✅ 测试集文件加载成功，调用displayFileInfo');
            displayFileInfo(result);
            showSuccess(`已选择文件: ${filename}`);
            
            // 切换回文件上传选项卡显示结果
            switchUploadTab('new');
        } else {
            console.error('❌ 测试集文件加载失败:', result.error);
            showError(result.error || '选择文件失败');
        }
    } catch (error) {
        showError('网络错误：' + error.message);
    } finally {
        hideLoading();
    }
}

// 重命名测试集文件
async function renameDatasetFile(originalFilename) {
    // 提取不含扩展名的文件名作为默认值
    const nameWithoutExt = originalFilename.replace(/\.[^/.]+$/, "");
    const extension = originalFilename.slice(originalFilename.lastIndexOf('.'));
    
    const newName = prompt('请输入新的文件名（不含扩展名）:', nameWithoutExt);
    if (newName === null || newName.trim() === '') {
        return;
    }
    
    const trimmedName = newName.trim();
    if (trimmedName === nameWithoutExt) {
        return; // 名称没有变化
    }
    
    // 检查文件名合法性
    if (!/^[a-zA-Z0-9\u4e00-\u9fa5_\-\s]+$/.test(trimmedName)) {
        showError('文件名只能包含中英文、数字、下划线、连字符和空格');
        return;
    }
    
    if (trimmedName.length > 50) {
        showError('文件名长度不能超过50个字符');
        return;
    }
    
    const newFilename = trimmedName + extension;
    
    // 检查新文件名是否已存在
    try {
        const checkResponse = await fetch(`/check_file_exists/${encodeURIComponent(newFilename)}`);
        const checkResult = await checkResponse.json();
        
        if (checkResult.exists) {
            showError('该文件名已存在，请选择其他名称');
            return;
        }
    } catch (error) {
        console.error('检查文件名失败:', error);
    }
    
    showLoading('正在重命名文件...');
    
    try {
        const response = await fetch('/api/dataset/rename', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                original_filename: originalFilename,
                new_filename: newFilename
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('文件重命名成功');
            loadHistoryFiles(); // 刷新文件列表
        } else {
            showError(result.error || '重命名失败');
        }
    } catch (error) {
        showError('重命名失败: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 下载测试集文件
function downloadHistoryFile(filename) {
    window.open(`/download_uploaded_file/${encodeURIComponent(filename)}`, '_blank');
}

// 删除测试集文件
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

// 刷新测试集
function refreshHistoryFiles() {
    loadHistoryFiles();
}

// 开始评测
async function startEvaluation() {
    console.log('🚀 开始评测');
    
    const selectedModels = Array.from(document.querySelectorAll('.model-card.selected'))
        .map(item => item.dataset.model);
    
    const evalMode = document.querySelector('input[name="eval-mode"]:checked').value;
    
    // 获取自定义配置
    const customName = document.getElementById('result-name').value.trim();
    const saveToHistory = document.getElementById('save-to-history').checked;
    
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
        force_mode: evalMode,
        custom_name: customName,
        save_to_history: saveToHistory
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
    if (!currentTaskId) {
        console.warn('⚠️ 无法开始进度监控：currentTaskId 为空');
        return;
    }

    console.log(`🔄 开始监控任务进度: ${currentTaskId}`);
    
    // 清除之前可能存在的定时器
    if (window.progressInterval) {
        clearInterval(window.progressInterval);
    }
    
    let errorCount = 0;  // 错误计数器
    const maxErrors = 5;  // 最大错误次数
    
    window.progressInterval = setInterval(async () => {
        try {
            const response = await fetch(`/task_status/${currentTaskId}`);
            const status = await response.json();

            if (response.ok) {
                // 重置错误计数器
                errorCount = 0;
                
                updateProgressDisplay(status);

                if (status.status === '完成') {
                    clearInterval(window.progressInterval);
                    console.log('✅ 任务完成，停止进度监控');
                    onEvaluationComplete(status);
                } else if (status.status === '失败') {
                    clearInterval(window.progressInterval);
                    console.log('❌ 任务失败，停止进度监控');
                    onEvaluationFailed(status);
                }
            } else {
                errorCount++;
                console.error(`❌ 获取任务状态失败 (${errorCount}/${maxErrors}):`, response.status);
                addToLog(`[${new Date().toLocaleTimeString()}] ⚠️ 获取任务状态失败 (${errorCount}/${maxErrors})`);
                
                if (errorCount >= maxErrors) {
                    clearInterval(window.progressInterval);
                    showError('获取任务状态失败次数过多，已停止监控');
                }
            }
        } catch (error) {
            errorCount++;
            console.error(`❌ 网络错误 (${errorCount}/${maxErrors}):`, error);
            addToLog(`[${new Date().toLocaleTimeString()}] ⚠️ 网络错误 (${errorCount}/${maxErrors}): ${error.message}`);
            
            if (errorCount >= maxErrors) {
                clearInterval(window.progressInterval);
                showError('网络错误次数过多，已停止监控');
            }
        }
    }, 2000);
    
    // 立即执行一次状态检查
    setTimeout(async () => {
        try {
            const response = await fetch(`/task_status/${currentTaskId}`);
            const status = await response.json();
            if (response.ok) {
                updateProgressDisplay(status);
            }
        } catch (error) {
            console.warn('首次状态检查失败:', error);
        }
    }, 100);
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

    // 根据任务状态更新控制按钮
    updateTaskControlButtons(status.status);

    // 添加到日志
    addToLog(`[${new Date().toLocaleTimeString()}] ${status.current_step}`);
}

// 更新任务控制按钮的显示状态
function updateTaskControlButtons(status) {
    const pauseBtn = document.getElementById('pause-task-btn');
    const resumeBtn = document.getElementById('resume-task-btn');
    const cancelBtn = document.getElementById('cancel-task-btn');
    
    if (pauseBtn && resumeBtn && cancelBtn) {
        // 隐藏所有按钮
        pauseBtn.style.display = 'none';
        resumeBtn.style.display = 'none';
        
        // 根据状态显示相应按钮
        if (status === '运行中' || status === '评测中') {
            pauseBtn.style.display = 'inline-block';
        } else if (status === '已暂停') {
            resumeBtn.style.display = 'inline-block';
        }
        
        // 取消按钮在未完成时始终显示
        if (status !== '完成' && status !== '失败') {
            cancelBtn.style.display = 'inline-block';
        } else {
            cancelBtn.style.display = 'none';
        }
    }
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
    console.log('Loading:', message);
    
    // 创建或更新加载遮罩
    let loadingOverlay = document.getElementById('loading-overlay');
    if (!loadingOverlay) {
        loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'loading-overlay';
        loadingOverlay.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner">
                    <i class="fas fa-spinner fa-spin"></i>
                </div>
                <div class="loading-message"></div>
            </div>
        `;
        document.body.appendChild(loadingOverlay);
    }
    
    loadingOverlay.querySelector('.loading-message').textContent = message;
    loadingOverlay.style.display = 'flex';
    
    // 禁用文件输入和上传区域
    const fileInput = document.getElementById('file-input');
    const uploadArea = document.getElementById('file-upload-area');
    if (fileInput) fileInput.disabled = true;
    if (uploadArea) uploadArea.style.pointerEvents = 'none';
}

function hideLoading() {
    console.log('Loading finished');
    
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
    
    // 重新启用文件输入和上传区域
    const fileInput = document.getElementById('file-input');
    const uploadArea = document.getElementById('file-upload-area');
    if (fileInput) fileInput.disabled = false;
    if (uploadArea) uploadArea.style.pointerEvents = 'auto';
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
        
        const { env_file_exists, saved_keys, saved_cookies, total_saved } = data;
        
        if (!env_file_exists || total_saved === 0) {
            statusDiv.innerHTML = '<span style="color: #95a5a6;">📁 暂未保存任何配置到本地文件</span>';
        } else {
            let displayParts = [];
            
            // 处理API密钥
            if (saved_keys.length > 0) {
                const keyList = saved_keys.map(key => {
                    const displayName = key.replace('ARK_API_KEY_', '').replace('GOOGLE_API_KEY', 'Google Gemini');
                    return `<span style="color: #27ae60;">✓ ${displayName}</span>`;
                }).join(', ');
                displayParts.push(`API密钥: ${keyList}`);
            }
            
            // 处理Copilot Cookie
            if (saved_cookies.length > 0) {
                const cookieList = saved_cookies.map(key => {
                    const displayName = key.replace('COPILOT_COOKIE_', '').toLowerCase();
                    const envNames = {
                        'prod': '生产环境',
                        'test': '测试环境',
                        'net': '备用环境'
                    };
                    return `<span style="color: #3498db;">🍪 ${envNames[displayName] || displayName}</span>`;
                }).join(', ');
                displayParts.push(`Cookie: ${cookieList}`);
            }
            
            const displayText = displayParts.join(' | ');
            statusDiv.innerHTML = `<span style="color: #27ae60;">💾 已保存 ${total_saved} 项配置</span><br/><span style="font-size: 0.9em;">${displayText}</span>`;
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
    
    // 获取Copilot Cookie字段
    const copilotCookieProd = document.getElementById('copilot-cookie-prod').value.trim();
    const copilotCookieTest = document.getElementById('copilot-cookie-test').value.trim();
    const copilotCookieNet = document.getElementById('copilot-cookie-net').value.trim();
    
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
    
    // 保存Copilot Cookie到sessionStorage
    if (copilotCookieProd) {
        sessionStorage.setItem('COPILOT_COOKIE_PROD', copilotCookieProd);
    }
    if (copilotCookieTest) {
        sessionStorage.setItem('COPILOT_COOKIE_TEST', copilotCookieTest);
    }
    if (copilotCookieNet) {
        sessionStorage.setItem('COPILOT_COOKIE_NET', copilotCookieNet);
    }
    
    let successMessage = 'API密钥和Cookie配置已保存到当前会话！';
    
    // 检查是否有任何配置需要保存
    const hasAnyConfig = googleKey || hkgaiV1Key || hkgaiV2Key || 
                        copilotCookieProd || copilotCookieTest || copilotCookieNet;
    
    // 如果选择保存到文件，则调用后端API
    if (saveToFile && hasAnyConfig) {
        try {
            const response = await fetch('/save_api_keys', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    google_api_key: googleKey,
                    hkgai_v1_key: hkgaiV1Key,
                    hkgai_v2_key: hkgaiV2Key,
                    copilot_cookie_prod: copilotCookieProd,
                    copilot_cookie_test: copilotCookieTest,
                    copilot_cookie_net: copilotCookieNet
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

// Cookie帮助弹窗控制函数
function showCookieHelp() {
    const modal = document.getElementById('cookie-help-modal');
    const backdrop = document.getElementById('cookie-help-backdrop');
    
    if (modal && backdrop) {
        modal.style.display = 'block';
        backdrop.style.display = 'block';
        
        // 添加动画效果
        requestAnimationFrame(() => {
            modal.style.opacity = '1';
            modal.style.transform = 'scale(1)';
        });
    }
}

function closeCookieHelp() {
    const modal = document.getElementById('cookie-help-modal');
    const backdrop = document.getElementById('cookie-help-backdrop');
    
    if (modal && backdrop) {
        modal.style.opacity = '0';
        modal.style.transform = 'scale(0.95)';
        
        setTimeout(() => {
            modal.style.display = 'none';
            backdrop.style.display = 'none';
        }, 300);
    }
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

// ========== 已移除查看评分标准功能 ==========
// 简化为只保留"编辑提示词"功能，用户可以在编辑提示词时直接查看和修改评分标准



// 点击模态框外部关闭
document.addEventListener('click', function(event) {
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
        console.log(`👆 [前端] 用户点击编辑文件 ${filename} 的提示词`);
        
        // 获取当前提示词
        console.log(`🔄 [前端] 正在获取文件 ${filename} 的当前提示词...`);
        const response = await fetch(`/api/file-prompt/${encodeURIComponent(filename)}`);
        if (!response.ok) {
            console.log(`❌ [前端] 获取提示词失败: ${response.status} ${response.statusText}`);
            throw new Error('获取提示词失败');
        }
        
        const data = await response.json();
        console.log(`✅ [前端] 成功获取提示词，长度: ${data.custom_prompt.length} 字符`);
        console.log(`📊 [前端] 提示词更新信息: ${data.updated_at} by ${data.updated_by}`);
        
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
                            <i class="fas fa-edit"></i> 编辑评测提示词 (${filename})
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
                            <button id="save-prompt-btn" onclick="saveFilePrompt('${filename}')" style="
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
        console.log(`🖼️ [前端] 正在显示提示词编辑模态框...`);
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        console.log(`✅ [前端] 提示词编辑界面已打开，用户可以开始编辑`);
        
    } catch (error) {
        console.error(`❌ [前端] 编辑提示词错误:`, error);
        showAlert('获取提示词失败: ' + error.message, 'error');
    }
}

// 保存文件提示词
async function saveFilePrompt(filename) {
    // 获取保存按钮和编辑器
    const saveButton = document.getElementById('save-prompt-btn');
    const promptEditor = document.getElementById('prompt-editor');
    
    try {
        const promptText = promptEditor.value.trim();
        
        console.log(`✏️ [前端] 用户开始保存文件 ${filename} 的提示词，长度: ${promptText.length} 字符`);
        
        if (!promptText) {
            console.log(`⚠️ [前端] 提示词为空，停止保存操作`);
            showAlert('提示词不能为空', 'error');
            return;
        }
        
        // 禁用保存按钮和编辑器，显示保存中状态
        if (saveButton) {
            saveButton.disabled = true;
            saveButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';
        }
        if (promptEditor) {
            promptEditor.disabled = true;
        }
        
        // 显示保存中提示
        showAlert('正在保存提示词...', 'info');
        
        console.log(`🔄 [前端] 正在发送保存请求到服务器...`);
        
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
            console.log(`❌ [前端] 服务器响应错误: ${response.status} ${response.statusText}`);
            throw new Error(`服务器错误 ${response.status}`);
        }
        
        const result = await response.json();
        console.log(`📝 [前端] 服务器响应:`, result);
        
        if (result.success) {
            console.log(`✅ [前端] 提示词保存成功，文件: ${filename}`);
            showAlert('✅ 提示词保存成功！您的自定义评测标准已生效', 'success');
            
            // 延迟关闭模态框，让用户看到成功提示
            setTimeout(() => {
                closeFilePromptModal();
                // 刷新文件列表以显示更新时间
                loadHistoryFiles();
            }, 1000);
        } else {
            console.log(`❌ [前端] 保存失败，错误信息: ${result.error}`);
            throw new Error(result.error || '保存失败');
        }
        
    } catch (error) {
        console.error(`❌ [前端] 保存提示词错误:`, error);
        showAlert('❌ 保存提示词失败: ' + error.message, 'error');
    } finally {
        // 恢复按钮和编辑器状态
        if (saveButton) {
            saveButton.disabled = false;
            saveButton.innerHTML = '<i class="fas fa-save"></i> 保存';
        }
        if (promptEditor) {
            promptEditor.disabled = false;
        }
    }
}

// 关闭文件提示词编辑模态框
function closeFilePromptModal() {
    const modal = document.getElementById('file-prompt-modal');
    if (modal) {
        modal.remove();
    }
}

// ==================== 正在进行的任务管理 ====================

// 加载正在进行的任务
async function loadRunningTasks() {
    try {
        const response = await fetch('/api/tasks/running');
        const result = await response.json();
        
        if (result.success && result.tasks.length > 0) {
            displayRunningTasks(result.tasks);
        } else {
            hideRunningTasksSection();
        }
    } catch (error) {
        console.error('获取正在进行的任务失败:', error);
        hideRunningTasksSection();
    }
}

// 显示正在进行的任务
function displayRunningTasks(tasks) {
    const section = document.getElementById('running-tasks-section');
    const tasksList = document.getElementById('running-tasks-list');
    
    if (!section || !tasksList) return;
    
    let html = '';
    tasks.forEach(task => {
        const progress = task.total > 0 ? Math.round((task.progress / task.total) * 100) : 0;
        const statusClass = task.is_active ? 'task-active' : 'task-inactive';
        const statusText = task.is_active ? (task.memory_status || task.status) : '已断开';
        const statusIcon = task.is_active ? 'fa-play-circle' : 'fa-pause-circle';
        
        html += `
            <div class="running-task-item ${statusClass}" style="background: white; border: 1px solid #dee2e6; border-radius: 6px; padding: 12px; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px;">
                    <div style="flex: 1;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                            <i class="fas ${statusIcon}" style="color: ${task.is_active ? '#28a745' : '#6c757d'};"></i>
                            <strong style="color: #495057;">${task.task_name}</strong>
                            <span class="badge" style="background: ${task.is_active ? '#d4edda' : '#f8f9fa'}; color: ${task.is_active ? '#155724' : '#6c757d'}; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                                ${statusText}
                            </span>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <div style="background: #e9ecef; border-radius: 10px; height: 6px; overflow: hidden;">
                                <div style="background: #007bff; height: 100%; width: ${progress}%; transition: width 0.3s ease;"></div>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-top: 4px; font-size: 12px; color: #6c757d;">
                                <span>${task.progress}/${task.total} (${progress}%)</span>
                                <span>${task.evaluation_mode === 'objective' ? '客观题' : '主观题'}</span>
                            </div>
                        </div>
                        <div style="font-size: 13px; color: #6c757d;">
                            模型: ${task.selected_models.join(', ')}
                        </div>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 5px;">
                        <button class="btn btn-sm btn-primary" onclick="connectToTask('${task.task_id}')" 
                                style="padding: 4px 8px; font-size: 12px; min-width: 60px;">
                            <i class="fas fa-external-link-alt"></i> 进入
                        </button>
                        ${task.is_active && task.status === 'running' ? `
                            <button class="btn btn-sm btn-warning" onclick="pauseTask('${task.task_id}')" 
                                    style="padding: 4px 8px; font-size: 12px;">
                                <i class="fas fa-pause"></i> 暂停
                            </button>
                        ` : ''}
                        ${task.is_active && task.status === 'paused' ? `
                            <button class="btn btn-sm btn-success" onclick="resumeTask('${task.task_id}')" 
                                    style="padding: 4px 8px; font-size: 12px;">
                                <i class="fas fa-play"></i> 继续
                            </button>
                        ` : ''}
                        <button class="btn btn-sm btn-danger" onclick="cancelTask('${task.task_id}')" 
                                style="padding: 4px 8px; font-size: 12px;">
                            <i class="fas fa-trash"></i> 删除
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    
    tasksList.innerHTML = html;
    section.style.display = 'block';
}

// 隐藏正在进行的任务区域
function hideRunningTasksSection() {
    const section = document.getElementById('running-tasks-section');
    if (section) {
        section.style.display = 'none';
    }
}

// 连接到现有任务
async function connectToTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/connect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            // 设置当前任务ID
            currentTaskId = taskId;
            
            // 切换到进度页面（第3步）
            currentStep = 3;
            updateStepDisplay();
            
            // 开始监控进度
            startProgressMonitoring();
            
            showSuccess('已重新连接到测评任务');
        } else {
            showError(result.error || '连接任务失败');
        }
    } catch (error) {
        console.error('连接任务失败:', error);
        showError('连接任务失败: ' + error.message);
    }
}

// 暂停任务
async function pauseTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/pause`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('任务已暂停');
            // 刷新任务列表
            setTimeout(() => loadRunningTasks(), 1000);
        } else {
            showError(result.error || '暂停任务失败');
        }
    } catch (error) {
        console.error('暂停任务失败:', error);
        showError('暂停任务失败: ' + error.message);
    }
}

// 继续任务
async function resumeTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/resume`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('任务已继续');
            // 刷新任务列表
            setTimeout(() => loadRunningTasks(), 1000);
        } else {
            showError(result.error || '继续任务失败');
        }
    } catch (error) {
        console.error('继续任务失败:', error);
        showError('继续任务失败: ' + error.message);
    }
}

// 取消/删除任务
async function cancelTask(taskId) {
    if (!confirm('确定要删除这个测评任务吗？此操作不可撤销。')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/tasks/${taskId}/cancel`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('任务已删除');
            // 刷新任务列表
            setTimeout(() => loadRunningTasks(), 1000);
        } else {
            showError(result.error || '删除任务失败');
        }
    } catch (error) {
        console.error('删除任务失败:', error);
        showError('删除任务失败: ' + error.message);
    }
}

// ==================== 进度页面任务控制 ====================

// 暂停当前任务
async function pauseCurrentTask() {
    if (!currentTaskId) {
        showError('没有正在进行的任务');
        return;
    }
    
    const pauseBtn = document.getElementById('pause-task-btn');
    if (pauseBtn) {
        pauseBtn.disabled = true;
        pauseBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 暂停中...';
    }
    
    try {
        const response = await fetch(`/api/tasks/${currentTaskId}/pause`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('任务已暂停');
            addToLog(`[${new Date().toLocaleTimeString()}] 用户手动暂停了任务`);
        } else {
            showError(result.error || '暂停任务失败');
        }
    } catch (error) {
        console.error('暂停任务失败:', error);
        showError('暂停任务失败: ' + error.message);
    } finally {
        if (pauseBtn) {
            pauseBtn.disabled = false;
            pauseBtn.innerHTML = '<i class="fas fa-pause"></i> 暂停测评';
        }
    }
}

// 继续当前任务
async function resumeCurrentTask() {
    if (!currentTaskId) {
        showError('没有正在进行的任务');
        return;
    }
    
    const resumeBtn = document.getElementById('resume-task-btn');
    if (resumeBtn) {
        resumeBtn.disabled = true;
        resumeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 继续中...';
    }
    
    try {
        const response = await fetch(`/api/tasks/${currentTaskId}/resume`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('任务已继续');
            addToLog(`[${new Date().toLocaleTimeString()}] 用户手动继续了任务`);
        } else {
            showError(result.error || '继续任务失败');
        }
    } catch (error) {
        console.error('继续任务失败:', error);
        showError('继续任务失败: ' + error.message);
    } finally {
        if (resumeBtn) {
            resumeBtn.disabled = false;
            resumeBtn.innerHTML = '<i class="fas fa-play"></i> 继续测评';
        }
    }
}

// 取消当前任务
async function cancelCurrentTask() {
    if (!currentTaskId) {
        showError('没有正在进行的任务');
        return;
    }
    
    if (!confirm('确定要取消当前的测评任务吗？此操作不可撤销。')) {
        return;
    }
    
    const cancelBtn = document.getElementById('cancel-task-btn');
    if (cancelBtn) {
        cancelBtn.disabled = true;
        cancelBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 取消中...';
    }
    
    try {
        const response = await fetch(`/api/tasks/${currentTaskId}/cancel`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('任务已取消');
            addToLog(`[${new Date().toLocaleTimeString()}] 用户取消了任务`);
            
            // 清除任务ID和监控
            currentTaskId = null;
            
            // 返回到第一步
            setTimeout(() => {
                resetForm();
            }, 2000);
        } else {
            showError(result.error || '取消任务失败');
        }
    } catch (error) {
        console.error('取消任务失败:', error);
        showError('取消任务失败: ' + error.message);
    } finally {
        if (cancelBtn) {
            cancelBtn.disabled = false;
            cancelBtn.innerHTML = '<i class="fas fa-times"></i> 取消测评';
        }
    }
}

// 页面加载完成后自动检查正在进行的任务
document.addEventListener('DOMContentLoaded', function() {
    // 延迟加载，确保页面完全加载
    setTimeout(() => {
        loadRunningTasks();
        
        // 每30秒刷新一次任务状态
        setInterval(() => {
            loadRunningTasks();
        }, 30000);
    }, 1000);
});
