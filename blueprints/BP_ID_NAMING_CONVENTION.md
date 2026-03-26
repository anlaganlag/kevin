# Blueprint ID 命名规范

## 概述

Blueprint ID 是 Blueprint 的唯一标识符，应该具有**语义化**、**可读性**和**可追溯性**。

## 命名格式

### 标准格式

```
bp_{domain}_{type}_{name}.{version}
```

### 格式说明

| 部分 | 说明 | 示例 | 必需 |
|------|------|------|------|
| `bp_` | Blueprint 前缀 | `bp_` | ✅ 是 |
| `{domain}` | 业务域/模块 | `frontend`, `backend`, `auth`, `payment` | ✅ 是 |
| `{type}` | Blueprint 类型 | `feature`, `bugfix`, `incident`, `refactor`, `infra` | ✅ 是 |
| `{name}` | 具体功能/任务名称 | `jwt_login`, `user_profile`, `api_timeout` | ✅ 是 |
| `.{version}` | 版本号 | `1.0.0`, `1.1.0`, `2.0.0` | ✅ 是 |

## 命名示例

### 功能开发 (Feature Development)

```
# 后端功能
bp_backend_feature_user_registration.1.0.0
bp_backend_feature_payment_integration.1.0.0
bp_auth_feature_jwt_authentication.1.0.0
bp_api_feature_rate_limiting.1.0.0

# 前端功能
bp_frontend_feature_user_dashboard.1.0.0
bp_frontend_feature_shopping_cart.1.0.0
bp_ui_feature_dark_mode.1.0.0
bp_mobile_feature_push_notification.1.0.0
```

### Bug 修复 (Bug Fix)

```
# 后端 Bug
bp_backend_bugfix_api_timeout.1.0.0
bp_backend_bugfix_memory_leak.1.0.0
bp_auth_bugfix_token_validation.1.0.0
bp_database_bugfix_connection_pool.1.0.0

# 前端 Bug
bp_frontend_bugfix_login_button.1.0.0
bp_ui_bugfix_responsive_layout.1.0.0
bp_mobile_bugfix_crash_on_launch.1.0.0
```

### 事件响应 (Incident Response)

```
bp_incident_database_outage.1.0.0
bp_incident_payment_gateway_down.1.0.0
bp_incident_high_cpu_usage.1.0.0
bp_incident_security_breach.1.0.0
```

### 重构 (Refactoring)

```
bp_backend_refactor_legacy_code.1.0.0
bp_frontend_refactor_component_library.1.0.0
bp_api_refactor_rest_to_graphql.1.0.0
```

### 基础设施变更 (Infrastructure)

```
bp_infra_k8s_migration.1.0.0
bp_infra_ci_cd_pipeline.1.0.0
bp_infra_monitoring_setup.1.0.0
bp_infra_vpc_configuration.1.0.0
```

### 数据分析 (Data Analysis)

```
bp_analytics_user_behavior.1.0.0
bp_analytics_performance_metrics.1.0.0
bp_analytics_sales_report.1.0.0
```

## 版本号规范

遵循 [Semantic Versioning 2.0.0](https://semver.org/)：

```
MAJOR.MINOR.PATCH

MAJOR:    不兼容的 API 变更
MINOR:    向后兼容的功能新增
PATCH:    向后兼容的问题修复
```

### 版本示例

```
bp_auth_feature_jwt_authentication.1.0.0    # 初始版本
bp_auth_feature_jwt_authentication.1.1.0    # 新增 refresh token 功能
bp_auth_feature_jwt_authentication.1.1.1    # 修复 token 过期时间 bug
bp_auth_feature_jwt_authentication.2.0.0    # 重构 API，不兼容 1.x
```

## Domain（域）分类

### 通用域

| Domain | 说明 | 示例 |
|--------|------|------|
| `frontend` | 前端相关 | React, Vue, Angular 等 |
| `backend` | 后端相关 | API, 服务层等 |
| `auth` | 认证授权 | 登录, 权限等 |
| `database` | 数据库相关 | Schema, 迁移等 |
| `infra` | 基础设施 | K8s, Terraform 等 |
| `ci_cd` | CI/CD 流水线 | GitHub Actions, Jenkins 等 |
| `monitoring` | 监控告警 | Prometheus, Grafana 等 |
| `security` | 安全相关 | 漏洞修复, 安全扫描等 |
| `performance` | 性能优化 | 缓存, 查询优化等 |
| `testing` | 测试相关 | 单元测试, 集成测试等 |
| `ui_ux` | UI/UX 设计 | 组件, 样式等 |
| `mobile` | 移动端 | iOS, Android 等 |
| `analytics` | 数据分析 | 报表, 指标等 |

### 业务域（根据实际业务调整）

| Domain | 说明 |
|--------|------|
| `payment` | 支付相关 |
| `order` | 订单相关 |
| `user` | 用户相关 |
| `product` | 商品相关 |
| `inventory` | 库存相关 |
| `shipping` | 物流相关 |

## Type（类型）分类

| Type | 说明 | 使用场景 |
|------|------|----------|
| `feature` | 新功能开发 | 添加新功能, 新特性 |
| `bugfix` | Bug 修复 | 修复缺陷, 错误 |
| `incident` | 事件响应 | 生产事故, 紧急修复 |
| `refactor` | 重构 | 代码重构, 架构调整 |
| `infra` | 基础设施变更 | IaC, 配置变更 |
| `perf` | 性能优化 | 性能提升, 优化 |
| `security` | 安全相关 | 安全加固, 漏洞修复 |
| `test` | 测试相关 | 测试增强, 覆盖率提升 |
| `docs` | 文档更新 | API 文档, 架构文档 |
| `config` | 配置变更 | 特性开关, 环境配置 |

## Name（名称）规范

### 命名原则

1. **使用小写字母**
2. **单词间用下划线分隔**
3. **使用描述性名称**
4. **避免缩写（除非是通用缩写）**
5. **简洁但明确**

### 好的示例

```
✅ bp_auth_feature_jwt_authentication.1.0.0
✅ bp_frontend_bugfix_login_button.1.0.0
✅ bp_backend_refactor_user_service.1.0.0
✅ bp_infra_k8s_migration.1.0.0
```

### 不好的示例

```
❌ bp_auth_feat_jwt.1.0.0                    # 缩写不明确
❌ bp_frontend_bug_fix_login_btn.1.0.0       # 过长
❌ bp_backend_feature_do_something.1.0.0     # 不明确
❌ bp-auth-feature-jwt-authentication.1.0.0  # 使用连字符
❌ BP_AUTH_FEATURE_JWT.1.0.0                 # 使用大写
```

## 特殊场景

### 1. 紧急 Hotfix

```
bp_{domain}_hotfix_{name}.{version}

示例:
bp_auth_hotfix_critical_vulnerability.1.0.0
bp_payment_hotfix_transaction_fail.1.0.0
```

### 2. 实验性功能

```
bp_{domain}_experimental_{name}.{version}

示例:
bp_frontend_experimental_ai_chatbot.0.1.0
```

### 3. 依赖/依赖更新

```
bp_{domain}_deps_update_{name}.{version}

示例:
bp_backend_deps_update_spring_boot.1.0.0
bp_frontend_deps_update_react.1.0.0
```

## Blueprint ID 与 GitHub Issue 的关联

### 推荐做法

在 GitHub Issue 的标题中使用 Blueprint ID：

```
[bp_auth_feature_jwt_authentication.1.0.0] 实现 JWT 认证系统
```

### Issue 标签

建议添加以下标签：
- `blueprint`
- `{domain}`: `auth`, `frontend`, `backend` 等
- `{type}`: `feature`, `bugfix`, `incident` 等
- `version:{version}`: `version:1.0.0`

### Issue 模板

```markdown
## Blueprint ID
bp_auth_feature_jwt_authentication.1.0.0

## Blueprint Type
feature_development

## Description
实现基于 JWT 的用户认证系统

## Acceptance Criteria
- [ ] 用户注册功能
- [ ] 用户登录功能
- [ ] JWT Token 生成和验证
- [ ] Token 刷新机制

## Blocks
- [ ] BLOCK-BA-REQUIREMENT-ANALYSIS
- [ ] BLOCK-PLANNING-ARCHITECTURE-DESIGN
- [ ] BLOCK-BUILDER-AUTH-IMPLEMENTATION
- [ ] BLOCK-QA-TESTING
- [ ] BLOCK-SECURITY-SCANNING
```

## Blueprint ID 查询和检索

### 按域查询

```bash
# 查询所有认证相关的 Blueprint
bp_auth_*

# 查询所有前端相关的 Blueprint
bp_frontend_*
```

### 按类型查询

```bash
# 查询所有功能开发的 Blueprint
*_feature_*

# 查询所有 Bug 修复的 Blueprint
*_bugfix_*
```

### 按版本查询

```bash
# 查询特定版本
bp_auth_feature_jwt_authentication.1.0.0

# 查询所有 1.x 版本
bp_auth_feature_jwt_authentication.1.*
```

## 迁移指南

### 从旧格式迁移

如果现有 Blueprint 使用旧格式（如 `BLUEPRINT-20260326-001`），可以按以下方式迁移：

```
旧格式: BLUEPRINT-20260326-001
新格式: bp_auth_feature_jwt_authentication.1.0.0

迁移步骤:
1. 确定业务域: auth
2. 确定类型: feature
3. 确定名称: jwt_authentication
4. 分配版本: 1.0.0
```

### 向后兼容

在迁移期间，可以在 Blueprint 元数据中保留旧 ID：

```yaml
metadata:
  blueprint_id: "bp_auth_feature_jwt_authentication.1.0.0"
  legacy_id: "BLUEPRINT-20260326-001"  # 保留以便追溯
```

## 最佳实践

1. **命名一致性**: 在项目中保持命名风格一致
2. **文档化**: 将命名规范写入项目文档
3. **自动化**: 使用工具验证 Blueprint ID 格式
4. **版本管理**: 遵循 Semantic Versioning
5. **可追溯性**: 在 Git commit 和 PR 中引用 Blueprint ID

## 验证规则

可以使用以下正则表达式验证 Blueprint ID 格式：

```regex
^bp_[a-z0-9]+_(feature|bugfix|incident|refactor|infra|perf|security|test|docs|config|hotfix|experimental|deps_update)_[a-z0-9_]+\.\d+\.\d+\.\d+$
```

### 验证示例

```python
import re

def validate_blueprint_id(blueprint_id):
    pattern = r'^bp_[a-z0-9]+_(feature|bugfix|incident|refactor|infra|perf|security|test|docs|config|hotfix|experimental|deps_update)_[a-z0-9_]+\.\d+\.\d+\.\d+$'
    return bool(re.match(pattern, blueprint_id))

# 测试
print(validate_blueprint_id("bp_auth_feature_jwt_authentication.1.0.0"))  # True
print(validate_blueprint_id("BP_AUTH_FEATURE_JWT.1.0.0"))                # False
print(validate_blueprint_id("bp-auth-feature-jwt.1.0.0"))                # False
```

## 总结

使用语义化的 Blueprint ID 命名规范可以：

✅ 提高可读性和可理解性
✅ 便于分类和检索
✅ 支持版本管理
✅ 增强可追溯性
✅ 提升团队协作效率
