# 河桥振动试验归档

资料员从仪器收到一份有序原卷。甲乙班各领一个冻结父版，登记自己的勘误。发行员交出固定交换件，夜班关闭源库后仍能接纳和合流。领卷人员按卷号核对每次读数的出处和合计。

## 运行

使用 Python 3.11 标准库和 SQLite。平台提供 `check_project.py`。

```sh
python3 -B check_project.py
python3 -B demo.py samples/shift.json
```

直接运行完整回归可执行 `python3 -B -m unittest discover -s tests -t .`。

演示在临时目录分别使用一份源库和两个归档库。甲一在 B 后插入 X，乙把 B 换成 Y，甲二从甲一的冻结版把 X 换成 Z。演示在源库关闭后分别接纳甲一、甲二、乙及乙、甲一、甲二。两个归档重开后均签得 A、Y、Z、C，合计 32，且旧卷 A、B、C 仍合计 23。

## Python 接口

| 操作 | 入口与结果 |
| --- | --- |
| 打开源库 | `database.open_source(path)` 返回已启用外键的 SQLite 连接。调用者负责关闭。 |
| 导入 | `source.import_rows.import_root(conn, recording_id, rows)` 返回 `Recording`。每行可用 `Reading(name, value)` 或 `{"name": ..., "value": ...}`。 |
| 冻结 | `revision.freeze.freeze(conn, recording_id=...)` 或 `freeze(conn, work_id=...)` 返回带 `revision_id` 和有序出现项的 `FrozenRevision`。 |
| 登记 | `revision.amend.amend(conn, edit_id, parent_id, start, delete_count, inserts)` 返回带 `work_id` 的 `WorkingView`。`revision.views.load_current_working_view(conn, recording_key)` 读取最近新登记的工作视图。 |
| 发行 | `exchange.issue.issue(conn, edit_id, child_id)` 返回 `IssueReceipt`，其 `wire` 是固定包字节。`exchange.receipts.load_issue(conn, receipt_id)` 按号读回，未知号返回 `None`。 |
| 开立归档 | `archive.storage.ArchiveStore(path)` 支持上下文管理。`archive.root.open_archive(store, recording, root_revision_id)` 返回起始卷号。同根重开仍返回起始卷号。 |
| 接纳 | `archive.admit.admit(store, recording_id, wire)` 返回 `AdmissionReceipt`，其中 `edition_id` 可用于领取新卷。`store.load_current(recording_id)` 返回当前卷号。 |
| 领取 | `audit.retrieve.retrieve(store, edition_id)` 返回 `Reconciliation`，包括明细及 `total`。明细的 `position` 是卷内零基位置，`evidence.ordinal` 是来源内零基位置。 |

`recording_id` 和 `edit_id` 是非空文本，编辑号在录制内唯一。录制名称和行名称均保留原文，行名称允许重名。测值使用整数微应变，`None` 表示缺测。零和负值参与累加，布尔值、浮点数和字符串测值无效。缺测行保留，空卷与全缺测卷合计为零。所有修改入口自行开启事务，应使用没有外部活动事务的连接。

编辑只在所选冻结父版的可见明细上解释。起始位可从零到父版长度，删除数必须非负且不能越过卷尾。插入从该位置的左邻接续，卷首使用卷首锚。根行依次相接，层级为零。编辑层级为其父版最高层级加一。同锚先接较高层级，同层按编辑号升序，多行补录依原单顺序相接。删除隐藏其出现项，锚下的其余行仍按顺序出账。

固定包为 UTF-8 JSON，外层字段是 `version`、`package_id`、`manifest`。包号绑定规范化正文。正文包含冻结父子版、原勘误、被删除出现项、左邻、补录原据及发行回执号。断源归档凭本地根卷和已接纳件验证正文并签卷。固定卷号绑定根卷与已接纳包集合，历史卷按号持有独立快照。归档重新开立时保留当前指向、历史和回执。

`errors.py` 定义可区分的 `ValidationError`、`ConflictError`、`MissingParentError` 和 `NotFoundError`。SQLite 写入或提交失败保留原异常供调用者处理。完全相同的导入或勘误复用原记录。同件重投返回原接纳回执，无论当前卷是否已推进。同号异内容、缺父件或提交失败均不产生此次成果。补齐父件或解决提交错误后可重投原件。
