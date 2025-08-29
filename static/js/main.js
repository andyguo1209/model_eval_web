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

// 存储事件处理函数，用于去重
const uploadAreaHandlers = {
    dragover: function(e) {
        e.preventDefault();
        document.getElementById('file-upload-area').classList.add('dragover');
    },
    dragleave: function(e) {
        e.preventDefault();
        document.getElementById('file-upload-area').classList.remove('dragover');
    },
    drop: function(e) {
        e.preventDefault();
        const uploadArea = document.getElementById('file-upload-area');
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            document.getElementById('file-input').files = files;
            handleFileSelect();
        }
    },
    click: function() {
        console.log('🖱️ [点击上传区域] 触发文件选择对话框');
        
        // 防止在文件正在处理时重复打开文件选择器
        if (window.fileProcessing) {
            console.log('⚠️ [点击上传区域] 文件正在处理中，忽略点击');
            return;
        }
        
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.click();
        }
    }
};

// 设置文件上传功能
function setupFileUpload() {
    const fileInput = document.getElementById('file-input');
    const uploadArea = document.getElementById('file-upload-area');

    console.log('🔧 [初始化] 设置文件上传功能');

    // 移除可能存在的旧事件监听器，防止重复绑定
    fileInput.removeEventListener('change', handleFileSelect);
    uploadArea.removeEventListener('dragover', uploadAreaHandlers.dragover);
    uploadArea.removeEventListener('dragleave', uploadAreaHandlers.dragleave);
    uploadArea.removeEventListener('drop', uploadAreaHandlers.drop);
    uploadArea.removeEventListener('click', uploadAreaHandlers.click);
    
    // 重新绑定事件监听器
    fileInput.addEventListener('change', handleFileSelect);
    uploadArea.addEventListener('dragover', uploadAreaHandlers.dragover);
    uploadArea.addEventListener('dragleave', uploadAreaHandlers.dragleave);
    uploadArea.addEventListener('drop', uploadAreaHandlers.drop);
    uploadArea.addEventListener('click', uploadAreaHandlers.click);
    
    console.log('✅ [初始化] 所有文件上传事件监听器已绑定');
}

// 处理文件选择
function handleFileSelect() {
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];
    
    console.log('📁 [文件选择] 文件选择事件触发:', file ? file.name : '无文件');
    
    if (!file) {
        console.log('❌ [文件选择] 没有选择文件');
        window.fileProcessing = false; // 清理处理标志
        return;
    }

    // 设置文件处理标志，防止重复操作
    window.fileProcessing = true;
    console.log('🔒 [文件选择] 设置文件处理标志');

    // 检查文件格式
    const allowedTypes = ['.xlsx', '.xls', '.csv'];
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    
    console.log('🔍 [文件选择] 文件扩展名:', fileExtension);
    
    if (!allowedTypes.includes(fileExtension)) {
        console.log('❌ [文件选择] 不支持的文件格式:', fileExtension);
        showError('不支持的文件格式，请上传 .xlsx、.xls 或 .csv 文件');
        
        // 文件格式错误后重置文件输入框和处理标志
        fileInput.value = '';
        window.fileProcessing = false;
        console.log('🔄 [格式错误] 已重置文件输入框和处理标志');
        return;
    }

    console.log('✅ [文件选择] 文件格式检查通过，开始上传');
    uploadedFile = file;
    uploadFile(file);
}

// 上传文件
async function uploadFile(file, overwrite = false, retryCount = 0) {
    console.log(`📤 [上传文件] 开始上传: ${file.name}, 覆盖模式: ${overwrite}, 重试次数: ${retryCount}`);
    
    const maxRetries = 2;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('overwrite', overwrite.toString());

    // 显示适当的加载消息
    const loadingMessage = retryCount > 0 
        ? `正在重试上传文件... (${retryCount}/${maxRetries})` 
        : '正在上传文件...';
    
    console.log(`🔄 [上传文件] 显示加载状态: ${loadingMessage}`);
    showLoading(loadingMessage);

    try {
        const response = await fetch('/upload_file', {
            method: 'POST',
            body: formData
        });

        // 解析响应内容
        const result = await response.json();

        // 处理成功响应
        if (response.ok && result.success) {
            console.log('📤 上传成功，调用displayFileInfo');
            displayFileInfo(result);
            showSuccess('文件上传成功！');
            // 立即刷新测试集列表，确保用户能看到新文件
            refreshFileListWithFeedback('文件上传成功，正在更新列表...');
            
            // 上传成功后重置文件输入框
            const fileInput = document.getElementById('file-input');
            if (fileInput) {
                fileInput.value = '';
                console.log('🔄 [上传成功] 已重置文件输入框');
            }
            
            // 标记处理完成
            window.fileProcessing = false;
            console.log('🔓 [上传成功] 清理文件处理标志');
        } 
        // 处理文件冲突的情况
        else if (response.status === 409 || response.status === 403) {
            console.log(`📁 文件冲突: ${result.error}`, result);
            console.log(`🔍 [调试] 冲突类型: ${result.error}, 状态码: ${response.status}`);
            
            if (result.error === 'file_exists_own' || result.error === 'file_exists_admin' || result.error === 'file_exists_legacy') {
                // 可以覆盖的情况：自己的文件、管理员覆盖、遗留文件
                showFileExistsDialog(result.filename, file, result.message, result.owner);
                return; // 提前返回，避免在finally中清理标志
            } else if (result.error === 'file_owned_by_other_suggest_rename' || result.error === 'file_legacy_suggest_rename') {
                // 其他用户的文件或历史文件，提供重命名建议
                showFileRenameSuggestionDialog(result, file);
                return; // 提前返回，避免在finally中清理标志
            } else if (result.error === 'file_owned_by_other' || result.error === 'file_legacy_protected') {
                // 不能覆盖的情况：其他用户的文件、普通用户不能覆盖遗留文件
                showFileConflictError(result.message, result.filename, result.owner);
                // 清理处理标志，因为无法继续上传
                window.fileProcessing = false;
                return;
            } else if (result.error === 'file_exists') {
                // 兼容旧的错误类型
                showFileExistsDialog(result.filename, file, result.message);
                return;
            }
        } 
        // 处理其他错误
        else if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
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
            
            // 最终失败后重置文件输入框
            const fileInput = document.getElementById('file-input');
            if (fileInput) {
                fileInput.value = '';
                console.log('🔄 [上传失败] 已重置文件输入框');
            }
            
            // 清理处理标志
            window.fileProcessing = false;
            console.log('🔓 [上传失败] 清理文件处理标志');
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
        
        // 网络错误最终失败后重置文件输入框
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.value = '';
            console.log('🔄 [网络错误失败] 已重置文件输入框');
        }
        
        // 清理处理标志
        window.fileProcessing = false;
        console.log('🔓 [网络错误失败] 清理文件处理标志');
    } finally {
        hideLoading();
        
        // 最后确保清理处理标志（除非是显示覆盖对话框的情况）
        if (window.fileProcessing === undefined || window.fileProcessing === null) {
            window.fileProcessing = false;
            console.log('🔓 [finally] 确保文件处理标志已清理');
        }
    }
}

// 显示文件存在对话框
function showFileExistsDialog(filename, file, customMessage = null, owner = null) {
    console.log(`📁 [文件覆盖] 显示覆盖确认对话框: ${filename}`, { customMessage, owner });
    
    let messageText = customMessage || `文件 "${filename}" 已经存在。`;
    let ownerInfo = '';
    if (owner && owner !== '未知用户') {
        ownerInfo = `<div style="margin: 10px 0; padding: 8px; background: #e3f2fd; border-radius: 5px; font-size: 0.9em; color: #1976d2;">
            <i class="fas fa-user"></i> 文件上传者：<strong>${escapeHtml(owner)}</strong>
        </div>`;
    }
    
    const dialogHtml = `
        <div class="custom-alert">
            <div class="custom-alert-content">
                <div class="custom-alert-header">
                    <i class="fas fa-file-alt text-info"></i>
                    <h4>文件已存在</h4>
                </div>
                <div class="custom-alert-body">
                    <p>${escapeHtml(messageText)}</p>
                    ${ownerInfo}
                    <p>您希望覆盖现有文件还是取消上传？</p>
                    <div style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px; font-size: 0.9em; color: #6c757d; text-align: center;">
                        💡 选择"覆盖文件"将替换现有文件
                    </div>
                </div>
                <div class="custom-alert-footer">
                    <button class="btn btn-secondary" onclick="closeCustomAlert()">
                        <i class="fas fa-times"></i> 取消上传
                    </button>
                    <button class="btn btn-primary" onclick="overwriteFile('${filename}')">
                        <i class="fas fa-check"></i> 覆盖文件
                    </button>
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
    console.log(`🔄 [文件覆盖] 用户确认覆盖文件: ${filename}`);
    
    // 先保存文件对象，因为 closeCustomAlert 会清理它
    const fileToUpload = window.pendingFile;
    closeCustomAlert();
    
    if (fileToUpload) {
        console.log(`📤 [文件覆盖] 开始以覆盖模式重新上传: ${fileToUpload.name}`);
        await uploadFile(fileToUpload, true);
        
        // 确保文件输入框被重置
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.value = '';
            console.log('🔄 [文件覆盖] 已重置文件输入框');
        }
        
        console.log(`✅ [文件覆盖] 覆盖上传完成`);
    } else {
        console.error(`❌ [文件覆盖] 没有找到待上传的文件`);
        showError('上传失败：没有找到待上传的文件');
        
        // 确保清理处理标志
        window.fileProcessing = false;
        console.log('🔓 [文件覆盖错误] 清理文件处理标志');
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

// 显示文件冲突错误（不可覆盖）
function showFileConflictError(message, filename, owner = null) {
    console.log(`🚫 [文件冲突] 显示不可覆盖错误: ${filename}`, { message, owner });
    
    let ownerInfo = '';
    if (owner && owner !== '未知用户') {
        ownerInfo = `<div style="margin: 10px 0; padding: 8px; background: #ffebee; border-radius: 5px; font-size: 0.9em; color: #c62828;">
            <i class="fas fa-user"></i> 文件所有者：<strong>${escapeHtml(owner)}</strong>
        </div>`;
    }
    
    const dialogHtml = `
        <div class="custom-alert">
            <div class="custom-alert-content">
                <div class="custom-alert-header">
                    <i class="fas fa-exclamation-triangle text-danger"></i>
                    <h4>无法上传文件</h4>
                </div>
                <div class="custom-alert-body">
                    <p>${escapeHtml(message)}</p>
                    ${ownerInfo}
                    <div style="margin-top: 15px; padding: 12px; background: #fff3cd; border: 1px solid #ffecb5; border-radius: 5px; font-size: 0.9em; color: #856404;">
                        <i class="fas fa-lightbulb"></i> 
                        <strong>建议解决方案：</strong>
                        <ul style="margin: 8px 0 0 20px; padding-left: 0;">
                            <li>为您的文件选择一个不同的名称</li>
                            <li>在文件名中添加日期或版本号</li>
                            <li>例如：${escapeHtml(filename)?.replace(/\.(xlsx?|csv)$/i, '_v2.$1') || 'yourfile_v2.xlsx'}</li>
                        </ul>
                    </div>
                </div>
                <div class="custom-alert-footer">
                    <button class="btn btn-primary" onclick="closeCustomAlert()">
                        <i class="fas fa-check"></i> 知道了
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // 添加弹窗到页面
    const alertContainer = document.createElement('div');
    alertContainer.innerHTML = dialogHtml;
    alertContainer.id = 'custom-alert-container';
    document.body.appendChild(alertContainer);
    
    // 添加点击背景关闭功能
    alertContainer.addEventListener('click', function(e) {
        if (e.target === alertContainer) {
            closeCustomAlert();
        }
    });
    
    // 清理待上传文件状态
    if (window.pendingFile) {
        window.pendingFile = null;
    }
}

// 关闭自定义弹窗
function closeCustomAlert() {
    console.log('🔄 [弹窗关闭] 关闭自定义弹窗并清理状态');
    
    const alertContainer = document.getElementById('custom-alert-container');
    if (alertContainer) {
        alertContainer.remove();
    }
    
    // 清理待上传文件状态
    if (window.pendingFile) {
        console.log('🗑️ [弹窗关闭] 清理pendingFile状态');
        window.pendingFile = null;
    }
    
    // 清理重命名相关状态
    if (window.pendingRenameData) {
        console.log('🗑️ [弹窗关闭] 清理pendingRenameData状态');
        window.pendingRenameData = null;
    }
    
    // 重置文件输入框
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        console.log('🔄 [弹窗关闭] 重置文件输入框');
        fileInput.value = '';
    }
    
    // 清理文件处理标志
    window.fileProcessing = false;
    console.log('🔓 [弹窗关闭] 清理文件处理标志');
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

// 通用的文件列表刷新函数，带用户反馈
function refreshFileListWithFeedback(message = '正在更新文件列表...') {
    console.log(`🔄 [文件刷新] ${message}`);
    
    // 先显示刷新提示（如果有历史列表容器）
    const historyList = document.getElementById('history-files-list');
    if (historyList) {
        // 保存当前内容以便出错时恢复
        const originalContent = historyList.innerHTML;
        
        // 显示刷新状态
        historyList.innerHTML = `<div class="loading-placeholder">
            <i class="fas fa-sync fa-spin"></i> ${message}
        </div>`;
        
        // 延迟执行刷新，给用户看到刷新提示的时间
        setTimeout(() => {
            loadHistoryFiles().catch(error => {
                console.error('❌ 刷新文件列表失败:', error);
                // 出错时恢复原内容
                historyList.innerHTML = originalContent;
                showError('刷新文件列表失败');
            });
        }, 150); // 给用户足够时间看到刷新提示
    } else {
        // 没有历史列表容器时直接刷新
        setTimeout(() => {
            loadHistoryFiles().catch(error => {
                console.error('❌ 刷新文件列表失败:', error);
                showError('刷新文件列表失败');
            });
        }, 100);
    }
}

// 加载测试集列表
async function loadHistoryFiles() {
    const historyList = document.getElementById('history-files-list');
    
    // 显示加载状态
    historyList.innerHTML = '<div class="loading-placeholder"><i class="fas fa-spinner fa-spin"></i> 加载测试集列表中...</div>';
    
    try {
        console.log('🔄 开始加载测试集列表...');
        
        // 构建查询参数（包含用户筛选）
        const params = new URLSearchParams();
        const selectedUser = document.getElementById('files-user-filter')?.value;
        if (selectedUser) {
            params.append('user_id', selectedUser);
        }
        
        const url = `/get_uploaded_files${params.toString() ? `?${params.toString()}` : ''}`;
        const response = await fetch(url);
        
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
            
            // 如果是管理员，显示用户筛选器并更新用户列表
            if (result.is_admin) {
                const userFilterContainer = document.getElementById('files-user-filter-container');
                if (userFilterContainer) {
                    userFilterContainer.style.display = 'block';
                    if (result.users) {
                        updateFilesUserFilter(result.users, result.selected_user);
                    }
                }
            }
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
        
        let metaContent = `
            <span><i class="fas fa-clock"></i> ${file.upload_time}</span>
            <span><i class="fas fa-hdd"></i> ${file.size_formatted}</span>
        `;
        
        // 为管理员显示上传者信息
        if (file.uploader_name && file.uploader_name !== '历史数据') {
            metaContent += `<span><i class="fas fa-user"></i> ${escapeHtml(file.uploader_name)}</span>`;
        }
        
        fileMeta.innerHTML = metaContent;
        
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
        
        // 编辑数据按钮
        const editDataBtn = document.createElement('button');
        editDataBtn.className = 'btn btn-sm btn-success';
        editDataBtn.title = '编辑数据内容';
        editDataBtn.innerHTML = '<i class="fas fa-table"></i>';
        editDataBtn.onclick = () => editFileData(file.filename);
        
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
        
        // 只有admin和reviewer可以编辑数据内容
        if (window.currentUserData && (window.currentUserData.role === 'admin' || window.currentUserData.role === 'reviewer')) {
            fileActions.appendChild(editDataBtn);
        }
        
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
            // 立即刷新文件列表，确保用户能看到更新
            refreshFileListWithFeedback('文件重命名成功，正在更新列表...');
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
            // 立即刷新文件列表，确保用户能看到更新
            refreshFileListWithFeedback('文件删除成功，正在更新列表...');
            
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

// 更新文件用户筛选器
function updateFilesUserFilter(users, selectedUserId) {
    const userFilter = document.getElementById('files-user-filter');
    if (!userFilter) return;
    
    let options = '<option value="">所有用户</option>';
    users.forEach(user => {
        const selected = user.id === selectedUserId ? 'selected' : '';
        options += `<option value="${user.id}" ${selected}>${escapeHtml(user.display_name)} (${escapeHtml(user.username)})</option>`;
    });
    
    userFilter.innerHTML = options;
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
    const cancelBtn = document.getElementById('cancel-task-btn');
    
    if (cancelBtn) {
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
    // 检查管理员权限
    const isAdmin = window.currentUserData && window.currentUserData.role === 'admin';
    if (!isAdmin) {
        showError('您没有权限访问API配置功能');
        return;
    }
    
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
    
    // 显示或隐藏API状态提示（只对管理员显示）
    const isAdmin = window.currentUserData && window.currentUserData.role === 'admin';
    if (hasUnavailableModels && isAdmin) {
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
    
    // 如果是管理员，显示管理员功能
    if (user.role === 'admin') {
        document.getElementById('adminLink').style.display = 'inline-block';
        document.getElementById('apiConfigBtn').style.display = 'inline-block';
    }
}

// 隐藏用户信息
function hideUserInfo() {
    document.getElementById('loginLink').style.display = 'inline-block';
    document.getElementById('userInfo').style.display = 'none';
    document.getElementById('adminLink').style.display = 'none';
    document.getElementById('apiConfigBtn').style.display = 'none';
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

// ========== 文件数据编辑功能 ==========

// 编辑文件数据内容
async function editFileData(filename) {
    try {
        console.log(`👆 [前端] 用户点击编辑文件 ${filename} 的数据内容`);
        
        // 获取文件数据
        console.log(`🔄 [前端] 正在获取文件 ${filename} 的数据...`);
        const response = await fetch(`/api/file-data/${encodeURIComponent(filename)}`);
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('您没有权限编辑此文件');
            }
            throw new Error('获取文件数据失败');
        }
        
        const data = await response.json();
        console.log(`✅ [前端] 成功获取文件数据，包含 ${data.data.length} 行`);
        
        // 显示编辑模态框
        showDataEditModal(filename, data);
        
    } catch (error) {
        console.error(`❌ [前端] 编辑文件数据失败:`, error);
        showError(`编辑失败: ${error.message}`);
    }
}

// 显示数据编辑模态框
function showDataEditModal(filename, fileData) {
    const modal = `
        <div id="data-edit-modal" class="custom-modal" style="
            display: block;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100vw;
            height: 100vh;
            background-color: white;
            margin: 0;
            padding: 0;
        ">
            <!-- 全屏标题栏 -->
            <div style="
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%); 
                color: white; 
                padding: 15px 25px; 
                display: flex; 
                justify-content: space-between; 
                align-items: center;
                border-bottom: 1px solid #ddd;
            ">
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">
                    <i class="fas fa-table"></i> 编辑数据内容 - ${escapeHtml(filename)}
                </h3>
                <div style="display: flex; align-items: center; gap: 15px;">
                    <span style="font-size: 13px; opacity: 0.9;">
                        <i class="fas fa-keyboard"></i> 快捷键：Ctrl+S保存，ESC退出
                    </span>
                    <button onclick="closeDataEditModal()" style="
                        background: rgba(255,255,255,0.2); 
                        border: none; 
                        color: white; 
                        width: 36px; height: 36px; 
                        border-radius: 50%; 
                        cursor: pointer; 
                        font-size: 20px;
                        transition: background 0.2s;
                    " onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">×</button>
                </div>
            </div>
            
            <!-- 全屏内容区域 -->
            <div style="
                background: #f8f9fa;
                height: calc(100vh - 70px);
                overflow: hidden;
                display: flex;
                flex-direction: column;
            ">
                <div id="data-edit-toolbar" style="
                    background: white; 
                    padding: 15px 25px; 
                    border-bottom: 1px solid #ddd;
                    flex-shrink: 0;
                ">
                    <button class="btn btn-success" onclick="addNewRow()" style="margin-right: 10px;">
                        <i class="fas fa-plus"></i> 添加行
                    </button>
                    <button class="btn btn-primary" onclick="saveFileData('${escapeAttr(filename)}')" style="margin-right: 10px;">
                        <i class="fas fa-save"></i> 保存
                    </button>
                    <button class="btn btn-secondary" onclick="closeDataEditModal()">
                        <i class="fas fa-times"></i> 取消
                    </button>
                </div>
                
                <div id="data-edit-table-container" style="
                    flex: 1;
                    overflow: auto;
                    margin: 15px 25px;
                    background: white;
                    border: 1px solid #ddd; 
                    border-radius: 8px;
                ">
                    <!-- 表格将在这里动态生成 -->
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modal);
    
    // 添加键盘快捷键支持
    const handleKeyDown = (e) => {
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            saveFileData(filename);
        } else if (e.key === 'Escape') {
            closeDataEditModal();
        }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    
    // 存储事件处理器，以便清理
    document.getElementById('data-edit-modal').setAttribute('data-keyhandler', 'true');
    window.dataEditKeyHandler = handleKeyDown;
    
    // 生成可编辑表格
    generateEditableTable(fileData);
}

// 生成可编辑表格
function generateEditableTable(fileData) {
    const container = document.getElementById('data-edit-table-container');
    const columns = fileData.columns;
    const data = fileData.data;
    
    let tableHtml = `
        <table id="editable-data-table" style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 8px; border: 1px solid #ddd; width: 50px;">#</th>
                    ${columns.map(col => `
                        <th style="padding: 8px; border: 1px solid #ddd; min-width: 150px;">
                            ${escapeHtml(col)}
                        </th>
                    `).join('')}
                    <th style="padding: 8px; border: 1px solid #ddd; width: 80px;">操作</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    data.forEach((row, index) => {
        tableHtml += `
            <tr data-row-index="${index}">
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center; background: #f8f9fa;">
                    ${index + 1}
                </td>
                ${columns.map(col => `
                    <td style="padding: 4px; border: 1px solid #ddd;">
                        <textarea 
                            data-column="${escapeAttr(col)}" 
                            style="
                                width: 100%; 
                                border: none; 
                                resize: vertical; 
                                min-height: 40px;
                                padding: 4px;
                                font-size: 13px;
                                line-height: 1.3;
                            "
                        >${escapeHtml(String(row[col] || ''))}</textarea>
                    </td>
                `).join('')}
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                    <button class="btn btn-sm btn-danger" onclick="deleteRow(${index})" title="删除行">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    tableHtml += `
            </tbody>
        </table>
    `;
    
    container.innerHTML = tableHtml;
}

// 添加新行
function addNewRow() {
    const table = document.getElementById('editable-data-table');
    const tbody = table.querySelector('tbody');
    const firstRow = tbody.querySelector('tr');
    
    if (!firstRow) return;
    
    const columns = Array.from(firstRow.querySelectorAll('textarea')).map(ta => ta.dataset.column);
    const newIndex = tbody.querySelectorAll('tr').length;
    
    const newRowHtml = `
        <tr data-row-index="${newIndex}">
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center; background: #f8f9fa;">
                ${newIndex + 1}
            </td>
            ${columns.map(col => `
                <td style="padding: 4px; border: 1px solid #ddd;">
                    <textarea 
                        data-column="${escapeAttr(col)}" 
                        style="
                            width: 100%; 
                            border: none; 
                            resize: vertical; 
                            min-height: 40px;
                            padding: 4px;
                            font-size: 13px;
                            line-height: 1.3;
                        "
                    ></textarea>
                </td>
            `).join('')}
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                <button class="btn btn-sm btn-danger" onclick="deleteRow(${newIndex})" title="删除行">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        </tr>
    `;
    
    tbody.insertAdjacentHTML('beforeend', newRowHtml);
    updateRowNumbers();
}

// 删除行
function deleteRow(index) {
    if (confirm('确定要删除这一行吗？')) {
        const row = document.querySelector(`tr[data-row-index="${index}"]`);
        if (row) {
            row.remove();
            updateRowNumbers();
        }
    }
}

// 更新行号
function updateRowNumbers() {
    const rows = document.querySelectorAll('#editable-data-table tbody tr');
    rows.forEach((row, index) => {
        row.setAttribute('data-row-index', index);
        row.querySelector('td').textContent = index + 1;
        const deleteBtn = row.querySelector('button[onclick*="deleteRow"]');
        if (deleteBtn) {
            deleteBtn.setAttribute('onclick', `deleteRow(${index})`);
        }
    });
}

// 保存文件数据
async function saveFileData(filename) {
    try {
        const table = document.getElementById('editable-data-table');
        const rows = table.querySelectorAll('tbody tr');
        const data = [];
        
        // 收集所有数据
        rows.forEach(row => {
            const rowData = {};
            const textareas = row.querySelectorAll('textarea');
            textareas.forEach(textarea => {
                const column = textarea.dataset.column;
                rowData[column] = textarea.value.trim();
            });
            data.push(rowData);
        });
        
        console.log(`💾 [前端] 准备保存文件 ${filename}，包含 ${data.length} 行数据`);
        
        // 发送到后端保存
        const response = await fetch(`/api/file-data/${encodeURIComponent(filename)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ data: data })
        });
        
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('您没有权限保存此文件');
            }
            throw new Error('保存文件失败');
        }
        
        const result = await response.json();
        console.log(`✅ [前端] 文件保存成功:`, result);
        
        showSuccess('文件保存成功！');
        closeDataEditModal();
        
        // 刷新文件列表
        loadHistoryFiles();
        
    } catch (error) {
        console.error(`❌ [前端] 保存文件失败:`, error);
        showError(`保存失败: ${error.message}`);
    }
}

// 显示文件重命名建议对话框
function showFileRenameSuggestionDialog(result, file) {
    console.log(`💡 [文件重命名] 显示重命名建议对话框:`, result);
    
    const dialogHtml = `
        <div class="custom-alert">
            <div class="custom-alert-content">
                <div class="custom-alert-header">
                    <i class="fas fa-exclamation-triangle text-warning"></i>
                    <h4>文件名冲突</h4>
                </div>
                <div class="custom-alert-body">
                    <p>${escapeHtml(result.message)}</p>
                    
                    <div style="margin: 15px 0; padding: 12px; background: #ffebee; border-radius: 5px; font-size: 0.9em; color: #c62828;">
                        <i class="fas fa-user"></i> 
                        <strong>文件所有者：</strong>${escapeHtml(result.owner)}
                    </div>
                    
                    <div style="margin: 20px 0; padding: 15px; background: #e8f5e8; border: 1px solid #4caf50; border-radius: 8px;">
                        <h5 style="margin: 0 0 10px 0; color: #2e7d32;">
                            <i class="fas fa-lightbulb"></i> 智能解决方案
                        </h5>
                        <p style="margin: 0 0 10px 0; color: #2e7d32;">
                            系统建议将您的文件重命名为：
                        </p>
                        <div style="background: #f1f8e9; padding: 10px; border-radius: 4px; font-family: monospace; color: #1b5e20; font-weight: bold; border-left: 4px solid #4caf50;">
                            ${escapeHtml(result.suggested_filename)}
                        </div>
                        <p style="margin: 10px 0 0 0; font-size: 0.85em; color: #558b2f;">
                            💡 这样可以避免与其他用户的文件冲突，同时保持文件内容不变
                        </p>
                    </div>
                    
                    <p>您希望如何处理？</p>
                </div>
                <div class="custom-alert-footer">
                    <button class="btn btn-secondary" onclick="closeCustomAlert()">
                        <i class="fas fa-times"></i> 取消上传
                    </button>
                    <button class="btn btn-success" onclick="uploadWithSuggestedName('${escapeAttr(result.suggested_filename)}')">
                        <i class="fas fa-check"></i> 使用建议名称上传
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // 添加弹窗到页面
    const alertContainer = document.createElement('div');
    alertContainer.innerHTML = dialogHtml;
    alertContainer.id = 'custom-alert-container';
    document.body.appendChild(alertContainer);
    
    // 添加点击背景关闭功能
    alertContainer.addEventListener('click', function(e) {
        if (e.target === alertContainer) {
            closeCustomAlert();
        }
    });
    
    // 存储文件对象以便重命名上传时使用
    window.pendingFile = file;
    window.pendingRenameData = result;
}

// 使用建议的文件名上传
async function uploadWithSuggestedName(suggestedFilename) {
    console.log(`📝 [重命名上传] 用户同意使用建议文件名: ${suggestedFilename}`);
    
    // 先保存文件对象，因为 closeCustomAlert 会清理它
    const originalFile = window.pendingFile;
    closeCustomAlert();
    
    if (originalFile) {
        console.log(`📤 [重命名上传] 开始上传，原始文件: ${originalFile.name} -> 新文件名: ${suggestedFilename}`);
        
        // 创建一个新的File对象，使用建议的文件名但保持原始文件内容
        const renamedFile = new File([originalFile], suggestedFilename, {
            type: originalFile.type,
            lastModified: originalFile.lastModified
        });
        
        console.log(`🔄 [重命名上传] 文件对象创建成功: ${renamedFile.name}, 大小: ${renamedFile.size} bytes`);
        
        // 上传重命名后的文件
        await uploadFile(renamedFile, false);
        
        // 清理状态
        window.pendingFile = null;
        window.pendingRenameData = null;
        
        // 确保文件输入框被重置
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.value = '';
            console.log('🔄 [重命名上传] 已重置文件输入框');
        }
        
        console.log(`✅ [重命名上传] 重命名上传完成`);
    } else {
        console.error(`❌ [重命名上传] 没有找到待上传的文件`);
        console.error(`🔍 [重命名上传] 调试信息: window.pendingFile=${window.pendingFile}, originalFile=${originalFile}`);
        showError('上传失败：没有找到待上传的文件');
        
        // 确保清理处理标志
        window.fileProcessing = false;
        console.log('🔓 [重命名上传错误] 清理文件处理标志');
    }
}

// 关闭数据编辑模态框
function closeDataEditModal() {
    const modal = document.getElementById('data-edit-modal');
    if (modal) {
        // 清理键盘事件监听器
        if (window.dataEditKeyHandler) {
            document.removeEventListener('keydown', window.dataEditKeyHandler);
            window.dataEditKeyHandler = null;
        }
        modal.remove();
    }
}

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
