# 🔐 安全须知

## ⚠️ 重要警告：绝不提交API密钥到Git仓库！

### 🚫 禁止事项

**绝对不要**在以下地方包含真实的API密钥：
- 代码文件中的硬编码
- 配置文件
- 环境变量文件（.env）
- 注释或文档中的示例
- 测试文件
- 任何提交到Git的文件

### ✅ 安全做法

1. **使用环境变量**
   ```bash
   export GOOGLE_API_KEY="your_real_key"
   export ARK_API_KEY_HKGAI_V1="your_real_key"
   export ARK_API_KEY_HKGAI_V2="your_real_key"
   ```

2. **使用Web界面配置**
   - 点击页面右上角"API配置"按钮
   - 密钥仅保存在浏览器sessionStorage中
   - 关闭浏览器后自动清除

3. **本地配置文件**（不提交到Git）
   ```bash
   # 创建本地配置（已在.gitignore中排除）
   echo "GOOGLE_API_KEY=your_real_key" > .env.local
   echo "ARK_API_KEY_HKGAI_V1=your_real_key" >> .env.local
   echo "ARK_API_KEY_HKGAI_V2=your_real_key" >> .env.local
   ```

### 🛡️ 保护措施

1. **.gitignore 配置**
   - 已配置忽略所有可能包含密钥的文件
   - 包括 `.env*`, `*.key`, `*.secret` 等

2. **代码设计**
   - 所有密钥通过环境变量或HTTP头传递
   - 没有硬编码密钥
   - 支持运行时动态配置

3. **检查脚本**
   ```bash
   # 运行安全检查
   ./security_check.sh
   ```

### 🔍 如何检查密钥泄露

```bash
# 检查是否有API密钥格式
grep -r "sk-" . --exclude-dir=.git --exclude-dir=.venv
grep -r "AIza" . --exclude-dir=.git --exclude-dir=.venv

# 检查Git历史记录
git log --all --full-history -- "*.env*"
```

### 🚨 发现泄露时的处理

如果意外提交了API密钥：

1. **立即撤销密钥**
   - 去API提供商平台撤销泄露的密钥
   - 生成新的密钥

2. **清理Git历史**
   ```bash
   # 从历史记录中移除敏感文件
   git filter-branch --force --index-filter \
   'git rm --cached --ignore-unmatch path/to/secret/file' \
   --prune-empty --tag-name-filter cat -- --all
   ```

3. **强制推送**
   ```bash
   git push origin --force --all
   ```

### 📋 最佳实践

1. **定期轮换密钥**
2. **使用最小权限原则**
3. **监控API使用情况**
4. **定期进行安全审计**
5. **团队成员安全培训**

### ✅ 本项目安全状态

- ✅ 无硬编码密钥
- ✅ 完善的.gitignore配置
- ✅ 环境变量设计
- ✅ Web界面临时存储
- ✅ 安全检查脚本
- ✅ 详细的安全文档

**记住：API密钥就像密码一样，永远不要分享或提交到公共仓库！**
