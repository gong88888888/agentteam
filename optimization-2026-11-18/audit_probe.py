"""Read-only probes of the audited checkout; all mutations use TemporaryDirectory."""
from __future__ import annotations
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'implementation-audit'
sys.path.insert(0, str(ROOT))
from orchestrator.product_review import ProductReviewRunner, ROLE_MAP, extract_source_sections
from orchestrator.role_gates import evaluate_role
from orchestrator.process import definition_of_done
from orchestrator.models.router import ModelRouter

def main():
    rows = []
    with tempfile.TemporaryDirectory(prefix='agentteam-audit-') as td:
        root = Path(td)
        doc = root / 'input.md'
        doc.write_text('# Goal\n## Rules\nKeep input on failure.\n', encoding='utf-8')
        review = ProductReviewRunner(doc=doc, out_dir=root/'review', offline=True)
        review.prepare()
        rel = 'docs/product-review/01-document-map.md'
        target = review.out_dir / rel
        target.write_text('来源 主张 歧义 覆盖 SRC-999', encoding='utf-8')
        result = review.gate(ROLE_MAP['doc-analyst'], {'status':'blocked','summary':''}, [{'path':rel}], 1.0)
        rows.append({'id':'P01-invalid-source-and-blocked-review','actual':result['status'],
                     'expected':'fail','note':'Fabricated source reference and blocked output.'})
        p = root / 'web'
        for rel in ['src/backend/app.py','docs/product/product-baseline.md','docs/architecture/architecture.md']:
            t=p/rel;t.parent.mkdir(parents=True,exist_ok=True);t.write_text('not valid code or a substantive specification',encoding='utf-8')
        state={'product':{'status':'done','gate':{'status':'pass'}}}
        result=definition_of_done(p,'web',state)
        rows.append({'id':'P02-incomplete-web-project-dod','actual':result['status'],
                     'expected':'fail','note':'One role, invalid Python entry, no runtime acceptance.'})
        t=p/'docs/product/product-baseline.md';t.write_text('',encoding='utf-8')
        result=evaluate_role('product',{'role':'product','status':'done',
            'summary':'验收和非目标已经列出，当前可以继续后续流程。'},project_dir=p,files=[])
        rows.append({'id':'P03-empty-product-document','actual':result.status,
                     'expected':'fail','note':'Empty document plus keyword-bearing summary.'})
        result=evaluate_role('backend',{'role':'backend','status':'done','summary':'Implementation output is ready for verification.'},project_dir=p,
            files=[{'path':'src/backend/app.py'}],tool_result={'subject_hash':'unverified-subject',
              'evidence':[{'kind':'compile','result':'pass','evidence_id':'FAKE1'},
                          {'kind':'unit','result':'pass','evidence_id':'FAKE2'}]})
        rows.append({'id':'P04-gate-consumer-unverified-dictionaries','actual':result.status,
                     'expected':'reject at trust boundary','note':'Direct function probe; not proof of an externally reachable exploit.'})
        review=ProductReviewRunner(doc=doc,out_dir=root/'resume',offline=True)
        first=review.run()
        doc.write_text('# Changed\n## Different requirements\nNew semantics.\n',encoding='utf-8')
        second=ProductReviewRunner(doc=doc,out_dir=root/'resume',offline=True,roles=['product-lead'])
        def fail(*args,**kwargs):raise RuntimeError('injected backend failure')
        second.router.execution=fail
        result=second.run()
        saved=json.loads((second.out_dir/'state/roles.json').read_text(encoding='utf-8'))
        rows.append({'id':'P05-stale-review-gates','initial':first['status'],'actual':result['status'],
                     'latest_role_status':saved['product-lead']['status'],'expected':'fail',
                     'note':'Changed source, latest role failed, old complete gate set survives.'})
    router=ModelRouter({},offline=False)
    rows.append({'id':'P06-unknown-backend','actual':router._backend('deapseek').name,
                 'expected':'configuration error','note':'No API calls performed.'})
    text='# Original\n## Keep\nRule\n'
    a=extract_source_sections(text);b=extract_source_sections('# Added\n'+text)
    rows.append({'id':'P07-heading-id-shift','before':a[1]['id'],'after':b[2]['id'],
                 'note':'Same heading changes ID after prepending a heading.'})
    sample=ROOT/'projects/test1/game'
    imports=[]
    for rel in ['index.html','js/main.js','js/core.js']:
        content=(sample/rel).read_text(encoding='utf-8')
        imports += re.findall(r'(?:from\s+[\"\x27]|import\s*\(\s*[\"\x27]|src=[\"\x27])([^\"\x27]+)',content)
    rows.append({'id':'P08-game-generated-module-reachability','entry_imports':imports,
                 'generated_modules':len(list((sample/'js/gameplay').glob('*.js'))),
                 'note':'Entry/core/main do not reference gameplay or UI increments; static entry graph only.'})
    out=Path(__file__).with_name('audit-probes.json')
    out.write_text(json.dumps({'commit':'afbfaab7e0e290373722b811bbfe536606511411','probes':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(rows,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
