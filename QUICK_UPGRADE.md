# ⚡ 快速升级指引

## 🎯 一键升级 (推荐)

```bash
# 1. 停止服务 (如果在运行)
pkill -f "python.*app.py"

# 2. 进入项目目录
cd /path/to/model-evaluation-web

# 3. 执行一键升级
./upgrade.sh
```

## 📋 手动升级步骤

如果一键升级失败，可按以下步骤手动操作：

### 1. 数据备份
```bash
./upgrade_backup.sh
```

### 2. 更新代码
```bash
# 如果使用git
git pull origin main

# 如果手动复制，请确保复制以下文件：
# - app.py
# - database.py  
# - templates/shared_*.html
# - templates/results.html
# - templates/history.html
```

### 3. 数据库迁移
```bash
python3 db_migration.py
```

### 4. 启动服务
```bash
python3 app.py
```

## ✅ 验证升级

访问系统 → 登录 → 查看评测结果 → 点击"分享结果"按钮

## 🆘 遇到问题？

1. **数据库错误**: 使用备份恢复
   ```bash
   cp backup_YYYYMMDD_HHMMSS/evaluation_system.db.backup evaluation_system.db
   ```

2. **服务启动失败**: 检查端口占用
   ```bash
   lsof -i :8080
   ```

3. **分享功能异常**: 重新执行迁移
   ```bash
   python3 db_migration.py
   ```

## 📞 技术支持

📧 guozhenhua@hkgai.org
