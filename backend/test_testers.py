"""
Unit tests for connection testers.
Run with: python -m pytest backend/test_testers.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestSnowflakeTester:
    """Tests for Snowflake connection tester."""
    
    def test_missing_fields(self):
        """Test error when required fields are missing."""
        from testers.snowflake import test_connection
        
        result = test_connection({"account": "test"})
        
        assert result["success"] is False
        assert "Missing required fields" in result["message"]
        assert result["category"] == "connectivity"
    
    @patch("testers.snowflake.snowflake.connector.connect")
    def test_successful_connection(self, mock_connect):
        """Test successful Snowflake connection."""
        from testers.snowflake import test_connection
        
        mock_cursor = MagicMock()
        # version lookup, then the database-exists and schema-exists checks
        mock_cursor.fetchone.side_effect = [("3.0.0",), ("test_db",), ("PUBLIC",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = {
            "account": "test_account",
            "user": "test_user",
            "password": "test_password",
            "warehouse": "test_warehouse",
            "database": "test_db",
            "schema": "PUBLIC"
        }

        result = test_connection(config)

        assert result["success"] is True
        assert "Connected to Snowflake" in result["message"]
        assert result["details"]["database"] == "test_db"

    @patch("testers.snowflake.snowflake.connector.connect")
    def test_missing_schema_reports_not_found(self, mock_connect):
        """A schema that doesn't exist is an error, not a soft warning."""
        from testers.snowflake import test_connection

        mock_cursor = MagicMock()
        # version, database found, schema missing
        mock_cursor.fetchone.side_effect = [("3.0.0",), ("test_db",), None]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = test_connection({
            "account": "a", "user": "u", "password": "p",
            "warehouse": "w", "database": "test_db", "schema": "NOPE",
        })

        assert result["success"] is False
        assert result["category"] == "not_found"
    
    @patch("testers.snowflake.snowflake.connector.connect")
    def test_auth_failure(self, mock_connect):
        """Test authentication failure."""
        from testers.snowflake import test_connection
        from snowflake.connector import errors
        
        mock_connect.side_effect = errors.OperationalError("Invalid credentials")
        
        config = {
            "account": "test_account",
            "user": "test_user",
            "password": "wrong_password",
            "warehouse": "test_warehouse",
            "database": "test_db"
        }
        
        result = test_connection(config)
        
        assert result["success"] is False
        assert result["category"] == "auth"
    
    @patch("testers.snowflake.snowflake.connector.connect")
    def test_network_error(self, mock_connect):
        """Test network/connectivity error."""
        from testers.snowflake import test_connection
        from snowflake.connector import errors
        
        mock_connect.side_effect = errors.OperationalError("Network error")
        
        config = {
            "account": "test_account",
            "user": "test_user",
            "password": "test_password",
            "warehouse": "test_warehouse",
            "database": "test_db"
        }
        
        result = test_connection(config)
        
        assert result["success"] is False
        assert result["category"] in ("connectivity", "auth")


class TestPostgresTester:
    """Tests for PostgreSQL connection tester."""
    
    def test_missing_fields(self):
        """Test error when required fields are missing."""
        from testers.postgres import test_connection
        
        result = test_connection({"host": "localhost"})
        
        assert result["success"] is False
        assert "Missing required fields" in result["message"]
    
    @patch("testers.postgres.psycopg2.connect")
    def test_successful_connection(self, mock_connect):
        """Test successful PostgreSQL connection."""
        from testers.postgres import test_connection
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        config = {
            "host": "localhost",
            "database": "testdb",
            "user": "testuser",
            "password": "testpass"
        }
        
        result = test_connection(config)
        
        assert result["success"] is True
        assert "Connected to PostgreSQL" in result["message"]
    
    @patch("testers.postgres.psycopg2.connect")
    def test_auth_failure(self, mock_connect):
        """Test authentication failure."""
        from testers.postgres import test_connection
        from psycopg2 import OperationalError
        
        mock_connect.side_effect = OperationalError("password authentication failed")
        
        config = {
            "host": "localhost",
            "database": "testdb",
            "user": "testuser",
            "password": "wrongpass"
        }
        
        result = test_connection(config)
        
        assert result["success"] is False
        assert result["category"] == "auth"
    
    @patch("testers.postgres.psycopg2.connect")
    def test_host_unreachable(self, mock_connect):
        """Test connection refused error."""
        from testers.postgres import test_connection
        from psycopg2 import OperationalError
        
        mock_connect.side_effect = OperationalError("could not connect to server")
        
        config = {
            "host": "invalid.host.local",
            "database": "testdb",
            "user": "testuser",
            "password": "testpass"
        }
        
        result = test_connection(config)
        
        assert result["success"] is False
        assert result["category"] == "connectivity"


class TestS3Tester:
    """Tests for S3 connection tester."""
    
    def test_missing_bucket(self):
        """Test error when bucket is missing."""
        from testers.s3 import test_connection
        
        result = test_connection({})
        
        assert result["success"] is False
        assert "bucket" in result["message"].lower()
    
    @patch("testers.s3.boto3.client")
    def test_successful_connection(self, mock_client):
        """Test successful S3 connection."""
        from testers.s3 import test_connection
        
        mock_s3 = MagicMock()
        mock_s3.head_bucket.return_value = None
        mock_s3.list_objects_v2.return_value = {"Contents": []}
        mock_client.return_value = mock_s3
        
        config = {
            "bucket": "test-bucket",
            "access_key": "test_key",
            "secret_key": "test_secret",
            "region": "us-east-1"
        }
        
        result = test_connection(config)
        
        assert result["success"] is True
        assert "test-bucket" in result["message"]
    
    @patch("testers.s3.boto3.client")
    def test_bucket_not_found(self, mock_client):
        """Test bucket not found error."""
        from testers.s3 import test_connection
        from botocore.exceptions import ClientError
        
        mock_s3 = MagicMock()
        error_response = {"Error": {"Code": "404"}}
        mock_s3.head_bucket.side_effect = ClientError(error_response, "HeadBucket")
        mock_client.return_value = mock_s3
        
        config = {
            "bucket": "nonexistent-bucket",
            "access_key": "test_key",
            "secret_key": "test_secret"
        }
        
        result = test_connection(config)
        
        assert result["success"] is False
        assert result["category"] == "not_found"
    
    @patch("testers.s3.boto3.client")
    def test_access_denied(self, mock_client):
        """Test access denied error."""
        from testers.s3 import test_connection
        from botocore.exceptions import ClientError
        
        mock_s3 = MagicMock()
        error_response = {"Error": {"Code": "403"}}
        mock_s3.head_bucket.side_effect = ClientError(error_response, "HeadBucket")
        mock_client.return_value = mock_s3
        
        config = {
            "bucket": "private-bucket",
            "access_key": "bad_key",
            "secret_key": "bad_secret"
        }
        
        result = test_connection(config)
        
        assert result["success"] is False
        assert result["category"] == "auth"


class TestApiTester:
    """Tests for API connection tester."""
    
    def test_missing_base_url(self):
        """Test error when base_url is missing."""
        from testers.api import test_connection
        
        result = test_connection({"test_endpoint": "/health"})
        
        assert result["success"] is False
        assert "base_url" in result["message"].lower()
    
    @staticmethod
    def _mock_client(mock_client, status_code):
        """Wire a mocked httpx.Client context manager returning status_code."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = Mock(return_value=mock_ctx)
        mock_ctx.__exit__ = Mock(return_value=False)
        mock_ctx.request.return_value = mock_response
        mock_client.return_value = mock_ctx
        return mock_ctx

    @patch("testers.api.httpx.Client")
    def test_missing_test_endpoint_falls_back_to_base_url(self, mock_client):
        """An absent test_endpoint probes base_url directly rather than erroring."""
        from testers.api import test_connection

        mock_ctx = self._mock_client(mock_client, 200)

        result = test_connection({"base_url": "https://api.example.com"})

        assert result["success"] is True
        assert mock_ctx.request.call_args[0][1] == "https://api.example.com"

    @patch("testers.api.httpx.Client")
    def test_test_endpoint_equal_to_base_url_is_not_doubled(self, mock_client):
        """The frontend defaults test_endpoint to base_url; don't concatenate them."""
        from testers.api import test_connection

        mock_ctx = self._mock_client(mock_client, 200)

        result = test_connection({
            "base_url": "https://api.example.com/search",
            "test_endpoint": "https://api.example.com/search",
        })

        assert result["success"] is True
        assert mock_ctx.request.call_args[0][1] == "https://api.example.com/search"

    @patch("testers.api.httpx.Client")
    def test_successful_connection(self, mock_client):
        """Test successful API connection."""
        from testers.api import test_connection

        mock_ctx = self._mock_client(mock_client, 200)

        config = {
            "base_url": "https://api.example.com",
            "test_endpoint": "/health",
            "auth_type": "none"
        }

        result = test_connection(config)

        assert result["success"] is True
        assert result["category"] == "success"
        assert mock_ctx.request.call_args[0][1] == "https://api.example.com/health"

    @patch("testers.api.httpx.Client")
    def test_auth_failure_401(self, mock_client):
        """Test 401 authentication failure."""
        from testers.api import test_connection

        self._mock_client(mock_client, 401)

        config = {
            "base_url": "https://api.example.com",
            "test_endpoint": "/health",
            "auth_type": "bearer",
            "bearer_token": "invalid_token"
        }

        result = test_connection(config)

        assert result["success"] is False
        assert result["category"] == "auth"

    @patch("testers.api.httpx.Client")
    def test_server_error_500(self, mock_client):
        """Test 500 server error."""
        from testers.api import test_connection

        self._mock_client(mock_client, 500)

        config = {
            "base_url": "https://api.example.com",
            "test_endpoint": "/health",
            "auth_type": "none"
        }

        result = test_connection(config)

        assert result["success"] is False
        assert result["category"] == "server_error"

    @patch("testers.api.httpx.Client")
    def test_unknown_auth_type_is_treated_as_no_auth(self, mock_client):
        """An unrecognised auth_type adds no credentials rather than erroring."""
        from testers.api import test_connection

        mock_ctx = self._mock_client(mock_client, 200)

        config = {
            "base_url": "https://api.example.com",
            "test_endpoint": "/health",
            "auth_type": "invalid_auth"
        }

        result = test_connection(config)

        assert result["success"] is True
        assert mock_ctx.request.call_args.kwargs["headers"] == {}
        assert mock_client.call_args.kwargs["auth"] is None


class TestLocalFolderTester:
    """Tests for local folder validation in main.py."""
    
    def test_local_folder_valid(self):
        """Test valid local folder path."""
        import tempfile
        import os
        from fastapi.testclient import TestClient
        from backend.main_test import app
        
        with tempfile.TemporaryDirectory() as tmpdir:
            client = TestClient(app)
            response = client.post("/connectors/test", json={
                "source_type": "local_folder",
                "config": {"base_path": tmpdir}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    def test_local_folder_invalid(self):
        """Test invalid local folder path."""
        from fastapi.testclient import TestClient
        from backend.main_test import app
        
        client = TestClient(app)
        response = client.post("/connectors/test", json={
            "source_type": "local_folder",
            "config": {"base_path": "/nonexistent/path/that/does/not/exist"}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["category"] == "not_found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])