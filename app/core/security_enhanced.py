"""
Enhanced security measures and vulnerability assessment tools.
Provides rate limiting, security monitoring, vulnerability scanning, and threat detection.
"""

import logging
import uuid
import asyncio
import hashlib
import secrets
import re
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from ipaddress import ip_address, ip_network
import json

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

@dataclass
class SecurityEvent:
    """Security event for monitoring and alerting."""
    event_type: str
    severity: str  # low, medium, high, critical
    source_ip: str
    user_id: Optional[int] = None
    endpoint: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration."""
    requests: int
    window_seconds: int
    burst_allowance: int = 0


class SecurityMonitor:
    """
    Security monitoring system for tracking threats and anomalies.
    """
    
    def __init__(self):
        self.events: List[SecurityEvent] = []
        self.blocked_ips: Set[str] = set()
        self.suspicious_patterns: Dict[str, int] = defaultdict(int)
        self.max_events = 10000
    
    def log_event(self, event: SecurityEvent):
        """Log a security event."""
        self.events.append(event)
        
        # Keep only recent events
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # Auto-block IPs with critical events
        if event.severity == "critical":
            self.blocked_ips.add(event.source_ip)
            logger.warning(f"Auto-blocked IP {event.source_ip} due to critical security event")
        
        # Track suspicious patterns
        pattern_key = f"{event.event_type}:{event.source_ip}"
        self.suspicious_patterns[pattern_key] += 1
        
        # Alert on repeated suspicious activity
        if self.suspicious_patterns[pattern_key] >= 5:
            logger.warning(f"Repeated suspicious activity detected: {pattern_key}")
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked."""
        return ip in self.blocked_ips
    
    def block_ip(self, ip: str, reason: str = "Manual block"):
        """Block an IP address."""
        self.blocked_ips.add(ip)
        self.log_event(SecurityEvent(
            event_type="ip_blocked",
            severity="high",
            source_ip=ip,
            details={"reason": reason}
        ))
    
    def unblock_ip(self, ip: str):
        """Unblock an IP address."""
        self.blocked_ips.discard(ip)
        self.log_event(SecurityEvent(
            event_type="ip_unblocked",
            severity="medium",
            source_ip=ip
        ))
    
    def get_recent_events(self, hours: int = 24) -> List[SecurityEvent]:
        """Get recent security events."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [event for event in self.events if event.timestamp > cutoff]
    
    def get_threat_summary(self) -> Dict[str, Any]:
        """Get threat summary statistics."""
        recent_events = self.get_recent_events()
        
        severity_counts = defaultdict(int)
        event_type_counts = defaultdict(int)
        top_source_ips = defaultdict(int)
        
        for event in recent_events:
            severity_counts[event.severity] += 1
            event_type_counts[event.event_type] += 1
            top_source_ips[event.source_ip] += 1
        
        return {
            "total_events_24h": len(recent_events),
            "blocked_ips": len(self.blocked_ips),
            "severity_distribution": dict(severity_counts),
            "event_types": dict(event_type_counts),
            "top_source_ips": dict(sorted(top_source_ips.items(), key=lambda x: x[1], reverse=True)[:10])
        }


class RateLimiter:
    """
    Advanced rate limiting with multiple strategies and burst protection.
    """
    
    def __init__(self):
        self.requests: Dict[str, List[datetime]] = defaultdict(list)
        self.rules: Dict[str, RateLimitRule] = {
            "default": RateLimitRule(requests=100, window_seconds=60),
            "auth": RateLimitRule(requests=5, window_seconds=60),
            "api": RateLimitRule(requests=1000, window_seconds=3600),
            "upload": RateLimitRule(requests=10, window_seconds=300)
        }
    
    def is_allowed(self, identifier: str, rule_name: str = "default") -> bool:
        """Check if request is allowed under rate limit."""
        rule = self.rules.get(rule_name, self.rules["default"])
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=rule.window_seconds)
        
        # Clean old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ]
        
        # Check rate limit
        current_requests = len(self.requests[identifier])
        
        if current_requests >= rule.requests:
            return False
        
        # Record this request
        self.requests[identifier].append(now)
        return True
    
    def get_remaining_requests(self, identifier: str, rule_name: str = "default") -> int:
        """Get remaining requests in current window."""
        rule = self.rules.get(rule_name, self.rules["default"])
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=rule.window_seconds)
        
        # Clean old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ]
        
        current_requests = len(self.requests[identifier])
        return max(0, rule.requests - current_requests)
    
    def add_rule(self, name: str, rule: RateLimitRule):
        """Add a new rate limiting rule."""
        self.rules[name] = rule


class VulnerabilityScanner:
    """
    Vulnerability scanner for detecting common security issues.
    """
    
    def __init__(self):
        self.sql_injection_patterns = [
            r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
            r"(--|#|/\*|\*/)",
            r"(\b(or|and)\s+\d+\s*=\s*\d+)",
            r"(\'\s*(or|and)\s*\'\w*\'\s*=\s*\'\w*)",
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
        ]
        
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e\\",
        ]
    
    def scan_sql_injection(self, text: str) -> List[str]:
        """Scan for SQL injection patterns."""
        findings = []
        text_lower = text.lower()
        
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                findings.append(f"Potential SQL injection: {pattern}")
        
        return findings
    
    def scan_xss(self, text: str) -> List[str]:
        """Scan for XSS patterns."""
        findings = []
        
        for pattern in self.xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                findings.append(f"Potential XSS: {pattern}")
        
        return findings
    
    def scan_path_traversal(self, text: str) -> List[str]:
        """Scan for path traversal patterns."""
        findings = []
        
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                findings.append(f"Potential path traversal: {pattern}")
        
        return findings
    
    def scan_request(self, request: Request) -> List[str]:
        """Comprehensive request vulnerability scan."""
        findings = []
        
        # Scan URL parameters
        for key, value in request.query_params.items():
            findings.extend(self.scan_sql_injection(value))
            findings.extend(self.scan_xss(value))
            findings.extend(self.scan_path_traversal(value))
        
        # Scan headers
        for key, value in request.headers.items():
            if key.lower() not in ["authorization", "cookie"]:  # Skip sensitive headers
                findings.extend(self.scan_xss(value))
                findings.extend(self.scan_path_traversal(value))
        
        # Scan path
        findings.extend(self.scan_path_traversal(str(request.url.path)))
        
        return findings


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive security middleware with multiple protection layers.
    """
    
    def __init__(self, app, security_monitor: SecurityMonitor, rate_limiter: RateLimiter, vulnerability_scanner: VulnerabilityScanner):
        super().__init__(app)
        self.security_monitor = security_monitor
        self.rate_limiter = rate_limiter
        self.vulnerability_scanner = vulnerability_scanner
        
        # Trusted IP networks (private networks)
        self.trusted_networks = [
            ip_network("10.0.0.0/8"),
            ip_network("172.16.0.0/12"),
            ip_network("192.168.0.0/16"),
            ip_network("127.0.0.0/8"),
        ]
    
    def get_client_ip(self, request: Request) -> str:
        """Get client IP address with proxy support."""
        # Check X-Forwarded-For header
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct connection
        return request.client.host if request.client else "unknown"
    
    def is_trusted_ip(self, ip: str) -> bool:
        """Check if IP is in trusted networks."""
        try:
            ip_addr = ip_address(ip)
            return any(ip_addr in network for network in self.trusted_networks)
        except ValueError:
            return False
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request through security layers."""
        start_time = datetime.utcnow()
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        client_ip = self.get_client_ip(request)
        
        # Check if IP is blocked
        if self.security_monitor.is_ip_blocked(client_ip):
            self.security_monitor.log_event(SecurityEvent(
                event_type="blocked_ip_attempt",
                severity="high",
                source_ip=client_ip,
                endpoint=str(request.url.path)
            ))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Rate limiting (skip for trusted IPs)
        if not self.is_trusted_ip(client_ip):
            rule_name = self.get_rate_limit_rule(request)
            
            if not self.rate_limiter.is_allowed(client_ip, rule_name):
                self.security_monitor.log_event(SecurityEvent(
                    event_type="rate_limit_exceeded",
                    severity="medium",
                    source_ip=client_ip,
                    endpoint=str(request.url.path),
                    details={"rule": rule_name}
                ))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
        
        # Vulnerability scanning
        vulnerabilities = self.vulnerability_scanner.scan_request(request)
        if vulnerabilities:
            self.security_monitor.log_event(SecurityEvent(
                event_type="vulnerability_detected",
                severity="high",
                source_ip=client_ip,
                endpoint=str(request.url.path),
                details={"vulnerabilities": vulnerabilities}
            ))
            
            # Block request if critical vulnerabilities found
            if len(vulnerabilities) >= 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Request blocked due to security concerns"
                )
        
        # Process request
        try:
            response = await call_next(request)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault("X-XSS-Protection", "0")
            response.headers[REQUEST_ID_HEADER] = request_id
            
            # Log successful request
            duration = (datetime.utcnow() - start_time).total_seconds()
            if duration > 5.0:  # Log slow requests
                self.security_monitor.log_event(SecurityEvent(
                    event_type="slow_request",
                    severity="low",
                    source_ip=client_ip,
                    endpoint=str(request.url.path),
                    details={"duration": duration}
                ))
            
            return response
            
        except HTTPException as e:
            # Log HTTP errors
            if e.status_code >= 400:
                severity = "high" if e.status_code >= 500 else "medium"
                self.security_monitor.log_event(SecurityEvent(
                    event_type="http_error",
                    severity=severity,
                    source_ip=client_ip,
                    endpoint=str(request.url.path),
                    details={"status_code": e.status_code, "detail": e.detail}
                ))
            raise
        
        except Exception as e:
            # Log unexpected errors
            self.security_monitor.log_event(SecurityEvent(
                event_type="server_error",
                severity="critical",
                source_ip=client_ip,
                endpoint=str(request.url.path),
                details={"error": str(e)}
            ))
            raise
    
    def get_rate_limit_rule(self, request: Request) -> str:
        """Determine rate limit rule based on request."""
        path = request.url.path
        
        if "/auth/" in path:
            return "auth"
        elif "/api/" in path:
            return "api"
        elif request.method in ["POST", "PUT", "PATCH"] and "upload" in path:
            return "upload"
        else:
            return "default"


class CSRFProtection:
    """
    CSRF protection with token validation.
    """
    
    def __init__(self):
        self.tokens: Dict[str, datetime] = {}
        self.token_lifetime = timedelta(hours=1)
    
    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session."""
        token = secrets.token_urlsafe(32)
        self.tokens[token] = datetime.utcnow()
        return token
    
    def validate_token(self, token: str) -> bool:
        """Validate CSRF token."""
        if token not in self.tokens:
            return False
        
        # Check if token is expired
        if datetime.utcnow() - self.tokens[token] > self.token_lifetime:
            del self.tokens[token]
            return False
        
        return True
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens."""
        now = datetime.utcnow()
        expired_tokens = [
            token for token, created_at in self.tokens.items()
            if now - created_at > self.token_lifetime
        ]
        
        for token in expired_tokens:
            del self.tokens[token]


class SecurityAudit:
    """
    Security audit tools for compliance and assessment.
    """
    
    def __init__(self, security_monitor: SecurityMonitor):
        self.security_monitor = security_monitor
    
    def generate_security_report(self, days: int = 7) -> Dict[str, Any]:
        """Generate comprehensive security report."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        events = [event for event in self.security_monitor.events if event.timestamp > cutoff]
        
        # Categorize events
        categories = defaultdict(list)
        for event in events:
            categories[event.event_type].append(event)
        
        # Calculate risk score
        risk_score = self.calculate_risk_score(events)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(events)
        
        return {
            "report_period": f"{days} days",
            "total_events": len(events),
            "risk_score": risk_score,
            "event_categories": {
                category: len(event_list) for category, event_list in categories.items()
            },
            "blocked_ips": len(self.security_monitor.blocked_ips),
            "recommendations": recommendations,
            "compliance_status": self.check_compliance(events)
        }
    
    def calculate_risk_score(self, events: List[SecurityEvent]) -> int:
        """Calculate overall risk score (0-100)."""
        if not events:
            return 0
        
        severity_weights = {"low": 1, "medium": 3, "high": 7, "critical": 15}
        total_weight = sum(severity_weights.get(event.severity, 0) for event in events)
        
        # Normalize to 0-100 scale
        max_possible = len(events) * 15  # All critical
        risk_score = min(100, int((total_weight / max_possible) * 100)) if max_possible > 0 else 0
        
        return risk_score
    
    def generate_recommendations(self, events: List[SecurityEvent]) -> List[str]:
        """Generate security recommendations based on events."""
        recommendations = []
        
        # Count event types
        event_counts = defaultdict(int)
        for event in events:
            event_counts[event.event_type] += 1
        
        # Generate specific recommendations
        if event_counts["rate_limit_exceeded"] > 10:
            recommendations.append("Consider implementing more aggressive rate limiting")
        
        if event_counts["vulnerability_detected"] > 5:
            recommendations.append("Review and strengthen input validation")
        
        if event_counts["blocked_ip_attempt"] > 20:
            recommendations.append("Consider implementing geographic IP filtering")
        
        if event_counts["server_error"] > 10:
            recommendations.append("Investigate and fix recurring server errors")
        
        if len(self.security_monitor.blocked_ips) > 50:
            recommendations.append("Review blocked IP list and implement automatic cleanup")
        
        return recommendations
    
    def check_compliance(self, events: List[SecurityEvent]) -> Dict[str, str]:
        """Check compliance with security standards."""
        compliance = {}
        
        # Check logging compliance
        if len(events) > 0:
            compliance["logging"] = "compliant"
        else:
            compliance["logging"] = "non_compliant"
        
        # Check incident response
        critical_events = [e for e in events if e.severity == "critical"]
        if len(critical_events) > 0:
            compliance["incident_response"] = "requires_review"
        else:
            compliance["incident_response"] = "compliant"
        
        # Check access control
        blocked_attempts = len([e for e in events if e.event_type == "blocked_ip_attempt"])
        if blocked_attempts > 0:
            compliance["access_control"] = "active"
        else:
            compliance["access_control"] = "passive"
        
        return compliance


# Global security instances
security_monitor = SecurityMonitor()
rate_limiter = RateLimiter()
vulnerability_scanner = VulnerabilityScanner()
csrf_protection = CSRFProtection()
security_audit = SecurityAudit(security_monitor)


def create_security_middleware():
    """Create security middleware with all protection layers."""
    return SecurityMiddleware(
        app=None,  # Will be set by FastAPI
        security_monitor=security_monitor,
        rate_limiter=rate_limiter,
        vulnerability_scanner=vulnerability_scanner
    )


async def get_security_status() -> Dict[str, Any]:
    """Get comprehensive security status."""
    return {
        "threat_summary": security_monitor.get_threat_summary(),
        "blocked_ips": len(security_monitor.blocked_ips),
        "rate_limiter_rules": len(rate_limiter.rules),
        "recent_events": len(security_monitor.get_recent_events()),
        "security_report": security_audit.generate_security_report(1)  # Last 24 hours
    }