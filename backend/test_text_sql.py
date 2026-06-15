"""
Test script for Text-to-SQL Agent

Run this to verify the text-sql agent is working correctly.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from text_sql import (
    Text2SQLAgent,
    PostgresExecutor,
    PostgresSchemaManager,
    validate_sql,
    ask
)


def test_connection():
    """Test database connection."""
    print("=" * 60)
    print("Testing Database Connection")
    print("=" * 60)
    
    executor = PostgresExecutor()
    success, msg = executor.test_connection()
    
    if success:
        print(f"✓ Connected: {msg}")
        return True
    else:
        print(f"✗ Connection failed: {msg}")
        return False


def test_schema_manager():
    """Test schema manager."""
    print("\n" + "=" * 60)
    print("Testing Schema Manager")
    print("=" * 60)
    
    try:
        manager = PostgresSchemaManager()
        schema_text, schema_dict = manager.build_schema_text()
        
        print(f"✓ Schema loaded successfully")
        print(f"  Tables: {len(schema_dict)}")
        print(f"  Total columns: {sum(len(cols) for cols in schema_dict.values())}")
        print(f"\nTables found: {list(schema_dict.keys())[:5]}...")
        
        return True
    except Exception as e:
        print(f"✗ Schema manager test failed: {e}")
        return False


def test_validator():
    """Test SQL validator."""
    print("\n" + "=" * 60)
    print("Testing SQL Validator")
    print("=" * 60)
    
    schema = {
        "users": {"id", "name", "email"},
        "orders": {"id", "user_id", "amount", "status"}
    }
    
    test_cases = [
        ("SELECT * FROM users", True),
        ("SELECT name FROM users WHERE id = 1", True),
        ("DELETE FROM users", False),
        ("INSERT INTO users VALUES (1)", False),
        ("DROP TABLE users", False),
        ("SELECT * FROM nonexistent", False),
    ]
    
    passed = 0
    failed = 0
    
    for sql, expected in test_cases:
        is_valid, msg = validate_sql(sql, schema)
        status = "✓" if is_valid == expected else "✗"
        print(f"{status} {sql[:40]:40} -> {'Valid' if is_valid else 'Invalid'}")
        if is_valid == expected:
            passed += 1
        else:
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_agent():
    """Test the full agent."""
    print("\n" + "=" * 60)
    print("Testing Text-to-SQL Agent")
    print("=" * 60)
    
    try:
        agent = Text2SQLAgent()
        info = agent.get_schema_info()
        
        print(f"✓ Agent initialized")
        print(f"  Tables available: {info['tables']}")
        
        # Test with a simple question
        print("\nTesting question: 'How many tables are in the database?'")
        result = agent.run("How many tables are in the database?")
        
        if result.get("sql"):
            print(f"✓ SQL generated: {result['sql'][:80]}...")
        
        if result.get("success"):
            print(f"✓ Execution successful")
            print(f"  Row count: {result.get('row_count', 0)}")
            if result.get("summary"):
                print(f"  Summary: {result['summary'][:100]}...")
        else:
            print(f"⚠ Execution status: {result.get('execution_status')}")
            if result.get("error"):
                print(f"  Error: {result.get('error')}")
        
        return True
        
    except Exception as e:
        print(f"✗ Agent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints():
    """Test API endpoints (requires server to be running)."""
    print("\n" + "=" * 60)
    print("Testing API Endpoints")
    print("=" * 60)
    
    import requests
    
    base_url = "http://localhost:8000/text2sql"
    
    try:
        # Health check
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"✓ Health check: {response.json()}")
        else:
            print(f"⚠ Health check returned: {response.status_code}")
    except Exception as e:
        print(f"⚠ Could not connect to API: {e}")
        print("  (Make sure the server is running with: python run.py)")
        return False
    
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Text-to-SQL Agent Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Database Connection", test_connection()))
    results.append(("Schema Manager", test_schema_manager()))
    results.append(("SQL Validator", test_validator()))
    results.append(("Text-to-SQL Agent", test_agent()))
    results.append(("API Endpoints", test_api_endpoints()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All tests passed! The Text-to-SQL agent is ready to use.")
    else:
        print("\n⚠ Some tests failed. Check the errors above.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
