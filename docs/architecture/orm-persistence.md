# ORM 持久化与裸 SQL 审计

## 策略

`agent/adapters/orm/` 下的运行时仓储全部使用 SQLAlchemy Core 表达式
（`select` / `insert` / `update` / `delete` 作用于 `models.py` 中的 `Table` 对象），
不拼接 SQL 字符串。标识符（表名、列名）只能来自 ORM 模型常量或
`runtime_schema.RUNTIME_TABLES` 白名单，不接受调用方输入。

## 已批准的裸 SQL 例外

| 位置 | 语句 | 保留原因 |
| ---- | ---- | -------- |
| `agent/adapters/orm/database.py` | `PRAGMA foreign_keys = ON`、`PRAGMA busy_timeout = 5000` | 每个 SQLite 连接必须单独设置；无 ORM 等价物。语句为静态常量。 |
| `agent/adapters/orm/database.py` | `BEGIN IMMEDIATE` | SQLite 写串行化语义（租约/合并状态的写锁获取），需要显式事务模式。 |
| `agent/adapters/sqlite/*.py`、`agent/memory/repository.py` | 旧 sqlite3 驱动的参数化语句 | 迁移前遗留层；仅使用 `?` 占位符参数，无标识符插值。按 change 逐个移植到 ORM 后删除。 |

测试代码中的裸 SQL（如 `test_orm_database.py` 查询 `alembic_version`）仅用于
断言，不进入产品路径。

## 桌面打包约束

后端在启动时通过 `run_migrations()` 执行 Alembic 升级，因此桌面打包
（`web/scripts/package-backend.cjs`）必须携带 `alembic.ini` 与 `alembic/`
目录（`--add-data` 到 PyInstaller `_internal/`），打包脚本在构建后强制校验
这两个资产存在。`run_migrations()` 以绝对路径设置 `script_location`，
与进程工作目录（桌面端为 userData 目录）无关。
