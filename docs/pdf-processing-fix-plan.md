# PDF Processing Fix Plan: PT1 Matching Issue

## Problem Analysis

The current PDF processing pipeline is only returning 3 matches for "PT1" when the expected count is 21. After analyzing the code, the primary issue is **overly aggressive deduplication logic**.

## Root Cause

### Issue 1: Flawed Deduplication Logic
**Location**: `functions/pdf-processor/main.py`, lines 481-490

**Problem**: The current logic treats ANY two occurrences of the same pattern on the same page as duplicates if both have bounding boxes, regardless of their actual coordinates:

```python
# Check for duplicates on same page
existing_on_page = False
for existing_loc in items[item_key]["locations"]:
    if existing_loc["page"] == page_num:
        # If very close coordinates, consider it duplicate
        if bounding_box and existing_loc.get("bounding_box"):
            existing_on_page = True  # This is wrong!
            break
```

**Impact**: This causes the system to only keep the first occurrence of "PT1" per page, ignoring all subsequent occurrences.

### Issue 2: Missing Distance Calculation
The comment says "If very close coordinates, consider it duplicate" but there's no actual distance calculation.

### Issue 3: Potential Regex Issues
The current regex pattern is: `r'\b(PT-?\d+|M-?\d+|[A-Z]-?\d+)\b'`
This should catch PT1, PT-1, etc., but we need to verify it's working correctly.

## Solution Implementation Plan

### Phase 1: Fix Deduplication Logic

1. **Replace the flawed logic** with proper coordinate distance calculation
2. **Implement configurable distance threshold** (default: 10 pixels)
3. **Add logging** to track deduplication decisions

### Phase 2: Improve Pattern Detection

1. **Add regex debugging** to see what patterns are being matched
2. **Implement fallback text search** for critical patterns
3. **Add pattern statistics logging**

### Phase 3: Testing and Validation

1. **Test with the problematic PDF** (Boathouse - WhiteOaks)
2. **Verify PT1 count matches expected (21)**
3. **Test with other PDFs** to ensure no regression

## Detailed Implementation

### File: `functions/pdf-processor/main.py`

#### Change 1: Fix Deduplication Logic (Lines 481-490)

**Replace:**
```python
# Check for duplicates on same page
existing_on_page = False
for existing_loc in items[item_key]["locations"]:
    if existing_loc["page"] == page_num:
        # If very close coordinates, consider it duplicate
        if bounding_box and existing_loc.get("bounding_box"):
            existing_on_page = True
            break
```

**With:**
```python
# Check for duplicates on same page with proper distance calculation
existing_on_page = False
for existing_loc in items[item_key]["locations"]:
    if existing_loc["page"] == page_num:
        # Calculate distance between bounding boxes
        if bounding_box and existing_loc.get("bounding_box"):
            distance = calculate_bounding_box_distance(bounding_box, existing_loc["bounding_box"])
            if distance < 10:  # pixels threshold
                existing_on_page = True
                print(f"Duplicate {item_key} found on page {page_num} (distance: {distance:.2f}px)")
                break
        else:
            # If no bounding box info, be more lenient
            existing_on_page = False
```

#### Change 2: Add Distance Calculation Function

**Add new function after line 611:**
```python
def calculate_bounding_box_distance(bbox1, bbox2):
    """Calculate distance between two bounding boxes"""
    if not bbox1 or not bbox2:
        return float('inf')
    
    if 'vertices' not in bbox1 or 'vertices' not in bbox2:
        return float('inf')
    
    if len(bbox1['vertices']) == 0 or len(bbox2['vertices']) == 0:
        return float('inf')
    
    # Get center points of bounding boxes
    center1 = get_bounding_box_center(bbox1)
    center2 = get_bounding_box_center(bbox2)
    
    # Calculate Euclidean distance
    dx = center1['x'] - center2['x']
    dy = center1['y'] - center2['y']
    return (dx**2 + dy**2)**0.5

def get_bounding_box_center(bbox):
    """Get center point of a bounding box"""
    vertices = bbox['vertices']
    if len(vertices) == 0:
        return {'x': 0, 'y': 0}
    
    sum_x = sum(v.get('x', 0) for v in vertices)
    sum_y = sum(v.get('y', 0) for v in vertices)
    
    return {
        'x': sum_x / len(vertices),
        'y': sum_y / len(vertices)
    }
```

#### Change 3: Add Debug Logging (Line 413)

**Replace:**
```python
print("Extracting patterns and words from Document AI tokens...")
```

**With:**
```python
print("Extracting patterns and words from Document AI tokens...")
print(f"Looking for pattern: {pattern_regex.pattern}")
print(f"Document has {len(doc.pages)} pages")
```

#### Change 4: Add Pattern Match Logging (After line 450)

**Add after the pattern matching:**
```python
# Check if token is a pattern
if pattern_regex.match(token_text):
    item_key = token_text.upper().strip()
    item_type = "pattern"
    category = categorize_pattern(item_key)
    
    # Add debug logging for PT patterns
    if 'PT' in item_key:
        print(f"Found PT pattern: '{token_text}' -> '{item_key}' on page {page_num}")
```

#### Change 5: Fix Block-level Deduplication (Line 546)

**Replace:**
```python
# Check if we already have this on this page
existing_on_page = any(loc["page"] == page_num for loc in items[item_key]["locations"])
```

**With:**
```python
# Check if we already have this on this page with distance check
existing_on_page = False
for existing_loc in items[item_key]["locations"]:
    if existing_loc["page"] == page_num:
        if block_bounding_box and existing_loc.get("bounding_box"):
            distance = calculate_bounding_box_distance(block_bounding_box, existing_loc["bounding_box"])
            if distance < 20:  # Slightly higher threshold for blocks
                existing_on_page = True
                break
```

## Testing Plan

### Test Script Enhancement

Update `scripts/test-complete-pipeline.sh` to:

1. **Test the specific PDF** with PT1 counting
2. **Log detailed pattern matching results**
3. **Compare before/after results**

### Expected Outcomes

1. **PT1 matches should increase** from 3 to ~21
2. **No significant performance degradation**
3. **Other patterns should maintain accuracy**

### Rollback Plan

If issues arise:
1. **Revert the distance calculation logic**
2. **Fall back to simple existence check** with debug logging
3. **Investigate Document AI token extraction issues**

## Success Criteria

- [ ] PT1 count matches expected value (21)
- [ ] No regression in other pattern detection
- [ ] Processing time remains acceptable (<60 seconds)
- [ ] Duplicate detection still works for actual duplicates
- [ ] Detailed logging shows pattern matching decisions

## Files to Modify

1. `functions/pdf-processor/main.py` - Main implementation
2. `scripts/test-complete-pipeline.sh` - Enhanced testing
3. `docs/progress.md` - Update progress tracking

## Implementation Priority

**High Priority**: Fix deduplication logic (Changes 1-2)
**Medium Priority**: Add debugging (Changes 3-4)  
**Low Priority**: Testing enhancements (Change 5) 