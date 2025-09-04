# RAG-Anything API Security Audit Report

## Executive Summary

This comprehensive security audit reveals **critical security vulnerabilities** in the RAG-Anything API that must be addressed immediately. The system currently operates with **no authentication by default** and has **multiple high-severity security issues** that expose it to various attack vectors.

**Risk Level: 🔴 CRITICAL**

### Key Risk Areas
1. **No Authentication/Authorization** (CRITICAL)
2. **Overly Permissive CORS** (CRITICAL)  
3. **Insufficient Input Validation** (CRITICAL)
4. **Command Injection Vulnerabilities** (HIGH)
5. **Information Disclosure** (MEDIUM)

---

## 1. Authentication & Authorization Assessment

### 🔴 CRITICAL: No Authentication Implemented

**Issue:** The main API server operates without authentication despite having an authentication system available.

**Location:** `/api/rag_api_server.py`
- No authentication middleware applied
- No `Depends(auth)` in endpoint definitions
- All endpoints are publicly accessible

**Evidence:**
```python
@app.post("/api/v1/documents/upload") 
async def upload_document(file: UploadFile = File(...)):
    # ❌ No authentication required
```

### 🔴 CRITICAL: Insecure Default Configuration

**Location:** `/apibak/auth/simple_auth.py`

**Issues:**
1. **Authentication disabled by default:**
   ```python
   self.require_auth = os.getenv("RAG_REQUIRE_AUTH", "false").lower() == "true"
   ```

2. **Localhost bypass enabled by default:**
   ```python
   self.localhost_bypass = os.getenv("RAG_LOCALHOST_BYPASS", "true").lower() == "true"
   ```

3. **Predictable default token:**
   ```python
   self.api_token = "rag-local-default-token-2024"
   ```

**Impact:**
- Anyone can access and manipulate the RAG system
- Unauthorized file uploads and deletions
- Data extraction and system manipulation
- No audit trail of actions

---

## 2. CORS Configuration Analysis

### 🔴 CRITICAL: Overly Permissive CORS

**Location:** `/api/rag_api_server.py:64-70`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # ❌ Allows ANY origin
    allow_credentials=True,        # ❌ Dangerous with wildcard
    allow_methods=["*"],           # ❌ Allows ALL methods  
    allow_headers=["*"],           # ❌ Allows ALL headers
)
```

**Security Issues:**
1. **Cross-Origin Resource Sharing with any domain**
2. **CSRF attacks enabled** 
3. **Credential theft through malicious websites**
4. **No same-origin policy protection**

**Attack Scenarios:**
- Malicious website can make requests to API with user credentials
- Data exfiltration through cross-origin requests
- CSRF attacks to modify or delete documents

---

## 3. Input Validation & Sanitization Assessment

### 🔴 CRITICAL: Insufficient Input Validation

#### File Upload Vulnerabilities
**Location:** `/api/rag_api_server.py:1300+`

**Issues:**
1. **No file type validation:**
   ```python
   # Only checks for filename duplicates
   existing_docs = [doc for doc in documents.values() if doc["file_name"] == file.filename]
   ```

2. **No file size limits (consistent):**
   - Batch upload has 100MB limit, single upload doesn't
   - No global file size restrictions

3. **No filename sanitization:**
   - Path traversal vulnerabilities (`../../../etc/passwd`)
   - Special characters in filenames not handled

4. **No content validation:**
   - No malware scanning
   - No magic number verification
   - Relies only on file extensions

#### Query Parameter Injection
**Location:** `/api/rag_api_server.py:1925+`

```python
@app.post("/api/v1/query")
async def query_documents(request: QueryRequest):
    if not request.query.strip():  # ❌ Minimal validation only
        raise HTTPException(status_code=400, detail="查询内容不能为空")
```

**Vulnerabilities:**
- No SQL injection protection
- No XSS filtering  
- No query length limits
- No content sanitization

#### Path Parameter Vulnerabilities
- `document_id` and `task_id` parameters not validated
- Direct usage without sanitization
- Potential for path traversal attacks

---

## 4. Command Injection Assessment

### 🟡 HIGH: Subprocess Command Construction

**Location:** `/raganything/parser.py:580-643`

**Issue:** External command execution with user-controlled input
```python
cmd = [
    "mineru",
    "-p", str(input_path),    # ❌ User-controlled path
    "-o", str(output_dir),    # ❌ User-controlled path  
    "-m", method,             # ❌ User input
]
# ... more user inputs added to cmd
process = subprocess.Popen(cmd, **subprocess_kwargs)
```

**Risk:**
- Command injection through file paths
- Arbitrary command execution
- System compromise

**Mitigation:** Input uses list format (safer than shell=True) but still needs validation.

---

## 5. Information Disclosure

### 🟡 MEDIUM: Sensitive Information Exposure

#### System Information Leakage
**Location:** `/api/rag_api_server.py:390+`

```python
@app.get("/health")
async def health_check():
    return {
        "services": {...},
        "statistics": {...},      # ❌ Internal stats exposed
        "system_checks": {...}    # ❌ System info exposed
    }
```

#### Error Information Disclosure
- Stack traces may be exposed
- File system paths visible in errors
- Internal system architecture revealed

#### Configuration Exposure
- Environment variable names visible
- System paths and directory structure exposed
- Processing capabilities and limitations revealed

---

## 6. Data Storage Security

### 🟡 MEDIUM: File Storage Issues

**Issues:**
1. **Unencrypted file storage:**
   - Uploaded files stored in plaintext
   - No encryption at rest

2. **Predictable file paths:**
   - Files stored with original names
   - Predictable directory structure

3. **No access controls:**
   - File system permissions not managed
   - No isolation between users/sessions

---

## 7. Session & State Management

### 🟡 MEDIUM: Insecure Session Handling

**Issues:**
1. **No session management:**
   - No user sessions tracked
   - No session timeouts

2. **State persistence security:**
   - Document state stored in JSON files
   - No encryption of sensitive state data
   - Race conditions in concurrent access

---

## Threat Model Analysis

### Attack Vectors

1. **Unauthenticated Access**
   - **Likelihood:** Very High
   - **Impact:** Critical
   - **Vector:** Direct API access

2. **Cross-Site Request Forgery (CSRF)**
   - **Likelihood:** High  
   - **Impact:** High
   - **Vector:** Malicious website + permissive CORS

3. **File Upload Attacks**
   - **Likelihood:** High
   - **Impact:** High
   - **Vector:** Malicious file uploads

4. **Command Injection**
   - **Likelihood:** Medium
   - **Impact:** Critical
   - **Vector:** Crafted file paths/parameters

5. **Information Disclosure**
   - **Likelihood:** High
   - **Impact:** Medium
   - **Vector:** Error messages, health checks

### Risk Matrix

| Vulnerability | Likelihood | Impact | Overall Risk | Priority |
|---------------|------------|---------|--------------|----------|
| No Authentication | Very High | Critical | 🔴 Critical | P0 |
| Permissive CORS | High | High | 🔴 Critical | P0 |
| Input Validation | High | High | 🔴 Critical | P0 |
| Command Injection | Medium | Critical | 🟠 High | P1 |
| Info Disclosure | High | Medium | 🟡 Medium | P2 |
| File Storage | Medium | Medium | 🟡 Medium | P2 |

---

## Security Hardening Recommendations

### 🔴 P0: Critical Immediate Actions

#### 1. Enable Authentication
```python
# In rag_api_server.py
from apibak.auth.simple_auth import get_current_user_required

@app.post("/api/v1/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_required)  # ✅ Add auth
):
```

#### 2. Secure CORS Configuration
```python
# Replace permissive CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # ✅ Specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],                     # ✅ Specific methods
    allow_headers=["Authorization", "Content-Type"],                    # ✅ Specific headers
)
```

#### 3. Input Validation Framework
```python
from typing import List
import re
import magic

def validate_filename(filename: str) -> bool:
    """Validate and sanitize filename"""
    if not filename or len(filename) > 255:
        return False
    
    # Block path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
        
    # Only allow safe characters
    safe_pattern = re.compile(r'^[a-zA-Z0-9._-]+$')
    return safe_pattern.match(filename)

def validate_file_content(file_content: bytes, allowed_types: List[str]) -> bool:
    """Validate file content using magic numbers"""
    try:
        file_type = magic.from_buffer(file_content, mime=True)
        return file_type in allowed_types
    except:
        return False

# Usage in upload endpoint
if not validate_filename(file.filename):
    raise HTTPException(status_code=400, detail="Invalid filename")
    
content = await file.read()
if not validate_file_content(content, ["application/pdf", "text/plain"]):
    raise HTTPException(status_code=400, detail="Invalid file type")
```

### 🟠 P1: High Priority Actions

#### 1. Command Injection Prevention
```python
import shlex
from pathlib import Path

def safe_path_validation(path_str: str) -> Path:
    """Safely validate and normalize file paths"""
    try:
        path = Path(path_str).resolve()
        # Ensure path is within allowed directories
        allowed_dirs = [Path("/upload_dir").resolve(), Path("/output_dir").resolve()]
        
        for allowed_dir in allowed_dirs:
            try:
                path.relative_to(allowed_dir)
                return path
            except ValueError:
                continue
        
        raise ValueError("Path outside allowed directories")
    except:
        raise ValueError("Invalid path")

def safe_command_construction(input_path: str, output_dir: str, method: str):
    """Safely construct command with validation"""
    # Validate all inputs
    validated_input = safe_path_validation(input_path)
    validated_output = safe_path_validation(output_dir)
    
    # Whitelist allowed methods
    allowed_methods = ["auto", "text", "ocr"]
    if method not in allowed_methods:
        raise ValueError("Invalid method")
    
    return [
        "mineru",
        "-p", str(validated_input),
        "-o", str(validated_output),
        "-m", method
    ]
```

#### 2. Rate Limiting
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/v1/documents/upload")
@limiter.limit("10/minute")  # ✅ Rate limit uploads
async def upload_document(request: Request, file: UploadFile = File(...)):
```

### 🟡 P2: Medium Priority Actions

#### 1. Security Headers
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Add security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
app.add_middleware(HTTPSRedirectMiddleware)  # Force HTTPS in production

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

#### 2. Secure File Storage
```python
import hashlib
from cryptography.fernet import Fernet

class SecureFileManager:
    def __init__(self, storage_dir: str, encryption_key: bytes):
        self.storage_dir = Path(storage_dir)
        self.fernet = Fernet(encryption_key)
    
    def secure_filename(self, original_name: str) -> str:
        """Generate secure filename"""
        timestamp = int(time.time())
        hash_value = hashlib.sha256(f"{original_name}{timestamp}".encode()).hexdigest()[:16]
        extension = Path(original_name).suffix
        return f"{hash_value}{extension}"
    
    def store_file(self, content: bytes, filename: str) -> str:
        """Store file with encryption"""
        secure_name = self.secure_filename(filename)
        encrypted_content = self.fernet.encrypt(content)
        
        file_path = self.storage_dir / secure_name
        with open(file_path, "wb") as f:
            f.write(encrypted_content)
        
        return secure_name
```

#### 3. Audit Logging
```python
import logging
from datetime import datetime

security_logger = logging.getLogger("security_audit")

def log_security_event(event_type: str, user_id: str, details: dict):
    """Log security-relevant events"""
    security_logger.info({
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "details": details,
        "source_ip": request.client.host if request else None
    })

# Usage in endpoints
@app.post("/api/v1/documents/upload")
async def upload_document(...):
    log_security_event("FILE_UPLOAD", current_user, {
        "filename": file.filename,
        "size": file.size
    })
```

---

## Implementation Timeline

### Phase 1: Critical Fixes (Week 1)
- [ ] Enable authentication on all endpoints
- [ ] Configure restrictive CORS policy  
- [ ] Implement basic input validation
- [ ] Add file type and size validation

### Phase 2: High Priority (Week 2-3)
- [ ] Implement rate limiting
- [ ] Add command injection protection
- [ ] Security headers middleware
- [ ] Audit logging system

### Phase 3: Medium Priority (Week 4-6)
- [ ] Secure file storage with encryption
- [ ] Session management
- [ ] Comprehensive monitoring
- [ ] Security testing framework

---

## Testing & Validation

### Security Test Cases

1. **Authentication Tests:**
   - Verify unauthenticated requests are rejected
   - Test token validation logic
   - Verify secure token storage

2. **Input Validation Tests:**
   - Test file upload with malicious files
   - Path traversal attack attempts
   - SQL injection in query parameters
   - XSS payload injection

3. **CORS Tests:**
   - Cross-origin request validation
   - Credential handling verification
   - Preflight request handling

4. **Rate Limiting Tests:**
   - Verify rate limits are enforced
   - Test rate limit bypass attempts

### Security Scanning Tools
- **OWASP ZAP** for vulnerability scanning
- **Bandit** for Python security analysis
- **Safety** for dependency vulnerability checking
- **Semgrep** for custom security rules

---

## Conclusion

The RAG-Anything API currently operates with **critical security vulnerabilities** that require immediate attention. The lack of authentication, permissive CORS configuration, and insufficient input validation create significant risks for data theft, system compromise, and service disruption.

**Immediate actions required:**
1. Enable authentication on all endpoints
2. Configure restrictive CORS policies
3. Implement comprehensive input validation
4. Add security monitoring and logging

The provided implementation guide offers concrete solutions for addressing these vulnerabilities. Security should be treated as a top priority before deploying this system to any production or shared environment.

---

**Report Generated:** 2025-09-04  
**Auditor:** Claude (Security Specialist)  
**Severity:** 🔴 CRITICAL - Immediate Action Required