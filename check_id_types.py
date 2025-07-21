import json

# Load reference and generated files
with open('gaea-references/Official Gaea Projects/Alien Surface.terrain', 'r') as f:
    reference = json.load(f)

with open('test_format_fixed.json', 'r') as f:
    generated = json.load(f)

print("=== ID TYPE ANALYSIS ===\n")

# Check reference file ID types
def check_id_types(obj, path="", depth=0):
    if depth > 10:  # Prevent infinite recursion
        return
        
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "$id":
                print(f"{path}.{key}: type={type(value).__name__}, value={repr(value)}")
            elif key == "$ref":
                print(f"{path}.{key}: type={type(value).__name__}, value={repr(value)}")
            elif isinstance(value, (dict, list)):
                check_id_types(value, f"{path}.{key}", depth + 1)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                check_id_types(item, f"{path}[{i}]", depth + 1)

print("REFERENCE FILE:")
check_id_types(reference)

print("\n\nGENERATED FILE:")
check_id_types(generated)

# Check specific problem areas
print("\n\n=== SPECIFIC CHECKS ===")

# Check if Port Records have correct ID types
ref_nodes = reference['Assets']['$values'][0]['Terrain']['Nodes']
for node_id, node in ref_nodes.items():
    if node_id != '$id' and 'Ports' in node:
        ports = node['Ports']['$values']
        for port in ports:
            if 'Record' in port:
                rec = port['Record']
                print(f"\nREFERENCE Record IDs:")
                print(f"  From: type={type(rec['From']).__name__}, value={rec['From']}")
                print(f"  To: type={type(rec['To']).__name__}, value={rec['To']}")
                break
        break

gen_nodes = generated['Assets']['$values'][0]['Terrain']['Nodes']
for node_id, node in gen_nodes.items():
    if node_id != '$id' and 'Ports' in node:
        ports = node['Ports']['$values']
        for port in ports:
            if 'Record' in port:
                rec = port['Record']
                print(f"\nGENERATED Record IDs:")
                print(f"  From: type={type(rec['From']).__name__}, value={rec['From']}")
                print(f"  To: type={type(rec['To']).__name__}, value={rec['To']}")
                break
        break