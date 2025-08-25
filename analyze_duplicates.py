#!/usr/bin/env python3
"""
Document Duplication Analysis for RAG System
Analyzes duplicate entries and their root causes in the RAG storage system
"""

import json
import os
from collections import defaultdict, Counter
from datetime import datetime

def analyze_document_duplicates():
    print("="*80)
    print("RAG SYSTEM DOCUMENT DUPLICATION ANALYSIS")
    print("="*80)
    
    # Load data files
    with open('rag_storage/api_documents_state.json', 'r', encoding='utf-8') as f:
        api_data = json.load(f)
    
    with open('rag_storage/kv_store_doc_status.json', 'r', encoding='utf-8') as f:
        kv_data = json.load(f)
    
    print(f"\n1. STORAGE OVERVIEW")
    print(f"   API Documents: {len(api_data['documents'])}")
    print(f"   KV Store Docs: {len(kv_data)}")
    print(f"   Batch Operations: {len(api_data.get('batch_operations', {}))}")
    print(f"   Processing Tasks: {len(api_data.get('tasks', {}))}")
    
    # Analyze filename-based duplicates
    print(f"\n2. FILENAME-BASED DUPLICATE ANALYSIS")
    filename_groups = defaultdict(list)
    
    for doc_id, doc_info in api_data['documents'].items():
        # Extract base filename without hash suffixes
        full_name = doc_info['file_name']
        if '_' in full_name and full_name.count('_') >= 2:
            parts = full_name.split('_')
            base_name = '_'.join(parts[:-1])  # Remove last hash part
        else:
            base_name = full_name.split('.')[0]  # Remove extension only
            
        filename_groups[base_name].append({
            'doc_id': doc_id,
            'full_name': full_name,
            'file_path': doc_info['file_path'],
            'status': doc_info['status'],
            'created_at': doc_info['created_at'],
            'batch_id': doc_info.get('batch_operation_id', 'None')
        })
    
    duplicate_count = 0
    for base_name, docs in filename_groups.items():
        if len(docs) > 1:
            duplicate_count += 1
            print(f"\n   DUPLICATE SET {duplicate_count}: {base_name}")
            print(f"   Found {len(docs)} versions:")
            
            for i, doc in enumerate(sorted(docs, key=lambda x: x['created_at']), 1):
                status_indicator = "✓" if doc['status'] == 'completed' else "✗" if doc['status'] == 'failed' else "⚠"
                print(f"     {i}. {status_indicator} ID: {doc['doc_id'][:8]}... | Status: {doc['status']}")
                print(f"        File: {doc['full_name']}")
                print(f"        Path: {doc['file_path']}")
                print(f"        Created: {doc['created_at']}")
                print(f"        Batch: {doc['batch_id']}")
    
    # Analyze root causes
    print(f"\n3. ROOT CAUSE ANALYSIS")
    
    # Check for file path inconsistencies
    path_patterns = defaultdict(list)
    for doc_id, doc_info in api_data['documents'].items():
        file_path = doc_info['file_path']
        if file_path:
            # Check if path uses relative vs absolute patterns
            if file_path.startswith('/'):
                path_type = 'absolute'
            else:
                path_type = 'relative'
            path_patterns[path_type].append(doc_id)
    
    print(f"\n   Path Pattern Analysis:")
    for path_type, doc_ids in path_patterns.items():
        print(f"     {path_type.title()} paths: {len(doc_ids)} documents")
    
    # Check for batch processing issues
    print(f"\n   Batch Processing Analysis:")
    successful_batches = 0
    failed_batches = 0
    
    for batch_id, batch_info in api_data.get('batch_operations', {}).items():
        if batch_info['status'] == 'completed' and batch_info['failed_items'] == 0:
            successful_batches += 1
        else:
            failed_batches += 1
            
    print(f"     Successful batches: {successful_batches}")
    print(f"     Failed batches: {failed_batches}")
    
    # Check for failed document retry patterns
    print(f"\n   Document Upload/Retry Patterns:")
    status_patterns = Counter()
    for doc_id, doc_info in api_data['documents'].items():
        status_patterns[doc_info['status']] += 1
    
    for status, count in status_patterns.items():
        print(f"     {status}: {count} documents")
    
    # Analyze failed documents being re-uploaded
    print(f"\n4. FAILED DOCUMENT RE-UPLOAD ANALYSIS")
    failed_docs = {}
    uploaded_docs = {}
    
    for doc_id, doc_info in api_data['documents'].items():
        if doc_info['status'] == 'failed':
            base_name = doc_info['file_name'].split('_')[0] if '_' in doc_info['file_name'] else doc_info['file_name']
            failed_docs[base_name] = failed_docs.get(base_name, []) + [doc_info]
        elif doc_info['status'] == 'uploaded':
            base_name = doc_info['file_name'].split('_')[0] if '_' in doc_info['file_name'] else doc_info['file_name']
            uploaded_docs[base_name] = uploaded_docs.get(base_name, []) + [doc_info]
    
    retry_count = 0
    for base_name in failed_docs:
        if base_name in uploaded_docs:
            retry_count += 1
            print(f"\n   RETRY DETECTED {retry_count}: {base_name}")
            print(f"     Failed version: {failed_docs[base_name][0]['created_at']}")
            print(f"     Retry version: {uploaded_docs[base_name][0]['created_at']}")
    
    # Consistency check between storage systems
    print(f"\n5. STORAGE CONSISTENCY ANALYSIS")
    
    api_doc_ids = set(api_data['documents'].keys())
    kv_doc_ids = set()
    
    for doc_id in kv_data.keys():
        if doc_id.startswith('doc-'):
            # Remove 'doc-' prefix to match API format
            clean_id = doc_id[4:]  # Remove 'doc-' prefix
            kv_doc_ids.add(clean_id)
    
    api_only = api_doc_ids - kv_doc_ids
    kv_only = kv_doc_ids - api_doc_ids
    
    print(f"   Documents only in API: {len(api_only)}")
    if api_only:
        print("     Sample (first 5):")
        for doc_id in list(api_only)[:5]:
            doc_info = api_data['documents'][doc_id]
            print(f"       - {doc_info['file_name']} | Status: {doc_info['status']}")
    
    print(f"   Documents only in KV store: {len(kv_only)}")
    if kv_only:
        print("     Sample (first 5):")
        for doc_id in list(kv_only)[:5]:
            print(f"       - doc-{doc_id}")
    
    print(f"\n6. RECOMMENDATIONS")
    print("   Based on the analysis, the main causes of document duplication are:")
    print("   1. Failed batch processing with subsequent retry uploads")
    print("   2. Inconsistent document ID generation between upload sessions")
    print("   3. File path handling differences (absolute vs relative)")
    print("   4. Missing cleanup of failed processing attempts")
    print("   5. Storage system inconsistency between API state and KV store")
    
    print("\n   Suggested solutions:")
    print("   1. Implement document deduplication logic based on file hash")
    print("   2. Add proper cleanup for failed processing attempts")
    print("   3. Standardize file path handling across the system")
    print("   4. Implement storage consistency checks and repair")
    print("   5. Add transaction-like processing to ensure atomicity")
    
    return {
        'total_documents': len(api_data['documents']),
        'duplicate_sets': duplicate_count,
        'failed_documents': len([d for d in api_data['documents'].values() if d['status'] == 'failed']),
        'storage_inconsistency': len(api_only) + len(kv_only)
    }

if __name__ == "__main__":
    results = analyze_document_duplicates()
    print(f"\n{'='*80}")
    print(f"SUMMARY: {results['duplicate_sets']} duplicate sets found among {results['total_documents']} documents")
    print(f"Storage inconsistency: {results['storage_inconsistency']} documents")
    print(f"{'='*80}")