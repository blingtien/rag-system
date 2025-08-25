#!/usr/bin/env python3
"""
Check document processing results after completion
"""

import os
import json
import glob
from pathlib import Path
from datetime import datetime

def check_parsing_output(document_id, filename):
    """Check for parsing output files"""
    print("\n" + "="*60)
    print("DOCUMENT PROCESSING RESULTS")
    print("="*60)
    print(f"Document ID: {document_id}")
    print(f"Filename: {filename}")
    print("="*60)
    
    # Check various output directories
    possible_dirs = [
        "./output",
        "./parsed_output", 
        "./rag_storage",
        "./processing_output",
        f"./output/{document_id}",
        f"./parsed_output/{document_id}",
        "./uploads/parsed",
        "./uploads/output"
    ]
    
    results_found = False
    
    for dir_path in possible_dirs:
        if os.path.exists(dir_path):
            print(f"\n📁 Checking directory: {dir_path}")
            
            # Look for files related to this document
            patterns = [
                f"*{document_id}*",
                f"*{filename.split('.')[0]}*",
                f"*国家电网公司电网设备消防管理规定*"
            ]
            
            for pattern in patterns:
                files = glob.glob(os.path.join(dir_path, pattern), recursive=False)
                if files:
                    results_found = True
                    print(f"  Found {len(files)} matching files:")
                    for file in files[:10]:  # Show first 10 matches
                        file_stat = os.stat(file)
                        size_mb = file_stat.st_size / (1024 * 1024)
                        mod_time = datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        print(f"    - {os.path.basename(file)} ({size_mb:.2f} MB, modified: {mod_time})")
                        
                        # Check if it's a JSON file we can read
                        if file.endswith('.json'):
                            try:
                                with open(file, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    if isinstance(data, list):
                                        print(f"      Content items: {len(data)}")
                                        # Count content types
                                        type_counts = {}
                                        for item in data:
                                            t = item.get('type', 'unknown')
                                            type_counts[t] = type_counts.get(t, 0) + 1
                                        print(f"      Content types: {type_counts}")
                                    elif isinstance(data, dict):
                                        print(f"      Keys: {list(data.keys())[:5]}...")
                            except Exception as e:
                                print(f"      Could not read JSON: {e}")
    
    # Check for database storage
    print("\n📊 Checking for database storage:")
    db_files = glob.glob("*.db")
    for db_file in db_files:
        print(f"  Found database: {db_file}")
        try:
            import sqlite3
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Try to find tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"    Tables: {[t[0] for t in tables]}")
            
            # Try to find document-related records
            for table in tables:
                table_name = table[0]
                if 'doc' in table_name.lower() or 'task' in table_name.lower():
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        print(f"    Records in {table_name}: {count}")
                        
                        # Try to find our specific document
                        cursor.execute(f"SELECT * FROM {table_name} WHERE id = ? OR document_id = ? LIMIT 1", 
                                     (document_id, document_id))
                        record = cursor.fetchone()
                        if record:
                            print(f"    ✓ Found record for document {document_id} in {table_name}")
                            results_found = True
                    except Exception as e:
                        pass
            
            conn.close()
        except Exception as e:
            print(f"    Could not read database: {e}")
    
    # Check RAG storage
    print("\n🗂️ Checking RAG storage:")
    rag_dirs = ["./rag_storage", "./working_dir", "./lightrag_storage"]
    for rag_dir in rag_dirs:
        if os.path.exists(rag_dir):
            print(f"  Found RAG directory: {rag_dir}")
            subdirs = [d for d in os.listdir(rag_dir) if os.path.isdir(os.path.join(rag_dir, d))]
            if subdirs:
                print(f"    Subdirectories: {subdirs[:5]}...")
            
            # Check for graph database
            graph_db = os.path.join(rag_dir, "graph_storage.db")
            if os.path.exists(graph_db):
                print(f"    ✓ Found graph database")
                results_found = True
            
            # Check for vector index
            vector_files = glob.glob(os.path.join(rag_dir, "*.index"))
            if vector_files:
                print(f"    ✓ Found {len(vector_files)} vector index files")
                results_found = True
    
    # Summary
    print("\n" + "="*60)
    if results_found:
        print("✅ PROCESSING COMPLETED SUCCESSFULLY")
        print("   Document has been parsed and stored in the system")
    else:
        print("⚠️ WARNING: Could not find processing output files")
        print("   The document may still be processing or stored elsewhere")
    print("="*60)
    
    return results_found

if __name__ == "__main__":
    # Document details
    DOCUMENT_ID = "8338d4ff-4f1e-4e4e-abae-046213088a7a"
    FILENAME = "国家电网公司电网设备消防管理规定_1406604299854.doc"
    
    # Check results
    check_parsing_output(DOCUMENT_ID, FILENAME)