# 网易云音乐后端服务文档

## 项目概述
本后端服务为网易云音乐风格的音乐平台提供核心业务支撑，包含用户管理、歌单维护、播放行为记录等核心模块。采用Flask框架构建，使用SQLAlchemy ORM进行数据库操作，集成Redis实现播放日志的缓冲存储。

## 核心模块

### 用户模块 (user)
- **模型定义**：
  - `User` 表存储用户基础信息
  - 包含用户ID（BigInteger主键）、昵称、头像URL、Cookies等字段
  - 自动维护创建时间和更新时间

### 歌单模块 (playlist)
- **数据同步机制**：
  1. 接收UID参数查询本地数据库
  2. 不存在记录时调用网易云API获取数据
  3. 实现数据库与API数据的自动比对更新
- **缓存策略**：
  - 当API不可用时自动降级返回数据库缓存

### 播放日志模块 (play_log)
- **双存储架构**：
  - Redis临时存储：使用hash结构缓存播放进度（key格式：play_log:{user_id}）
  - MySQL持久化存储：
    - 定时任务每30秒刷写过期日志
    - 智能进度处理（超过90%时长自动归零）
- **数据字段**：
  ```
  | 字段 | 类型 | 描述 |
  |------------|-----------|-------------------|
  | current_position | Float | 智能处理后的播放进度 |
  | song_duration | Float | 歌曲完整时长 |
  | played_at | DateTime | 播放行为发生时间 |
  ```

## 接口文档

### 播放记录接口
`GET /play_logs`
- 参数：
  - user_id（必填）
- 响应示例：
  ```json
  {
    "data": [
      {
        "song_id": 123456,
        "adjusted_current_time": 125.3,
        "song_duration": 240.0,
        "played_at": "2023-09-15T14:30:00"
      }
    ]
  }
  ```

### 歌单接口
`GET /playlist`
- 智能返回策略：
  1. 优先返回最新API数据
  2. API不可用时返回数据库缓存
  3. 数据变更时自动更新本地存储

## 技术亮点
1. **双重日志机制**：
   - 业务日志：记录接口访问、数据同步等关键节点
   - 播放日志：Redis缓存+MySQL持久化的双层存储

2. **异常熔断策略**：
   - 外部API调用超时自动切换本地缓存
   - 数据库操作失败时保留Redis日志等待下次同步

3. **智能进度处理**：
   ```sql
   CASE 
     WHEN current_position >= song_duration * 0.9 THEN 0
     ELSE current_position
   END AS adjusted_current_time
   ```

## 部署指南
1. 依赖安装：
   ```bash
   pip install -r requirements.txt
   ```
2. 数据库初始化：
   ```python
   from utils.db import db
   db.create_all()
   ```
3. 定时任务启动：
   ```python
   # 配置APScheduler执行flush_redis_play_logs
   ```

## 监控指标
- Redis播放日志堆积量
- 数据库同步成功率
- 外部API响应时间

## 架构图
```
[用户请求] → [Nginx] → [Flask应用]
                    ├── 用户模块
                    ├── 歌单模块 → [网易云API]
                    └── 播放模块 → [Redis] → [定时任务] → [MySQL]
```