import urllib.request, json
# 1. Fetch directives
req = urllib.request.Request('http://localhost:8000/api/v1/directives?store_id=DS-CENTRAL')
with urllib.request.urlopen(req) as response:
    dirs = json.loads(response.read())['directives']
    
print(f'Got {len(dirs)} directives.')
if not dirs: exit(1)

# 2. Confirm the first 2 directives
for d in dirs[:2]:
    data = json.dumps({'sku': d['sku'], 'quantity': d['recommended_qty'], 'directive_id': d['id']}).encode('utf-8')
    req = urllib.request.Request('http://localhost:8000/api/v1/orders/confirm?store_id=DS-CENTRAL', data=data, headers={'Content-Type': 'application/json'})
    try:
      urllib.request.urlopen(req)
      print(f'Confirmed sku ' + d['sku'])
    except Exception as e: print(e)

# 3. Generate PO
try:
    req = urllib.request.Request('http://localhost:8000/api/v1/orders/generate-pos?store_id=DS-CENTRAL', data=b'', headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req) as response:
        pos = json.loads(response.read())
        print(f'Generated {len(pos)} POs!')
        for po in pos:
            print(f" - PO: {po['id']} Supplier: {po['supplier_name']} Items: {po['total_quantity']}")
except Exception as e:
    print(e.read())
