#!/bin/bash
# Integration tests for kv CLI

set -e

# Setup
export KV_DB=/tmp/kv-integration-test.db
rm -f "$KV_DB"

echo "Running integration tests..."

# Test 1: Set and get
echo -n "Test 1: Set and get... "
kv set test-key "hello world"
result=$(kv get test-key)
if [ "$result" = "hello world" ]; then
    echo "✓"
else
    echo "✗ Expected 'hello world', got '$result'"
    exit 1
fi

# Test 2: Get nonexistent key
echo -n "Test 2: Get nonexistent key... "
if kv get nonexistent 2>/dev/null; then
    echo "✗ Should have failed"
    exit 1
else
    exit_code=$?
    if [ $exit_code -eq 2 ]; then
        echo "✓"
    else
        echo "✗ Expected exit code 2, got $exit_code"
        exit 1
    fi
fi

# Test 3: Invalid key
echo -n "Test 3: Invalid key... "
if kv set INVALID "value" 2>/dev/null; then
    echo "✗ Should have failed"
    exit 1
else
    echo "✓"
fi

# Test 4: Stdin input
echo -n "Test 4: Stdin input... "
echo "from stdin" | kv set stdin-test
result=$(kv get stdin-test)
if [ "$result" = "from stdin" ]; then
    echo "✓"
else
    echo "✗ Expected 'from stdin', got '$result'"
    exit 1
fi

# Test 5: List keys
echo -n "Test 5: List keys... "
kv set alpha "first"
kv set zebra "last"
result=$(kv list --plain | cut -f1)
expected=$'alpha\nstdin-test\ntest-key\nzebra'
if [ "$result" = "$expected" ]; then
    echo "✓"
else
    echo "✗ Keys not in expected order"
    exit 1
fi

# Test 6: Expire and clean
echo -n "Test 6: Expire and clean... "
kv expire alpha 1
sleep 2
if kv get alpha 2>/dev/null; then
    exit_code=$?
    if [ $exit_code -ne 3 ]; then
        echo "✗ Expected exit code 3 for expired key, got $exit_code"
        exit 1
    fi
else
    exit_code=$?
    if [ $exit_code -eq 3 ]; then
        kv clean >/dev/null
        if kv get alpha 2>/dev/null; then
            echo "✗ Key should have been cleaned"
            exit 1
        else
            exit_code=$?
            if [ $exit_code -eq 2 ]; then
                echo "✓"
            else
                echo "✗ Expected exit code 2 after clean, got $exit_code"
                exit 1
            fi
        fi
    else
        echo "✗ Expected exit code 3 for expired key, got $exit_code"
        exit 1
    fi
fi

# Test 7: Remove key
echo -n "Test 7: Remove key... "
kv rm test-key
if kv get test-key 2>/dev/null; then
    echo "✗ Key should have been removed"
    exit 1
else
    exit_code=$?
    if [ $exit_code -eq 2 ]; then
        echo "✓"
    else
        echo "✗ Expected exit code 2, got $exit_code"
        exit 1
    fi
fi

# Test 8: Database permissions
echo -n "Test 8: Database permissions... "
rm -f "$KV_DB"
kv set perm-test "value"
perms=$(stat -c "%a" "$KV_DB")
if [ "$perms" = "600" ]; then
    echo "✓"
else
    echo "✗ Expected permissions 600, got $perms"
    exit 1
fi

# Cleanup
rm -f "$KV_DB"

echo ""
echo "All integration tests passed! ✓"
