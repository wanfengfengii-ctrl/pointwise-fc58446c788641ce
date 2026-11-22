# 河桥振动试验归档勘误事故

## 断源错卷

原卷为 A=7、B=7、C=9，单位为微应变。甲一从原卷在 B 后补入 X=8，乙从原卷将 B 换成 Y=6，甲二从甲一的冻结版将 X 换成 Z=10。发行后关闭源库，夜班分别用甲一、甲二、乙及乙、甲一、甲二两种顺序接纳。

乙先到时，当前卷领出 A、Y、X、Z，合计 31。两种顺序都应领出 A、Y、Z、C，合计 32，且当前卷号和逐行出处一致。C 仍来自原卷第三行。重开后用起始卷号仍应领出 A、B、C 及合计 23。

另有一个只删不补的对照。乙仅删除 B，按甲一、乙、甲二接纳时，甲二到达前当前卷为 A、X、C。甲二接纳后应领出 A、Z、C，合计 26。

```sh
python3 -B -m unittest tests.test_archive.MergeTests.test_deleted_anchor
python3 -B -m unittest tests.test_archive.MergeTests.test_author_position_shift
python3 -B demo.py samples/shift.json
```

## 延迟发行错据

将旧勘误 B 换 R=4 登记并冻结后，先在工作视图卷首补 N=1，再首次发行旧勘误。旧件应仍绑定原卷中的 B 和左邻 A，供夜班离线复核。现有来件中的删除凭据指向 A。

```sh
python3 -B -m unittest tests.test_issue.IssueTests.test_frozen_base
python3 -B check_project.py
```

接口、包格式、顺序和回执规则见 README.md。完整核验及演示沿用项目运行清单。

## 根因与修复记录

### 根因

1. 勘误签发（`exchange/issue.py`）：发行旧勘误时，若录制的工作版已推进到新登记的工作视图，删除凭据与左邻改从当前工作版按位置截取，而非作者选定的冻结父版。B 换 R=4 的删换指向因此落到同值行 A（出处序号 0）上，左邻错指为卷首补录的 N。
2. 离线合流（`archive/merge.py`）：接纳时把包内行位、删除数直接按当前卷位置解释，锚行在本卷不可见时把补录追加到卷尾。乙先到时，甲二的"删第 3 行"误删 C，甲一的 X 挂到卷尾，当前卷错为 A、Y、X、Z（31）。

### 修复

1. 签发一律以作者选定的冻结父版为准截取删除凭据与左邻，不再读取当前工作版；同值行按各自出处序号区分。
2. 收件方凭离线原卷和已收父件重建作者冻结父版，核验包内删除凭据与左邻（不符即拒，不产生成果）；当前卷改为由原卷加已接纳件集合整体重放：删除按出处隐藏（被删行只留下插入位置），插入接在父版左邻或卷首，同锚先接较高层级、同层按编辑号升序、多行补录依原单次序。卷号仍绑定根卷与已接纳包集合，故所有合法到件次序收敛到同一卷号、行明细和合计。

### 回归用例

`tests/test_incident.py`：延迟发行件离线核验与同值行可辨、六种到件次序（含缺父重投）收敛、卷首锚层级次序、只删不补对照重开。

### 实际运行结果

- `python3 -B check_project.py`：22 个用例全部通过（TEST SUMMARY total=22 result=PASS）。
- `python3 -B demo.py samples/shift.json`：两种接纳次序均签得 A、Y、Z、C 合计 32，起始卷号领回 A、B、C 合计 23，actual 与 expected 完全一致。
- `python3 -B -m unittest tests.test_archive.MergeTests.test_deleted_anchor tests.test_archive.MergeTests.test_author_position_shift tests.test_issue.IssueTests.test_frozen_base`：3 个用例通过。
