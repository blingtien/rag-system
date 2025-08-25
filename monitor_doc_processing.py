#!/usr/bin/env python3
"""
Real-time Document Processing Monitor
Monitors the parsing process of a document with WebSocket and polling
"""

import asyncio
import json
import sys
import time
from datetime import datetime
import requests
import websockets
from typing import Dict, Any, Optional
import threading

class DocumentProcessingMonitor:
    def __init__(self, base_url: str, task_id: str, document_id: str):
        self.base_url = base_url
        self.task_id = task_id
        self.document_id = document_id
        self.ws_url = f"ws://127.0.0.1:8001/ws/task/{task_id}"
        self.start_time = time.time()
        self.last_status = None
        self.error_count = 0
        self.progress_data = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        color = {
            "INFO": "\033[0m",      # Default
            "SUCCESS": "\033[92m",   # Green
            "WARNING": "\033[93m",   # Yellow
            "ERROR": "\033[91m",     # Red
            "PROGRESS": "\033[94m"    # Blue
        }
        color_code = color.get(level, "\033[0m")
        reset_code = "\033[0m"
        print(f"{color_code}[{timestamp}] [{level}] {message}{reset_code}")
        
    async def monitor_websocket(self):
        """Monitor processing via WebSocket"""
        self.log(f"Connecting to WebSocket: {self.ws_url}", "INFO")
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                self.log("WebSocket connected successfully", "SUCCESS")
                
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=60)
                        data = json.loads(message)
                        
                        # Process WebSocket message
                        self.process_update(data)
                        
                        # Check if processing is complete
                        if data.get("status") in ["completed", "failed", "error"]:
                            self.log(f"Processing finished with status: {data.get('status')}", 
                                   "SUCCESS" if data.get("status") == "completed" else "ERROR")
                            break
                            
                    except asyncio.TimeoutError:
                        self.log("WebSocket timeout - checking status via HTTP", "WARNING")
                        await self.poll_status()
                    except websockets.exceptions.ConnectionClosed:
                        self.log("WebSocket connection closed", "WARNING")
                        break
                    except Exception as e:
                        self.log(f"WebSocket error: {str(e)}", "ERROR")
                        self.error_count += 1
                        if self.error_count > 5:
                            break
                        
        except Exception as e:
            self.log(f"Failed to connect to WebSocket: {str(e)}", "ERROR")
            self.log("Falling back to polling method", "WARNING")
            await self.monitor_polling()
            
    async def monitor_polling(self):
        """Monitor processing via HTTP polling"""
        self.log("Starting HTTP polling monitor", "INFO")
        
        while True:
            try:
                await self.poll_status()
                
                # Check if processing is complete
                if self.last_status and self.last_status.get("status") in ["completed", "failed", "error"]:
                    self.log(f"Processing finished with status: {self.last_status.get('status')}", 
                           "SUCCESS" if self.last_status.get("status") == "completed" else "ERROR")
                    break
                    
                await asyncio.sleep(2)  # Poll every 2 seconds
                
            except Exception as e:
                self.log(f"Polling error: {str(e)}", "ERROR")
                self.error_count += 1
                if self.error_count > 10:
                    break
                await asyncio.sleep(5)
                
    async def poll_status(self):
        """Poll the status via HTTP"""
        try:
            # Get detailed status
            response = requests.get(f"{self.base_url}/api/v1/tasks/{self.task_id}/detailed-status")
            if response.status_code == 200:
                data = response.json()
                self.process_update(data)
                self.last_status = data
            else:
                self.log(f"Failed to get status: {response.status_code}", "ERROR")
                
        except Exception as e:
            self.log(f"HTTP request error: {str(e)}", "ERROR")
            
    def process_update(self, data: Dict[str, Any]):
        """Process status update data"""
        status = data.get("status", "unknown")
        progress = data.get("progress", 0)
        message = data.get("message", "")
        
        # Log progress
        if progress > 0:
            elapsed = time.time() - self.start_time
            self.log(f"Progress: {progress:.1f}% | Status: {status} | Elapsed: {elapsed:.1f}s", "PROGRESS")
            
        # Log specific messages
        if message:
            self.log(f"Message: {message}", "INFO")
            
        # Check for errors
        if "error" in data:
            self.log(f"ERROR: {data.get('error')}", "ERROR")
            self.error_count += 1
            
        # Log stage information
        if "current_stage" in data:
            self.log(f"Current Stage: {data.get('current_stage')}", "INFO")
            
        # Log performance metrics
        if "metrics" in data:
            metrics = data.get("metrics", {})
            if metrics:
                self.log(f"Metrics: Pages={metrics.get('pages_processed', 0)}, "
                        f"Content Items={metrics.get('content_items', 0)}, "
                        f"Images={metrics.get('images_processed', 0)}", "INFO")
                
        # Store progress data
        self.progress_data.append({
            "timestamp": time.time(),
            "status": status,
            "progress": progress,
            "message": message
        })
        
    def get_final_results(self):
        """Get final parsing results"""
        self.log("Fetching final parsing results...", "INFO")
        
        try:
            # Get document details
            response = requests.get(f"{self.base_url}/api/v1/documents/{self.document_id}")
            if response.status_code == 200:
                doc_data = response.json()
                
                self.log("=" * 60, "INFO")
                self.log("FINAL PARSING RESULTS", "SUCCESS")
                self.log("=" * 60, "INFO")
                
                # Basic info
                self.log(f"Document: {doc_data.get('filename', 'Unknown')}", "INFO")
                self.log(f"Status: {doc_data.get('parse_status', 'Unknown')}", "INFO")
                self.log(f"Total processing time: {time.time() - self.start_time:.2f} seconds", "INFO")
                
                # Content statistics
                if "content_stats" in doc_data:
                    stats = doc_data.get("content_stats", {})
                    self.log(f"Content Statistics:", "INFO")
                    self.log(f"  - Total pages: {stats.get('total_pages', 0)}", "INFO")
                    self.log(f"  - Text blocks: {stats.get('text_blocks', 0)}", "INFO")
                    self.log(f"  - Images: {stats.get('images', 0)}", "INFO")
                    self.log(f"  - Tables: {stats.get('tables', 0)}", "INFO")
                    self.log(f"  - Equations: {stats.get('equations', 0)}", "INFO")
                    
                # Error information
                if doc_data.get("parse_error"):
                    self.log(f"Parse Error: {doc_data.get('parse_error')}", "ERROR")
                    
                # Processing stages
                if "processing_stages" in doc_data:
                    stages = doc_data.get("processing_stages", {})
                    self.log("Processing Stages:", "INFO")
                    for stage, info in stages.items():
                        status = "✓" if info.get("completed") else "✗"
                        self.log(f"  {status} {stage}: {info.get('status', 'Unknown')}", "INFO")
                        
                self.log("=" * 60, "INFO")
                
                # Save detailed results
                self.save_results(doc_data)
                
            else:
                self.log(f"Failed to get document details: {response.status_code}", "ERROR")
                
        except Exception as e:
            self.log(f"Error fetching final results: {str(e)}", "ERROR")
            
    def save_results(self, data: Dict[str, Any]):
        """Save processing results to file"""
        filename = f"parsing_results_{self.document_id}_{int(time.time())}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "document_id": self.document_id,
                    "task_id": self.task_id,
                    "processing_time": time.time() - self.start_time,
                    "error_count": self.error_count,
                    "progress_data": self.progress_data,
                    "final_data": data
                }, f, indent=2, ensure_ascii=False)
            self.log(f"Results saved to: {filename}", "SUCCESS")
        except Exception as e:
            self.log(f"Failed to save results: {str(e)}", "ERROR")
            
    async def start_monitoring(self):
        """Start the monitoring process"""
        self.log("=" * 60, "INFO")
        self.log("DOCUMENT PROCESSING MONITOR", "INFO")
        self.log("=" * 60, "INFO")
        self.log(f"Document ID: {self.document_id}", "INFO")
        self.log(f"Task ID: {self.task_id}", "INFO")
        self.log(f"API Server: {self.base_url}", "INFO")
        self.log("=" * 60, "INFO")
        
        # Try WebSocket first, fall back to polling if needed
        await self.monitor_websocket()
        
        # Get final results
        self.get_final_results()
        
        # Summary
        self.log("=" * 60, "INFO")
        self.log("MONITORING COMPLETE", "SUCCESS")
        self.log(f"Total errors encountered: {self.error_count}", 
               "WARNING" if self.error_count > 0 else "INFO")
        self.log("=" * 60, "INFO")

async def main():
    """Main function"""
    # Configuration
    BASE_URL = "http://127.0.0.1:8001"
    TASK_ID = "be3e2112-d95c-4792-aa29-86104e4ab174"
    DOCUMENT_ID = "8338d4ff-4f1e-4e4e-abae-046213088a7a"
    
    # Create and start monitor
    monitor = DocumentProcessingMonitor(BASE_URL, TASK_ID, DOCUMENT_ID)
    await monitor.start_monitoring()

if __name__ == "__main__":
    asyncio.run(main())