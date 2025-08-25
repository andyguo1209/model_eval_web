# AI模型评测系统 - API密钥配置指南

## 需要配置的API密钥

系统需要以下两个API密钥才能正常工作：

### 1. Google Gemini API密钥 (GOOGLE_API_KEY)
- **用途**: 用于AI评分和评测功能
- **获取方式**: 
  1. 访问 [Google AI Studio](https://makersuite.google.com/)
  2. 登录您的Google账号
  3. 点击"Get API Key"创建新的API密钥
  4. 复制生成的API密钥

### 2. HKGAI-V1模型API密钥 (ARK_API_KEY_HKGAI_V1)
- **用途**: 用于调用HKGAI-V1模型
- **获取方式**: 联系HKGAI服务提供商获取V1版本的API密钥

### 3. HKGAI-V2模型API密钥 (ARK_API_KEY_HKGAI_V2)
- **用途**: 用于调用HKGAI-V2模型
- **获取方式**: 联系HKGAI服务提供商获取V2版本的API密钥

## 配置方法

### 方法一：临时设置（推荐用于测试）

在启动系统前设置环境变量：

```bash
# 设置Google API密钥
export GOOGLE_API_KEY='your_google_api_key_here'

# 设置HKGAI V1 API密钥
export ARK_API_KEY_HKGAI_V1='your_hkgai_v1_api_key_here'

# 设置HKGAI V2 API密钥
export ARK_API_KEY_HKGAI_V2='your_hkgai_v2_api_key_here'

# 启动系统
source .venv/bin/activate
python3 start.py
```

### 方法二：一次性启动命令

```bash
GOOGLE_API_KEY='your_google_api_key_here' ARK_API_KEY_HKGAI_V1='your_hkgai_v1_api_key_here' ARK_API_KEY_HKGAI_V2='your_hkgai_v2_api_key_here' python3 start.py
```

### 方法三：永久设置（添加到shell配置文件）

#### 对于 zsh（macOS默认）:
```bash
echo 'export GOOGLE_API_KEY="your_google_api_key_here"' >> ~/.zshrc
echo 'export ARK_API_KEY_HKGAI_V1="your_hkgai_v1_api_key_here"' >> ~/.zshrc
echo 'export ARK_API_KEY_HKGAI_V2="your_hkgai_v2_api_key_here"' >> ~/.zshrc
source ~/.zshrc
```

#### 对于 bash:
```bash
echo 'export GOOGLE_API_KEY="your_google_api_key_here"' >> ~/.bashrc
echo 'export ARK_API_KEY_HKGAI_V1="your_hkgai_v1_api_key_here"' >> ~/.bashrc
echo 'export ARK_API_KEY_HKGAI_V2="your_hkgai_v2_api_key_here"' >> ~/.bashrc
source ~/.bashrc
```

### 方法四：使用.env文件

1. 在项目根目录创建 `.env` 文件：

```bash
GOOGLE_API_KEY=your_google_api_key_here
ARK_API_KEY_HKGAI_V1=your_hkgai_v1_api_key_here
ARK_API_KEY_HKGAI_V2=your_hkgai_v2_api_key_here
```

2. 修改启动脚本以加载.env文件（可选）

## 验证配置

启动系统后，如果看到以下信息说明配置成功：
```
✅ API密钥配置完成
```

如果看到以下警告，说明还需要配置：
```
⚠️  缺少以下API密钥:
   - GOOGLE_API_KEY
   - ARK_API_KEY_HKGAI_V1
   - ARK_API_KEY_HKGAI_V2
```

## 注意事项

1. **安全性**: 请勿将API密钥提交到代码仓库
2. **有效性**: 确保API密钥有效且有足够的配额
3. **权限**: 确保API密钥有调用相应服务的权限

## 测试配置

配置完成后，您可以：
1. 访问 http://localhost:5001
2. 上传测试文件（如 data/sample_subjective.csv）
3. 选择模型进行评测
4. 查看评测结果

## 故障排除

如果遇到API调用失败：
1. 检查API密钥是否正确
2. 检查网络连接
3. 检查API配额是否充足
4. 查看系统日志获取详细错误信息
