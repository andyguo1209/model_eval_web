# 🚀 HKGAI模型评测系统 - 升级指南

## 📋 本次升级内容

### ✨ 新增功能
- **分享评测结果功能**: 支持生成公开链接分享评测结果
- **密码保护**: 可设置访问密码保护分享内容
- **访问控制**: 支持设置过期时间和访问次数限制
- **美观界面**: 专门设计的分享页面，支持详情查看和数据分析

### 🗄️ 数据库变更
- 新增 `shared_links` 表 (分享链接管理)
- 新增 `shared_access_logs` 表 (访问日志记录)
- 新增相关索引提升查询性能

### 📁 新增文件
- `templates/shared_result.html` - 分享结果页面
- `templates/shared_password.html` - 密码验证页面  
- `templates/shared_error.html` - 错误提示页面

---

## 🛡️ 零数据丢失升级步骤

### 步骤1: 停止服务
```bash
# 停止正在运行的服务
pkill -f "python.*app.py"
# 或者如果使用gunicorn
pkill -f gunicorn
```

### 步骤2: 备份数据 (⚠️ 必须执行)
```bash
# 进入项目目录
cd /path/to/model-evaluation-web

# 执行备份脚本
chmod +x upgrade_backup.sh
./upgrade_backup.sh
```

### 步骤3: 更新代码
```bash
# 拉取最新代码
git pull origin main

# 或者手动复制新文件（如果不使用git）
# 复制以下文件:
# - app.py (包含新的分享API路由)
# - database.py (包含新的表结构和方法)
# - templates/shared_*.html (新的分享页面模板)
# - templates/results.html (更新的结果页面)
# - templates/history.html (更新的历史页面)
```

### 步骤4: 数据库迁移
```bash
# 执行数据库迁移脚本
python3 db_migration.py

# 或者指定数据库路径
python3 db_migration.py /path/to/evaluation_system.db
```

### 步骤5: 验证升级
```bash
# 检查数据库表结构
python3 -c "
import sqlite3
conn = sqlite3.connect('evaluation_system.db')
cursor = conn.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
tables = [row[0] for row in cursor.fetchall()]
print('数据库表列表:', tables)
print('shared_links存在:', 'shared_links' in tables)
print('shared_access_logs存在:', 'shared_access_logs' in tables)
conn.close()
"
```

### 步骤6: 启动服务
```bash
# 启动服务
python3 app.py

# 或者使用gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

### 步骤7: 功能测试
1. 访问系统首页，确认正常运行
2. 登录系统，查看历史评测结果
3. 在结果页面测试"分享结果"功能
4. 验证分享链接可以正常访问

---

## 🔧 手动数据库迁移 (高级用户)

如果自动迁移失败，可以手动执行SQL：

```sql
-- 1. 创建分享链接表
CREATE TABLE IF NOT EXISTS shared_links (
    id TEXT PRIMARY KEY,
    share_token TEXT UNIQUE NOT NULL,
    result_id TEXT NOT NULL,
    share_type TEXT NOT NULL,
    shared_by TEXT NOT NULL,
    shared_to TEXT,
    title TEXT,
    description TEXT,
    allow_download BOOLEAN DEFAULT 0,
    password_protected TEXT,
    expires_at TIMESTAMP,
    view_count INTEGER DEFAULT 0,
    access_limit INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP,
    revoked_by TEXT,
    FOREIGN KEY (result_id) REFERENCES evaluation_results (id),
    FOREIGN KEY (shared_by) REFERENCES users (id),
    FOREIGN KEY (shared_to) REFERENCES users (id),
    FOREIGN KEY (revoked_by) REFERENCES users (id)
);

-- 2. 创建访问日志表
CREATE TABLE IF NOT EXISTS shared_access_logs (
    id TEXT PRIMARY KEY,
    share_id TEXT NOT NULL,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    user_agent TEXT,
    user_id TEXT,
    FOREIGN KEY (share_id) REFERENCES shared_links (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- 3. 创建索引
CREATE INDEX IF NOT EXISTS idx_shared_links_token ON shared_links(share_token);
CREATE INDEX IF NOT EXISTS idx_shared_links_result ON shared_links(result_id);
CREATE INDEX IF NOT EXISTS idx_shared_links_shared_by ON shared_links(shared_by);
CREATE INDEX IF NOT EXISTS idx_shared_links_active ON shared_links(is_active);
CREATE INDEX IF NOT EXISTS idx_shared_access_logs_share ON shared_access_logs(share_id);
```

---

## 🆘 故障恢复方案

### 如果升级失败：

1. **恢复数据库**:
   ```bash
   cp backup_YYYYMMDD_HHMMSS/evaluation_system.db.backup evaluation_system.db
   ```

2. **恢复代码文件**:
   ```bash
   git checkout HEAD~1  # 回到上一个版本
   ```

3. **重启服务**:
   ```bash
   python3 app.py
   ```

### 如果分享功能异常：

1. **检查数据库表**:
   ```bash
   sqlite3 evaluation_system.db ".tables" | grep shared
   ```

2. **重新执行迁移**:
   ```bash
   python3 db_migration.py
   ```

3. **查看日志**:
   ```bash
   tail -f app.log  # 如果有日志文件
   ```

---

## ✅ 升级检查清单

- [ ] 已停止服务
- [ ] 已完成数据备份
- [ ] 已更新代码文件
- [ ] 已执行数据库迁移
- [ ] 数据库新表创建成功
- [ ] 服务正常启动
- [ ] 原有功能正常
- [ ] 分享功能可用
- [ ] 备份文件已妥善保存

---

## 📞 技术支持

如果升级过程中遇到问题：
- 📧 邮箱: guozhenhua@hkgai.org
- 📋 请提供详细的错误信息和系统环境

---

## 📝 升级日志

请记录您的升级信息：
- 升级时间: ________________
- 升级前版本: ______________
- 升级后版本: ______________
- 升级负责人: ______________
- 是否成功: ________________
- 备注: ____________________
