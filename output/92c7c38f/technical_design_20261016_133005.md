# 统一认证服务（Auth Service）采用「无状态认证微服务 + API 网关 + Redis 缓存 + 关系型数据库 + 消息队列」的架构。核心设计原则：认证服务本身完全无状态（不保存会话），所有令牌为自包含 JWT，通过 Redis 承载令牌黑名单、登录失败计数、限流计数与密码重置令牌等短生命周期状态，从而支持水平扩展与滚动发布。对外通过 API 网关统一暴露版本化 RESTful 接口（/api/v1/auth/*），网关负责 TLS 终止、全局限流与路由；认证服务内部按领域拆分为注册、登录与令牌签发、令牌认证中间件、密码加密、密码重置、登出与令牌吊销、限流与高并发支撑、安全审计与日志等模块。邮件发送与审计日志写入通过消息队列异步化，避免阻塞认证主链路。可观测性通过 Prometheus 指标、结构化日志与 OpenTelemetry 链路追踪实现。所有功能模块（邮箱注册、邮箱登录与令牌签发、JWT 令牌认证中间件、密码加密存储、密码重置、RESTful API 接口层、登出与令牌吊销、高并发支撑能力、安全审计与日志）均在服务组件、API 端点与数据库表/字段三个层面建立可追溯映射。 - 技术设计方案

## 1. 架构风格
微服务（无状态认证服务）+ API 网关 + 事件驱动异步处理；服务无状态可水平扩展，短生命周期状态外置至 Redis

## 2. 服务组件

### API 网关（Gateway）
- 职责：统一入口，负责 TLS 终止、路由转发、全局 IP 维度限流、请求日志与版本管理（/api/v1），为 RESTful API 接口层提供统一规范与错误码透传。
- 技术栈：Nginx / Kong / Spring Cloud Gateway, TLS 1.3, Rate Limit Plugin

### 认证核心服务（Auth Core Service）
- 职责：承载邮箱注册、邮箱登录与令牌签发、JWT 令牌认证中间件、登出与令牌吊销等核心认证逻辑；无状态设计，可水平扩展。
- 技术栈：Go / Node.js (NestJS) / Java (Spring Boot), JWT (RS256), bcrypt / Argon2id

### 密码安全模块（Password Security Module）
- 职责：实现密码加密存储：bcrypt/Argon2id 加盐哈希、算法与强度参数可配置、密码比对安全校验、历史密码策略（可选），禁止明文存储。
- 技术栈：bcrypt, Argon2id, 配置中心（Nacos/Consul）

### 密码重置服务（Password Reset Service）
- 职责：处理密码重置请求，生成一次性重置令牌，通过消息队列异步发送邮件链接/验证码，校验令牌有效期与一次性，更新密码哈希并失效相关令牌。
- 技术栈：Go / Node.js, Redis (TTL 一次性令牌), RabbitMQ / Kafka, SMTP / 邮件服务商 SDK

### 令牌与缓存服务（Token & Cache Service）
- 职责：管理 JWT 黑名单、刷新令牌吊销、登录失败计数与锁定、限流计数；基于 Redis 实现，支持连接池与集群模式，支撑高并发支撑能力。
- 技术栈：Redis Cluster, Redis 连接池, Lua 脚本原子操作

### 限流与防刷组件（Rate Limiter）
- 职责：按 IP/账号维度对注册、登录、密码重置等接口实施限流与防刷，超限返回 429；对重置邮件发送频率进行限制。
- 技术栈：Redis + 令牌桶/滑动窗口, 网关限流插件

### 审计与日志服务（Audit & Logging Service）
- 职责：消费消息队列中的认证事件，记录登录/注册/重置事件日志、异常登录告警、审计日志留存，并对敏感信息脱敏（不记录明文密码与完整令牌）。
- 技术栈：Kafka / RabbitMQ, Elasticsearch / ClickHouse, OpenTelemetry, Prometheus + Grafana

### 邮件通知服务（Email Notification Worker）
- 职责：异步消费邮件发送任务，投递密码重置链接/验证码，记录送达状态以支撑邮件送达率指标。
- 技术栈：Node.js / Go Worker, SMTP, SendGrid / 阿里云邮件推送

### 数据库层（PostgreSQL）
- 职责：持久化用户账号、密码哈希、刷新令牌、密码重置令牌、登录失败记录、审计日志等数据；通过连接池支撑高并发。
- 技术栈：PostgreSQL 15+, PgBouncer 连接池, 主从复制


## 3. 数据库设计（PostgreSQL 15+（主从复制）+ Redis Cluster（缓存/黑名单/限流））

### users
用户账号表，承载邮箱注册功能：存储邮箱唯一标识、密码哈希（bcrypt/Argon2id 加盐哈希，禁止明文）、账号状态与登录锁定信息。

| 字段 | 类型 | 可空 | 描述 |
|------|------|------|------|

| id | UUID | False | 用户唯一标识（注册成功返回的 user_id），主键 |

| email | VARCHAR(255) | False | 注册邮箱，唯一索引，用于邮箱注册唯一性校验与登录凭据查询 |

| password_hash | VARCHAR(255) | False | 密码加盐哈希值（bcrypt/Argon2id），禁止明文存储 |

| password_algo | VARCHAR(32) | False | 密码哈希算法标识（bcrypt/argon2id），支持算法参数可配置与平滑升级 |

| password_updated_at | TIMESTAMPTZ | True | 密码最近更新时间，用于历史密码策略与令牌失效判断 |

| status | VARCHAR(16) | False | 账号状态：active / locked / disabled，支撑登录失败锁定 |

| failed_login_count | INTEGER | False | 连续登录失败计数，达到 5 次锁定 15 分钟 |

| locked_until | TIMESTAMPTZ | True | 账号锁定截止时间，登录失败锁定策略使用 |

| last_login_at | TIMESTAMPTZ | True | 最近登录时间，用于异常登录检测与审计 |

| created_at | TIMESTAMPTZ | False | 账号创建时间 |

| updated_at | TIMESTAMPTZ | False | 账号更新时间 |

| deleted_at | TIMESTAMPTZ | True | 软删除时间，支撑合规与隐私要求下的用户数据删除请求 |


### refresh_tokens
刷新令牌表，承载邮箱登录与令牌签发中的刷新令牌签发、令牌刷新与登出令牌吊销：记录刷新令牌哈希、有效期与吊销状态。

| 字段 | 类型 | 可空 | 描述 |
|------|------|------|------|

| id | UUID | False | 刷新令牌记录主键 |

| user_id | UUID | False | 所属用户，外键关联 users.id |

| token_hash | VARCHAR(255) | False | 刷新令牌的哈希值（不存储明文令牌），用于令牌刷新校验 |

| jti | VARCHAR(64) | False | JWT 唯一标识，用于令牌吊销与黑名单关联 |

| expires_at | TIMESTAMPTZ | False | 刷新令牌过期时间 |

| revoked_at | TIMESTAMPTZ | True | 吊销时间，登出或密码重置后失效相关令牌 |

| revoked_reason | VARCHAR(32) | True | 吊销原因：logout / password_reset / admin_revoke |

| user_agent | VARCHAR(255) | True | 签发时的客户端 UA，用于异常登录审计 |

| ip_address | INET | True | 签发时的客户端 IP，用于安全审计与异常登录告警 |

| created_at | TIMESTAMPTZ | False | 签发时间 |


### password_reset_tokens
密码重置令牌表，承载密码重置功能：存储一次性重置令牌哈希、有效期与使用状态，校验后允许设置新密码。

| 字段 | 类型 | 可空 | 描述 |
|------|------|------|------|

| id | UUID | False | 重置令牌记录主键 |

| user_id | UUID | False | 所属用户，外键关联 users.id |

| token_hash | VARCHAR(255) | False | 一次性重置令牌哈希（链接/验证码），不存储明文 |

| channel | VARCHAR(16) | False | 重置方式：email_link / email_code |

| expires_at | TIMESTAMPTZ | False | 重置令牌有效期（如 15 分钟） |

| used_at | TIMESTAMPTZ | True | 使用时间，保证一次性校验（已使用不可复用） |

| request_ip | INET | True | 发起重置请求的 IP，用于防刷与审计 |

| created_at | TIMESTAMPTZ | False | 创建时间 |


### password_history
历史密码表，承载密码加密存储中的历史密码策略（可选）：记录历史密码哈希，防止重复使用旧密码。

| 字段 | 类型 | 可空 | 描述 |
|------|------|------|------|

| id | UUID | False | 历史密码记录主键 |

| user_id | UUID | False | 所属用户，外键关联 users.id |

| password_hash | VARCHAR(255) | False | 历史密码哈希值 |

| created_at | TIMESTAMPTZ | False | 记录时间，用于保留最近 N 条历史密码 |


### login_attempts
登录尝试记录表，承载邮箱登录与令牌签发中的登录失败计数与锁定、以及安全审计与日志中的异常登录告警。

| 字段 | 类型 | 可空 | 描述 |
|------|------|------|------|

| id | BIGSERIAL | False | 记录主键 |

| email | VARCHAR(255) | False | 尝试登录的邮箱（脱敏后存储/展示） |

| user_id | UUID | True | 匹配到的用户 ID（邮箱不存在时为空） |

| success | BOOLEAN | False | 登录是否成功 |

| failure_reason | VARCHAR(64) | True | 失败原因：bad_credentials / account_locked / account_disabled |

| ip_address | INET | True | 客户端 IP，用于按 IP 维度限流与异常登录检测 |

| user_agent | VARCHAR(255) | True | 客户端 UA |

| created_at | TIMESTAMPTZ | False | 尝试时间 |


### audit_logs
安全审计日志表，承载安全审计与日志功能：记录登录/注册/重置/登出等关键认证事件，支持审计留存与异常追踪，敏感信息脱敏。

| 字段 | 类型 | 可空 | 描述 |
|------|------|------|------|

| id | BIGSERIAL | False | 审计日志主键 |

| event_type | VARCHAR(64) | False | 事件类型：user_registered / user_login / login_failed / token_refreshed / password_reset_requested / password_reset_completed / user_logout / token_revoked |

| user_id | UUID | True | 关联用户 ID |

| email_masked | VARCHAR(255) | True | 脱敏后的邮箱（如 a***@example.com），满足隐私合规 |

| ip_address | INET | True | 客户端 IP |

| user_agent | VARCHAR(255) | True | 客户端 UA |

| result | VARCHAR(16) | False | 事件结果：success / failure |

| detail | JSONB | True | 事件详情（脱敏，不含明文密码与完整令牌） |

| trace_id | VARCHAR(64) | True | 链路追踪 ID，用于排障 |

| created_at | TIMESTAMPTZ | False | 事件时间，审计日志留存依据 |


### email_delivery_logs
邮件投递日志表，承载密码重置中的邮件发送重置链接/验证码，记录送达状态以支撑邮件送达率指标。

| 字段 | 类型 | 可空 | 描述 |
|------|------|------|------|

| id | BIGSERIAL | False | 投递记录主键 |

| user_id | UUID | True | 关联用户 ID |

| email_masked | VARCHAR(255) | False | 脱敏后的收件邮箱 |

| template | VARCHAR(64) | False | 邮件模板：password_reset_link / password_reset_code |

| status | VARCHAR(16) | False | 投递状态：queued / sent / delivered / failed |

| provider_message_id | VARCHAR(128) | True | 邮件服务商返回的消息 ID |

| error_message | VARCHAR(255) | True | 失败原因 |

| created_at | TIMESTAMPTZ | False | 创建时间 |

| delivered_at | TIMESTAMPTZ | True | 送达时间 |


### rate_limit_policies
限流策略配置表，承载高并发支撑能力中的接口限流与防刷：按 IP/账号维度配置注册、登录、密码重置等接口的限流阈值。

| 字段 | 类型 | 可空 | 描述 |
|------|------|------|------|

| id | UUID | False | 策略主键 |

| scope | VARCHAR(32) | False | 限流维度：ip / account / endpoint |

| endpoint | VARCHAR(128) | False | 目标接口路径，如 /api/v1/auth/login |

| limit_count | INTEGER | False | 窗口内允许请求数 |

| window_seconds | INTEGER | False | 限流窗口秒数 |

| enabled | BOOLEAN | False | 是否启用 |

| created_at | TIMESTAMPTZ | False | 创建时间 |

| updated_at | TIMESTAMPTZ | False | 更新时间 |



## 4. API 端点

### POST /api/v1/auth/register
邮箱注册：校验邮箱格式与唯一性、密码复杂度，使用 bcrypt/Argon2id 加盐哈希存储密码，创建账号并返回用户标识。
- 认证：否

### POST /api/v1/auth/login
邮箱登录与令牌签发：校验邮箱+密码凭据，失败时记录失败计数并在 5 次后锁定 15 分钟，成功则签发 JWT 访问令牌与刷新令牌并返回过期时间。
- 认证：否

### POST /api/v1/auth/refresh
令牌刷新：校验刷新令牌有效性与是否被吊销，通过后签发新的访问令牌并返回新的过期时间。
- 认证：否

### POST /api/v1/auth/logout
登出与令牌吊销：将当前访问令牌加入 Redis 黑名单并吊销对应刷新令牌，返回登出结果。
- 认证：是

### POST /api/v1/auth/password/reset-request
密码重置请求：校验邮箱后生成一次性重置令牌，通过消息队列异步发送重置链接/验证码邮件，并受发送频率限制。
- 认证：否

### POST /api/v1/auth/password/reset-confirm
密码重置确认：校验一次性重置令牌有效期与是否已使用，设置新密码并更新密码哈希，随后失效相关访问令牌与刷新令牌。
- 认证：否

### POST /api/v1/auth/introspect
JWT 令牌认证中间件校验接口：校验令牌签名、有效期与 Redis 黑名单，返回令牌有效性与用户身份，供业务服务低侵入鉴权。
- 认证：否

### GET /api/v1/auth/me
获取当前登录用户身份：受 JWT 令牌认证中间件保护的示例受保护接口，返回当前令牌对应的用户标识与邮箱。
- 认证：是

### GET /api/v1/auth/audit-logs
安全审计与日志查询：按用户/事件类型/时间范围查询登录、注册、重置、登出等关键认证事件审计日志（敏感信息脱敏），仅限安全管理员。
- 认证：是

### GET /api/v1/auth/rate-limit-policies
限流策略查询：返回按 IP/账号维度配置的注册、登录、密码重置接口限流策略，供运维/安全人员查看与核对。
- 认证：是

### PUT /api/v1/auth/rate-limit-policies/{id}
限流策略更新：运维/安全人员调整指定接口的限流阈值与窗口，变更后热生效于网关与认证服务。
- 认证：是

### GET /api/v1/auth/health
健康检查与可观测性：返回服务健康状态、依赖（PostgreSQL/Redis）连通性与关键指标（QPS、延迟、错误率、令牌签发量），供负载均衡与自动扩缩容使用。
- 认证：否

### DELETE /api/v1/auth/users/{user_id}
用户数据删除：响应合规与隐私要求下的用户数据删除请求，软删除账号并吊销其全部令牌、清理重置令牌与历史密码。
- 认证：是


## 5. 技术风险

- **high** - JWT 无状态特性导致令牌吊销存在窗口期，登出/密码重置后旧访问令牌在过期前仍可能被使用（登出与令牌吊销、JWT 令牌认证中间件）
  - 缓解：引入 Redis 黑名单（按 jti 存储，TTL 等于令牌剩余有效期），认证中间件每次校验黑名单；密码重置后吊销该用户全部刷新令牌并写入用户级吊销时间戳，访问令牌签发时间早于该时间戳即失效；黑名单键设置 TTL 自动清理。

- **high** - 高并发下 Redis 成为单点瓶颈或故障导致认证不可用（高并发支撑能力）
  - 缓解：采用 Redis Cluster 分片 + 连接池；黑名单/限流使用 Lua 脚本保证原子性；Redis 故障时降级为「仅校验 JWT 签名与有效期」的宽松模式并告警，避免认证全链路不可用；本地二级缓存热点黑名单。

- **high** - 密码哈希计算（bcrypt cost≥10 / Argon2id）为 CPU 密集操作，高并发登录时导致 P99 延迟超标（密码加密存储、邮箱登录与令牌签发）
  - 缓解：哈希计算放入独立线程池/Worker 并限制并发度；按实例 CPU 核数配置并发上限；登录接口独立限流；压测确定单实例哈希吞吐并据此水平扩展；必要时对同一账号登录做去重合并。

- **high** - 暴力破解与撞库攻击（邮箱登录与令牌签发、高并发支撑能力）
  - 缓解：登录失败 5 次锁定 15 分钟；按 IP + 账号双维度限流，超限返回 429；引入验证码/延迟递增策略；异常登录（新 IP/新 UA）触发告警并记录审计日志。

- **high** - 密码重置令牌泄露或重放（密码重置）
  - 缓解：重置令牌仅存哈希、有效期 15 分钟、一次性使用（used_at 标记）；重置链接使用 HTTPS 且令牌随机强度足够；重置请求按邮箱与 IP 限流防刷；重置成功后吊销全部令牌并记录审计日志。

- **medium** - 审计日志与邮件投递日志中泄露敏感信息（安全审计与日志、合规与隐私）
  - 缓解：日志中禁止记录明文密码与完整令牌，邮箱脱敏存储（email_masked）；审计日志写入前统一脱敏过滤器；审计日志设置留存周期与访问权限控制，仅安全管理员可查询。

- **medium** - 邮件服务商不可用或送达率不足导致密码重置成功率下降（密码重置）
  - 缓解：邮件发送通过消息队列异步化并支持重试与死信队列；记录 email_delivery_logs 监控送达率；配置备用邮件服务商；对失败任务告警。

- **medium** - 数据库连接耗尽或慢查询影响认证性能（高并发支撑能力）
  - 缓解：使用 PgBouncer 连接池并配置合理上限；users.email、refresh_tokens.jti 等关键字段建立索引；读写分离，审计日志写入异步化；对核心接口做压测与慢查询监控。

- **medium** - 水平扩展时配置不一致（JWT 密钥、哈希参数、限流阈值）导致行为不一致（高并发支撑能力、密码加密存储）
  - 缓解：JWT 使用 RS256 非对称密钥，公钥分发、私钥集中管理并支持轮换（kid）；哈希与限流参数通过配置中心统一下发；滚动发布时保证配置版本一致。

- **medium** - 多实例部署下登录失败计数与限流计数不一致（邮箱登录与令牌签发、高并发支撑能力）
  - 缓解：失败计数与限流计数统一使用 Redis 原子操作（INCR + EXPIRE / Lua），数据库仅做审计落库；锁定状态以 Redis 为准并定期与数据库对账。


## 6. 代码骨架
```

auth-service/

├── cmd/

│   └── server/main.go                # 服务入口，加载配置、初始化依赖、启动 HTTP Server

├── internal/

│   ├── config/                       # 配置加载（JWT 密钥、哈希参数、限流阈值、Redis/DB 连接池）

│   ├── api/

│   │   ├── router.go                 # /api/v1/auth/* 路由注册与版本管理

│   │   ├── handler/

│   │   │   ├── register_handler.go   # 邮箱注册

│   │   │   ├── login_handler.go      # 邮箱登录与令牌签发

│   │   │   ├── refresh_handler.go    # 令牌刷新

│   │   │   ├── logout_handler.go     # 登出与令牌吊销

│   │   │   ├── password_handler.go   # 密码重置请求/确认

│   │   │   ├── introspect_handler.go # 令牌校验（认证中间件对外接口）

│   │   │   ├── audit_handler.go      # 安全审计日志查询

│   │   │   └── admin_handler.go      # 限流策略与用户数据删除

│   │   ├── middleware/

│   │   │   ├── jwt_auth.go           # JWT 令牌认证中间件（签名/有效期/黑名单校验）

│   │   │   ├── rate_limit.go         # 限流与防刷中间件（IP/账号维度）

│   │   │   ├── request_id.go         # 链路追踪 ID 注入

│   │   │   └── error_handler.go      # 统一错误码与错误响应

│   │   └── dto/                      # 请求/响应 DTO 与校验规则

│   ├── service/

│   │   ├── auth_service.go           # 注册/登录/登出/刷新编排

│   │   ├── password_service.go       # 密码哈希、比对、历史密码策略

│   │   ├── token_service.go          # JWT 签发/校验、黑名单、刷新令牌管理

│   │   ├── reset_service.go          # 密码重置令牌生成与校验

│   │   └── audit_service.go          # 审计事件发布与查询

│   ├── repository/

│   │   ├── user_repo.go              # users 表访问

│   │   ├── refresh_token_repo.go     # refresh_tokens 表访问

│   │   ├── reset_token_repo.go       # password_reset_tokens 表访问

│   │   ├── audit_repo.go             # audit_logs / login_attempts 表访问

│   │   └── rate_limit_repo.go        # rate_limit_policies 表访问

│   ├── cache/

│   │   ├── redis_client.go           # Redis Cluster 客户端与连接池

│   │   ├── blacklist.go              # 令牌黑名单（jti + TTL）

│   │   └── limiter.go                # 令牌桶/滑动窗口限流（Lua 原子脚本）

│   ├── mq/

│   │   ├── producer.go               # 认证事件/邮件任务投递

│   │   └── consumer.go               # 审计落库与邮件发送消费

│   └── observability/

│       ├── metrics.go                # Prometheus 指标（QPS/延迟/错误率/令牌签发量）

│       └── tracing.go                # OpenTelemetry 链路追踪

├── migrations/                       # 数据库迁移脚本（users/refresh_tokens/...）

├── docs/openapi.yaml                 # OpenAPI/Swagger 接口文档

├── deploy/                           # Dockerfile / k8s manifests / 网关配置

└── tests/                            # 单元测试与压测脚本

```