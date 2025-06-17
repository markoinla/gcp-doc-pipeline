#!/usr/bin/env python3
"""
Chunking Performance Analysis: Test different chunk sizes for optimal performance
"""

def analyze_chunking_performance():
    """Analyze optimal chunk sizes for our 18-page PDF"""
    
    total_pages = 18
    avg_time_per_page = 3.94  # seconds from our test
    parallel_workers = 15
    
    print("🔍 CHUNKING PERFORMANCE ANALYSIS")
    print(f"📄 Total pages: {total_pages}")
    print(f"⏱️  Avg time per page: {avg_time_per_page}s")
    print(f"👥 Available workers: {parallel_workers}")
    print(f"📊 Sequential total: {total_pages * avg_time_per_page:.1f}s")
    print()
    
    chunk_sizes = [1, 2, 3, 4, 5, 6, 9, 18]  # Different chunk sizes to test
    
    print("🚀 CHUNK SIZE PERFORMANCE COMPARISON:")
    print("Chunk | Chunks | Longest | Parallel | Speedup | Workers")
    print("Size  | Total  | Chunk   | Time     | Factor  | Used")
    print("-" * 55)
    
    for chunk_size in chunk_sizes:
        # Calculate number of chunks
        num_chunks = (total_pages + chunk_size - 1) // chunk_size
        
        # Calculate pages in longest chunk
        longest_chunk_pages = min(chunk_size, total_pages - (num_chunks - 1) * chunk_size)
        if longest_chunk_pages <= 0:
            longest_chunk_pages = chunk_size
            
        # Calculate parallel processing time (time of longest chunk)
        parallel_time = longest_chunk_pages * avg_time_per_page
        
        # Calculate speedup
        sequential_time = total_pages * avg_time_per_page
        speedup = sequential_time / parallel_time
        
        # Workers actually used
        workers_used = min(num_chunks, parallel_workers)
        
        print(f"{chunk_size:4d}  | {num_chunks:5d}  | {longest_chunk_pages:6d}  | {parallel_time:7.1f}s | {speedup:6.1f}x | {workers_used:6d}")
    
    print()
    print("🎯 RECOMMENDATIONS:")
    
    # Find optimal chunk size (best speedup while using workers efficiently)
    best_speedup = 0
    best_chunk_size = 5
    
    for chunk_size in chunk_sizes:
        num_chunks = (total_pages + chunk_size - 1) // chunk_size
        longest_chunk_pages = min(chunk_size, total_pages - (num_chunks - 1) * chunk_size)
        if longest_chunk_pages <= 0:
            longest_chunk_pages = chunk_size
        parallel_time = longest_chunk_pages * avg_time_per_page
        speedup = (total_pages * avg_time_per_page) / parallel_time
        
        if speedup > best_speedup and num_chunks <= parallel_workers:
            best_speedup = speedup
            best_chunk_size = chunk_size
    
    print(f"✅ OPTIMAL: chunk_size = {best_chunk_size} gives {best_speedup:.1f}x speedup")
    print(f"⏱️  Time reduction: {total_pages * avg_time_per_page:.1f}s → {total_pages * avg_time_per_page / best_speedup:.1f}s")
    print(f"💰 Cost efficiency: Better resource utilization with parallel processing")
    
    print()
    print("🔬 DETAILED ANALYSIS:")
    print("• chunk_size=1: Maximum parallelism but high overhead")
    print("• chunk_size=2-3: Great balance of speed vs overhead") 
    print("• chunk_size=5: Current default, good for most cases")
    print("• chunk_size=18: No parallelism (sequential)")
    
    return best_chunk_size

if __name__ == "__main__":
    analyze_chunking_performance() 