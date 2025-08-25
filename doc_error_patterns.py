#!/usr/bin/env python3
"""
DOC Processing Error Pattern Detection
Regex patterns and utilities for detecting DOC processing failures and corruption
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ErrorPattern:
    """Error pattern definition"""
    name: str
    pattern: str
    severity: str  # "critical", "warning", "info"
    description: str
    action: str

class DOCErrorPatternDetector:
    """Detects various DOC processing error patterns"""
    
    # Core error patterns for DOC processing
    ERROR_PATTERNS = [
        # Character encoding corruption patterns
        ErrorPattern(
            name="repeated_char_corruption",
            pattern=r"^(.)\1{20,}",
            severity="critical", 
            description="Single character repeated 20+ times indicating encoding corruption",
            action="Flag as encoding corruption, retry with different encoding parameters"
        ),
        
        ErrorPattern(
            name="chinese_encoding_corruption",
            pattern=r"[规]{10,}|[锟]{3,}|[烫]{3,}|[鎻]{3,}",
            severity="critical",
            description="Common Chinese character encoding corruption patterns",
            action="LibreOffice encoding issue, try alternative DOC parser"
        ),
        
        ErrorPattern(
            name="unicode_replacement_chars",
            pattern=r"[\ufffd]{5,}|[\u0000-\u001f]{10,}",
            severity="critical",
            description="Multiple Unicode replacement or control characters",
            action="Severe encoding corruption, document unreadable"
        ),
        
        # Content quality issues
        ErrorPattern(
            name="minimal_content",
            pattern=r"^.{0,50}$",
            severity="warning",
            description="Suspiciously short content after processing large DOC file",
            action="Check if content extraction failed or file is mostly non-text"
        ),
        
        ErrorPattern(
            name="no_readable_text",
            pattern=r"^[\W\s]*$",
            severity="warning", 
            description="No readable text content, only whitespace/symbols",
            action="Content extraction failed, file may be corrupted or image-only"
        ),
        
        # LibreOffice process errors
        ErrorPattern(
            name="libreoffice_conversion_fail",
            pattern=r"LibreOffice.*(?:failed|error|conversion.*failed)",
            severity="critical",
            description="LibreOffice subprocess reported conversion failure",
            action="LibreOffice process failed, check system dependencies and file permissions"
        ),
        
        ErrorPattern(
            name="libreoffice_timeout",
            pattern=r"LibreOffice.*timeout|conversion.*timeout",
            severity="warning",
            description="LibreOffice conversion process timed out",
            action="Large file or performance issue, increase timeout or process in chunks"
        ),
        
        # File format issues
        ErrorPattern(
            name="unsupported_doc_format", 
            pattern=r"unsupported.*format|unknown.*doc.*format",
            severity="warning",
            description="DOC file format not supported by current parser",
            action="Try alternative DOC parser or convert file manually"
        ),
        
        ErrorPattern(
            name="corrupted_doc_file",
            pattern=r"corrupted.*doc|damaged.*document|invalid.*doc.*structure",
            severity="critical",
            description="DOC file structure is corrupted or damaged",
            action="File is unrecoverable, request user to provide uncorrupted version"
        ),
        
        # RAG insertion issues
        ErrorPattern(
            name="rag_insertion_empty",
            pattern=r"inserted.*0.*chunks|empty.*content.*list",
            severity="warning",
            description="RAG insertion completed but no chunks were created",
            action="Content extraction succeeded but produced no indexable content"
        ),
        
        ErrorPattern(
            name="rag_insertion_fail",
            pattern=r"RAG.*insertion.*failed|lightrag.*error",
            severity="critical",
            description="RAG system failed to index the extracted content",
            action="RAG system issue, check database connectivity and disk space"
        ),
        
        # Memory and resource issues
        ErrorPattern(
            name="memory_exhaustion",
            pattern=r"memory.*error|out.*of.*memory|OOM",
            severity="critical",
            description="System ran out of memory during DOC processing",
            action="File too large for available memory, increase memory or process in chunks"
        ),
        
        ErrorPattern(
            name="disk_space_full",
            pattern=r"no.*space.*left|disk.*full|insufficient.*disk.*space",
            severity="critical", 
            description="Insufficient disk space during processing",
            action="Clean up temporary files or increase available disk space"
        )
    ]
    
    # Status reporting inconsistency patterns
    STATUS_INCONSISTENCY_PATTERNS = [
        ErrorPattern(
            name="success_with_no_content",
            pattern=r"processing.*successful.*content_length.*0",
            severity="warning",
            description="Processing reported successful but content length is 0",
            action="False positive success, investigate content extraction"
        ),
        
        ErrorPattern(
            name="success_with_corrupted_content", 
            pattern=r"processing.*successful.*content.*[规锟烫]{10,}",
            severity="critical",
            description="Processing successful but content is clearly corrupted",
            action="LibreOffice encoding issue masquerading as success"
        )
    ]
    
    def __init__(self):
        """Initialize the error pattern detector"""
        self.compiled_patterns = {}
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Pre-compile all regex patterns for performance"""
        all_patterns = self.ERROR_PATTERNS + self.STATUS_INCONSISTENCY_PATTERNS
        
        for pattern_obj in all_patterns:
            try:
                self.compiled_patterns[pattern_obj.name] = re.compile(pattern_obj.pattern, re.MULTILINE | re.UNICODE)
            except re.error as e:
                logger.error(f"Failed to compile pattern '{pattern_obj.name}': {e}")
    
    def detect_content_corruption(self, content: str) -> List[Dict]:
        """
        Detect content corruption patterns in extracted text
        
        Args:
            content: Extracted text content to analyze
            
        Returns:
            List of detected issues with details
        """
        issues = []
        
        corruption_patterns = [
            "repeated_char_corruption",
            "chinese_encoding_corruption", 
            "unicode_replacement_chars",
            "minimal_content",
            "no_readable_text"
        ]
        
        for pattern_name in corruption_patterns:
            if pattern_name in self.compiled_patterns:
                regex = self.compiled_patterns[pattern_name]
                pattern_obj = next(p for p in self.ERROR_PATTERNS if p.name == pattern_name)
                
                if regex.search(content):
                    issues.append({
                        "type": "content_corruption",
                        "pattern": pattern_name,
                        "severity": pattern_obj.severity,
                        "description": pattern_obj.description,
                        "action": pattern_obj.action,
                        "sample": content[:100] if content else "No content"
                    })
                    
        return issues
    
    def detect_log_errors(self, log_text: str) -> List[Dict]:
        """
        Detect error patterns in log text
        
        Args:
            log_text: Log text to analyze
            
        Returns:
            List of detected log errors with details
        """
        issues = []
        
        log_patterns = [
            "libreoffice_conversion_fail",
            "libreoffice_timeout", 
            "unsupported_doc_format",
            "corrupted_doc_file",
            "rag_insertion_empty",
            "rag_insertion_fail",
            "memory_exhaustion",
            "disk_space_full"
        ]
        
        for pattern_name in log_patterns:
            if pattern_name in self.compiled_patterns:
                regex = self.compiled_patterns[pattern_name]
                pattern_obj = next(p for p in self.ERROR_PATTERNS if p.name == pattern_name)
                
                matches = regex.findall(log_text)
                if matches:
                    issues.append({
                        "type": "log_error",
                        "pattern": pattern_name,
                        "severity": pattern_obj.severity,
                        "description": pattern_obj.description,
                        "action": pattern_obj.action,
                        "matches": matches[:3]  # Limit to first 3 matches
                    })
                    
        return issues
    
    def detect_status_inconsistencies(self, status_data: Dict) -> List[Dict]:
        """
        Detect inconsistencies between reported status and actual results
        
        Args:
            status_data: Document status data to analyze
            
        Returns:
            List of detected inconsistencies
        """
        issues = []
        
        # Check for success with no content
        if (status_data.get("status") == "processed" and 
            status_data.get("content_length", 0) == 0):
            issues.append({
                "type": "status_inconsistency",
                "pattern": "success_with_no_content",
                "severity": "warning",
                "description": "Status shows processed but content length is 0",
                "action": "Investigate content extraction failure"
            })
        
        # Check for success with corrupted content
        content_summary = status_data.get("content_summary", "")
        if (status_data.get("status") == "processed" and 
            re.search(r"[规锟烫]{10,}", content_summary)):
            issues.append({
                "type": "status_inconsistency", 
                "pattern": "success_with_corrupted_content",
                "severity": "critical",
                "description": "Status shows processed but content is corrupted",
                "action": "LibreOffice encoding issue, content unusable"
            })
            
        return issues
    
    def analyze_doc_processing(self, content: str, log_text: str, status_data: Dict) -> Dict:
        """
        Comprehensive analysis of DOC processing results
        
        Args:
            content: Extracted text content
            log_text: Processing log text  
            status_data: Document status data
            
        Returns:
            Analysis results with all detected issues
        """
        analysis = {
            "content_issues": self.detect_content_corruption(content),
            "log_issues": self.detect_log_errors(log_text),
            "status_issues": self.detect_status_inconsistencies(status_data),
            "overall_health": "unknown"
        }
        
        # Determine overall health
        critical_issues = [
            issue for issues in analysis.values() 
            if isinstance(issues, list)
            for issue in issues 
            if issue.get("severity") == "critical"
        ]
        
        warning_issues = [
            issue for issues in analysis.values()
            if isinstance(issues, list) 
            for issue in issues
            if issue.get("severity") == "warning"
        ]
        
        if critical_issues:
            analysis["overall_health"] = "critical"
        elif warning_issues:
            analysis["overall_health"] = "warning"
        else:
            analysis["overall_health"] = "healthy"
        
        analysis["summary"] = {
            "critical_count": len(critical_issues),
            "warning_count": len(warning_issues),
            "total_issues": len(critical_issues) + len(warning_issues)
        }
        
        return analysis
    
    def get_pattern_documentation(self) -> str:
        """Generate documentation for all error patterns"""
        doc = "# DOC Processing Error Patterns\n\n"
        
        for pattern in self.ERROR_PATTERNS:
            doc += f"## {pattern.name}\n"
            doc += f"**Severity:** {pattern.severity}\n"
            doc += f"**Pattern:** `{pattern.pattern}`\n"
            doc += f"**Description:** {pattern.description}\n"
            doc += f"**Recommended Action:** {pattern.action}\n\n"
            
        return doc

# Usage example and testing functions
def test_error_patterns():
    """Test the error pattern detection with sample data"""
    detector = DOCErrorPatternDetector()
    
    # Test corrupted content
    corrupted_content = "规规规规规规规规规规规规规规规规规规规规规规规规规规规规"
    content_issues = detector.detect_content_corruption(corrupted_content)
    print(f"Content corruption detected: {len(content_issues)} issues")
    
    # Test log errors
    sample_log = "LibreOffice conversion failed: encoding error"
    log_issues = detector.detect_log_errors(sample_log)
    print(f"Log errors detected: {len(log_issues)} issues")
    
    # Test status inconsistency
    sample_status = {
        "status": "processed",
        "content_length": 0,
        "content_summary": "规规规规规规规规规规规规规"
    }
    status_issues = detector.detect_status_inconsistencies(sample_status)
    print(f"Status inconsistencies: {len(status_issues)} issues")

if __name__ == "__main__":
    # Generate pattern documentation
    detector = DOCErrorPatternDetector()
    print(detector.get_pattern_documentation())
    
    # Run tests
    test_error_patterns()