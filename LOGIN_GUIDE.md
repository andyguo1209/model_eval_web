# 用户登录系统使用指南

## 🎉 功能概览

本系统现在包含完整的用户认证和管理功能：

- ✅ 用户登录/退出
- ✅ 基于角色的权限控制
- ✅ 用户管理后台
- ✅ 安全的密码存储（SHA256哈希）
- ✅ Session会话管理

## 🔐 默认账户

### 管理员账户
- **用户名**: `admin`
- **密码**: `admin123`
- **权限**: 完全管理权限，可以访问用户管理后台

## 📱 使用方法

### 1. 登录系统
1. 访问 `http://localhost:5001/login`
2. 输入用户名和密码
3. 点击登录按钮

### 2. 用户管理（仅管理员）
1. 登录后，管理员可以看到"用户管理"按钮
2. 点击进入 `http://localhost:5001/admin`
3. 可以进行以下操作：
   - 查看所有用户列表
   - 添加新用户
   - 编辑用户信息
   - 启用/禁用用户
   - 修改用户角色

### 3. 用户角色说明
- **admin**: 管理员，拥有所有权限
- **reviewer**: 审核员，可以审核评测结果
- **annotator**: 标注员，可以进行数据标注
- **viewer**: 查看者，只能查看结果

## 🛠️ 开发者信息

### 数据库表结构
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    role TEXT DEFAULT 'annotator',
    email TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,
    last_login TIMESTAMP,
    preferences TEXT,
    created_by TEXT
);
```

### API 端点
- `GET /login` - 登录页面
- `POST /login` - 执行登录
- `POST /logout` - 退出登录
- `GET /admin` - 管理员页面
- `GET /admin/users` - 获取用户列表
- `POST /admin/users` - 创建新用户
- `PUT /admin/users/<id>` - 更新用户信息

### 认证装饰器
```python
@login_required  # 需要登录
@admin_required  # 需要管理员权限
```

## 💻 代码级别添加用户

### 方法1: 通过Python代码
```python
from database import db

# 创建新用户
user_id = db.create_user(
    username="新用户名",
    password="密码",
    role="annotator",  # admin, reviewer, annotator, viewer
    display_name="显示名称",
    email="email@example.com"
)
```

### 方法2: 直接操作数据库
```python
import sqlite3
import hashlib
import uuid

# 连接数据库
conn = sqlite3.connect('evaluation_system.db')
cursor = conn.cursor()

# 准备用户数据
user_id = str(uuid.uuid4())
username = "新用户名"
password_hash = hashlib.sha256("密码".encode()).hexdigest()
display_name = "显示名称"
role = "annotator"

# 插入用户
cursor.execute("""
    INSERT INTO users (id, username, password_hash, display_name, role)
    VALUES (?, ?, ?, ?, ?)
""", (user_id, username, password_hash, display_name, role))

conn.commit()
conn.close()
```

## 🔧 配置选项

### 环境变量
```bash
# Flask会话密钥
SECRET_KEY=your_secret_key_here

# 数据库路径
DATABASE_PATH=evaluation_system.db
```

### 安全建议
1. **修改默认密码**: 首次使用后立即修改admin密码
2. **使用强密码**: 设置复杂密码，至少6位字符
3. **定期清理**: 定期清理不活跃的用户账户
4. **权限控制**: 根据实际需要分配用户角色

## 🧪 测试功能

运行测试脚本验证登录功能：
```bash
python3 test_login.py
```

## 🚀 快速开始

1. **启动系统**:
   ```bash
   python3 start.py
   ```

2. **访问登录页面**:
   ```
   http://localhost:5001/login
   ```

3. **使用默认管理员账户登录**:
   - 用户名: admin
   - 密码: admin123

4. **开始管理用户**:
   - 登录后点击"用户管理"
   - 添加新用户和分配角色

## 📞 技术支持

如果遇到问题，请检查：
1. 数据库文件是否存在
2. 数据库表结构是否正确
3. Flask session配置是否正确
4. 端口5001是否被占用

---

🎯 **现在您可以使用完整的用户认证系统了！**
