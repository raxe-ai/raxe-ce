"""Tests for get_remote_file_size function."""

from unittest.mock import MagicMock, patch

from raxe.infrastructure.ml.model_downloader import get_remote_file_size


class TestGetRemoteFileSize:
    """Tests for get_remote_file_size function."""

    def test_returns_content_length_on_success(self) -> None:
        """Should return Content-Length header value as int."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "12345678"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "raxe.infrastructure.ml.model_downloader.urlopen",
            return_value=mock_response,
        ):
            result = get_remote_file_size("https://example.com/file.tar.gz")

        assert result == 12345678
        mock_response.headers.get.assert_called_once_with("Content-Length")

    def test_returns_none_when_no_content_length(self) -> None:
        """Should return None when Content-Length header is missing."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = None
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "raxe.infrastructure.ml.model_downloader.urlopen",
            return_value=mock_response,
        ):
            result = get_remote_file_size("https://example.com/file.tar.gz")

        assert result is None

    def test_returns_none_on_network_error(self) -> None:
        """Should return None on network errors (not raise exception)."""
        with patch(
            "raxe.infrastructure.ml.model_downloader.urlopen",
            side_effect=Exception("Network error"),
        ):
            result = get_remote_file_size("https://example.com/file.tar.gz")

        assert result is None

    def test_uses_head_request(self) -> None:
        """Should use HEAD method for efficiency."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "1000"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "raxe.infrastructure.ml.model_downloader.urlopen",
            return_value=mock_response,
        ) as mock_urlopen:
            get_remote_file_size("https://example.com/file.tar.gz")

        # Verify HEAD request was made
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.get_method() == "HEAD"

    def test_uses_custom_timeout(self) -> None:
        """Should use provided timeout value."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "1000"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "raxe.infrastructure.ml.model_downloader.urlopen",
            return_value=mock_response,
        ) as mock_urlopen:
            get_remote_file_size("https://example.com/file.tar.gz", timeout=5)

        # Verify timeout was passed
        call_args = mock_urlopen.call_args
        assert call_args[1]["timeout"] == 5
