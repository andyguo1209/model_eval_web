#!/bin/bash

# 🔐 API密钥安全检查脚本
# 用于检测项目中是否意外包含了API密钥

echo "🔍 开始API密钥安全检查..."

# 定义颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_pattern() {
    local pattern=$1
    local description=$2
    local files
    
    files=$(grep -r "$pattern" . --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude="*.md" --exclude="security_check.sh" 2>/dev/null)
    
    if [ -n "$files" ]; then
        echo -e "${RED}❌ 发现可疑内容: $description${NC}"
        echo "$files"
        echo ""
        return 1
    else
        echo -e "${GREEN}✅ $description: 安全${NC}"
        return 0
    fi
}

# 初始化检查结果
ISSUES=0

# 检查OpenAI API密钥格式
if ! check_pattern "sk-[a-zA-Z0-9]{48}" "OpenAI API密钥格式"; then
    ((ISSUES++))
fi

# 检查Google API密钥格式
if ! check_pattern "AIza[a-zA-Z0-9_-]{35}" "Google API密钥格式"; then
    ((ISSUES++))
fi

# 检查常见密钥关键词（但排除明显的占位符）
if ! check_pattern "['\"][a-zA-Z0-9]{20,}['\"]" "长字符串（可能是密钥）" | grep -v "your_.*_key_here"; then
    ((ISSUES++))
fi

# 检查环境变量文件是否被跟踪
if [ -f ".env" ] && git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo -e "${RED}❌ .env文件被Git跟踪！这可能包含敏感信息${NC}"
    ((ISSUES++))
fi

# 检查是否有被跟踪的密钥文件
for pattern in "*.key" "*.pem" "*.secret" "*secret*" "*apikey*"; do
    if git ls-files "$pattern" 2>/dev/null | grep -q .; then
        echo -e "${RED}❌ 发现被跟踪的密钥文件: $pattern${NC}"
        git ls-files "$pattern"
        ((ISSUES++))
    fi
done

# 检查.gitignore是否存在并包含关键排除项
if [ ! -f ".gitignore" ]; then
    echo -e "${RED}❌ 缺少.gitignore文件${NC}"
    ((ISSUES++))
else
    # 检查.gitignore是否包含重要的排除项
    required_patterns=(".env" "*.key" "*.secret")
    for pattern in "${required_patterns[@]}"; do
        if ! grep -q "$pattern" .gitignore; then
            echo -e "${YELLOW}⚠️  .gitignore缺少模式: $pattern${NC}"
        fi
    done
fi

echo ""
echo "🔍 安全检查完成！"

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}🎉 没有发现安全问题！${NC}"
    echo -e "${GREEN}✅ 项目API密钥安全状态良好${NC}"
else
    echo -e "${RED}⚠️  发现 $ISSUES 个潜在安全问题${NC}"
    echo -e "${RED}请立即处理上述问题！${NC}"
    echo ""
    echo "🚨 如果发现真实的API密钥："
    echo "1. 立即撤销该密钥"
    echo "2. 生成新的密钥"
    echo "3. 从Git历史记录中移除（如果已提交）"
    echo "4. 通知团队成员"
    exit 1
fi
