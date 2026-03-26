# Rules 和 Constraints 配置管理架构

## 概述

实现 Rules 和 Constraints 的切面化、全局管理，支持从项目目录加载配置，并允许 Blueprint 级别的覆盖和扩展。

## 目录结构

```
project/
├── .agentic/                    # AgenticSDLC 配置目录
│   ├── profiles/                # 配置概要（预设组合）
│   │   ├── default_profile.yaml
│   │   ├── strict_profile.yaml
│   │   └── fast_profile.yaml
│   │
│   ├── rules/                   # 规则定义
│   │   ├── naming/              # 命名规范
│   │   │   ├── general.yaml
│   │   │   ├── go.yaml
│   │   │   ├── typescript.yaml
│   │   │   └── python.yaml
│   │   │
│   │   ├── code_style/          # 代码风格
│   │   │   ├── general.yaml
│   │   │   ├── linters.yaml
│   │   │   └── formatters.yaml
│   │   │
│   │   ├── security/            # 安全规则
│   │   │   ├── owasp_top10.yaml
│   │   │   ├── secret_management.yaml
│   │   │   └── dependency_scanning.yaml
│   │   │
│   │   ├── testing/             # 测试规则
│   │   │   ├── coverage.yaml
│   │   │   ├── unit_tests.yaml
│   │   │   └── integration_tests.yaml
│   │   │
│   │   ├── documentation/       # 文档规则
│   │   │   ├── api_docs.yaml
│   │   │   ├── code_comments.yaml
│   │   │   └── readme.yaml
│   │   │
│   │   └── workflows/           # 工作流规则
│   │       ├── git_workflow.yaml
│   │       ├── pr_workflow.yaml
│   │       └── release_workflow.yaml
│   │
│   ├── constraints/             # 约束定义
│   │   ├── infra/               # 基础设施约束
│   │   │   ├── static/
│   │   │   │   ├── version_control.yaml
│   │   │   │   ├── pipeline_system.yaml
│   │   │   │   ├── network_architecture.yaml
│   │   │   │   ├── technical_stack.yaml
│   │   │   │   └── access_control.yaml
│   │   │   │
│   │   │   └── dynamic/
│   │   │       ├── resource_quotas.yaml
│   │   │       ├── deployment_status.yaml
│   │   │       └── network_topology.yaml
│   │   │
│   │   ├── devops/              # DevOps 约束
│   │   │   ├── ci/
│   │   │   │   ├── platforms.yaml
│   │   │   │   ├── pipelines.yaml
│   │   │   │   └── quality_gates.yaml
│   │   │   │
│   │   │   └── cd/
│   │   │       ├── strategies.yaml
│   │   │       ├── environments.yaml
│   │   │       └── rollback_policies.yaml
│   │   │
│   │   ├── business/            # 业务约束
│   │   │   ├── api_standards.yaml
│   │   │   ├── data_models.yaml
│   │   │   ├── compliance.yaml
│   │   │   └── slos.yaml
│   │   │
│   │   └── resources/           # 资源约束
│   │       ├── compute.yaml
│   │       ├── storage.yaml
│   │       └── budgets.yaml
│   │
│   └── templates/               # 规则/约束模板
│       ├── microservice_template.yaml
│       ├── webapp_template.yaml
│       └── library_template.yaml
│
└── blueprints/                  # Blueprint 定义
    ├── bp_auth_feature_jwt.1.0.0.yaml
    └── bp_frontend_bugfix_login.1.0.0.yaml
```

## 配置加载优先级

```
1. 系统默认配置 (最低优先级)
   ↓
2. 全局项目配置 (.agentic/)
   ↓
3. Profile 配置 (.agentic/profiles/)
   ↓
4. Blueprint 级别配置 (Blueprint 文件中)
   ↓
5. 运行时覆盖 (最高优先级)
```

## 配置文件格式

### 1. Rules 配置示例

#### `.agentic/rules/naming/general.yaml`
```yaml
rules:
  naming_conventions:
    # 通用命名规范
    files:
      convention: "snake_case"
      max_length: 100
      forbidden_chars: [" ", "@", "#"]

    directories:
      convention: "snake_case"
      max_depth: 5

    environment_variables:
      convention: "SCREAMING_SNAKE_CASE"
      prefix: "APP_"

    git_branches:
      convention: "kebab-case"
      forbidden_prefixes: ["origin/"]

  validation:
    on_create: true
    on_update: false
    severity: "warning"
```

#### `.agentic/rules/naming/go.yaml`
```yaml
extends: "general.yaml"

rules:
  naming_conventions:
    # Go 特定命名规范
    files:
      convention: "snake_case"
      test_suffix: "_test.go"
      interface_suffix: "er.go"

    packages:
      convention: "lowercase"
      no_underscores: true

    constants:
      convention: "PascalCase"
      max_length: 50

    variables:
      convention: "camelCase"
      exported: "PascalCase"
      private: "camelCase"

    functions:
      exported: "PascalCase"
      private: "camelCase"
      receivers: "one_letter_or_abbr"

    interfaces:
      convention: "PascalCase"
      suffix: "er"

  overrides:
    - rule: "files.convention"
      value: "snake_case"
      scope: "go_only"
```

#### `.agentic/rules/security/owasp_top10.yaml`
```yaml
rules:
  security:
    owasp_top_10:
      # A01:2021 – Broken Access Control
      access_control:
        enforce_authentication: true
        authorize_all_requests: true
        limit_admin_access: true
        check_user_ownership: true

      # A02:2021 – Cryptographic Failures
      cryptography:
        encrypt_sensitive_data: true
        use_strong_encryption: "AES-256"
        no_hardcoded_secrets: true
        tls_required: true
        min_tls_version: "1.2"

      # A03:2021 – Injection
      injection:
        use_parameterized_queries: true
        validate_input: true
        escape_output: true
        no_sql_concatenation: true

      # A04:2021 – Insecure Design
      secure_design:
        threat_modeling: true
        security_review: true
        principle_of_least_privilege: true

      # A05:2021 – Security Misconfiguration
      secure_configuration:
        no_default_credentials: true
        disable_debug_mode: true
        secure_headers: true
        cors_restriction: true

      # A06:2021 – Vulnerable and Outdated Components
      dependency_management:
        scan_dependencies: true
        update_dependencies: true
        no_vulnerable_versions: true

      # A07:2021 – Identification and Authentication Failures
      authentication:
        password_policy:
          min_length: 12
          require_special_char: true
          require_number: true
          require_uppercase: true
        session_management:
          timeout: 1800  # 30 minutes
          secure_cookies: true
          regenerate_on_login: true

      # A08:2021 – Software and Data Integrity Failures
      integrity:
        verify_signatures: true
        checksum_validation: true
        immutable_logs: true

      # A09:2021 – Security Logging and Monitoring Failures
      logging:
        log_auth_events: true
        log_failures: true
        log_admin_actions: true
        audit_trail: true

      # A10:2021 – Server-Side Request Forgery (SSRF)
      ssrf_protection:
        validate_urls: true
        block_private_ips: true
        network_segmentation: true

  enforcement:
    level: "strict"  # strict | moderate | advisory
    block_violations: true
    auto_fix: false
```

### 2. Constraints 配置示例

#### `.agentic/constraints/infra/static/technical_stack.yaml`
```yaml
constraints:
  technical_stack:
    # 允许的编程语言
    languages:
      - name: "Go"
        version: ">= 1.21"
        primary: true
        use_cases: ["backend", "microservices"]

      - name: "TypeScript"
        version: ">= 5.0"
        primary: true
        use_cases: ["frontend", "backend"]

      - name: "Python"
        version: ">= 3.11"
        primary: false
        use_cases: ["scripts", "data_processing"]

    # 框架版本
    frameworks:
      - name: "Gin"
        language: "Go"
        version: ">= 1.9.0"

      - name: "React"
        language: "TypeScript"
        version: ">= 18.0.0"

      - name: "FastAPI"
        language: "Python"
        version: ">= 0.100.0"

    # 数据库
    databases:
      - name: "PostgreSQL"
        version: ">= 14.0"
        primary: true

      - name: "Redis"
        version: ">= 7.0"
        use_case: "cache"

    # 消息队列
    message_queues:
      - name: "RabbitMQ"
        version: ">= 3.12"
        use_case: "task_queue"

      - name: "Kafka"
        version: ">= 3.5"
        use_case: "event_streaming"

  validation:
    enforce_version_constraints: true
    allow_latest: false
    require_pinned_versions: true
```

#### `.agentic/constraints/devops/ci/quality_gates.yaml`
```yaml
constraints:
  quality_gates:
    # 测试覆盖率
    test_coverage:
      minimum: 95
      threshold: "hard_gate"  # hard_gate | soft_gate | advisory
      per_module: false
      exclude_patterns:
        - "*/mocks/*"
        - "*/generated/*"

    # 代码质量
    code_quality:
      max_complexity: 10
      max_function_length: 50
      max_file_length: 500
      code_smells: 5
      vulnerabilities:
        critical: 0
        high: 0
        medium: 3
        low: 10

    # 安全扫描
    security_scan:
      sast:
        required: true
        tools: ["semgrep", "sonarqube"]
        fail_threshold: "high"

      dast:
        required: true
        tools: ["owasp_zap"]
        fail_threshold: "medium"

      dependency_scan:
        required: true
        tools: ["snyk", "dependabot"]
        fail_threshold: "high"

    # 性能测试
    performance:
      response_time_p95: 200  # ms
      response_time_p99: 500  # ms
      throughput: 1000  # req/s
      memory_leak_check: true

    # 文档
    documentation:
      api_docs_required: true
      readme_required: true
      changelog_required: true

  enforcement:
    block_on_failure: true
    auto_fix_style: true
    notification_on_failure: true
```

## Blueprint 中的配置引用

### 更新后的 Blueprint 模板

```yaml
blueprint:
  metadata:
    blueprint_id: "bp_auth_feature_jwt_authentication.1.0.0"
    profile: "default_profile"  # 引用 Profile

  # ================================================================
  # 配置加载声明
  # ================================================================
  configuration:
    # Profile 引用（快速应用预设配置）
    profile:
      name: "strict_profile"  # 或 "default_profile", "fast_profile"
      overrides:
        # 覆盖 Profile 中的特定配置
        security:
          level: "very_strict"

    # Rules 加载声明
    rules:
      # 方式1: 引用整个规则目录
      load_from:
        - ".agentic/rules/naming/"
        - ".agentic/rules/security/"
        - ".agentic/rules/testing/"

      # 方式2: 引用特定规则文件
      specific:
        - ".agentic/rules/code_style/linters.yaml"
        - ".agentic/rules/workflows/pr_workflow.yaml"

      # 方式3: Blueprint 特定规则（内联定义）
      inline:
        custom_rules:
          - name: "jwt_token_expiration"
            rule: "JWT tokens must expire within 1 hour"
            enforcement: "strict"
            validator: "custom_jwt_validator"

    # Constraints 加载声明
    constraints:
      # 方式1: 引用整个约束目录
      load_from:
        - ".agentic/constraints/infra/static/"
        - ".agentic/constraints/devops/ci/"

      # 方式2: 引用特定约束文件
      specific:
        - ".agentic/constraints/infra/static/technical_stack.yaml"
        - ".agentic/constraints/devops/ci/quality_gates.yaml"

      # 方式3: Blueprint 特定约束（内联定义和覆盖）
      inline:
        technical_stack:
          # 覆盖全局约束，本 Blueprint 使用特定版本
          go_version: "1.22"  # 覆盖全局的 1.21

        resource_quotas:
          # Blueprint 特定的资源限制
          max_cpu: "4"
          max_memory: "8Gi"
          timeout: "30m"

  # ================================================================
  # 配置合并后的结果（运行时生成）
  # ================================================================
  # 以下内容由系统在运行时自动合并生成
  # 展示最终生效的 Rules 和 Constraints

  # rules: (系统自动加载并合并)
  #   naming: (从 .agentic/rules/naming/ 加载)
  #   security: (从 .agentic/rules/security/ 加载)
  #   testing: (从 .agentic/rules/testing/ 加载)
  #   custom: (从 Blueprint inline 加载)
  #
  # constraints: (系统自动加载并合并)
  #   technical_stack: (从 .agentic/constraints/infra/static/technical_stack.yaml 加载，然后应用 Blueprint inline 覆盖)
  #   quality_gates: (从 .agentic/constraints/devops/ci/quality_gates.yaml 加载)
  #   resource_quotas: (从 Blueprint inline 加载)
```

## Profile 配置示例

### `.agentic/profiles/default_profile.yaml`
```yaml
profile:
  name: "default_profile"
  description: "默认配置概要，平衡速度和质量"

  rules:
    naming:
      - ".agentic/rules/naming/general.yaml"
      - ".agentic/rules/naming/go.yaml"
      - ".agentic/rules/naming/typescript.yaml"

    security:
      - ".agentic/rules/security/owasp_top10.yaml"

    testing:
      - ".agentic/rules/testing/coverage.yaml"
      - ".agentic/rules/testing/unit_tests.yaml"

  constraints:
    infra:
      - ".agentic/constraints/infra/static/"

    devops:
      - ".agentic/constraints/devops/ci/"
      - ".agentic/constraints/devops/cd/"

  settings:
    quality_vs_speed: "balanced"
    security_level: "moderate"
    testing_depth: "standard"
```

### `.agentic/profiles/strict_profile.yaml`
```yaml
profile:
  name: "strict_profile"
  description: "严格配置概要，优先保证质量和安全"

  extends: "default_profile"  # 继承并覆盖

  rules:
    security:
      - ".agentic/rules/security/owasp_top10.yaml"  # 覆盖，使用更严格的配置

    testing:
      - ".agentic/rules/testing/coverage.yaml"
      - ".agentic/rules/testing/unit_tests.yaml"
      - ".agentic/rules/testing/integration_tests.yaml"  # 额外的集成测试

  constraints:
    quality_gates:
      test_coverage:
        minimum: 98  # 覆盖默认的 95

      security_scan:
        fail_threshold: "medium"  # 覆盖默认的 "high"

  settings:
    quality_vs_speed: "quality_first"
    security_level: "strict"
    testing_depth: "comprehensive"
```

### `.agentic/profiles/fast_profile.yaml`
```yaml
profile:
  name: "fast_profile"
  description: "快速迭代配置概要，优先保证速度"

  extends: "default_profile"

  rules:
    testing:
      - ".agentic/rules/testing/unit_tests.yaml"  # 只要求单元测试

  constraints:
    quality_gates:
      test_coverage:
        minimum: 80  # 降低覆盖率要求
        threshold: "soft_gate"  # 改为软门禁

      security_scan:
        fail_threshold: "critical"  # 只阻止 critical 级别

  settings:
    quality_vs_speed: "speed_first"
    security_level: "basic"
    testing_depth: "minimal"
```

## 配置验证规则

```yaml
# .agentic/config_validation.yaml
validation:
  # 配置文件语法验证
  syntax:
    schema_version: "1.0"
    validator: "json_schema"
    strict_mode: true

  # 引用验证
  references:
    check_existence: true
    warn_on_broken_links: true
    allow_wildcards: true

  # 值验证
  values:
    type_checking: true
    range_validation: true
    enum_validation: true

  # 冲突检测
  conflicts:
    detect_overrides: true
    warn_on_silent_override: true
    require_explicit_override: true

  # 循环依赖检测
  cycles:
    detect_circular_refs: true
    max_depth: 10
```

## 配置热更新

```yaml
# .agentic/config_reload_policy.yaml
reload_policy:
  # 自动重载
  auto_reload:
    enabled: true
    watch_directories:
      - ".agentic/rules/"
      - ".agentic/constraints/"
    debounce_seconds: 5

  # 重载验证
  validate_on_reload: true
  rollback_on_error: true

  # 通知
  notify_on_reload:
    channels: ["slack", "email"]
    on_success: false
    on_failure: true

  # 版本控制
  versioning:
    track_changes: true
    auto_commit: false
    require_approval: true
```

## 配置管理 CLI 命令

```bash
# 验证配置
agentic config validate

# 查看当前生效的配置
agentic config show

# 查看配置来源
agentic config trace <rule_name>

# 测试配置
agentic config test --blueprint bp_auth_feature_jwt.1.0.0

# 导出配置
agentic config export --output merged_config.yaml

# 创建 Profile
agentic profile create --name custom_profile --extends default_profile

# 比较 Profile
agentic profile diff default_profile strict_profile
```

## 最佳实践

### 1. 配置组织

✅ **推荐**:
```yaml
configuration:
  rules:
    load_from:
      - ".agentic/rules/naming/"      # 按类别组织
      - ".agentic/rules/security/"
```

❌ **不推荐**:
```yaml
configuration:
  rules:
    specific:
      - ".agentic/rules/naming/go.yaml"
      - ".agentic/rules/naming/typescript.yaml"
      - ".agentic/rules/naming/python.yaml"
      # ... 列出所有文件
```

### 2. 使用 Profile

✅ **推荐**:
```yaml
configuration:
  profile:
    name: "strict_profile"
```

❌ **不推荐**:
```yaml
configuration:
  rules:
    load_from:
      - ".agentic/rules/naming/"
      - ".agentic/rules/security/"
      - ".agentic/rules/testing/"
    # ... 手动列出所有规则
```

### 3. 明确覆盖

✅ **推荐**:
```yaml
configuration:
  constraints:
    inline:
      test_coverage:
        minimum: 98  # 明确覆盖全局的 95
```

❌ **不推荐**:
```yaml
constraints:
  test_coverage:
    minimum: 98  # 不清楚这是覆盖还是全局配置
```

## 总结

通过这种配置管理架构，我们可以：

✅ **全局管理** - 在 `.agentic/` 目录统一管理所有规则和约束
✅ **切面化** - 按类别组织（命名、安全、测试等）
✅ **层级覆盖** - 支持 Profile 全局配置和 Blueprint 局部覆盖
✅ **可追溯** - 每个配置都有明确的来源和优先级
✅ **易于维护** - 集中管理，避免重复配置
✅ **灵活性** - 支持内联覆盖和运行时覆盖
