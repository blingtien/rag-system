#!/bin/bash
# Quick test execution script for RAG-Anything Batch Processing Optimization Tests
# Author: Claude Code
# Date: 2025-08-23

echo "🚀 RAG-Anything Batch Processing Optimization Test Suite"
echo "========================================================"
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if server is running
check_server() {
    echo "🔍 Checking API server health..."
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ API server is running and healthy${NC}"
        return 0
    else
        echo -e "${RED}❌ API server is not available on localhost:8001${NC}"
        echo "Please start the RAG API server before running tests."
        echo
        echo "To start the server:"
        echo "  cd /path/to/RAG-Anything/api"
        echo "  python rag_api_server.py"
        echo
        return 1
    fi
}

# Function to check dependencies
check_dependencies() {
    echo "📦 Checking test dependencies..."
    
    local deps=("httpx" "websockets" "matplotlib" "numpy" "psutil")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! python -c "import $dep" 2>/dev/null; then
            missing+=("$dep")
        fi
    done
    
    if [ ${#missing[@]} -eq 0 ]; then
        echo -e "${GREEN}✅ All dependencies are installed${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️ Missing dependencies: ${missing[*]}${NC}"
        echo "Installing missing dependencies..."
        pip install "${missing[@]}"
        return $?
    fi
}

# Function to run individual test
run_individual_test() {
    local test_name=$1
    local test_file=$2
    
    echo -e "${BLUE}🧪 Running $test_name...${NC}"
    
    if python "$test_file"; then
        echo -e "${GREEN}✅ $test_name completed successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ $test_name failed${NC}"
        return 1
    fi
}

# Function to run all tests
run_all_tests() {
    echo -e "${BLUE}🧪 Running comprehensive test suite...${NC}"
    echo
    
    if python run_all_batch_optimization_tests.py; then
        echo
        echo -e "${GREEN}✅ All tests completed successfully!${NC}"
        return 0
    else
        echo
        echo -e "${RED}❌ Some tests failed. Check the results for details.${NC}"
        return 1
    fi
}

# Main menu
show_menu() {
    echo "Select test execution option:"
    echo "1) Run all tests (comprehensive)"
    echo "2) Run batch processing optimization tests"
    echo "3) Run performance benchmark tests"
    echo "4) Run cache effectiveness tests"
    echo "5) Run error handling tests"
    echo "6) Run progress tracking tests"
    echo "7) Run frontend integration tests"
    echo "8) Run system health monitoring tests"
    echo "9) Check server health only"
    echo "0) Exit"
    echo
}

# Process menu choice
process_choice() {
    case $1 in
        1)
            run_all_tests
            ;;
        2)
            run_individual_test "Batch Processing Optimization" "test_batch_processing_optimizations.py"
            ;;
        3)
            run_individual_test "Performance Benchmark" "test_batch_performance_optimization.py"
            ;;
        4)
            run_individual_test "Cache Effectiveness" "test_intelligent_cache_system.py"
            ;;
        5)
            run_individual_test "Error Handling" "test_enhanced_error_handling.py"
            ;;
        6)
            run_individual_test "Progress Tracking" "test_progress_tracking_websocket.py"
            ;;
        7)
            run_individual_test "Frontend Integration" "test_frontend_integration_patterns.py"
            ;;
        8)
            run_individual_test "System Health Monitoring" "test_system_health_monitoring.py"
            ;;
        9)
            check_server
            ;;
        0)
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Invalid option. Please select 0-9.${NC}"
            ;;
    esac
}

# Main execution
main() {
    # Check if we're in the right directory
    if [ ! -f "run_all_batch_optimization_tests.py" ]; then
        echo -e "${RED}❌ Error: Test files not found in current directory${NC}"
        echo "Please run this script from the RAG-Anything/api directory"
        exit 1
    fi
    
    # Check dependencies
    if ! check_dependencies; then
        echo -e "${RED}❌ Failed to install dependencies${NC}"
        exit 1
    fi
    
    echo
    
    # Check server health
    if ! check_server; then
        exit 1
    fi
    
    echo
    
    # If command line argument provided, run that test
    if [ $# -eq 1 ]; then
        case $1 in
            "all"|"comprehensive")
                run_all_tests
                exit $?
                ;;
            "batch")
                run_individual_test "Batch Processing Optimization" "test_batch_processing_optimizations.py"
                exit $?
                ;;
            "performance")
                run_individual_test "Performance Benchmark" "test_batch_performance_optimization.py"
                exit $?
                ;;
            "cache")
                run_individual_test "Cache Effectiveness" "test_intelligent_cache_system.py"
                exit $?
                ;;
            "error")
                run_individual_test "Error Handling" "test_enhanced_error_handling.py"
                exit $?
                ;;
            "progress")
                run_individual_test "Progress Tracking" "test_progress_tracking_websocket.py"
                exit $?
                ;;
            "frontend")
                run_individual_test "Frontend Integration" "test_frontend_integration_patterns.py"
                exit $?
                ;;
            "health")
                run_individual_test "System Health Monitoring" "test_system_health_monitoring.py"
                exit $?
                ;;
            *)
                echo -e "${RED}❌ Unknown test: $1${NC}"
                echo "Available tests: all, batch, performance, cache, error, progress, frontend, health"
                exit 1
                ;;
        esac
    fi
    
    # Interactive mode
    while true; do
        echo
        show_menu
        read -p "Enter your choice (0-9): " choice
        echo
        
        process_choice "$choice"
        
        if [ "$choice" != "9" ] && [ "$choice" != "0" ]; then
            echo
            read -p "Press Enter to continue..."
        fi
    done
}

# Help text
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "RAG-Anything Batch Processing Optimization Test Runner"
    echo
    echo "Usage:"
    echo "  $0                    # Interactive mode"
    echo "  $0 all               # Run all tests"
    echo "  $0 batch             # Run batch processing tests"
    echo "  $0 performance       # Run performance benchmark tests"
    echo "  $0 cache             # Run cache effectiveness tests"
    echo "  $0 error             # Run error handling tests"
    echo "  $0 progress          # Run progress tracking tests"
    echo "  $0 frontend          # Run frontend integration tests"
    echo "  $0 health            # Run system health monitoring tests"
    echo
    echo "Prerequisites:"
    echo "  - RAG API server running on localhost:8001"
    echo "  - Python dependencies: httpx, websockets, matplotlib, numpy, psutil"
    echo
    echo "Results are saved as JSON files in the current directory."
    echo
    exit 0
fi

# Run main function
main "$@"