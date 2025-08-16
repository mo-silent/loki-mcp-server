"""Performance tests for query handling."""

import asyncio
import time
from unittest.mock import AsyncMock, patch
import pytest

from app.config import LokiConfig
from ..fixtures.sample_logs import (
    SAMPLE_QUERY_RANGE_RESPONSE,
    SAMPLE_QUERY_INSTANT_RESPONSE,
    SAMPLE_LABELS_RESPONSE,
    generate_large_log_dataset
)
from ..utils.mcp_client import MCPTestClient, simulate_concurrent_requests


class TestQueryPerformance:
    """Test query performance and scalability."""
    
    @pytest.fixture
    def config(self):
        """Performance test configuration."""
        return LokiConfig(
            url="http://localhost:3100",
            timeout=60,  # Longer timeout for performance tests
            max_retries=1,
            rate_limit_requests=1000,  # High rate limit for performance testing
            rate_limit_period=60
        )
    
    @pytest.mark.asyncio
    async def test_single_query_performance(self, config):
        """Test performance of single query execution."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            async with MCPTestClient(config) as client:
                # Measure single query performance
                start_time = time.time()
                
                response = await client.query_logs(
                    query='{job="web-server"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T01:00:00Z",
                    limit=1000
                )
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Should complete within reasonable time
                assert execution_time < 1.0  # Less than 1 second
                assert len(response) > 0
                assert response[0].text is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_query_performance(self, config):
        """Test performance with concurrent queries."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            # Prepare multiple concurrent queries
            num_queries = 20
            tool_calls = []
            for i in range(num_queries):
                tool_calls.append({
                    "name": "query_logs",
                    "arguments": {
                        "query": f'{{job="service-{i}"}}',
                        "start": "2024-01-01T00:00:00Z",
                        "end": "2024-01-01T01:00:00Z",
                        "limit": 100
                    }
                })
            
            async with MCPTestClient(config) as client:
                start_time = time.time()
                
                # Execute concurrent queries
                results = await simulate_concurrent_requests(
                    client,
                    tool_calls,
                    max_concurrent=10
                )
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Should complete all queries efficiently
                assert execution_time < 5.0  # Less than 5 seconds for 20 queries
                assert len(results) == num_queries
                
                # All queries should succeed
                for result in results:
                    assert not isinstance(result, Exception)
                    assert len(result) > 0
                
                # Calculate queries per second
                qps = num_queries / execution_time
                assert qps > 4  # At least 4 queries per second
    
    @pytest.mark.asyncio
    async def test_large_response_performance(self, config):
        """Test performance with large response datasets."""
        large_response = generate_large_log_dataset(10000)
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = large_response
            
            async with MCPTestClient(config) as client:
                start_time = time.time()
                
                response = await client.query_logs(
                    query='{job="web-server"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T23:59:59Z",
                    limit=10000
                )
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Should handle large responses efficiently
                assert execution_time < 2.0  # Less than 2 seconds
                assert len(response) > 0
                
                response_text = response[0].text
                assert "Found 10000 log entries" in response_text
                # Should truncate display for performance
                assert "... and 9990 more entries" in response_text
    
    @pytest.mark.asyncio
    async def test_memory_usage_with_large_datasets(self, config):
        """Test memory usage with large datasets."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate very large response
        very_large_response = generate_large_log_dataset(50000)
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = very_large_response
            
            async with MCPTestClient(config) as client:
                # Process large dataset
                response = await client.query_logs(
                    query='{job="web-server"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T23:59:59Z",
                    limit=50000
                )
                
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory
                
                # Memory increase should be reasonable (less than 100MB)
                assert memory_increase < 100
                assert len(response) > 0
    
    @pytest.mark.asyncio
    async def test_rate_limiting_performance(self, config):
        """Test performance under rate limiting conditions."""
        # Set moderate rate limits
        config.rate_limit_requests = 10
        config.rate_limit_period = 1
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_INSTANT_RESPONSE
            
            async with MCPTestClient(config) as client:
                # Make requests that will hit rate limits
                num_requests = 15
                start_time = time.time()
                
                tasks = []
                for i in range(num_requests):
                    task = client.query_logs(query=f'{{job="service-{i}"}}')
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Should take at least 1 second due to rate limiting
                assert execution_time >= 0.9
                
                # All requests should eventually succeed
                successful_results = [r for r in results if not isinstance(r, Exception)]
                assert len(successful_results) == num_requests
    
    @pytest.mark.asyncio
    async def test_search_performance_with_multiple_keywords(self, config):
        """Test search performance with multiple keywords."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            # Test with increasing number of keywords
            keyword_sets = [
                ["error"],
                ["error", "failed"],
                ["error", "failed", "timeout"],
                ["error", "failed", "timeout", "exception", "critical"]
            ]
            
            async with MCPTestClient(config) as client:
                performance_results = []
                
                for keywords in keyword_sets:
                    start_time = time.time()
                    
                    response = await client.search_logs(
                        keywords=keywords,
                        start="2024-01-01T00:00:00Z",
                        end="2024-01-01T01:00:00Z",
                        limit=1000
                    )
                    
                    end_time = time.time()
                    execution_time = end_time - start_time
                    
                    performance_results.append({
                        "keyword_count": len(keywords),
                        "execution_time": execution_time
                    })
                    
                    # Each search should complete quickly
                    assert execution_time < 1.0
                    assert len(response) > 0
                
                # Performance should not degrade significantly with more keywords
                max_time = max(r["execution_time"] for r in performance_results)
                min_time = min(r["execution_time"] for r in performance_results)
                assert max_time / min_time < 3.0  # Less than 3x difference
    
    @pytest.mark.asyncio
    async def test_label_operations_performance(self, config):
        """Test performance of label operations."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_LABELS_RESPONSE
            
            async with MCPTestClient(config) as client:
                # Test multiple label operations
                operations = [
                    ("get_labels", {}),
                    ("get_labels", {"label_name": "job"}),
                    ("get_labels", {"label_name": "level"}),
                    ("get_labels", {"label_name": "instance"})
                ]
                
                start_time = time.time()
                
                for operation_name, args in operations:
                    response = await client.get_labels(**args)
                    assert len(response) > 0
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # All label operations should complete quickly
                assert execution_time < 2.0
                
                # Calculate operations per second
                ops_per_second = len(operations) / execution_time
                assert ops_per_second > 2  # At least 2 operations per second
    
    @pytest.mark.asyncio
    async def test_mixed_workload_performance(self, config):
        """Test performance with mixed workload (queries, searches, labels)."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.side_effect = [
                SAMPLE_LABELS_RESPONSE,
                SAMPLE_QUERY_RANGE_RESPONSE,
                SAMPLE_QUERY_INSTANT_RESPONSE,
                SAMPLE_LABELS_RESPONSE,
                SAMPLE_QUERY_RANGE_RESPONSE
            ] * 10  # Repeat pattern 10 times
            
            # Mixed workload
            mixed_calls = []
            for i in range(10):
                mixed_calls.extend([
                    {"name": "get_labels", "arguments": {}},
                    {"name": "query_logs", "arguments": {
                        "query": f'{{job="service-{i}"}}',
                        "start": "2024-01-01T00:00:00Z",
                        "end": "2024-01-01T01:00:00Z"
                    }},
                    {"name": "search_logs", "arguments": {
                        "keywords": ["error"],
                        "start": "2024-01-01T00:00:00Z",
                        "end": "2024-01-01T01:00:00Z"
                    }},
                    {"name": "get_labels", "arguments": {"label_name": "level"}},
                    {"name": "query_logs", "arguments": {
                        "query": f'{{level="error"}}',
                        "start": "2024-01-01T00:00:00Z",
                        "end": "2024-01-01T01:00:00Z"
                    }}
                ])
            
            async with MCPTestClient(config) as client:
                start_time = time.time()
                
                results = await simulate_concurrent_requests(
                    client,
                    mixed_calls,
                    max_concurrent=5
                )
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Should handle mixed workload efficiently
                assert execution_time < 10.0  # Less than 10 seconds for 50 operations
                assert len(results) == len(mixed_calls)
                
                # All operations should succeed
                successful_results = [r for r in results if not isinstance(r, Exception)]
                assert len(successful_results) == len(mixed_calls)
                
                # Calculate throughput
                throughput = len(mixed_calls) / execution_time
                assert throughput > 5  # At least 5 operations per second
    
    @pytest.mark.asyncio
    async def test_response_formatting_performance(self, config):
        """Test performance of response formatting with large datasets."""
        # Create response with many entries
        large_response = generate_large_log_dataset(1000)
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = large_response
            
            async with MCPTestClient(config) as client:
                start_time = time.time()
                
                response = await client.query_logs(
                    query='{job="web-server"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T01:00:00Z",
                    limit=1000
                )
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Response formatting should be fast even with large datasets
                assert execution_time < 1.0
                assert len(response) > 0
                
                response_text = response[0].text
                # Should limit display for performance
                assert "Found 1000 log entries" in response_text
                assert "... and 990 more entries" in response_text
    
    @pytest.mark.asyncio
    async def test_error_handling_performance(self, config):
        """Test performance of error handling."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            # Simulate various errors
            mock_request.side_effect = Exception("Simulated error")
            
            async with MCPTestClient(config) as client:
                start_time = time.time()
                
                # Make multiple requests that will fail
                error_calls = []
                for i in range(10):
                    error_calls.extend([
                        {"name": "query_logs", "arguments": {"query": f'{{job="service-{i}"}}'}},
                        {"name": "search_logs", "arguments": {"keywords": ["error"]}},
                        {"name": "get_labels", "arguments": {}}
                    ])
                
                results = await simulate_concurrent_requests(
                    client,
                    error_calls,
                    max_concurrent=5
                )
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Error handling should be fast
                assert execution_time < 3.0
                assert len(results) == len(error_calls)
                
                # All should return error responses (not exceptions)
                for result in results:
                    assert not isinstance(result, Exception)
                    assert len(result) > 0
                    assert result[0].text.startswith("Error:")


@pytest.mark.performance
class TestPerformanceBenchmarks:
    """Performance benchmarks for regression testing."""
    
    @pytest.fixture
    def benchmark_config(self):
        """Configuration optimized for benchmarking."""
        return LokiConfig(
            url="http://localhost:3100",
            timeout=30,
            max_retries=0,  # No retries for consistent timing
            rate_limit_requests=1000,
            rate_limit_period=60
        )
    
    @pytest.mark.asyncio
    async def test_baseline_query_benchmark(self, benchmark_config):
        """Baseline benchmark for query performance."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            async with MCPTestClient(benchmark_config) as client:
                # Warm up
                await client.query_logs(query='{job="warmup"}')
                
                # Benchmark
                iterations = 100
                start_time = time.time()
                
                for i in range(iterations):
                    await client.query_logs(
                        query=f'{{job="benchmark-{i % 10}"}}',
                        start="2024-01-01T00:00:00Z",
                        end="2024-01-01T01:00:00Z"
                    )
                
                end_time = time.time()
                total_time = end_time - start_time
                avg_time = total_time / iterations
                
                # Performance targets
                assert avg_time < 0.01  # Less than 10ms per query
                assert total_time < 1.0  # Less than 1 second total
                
                print(f"Baseline benchmark: {avg_time*1000:.2f}ms per query, {iterations/total_time:.1f} QPS")
    
    @pytest.mark.asyncio
    async def test_concurrent_benchmark(self, benchmark_config):
        """Benchmark for concurrent query performance."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            concurrent_levels = [1, 5, 10, 20]
            results = {}
            
            async with MCPTestClient(benchmark_config) as client:
                for concurrency in concurrent_levels:
                    # Prepare concurrent calls
                    calls = [
                        {"name": "query_logs", "arguments": {"query": f'{{job="test-{i}"}}'}}
                        for i in range(concurrency * 5)  # 5 calls per concurrent level
                    ]
                    
                    start_time = time.time()
                    
                    await simulate_concurrent_requests(
                        client,
                        calls,
                        max_concurrent=concurrency
                    )
                    
                    end_time = time.time()
                    total_time = end_time - start_time
                    
                    results[concurrency] = {
                        "total_time": total_time,
                        "qps": len(calls) / total_time
                    }
                
                # Performance should scale with concurrency
                assert results[10]["qps"] > results[1]["qps"]
                assert results[20]["qps"] > results[5]["qps"]
                
                for concurrency, metrics in results.items():
                    print(f"Concurrency {concurrency}: {metrics['qps']:.1f} QPS")