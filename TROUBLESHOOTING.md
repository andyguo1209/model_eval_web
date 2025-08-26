# 🛠️ 环境问题解决指南

## 常见部署问题及解决方案

### 1. ❌ numpy/pandas兼容性错误

**错误信息:**
```
ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject
```

**解决方案:**

#### 快速修复 (推荐)
```bash
# 运行自动修复脚本
chmod +x fix_environment.sh
./fix_environment.sh
```

#### 手动修复
```bash
# 1. 卸载冲突的包
pip uninstall -y numpy pandas

# 2. 安装兼容版本
pip install "numpy>=1.21.0,<1.25.0"
pip install "pandas==2.0.3"

# 3. 重新安装其他依赖
pip install -r requirements.txt
```

### 2. ⚠️ ".env文件不存在"提示

**错误信息:**
```
未找到.env文件或文件为空
```

**解决方案:**

#### 方式1: 创建.env文件
```bash
# 复制模板
cp config.env.template .env

# 编辑配置
nano .env
```

#### 方式2: 使用环境变量
```bash
# 临时设置
export GOOGLE_API_KEY="your_api_key_here"
export ARK_API_KEY_HKGAI_V1="your_hkgai_v1_key"
export ARK_API_KEY_HKGAI_V2="your_hkgai_v2_key"

# 启动系统
python3 start.py
```

#### 方式3: Web界面配置
1. 直接启动系统: `python3 start.py`
2. 访问: http://localhost:5001
3. 在页面中配置API密钥

### 3. 🐍 Python版本问题

**要求:** Python 3.8+

**检查版本:**
```bash
python3 --version
```

**升级Python (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.9 python3.9-pip
```

**升级Python (CentOS/RHEL):**
```bash
sudo yum install python39 python39-pip
```

### 4. 📦 依赖包缺失

**错误信息:**
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方案:**
```bash
# 安装所有依赖
pip3 install -r requirements.txt

# 或单独安装缺失的包
pip3 install 包名
```

### 5. 🔒 权限问题

**错误信息:**
```
Permission denied
```

**解决方案:**
```bash
# 给脚本执行权限
chmod +x *.sh

# 如果是pip权限问题，使用用户安装
pip3 install --user -r requirements.txt
```

### 6. 🌐 端口占用问题

**错误信息:**
```
Port 5001 is in use by another program
```

**解决方案:**

#### 方式1: 杀死占用进程
```bash
# 查找占用进程
lsof -i :5001

# 杀死进程
kill -9 进程ID
```

#### 方式2: 更换端口
编辑 `start.py` 或 `app.py` 中的端口配置

### 7. 💾 磁盘空间不足

**检查磁盘空间:**
```bash
df -h
```

**清理空间:**
```bash
# 清理pip缓存
pip cache purge

# 清理临时文件
rm -rf /tmp/*

# 清理系统包缓存 (Ubuntu)
sudo apt clean
```

### 8. 🔧 环境管理问题

#### Conda环境问题

**问题: conda命令未找到**
```bash
# 解决方案: 安装conda
# 下载Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 重新加载shell配置
source ~/.bashrc
```

**问题: 环境创建失败**
```bash
# 清理conda缓存
conda clean --all

# 更新conda
conda update conda

# 重新创建环境
conda env remove -n model-evaluation-web
conda env create -f environment.yml
```

**问题: 包冲突**
```bash
# 严格按照environment.yml创建环境
conda env create -f environment.yml --force

# 如果仍有问题，使用mamba (更快的包管理器)
conda install mamba -c conda-forge
mamba env create -f environment.yml
```

#### pip/venv环境问题

**推荐使用虚拟环境:**
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 9. 🐍 环境管理最佳实践

#### Conda环境管理
```bash
# 创建环境
conda env create -f environment.yml

# 激活环境
conda activate model-evaluation-web

# 更新环境
conda env update -f environment.yml

# 导出环境
conda env export > environment.yml

# 删除环境
conda env remove -n model-evaluation-web

# 列出所有环境
conda env list
```

#### pip环境管理
```bash
# 创建虚拟环境
python -m venv venv

# 激活环境
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 更新pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt

# 导出环境
pip freeze > requirements.txt

# 停用环境
deactivate
```

## 🚀 一键诊断和修复

我们提供了自动化修复脚本，可以解决大部分常见问题：

```bash
# 下载并运行修复脚本
curl -fsSL https://raw.githubusercontent.com/your-repo/model-evaluation-web/main/fix_environment.sh | bash

# 或者本地运行
chmod +x fix_environment.sh
./fix_environment.sh
```

## 📞 获取帮助

如果上述解决方案都无法解决您的问题，请：

1. **检查日志输出** - 查看详细的错误信息
2. **查看GitHub Issues** - 搜索是否有类似问题
3. **提交Issue** - 包含以下信息：
   - 操作系统和版本
   - Python版本
   - 完整的错误信息
   - 执行的命令

## 💡 预防措施

为了避免环境问题，建议：

1. **使用虚拟环境** - 避免包冲突
2. **定期更新** - 保持依赖包最新
3. **备份配置** - 保存.env文件
4. **文档记录** - 记录自定义配置

---

📚 更多信息请参考：
- [README.md](README.md) - 项目主要文档
- [DEPLOYMENT.md](DEPLOYMENT.md) - 详细部署指南
- [CHANGELOG.md](CHANGELOG.md) - 更新日志
