"""技术改造模块规则的端到端验证：直接用 TestClient 打真实接口。

运行：cd backend && python tests/test_renovation_rules.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# 岗位操作人
ZHANG = {"X-Operator-Id": "u_zhang"}   # 张立 立项岗 信号技术科
CHEN = {"X-Operator-Id": "u_chen"}     # 陈审 审核岗 技术改造科
SUN = {"X-Operator-Id": "u_sun"}       # 孙算 预算岗 计划财务科
LI = {"X-Operator-Id": "u_li"}         # 李工 实施岗 信号车间
ZHOU = {"X-Operator-Id": "u_zhou"}     # 周验 验收岗 安全质量科
WANG = {"X-Operator-Id": "u_wang"}     # 王看 查看岗 运营管理科
WU = {"X-Operator-Id": "u_wu"}         # 吴协 立项岗 通信技术科

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def call(method: str, path: str, headers: dict[str, str], **kwargs):
    resp = getattr(client, method)(path, headers=headers, **kwargs)
    return resp


def body(resp) -> dict:
    return resp.json() if resp.content else {}


# 1. 立项：立项岗可以立项；查看岗不能立项
r = call("post", "/api/renovation/projects", WANG, json={"项目名称": "越权立项尝试"})
check("查看岗不能立项", r.status_code == 403 and "renovation:project:create" in r.text, r.text[:200])

r = call("post", "/api/renovation/projects", ZHANG, json={"项目名称": "道口信号电源改造", "预算金额": 12.5})
check("立项岗立项成功", r.status_code == 200 and r.json()["ok"], r.text[:200])
new_id = r.json()["entry"]["id"]
check(
    "立项后台账/立项单/验收页负责人为同一人(立项人)",
    r.json()["entry"]["责任人"] == "张立" == r.json()["entry"]["立项人"],
)

# 2. 立项人只能改自己提交的项目：别人改张立的项目
r = call("patch", f"/api/renovation/projects/{new_id}", SUN, json={"项目名称": "被人篡改"})
check("非立项人改立项单被403拦截并说明权限", r.status_code == 403 and "renovation:owner:self" in r.text, r.text[:200])

# 预算：查看岗改预算 → 403 缺预算权限；立项人(有预算权限)在编制中可改
r = call("patch", f"/api/renovation/projects/{new_id}", WANG, json={"预算金额": 999})
check("查看岗改预算被拦且报缺预算权限", r.status_code == 403 and "renovation:budget:edit" in str(r.json()), r.text[:200])

r = call("patch", f"/api/renovation/projects/{new_id}", ZHANG, json={"预算金额": 15.0})
check("立项人编制中可改预算", r.status_code == 200 and r.json()["entry"]["预算金额"] == 15.0, r.text[:200])

# 3. 审核退回必须写理由
r = call("post", f"/api/renovation/projects/{new_id}/actions", ZHANG, json={"action": "提交审核"})
check("立项人提交审核", r.status_code == 200, r.text[:200])

r = call("post", f"/api/renovation/projects/{new_id}/actions", CHEN, json={"action": "审核退回", "reason": ""})
check("退回不写理由被拒(400)", r.status_code == 400 and "理由" in r.text, r.text[:200])

r = call("post", f"/api/renovation/projects/{new_id}/actions", LI, json={"action": "审核退回", "reason": "测试"})
check("实施岗无审核退回权限被403", r.status_code == 403 and "renovation:review:reject" in r.text, r.text[:200])

r = call("post", f"/api/renovation/projects/{new_id}/actions", CHEN, json={"action": "审核退回", "reason": "预算依据不足"})
check("审核岗写明理由退回成功", r.status_code == 200 and r.json()["entry"]["退回理由"] == "预算依据不足", r.text[:200])

# 4. 退回后别人不能重提，立项人修改后重提
r = call("post", f"/api/renovation/projects/{new_id}/actions", WANG, json={"action": "重新提交"})
check("查看岗不能重新提交", r.status_code == 403, r.text[:150])
r = call("patch", f"/api/renovation/projects/{new_id}", ZHANG, json={"预算金额": 16.8})
check("退回后立项人可修改预算", r.status_code == 200, r.text[:150])
r = call("post", f"/api/renovation/projects/{new_id}/actions", ZHANG, json={"action": "重新提交"})
check("立项人重新提交", r.status_code == 200, r.text[:150])

# 5. 批复后预算不可改（即使是立项人本人）
r = call("post", f"/api/renovation/projects/{new_id}/actions", CHEN, json={"action": "审核通过"})
check("审核通过批复", r.status_code == 200, r.text[:150])
r = call("patch", f"/api/renovation/projects/{new_id}", ZHANG, json={"预算金额": 1})
check("批复后立项人改预算被业务规则拒绝", r.status_code == 400, r.text[:150])

# 6. 实施 → 报竣 → 验收结论只有验收岗能填
r = call("post", f"/api/renovation/projects/{new_id}/actions", CHEN, json={"action": "安排实施"})
check("审核岗不能安排实施(缺实施权限)", r.status_code == 403 and "renovation:implement" in r.text, r.text[:200])
r = call("post", f"/api/renovation/projects/{new_id}/actions", LI, json={"action": "安排实施"})
check("实施岗安排实施", r.status_code == 200, r.text[:150])
r = call("post", f"/api/renovation/projects/{new_id}/actions", LI, json={"action": "实施报竣"})
check("实施报竣", r.status_code == 200, r.text[:150])
r = call("post", f"/api/renovation/projects/{new_id}/actions", LI, json={"action": "投运验收", "conclusion": "合格"})
check("实施岗不能填验收结论", r.status_code == 403 and "renovation:accept" in r.text, r.text[:200])
r = call("post", f"/api/renovation/projects/{new_id}/actions", ZHOU, json={"action": "投运验收", "conclusion": ""})
check("验收结论为空被拒", r.status_code == 400, r.text[:150])
r = call("post", f"/api/renovation/projects/{new_id}/actions", ZHOU, json={"action": "投运验收", "conclusion": "验收合格，同意投运"})
check("验收岗投运验收", r.status_code == 200, r.text[:150])

# 7. 已投运只读：所有写动作（预算/结论/责任人）都拦
r = call("patch", f"/api/renovation/projects/{new_id}", ZHANG, json={"预算金额": 1})
check("投运后立项人改预算被只读拦截", r.status_code == 400 and "仅可查看" in r.text, r.text[:200])
r = call("post", f"/api/renovation/projects/{new_id}/transfer", ZHOU, json={"to_user_id": "u_li"})
check("投运后移交责任人被只读拦截", r.status_code == 400, r.text[:150])
r = call("post", f"/api/renovation/projects/{new_id}/actions", ZHOU, json={"action": "投运验收", "conclusion": "再改"})
check("投运后验收结论不可改", r.status_code == 400, r.text[:150])

# 8. 同部门责任人唯一：在未投运项目上移交
# 项目1 张立(信号技术科) → 李工(信号车间)，不同部门允许
r = call("post", "/api/renovation/projects/1/transfer", ZHANG, json={"to_user_id": "u_li", "reason": "下放车间"})
check("跨部门移交成功", r.status_code == 200 and r.json()["entry"]["责任人"] == "李工", r.text[:200])
r = call("get", "/api/renovation/projects/1/transfers", ZHANG)
check("移交记录刷新后仍在", r.status_code == 200 and len(r.json()["items"]) == 1 and r.json()["items"][0]["新责任人"] == "李工", r.text[:200])

# 再指定同部门(信号车间)共同责任人 → 拒绝（一部门两个责任人）
r = call("post", "/api/renovation/projects/1/co-owners", ZHANG, json={"user_id": "u_li"})
check("共同责任人与责任部门相同被拒", r.status_code == 400 and "其他部门" in r.text, r.text[:200])

# 9. 跨部门共同责任人共享查看
r = call("post", "/api/renovation/projects/1/co-owners", ZHANG, json={"user_id": "u_wu"})
check("指定跨部门共同责任人", r.status_code == 200, r.text[:200])
r = call("get", "/api/renovation/projects/1", WU)
check("共同责任人可查看项目", r.status_code == 200 and r.json()["entry"]["责任人"] == "李工", r.text[:200])
r = call("patch", "/api/renovation/projects/1", WU, json={"项目名称": "外人改单"})
check("共同责任人只读不能改", r.status_code == 403, r.text[:150])

# 10. 重复共同责任人同部门 → 拒绝
r = call("post", "/api/renovation/projects/5/co-owners", ZHANG, json={"user_id": "u_wu"})
check("重复指定同一共同责任人被拒", r.status_code == 400, r.text[:150])

# 11. 查看岗对台账：只能看到本部门/共享项目，看不到别的
r = call("get", "/api/renovation/projects", WANG)
ids_wang = {item["id"] for item in r.json()["items"]}
check("查看岗看不到非本部门项目", new_id not in ids_wang and 1 not in ids_wang, f"看到{ids_wang}")
r = call("get", "/api/renovation/projects", ZHANG)
ids_zhang = {item["id"] for item in r.json()["items"]}
check("立项人能看到自己的项目", new_id in ids_zhang and 1 in ids_zhang, f"看到{ids_zhang}")

# 12. 直接访问不可见项目 → 404
r = call("get", f"/api/renovation/projects/{new_id}", WANG)
check("查看岗直查别人项目返回404", r.status_code == 404, r.text[:150])

# 13. 三处页面负责人一致：台账行、立项详情里的责任人字段同源
r = call("get", "/api/renovation/projects", LI)
row1_list = next(i for i in r.json()["items"] if i["id"] == 1)
r = call("get", "/api/renovation/projects/1", LI)
row1_detail = r.json()["entry"]
check("台账与详情负责人一致", row1_list["责任人"] == row1_detail["责任人"] == "李工")

# 输出结果
failed = [item for item in results if not item[1]]
for name, ok, detail in results:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}")
    if not ok:
        print(f"       {detail}")
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
