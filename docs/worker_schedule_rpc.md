# WorkerSchedule gRPC 接口文档

服务名：`worker_schedule.v1.WorkerScheduleService`

## 鉴权方式

所有方法都要求 gRPC metadata：

- `x-user-id`: 调用人ID（必填）
- `x-user-role`: 调用人角色（必填）

缺失任一字段会返回：`UNAUTHENTICATED`。

## 状态定义

### WorkerStatus

- `WORKER_STATUS_AVAILABLE`：空闲
- `WORKER_STATUS_ASSIGNED`：已排单
- `WORKER_STATUS_IN_SERVICE`：服务中

### OrderEventType

- `ORDER_EVENT_TYPE_ASSIGNED`：派单
- `ORDER_EVENT_TYPE_SERVICE_STARTED`：开始服务
- `ORDER_EVENT_TYPE_COMPLETED`：完成订单
- `ORDER_EVENT_TYPE_CANCELED`：取消订单

### ScheduleTaskStatus

- `SCHEDULE_TASK_STATUS_ASSIGNED`
- `SCHEDULE_TASK_STATUS_IN_SERVICE`
- `SCHEDULE_TASK_STATUS_COMPLETED`
- `SCHEDULE_TASK_STATUS_CANCELED`

## 接口列表

### RegisterWorker

注册/更新工人基础信息。

请求：
- `worker_id` string
- `worker_name` string

响应：
- `worker` WorkerRecord

---

### ListWorkers

查询全部工人当前状态（实时查询）。

请求：空

响应：
- `workers[]` WorkerRecord

---

### UpdateWorkerStatus

手动更新工人状态（严格状态机校验）：

- `AVAILABLE -> ASSIGNED`
- `ASSIGNED -> IN_SERVICE`
- `ASSIGNED -> AVAILABLE`
- `IN_SERVICE -> AVAILABLE`

非法迁移返回：`INVALID_ARGUMENT`。

请求：
- `worker_id` string
- `status` WorkerStatus

响应：
- `worker` WorkerRecord

---

### SyncOrderEvent

接收订单事件并自动更新工人状态与排班任务。

请求：
- `order_id` string
- `worker_id` string
- `worker_name` string
- `event_type` OrderEventType
- `start_time` string(ISO-8601, 必须带时区)
- `end_time` string(ISO-8601, 必须带时区)
- `title` string

规则：
- `ASSIGNED`：创建/更新排班任务，并将工人状态更新为 `ASSIGNED`（若已有 `IN_SERVICE` 任务则保持 `IN_SERVICE`）
- `SERVICE_STARTED`：工人状态更新为 `IN_SERVICE`
- `COMPLETED/CANCELED`：任务状态变更后，根据剩余活跃任务回推工人状态
- 若同一工人在时间上有重叠活跃任务，返回：`FAILED_PRECONDITION`

响应：
- `worker` WorkerRecord

---

### ListDailySchedule

按日期查看排班（日历视图数据源）。

请求：
- `date` string (`YYYY-MM-DD`，按 `Asia/Shanghai` 解释)

响应：
- `tasks[]` ScheduleTaskRecord
  - `has_conflict`：是否检测到时间重叠

---

### GetOrderDetail

用于“点击排班查看订单详情”。

请求：
- `order_id` string

响应：
- `task` ScheduleTaskRecord

## 错误码说明

- `UNAUTHENTICATED`: metadata 缺失
- `INVALID_ARGUMENT`: 参数错误、非法状态迁移、时间格式错误
- `NOT_FOUND`: 工人或订单不存在
- `FAILED_PRECONDITION`: 时间冲突、前置状态不满足
