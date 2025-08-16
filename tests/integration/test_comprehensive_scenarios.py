"""Comprehensive integration test scenarios."""

import asyncio
from unittest.mock import AsyncMock, patch, Mock
import pytest

from app.config import LokiConfig
from app.server import LokiMCPServer
from app.loki_client import (
    LokiConnectionError, 
    LokiAuthenticationError, 
    LokiQueryError,
    LokiRateLimitError
)
from ..fixtures.sample_logs import (
    SAMPLE_QUERY_RANGE_RESPONSE,
    SAMPLE_QUERY_INSTANT_RESPONSE,
    SAMPLE_LABELS_RESPONSE,
    SAMPLE_LABEL_VALUES_RESPONSE,
    SAMPLE_ERROR_RESPONSES,
    TIME_RANGES
)
from ..utils.mcp_client import (
    MCPTestClient,
    assert_tool_response_format,
    assert_successful_response,
    assert_error_response,
    extract_response_text
)


class TestComprehensiveScenarios:
    """Comprehensive integration test scenarios."""
    
    @pytest.fixture
    def config(self):
        """Test configuration."""
        return LokiConfig(
            url="http://localhost:3100",
            timeout=30,
            max_retries=2
        )
    
    @pytest.mark.asyncio
    async def test_full_mcp_protocol_compliance(self, config):
        """Test full MCP protocol compliance."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_LABELS_RESPONSE
            
            # Test server initialization
            server = LokiMCPServer(config)
            assert server.config == config
            assert server.server is not None
            
            # Test tool listing
            async with MCPTestClient(config) as client:
                tools = await client.list_tools()
                
                assert len(tools) == 3
                tool_names = [tool.name for tool in tools]
                assert "query_logs" in tool_names
                assert "search_logs" in tool_names
                assert "get_labels" in tool_names
                
                # Verify tool schemas
                for tool in tools:
                    assert hasattr(tool, 'name')
                    assert hasattr(tool, 'description')
                    assert hasattr(tool, 'inputSchema')
                    assert isinstance(tool.inputSchema, dict)
                    assert tool.inputSchema.get("type") == "object"
    
    @pytest.mark.asyncio
    async def test_authentication_error_scenarios(self, config):
        """Test various authentication error scenarios."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.side_effect = LokiAuthenticationError("Authentication failed")
            
            async with MCPTestClient(config) as client:
                # Test authentication failure in query_logs
                response = await client.query_logs(query='{job="web-server"}')
                assert_error_response(response, "Authentication failed")
                
                # Test authentication failure in search_logs
                response = await client.search_logs(keywords=["error"])
                assert_error_response(response, "Authentication failed")
                
                # Test authentication failure in get_labels
                response = await client.get_labels()
                assert_error_response(response, "Authentication failed")
    
    @pytest.mark.asyncio
    async def test_connection_error_scenarios(self, config):
        """Test various connection error scenarios."""
        connection_errors = [
            LokiConnectionError("Connection refused"),
            LokiConnectionError("Timeout"),
            LokiConnectionError("DNS resolution failed"),
            LokiConnectionError("Network unreachable")
        ]
        
        for error in connection_errors:
            with patch('app.loki_client.LokiClient._make_request') as mock_request:
                mock_request.side_effect = error
                
                async with MCPTestClient(config) as client:
                    response = await client.query_logs(query='{job="web-server"}')
                    assert_error_response(response)
                    
                    response_text = extract_response_text(response)
                    assert str(error) in response_text
    
    @pytest.mark.asyncio
    async def test_query_error_scenarios(self, config):
        """Test various query error scenarios."""
        query_errors = [
            ('Invalid syntax', '{job="web-server"!}'),
            ('Missing quotes', '{job=web-server}'),
            ('Invalid operator', '{job~="web-server"}'),
            ('Empty query', ''),
            ('Malformed regex', '{job="web-server"} |~ "[invalid"')
        ]
        
        for error_desc, invalid_query in query_errors:
            with patch('app.loki_client.LokiClient._make_request') as mock_request:
                mock_request.side_effect = LokiQueryError(f"Query error: {error_desc}")
                
                async with MCPTestClient(config) as client:
                    response = await client.query_logs(query=invalid_query)
                    assert_error_response(response, error_desc)
    
    @pytest.mark.asyncio
    async def test_rate_limiting_scenarios(self, config):
        """Test rate limiting scenarios."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.side_effect = LokiRateLimitError("Rate limit exceeded")
            
            async with MCPTestClient(config) as client:
                response = await client.query_logs(query='{job="web-server"}')
                assert_error_response(response, "Rate limit exceeded")
                
                response_text = extract_response_text(response)
                assert "reducing the frequency of requests" in response_text
    
    @pytest.mark.asyncio
    async def test_parameter_validation_scenarios(self, config):
        """Test parameter validation scenarios."""
        async with MCPTestClient(config) as client:
            # Test missing required parameters
            response = await client.call_tool("query_logs", {})
            assert_error_response(response)
            
            # Test invalid parameter types
            response = await client.call_tool("query_logs", {"query": 123})
            assert_error_response(response)
            
            # Test invalid parameter values
            response = await client.call_tool("query_logs", {"query": ""})
            assert_error_response(response)
            
            # Test invalid keywords for search
            response = await client.call_tool("search_logs", {"keywords": []})
            assert_error_response(response)
            
            # Test invalid limit values
            response = await client.call_tool("query_logs", {
                "query": '{job="web-server"}',
                "limit": -1
            })
            assert_error_response(response)
    
    @pytest.mark.asyncio
    async def test_time_range_scenarios(self, config):
        """Test various time range scenarios."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            time_scenarios = [
                # Valid time ranges
                ("RFC3339 format", "2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"),
                ("Unix timestamp", "1704067200", "1704070800"),
                ("Relative time", "now-1h", "now"),
                
                # Edge cases
                ("Same start/end", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
                ("Very short range", "2024-01-01T00:00:00Z", "2024-01-01T00:00:01Z"),
            ]
            
            async with MCPTestClient(config) as client:
                for desc, start, end in time_scenarios:
                    response = await client.query_logs(
                        query='{job="web-server"}',
                        start=start,
                        end=end
                    )
                    assert_successful_response(response)
    
    @pytest.mark.asyncio
    async def test_complex_query_scenarios(self, config):
        """Test complex LogQL query scenarios."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            complex_queries = [
                # Label filtering
                '{job="web-server", level="error"}',
                '{job=~"web-.*", level!="debug"}',
                
                # Line filtering
                '{job="web-server"} |= "error"',
                '{job="web-server"} |~ "user.*failed"',
                '{job="web-server"} != "debug"',
                
                # JSON parsing
                '{job="api"} | json | status_code="500"',
                '{job="api"} | json | duration > 1000',
                
                # Regex and formatting
                '{job="web-server"} | regexp "(?P<method>\\w+) (?P<path>/\\S+)"',
                '{job="web-server"} | line_format "{{.timestamp}} {{.message}}"',
                
                # Metric queries
                'rate({job="web-server"}[5m])',
                'count_over_time({job="web-server"}[1h])',
                'sum(rate({job="web-server"}[5m])) by (level)',
                
                # Complex combinations
                'sum(rate({job=~"web-.*"} |= "error" | json | status_code="500" [5m])) by (instance)'
            ]
            
            async with MCPTestClient(config) as client:
                for query in complex_queries:
                    response = await client.query_logs(
                        query=query,
                        start=TIME_RANGES["last_hour"]["start"],
                        end=TIME_RANGES["last_hour"]["end"]
                    )
                    assert_tool_response_format(response)
                    # Complex queries should not error out
                    response_text = extract_response_text(response)
                    assert not response_text.startswith("Error:")
    
    @pytest.mark.asyncio
    async def test_search_keyword_scenarios(self, config):
        """Test various search keyword scenarios."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            keyword_scenarios = [
                # Single keyword
                (["error"], "Single keyword search"),
                
                # Multiple keywords
                (["error", "failed", "timeout"], "Multiple keyword search"),
                
                # Special characters
                (["error:", "failed!", "timeout?"], "Special characters"),
                
                # Case sensitivity
                (["ERROR", "Failed", "TIMEOUT"], "Mixed case"),
                
                # Numbers and symbols
                (["500", "404", "timeout=30"], "Numbers and symbols"),
                
                # Long keywords
                (["very_long_keyword_that_might_appear_in_logs"], "Long keywords")
            ]
            
            async with MCPTestClient(config) as client:
                for keywords, description in keyword_scenarios:
                    response = await client.search_logs(
                        keywords=keywords,
                        start=TIME_RANGES["last_hour"]["start"],
                        end=TIME_RANGES["last_hour"]["end"]
                    )
                    assert_successful_response(response)
    
    @pytest.mark.asyncio
    async def test_label_operation_scenarios(self, config):
        """Test various label operation scenarios."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            # Different responses for different label operations
            def mock_response_side_effect(*args, **kwargs):
                endpoint = args[1]
                if endpoint == "/loki/api/v1/labels":
                    return SAMPLE_LABELS_RESPONSE
                elif "/values" in endpoint:
                    return SAMPLE_LABEL_VALUES_RESPONSE
                else:
                    return {"data": []}
            
            mock_request.side_effect = mock_response_side_effect
            
            async with MCPTestClient(config) as client:
                # Test getting all labels
                response = await client.get_labels()
                assert_successful_response(response)
                response_text = extract_response_text(response)
                assert "Found 4 label names" in response_text
                
                # Test getting values for specific labels
                common_labels = ["job", "level", "instance", "service", "environment"]
                for label in common_labels:
                    response = await client.get_labels(label_name=label)
                    assert_successful_response(response)
                    response_text = extract_response_text(response)
                    assert f"values for label '{label}'" in response_text
    
    @pytest.mark.asyncio
    async def test_limit_and_pagination_scenarios(self, config):
        """Test limit and pagination scenarios."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            limit_scenarios = [
                (1, "Minimum limit"),
                (10, "Small limit"),
                (100, "Medium limit"),
                (1000, "Large limit"),
                (10000, "Very large limit")
            ]
            
            async with MCPTestClient(config) as client:
                for limit, description in limit_scenarios:
                    response = await client.query_logs(
                        query='{job="web-server"}',
                        start=TIME_RANGES["last_hour"]["start"],
                        end=TIME_RANGES["last_hour"]["end"],
                        limit=limit
                    )
                    assert_successful_response(response)
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_resilience(self, config):
        """Test error recovery and resilience scenarios."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            # Simulate intermittent failures
            call_count = 0
            def intermittent_failure(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count % 3 == 0:  # Every 3rd call fails
                    raise LokiConnectionError("Intermittent failure")
                return SAMPLE_QUERY_RANGE_RESPONSE
            
            mock_request.side_effect = intermittent_failure
            
            async with MCPTestClient(config) as client:
                # Make multiple calls, some should fail, others succeed
                results = []
                for i in range(10):
                    response = await client.query_logs(query=f'{{job="service-{i}"}}')
                    results.append(response)
                
                # Should have mix of successes and failures
                successful = [r for r in results if not extract_response_text(r).startswith("Error:")]
                failed = [r for r in results if extract_response_text(r).startswith("Error:")]
                
                assert len(successful) > 0
                assert len(failed) > 0
                assert len(successful) + len(failed) == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, config):
        """Test concurrent mixed operations."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            def mixed_response_side_effect(*args, **kwargs):
                endpoint = args[1]
                if "labels" in endpoint:
                    return SAMPLE_LABELS_RESPONSE
                else:
                    return SAMPLE_QUERY_RANGE_RESPONSE
            
            mock_request.side_effect = mixed_response_side_effect
            
            # Create mixed concurrent operations
            operations = []
            for i in range(20):
                if i % 3 == 0:
                    operations.append(("get_labels", {}))
                elif i % 3 == 1:
                    operations.append(("query_logs", {"query": f'{{job="service-{i}"}}'}))
                else:
                    operations.append(("search_logs", {"keywords": ["error"]}))
            
            async with MCPTestClient(config) as client:
                # Execute all operations concurrently
                tasks = []
                for op_name, args in operations:
                    if op_name == "get_labels":
                        task = client.get_labels(**args)
                    elif op_name == "query_logs":
                        task = client.query_logs(**args)
                    else:
                        task = client.search_logs(**args)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # All operations should succeed
                for result in results:
                    assert not isinstance(result, Exception)
                    assert_tool_response_format(result)
                    assert_successful_response(result)
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_scenarios(self, config):
        """Test resource cleanup scenarios."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            # Test multiple client sessions
            for i in range(5):
                async with MCPTestClient(config) as client:
                    response = await client.query_logs(query=f'{{job="service-{i}"}}')
                    assert_successful_response(response)
                # Client should be properly cleaned up after context exit
            
            # Test exception during client usage
            try:
                async with MCPTestClient(config) as client:
                    await client.query_logs(query='{job="web-server"}')
                    raise Exception("Simulated error")
            except Exception:
                pass  # Expected
            
            # Resources should still be cleaned up properly
    
    @pytest.mark.asyncio
    async def test_configuration_scenarios(self, config):
        """Test various configuration scenarios."""
        configs = [
            # Basic configuration
            LokiConfig(url="http://localhost:3100"),
            
            # With authentication
            LokiConfig(
                url="http://localhost:3100",
                username="admin",
                password="secret"
            ),
            
            # With bearer token
            LokiConfig(
                url="http://localhost:3100",
                bearer_token="test-token"
            ),
            
            # With custom timeouts and retries
            LokiConfig(
                url="http://localhost:3100",
                timeout=60,
                max_retries=5
            ),
            
            # With rate limiting
            LokiConfig(
                url="http://localhost:3100",
                rate_limit_requests=50,
                rate_limit_period=30
            )
        ]
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_LABELS_RESPONSE
            
            for test_config in configs:
                async with MCPTestClient(test_config) as client:
                    response = await client.get_labels()
                    assert_successful_response(response)