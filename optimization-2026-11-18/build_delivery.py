"""Build the reviewed Chinese plan and check its deliverable invariants."""
from pathlib import Path
import hashlib
import json
import re

BASE = Path(__file__).resolve().parent
chapters = sorted(BASE.glob('[0-9][0-9]-*.md'))
assert len(chapters) == 18, len(chapters)
body = '\n\n'.join(p.read_text(encoding='utf-8').strip() for p in chapters) + '\n'
han = len(re.findall(r'[\u4e00-\u9fff]', body))
nonspace = len(re.sub(r'\s', '', body))
assert han >= 50000, (han, nonspace)
task_text = '\n'.join(p.read_text(encoding='utf-8') for p in chapters if p.name.startswith(('11-', '12-')))
tasks = re.findall(r'^## (T\d{2})：', task_text, re.M)
assert tasks == [f'T{i:02d}' for i in range(32)], tasks
for task in tasks:
    assert task_text.count('## ' + task + '：') == 1
probes = json.loads((BASE/'audit-probes.json').read_text(encoding='utf-8'))
assert len(probes['probes']) == 8
commit = probes['commit']
out = BASE.parent / 'AgentTeam实际审查与五万字优化实施方案-2026-11-18.md'
intro = f'''# AgentTeam 实际审查与五万字优化实施方案

日期：2026-11-18（Asia/Shanghai）  
实际仓库：[gong88888888/agentteam](https://github.com/gong88888888/agentteam)  
固定审查提交：`{commit}`

本交付结合第一轮设计分析与实际代码审查。正文共 {len(chapters)} 篇，**{han:,} 个汉字**，非空白字符 **{nonspace:,}**；计数只统计以下章节一次，不包含第一轮报告、原仓库源码、目录、脚本或其他重复交付。

现状验证：Python 3.12 下既有单测 30 项全部通过；另执行 8 组确定性审查探针。没有调用真实付费模型，没有修改审查仓库的业务源码。本文的目标接口、任务卡与提示词是实施方案，不表示已经实现或通过新系统的端到端验收。

推荐使用方式：先读第一、二篇，再按第十一、十二篇的 T00—T31 执行；每次只给编码模型当前任务卡、相关设计篇章及实际代码。第十三篇提供可直接使用的提示词；第十五、十七篇提供失败演练与验收目标。

分章版、复现脚本和统计见：[交付目录]({(BASE/'README.md').as_posix()})。

---

'''
out.write_text(intro+body, encoding='utf-8')
toc = '\n'.join(f'- [{p.stem}]({p.as_posix()})' for p in chapters)
index = f'''# AgentTeam 优化交付目录

- [五万字合订版]({out.as_posix()})
- [第一轮设计报告]({(BASE.parent/'AgentTeam设计审查与持续迭代优化报告-2026-11-18.md').as_posix()})
- [审查探针脚本]({(BASE/'audit_probe.py').as_posix()})
- [探针原始结果]({(BASE/'audit-probes.json').as_posix()})
- [统计与验证清单]({(BASE/'verification.json').as_posix()})

正文包含 {han:,} 个汉字、{nonspace:,} 个非空白字符。共有 18 篇、32 张实施任务卡、24 项验收用例，并附角色提示词、接口协议和迁移回退步骤。

## 分章阅读

{toc}

## 本地复现

工作目录为独立审查仓库 `implementation-audit`，使用支持现代类型注解的 Python。本次实际使用 Python 3.12。

```powershell
py -3.12 -m unittest discover -s tests -v
py -3.12 ..\\optimization-2026-11-18\\audit_probe.py
```

探针所有业务文件写入使用临时目录；它验证当前缺口，不是修复测试通过声明。真实模型成功率、完整应用验收和另一台电脑的环境尚未验证。
'''
(BASE/'README.md').write_text(index, encoding='utf-8')
checks = {
 'date':'2026-11-18','timezone':'Asia/Shanghai','commit':commit,
 'body_chapters':len(chapters),'body_han_characters':han,
 'body_non_whitespace_characters':nonspace,'body_total_characters':len(body),
 'implementation_task_cards':tasks,'acceptance_catalog_cases':len(re.findall(r'^### 验收', (BASE/'17-验收用例目录与人工检查表.md').read_text(encoding='utf-8'), re.M)),
 'existing_unit_test_run':{'command':'py -3.12 -m unittest discover -s tests -v','tests':30,'result':'OK','duration_seconds':16.081,'scope':'existing repository tests, not implementation of this plan'},
 'audit_probe_count':8,'paid_model_calls':0,'source_implementation_modified':False,
 'combined_file':str(out),'combined_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
 'chapters':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in chapters]
}
(BASE/'verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:v for k,v in checks.items() if k in ['body_chapters','body_han_characters','body_non_whitespace_characters','acceptance_catalog_cases','combined_file']}, ensure_ascii=True))
