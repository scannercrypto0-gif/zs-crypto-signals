from pathlib import Path
p=Path('src/zs_smart_gate/ops24_budget.py')
s=p.read_text().replace('current = db.execute("SELECT cycle,policy FROM control").fetchone()', 'current = tuple(db.execute("SELECT cycle,policy FROM control").fetchone())')
s=s.replace('if (state["requests"] != 3 or state["active"] or state["halt"]', 'if (state["requests"] < 3 or state["active"] or state["halt"]')
s=s.replace('or state["used"] + 8*count > self.policy.max_observed_weight):', 'or state["used"] + max(0,weight-state["weight"]) > self.policy.max_observed_weight):')
p.write_text(s)
p=Path('src/zs_smart_gate/ops24_source.py')
s=p.read_text().replace('receipt["retry_after"] = headers.get("Retry-After")','receipt["retry_after"] = next((v for k,v in headers.items() if k.lower()=="retry-after"), None)')
s=s.replace('        atomic(budget.root/"inventory.private.json",canonical(snapshot))','''        inventory_path = budget.root/"inventory.private.json"
        if inventory_path.exists():
            frozen = json.loads(inventory_path.read_bytes())
            if frozen["source_manifest_sha256"] != snapshot["source_manifest_sha256"]:
                raise Hold("FROZEN_INVENTORY_DRIFT")
            snapshot = frozen
        else:
            atomic(inventory_path,canonical(snapshot))''')
s=s.replace('    packets = {}\n    eligible = []','''    result_path = budget.root/"result.json"
    pin_path = budget.root/"result.sha256"
    if result_path.exists():
        if not pin_path.exists() or digest(result_path.read_bytes()) != pin_path.read_text().strip():
            raise Hold("RESULT_READBACK_CORRUPTION")
        return json.loads(result_path.read_bytes())
    packets = {}
    eligible = []''')
s=s.replace('    result["expected_symbols"] = [row["symbol"] for row in eligible]','''    recorded = {row["symbol"] for row in result["rows"]}
    for item in eligible:
        if item["symbol"] not in recorded:
            result["rows"].append(dict(symbol=item["symbol"],state="UNKNOWN_OR_FINAL_GATE_HOLD",directions=[]))
    result["validated"] = sum(row["state"]=="VALIDATED" for row in result["rows"])
    result["missing"] = len(eligible)-result["validated"]
    result["expected_symbols"] = [row["symbol"] for row in eligible]''')
s=s.replace('    atomic(budget.root/"result.json",canonical(result))','''    atomic(result_path,canonical(result))
    atomic(pin_path,(digest(canonical(result))+"\\n").encode())''')
p.write_text(s)
p=Path('src/zs_smart_gate/ops24_runtime.py')
s=p.read_text().replace('from dataclasses import dataclass\n','')
p.write_text(s)

