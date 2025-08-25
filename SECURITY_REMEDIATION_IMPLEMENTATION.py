#!/usr/bin/env python3
"""
Security Remediation Implementation for V2 Batch Processing System
This file contains secure code implementations to address the vulnerabilities
identified in the security audit report.

Author: Security Team
Date: 2025-08-25
"""

import os
import re
import json
import secrets
import hashlib
import asyncio
import logging
import resource
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from html import escape

from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
from cryptography.fernet import Fernet
import bleach

logger = logging.getLogger(__name__)

# ============================================================================
# 1. SECURE AUTHENTICATION IMPLEMENTATION
# ============================================================================

class SecureAuthenticationSystem:
    """
    Production-ready authentication system with:
    - Token hashing
    - Rate limiting
    - Brute force protection
    - Audit logging
    """
    
    def __init__(self):
        # Token management
        self._load_secure_token()
        
        # Rate limiting
        self.failed_attempts = {}
        self.blocked_ips = {}
        self.rate_limit_window = 300  # 5 minutes
        self.max_attempts = 5
        self.block_duration = 3600  # 1 hour
        
        # Audit logging
        self.audit_logger = self._setup_audit_logger()
        
    def _load_secure_token(self):
        """Load and validate API token securely"""
        token = os.getenv("RAG_API_TOKEN")
        
        if not token:
            raise ValueError(
                "SECURITY ERROR: RAG_API_TOKEN must be set. "
                "Generate with: openssl rand -hex 32"
            )
        
        # Validate token strength
        if len(token) < 32:
            raise ValueError("SECURITY ERROR: Token must be at least 32 characters")
        
        # Store hashed version
        self.token_hash = hashlib.sha256(token.encode()).hexdigest()
        
    def _setup_audit_logger(self):
        """Setup dedicated security audit logger"""
        audit_logger = logging.getLogger("security.audit")
        audit_logger.setLevel(logging.INFO)
        
        # Create secure log file with restricted permissions
        log_file = Path("/var/log/rag-security-audit.log")
        if not log_file.parent.exists():
            log_file.parent.mkdir(parents=True, mode=0o700)
            
        handler = logging.FileHandler(log_file, mode='a')
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        audit_logger.addHandler(handler)
        
        return audit_logger
    
    def _is_blocked(self, client_ip: str) -> bool:
        """Check if IP is blocked"""
        if client_ip in self.blocked_ips:
            block_time = self.blocked_ips[client_ip]
            if datetime.now() < block_time:
                return True
            else:
                del self.blocked_ips[client_ip]
        return False
    
    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if IP has exceeded rate limit"""
        if client_ip not in self.failed_attempts:
            return False
            
        attempts = self.failed_attempts[client_ip]
        recent_attempts = [
            attempt for attempt in attempts 
            if datetime.now() - attempt < timedelta(seconds=self.rate_limit_window)
        ]
        
        self.failed_attempts[client_ip] = recent_attempts
        
        if len(recent_attempts) >= self.max_attempts:
            # Block the IP
            self.blocked_ips[client_ip] = datetime.now() + timedelta(seconds=self.block_duration)
            self.audit_logger.warning(f"IP blocked due to rate limit: {client_ip}")
            return True
            
        return False
    
    def _record_failed_attempt(self, client_ip: str):
        """Record failed authentication attempt"""
        if client_ip not in self.failed_attempts:
            self.failed_attempts[client_ip] = []
        
        self.failed_attempts[client_ip].append(datetime.now())
        self.audit_logger.warning(f"Failed authentication from: {client_ip}")
    
    async def verify_token(self, 
                          request: Request,
                          credentials: HTTPAuthorizationCredentials) -> str:
        """Verify token with comprehensive security checks"""
        client_ip = request.client.host if request.client else "unknown"
        
        # Check if IP is blocked
        if self._is_blocked(client_ip):
            self.audit_logger.error(f"Blocked IP attempted access: {client_ip}")
            raise HTTPException(
                status_code=403, 
                detail="Access temporarily blocked due to multiple failed attempts"
            )
        
        # Check rate limiting
        if self._is_rate_limited(client_ip):
            raise HTTPException(
                status_code=429, 
                detail="Too many authentication attempts. Please try again later."
            )
        
        # Validate credentials exist
        if not credentials or not credentials.credentials:
            self._record_failed_attempt(client_ip)
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Constant-time token comparison
        provided_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        
        if not secrets.compare_digest(provided_hash, self.token_hash):
            self._record_failed_attempt(client_ip)
            await asyncio.sleep(1)  # Slow down brute force attempts
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        # Log successful authentication
        self.audit_logger.info(f"Successful authentication from: {client_ip}")
        
        return f"authenticated_user_{client_ip}"

# ============================================================================
# 2. SECURE INPUT VALIDATION
# ============================================================================

class SecureInputValidator:
    """Comprehensive input validation system"""
    
    # Validation patterns
    UUID_PATTERN = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,254}$')
    
    @classmethod
    def validate_document_id(cls, doc_id: str) -> str:
        """Validate document ID format"""
        if not cls.UUID_PATTERN.match(doc_id):
            raise ValueError(f"Invalid document ID format: {doc_id}")
        return doc_id
    
    @classmethod
    def validate_filename(cls, filename: str) -> str:
        """Validate and sanitize filename"""
        # Remove any path components
        filename = os.path.basename(filename)
        
        # Check for dangerous patterns
        dangerous_patterns = ['..', '~', '$', '|', ';', '&', '>', '<', '\x00']
        if any(pattern in filename for pattern in dangerous_patterns):
            raise ValueError(f"Dangerous pattern in filename: {filename}")
        
        # Validate against safe pattern
        if not cls.SAFE_FILENAME_PATTERN.match(filename):
            raise ValueError(f"Invalid filename format: {filename}")
        
        return filename
    
    @classmethod
    def validate_file_path(cls, file_path: str, base_dir: str) -> str:
        """Validate file path against traversal attacks"""
        try:
            # Resolve paths
            requested_path = Path(file_path).resolve()
            base_path = Path(base_dir).resolve()
            
            # Ensure file is within allowed directory
            if not str(requested_path).startswith(str(base_path)):
                raise ValueError("Path traversal attempt detected")
            
            # Additional validation
            if not requested_path.exists():
                raise ValueError("File does not exist")
            
            if not requested_path.is_file():
                raise ValueError("Path is not a file")
            
            return str(requested_path)
            
        except Exception as e:
            logger.error(f"Path validation failed: {e}")
            raise ValueError(f"Invalid file path: {file_path}")
    
    @classmethod
    def sanitize_user_input(cls, data: Any) -> Any:
        """Recursively sanitize user input"""
        if isinstance(data, str):
            # Remove HTML/script tags
            sanitized = bleach.clean(data, tags=[], strip=True)
            # Escape special characters
            sanitized = escape(sanitized)
            # Limit length
            return sanitized[:1000]
            
        elif isinstance(data, dict):
            return {key: cls.sanitize_user_input(value) for key, value in data.items()}
            
        elif isinstance(data, list):
            return [cls.sanitize_user_input(item) for item in data]
            
        else:
            return data

# Pydantic models with built-in validation
class SecureBatchProcessRequest(BaseModel):
    """Secure batch processing request with validation"""
    
    document_ids: List[str] = Field(..., max_items=100, min_items=1)
    parser: str = Field(default="mineru", regex=r'^(mineru|docling)$')
    parse_method: str = Field(default="auto", regex=r'^(auto|ocr|txt)$')
    max_workers: Optional[int] = Field(default=None, ge=1, le=10)
    
    @validator('document_ids', each_item=True)
    def validate_document_ids(cls, doc_id):
        return SecureInputValidator.validate_document_id(doc_id)

# ============================================================================
# 3. SECURE RESOURCE MANAGEMENT
# ============================================================================

class SecureResourceManager:
    """Resource management with DoS protection"""
    
    def __init__(self):
        # Set resource limits
        self._set_memory_limits()
        self._set_cpu_limits()
        
        # Processing constraints
        self.max_concurrent_operations = 5
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.processing_timeout = 300  # 5 minutes
        
        # Thread pool with bounds
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_concurrent_operations,
            thread_name_prefix="secure-rag-worker"
        )
        
        # Semaphore for additional control
        self.processing_semaphore = asyncio.Semaphore(self.max_concurrent_operations)
        
    def _set_memory_limits(self):
        """Set memory limits to prevent DoS"""
        try:
            # Limit to 2GB of memory
            max_memory = 2 * 1024 * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory))
        except Exception as e:
            logger.warning(f"Could not set memory limit: {e}")
    
    def _set_cpu_limits(self):
        """Set CPU time limits"""
        try:
            # Limit CPU time to 1 hour
            resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))
        except Exception as e:
            logger.warning(f"Could not set CPU limit: {e}")
    
    async def process_with_limits(self, func, *args, **kwargs):
        """Process with resource limits and timeout"""
        async with self.processing_semaphore:
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._execute_in_thread(func, *args, **kwargs),
                    timeout=self.processing_timeout
                )
                return result
                
            except asyncio.TimeoutError:
                logger.error("Processing timeout exceeded")
                raise HTTPException(status_code=408, detail="Processing timeout")
                
            except MemoryError:
                logger.error("Memory limit exceeded")
                raise HTTPException(status_code=507, detail="Insufficient storage")
                
            except Exception as e:
                logger.error(f"Processing error: {e}")
                raise HTTPException(status_code=500, detail="Processing failed")
    
    async def _execute_in_thread(self, func, *args, **kwargs):
        """Execute function in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)
    
    def validate_file_size(self, file_path: str) -> bool:
        """Validate file size is within limits"""
        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            raise ValueError(f"File size {file_size} exceeds limit {self.max_file_size}")
        return True

# ============================================================================
# 4. SECURE DATA STORAGE
# ============================================================================

class SecureDataStorage:
    """Encrypted data storage with integrity protection"""
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        # Initialize encryption
        if encryption_key:
            self.cipher = Fernet(encryption_key)
        else:
            self.cipher = Fernet(Fernet.generate_key())
        
        # Thread-safe storage
        self._data = {}
        self._locks = {}
        self._global_lock = asyncio.Lock()
        
        # Integrity tracking
        self._checksums = {}
    
    @asynccontextmanager
    async def get_lock(self, key: str):
        """Get or create a lock for a specific key"""
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            lock = self._locks[key]
        
        async with lock:
            yield
    
    async def store(self, key: str, value: dict) -> None:
        """Store encrypted data with integrity check"""
        async with self.get_lock(key):
            # Serialize and encrypt
            serialized = json.dumps(value).encode()
            encrypted = self.cipher.encrypt(serialized)
            
            # Calculate checksum
            checksum = hashlib.sha256(encrypted).hexdigest()
            
            # Store
            self._data[key] = encrypted
            self._checksums[key] = checksum
    
    async def retrieve(self, key: str) -> Optional[dict]:
        """Retrieve and verify data"""
        async with self.get_lock(key):
            if key not in self._data:
                return None
            
            encrypted = self._data[key]
            
            # Verify integrity
            checksum = hashlib.sha256(encrypted).hexdigest()
            if checksum != self._checksums[key]:
                logger.error(f"Data integrity check failed for key: {key}")
                raise ValueError("Data integrity violation detected")
            
            # Decrypt
            try:
                decrypted = self.cipher.decrypt(encrypted)
                return json.loads(decrypted.decode())
            except Exception as e:
                logger.error(f"Decryption failed: {e}")
                raise ValueError("Data decryption failed")
    
    async def delete(self, key: str) -> bool:
        """Securely delete data"""
        async with self.get_lock(key):
            if key in self._data:
                # Overwrite with random data before deletion
                self._data[key] = os.urandom(len(self._data[key]))
                del self._data[key]
                del self._checksums[key]
                return True
            return False

# ============================================================================
# 5. SECURE ERROR HANDLING
# ============================================================================

class SecureErrorHandler:
    """Error handling without information disclosure"""
    
    # Error mapping for safe responses
    ERROR_MAPPING = {
        FileNotFoundError: ("Resource not found", 404),
        PermissionError: ("Access denied", 403),
        ValueError: ("Invalid request", 400),
        TimeoutError: ("Request timeout", 408),
        MemoryError: ("Insufficient resources", 507),
    }
    
    @classmethod
    def handle_error(cls, error: Exception, request_id: str) -> dict:
        """Handle error securely without exposing internals"""
        # Log full details internally
        logger.error(f"Request {request_id}: {type(error).__name__}: {str(error)}")
        
        # Get safe error message
        message, status_code = cls.ERROR_MAPPING.get(
            type(error), 
            ("An error occurred", 500)
        )
        
        # Return sanitized response
        return {
            "error": message,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "status_code": status_code
        }
    
    @classmethod
    def log_security_event(cls, event_type: str, details: dict):
        """Log security-relevant events"""
        security_logger = logging.getLogger("security.events")
        security_logger.warning(json.dumps({
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }))

# ============================================================================
# 6. SECURE LOGGING
# ============================================================================

class SecureLogger:
    """Logger that sanitizes sensitive information"""
    
    def __init__(self, logger):
        self.logger = logger
        self.sensitive_patterns = [
            (r'/home/[^/]+/', '/home/****/'),
            (r'/Users/[^/]+/', '/Users/****/'),
            (r'token=[^&\s]+', 'token=****'),
            (r'password=[^&\s]+', 'password=****'),
            (r'api[_-]?key=[^&\s]+', 'api_key=****'),
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '****@****.***'),
            (r'\b\d{4,}\b', '****'),  # Long numbers
            (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '***.***.***.***'),  # IP addresses
        ]
    
    def sanitize(self, message: str) -> str:
        """Remove sensitive information from messages"""
        if not isinstance(message, str):
            message = str(message)
            
        for pattern, replacement in self.sensitive_patterns:
            message = re.sub(pattern, replacement, message)
        
        return message
    
    def debug(self, message: str):
        self.logger.debug(self.sanitize(message))
    
    def info(self, message: str):
        self.logger.info(self.sanitize(message))
    
    def warning(self, message: str):
        self.logger.warning(self.sanitize(message))
    
    def error(self, message: str):
        self.logger.error(self.sanitize(message))

# ============================================================================
# 7. SECURITY MIDDLEWARE
# ============================================================================

async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # Remove server information
    response.headers.pop("server", None)
    response.headers.pop("x-powered-by", None)
    
    return response

async def request_validation_middleware(request: Request, call_next):
    """Validate and sanitize incoming requests"""
    # Check content type for POST/PUT requests
    if request.method in ["POST", "PUT", "PATCH"]:
        content_type = request.headers.get("content-type", "")
        
        # Only accept JSON
        if not content_type.startswith("application/json") and not content_type.startswith("multipart/form-data"):
            return HTTPException(status_code=415, detail="Unsupported media type")
        
        # Size limit check
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
            return HTTPException(status_code=413, detail="Request entity too large")
    
    response = await call_next(request)
    return response

# ============================================================================
# 8. USAGE EXAMPLE
# ============================================================================

async def secure_batch_processing_example():
    """Example of using secure components together"""
    
    # Initialize secure components
    auth_system = SecureAuthenticationSystem()
    resource_manager = SecureResourceManager()
    data_storage = SecureDataStorage()
    secure_logger = SecureLogger(logger)
    
    # Example endpoint with all security measures
    async def process_batch_securely(
        request: SecureBatchProcessRequest,
        current_user: str,
        client_ip: str
    ):
        request_id = str(secrets.token_hex(16))
        
        try:
            # Log the operation
            secure_logger.info(f"Batch processing started by {current_user} from {client_ip}")
            
            # Validate inputs
            validated_ids = [
                SecureInputValidator.validate_document_id(doc_id) 
                for doc_id in request.document_ids
            ]
            
            # Store request securely
            await data_storage.store(request_id, {
                "user": current_user,
                "document_ids": validated_ids,
                "timestamp": datetime.now().isoformat()
            })
            
            # Process with resource limits
            result = await resource_manager.process_with_limits(
                process_documents,
                validated_ids,
                request.parser,
                request.parse_method
            )
            
            # Return sanitized result
            return {
                "request_id": request_id,
                "status": "success",
                "documents_processed": len(validated_ids)
            }
            
        except Exception as e:
            # Handle error securely
            error_response = SecureErrorHandler.handle_error(e, request_id)
            SecureErrorHandler.log_security_event("batch_processing_error", {
                "request_id": request_id,
                "user": current_user,
                "error_type": type(e).__name__
            })
            raise HTTPException(
                status_code=error_response["status_code"],
                detail=error_response
            )

def process_documents(doc_ids, parser, method):
    """Placeholder for actual document processing"""
    # Actual implementation would go here
    return {"processed": len(doc_ids)}

# ============================================================================
# 9. SECURITY CONFIGURATION
# ============================================================================

class SecurityConfig:
    """Central security configuration"""
    
    # Environment validation
    REQUIRED_ENV_VARS = [
        "RAG_API_TOKEN",
        "ENCRYPTION_KEY",
        "LOG_LEVEL"
    ]
    
    @classmethod
    def validate_environment(cls):
        """Validate security environment variables"""
        missing = []
        for var in cls.REQUIRED_ENV_VARS:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
    
    @classmethod
    def get_secure_config(cls) -> dict:
        """Get validated security configuration"""
        cls.validate_environment()
        
        return {
            "auth_enabled": True,
            "rate_limiting": True,
            "encryption_enabled": True,
            "max_request_size": 10 * 1024 * 1024,  # 10MB
            "session_timeout": 3600,  # 1 hour
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "audit_logging": True,
            "secure_headers": True
        }

if __name__ == "__main__":
    # Example initialization
    print("Security Remediation Implementation Module")
    print("=" * 50)
    print("This module provides secure implementations for:")
    print("1. Authentication with rate limiting")
    print("2. Input validation and sanitization")
    print("3. Resource management with DoS protection")
    print("4. Encrypted data storage")
    print("5. Secure error handling")
    print("6. Sanitized logging")
    print("7. Security middleware")
    print("\nRefer to the security audit report for integration instructions.")