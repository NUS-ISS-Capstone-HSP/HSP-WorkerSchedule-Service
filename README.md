# HSP Worker Schedule Service Template

Python 后端模板，提供同一业务能力的 HTTP + gRPC 双入口，采用共享 `service + model`、分离 transport 的分层结构。

## 架构

- `domain`：领域模型与错误定义
- `repository`：仓储接口与实现（MySQL / InMemory）
- `service`：核心业务逻辑（与 transport 无关）
- `transport/http`：FastAPI controller、schema、mapper
- `transport/grpc`：gRPC servicer、mapper
- `bootstrap`：依赖装配（单进程启动 HTTP + gRPC）

## 功能接口

HTTP:
- `GET /healthz`
- `POST /api/schedule/v1/echo`
- `GET /api/schedule/v1/echo/{id}`

gRPC:
- `CreateEcho`
- `GetEcho`
- `Health`

## 本地开发

0. 准备 Python 环境（建议 3.12）

```bash
python --version
```

1. 准备环境变量文件

```bash
cp .env.example .env
```

如果服务在本机运行（`make run`），MySQL 也在本机 Docker 映射端口（如 `127.0.0.1:3306`），请将 `.env` 中的 `MYSQL_DSN` 改为：

```env
MYSQL_DSN=mysql+aiomysql://<username>:<pwd>@127.0.0.1:3306/execution_db
```

2. 安装依赖

```bash
make install
```

3. 生成 gRPC 代码（修改 proto 后执行）

```bash
make proto-gen
```

4. 运行服务（HTTP 8080 + gRPC 50051）

```bash
make run
```

5. 验证服务

```bash
curl http://127.0.0.1:8080/healthz
```

返回 `{"status":"ok"}` 表示 HTTP 服务启动成功。

6. 查看 Swagger/OpenAPI 文档

- Swagger UI: `http://127.0.0.1:8080/docs`
- OpenAPI JSON: `http://127.0.0.1:8080/openapi.json`

## 质量检查

```bash
make lint
make test-unit
make coverage
make swagger
```

## Docker

```bash
make docker-build
```

## 环境变量

参考 `.env.example`，关键项：
- `HTTP_HOST` / `HTTP_PORT`
- `GRPC_HOST` / `GRPC_PORT`
- `MYSQL_DSN`
- `USE_MOCK_REPOSITORY`
