"""Explicit operator declarations for the existing trusted sample; never auto-discovered intent.

These requirements were already manually defined in seed.py and fixtures/scenarios.py.
This manifest makes that provenance, ownership and approval boundary explicit.
"""
from pathlib import Path
import hashlib

DECLARATIONS = [
    {'id':'INV-PAY-01','description':'A payment event must be captured only once.','service':'S-PAYMENTS','service_name':'Payments','functions':['handle_gateway_webhook'],'tests':['TC-PAY-IDEMPOTENCY'],'scenario_function':'payment_idempotency'},
    {'id':'INV-STOCK-01','description':'Insufficient inventory must reject reservation; stock must never be negative.','service':'S-INVENTORY','service_name':'Inventory','functions':['reserve_inventory'],'tests':['TC-STOCK-NONNEGATIVE'],'scenario_function':'stock_never_negative'},
    {'id':'INV-ORDER-01','description':'Order totals must be bounded at zero after discounts.','service':'S-ORDERS','service_name':'Order Pricing','functions':['calculate_total'],'tests':['TC-ORDER-TOTAL'],'scenario_function':'total_never_negative'},
    {'id':'INV-REFUND-01','description':'Duplicate refund deliveries must not credit a wallet more than once.','service':'S-REFUNDS','service_name':'Refunds','functions':['process_refund'],'tests':[],'scenario_function':None},
]


def trusted_declarations(repository: str) -> list[dict]:
    if repository!='trusted-commerce':return []
    source=Path(__file__).read_text(encoding='utf-8');lines=source.splitlines();result=[]
    for item in DECLARATIONS:
        line=next(i for i,text in enumerate(lines,1) if "'id':'"+item['id']+"'" in text)
        result.append({**item,'declared_by':'bundled demo maintainer manifest','source':{'path':'package:faultline/context_declarations.py','line':line,'sha256':hashlib.sha256(source.encode()).hexdigest(),'origin':'operator_declared_configuration'}})
    return result
