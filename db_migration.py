#!/usr/bin/env python3
"""
🔄 数据库增量迁移脚本
专门用于添加分享功能的表结构，不影响现有数据
"""

import sqlite3
import os
import sys
from datetime import datetime

def check_table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None

def create_shared_tables(cursor):
    """创建分享功能相关的表"""
    print("🔧 开始创建分享功能表...")
    
    # 1. 创建 shared_links 表
    if not check_table_exists(cursor, 'shared_links'):
        print("📝 创建 shared_links 表...")
        cursor.execute('''
            CREATE TABLE shared_links (
                id TEXT PRIMARY KEY,
                share_token TEXT UNIQUE NOT NULL, -- 分享令牌，用于生成公开链接
                result_id TEXT NOT NULL, -- 关联的评测结果ID
                share_type TEXT NOT NULL, -- 'public', 'user_specific'
                shared_by TEXT NOT NULL, -- 分享者用户ID
                shared_to TEXT, -- 被分享者用户ID（仅user_specific类型使用）
                
                -- 分享设置
                title TEXT, -- 自定义分享标题
                description TEXT, -- 分享描述
                allow_download BOOLEAN DEFAULT 0, -- 是否允许下载
                password_protected TEXT, -- 密码哈希（如果设置了密码）
                
                -- 时间控制
                expires_at TIMESTAMP, -- 过期时间
                view_count INTEGER DEFAULT 0, -- 查看次数
                access_limit INTEGER DEFAULT 0, -- 访问次数限制，0表示无限制
                last_accessed TIMESTAMP, -- 最后访问时间
                
                -- 状态管理
                is_active BOOLEAN DEFAULT 1, -- 是否活跃
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at TIMESTAMP, -- 撤销时间
                revoked_by TEXT, -- 撤销者
                
                FOREIGN KEY (result_id) REFERENCES evaluation_results (id),
                FOREIGN KEY (shared_by) REFERENCES users (id),
                FOREIGN KEY (shared_to) REFERENCES users (id),
                FOREIGN KEY (revoked_by) REFERENCES users (id)
            )
        ''')
        print("✅ shared_links 表创建完成")
    else:
        print("ℹ️  shared_links 表已存在，跳过创建")
    
    # 2. 创建 shared_access_logs 表
    if not check_table_exists(cursor, 'shared_access_logs'):
        print("📝 创建 shared_access_logs 表...")
        cursor.execute('''
            CREATE TABLE shared_access_logs (
                id TEXT PRIMARY KEY,
                share_id TEXT NOT NULL, -- 分享链接ID
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT, -- 访问者IP
                user_agent TEXT, -- 浏览器信息
                user_id TEXT, -- 如果是登录用户访问
                
                FOREIGN KEY (share_id) REFERENCES shared_links (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        print("✅ shared_access_logs 表创建完成")
    else:
        print("ℹ️  shared_access_logs 表已存在，跳过创建")

def create_indexes(cursor):
    """创建分享功能相关的索引"""
    print("🔧 创建索引...")
    
    indexes = [
        ('idx_shared_links_token', 'shared_links', 'share_token'),
        ('idx_shared_links_result', 'shared_links', 'result_id'),
        ('idx_shared_links_shared_by', 'shared_links', 'shared_by'),
        ('idx_shared_links_active', 'shared_links', 'is_active'),
        ('idx_shared_access_logs_share', 'shared_access_logs', 'share_id'),
    ]
    
    for index_name, table_name, column_name in indexes:
        try:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})')
            print(f"✅ 索引 {index_name} 创建完成")
        except Exception as e:
            print(f"⚠️  创建索引 {index_name} 失败: {e}")

def migrate_database(db_path="evaluation_system.db"):
    """执行数据库迁移"""
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    print(f"🔄 开始迁移数据库: {db_path}")
    print(f"⏰ 迁移时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 创建分享功能表
            create_shared_tables(cursor)
            
            # 创建索引
            create_indexes(cursor)
            
            # 提交事务
            conn.commit()
            
            print("🎉 数据库迁移完成!")
            return True
            
    except Exception as e:
        print(f"❌ 数据库迁移失败: {e}")
        return False

def verify_migration(db_path="evaluation_system.db"):
    """验证迁移结果"""
    print("🔍 验证迁移结果...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 检查表是否存在
            required_tables = ['shared_links', 'shared_access_logs']
            for table in required_tables:
                if check_table_exists(cursor, table):
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"✅ 表 {table} 存在，当前记录数: {count}")
                else:
                    print(f"❌ 表 {table} 不存在!")
                    return False
            
            # 检查索引
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_shared%'")
            indexes = cursor.fetchall()
            print(f"✅ 分享相关索引数量: {len(indexes)}")
            
            print("🎉 迁移验证通过!")
            return True
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

if __name__ == "__main__":
    # 检查参数
    db_path = sys.argv[1] if len(sys.argv) > 1 else "evaluation_system.db"
    
    print("=" * 50)
    print("🚀 HKGAI模型评测系统 - 数据库迁移工具")
    print("=" * 50)
    
    # 执行迁移
    if migrate_database(db_path):
        # 验证迁移
        if verify_migration(db_path):
            print("\n✅ 迁移成功完成!")
            print("📋 新增功能:")
            print("   - 评测结果分享功能")
            print("   - 分享链接管理")
            print("   - 访问日志记录")
        else:
            print("\n⚠️  迁移可能不完整，请检查!")
    else:
        print("\n❌ 迁移失败!")
        sys.exit(1)
