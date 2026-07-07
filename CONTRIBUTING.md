# 🤝 贡献指南

感谢你对 AI Training Gym 感兴趣！我们欢迎各种形式的贡献。

## 📋 目录

- [行为准则](#行为准则)
- [如何贡献](#如何贡献)
- [开发流程](#开发流程)
- [任务贡献规范](#任务贡献规范)
- [代码风格](#代码风格)
- [提交 PR](#提交-pr)

## 行为准则

请阅读并遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。简而言之：**尊重他人，共建友好社区**。

## 如何贡献

### 🐛 报告 Bug

使用 [Bug Report 模板](https://github.com/zhangjiayang6835-cyber/ai-training-gym/issues/new?template=bug_report.md) 提交。

### ✨ 建议新功能

使用 [Feature Request 模板](https://github.com/zhangjiayang6835-cyber/ai-training-gym/issues/new?template=feature_request.md) 提交。

### 📦 贡献新任务

这是最有价值的贡献方式！请参见下方[任务贡献规范](#任务贡献规范)。

### 📖 改进文档

修正拼写错误、完善 README、补充示例代码等。

## 开发流程

```bash
# 1. Fork 本仓库
# 2. Clone 你的 Fork
git clone https://github.com/YOUR_USERNAME/ai-training-gym.git
cd ai-training-gym

# 3. 创建特性分支
git checkout -b feat/your-feature

# 4. 安装依赖
pip install -r requirements.txt

# 5. 进行修改，然后运行测试
pytest tasks/ -v

# 6. 提交并推送
git commit -m "feat: your description"
git push origin feat/your-feature

# 7. 创建 Pull Request
```

## 任务贡献规范

每个任务必须包含以下结构：

```
tasks/<task-id>/
├── task.yaml       # 任务定义（必填）
├── tests/          # 测试脚本目录（必填）
│   └── test_*.py   # pytest 测试
└── data/           # 数据集目录（可选）
    ├── train.jsonl # 训练集
    └── val.jsonl   # 验证集
```

### task.yaml 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 任务唯一标识 |
| `title` | string | 任务标题 |
| `type` | enum | `code_fix` / `generation` / `classification` / `qa` |
| `difficulty` | enum | `easy` / `medium` / `hard` |
| `source` | string | 数据来源说明 |
| `description` | string | 任务描述（中文或英文） |
| `evaluation` | object | 评测配置（至少包含 `metrics`） |

完整模板见 [tasks/task-spec.yaml](tasks/task-spec.yaml)。

### 验证清单

- [ ] task.yaml 包含所有必填字段
- [ ] pytest 测试覆盖安全检查和功能测试
- [ ] 本地运行 `pytest tasks/<task-id>/tests/ -v` 通过
- [ ] 没有硬编码的敏感信息

## 代码风格

- Python 代码遵循 [PEP 8](https://peps.python.org/pep-0008/)
- 使用 `black` 进行自动格式化
- 使用 `flake8` 进行 lint 检查
- 测试文件使用 `pytest` 风格

## 提交 PR

1. 确保 CI 全部通过
2. 在 PR 描述中关联相关 Issue（`Closes #123`）
3. PR 标题格式：`type: brief description`
   - `feat:` 新功能/新任务
   - `fix:` Bug 修复
   - `docs:` 文档更新
   - `ci:` CI 配置变更
   - `refactor:` 代码重构

---

再次感谢你的贡献！❤️
