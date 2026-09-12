"""
Exceptions for Scraper Client library.
"""


class ScraperClientError(Exception):
    """Base exception for all Scraper Client errors."""
    pass


class ScraperAPIError(ScraperClientError):
    """Raised when the scraper service returns an HTTP error."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"Scraper service returned HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class ScraperTimeoutError(ScraperClientError):
    """Raised when the client timed out communicating with scraper service."""
    pass
