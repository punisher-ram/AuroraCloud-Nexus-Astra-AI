from __future__ import annotations
import json, tempfile
from pathlib import Path

from app.database import Database
from app.services import BusinessService
from app.documents import DocumentEngine
import app.ai.serneia as ai

root=Path(tempfile.mkdtemp(prefix='aurora_smoke_'))
db=Database(root); db.migrate(); s=BusinessService(db); e=DocumentEngine(db,root)

cid=s.create_customer({'company_name':'Smoke Test Client','email':'smoke@example.com','tax_id':'GST-SMOKE'})
iid=s.create_item({'name':'Smoke Item','unit':'Unit','selling_price':100,'purchase_price':60,'tax_rate':18,'stock':5})
doc_id=s.create_document('INVOICE',cid,[{'item_id':iid,'description':'Smoke Item','quantity':2,'unit':'Unit','rate':100,'discount':0,'tax_rate':18}],notes='Smoke')
pid=s.record_payment(doc_id,100,'UPI','SMOKE-001','')
pdf=e.pdf(doc_id); receipt=e.receipt_pdf(pid)
health=db.health_check()
assert health['integrity']=='ok'
assert pdf.exists() and receipt.exists()

class FakeResponse:
    status_code=200
    text=''
    def json(self): return {'choices':[{'message':{'content':'Hello!'}}]}
orig=ai.requests.post
try:
    ai.requests.post=lambda *a,**k: FakeResponse()
    assert ai.call_groq_chat('openai/gpt-oss-120b',[{'role':'user','content':'hi'}])=='Hello!'
finally:
    ai.requests.post=orig
print(json.dumps({'database':'PASS','invoice_pdf':'PASS','receipt_pdf':'PASS','groq_chat_mock':'PASS','root':str(root)}))
