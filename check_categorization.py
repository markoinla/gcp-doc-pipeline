#!/usr/bin/env python3
"""
Check the updated categorization results to verify PT patterns are now categorized as painting
"""

import requests
import json

def main():
    print("🎨 Checking Updated Categorization Results")
    print("=" * 50)
    
    # URL of the newly processed document
    doc_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/documents/68c220f0-82a5-4ed5-8039-888c151095da.json"
    
    print(f"Fetching document from: {doc_url}")
    response = requests.get(doc_url)
    response.raise_for_status()
    
    data = response.json()
    
    print(f"✅ Document loaded successfully")
    print(f"📊 Total unique items: {len(data['items'])}")
    
    # Check categorization
    print(f"\n🏷️  CATEGORY BREAKDOWN:")
    print("=" * 50)
    
    categories = {}
    pt_patterns = []
    
    for item_key, item_data in data['items'].items():
        category = item_data['category']
        if category not in categories:
            categories[category] = 0
        categories[category] += 1
        
        # Collect PT patterns specifically
        if item_data['type'] == 'pattern' and item_key.startswith('PT'):
            pt_patterns.append({
                'pattern': item_key,
                'category': category,
                'count': item_data['total_count'],
                'pages': [loc['page'] for loc in item_data['locations']]
            })
    
    # Show category breakdown
    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count} items")
    
    # Show PT patterns specifically
    print(f"\n🎨 PT PATTERNS (Should be 'painting' category):")
    print("=" * 50)
    
    if pt_patterns:
        for pt in sorted(pt_patterns, key=lambda x: x['pattern']):
            pages_str = ', '.join(map(str, pt['pages']))
            print(f"  {pt['pattern']}: {pt['category']} ({pt['count']} instances on pages {pages_str})")
    else:
        print("  No PT patterns found")
    
    # Check if categorization worked
    painting_patterns = [pt for pt in pt_patterns if pt['category'] == 'painting']
    old_plumbing_patterns = [pt for pt in pt_patterns if pt['category'] == 'plumbing_technical']
    
    print(f"\n✅ CATEGORIZATION RESULTS:")
    print("=" * 50)
    print(f"  PT patterns correctly categorized as 'painting': {len(painting_patterns)}")
    print(f"  PT patterns still categorized as 'plumbing_technical': {len(old_plumbing_patterns)}")
    
    if len(painting_patterns) > 0 and len(old_plumbing_patterns) == 0:
        print("  🎉 SUCCESS: All PT patterns are now correctly categorized as painting!")
    elif len(old_plumbing_patterns) > 0:
        print("  ⚠️  WARNING: Some PT patterns still have old categorization")
    else:
        print("  ℹ️  INFO: No PT patterns found in this document")

if __name__ == "__main__":
    main() 