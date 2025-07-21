import json
import os
from collections import defaultdict

# Analyze multiple reference files
reference_dir = "gaea-references/Official Gaea Projects/"
reference_files = [
    "Alien Surface.terrain",
    "Canyon River with Sea.terrain",
    "Collapsed Gullies.terrain",
    "Complex Scene - Debris.terrain",
    "Modular Portal - Terrain.terrain"
]

# Load our generated file
with open('test_format_fixed.json', 'r') as f:
    generated = json.load(f)

print("=== DEEP FORMAT ANALYSIS ===\n")

# Analyze key ordering patterns
def get_key_order(obj):
    return list(obj.keys())

# Collect patterns from reference files
patterns = defaultdict(list)

for ref_file in reference_files:
    if os.path.exists(os.path.join(reference_dir, ref_file)):
        with open(os.path.join(reference_dir, ref_file), 'r') as f:
            ref = json.load(f)
            
        print(f"\nAnalyzing: {ref_file}")
        
        # Top-level structure
        top_keys = get_key_order(ref)
        patterns['top_level'].append(top_keys)
        print(f"Top-level keys: {top_keys}")
        
        # Asset structure
        if 'Assets' in ref and '$values' in ref['Assets'] and ref['Assets']['$values']:
            asset = ref['Assets']['$values'][0]
            asset_keys = get_key_order(asset)
            patterns['asset'].append(asset_keys)
            print(f"Asset keys: {asset_keys}")
            
            # Node structure - find first node
            if 'Terrain' in asset and 'Nodes' in asset['Terrain']:
                nodes = asset['Terrain']['Nodes']
                for node_id, node in nodes.items():
                    if node_id != '$id':
                        node_keys = get_key_order(node)
                        patterns['node'].append(node_keys)
                        print(f"Node keys: {node_keys[:15]}...")  # First 15 keys
                        
                        # Port structure with Record
                        if 'Ports' in node and '$values' in node['Ports']:
                            for port in node['Ports']['$values']:
                                if 'Record' in port:
                                    port_keys = get_key_order(port)
                                    patterns['port_with_record'].append(port_keys)
                                    print(f"Port w/Record keys: {port_keys}")
                                    
                                    # Record structure
                                    record_keys = get_key_order(port['Record'])
                                    patterns['record'].append(record_keys)
                                    print(f"Record keys: {record_keys}")
                                    break
                        break

print("\n=== COMPARING WITH GENERATED FILE ===")

# Compare our generated structure
gen_top = get_key_order(generated)
print(f"\nGenerated top-level: {gen_top}")

gen_asset = generated['Assets']['$values'][0]
gen_asset_keys = get_key_order(gen_asset)
print(f"Generated asset keys: {gen_asset_keys}")

# Find issues
print("\n=== POTENTIAL ISSUES ===")

# Check if asset key order matches any reference
if gen_asset_keys not in patterns['asset']:
    print("\n❌ Asset key order doesn't match any reference!")
    print("Expected one of:")
    for i, keys in enumerate(set(tuple(k) for k in patterns['asset'])):
        print(f"  {i+1}. {list(keys)}")
        
# Check node property order
gen_nodes = gen_asset['Terrain']['Nodes']
for node_id, node in gen_nodes.items():
    if node_id != '$id':
        gen_node_keys = get_key_order(node)
        # Check if it matches common patterns
        print(f"\n❌ Generated node keys: {gen_node_keys[:15]}...")
        print("Common reference patterns:")
        for i, keys in enumerate(set(tuple(k[:15]) for k in patterns['node'])):
            print(f"  {i+1}. {list(keys)}")
        break
        
# Export specific fields that might be wrong
print("\n=== SPECIFIC FIELD ANALYSIS ===")

# Check Export node SaveDefinition
for node_id, node in gen_nodes.items():
    if node_id != '$id' and 'Export' in node.get('$type', ''):
        print(f"\nExport node structure:")
        print(f"  Keys: {get_key_order(node)}")
        if 'SaveDefinition' in node:
            print(f"  SaveDefinition keys: {get_key_order(node['SaveDefinition'])}")
            print(f"  SaveDefinition: {node['SaveDefinition']}")
            
# Check for fields that should/shouldn't exist
print("\n=== FIELD EXISTENCE CHECK ===")

# Check Modifiers location
for ref_file in reference_files[:2]:  # Check first 2 files
    if os.path.exists(os.path.join(reference_dir, ref_file)):
        with open(os.path.join(reference_dir, ref_file), 'r') as f:
            ref = json.load(f)
        nodes = ref['Assets']['$values'][0]['Terrain']['Nodes']
        for node_id, node in nodes.items():
            if node_id != '$id':
                print(f"\n{ref_file} node has Modifiers: {'Modifiers' in node}")
                print(f"Node has SnapIns: {'SnapIns' in node}")
                break