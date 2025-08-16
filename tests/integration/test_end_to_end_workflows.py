"""End-to-end tests for complete workflows."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from app.config import LokiConfig
from ..fixtures.sample_logs import (
    SAMPLE_QUERY_RANGE_RESPONSE,
    SAMPLE_QUERY_INSTANT_RESPONSE,
    SAMPLE_LABELS_RESPONSE,
    SAMPLE_LABEL_VALUES_RESPONSE,
    SAMPLE_MCP_CALLS,
    TIME_RANGES
)
from ..utils.mcp_client import (
    MCPTestClient,
    assert_tool_response_format,
    assert_successful_response,
    assert_error_response,
    extract_response_text,
    simulate_concurrent_requests
)


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear label cache before each test."""
        from app.tools.get_labels import clear_label_cache
        clear_label_cache()
    
    @pytest.fixture
    def config(self):
        """Test configuration."""
        return LokiConfig(
            url="http://localhost:3100",
            timeout=30,
            max_retries=2
        )
    
    @pytest.mark.asyncio
    async def test_complete_log_investigation_workflow(self, config):
        """Test a complete log investigation workflow."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            # Setup responses for the workflow
            mock_request.side_effect = [
                SAMPLE_LABELS_RESPONSE,  # get_labels call
                SAMPLE_LABEL_VALUES_RESPONSE,  # get_labels with label_name
                SAMPLE_QUERY_RANGE_RESPONSE,  # query_logs call
                SAMPLE_QUERY_INSTANT_RESPONSE  # search_logs call
            ]
            
            async with MCPTestClient(config) as client:
                # Step 1: Discover available labels
                labels_response = await client.get_labels()
                assert_tool_response_format(labels_response)
                assert_successful_response(labels_response)
                
                labels_text = extract_response_text(labels_response)
                assert "Found 4 label names" in labels_text
                assert "job" in labels_text
                assert "level" in labels_text
                
                # Step 2: Get values for the 'level' label
                level_values_response = await client.get_labels(label_name="level")
                assert_tool_response_format(level_values_response)
                assert_successful_response(level_values_response)
                
                level_text = extract_response_text(level_values_response)
                assert "Found 4 values for label 'level'" in level_text
                assert "error" in level_text
                
                # Step 3: Query logs for a specific service
                query_response = await client.query_logs(
                    query='{job="web-server"}',
                    start=TIME_RANGES["last_hour"]["start"],
                    end=TIME_RANGES["last_hour"]["end"],
                    limit=100
                )
                assert_tool_response_format(query_response)
                assert_successful_response(query_response)
                
                query_text = extract_response_text(query_response)
                assert "Found" in query_text
                assert "web-server" in query_text
                
                # Step 4: Search for error logs
                search_response = await client.search_logs(
                    keywords=["error", "failed"],
                    start=TIME_RANGES["last_hour"]["start"],
                    end=TIME_RANGES["last_hour"]["end"],
                    limit=50
                )
                assert_tool_response_format(search_response)
                assert_successful_response(search_response)
                
                search_text = extract_response_text(search_response)
                assert "Found" in search_text
                
                # Verify all expected calls were made
                assert mock_request.call_count == 4
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, config):
        """Test workflow with error recovery."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            # First call fails, subsequent calls succeed
            mock_request.side_effect = [
                Exception("Connection timeout"),  # get_labels: First attempt fails
                SAMPLE_LABELS_RESPONSE,  # get_labels: Retry succeeds
                SAMPLE_QUERY_RANGE_RESPONSE,  # query_logs range: Succeeds
                SAMPLE_QUERY_INSTANT_RESPONSE  # query_logs instant: Succeeds
            ]
            
            async with MCPTestClient(config) as client:
                # First call should succeed after retry (first attempt fails, retry succeeds)
                labels_response = await client.get_labels()
                assert_tool_response_format(labels_response)
                assert_successful_response(labels_response)  # Should succeed after retry
                
                # Second call should succeed immediately
                query_response = await client.query_logs(
                    query='{job="web-server"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T01:00:00Z"
                )
                assert_tool_response_format(query_response)
                assert_successful_response(query_response)
                
                # Third call should also succeed
                query_response = await client.query_logs(query='{job="web-server"}')
                assert_tool_response_format(query_response)
                assert_successful_response(query_response)
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_workflow(self, config):
        """Test performance monitoring workflow with multiple queries."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            async with MCPTestClient(config) as client:
                # Simulate monitoring multiple services
                services = ["web-server", "api-gateway", "database", "cache"]
                
                start_time = asyncio.get_event_loop().time()
                
                # Query each service
                responses = []
                for service in services:
                    response = await client.query_logs(
                        query=f'{{job="{service}"}}',
                        start=TIME_RANGES["last_hour"]["start"],
                        end=TIME_RANGES["last_hour"]["end"],
                        limit=100
                    )
                    responses.append(response)
                
                end_time = asyncio.get_event_loop().time()
                
                # Verify all responses are successful
                for response in responses:
                    assert_tool_response_format(response)
                    assert_successful_response(response)
                
                # Should complete in reasonable time (sequential)
                assert end_time - start_time < 5.0
                assert mock_request.call_count == len(services)
    
    @pytest.mark.asyncio
    async def test_concurrent_investigation_workflow(self, config):
        """Test concurrent investigation workflow."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            # Prepare concurrent tool calls
            tool_calls = [
                {
                    "name": "query_logs",
                    "arguments": {
                        "query": '{job="web-server"}',
                        "start": TIME_RANGES["last_hour"]["start"],
                        "end": TIME_RANGES["last_hour"]["end"]
                    }
                },
                {
                    "name": "query_logs",
                    "arguments": {
                        "query": '{job="api-gateway"}',
                        "start": TIME_RANGES["last_hour"]["start"],
                        "end": TIME_RANGES["last_hour"]["end"]
                    }
                },
                {
                    "name": "search_logs",
                    "arguments": {
                        "keywords": ["error"],
                        "start": TIME_RANGES["last_hour"]["start"],
                        "end": TIME_RANGES["last_hour"]["end"]
                    }
                }
            ]
            
            async with MCPTestClient(config) as client:
                start_time = asyncio.get_event_loop().time()
                
                # Execute concurrent requests
                results = await simulate_concurrent_requests(
                    client, 
                    tool_calls, 
                    max_concurrent=3
                )
                
                end_time = asyncio.get_event_loop().time()
                
                # Verify all results are successful
                for result in results:
                    assert not isinstance(result, Exception)
                    assert_tool_response_format(result)
                    assert_successful_response(result)
                
                # Should complete faster than sequential execution
                assert end_time - start_time < 3.0
                assert mock_request.call_count == len(tool_calls)
    
    @pytest.mark.asyncio
    async def test_data_exploration_workflow(self, config):
        """Test data exploration workflow."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.side_effect = [
                SAMPLE_LABELS_RESPONSE,  # get_labels
                SAMPLE_LABEL_VALUES_RESPONSE,  # get_labels for 'job'
                SAMPLE_LABEL_VALUES_RESPONSE,  # get_labels for 'level'
                SAMPLE_QUERY_RANGE_RESPONSE,  # query specific job
                SAMPLE_QUERY_INSTANT_RESPONSE  # search for errors
            ]
            
            async with MCPTestClient(config) as client:
                # Step 1: Explore available labels
                labels_response = await client.get_labels()
                assert_successful_response(labels_response)
                
                # Step 2: Explore job values
                job_values_response = await client.get_labels(
                    label_name="job",
                    start=TIME_RANGES["last_day"]["start"],
                    end=TIME_RANGES["last_day"]["end"]
                )
                assert_successful_response(job_values_response)
                
                # Step 3: Explore level values
                level_values_response = await client.get_labels(
                    label_name="level",
                    start=TIME_RANGES["last_day"]["start"],
                    end=TIME_RANGES["last_day"]["end"]
                )
                assert_successful_response(level_values_response)
                
                # Step 4: Query specific job and level
                specific_query_response = await client.query_logs(
                    query='{job="web-server", level="info"}',
                    start=TIME_RANGES["last_hour"]["start"],
                    end=TIME_RANGES["last_hour"]["end"]
                )
                assert_successful_response(specific_query_response)
                
                # Step 5: Search for error patterns
                error_search_response = await client.search_logs(
                    keywords=["error", "exception", "failed"],
                    start=TIME_RANGES["last_hour"]["start"],
                    end=TIME_RANGES["last_hour"]["end"]
                )
                assert_successful_response(error_search_response)
                
                assert mock_request.call_count == 5
    
    @pytest.mark.asyncio
    async def test_time_range_analysis_workflow(self, config):
        """Test time range analysis workflow."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            async with MCPTestClient(config) as client:
                # Analyze different time ranges
                time_ranges = [
                    ("last_hour", TIME_RANGES["last_hour"]),
                    ("custom_range", TIME_RANGES["custom_range"])
                ]
                
                results = {}
                for range_name, time_range in time_ranges:
                    response = await client.query_logs(
                        query='{job="web-server"}',
                        start=time_range["start"],
                        end=time_range["end"],
                        limit=1000
                    )
                    
                    assert_successful_response(response)
                    results[range_name] = extract_response_text(response)
                
                # Verify we got results for each time range
                for range_name, result_text in results.items():
                    assert "Found" in result_text or "No" in result_text
                
                assert mock_request.call_count == len(time_ranges)
    
    @pytest.mark.asyncio
    async def test_complex_query_workflow(self, config):
        """Test workflow with complex LogQL queries."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            complex_queries = [
                '{job="web-server"} |= "error" | json | status_code="500"',
                '{job="web-server"} |~ "user.*failed" | line_format "{{.timestamp}} {{.message}}"',
                'rate({job="web-server"}[5m])',
                'count_over_time({job="web-server", level="error"}[1h])'
            ]
            
            async with MCPTestClient(config) as client:
                for query in complex_queries:
                    response = await client.query_logs(
                        query=query,
                        start=TIME_RANGES["last_hour"]["start"],
                        end=TIME_RANGES["last_hour"]["end"]
                    )
                    
                    assert_tool_response_format(response)
                    # Complex queries might return different result formats
                    # Just verify we get a response without errors
                    response_text = extract_response_text(response)
                    assert not response_text.startswith("Error:")
                
                assert mock_request.call_count == len(complex_queries)
    
    @pytest.mark.asyncio
    async def test_large_dataset_workflow(self, config):
        """Test workflow with large datasets."""
        from ..fixtures.sample_logs import generate_large_log_dataset
        
        large_response = generate_large_log_dataset(5000)
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = large_response
            
            async with MCPTestClient(config) as client:
                # Query large dataset
                response = await client.query_logs(
                    query='{job="web-server"}',
                    start=TIME_RANGES["last_day"]["start"],
                    end=TIME_RANGES["last_day"]["end"],
                    limit=5000
                )
                
                assert_tool_response_format(response)
                assert_successful_response(response)
                
                response_text = extract_response_text(response)
                assert "Found 5000 log entries" in response_text
                # Should truncate display to first 10 entries
                assert "... and 4990 more entries" in response_text
    
    @pytest.mark.asyncio
    async def test_empty_results_workflow(self, config):
        """Test workflow handling empty results."""
        empty_response = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": []
            }
        }
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = empty_response
            
            async with MCPTestClient(config) as client:
                # Query that returns no results
                response = await client.query_logs(
                    query='{job="nonexistent-service"}',
                    start=TIME_RANGES["last_hour"]["start"],
                    end=TIME_RANGES["last_hour"]["end"]
                )
                
                assert_tool_response_format(response)
                response_text = extract_response_text(response)
                assert "No log entries found matching the criteria" in response_text
                
                # Search that returns no results
                search_response = await client.search_logs(
                    keywords=["nonexistent-keyword"],
                    start=TIME_RANGES["last_hour"]["start"],
                    end=TIME_RANGES["last_hour"]["end"]
                )
                
                assert_tool_response_format(search_response)
                search_text = extract_response_text(search_response)
                assert "No log entries found matching the criteria" in search_text
    
    @pytest.mark.asyncio
    async def test_mixed_success_failure_workflow(self, config):
        """Test workflow with mixed success and failure responses."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.side_effect = [
                SAMPLE_LABELS_RESPONSE,  # Call 1: Success
                Exception("Query timeout"),  # Call 2: First attempt fails
                SAMPLE_QUERY_INSTANT_RESPONSE,  # Call 2: Retry succeeds
                Exception("Rate limit exceeded"),  # Call 3: First attempt fails
                Exception("Rate limit exceeded"),  # Call 3: Second retry fails  
                Exception("Rate limit exceeded"),  # Call 3: Third retry fails (exhausts retries)
                SAMPLE_QUERY_INSTANT_RESPONSE  # Call 4: Success
            ]
            
            async with MCPTestClient(config) as client:
                # Call 1: Should succeed
                response1 = await client.get_labels()
                assert_successful_response(response1)
                
                # Call 2: Should succeed after retry (fails first attempt, succeeds on retry)
                response2 = await client.query_logs(query='{job="web-server"}')
                assert_successful_response(response2)
                
                # Call 3: Should fail after all retries exhausted
                response3 = await client.query_logs(query='{job="api-gateway"}')
                assert_error_response(response3, "Rate limit exceeded")
                
                # Call 4: Should succeed
                response4 = await client.search_logs(keywords=["error"])
                assert_successful_response(response4)
                
                # Test demonstrates mixed success/failure with retry behavior