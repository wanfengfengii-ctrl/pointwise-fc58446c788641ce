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
