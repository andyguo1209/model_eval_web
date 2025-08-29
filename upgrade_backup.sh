#!/bin/bash

# ================================
# 🛡️ 数据库备份脚本
# ================================

# 获取当前时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="./backup_${TIMESTAMP}"

echo "🔄 开始数据备份..."

# 创建备份目录
mkdir -p ${BACKUP_DIR}

# 1. 备份数据库文件
if [ -f "evaluation_system.db" ]; then
    echo "📀 备份数据库文件..."
    cp evaluation_system.db ${BACKUP_DIR}/evaluation_system.db.backup
    echo "✅ 数据库备份完成: ${BACKUP_DIR}/evaluation_system.db.backup"
else
    echo "❌ 未找到数据库文件!"
    exit 1
fi

# 2. 备份结果文件夹
if [ -d "results" ]; then
    echo "📁 备份评测结果文件..."
    cp -r results ${BACKUP_DIR}/results_backup
    echo "✅ 结果文件备份完成"
fi

# 3. 备份历史结果
if [ -d "results_history" ]; then
    echo "📂 备份历史结果文件..."
    cp -r results_history ${BACKUP_DIR}/results_history_backup
    echo "✅ 历史结果备份完成"
fi

# 4. 备份上传文件
if [ -d "uploads" ]; then
    echo "📤 备份上传文件..."
    cp -r uploads ${BACKUP_DIR}/uploads_backup
    echo "✅ 上传文件备份完成"
fi

# 5. 备份配置文件
for config_file in "config.env" ".env" "config.py"; do
    if [ -f "$config_file" ]; then
        cp "$config_file" ${BACKUP_DIR}/
        echo "✅ 配置文件 $config_file 备份完成"
    fi
done

echo ""
echo "🎉 数据备份完成!"
echo "📁 备份位置: ${BACKUP_DIR}"
echo "📋 备份内容:"
echo "   - evaluation_system.db.backup (数据库)"
echo "   - results_backup/ (评测结果)"
echo "   - results_history_backup/ (历史结果)"
echo "   - uploads_backup/ (上传文件)"
echo "   - 配置文件"
echo ""
echo "⚠️  重要提示："
echo "   请在升级前确认备份文件完整无误!"
echo "   如果升级失败，可使用备份文件恢复:"
echo "   cp ${BACKUP_DIR}/evaluation_system.db.backup evaluation_system.db"
