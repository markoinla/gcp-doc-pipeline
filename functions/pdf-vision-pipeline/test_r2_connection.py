#!/usr/bin/env python3
"""
Test script to verify R2 connection using existing Secret Manager secrets
Run this locally with: python test_r2_connection.py
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from storage_handler import get_r2_client
import json

def test_r2_connection():
    """Test R2 connection and list bucket contents"""
    try:
        print("🔐 Testing R2 connection...")
        
        # Get R2 client using our existing setup
        client = get_r2_client()
        print("✅ R2 client created successfully")
        
        # Test with default bucket
        bucket_name = 'ladders-1'
        
        # List objects to test connection
        print(f"📦 Testing bucket access: {bucket_name}")
        response = client.list_objects_v2(Bucket=bucket_name, MaxKeys=5)
        
        if 'Contents' in response:
            print(f"✅ Bucket accessible! Found {len(response['Contents'])} objects")
            print("📋 Sample objects:")
            for obj in response['Contents'][:3]:
                print(f"   - {obj['Key']} ({obj['Size']} bytes)")
        else:
            print("✅ Bucket accessible but empty")
        
        # Test upload with a small file
        test_key = "test-connection/ping.json"
        test_data = {"status": "test", "timestamp": "2024-01-01T00:00:00Z"}
        
        print(f"📤 Testing upload: {test_key}")
        client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=json.dumps(test_data),
            ContentType='application/json'
        )
        print("✅ Upload successful!")
        
        # Clean up test file
        client.delete_object(Bucket=bucket_name, Key=test_key)
        print("🧹 Test file cleaned up")
        
        print("\n🎉 R2 connection test PASSED - Ready to deploy!")
        return True
        
    except Exception as e:
        print(f"❌ R2 connection test FAILED: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_r2_connection()
    sys.exit(0 if success else 1) 