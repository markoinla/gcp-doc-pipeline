import re

patterns = [
    r'\b[A-Za-z]-?\d+\b',       # Pattern 1
    r'\b[A-Za-z]{2}-\d+\b',     # Pattern 2
    r'\b[A-Za-z]{2}\d{1,3}\b',  # Pattern 3
]

# Test various scenarios that Vision API might return
test_cases = [
    'pt-2',
    'PT-2', 
    ' pt-2 ',
    'pt-2.',
    'pt-2,',
    'Text pt-2 more',
    'pt-2\n',
    'pt-2\t',
    'word pt-2 word',
    'ab-1',
    'AB-123',
    'xy-99',
    '(pt-2)',
    'pt-2)',
    '"pt-2"',
]

compiled = [re.compile(p, re.IGNORECASE) for p in patterns]

print("Testing regex patterns for two letters + hyphen + number:")
print("=" * 60)

for test in test_cases:
    print(f'Testing: {repr(test)}')
    found_match = False
    for i, regex in enumerate(compiled):
        match = regex.search(test)
        if match:
            print(f'  ✅ Pattern {i+1} matched: "{match.group()}"')
            found_match = True
    if not found_match:
        print(f'  ❌ No patterns matched')
    print()

# Test specifically for the issue pattern
print("\n" + "="*60)
print("SPECIFIC TEST FOR pt-2 patterns:")
print("="*60)

issue_patterns = ['pt-2', 'PT-2', 'ab-1', 'xy-99']
target_pattern = r'\b[A-Za-z]{2}-\d+\b'
target_regex = re.compile(target_pattern, re.IGNORECASE)

for test in issue_patterns:
    match = target_regex.search(test)
    print(f'Pattern: {target_pattern}')
    print(f'Test: "{test}" -> {"✅ MATCH" if match else "❌ NO MATCH"}')
    if match:
        print(f'Matched text: "{match.group()}"')
    print() 